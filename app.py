import streamlit as st
import numpy as np
from datetime import datetime, timedelta
import socket
import os
import sys
import re
import base64
import streamlit.components.v1 as components

# Custom Modules
from core import data
from core import pk_engine as analysis
from io import data_manager as inout
from io import emr_manager as EMR
from utils import utils
from ui import sidebar as ui
from ui import plot_utils as plot
from ui import simulation_tab as sim


# -----------------------------------------------------------------------------
# 0. 오프라인/온라인 환경 확인
# -----------------------------------------------------------------------------
def is_local_environment():
    # 1) 명시적 설정값(환경변수) 우선
    #    - true: 1, true, yes, on
    #    - false: 0, false, no, off
    for env_key in ("PHARMAFRAME_FORCE_OFFLINE", "FORCE_OFFLINE_MODE"):
        raw = os.getenv(env_key)
        if raw is None:
            continue
        val = str(raw).strip().lower()
        if val in ("1", "true", "yes", "on"):
            return True
        if val in ("0", "false", "no", "off"):
            return False

    # 2) fallback: 네트워크 힌트 기반 추정
    try:
        hostname = socket.gethostname()
        ip_addr = socket.gethostbyname(hostname)
        if "localhost" in hostname.lower():
            return True
        return ip_addr.startswith("127.") or ip_addr.startswith("10.") or ip_addr.startswith("192.168.")
    except OSError:
        # stlite/브라우저 런타임 등에서 소켓 조회가 제한될 수 있음
        return True

IS_OFFLINE = is_local_environment()


def _offline_onboarding_flag_path():
    """오프라인 랜딩 완료 상태를 영구 저장할 파일 경로"""
    if getattr(sys, "frozen", False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.abspath(".")
    return os.path.join(base_dir, ".pharmaframe_offline_onboarding_done")


def _load_offline_onboarding_done():
    try:
        with open(_offline_onboarding_flag_path(), "r", encoding="utf-8") as f:
            return f.read().strip() == "1"
    except OSError:
        return False


def _save_offline_onboarding_done():
    try:
        with open(_offline_onboarding_flag_path(), "w", encoding="utf-8") as f:
            f.write("1")
    except OSError:
        pass


def _mark_offline_onboarding_seen(stage):
    """오프라인에서 랜딩 2종 모두 본 경우 영구 스킵 처리"""
    if not IS_OFFLINE:
        return
    if stage == "disclaimer":
        st.session_state.offline_landing_seen_disclaimer = True
    elif stage == "welcome":
        st.session_state.offline_landing_seen_welcome = True

    if (
        st.session_state.get("offline_landing_seen_disclaimer", False)
        and st.session_state.get("offline_landing_seen_welcome", False)
        and not st.session_state.get("offline_onboarding_done", False)
    ):
        st.session_state.offline_onboarding_done = True
        _save_offline_onboarding_done()

# -----------------------------------------------------------------------------
# 1. 페이지 설정 (Page Configuration)
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="PharmaFrame",
    page_icon="💊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 커스텀 테마 CSS 적용
ui.apply_custom_theme()

# -----------------------------------------------------------------------------
# 2. 초기 로딩 및 세션 상태 초기화 (Splash Screen & Session Init)
# -----------------------------------------------------------------------------
# 앱이 처음 로드될 때 빈 화면 대신 로딩 애니메이션을 보여줍니다.
if "initialized" not in st.session_state:
    splash = st.empty()
    with splash.container():
        splash_html = """
            <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; height: 80vh;">
                <div class="st-loader"></div>
                <h2 style="color: #4A90E2; margin-top: 20px; font-family: sans-serif; font-weight: bold;">PharmaFrame</h2>
                <p style="color: #666; font-family: sans-serif; font-size: 0.9em;">__SPLASH_MSG__</p>
            </div>
            <style>
                .st-loader {
                    width: 50px;
                    height: 50px;
                    border: 5px solid #f3f3f3;
                    border-top: 5px solid #4A90E2;
                    border-radius: 50%;
                    animation: spin 1s linear infinite;
                }
                @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
            </style>
        """
        st.markdown(splash_html.replace("__SPLASH_MSG__", utils.t("splash_msg")), unsafe_allow_html=True)


if 'lang' not in st.session_state:
    # URL 파라미터에서 언어 설정 확인 (링크 공유 시 언어 유지)
    url_lang = st.query_params.get("lang", "KO")
    if url_lang in ["KO", "EN"]:
        st.session_state.lang = url_lang
    else:
        st.session_state.lang = "KO"

# 세션 상태 초기화: 새로고침 시에도 데이터가 유지되도록 기본값 설정
if 'user_name' not in st.session_state:
    st.session_state.user_name = utils.t("default_user")
if 'drug_schedule' not in st.session_state:
    st.session_state.drug_schedule = []
if 'drug_schedule_b' not in st.session_state:
    st.session_state.drug_schedule_b = []
if 'compare_mode' not in st.session_state:
    st.session_state.compare_mode = False
if 'user_profile' not in st.session_state:
    st.session_state.user_profile = {
        "name": utils.t("default_user"),
        "weight": 60.0, "height": 170.0, "age": 25, "ast": 20.0, "alt": 20.0, "body_fat": 22.0,
        "first_hrt_date": datetime.now().date()
    }
if 'calibration_factors' not in st.session_state:
    # 경로별 기본값 1.0
    st.session_state.calibration_factors = {
        "Injection": 1.0, "Oral": 1.0, "Transdermal": 1.0, "Sublingual": 1.0
    }
if 'lab_history' not in st.session_state:
    st.session_state.lab_history = {} # 구조: { "Injection": [{"day": 14, "value": 150}, ...], ... }
if 'surgery_mode' not in st.session_state:
    st.session_state.surgery_mode = False
if 'stop_day' not in st.session_state:
    st.session_state.stop_day = 30
if 'is_smoker' not in st.session_state:
    st.session_state.is_smoker = False
if 'history_vte' not in st.session_state:
    st.session_state.history_vte = False
if 'start_date' not in st.session_state:
    # 서버 시간(UTC)에 9시간을 더해 한국/아시아권 사용자들이
    # '오늘 날짜'를 볼 확률을 높여줍니다. (단순 편의성)
    st.session_state.start_date = (datetime.utcnow() + timedelta(hours=9)).date()
if 'anesthesia_type' not in st.session_state:
    st.session_state.anesthesia_type = utils.t("anesthesia_gen")
if 'stop_date' not in st.session_state:
    st.session_state.stop_date = st.session_state.start_date + timedelta(days=30)
if 'resume_date' not in st.session_state:
    st.session_state.resume_date = st.session_state.start_date + timedelta(days=50)
if 'surgery_date' not in st.session_state:
    st.session_state.surgery_date = st.session_state.start_date + timedelta(days=44)
if 'has_spiro' not in st.session_state: st.session_state.has_spiro = False
if 'has_cpa' not in st.session_state: st.session_state.has_cpa = False
if 'has_p4' not in st.session_state: st.session_state.has_p4 = False
if 'has_gnrh' not in st.session_state: st.session_state.has_gnrh = False
if 'selected_interactors' not in st.session_state: st.session_state.selected_interactors = []
if 'resume_day' not in st.session_state:
    st.session_state.resume_day = 50
if 'surg_sim_duration' not in st.session_state:
    st.session_state.surg_sim_duration = max(30, int(st.session_state.resume_day + 30))
if 'unit_choice' not in st.session_state:
    st.session_state.unit_choice = "pg/mL"
if "disclaimer_agreed" not in st.session_state:
    st.session_state.disclaimer_agreed = False
if "offline_landing_seen_disclaimer" not in st.session_state:
    st.session_state.offline_landing_seen_disclaimer = False
if "offline_landing_seen_welcome" not in st.session_state:
    st.session_state.offline_landing_seen_welcome = False
if "offline_onboarding_done" not in st.session_state:
    st.session_state.offline_onboarding_done = IS_OFFLINE and _load_offline_onboarding_done()

# EMR 업로더 로직이 rerun을 유발하므로 탭 생성 전 처리
EMR.init_session()
EMR.handle_mounting()
inout.DataManager.handle_import_session()

# -----------------------------------------------------------------------------
# 3. 캐싱 함수 (Caching Functions for Optimization)
# -----------------------------------------------------------------------------
@st.cache_resource
def get_analyzer(weight, age, ast, alt, body_fat, height):
    """Analyzer 객체 생성 캐싱: 사용자 프로필이 변경되지 않으면 객체를 재사용"""
    return analysis.HormoneAnalyzer(
        user_weight=weight, user_age=age, ast=ast, alt=alt, body_fat=body_fat, user_height=height
    )

# -----------------------------------------------------------------------------
# 4. 사이드바 렌더링 (Sidebar Rendering)
# -----------------------------------------------------------------------------
allow_app_without_landing = IS_OFFLINE and st.session_state.get("offline_onboarding_done", False)
with st.sidebar:
    # 동의 전 랜딩 화면에서는 lang 위젯 충돌 방지를 위해
    # 전체 사이드바(UI의 key="lang" 포함)를 렌더링하지 않습니다.
    if st.session_state.get("disclaimer_agreed", False) or allow_app_without_landing:
        IS_OFFLINE = ui.render_sidebar(IS_OFFLINE)
    else:
        st.title("💊 PharmaFrame")
        st.caption("Personalized Pharmacokinetics Simulator")

# -----------------------------------------------------------------------------
# 5. 로딩 화면 종료 (Clear Splash Screen)
# -----------------------------------------------------------------------------
if "initialized" not in st.session_state:
    st.session_state.initialized = True
    splash.empty()

# -----------------------------------------------------------------------------
# 6. Global Landing Page (사용 동의 -> 사용 설명 -> 약물 입력)
# -----------------------------------------------------------------------------
st.title(utils.t("dashboard_title"))
if not st.session_state.disclaimer_agreed and not allow_app_without_landing:
    with st.container():
        _mark_offline_onboarding_seen("disclaimer")
        st.warning(utils.t("landing_disclaimer_title"))
        st.markdown(f"""
        이 애플리케이션은 약동학(PK) 시뮬레이터입니다.
        
        1. 제공되는 데이터는 일반적인 수학적 모델을 따르며 개인차가 클 수 있습니다.
        2. 이 도구는 의료 기기가 아니며, 임상적 결정을 대체할 수 없습니다.
        3. 반드시 담당 의사 또는 약사와 상의 후 처방에 따르십시오.
        """)
        
        if st.button(utils.t("landing_agree_btn"), type="primary"):
            st.session_state.disclaimer_agreed = True
            st.rerun()
    st.stop()

if not st.session_state.drug_schedule and not allow_app_without_landing:
    with st.container():
        _mark_offline_onboarding_seen("welcome")
        st.info("👋 PharmaFrame에 오신 것을 환영합니다.")
        st.markdown(f"""
        왼쪽 패널(사이드바)에서 다음 단계를 진행해주세요:
        
        1. **임상 모듈 선택**: 갑상선, 폐경 후 요법 등 원하는 환경을 선택하세요.
        2. **신체 정보 입력**: 체중, 연령 등에 따라 시뮬레이션이 보정됩니다.
        3. **약물 스케줄 추가**: 복용할 약물의 용량과 주기를 설정하세요.
        """)
    ui.render_footer()
    st.stop()

# -----------------------------------------------------------------------------
# 7. 메인 콘텐츠 (Main Content)
# -----------------------------------------------------------------------------
tabs_config = [
    {"title": "📈 시뮬레이션 (Simulation)", "key": "sim"},
    {"title": "📊 리포트/데이터 (Export)", "key": "rep"},
    {"title": "❓ 도움말 (FAQ)", "key": "faq"}
]

tab_objs = st.tabs([t["title"] for t in tabs_config])
tabs = {config["key"]: obj for config, obj in zip(tabs_config, tab_objs)}

# -----------------------------------------------------------------------------
# 8. 각 탭 내부 로직
# -----------------------------------------------------------------------------

# [Tab 1: Simulation]
with tabs["sim"]:
    # simulation_tab에서 알아서 PKEngine을 캐싱 및 렌더링함
    sim.render_simulator_tab()

# [Tab 2: Report & Export]
with tabs["rep"]:
    if IS_OFFLINE:
        st.header(utils.t("emr_tab_title"))
        EMR.render_tab_management()
        st.markdown("---")
    
    st.header(utils.t("report_header"))
    c_rep3, c_rep4 = st.columns(2)

    with c_rep3:
        st.subheader("데이터 백업 (JSON)")
        st.caption("현재 입력된 프로필과 약물 스케줄을 파일로 저장합니다.")
        
        json_str = inout.DataManager.export_to_json(
            st.session_state.user_profile, 
            st.session_state.drug_schedule,
            st.session_state.calibration_factors,
            st.session_state.lab_history,
            st.session_state.drug_schedule_b,
            st.session_state.compare_mode
        )
        export_date = datetime.now().strftime('%Y%m%d')
        file_name = f"{st.session_state.user_name}_{export_date}.json"
        st.download_button(utils.t("json_export_btn"), json_str, file_name, "application/json", width="stretch", key="json_export_btn")
        
    with c_rep4:
        st.subheader(utils.t("json_import_label"))
        st.caption("저장된 JSON 파일을 불러와 이전 상태를 복원합니다.")
        st.file_uploader(
            utils.t("json_import_label"), 
            type="json", 
            key=st.session_state.get("import_uploader_key", "json_import_uploader_init")
        )

# [Tab 3: FAQ]
with tabs["faq"]:
    st.markdown("### FAQ")
    st.info("이 앱은 학술 및 교육 목적으로 제작된 시뮬레이터입니다.")

# -----------------------------------------------------------------------------
# 9. 푸터 (Footer)
# -----------------------------------------------------------------------------
ui.render_footer()
