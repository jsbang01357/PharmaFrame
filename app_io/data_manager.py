import json
import io
import csv
import datetime
import os
import sys
import re
from utils import utils
from ui import plot_utils as plot
import uuid

try:
    import requests
except ImportError:
    requests = None

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # 1. PyInstaller 번들 리소스 확인 (_MEIPASS)
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def get_writable_path(filename):
    """다운로드한 파일 등을 저장할 쓰기 가능한 경로 반환"""
    # 실행 파일이 있는 위치 또는 현재 작업 디렉토리 사용
    if getattr(sys, 'frozen', False):
        # PyInstaller로 패키징된 경우 실행 파일 옆에 저장
        return os.path.join(os.path.dirname(sys.executable), filename)
    else:
        return os.path.join(os.path.abspath("."), filename)

# PDF Generation
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    # 한글 폰트 지원을 위한 모듈 (필요시 폰트 파일 경로 지정)
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    REPORTLAB_AVAILABLE = True
except ImportError:
    A4 = None
    canvas = None
    mm = None
    colors = None
    pdfmetrics = None
    TTFont = None
    REPORTLAB_AVAILABLE = False

def ensure_font_exists(font_name="NanumGothic.ttf"):
    """폰트 파일이 없으면 다운로드"""
    # 1. 내장 리소스(또는 개발 경로)에 있는지 확인
    font_path = resource_path(font_name)
    if not os.path.exists(font_path):
        # 2. 없다면 쓰기 가능한 경로에서 확인하거나 다운로드 시도
        writable_font_path = get_writable_path(font_name)
        if os.path.exists(writable_font_path):
            return writable_font_path
            
        # 나눔고딕 폰트 URL (Google Fonts 또는 신뢰할 수 있는 소스)
        url = "https://github.com/google/fonts/raw/main/ofl/nanumgothic/NanumGothic-Regular.ttf"
        if requests is None:
            return None
        try:
            response = requests.get(url)
            if response.status_code == 200:
                with open(writable_font_path, 'wb') as f:
                    f.write(response.content)
                return writable_font_path
        except OSError as e:
            print(f"[inout] Font write failed: {type(e).__name__}: {e}")
            return None # 다운로드 실패
        except requests.RequestException as e:
            print(f"[inout] Font download failed: {type(e).__name__}: {e}")
            return None # 다운로드 실패
    return font_path

class DataManager:
    """
    데이터 저장(JSON), 리포트 생성(PDF), 일정 내보내기(ICS) 담당
    """

    # JSON으로 저장/복원할 사용자 입력 세션 키
    SESSION_EXPORT_KEYS = [
        "lang",
        "user_name",
        "user_profile",
        "drug_schedule",
        "drug_schedule_b",
        "compare_mode",
        "calibration_factors",
        "lab_history",
        "surgery_mode",
        "stop_day",
        "resume_day",
        "start_date",
        "anesthesia_type",
        "stop_date",
        "resume_date",
        "surgery_date",
        "is_smoker",
        "history_vte",
        "has_migraine",
        "has_spiro",
        "has_cpa",
        "has_p4",
        "has_gnrh",
        "selected_interactors",
        "unit_choice",
        "disclaimer_agreed",
        "patient_db",
        "edit_scenario_choice",
        "surg_unit_choice",
    ]

    # 세션 복원 시 허용 타입 스키마 (안전한 allowlist 기반 복원)
    SESSION_TYPE_RULES = {
        "lang": str,
        "user_name": str,
        "user_profile": dict,
        "drug_schedule": list,
        "drug_schedule_b": list,
        "compare_mode": bool,
        "calibration_factors": dict,
        "lab_history": dict,
        "surgery_mode": bool,
        "stop_day": int,
        "resume_day": int,
        "start_date": datetime.date,
        "anesthesia_type": str,
        "stop_date": datetime.date,
        "resume_date": datetime.date,
        "surgery_date": datetime.date,
        "is_smoker": bool,
        "history_vte": bool,
        "has_migraine": bool,
        "has_spiro": bool,
        "has_cpa": bool,
        "has_p4": bool,
        "has_gnrh": bool,
        "selected_interactors": list,
        "unit_choice": str,
        "disclaimer_agreed": bool,
        "patient_db": dict,
        "edit_scenario_choice": str,
        "surg_unit_choice": str,
    }
    
    @staticmethod
    def _json_default(obj):
        if isinstance(obj, (datetime.date, datetime.datetime)):
            return obj.isoformat()
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

    @staticmethod
    def _restore_profile_types(profile):
        """
        JSON/CSV에서 복원된 프로필 값 중 날짜 필드를 원래 타입으로 복원
        """
        if not isinstance(profile, dict):
            return profile

        restored = profile.copy()
        date_fields = ["first_hrt_date"]

        for field in date_fields:
            value = restored.get(field)
            if isinstance(value, str):
                try:
                    restored[field] = datetime.date.fromisoformat(value)
                except ValueError:
                    # ISO 날짜 문자열이 아니면 원본 유지
                    pass

        return restored

    @staticmethod
    def _restore_session_date_fields(session_data):
        """세션 상태의 날짜 필드(string -> date) 복원"""
        if not isinstance(session_data, dict):
            return {}

        restored = dict(session_data)
        date_fields = ["start_date", "stop_date", "resume_date", "surgery_date"]
        for key in date_fields:
            value = restored.get(key)
            if isinstance(value, str):
                try:
                    restored[key] = datetime.date.fromisoformat(value)
                except ValueError:
                    pass

        profile = restored.get("user_profile")
        restored["user_profile"] = DataManager._restore_profile_types(profile) if profile is not None else profile
        return restored

    @staticmethod
    def _sanitize_session_state(session_data):
        """
        allowlist + 타입 검증 기반으로 복원 가능한 세션만 추출.
        검증 실패 키는 무시합니다.
        """
        if not isinstance(session_data, dict):
            return {}

        sanitized = {}
        for key in DataManager.SESSION_EXPORT_KEYS:
            if key not in session_data:
                continue

            expected_type = DataManager.SESSION_TYPE_RULES.get(key)
            value = session_data.get(key)

            # 스키마가 없는 키는 기본적으로 차단
            if expected_type is None:
                continue

            if expected_type is int:
                # bool은 int의 서브클래스이므로 제외
                if isinstance(value, bool) or not isinstance(value, int):
                    continue
            elif not isinstance(value, expected_type):
                continue

            sanitized[key] = value

        # user_profile 날짜 필드 복원 재확인
        if "user_profile" in sanitized:
            sanitized["user_profile"] = DataManager._restore_profile_types(sanitized["user_profile"])
        return sanitized

    @staticmethod
    def _extract_current_session_state():
        """현재 Streamlit 세션에서 저장 가능한 사용자 입력 키만 추출"""
        try:
            import streamlit as st
        except ImportError:
            return {}

        extracted = {}
        for key in DataManager.SESSION_EXPORT_KEYS:
            if key in st.session_state:
                extracted[key] = st.session_state.get(key)
        return extracted

    @staticmethod
    def export_to_json(user_profile, drug_schedule, calibration_factors, lab_history, drug_schedule_b=None, compare_mode=False):
        """현재 세션을 JSON 문자열로 변환"""
        session_snapshot = DataManager._extract_current_session_state()

        # 기존 파라미터 값이 항상 우선되도록 덮어쓰기
        session_snapshot.update({
            "user_profile": user_profile,
            "drug_schedule": drug_schedule,
            "drug_schedule_b": drug_schedule_b or [],
            "compare_mode": compare_mode,
            "calibration_factors": calibration_factors,
            "lab_history": lab_history,
        })

        data = {
            "version": "2.0",
            "timestamp": datetime.datetime.now().isoformat(),
            "profile": user_profile,
            "schedule": drug_schedule,
            "schedule_b": drug_schedule_b or [],
            "compare_mode": compare_mode,
            "calibration_factors": calibration_factors,
            "lab_history": lab_history,
            "session_state": session_snapshot
        }
        return json.dumps(data, indent=4, ensure_ascii=False, default=DataManager._json_default)

    @staticmethod
    def export_db_to_json(patient_db):
        """전체 환자 데이터베이스를 단일 JSON으로 변환"""
        data = {
            "version": "DB_1.0",
            "timestamp": datetime.datetime.now().isoformat(),
            "patients": patient_db
        }
        return json.dumps(data, indent=4, ensure_ascii=False, default=DataManager._json_default)

    @staticmethod
    def export_db_to_csv(patient_db):
        """전체 환자 데이터베이스를 CSV 문자열로 변환"""
        fieldnames = [
            "label", "name", "patient_id", "profile",
            "schedule", "schedule_b", "compare_mode",
            "calibration_factors", "lab_history"
        ]
        rows = []
        for label, data in patient_db.items():
            # 복잡한 구조(dict, list)는 CSV 내에서 JSON 문자열로 저장
            row = {
                "label": label,
                "name": data.get("profile", {}).get("name"),
                "patient_id": data.get("profile", {}).get("patient_id"),
                "profile": json.dumps(data.get("profile"), ensure_ascii=False, default=DataManager._json_default),
                "schedule": json.dumps(data.get("schedule"), ensure_ascii=False, default=DataManager._json_default),
                "schedule_b": json.dumps(data.get("schedule_b", []), ensure_ascii=False, default=DataManager._json_default),
                "compare_mode": data.get("compare_mode", False),
                "calibration_factors": json.dumps(data.get("calibration_factors"), ensure_ascii=False, default=DataManager._json_default),
                "lab_history": json.dumps(data.get("lab_history"), ensure_ascii=False, default=DataManager._json_default)
            }
            rows.append(row)

        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
        # BOM 추가 (utf-8-sig)로 엑셀 한글 깨짐 방지
        return "\ufeff" + output.getvalue()

    @staticmethod
    def load_db_from_csv(csv_file):
        """CSV 파일에서 환자 데이터베이스 복원"""
        if hasattr(csv_file, "read"):
            raw = csv_file.read()
            if isinstance(raw, bytes):
                text = raw.decode("utf-8-sig")
            else:
                text = raw
        else:
            with open(csv_file, "r", encoding="utf-8-sig", newline="") as f:
                text = f.read()

        reader = csv.DictReader(io.StringIO(text))
        db = {}
        for row in reader:
            label = row["label"]
            db[label] = {
                "profile": DataManager._restore_profile_types(json.loads(row.get("profile", "{}"))),
                "schedule": json.loads(row.get("schedule", "[]")),
                "schedule_b": json.loads(row.get("schedule_b", "[]")),
                "compare_mode": str(row.get("compare_mode", "")).strip().lower() in ("true", "1", "yes"),
                "calibration_factors": json.loads(row.get("calibration_factors", "{}")),
                "lab_history": json.loads(row.get("lab_history", "{}"))
            }
        return db

    @staticmethod
    def load_from_json(json_file):
        """JSON 파일에서 데이터 복원 (프로필, 스케줄, 보정계수, 검사이력)"""
        try:
            data = json.load(json_file)
            profile = DataManager._restore_profile_types(data.get("profile"))
            return (
                profile,
                data.get("schedule"), 
                data.get("calibration_factors"), 
                data.get("lab_history"),
                data.get("schedule_b", []),
                data.get("compare_mode", False)
            )
        except (json.JSONDecodeError, AttributeError, TypeError, ValueError) as e:
            print(f"[inout] load_from_json failed: {type(e).__name__}: {e}")
            return None, None, None, None, None, None

    @staticmethod
    def load_full_state_from_json(json_file):
        """JSON 파일에서 전체 세션 상태를 복원 가능한 형태로 로드"""
        try:
            data = json.load(json_file)
        except (json.JSONDecodeError, AttributeError, TypeError, ValueError) as e:
            print(f"[inout] load_full_state_from_json failed: {type(e).__name__}: {e}")
            return None

        session_data = data.get("session_state", {})
        session_data = DataManager._restore_session_date_fields(session_data)
        session_data = DataManager._sanitize_session_state(session_data)
        if not session_data:
            return None
        return session_data

    @staticmethod
    def handle_import_session():
        """리포트 탭의 JSON 가져오기 처리 (탭 생성 전 실행)"""
        import streamlit as st
        import time
        
        # 업로더 키가 없으면 초기화
        if "import_uploader_key" not in st.session_state:
            st.session_state.import_uploader_key = str(uuid.uuid4())
            
        key = st.session_state.import_uploader_key
        
        # 업로더에 파일이 있으면 처리
        if key in st.session_state and st.session_state[key] is not None:
            uploaded_file = st.session_state[key]

            # 데이터 로드 (신규 전체 상태 + 구버전 호환)
            full_state = DataManager.load_full_state_from_json(uploaded_file)
            if full_state is not None:
                for k, v in full_state.items():
                    # 업로더 상태 키는 복원 대상에서 제외
                    if k in ("import_uploader_key", "db_uploader"):
                        continue
                    st.session_state[k] = v

                # 핵심 키 누락 대비 기본값 보정
                if "calibration_factors" not in st.session_state or not isinstance(st.session_state.calibration_factors, dict):
                    st.session_state.calibration_factors = {
                        "Injection": 1.0, "Oral": 1.0, "Transdermal": 1.0, "Sublingual": 1.0
                    }
                if "lab_history" not in st.session_state or not isinstance(st.session_state.lab_history, dict):
                    st.session_state.lab_history = {}
                if "drug_schedule_b" not in st.session_state or not isinstance(st.session_state.drug_schedule_b, list):
                    st.session_state.drug_schedule_b = []
                if "compare_mode" not in st.session_state:
                    st.session_state.compare_mode = False
                if "user_profile" in st.session_state and isinstance(st.session_state.user_profile, dict):
                    st.session_state.user_profile = DataManager._restore_profile_types(st.session_state.user_profile)
                
                # 성공 메시지
                st.toast(utils.t("json_load_success"), icon="✅")
                
                # 업로더 초기화를 위해 키 변경 (무한 루프 방지)
                st.session_state.import_uploader_key = str(uuid.uuid4())
                
                # UI 갱신을 위해 리런
                time.sleep(1)
                st.rerun()
            else:
                st.error(utils.t("json_v2_error"))
                # 실패 파일이 세션에 남아 반복 에러가 나는 것을 방지
                if key in st.session_state:
                    del st.session_state[key]
                st.session_state.import_uploader_key = str(uuid.uuid4())

    @staticmethod
    def generate_ics(
        drug_schedule,
        start_date=None,
        duration_days=90,
        schedule_b=None,
        compare_mode=False,
        surgery_mode=False,
        stop_date=None,
        surgery_date=None,
        resume_date=None,
        anesthesia_type=None,
    ):
        """
        약물 스케줄을 iCalendar(.ics) 포맷으로 변환
        :param start_date: 시뮬레이션 시작일 (datetime.date 객체)
        """
        ics_content = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//PharmaFrame//Medication Schedule//EN",
            "CALSCALE:GREGORIAN"
        ]
        
        # 시작일이 없으면 오늘로 설정
        if start_date is None:
            import datetime
            start_dt = datetime.datetime.now()
        else:
            import datetime
            # date 객체를 datetime 객체로 변환 (시간은 오전 9시로 고정)
            start_dt = datetime.datetime.combine(start_date, datetime.time(9, 0))
        
        all_schedules = []
        if isinstance(drug_schedule, list):
            all_schedules.extend([("A", d) for d in drug_schedule])
        if compare_mode and isinstance(schedule_b, list):
            all_schedules.extend([("B", d) for d in schedule_b])

        for scenario_label, drug in all_schedules:
            interval_days = float(drug.get('interval', 1.0))
            # Generic 에서는 cycling을 사용하지 않으므로 기본값 1
            duration = 1
            
            # 종료일 계산 (시뮬레이션 시작일 기준)
            until_date = start_dt + datetime.timedelta(days=duration_days)
            until_str = until_date.strftime("%Y%m%dT235959")
            
            # 주기에 따른 RRULE 설정 (1일 미만인 경우 HOURLY 사용)
            if interval_days < 1.0:
                interval_hours = round(interval_days * 24)
                rrule = f"RRULE:FREQ=HOURLY;INTERVAL={interval_hours};UNTIL={until_str}"
            else:
                rrule = f"RRULE:FREQ=DAILY;INTERVAL={int(interval_days)};UNTIL={until_str}"

            for d in range(duration):
                first_dose_dt = start_dt
                event_start = first_dose_dt.strftime("%Y%m%dT090000")
                interval_display = f"{interval_days:g} day(s)"
                
                event_block = [
                    "BEGIN:VEVENT",
                    f"DTSTART:{event_start}",
                    f"SUMMARY:💉 [{scenario_label}] {drug['name']} ({drug['dose']}mg)",
                    f"DESCRIPTION:EstroFrame Reminder: scenario={scenario_label}, route={drug['type']}, dose={drug['dose']}mg, interval={interval_display}",
                    rrule,
                    f"UID:{scenario_label}_{drug['id']}_{d}@estroframe.app",
                    "END:VEVENT"
                ]
                ics_content.extend(event_block)

        if surgery_mode:
            surgery_events = []
            if stop_date:
                surgery_events.append(("🛑 HRT Stop", stop_date, "Planned hormone cessation date"))
            if surgery_date:
                surg_desc = "Planned surgery date"
                if anesthesia_type:
                    surg_desc += f" (anesthesia: {anesthesia_type})"
                surgery_events.append(("🏥 Surgery", surgery_date, surg_desc))
            if resume_date:
                surgery_events.append(("🔄 HRT Resume", resume_date, "Planned hormone resumption date"))

            for idx, (summary, date_obj, description) in enumerate(surgery_events):
                if isinstance(date_obj, datetime.datetime):
                    event_dt = date_obj
                else:
                    event_dt = datetime.datetime.combine(date_obj, datetime.time(9, 0))
                event_start = event_dt.strftime("%Y%m%dT090000")
                event_end = (event_dt + datetime.timedelta(minutes=30)).strftime("%Y%m%dT093000")
                event_block = [
                    "BEGIN:VEVENT",
                    f"DTSTART:{event_start}",
                    f"DTEND:{event_end}",
                    f"SUMMARY:{summary}",
                    f"DESCRIPTION:{description}",
                    f"UID:surgery_{idx}@estroframe.app",
                    "END:VEVENT",
                ]
                ics_content.extend(event_block)

        ics_content.append("END:VCALENDAR")
        return "\n".join(ics_content)


class ReportGenerator:
    """PDF 리포트 생성기"""
    
    def __init__(self, buffer):
        self.c = canvas.Canvas(buffer, pagesize=A4)
        self.width, self.height = A4
        
        # [중요] 한글 폰트 등록
        try:
            font_path = ensure_font_exists("NanumGothic.ttf")
            if font_path and os.path.exists(font_path):
                pdfmetrics.registerFont(TTFont('NanumGothic', font_path))
                self.font_name = 'NanumGothic'
            else:
                # 폰트 로드 실패 시 기본 폰트 사용 (한글 깨짐 가능성 있음)
                self.font_name = 'Helvetica'
        except (OSError, ValueError, RuntimeError) as e:
            print(f"[inout] Font initialization fallback: {type(e).__name__}: {e}")
            self.font_name = 'Helvetica'

        self.margin_left = 18 * mm
        self.margin_right = 18 * mm
        self.top_y = self.height - 18 * mm
        self.bottom_y = 18 * mm
        self.current_y = self.top_y
        self.default_font_size = 10
        # 리포트는 흰 배경 기반 + 포인트 컬러만 핑크로 사용
        self.color_primary = colors.HexColor("#FF1493")
        self.color_accent = colors.HexColor("#FF69B4")
        self.color_text = colors.HexColor("#4A1230")
        self.color_muted = colors.HexColor("#A24B79")
        self.color_card_bg = colors.white
        self.color_card_border = colors.HexColor("#FFD6E9")
        self.card_radius = 3 * mm
        self.page_bottom = 12 * mm
        self.app_version = "Ver 1.0.0(260214)"
        self.logo_path = self._resolve_logo_path()
        self.section_icon_labels = {
            "profile": "PF",
            "protocol": "RX",
            "summary": "SM",
            "calibration": "LB",
            "safety": "SF",
            "surgery": "SU",
            "graph": "GR",
            "disclaimer": "DS",
        }

    def _new_page(self):
        self._draw_footer()
        self.c.showPage()
        self.current_y = self.top_y

    def _line_height(self, font_size=None):
        size = font_size if font_size is not None else self.default_font_size
        return size * 1.45

    def _plain_text(self, text):
        if text is None:
            return ""
        t = str(text)
        t = re.sub(r"\*\*(.*?)\*\*", r"\1", t)
        t = re.sub(r"\*(.*?)\*", r"\1", t)
        t = re.sub(r"`(.*?)`", r"\1", t)
        t = t.replace("### ", "").replace("## ", "").replace("# ", "")
        return t

    def _wrap_text(self, text, font_size=None, max_width=None):
        size = font_size if font_size is not None else self.default_font_size
        width = max_width if max_width is not None else (self.width - self.margin_left - self.margin_right)
        lines = []
        for raw in str(text).split("\n"):
            raw = raw.rstrip()
            if not raw:
                lines.append("")
                continue
            words = raw.split(" ")
            current = ""
            for word in words:
                candidate = word if not current else f"{current} {word}"
                try:
                    candidate_w = pdfmetrics.stringWidth(candidate, self.font_name, size)
                except (AttributeError, KeyError, TypeError, ValueError):
                    candidate_w = len(candidate) * (size * 0.55)
                if candidate_w <= width or not current:
                    current = candidate
                else:
                    lines.append(current)
                    current = word
            if current:
                lines.append(current)
        return lines

    def _ensure_space(self, needed_height):
        if self.current_y - needed_height < self.bottom_y:
            self._new_page()

    def _draw_footer(self):
        page_no = self.c.getPageNumber()
        line_y = self.page_bottom + (3 * mm)
        self.c.setStrokeColor(self.color_card_border)
        self.c.setLineWidth(0.6)
        self.c.line(self.margin_left, line_y, self.width - self.margin_right, line_y)
        self.c.setFillColor(self.color_muted)
        self.c.setFont(self.font_name, 8)
        self.c.drawString(self.margin_left, self.page_bottom, "EstroFrame")
        self.c.drawRightString(self.width - self.margin_right, self.page_bottom, f"Page {page_no}")

    def _resolve_logo_path(self):
        candidates = [
            resource_path("estroframe_logo.png"),
            resource_path("assets/estroframe_logo.png"),
            resource_path("logo.png"),
            resource_path("assets/logo.png"),
        ]
        for p in candidates:
            if p and os.path.exists(p):
                return p
        return None

    def _draw_logo_or_mark(self, x, y, size):
        if self.logo_path:
            try:
                from reportlab.lib.utils import ImageReader
                logo_img = ImageReader(self.logo_path)
                self.c.drawImage(
                    logo_img,
                    x,
                    y,
                    width=size,
                    height=size,
                    preserveAspectRatio=True,
                    mask="auto",
                )
                return
            except (ImportError, OSError, TypeError, ValueError) as e:
                print(f"[inout] Logo draw fallback: {type(e).__name__}: {e}")
                pass

        self.c.setFillColor(self.color_accent)
        self.c.roundRect(x, y, size, size, 1.8 * mm, stroke=0, fill=1)
        self.c.setFillColor(colors.white)
        self.c.setFont(self.font_name, 13)
        self.c.drawCentredString(x + (size / 2), y + (size * 0.31), "EF")

    def _draw_section_icon_badge(self, key, x, y):
        label = self.section_icon_labels.get(key, "SE")
        r = 3.4 * mm
        self.c.setFillColor(self.color_accent)
        self.c.circle(x + r, y - r, r, stroke=0, fill=1)
        self.c.setFillColor(colors.white)
        self.c.setFont(self.font_name, 7.5)
        self.c.drawCentredString(x + r, y - r - 2, label)

    def _draw_badge(self, x, y, text, bg_color, text_color=colors.white):
        pad_x = 2.2 * mm
        badge_h = 6.0 * mm
        self.c.setFont(self.font_name, 8.5)
        try:
            text_w = pdfmetrics.stringWidth(text, self.font_name, 8.5)
        except Exception:
            text_w = len(str(text)) * 4.2
        badge_w = text_w + (2 * pad_x)
        self.c.setFillColor(bg_color)
        self.c.roundRect(x, y, badge_w, badge_h, 1.8 * mm, stroke=0, fill=1)
        self.c.setFillColor(text_color)
        self.c.drawString(x + pad_x, y + 1.9 * mm, str(text))
        return badge_w

    def _draw_wrapped(self, text, font_size=None, color=colors.black, indent_mm=0):
        size = font_size if font_size is not None else self.default_font_size
        x = self.margin_left + (indent_mm * mm)
        max_w = self.width - x - self.margin_right
        lines = self._wrap_text(text, font_size=size, max_width=max_w)
        lh = self._line_height(size)
        self._ensure_space(max(lh, lh * len(lines)))
        self.c.setFont(self.font_name, size)
        self.c.setFillColor(color)
        for line in lines:
            self.c.drawString(x, self.current_y, line)
            self.current_y -= lh

    def _draw_card(self, lines, title=None, font_size=9.5):
        if not lines:
            return
        x = self.margin_left
        total_w = self.width - self.margin_left - self.margin_right
        pad_x = 3.5 * mm
        pad_top = 3.0 * mm
        pad_bottom = 2.8 * mm
        text_w = total_w - (2 * pad_x)
        lh = self._line_height(font_size)

        wrapped = []
        for line in lines:
            wrapped.extend(self._wrap_text(line, font_size=font_size, max_width=text_w))

        title_h = 0
        if title:
            title_h = self._line_height(10) + (0.8 * mm)
        needed_h = pad_top + title_h + (lh * max(1, len(wrapped))) + pad_bottom
        self._ensure_space(needed_h + (2 * mm))

        top_y = self.current_y
        y = top_y - needed_h
        self.c.setFillColor(self.color_card_bg)
        self.c.setStrokeColor(self.color_card_border)
        self.c.roundRect(x, y, total_w, needed_h, self.card_radius, stroke=1, fill=1)

        cursor_y = top_y - pad_top
        if title:
            self.c.setFont(self.font_name, 10)
            self.c.setFillColor(self.color_accent)
            self.c.drawString(x + pad_x, cursor_y - self._line_height(10) + 3, title)
            cursor_y -= title_h

        self.c.setFont(self.font_name, font_size)
        self.c.setFillColor(self.color_text)
        for line in wrapped:
            self.c.drawString(x + pad_x, cursor_y - lh + 2, line)
            cursor_y -= lh

        self.current_y = y - (2 * mm)

    def _section_title(self, title, icon_key=None):
        self._ensure_space(11 * mm)
        self.current_y -= 2 * mm
        bar_w = 1.6 * mm
        bar_h = 6.2 * mm
        self.c.setFillColor(self.color_accent)
        icon_offset = 0
        if icon_key:
            self._draw_section_icon_badge(icon_key, self.margin_left, self.current_y + 2)
            icon_offset = 9.0 * mm
        self.c.rect(self.margin_left + icon_offset, self.current_y - bar_h + 1, bar_w, bar_h, stroke=0, fill=1)
        self.c.setFillColor(self.color_primary)
        self.c.setFont(self.font_name, 14)
        self.c.drawString(self.margin_left + icon_offset + (3 * mm), self.current_y - 4, title)
        self.current_y -= 7 * mm
        self.c.setStrokeColor(self.color_card_border)
        self.c.line(self.margin_left, self.current_y, self.width - self.margin_right, self.current_y)
        self.current_y -= 3 * mm

    def draw_header(self, profile=None, sim_data=None):
        box_h = 30 * mm
        self._ensure_space(box_h + (6 * mm))
        y = self.current_y - box_h
        self.c.setFillColor(colors.white)
        self.c.setStrokeColor(self.color_card_border)
        self.c.roundRect(
            self.margin_left,
            y,
            self.width - self.margin_left - self.margin_right,
            box_h,
            self.card_radius,
            stroke=1,
            fill=1,
        )
        logo_size = 12 * mm
        logo_x = self.margin_left + (4 * mm)
        logo_y = y + box_h - logo_size - (4.5 * mm)
        self._draw_logo_or_mark(logo_x, logo_y, logo_size)
        self.c.setFont(self.font_name, 22)
        self.c.setFillColor(self.color_primary)
        self.c.drawString(logo_x + logo_size + (3 * mm), y + box_h - (10 * mm), "EstroFrame Report")
        date_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        self.c.setFont(self.font_name, 9)
        self.c.setFillColor(self.color_muted)
        self.c.drawString(logo_x + logo_size + (3 * mm), y + (5 * mm), f"{utils.t('pdf_generated_on')}: {date_str}")

        # Patient / Version
        if isinstance(profile, dict):
            patient_name = profile.get("name", utils.t("default_user"))
            self.c.setFont(self.font_name, 9)
            self.c.setFillColor(self.color_muted)
            self.c.drawRightString(
                self.width - self.margin_right - (4 * mm),
                y + (5 * mm),
                f"{utils.t('patient_name')}: {patient_name} · {self.app_version}",
            )

        # Quick summary badges
        badge_y = y + (12 * mm)
        badge_x = logo_x + logo_size + (3 * mm)
        if isinstance(sim_data, dict):
            stats = sim_data.get("stats") or {}
            unit = sim_data.get("unit_choice", "pg/mL")
            avg_val = float(stats.get("avg", 0.0) or 0.0)
            peak_val = float(stats.get("peak", 0.0) or 0.0)
            b1 = self._draw_badge(
                badge_x,
                badge_y,
                f"{utils.t('avg')}: {avg_val:.1f} {unit}",
                colors.HexColor("#FF69B4"),
            )
            b2 = self._draw_badge(
                badge_x + b1 + (2 * mm),
                badge_y,
                f"{utils.t('peak')}: {peak_val:.1f} {unit}",
                colors.HexColor("#FF1493"),
            )
            if unit == "pmol/L":
                in_target = 370 <= avg_val <= 740
            else:
                in_target = 100 <= avg_val <= 200
            status_text = "Range OK" if in_target else "Range Check"
            status_color = colors.HexColor("#15803D") if in_target else colors.HexColor("#B45309")
            self._draw_badge(
                badge_x + b1 + b2 + (4 * mm),
                badge_y,
                status_text,
                status_color,
            )

        self.current_y = y - (4 * mm)

    def draw_profile(self, profile):
        self._section_title(utils.t("pdf_profile_title"), icon_key="profile")
        h = float(profile.get("height", 170.0) or 170.0)
        w = float(profile.get("weight", 60.0) or 60.0)
        bmi = w / ((h / 100) ** 2) if h > 0 else 0.0
        lines = [
            f"{utils.t('age_label')}: {profile.get('age', '-')}",
            f"{utils.t('height_label')}: {h:.1f} cm",
            f"{utils.t('weight_label')}: {w:.1f} kg",
            f"BMI: {bmi:.1f}",
            f"{utils.t('body_fat_label')}: {profile.get('body_fat', '-')}",
            f"AST/ALT: {profile.get('ast', '-')}/{profile.get('alt', '-')}",
        ]
        self._draw_card(lines)

    def _route_label(self, route_type):
        route_translation_keys = {
            "Injection": "route_injection",
            "Oral": "route_oral",
            "Transdermal": "route_transdermal",
            "Sublingual": "route_sublingual",
            "Anti-Androgen": "route_anti_androgen",
            "Progesterone": "route_progesterone",
            "GnRH-Agonist": "route_gnrh",
            "Injection (주사)": "route_injection",
            "Oral (경구)": "route_oral",
            "Transdermal (패치/젤)": "route_transdermal",
            "Sublingual (설하)": "route_sublingual",
            "Anti-Androgen (항안드로겐)": "route_anti_androgen",
            "Progesterone (프로게스테론)": "route_progesterone",
            "GnRH-Agonist (사춘기 억제제)": "route_gnrh",
        }
        return utils.t(route_translation_keys.get(route_type, route_type))

    def draw_protocol(self, schedule, title_suffix="A"):
        title = utils.t("pdf_protocol_title")
        if title_suffix:
            title = f"{title} - {title_suffix}"
        self._section_title(title, icon_key="protocol")

        if not schedule:
            self._draw_card(["(empty)"], font_size=10)
            return

        for idx, drug in enumerate(schedule, start=1):
            route_label = self._route_label(drug.get("type", ""))
            freq_text = utils.t("pdf_freq_format").format(
                dose=drug.get("dose", "-"),
                interval=drug.get("interval", "-"),
            )
            lines = [f"{route_label} / {freq_text}"]
            if drug.get("is_cycling"):
                lines.append(f"Cycling: start={drug.get('offset', 0)}, duration={drug.get('duration', 1)}")
            self._draw_card(lines, title=f"{idx}. {drug.get('name', '-')}", font_size=9)

    def draw_simulation_summary(self, sim_data):
        self._section_title("Simulation Summary", icon_key="summary")
        stats = sim_data.get("stats") or {}
        stats_b = sim_data.get("stats_b")
        unit = sim_data.get("unit_choice", "pg/mL")
        sim_duration = sim_data.get("sim_duration", "-")
        compare_mode = bool(sim_data.get("compare_mode", False))

        overview_lines = [
            f"Unit: {unit}",
            f"Duration: {sim_duration} days",
            f"Compare mode: {'ON' if compare_mode else 'OFF'}",
            f"Scenario A drugs: {sim_data.get('scenario_a_count', 'N/A')}",
        ]
        if compare_mode:
            overview_lines.append(f"Scenario B drugs: {sim_data.get('scenario_b_count', 'N/A')}")
        self._draw_card(overview_lines, title="Overview")

        metric_lines = [
            f"{utils.t('peak')}: {stats.get('peak', 0):.1f} {unit}",
            f"{utils.t('trough')}: {stats.get('trough', 0):.1f} {unit}",
            f"{utils.t('avg')}: {stats.get('avg', 0):.1f} {unit}",
            f"{utils.t('fluctuation')}: {stats.get('fluctuation', 0):.1f}%",
            f"{utils.t('max_slope')}: {stats.get('max_slope', 0):.1f} ({unit}/day)",
        ]
        rmse = sim_data.get("rmse")
        if rmse is not None:
            metric_lines.append(f"{utils.t('rmse_label')}: {rmse:.1f} {unit}")
        else:
            metric_lines.append(f"{utils.t('rmse_label')}: N/A")

        rel = sim_data.get("reliability") or {}
        if rel.get("text"):
            metric_lines.append(f"{utils.t('model_rel')}: {rel.get('text')}")
        self._draw_card(metric_lines, title="Key Metrics")

        if compare_mode and isinstance(stats_b, dict):
            b_lines = [
                f"{utils.t('peak')}: {stats_b.get('peak', 0):.1f} {unit}",
                f"{utils.t('trough')}: {stats_b.get('trough', 0):.1f} {unit}",
                f"{utils.t('avg')}: {stats_b.get('avg', 0):.1f} {unit}",
                f"{utils.t('fluctuation')}: {stats_b.get('fluctuation', 0):.1f}%",
                f"{utils.t('max_slope')}: {stats_b.get('max_slope', 0):.1f} ({unit}/day)",
            ]
            self._draw_card(b_lines, title="Scenario B Metrics")

    def draw_calibration_and_labs(self, sim_data):
        self._section_title("Calibration & Lab Data", icon_key="calibration")
        cal_factors = sim_data.get("calibration_factors") or {}
        active = sim_data.get("active_calibrations") or []
        lab_history = sim_data.get("lab_history") or {}

        if active:
            self._draw_card([str(row) for row in active], title="Active calibration factors")
        elif cal_factors:
            self._draw_card([f"{k}: {v:.2f}x" for k, v in cal_factors.items()], title="Calibration factors")
        else:
            self._draw_card(["No calibration applied."], title="Calibration")

        if not lab_history:
            self._draw_card(["No lab records."], title="Lab history")
            return

        lab_lines = []
        for route, records in lab_history.items():
            lab_lines.append(f"{route} ({len(records)} records)")
            for rec in records[:12]:
                lab_lines.append(f"day={rec.get('day', '-')}, value={rec.get('value', '-')} pg/mL")
        self._draw_card(lab_lines, title="Lab history", font_size=9)

    def draw_safety(self, sim_data):
        self._section_title("Clinical Safety Results", icon_key="safety")
        analysis_res = sim_data.get("analysis_res") or {}
        risks = analysis_res.get("risks") or []
        mono = analysis_res.get("monotherapy")
        bone_risk = bool(analysis_res.get("bone_risk"))
        interactors = sim_data.get("selected_interactors") or []

        safety_lines = []
        if not risks and not mono and not bone_risk:
            safety_lines.append("No major warnings detected.")
        else:
            if risks:
                for risk in risks:
                    level = risk.get("level", "INFO")
                    msg = self._plain_text(risk.get("msg", ""))
                    safety_lines.append(f"[{level}] {msg}")

            if mono:
                safety_lines.append(self._plain_text(mono.get('msg', '')))

            if bone_risk:
                safety_lines.append(self._plain_text(utils.t('bone_risk')))
        self._draw_card(safety_lines, title="Risk warnings", font_size=9)

        if interactors:
            self._draw_card([", ".join(map(str, interactors))], title="Selected interacting meds/supplements", font_size=9)

        monitoring_table = sim_data.get("monitoring_table")
        if monitoring_table:
            monitor_lines = []
            for line in monitoring_table.splitlines():
                line = line.strip()
                if not line or line.startswith("| :---"):
                    continue
                if line.startswith("|"):
                    cells = [c.strip(" *") for c in line.strip("|").split("|")]
                    if len(cells) >= 2 and cells[0] != utils.t("monitor_table_header_drug"):
                        monitor_lines.append(f"{cells[0]}: {cells[1]}")
            if monitor_lines:
                self._draw_card(monitor_lines, title="Monitoring checklist", font_size=9)

    def draw_graph(self, sim_data):
        self._new_page()
        self._section_title(utils.t("pdf_graph_title"), icon_key="graph")
        try:
            chart_keys = [
                "t_dates", "t_days", "y_conc", "unit_choice",
                "compare_mode", "y_conc_b",
                "surgery_mode", "stop_day", "resume_day",
                "surgery_date", "start_date", "anesthesia_type",
                "lab_data", "stats", "sim_duration",
            ]
            graph_payload = {k: sim_data.get(k) for k in chart_keys if k != "anesthesia_type" and k != "stats"}
            fig = plot.create_pk_chart(**graph_payload)
            fig.update_layout(
                font=dict(family="NanumGothic, Malgun Gothic, AppleGothic, sans-serif", size=14),
                plot_bgcolor='white',
                paper_bgcolor='white',
            )
            import plotly.io as pio
            img_bytes = pio.to_image(fig, format='png', width=1200, height=680, scale=2)
            from reportlab.lib.utils import ImageReader
            img = ImageReader(io.BytesIO(img_bytes))
            target_h = 130 * mm
            self._ensure_space(target_h + 8 * mm)
            y = self.current_y - target_h
            self.c.drawImage(
                img,
                self.margin_left,
                y,
                width=self.width - self.margin_left - self.margin_right,
                height=target_h,
                preserveAspectRatio=True,
                mask='auto',
            )
            self.current_y = y - 6 * mm
        except (ImportError, RuntimeError, OSError, ValueError, TypeError) as e:
            self._draw_wrapped(f"Graph rendering failed: {e}", font_size=10, color=colors.red)

    def draw_surgery_plan(self, surgery_plan):
        if not surgery_plan:
            return
        self._section_title(utils.t("surg_title"), icon_key="surgery")

        is_on = bool(surgery_plan.get("surgery_mode", False))
        if not is_on:
            self._draw_card(["Surgery mode is OFF."], title="Surgery Plan")
            return

        lines = [
            f"{utils.t('surg_type_label')}: {surgery_plan.get('surgery_type_label', '-')}",
            f"{utils.t('anesthesia_label')}: {surgery_plan.get('anesthesia_type', '-')}",
            f"{utils.t('date_stop_label')}: {surgery_plan.get('stop_date', '-')}",
            f"{utils.t('date_surg_label')}: {surgery_plan.get('surgery_date', '-')}",
            f"{utils.t('date_resume_label')}: {surgery_plan.get('resume_date', '-')}",
        ]
        if surgery_plan.get("recommendation"):
            lines.append(str(surgery_plan.get("recommendation")))
        self._draw_card(lines, title="Surgery Timeline", font_size=9.3)

    def draw_surgery_graph(self, graph_data):
        if not graph_data:
            return
        self._new_page()
        self._section_title(f"{utils.t('pdf_graph_title')} ({utils.t('surg_title')})", icon_key="graph")
        try:
            # Remove keys not supported by create_pk_chart
            clean_graph_data = {k: v for k, v in graph_data.items() if k != "anesthesia_type" and k != "stats"}
            fig = plot.create_pk_chart(**clean_graph_data)
            fig.update_layout(
                font=dict(family="NanumGothic, Malgun Gothic, AppleGothic, sans-serif", size=14),
                plot_bgcolor='white',
                paper_bgcolor='white',
            )
            import plotly.io as pio
            img_bytes = pio.to_image(fig, format='png', width=1200, height=680, scale=2)
            from reportlab.lib.utils import ImageReader
            img = ImageReader(io.BytesIO(img_bytes))
            target_h = 130 * mm
            self._ensure_space(target_h + 8 * mm)
            y = self.current_y - target_h
            self.c.drawImage(
                img,
                self.margin_left,
                y,
                width=self.width - self.margin_left - self.margin_right,
                height=target_h,
                preserveAspectRatio=True,
                mask='auto',
            )
            self.current_y = y - 6 * mm
        except (ImportError, RuntimeError, OSError, ValueError, TypeError) as e:
            self._draw_wrapped(f"Surgery graph rendering failed: {e}", font_size=10, color=colors.red)

    def draw_disclaimer(self):
        self.current_y -= 2 * mm
        self._section_title("Disclaimer", icon_key="disclaimer")
        self._draw_card([utils.t("pdf_disclaimer")], font_size=9)

    def save(self):
        self._draw_footer()
        self.c.save()

def create_pdf(
    profile,
    schedule,
    sim_data,
    schedule_b=None,
    compare_mode=False,
    calibration_factors=None,
    lab_history=None,
    surgery_plan=None,
    surgery_graph_data=None,
):
    """PDF 생성 진입 함수"""
    if not REPORTLAB_AVAILABLE:
        raise RuntimeError("ReportLab is not available in this environment. PDF export is disabled.")

    buffer = io.BytesIO()
    report = ReportGenerator(buffer)
    
    merged_sim_data = dict(sim_data or {})
    if calibration_factors is not None and "calibration_factors" not in merged_sim_data:
        merged_sim_data["calibration_factors"] = dict(calibration_factors)
    if lab_history is not None and "lab_history" not in merged_sim_data:
        merged_sim_data["lab_history"] = dict(lab_history)

    report.draw_header(profile=profile, sim_data=merged_sim_data)
    report.draw_profile(profile)
    report.draw_protocol(schedule, title_suffix="A")
    if compare_mode and schedule_b:
        report.draw_protocol(schedule_b, title_suffix="B")
    report.draw_simulation_summary(merged_sim_data)
    report.draw_calibration_and_labs(merged_sim_data)
    report.draw_safety(merged_sim_data)
    report.draw_surgery_plan(surgery_plan)
    report.draw_graph(merged_sim_data)
    report.draw_surgery_graph(surgery_graph_data)
    report.draw_disclaimer()
    report.save()
    
    buffer.seek(0)
    return buffer
