import datetime
import numpy as np
import json
import os
from core import data
from datetime import datetime, timedelta

"""
EstroFrame Utilities Module
- Unit conversion logic (Estradiol, Testosterone)
- Formatting helpers for UI
- Medical index calculators
"""

# -----------------------------------------------------------------------------
# 0. Internationalization (i18n)
# -----------------------------------------------------------------------------

def _load_translations():
    """Load translation data from i18n.json"""
    try:
        base_path = os.path.dirname(__file__)
        file_path = os.path.join(base_path, "i18n.json")
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"[utils] Failed to load i18n.json: {type(e).__name__}: {e}")
        return {}

TRANSLATIONS = _load_translations()

def t(key):
    """
    Translate a key based on the current session language.
    Default to KO if not set.
    """
    import streamlit as st
    lang = st.session_state.get("lang", "KO")
    # Fallback logic: Selected Lang -> KO -> Key itself
    lang_dict = TRANSLATIONS.get(lang, TRANSLATIONS.get("KO", {}))
    return lang_dict.get(key, key)

def get_localized_desc(drug_info):
    """Get drug description based on language"""
    import streamlit as st
    lang = st.session_state.get("lang", "KO")
    if lang == "EN" and drug_info.desc_en:
        return drug_info.desc_en
    return drug_info.desc

def get_localized_warning(drug_info):
    """Get drug warning message based on language"""
    import streamlit as st
    lang = st.session_state.get("lang", "KO")
    # Note: DrugInfo currently uses warning_msg for both languages or handles it via i18n
    return drug_info.warning_msg

def get_localized_surg_desc(surg_info):
    """Get surgery description based on language"""
    import streamlit as st
    lang = st.session_state.get("lang", "KO")
    if lang == "EN":
        return surg_info.get("desc_en", surg_info.get("desc", ""))
    return surg_info.get("desc", "")


# -----------------------------------------------------------------------------
# 1. Unit Converters (Medical Standards)
# -----------------------------------------------------------------------------

def convert_e2_unit(value, target_unit="pg/mL"):
    """
    Estradiol (E2) Unit Converter
    - Molar Mass of Estradiol: 272.38 g/mol
    - Factor: 1 pg/mL = 3.6713 pmol/L
    """
    factor = 3.6713
    
    if target_unit == "pmol/L":
        return value * factor
    elif target_unit == "pg/mL":
        return value  # Base unit is pg/mL
    else:
        return value

def convert_back_from_pmol(value_pmol):
    """pmol/L -> pg/mL (for internal calculation)"""
    return value_pmol / 3.6713

# -----------------------------------------------------------------------------
# 2. Statistics & Analysis Helpers
# -----------------------------------------------------------------------------

def calculate_stats(concentration_array, t_days=None):
    """
    농도 배열에서 임상적으로 의미 있는 통계 추출
    초기 상승 단계(0에서 시작)와 투약 중단 후 하강 단계를 제외한 '유지기(Steady State)' 기준의 통계를 반환합니다.
    """
    if len(concentration_array) == 0:
        return {"peak": 0, "trough": 0, "avg": 0, "fluctuation": 0, "max_slope": 0}

    peak = max(concentration_array)
    if peak <= 0:
        return {"peak": 0, "trough": 0, "avg": 0, "fluctuation": 0, "max_slope": 0}

    # [NEW] 최대 변화율(Slope) 계산 (단위: pg/mL per Day)
    max_slope = 0
    if t_days is not None and len(t_days) > 1:
        dy = np.diff(concentration_array)
        dt = np.diff(t_days)
        # 절대값 기준 가장 가파른 기울기 추출
        max_slope = np.max(np.abs(dy / dt))

    # 1. 유지기 구간 추출 (첫 피크 도달 시점 ~ 마지막 피크 도달 시점)
    # 초기 0부터 상승하는 구간을 제외하기 위해 첫 번째 피크 근처(99%) 도달 시점을 찾음
    first_peak_idx = 0
    for i, val in enumerate(concentration_array):
        if val >= peak * 0.99:
            first_peak_idx = i
            break
    
    # 마지막 피크 도달 시점을 찾아 수술 모드 등의 중단 이후 하강 구간을 제외
    last_peak_idx = first_peak_idx
    for i in range(len(concentration_array) - 1, -1, -1):
        if concentration_array[i] >= peak * 0.99:
            last_peak_idx = i
            break
    
    # 유지기 배열 설정 (피크가 하나인 경우 그 이후 전체를 대상으로 함)
    if first_peak_idx == last_peak_idx:
        steady_state_array = concentration_array[first_peak_idx:]
    else:
        steady_state_array = concentration_array[first_peak_idx:last_peak_idx + 1]

    trough = min(steady_state_array) if len(steady_state_array) > 0 else peak
    avg = sum(steady_state_array) / len(steady_state_array) if len(steady_state_array) > 0 else peak
    
    # 변동 지수 (Fluctuation Index): (Peak - Trough) / Average
    fluctuation = ((peak - trough) / avg * 100) if avg > 0 else 0
    
    return {
        "peak": peak,
        "trough": trough,
        "avg": avg,
        "fluctuation": fluctuation,
        "max_slope": max_slope
    }

def calculate_rmse(t_days, y_conc, lab_points):
    """
    예측 곡선(t_days, y_conc)과 실제 측정 점들(lab_points) 사이의 RMSE 계산
    :param lab_points: list of (day, value) tuples
    """
    if not lab_points:
        return None
    
    sq_errors = []
    for day, val in lab_points:
        # 시뮬레이션 시간축에서 검사일과 가장 가까운 인덱스 찾기
        idx = (np.abs(t_days - day)).argmin()
        prediction = y_conc[idx]
        sq_errors.append((prediction - val) ** 2)
    
    if not sq_errors:
        return None
        
    return np.sqrt(np.mean(sq_errors))

def check_slope_risk(slope, current_conc):
    """
    농도 변화율(Slope)이 임상적으로 위험한 수준인지 판별
    :param slope: 변화율 (pg/mL per day)
    :param current_conc: 현재 농도 (pg/mL)
    """
    # 기준 1: 절대 변화량 (1000 pg/mL 이상)
    absolute_risk = abs(slope) > 1000.0
    
    # 기준 2: 상대 변화율 (현재 농도의 50% 이상 급변)
    # 농도가 낮을 때는 작은 변화도 크게 느껴질 수 있음
    if current_conc > 0:
        relative_risk = (abs(slope) / current_conc) > 0.5
    else:
        relative_risk = False
        
    return absolute_risk or relative_risk

def calculate_vte_risk_score(profile, is_smoker, history_vte, surgery_risk_level, has_oral_estrogen):
    """
    임상 지침을 기반으로 한 간이 VTE(혈전증) 위험 점수 계산
    """
    score = 0
    
    # 1. BMI (25 이상 +1, 30 이상 +2)
    bmi = profile['weight'] / ((profile['height'] / 100) ** 2)
    if bmi >= 30: score += 2
    elif bmi >= 25: score += 1
    
    # 2. 흡연 (+2)
    if is_smoker: score += 2
    
    # 3. 나이 (40세 이상 +1, 60세 이상 +2)
    if profile['age'] >= 60: score += 2
    elif profile['age'] >= 40: score += 1
    
    # 4. 과거력/가족력 (+3)
    if history_vte: score += 3
    
    # 5. 수술 자체의 위험도
    risk_map = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}
    score += risk_map.get(surgery_risk_level, 0)
    
    # 6. 경구제 사용 여부 (+1)
    if has_oral_estrogen: score += 1
    
    # 등급 판정
    if score <= 2: return score, t("risk_low"), "green"
    if score <= 4: return score, t("risk_mod"), "orange"
    if score <= 6: return score, t("risk_high"), "red"
    return score, t("risk_vhigh"), "#8B0000"

def get_monitoring_messages(drugs, checklist=None):
    """
    처방된 약물 및 체크리스트에 따른 필수 검사 항목을 마크다운 표 형태로 반환
    """
    if checklist is None: checklist = {}
    
    # 중복 제거를 위해 딕셔너리 사용 {약물명: 검사항목}
    monitoring_map = {}

    # Protocol 1 (Drugs)
    for drug in drugs:
        if drug['name'] in data.DRUG_DB:
            db_info = data.DRUG_DB[drug['name']]
            if db_info.monitoring:
                if drug['name'] not in monitoring_map:
                    monitoring_map[drug['name']] = ', '.join(db_info.monitoring)

    # Protocol 2 (Checklist)
    if checklist.get("has_spiro"):
        monitoring_map["Spironolactone"] = "Potassium (K+), Renal Function (eGFR), BP"
    if checklist.get("has_cpa"):
        monitoring_map["Cyproterone Acetate"] = "Liver Function (LFT), Prolactin"
    if checklist.get("has_p4"):
        monitoring_map["Progesterone"] = "Lipid Profile, BP"
    if checklist.get("has_gnrh"):
        monitoring_map["GnRH Agonist"] = "Bone Density (DXA), LH/FSH"
        
    if not monitoring_map:
        return None

    # 마크다운 표 생성
    md_table = f"| {t('monitor_table_header_drug')} | {t('monitor_table_header_exams')} |\n| :--- | :--- |\n"
    for name, exams in monitoring_map.items():
        md_table += f"| **{name}** | {exams} |\n"
        
    return md_table

def check_drug_interactions(current_schedule, other_meds_list):
    """
    current_schedule: 사용자가 복용 중인 HRT 약물 리스트
    other_meds_list: 사용자가 선택한 병용 약물 (예: ['Grapefruit', 'Rifampin'])
    """
    warnings = []
    
    # 1. 사용자의 HRT 약물 특성 파악 (data.DRUG_DB 활용)
    has_estrogen = False
    has_spiro = False
    
    for d in current_schedule:
        name = d.get('name')
        if name in data.DRUG_DB:
            drug_type = data.DRUG_DB[name].type
            if drug_type in ['Oral', 'Injection', 'Transdermal', 'Sublingual']:
                has_estrogen = True
            if name == 'Spironolactone':
                has_spiro = True
    
    for med_name in other_meds_list:
        if med_name not in data.INTERACTION_DB:
            continue
            
        interactor = data.INTERACTION_DB[med_name]
        m_type = interactor['type']
        
        # [Logic A] CYP3A4 상호작용 (에스트로겐)
        if has_estrogen:
            if m_type == "CYP3A4_INHIBITOR":
                warnings.append({
                    "level": "MEDIUM",
                    "title": t("ddi_inhibitor_title").format(med_name=med_name),
                    "msg": t("ddi_inhibitor_msg").format(med_name=med_name)
                })
            elif m_type == "CYP3A4_INDUCER":
                warnings.append({
                    "level": "HIGH",
                    "title": t("ddi_inducer_title").format(med_name=med_name),
                    "msg": t("ddi_inducer_msg").format(med_name=med_name)
                })
        
        # [Logic B] 칼륨/신장 상호작용 (스피로노락톤)
        if has_spiro:
            if m_type in ["K_SPARING", "RENAL_STRESS"]:
                warnings.append({
                    "level": "CRITICAL",
                    "title": t("ddi_spiro_title").format(med_name=med_name),
                    "msg": t("ddi_spiro_msg").format(med_name=med_name)
                })

    return warnings

def perform_safety_analysis(drugs, user_profile, is_smoker, history_vte, has_migraine, stats, stats_b, unit_choice, compare_mode, checklist=None, interactors=None):
    """
    종합적인 임상 안전성 분석 수행 (VTE, 간 독성, 급격한 농도 변화 등)
    """
    if checklist is None: checklist = {}
    risk_messages = []
    
    # A. VTE 리스크 평가
    has_oral_estrogen = any(str(d.get('type', '')).startswith('Oral') for d in drugs)
    user_age = user_profile['age']

    if has_oral_estrogen:
        if user_age > 35 and is_smoker:
            risk_messages.append({
                "level": "CRITICAL",
                "msg": t("risk_vte_smoker")
            })
        elif history_vte:
            risk_messages.append({
                "level": "HIGH",
                "msg": t("risk_vte_history")
            })
    
    if has_migraine and has_oral_estrogen:
        risk_messages.append({
            "level": "HIGH",
            "msg": t("risk_migraine")
        })

    # 청소년기 Tanner Stage 체크
    if 15 <= user_age <= 18:
        risk_messages.append({
            "level": "MEDIUM",
            "msg": t("tanner_stage_msg")
        })

    # 급격한 농도 상승(Dose Dumping) 경고
    spike_limit_pg = data.GUIDELINES["ACUTE_SPIKE"]["e2_max"]
    
    def check_spike(s, label_prefix):
        if s is None: return
        p_pg = s['peak'] if unit_choice == "pg/mL" else convert_back_from_pmol(s['peak'])
        
        # 1. 초고농도 경고 (1500 pg/mL 초과)
        if p_pg > 1500:
            risk_messages.append({
                "level": "HIGH",
                "msg": t("risk_estrogen_super_high")
            })
            
        if p_pg > spike_limit_pg:
            risk_messages.append({
                "level": "MEDIUM",
                "msg": t("risk_dose_dumping").format(label=label_prefix, limit=spike_limit_pg)
            })
    
    check_spike(stats, f"{t('scenario_a')}: " if compare_mode else "")
    if compare_mode:
        check_spike(stats_b, f"{t('scenario_b')}: ")

    # 감정 변화 리스크 (PMS/Mood Swing)
    trough_pg = stats['trough'] if unit_choice == "pg/mL" else convert_back_from_pmol(stats['trough'])
    slope_pg = stats['max_slope'] if unit_choice == "pg/mL" else convert_back_from_pmol(stats['max_slope'])
    avg_pg = stats['avg'] if unit_choice == "pg/mL" else convert_back_from_pmol(stats['avg'])

    is_slope_risky = check_slope_risk(slope_pg, avg_pg)

    if trough_pg < 50 or is_slope_risky:
        reason = []
        if trough_pg < 50: reason.append(t("reason_low_trough"))
        if is_slope_risky: reason.append(t("reason_high_slope"))
        risk_messages.append({
            "level": "MEDIUM",
            "msg": t("risk_mood_swing").format(reasons=', '.join(reason))
        })

    # 프로게스테론 부작용 체크
    has_p4_check = checklist.get("has_p4", False)
    has_p4_drug = any(d.get('type') == 'Progesterone' for d in drugs)
    if has_p4_drug or has_p4_check:
        risk_messages.append({
            "level": "MEDIUM",
            "msg": t("risk_p4_side_effect")
        })

    # 간 수치 체크
    ast_val = user_profile.get('ast', 20.0)
    alt_val = user_profile.get('alt', 20.0)
    if ast_val > 40 or alt_val > 40:
        risk_messages.append({
            "level": "HIGH",
            "msg": t("liver_risk").format(ast=ast_val, alt=alt_val)
        })

    # D. 약물 상호작용 분석
    if interactors:
        interaction_warnings = check_drug_interactions(drugs, interactors)
        for w in interaction_warnings:
            risk_messages.append({
                "level": w["level"],
                "msg": f"**{w['title']}**: {w['msg']}"
            })

    # C. 단독 요법 및 골밀도 피드백
    has_aa = any("Anti-Androgen" in d['type'] for d in drugs)
    has_aa_check = checklist.get("has_spiro") or checklist.get("has_cpa") or checklist.get("has_gnrh")
    is_combo_therapy = has_aa or has_aa_check
    monotherapy_status = None
    
    if trough_pg > 200:
        monotherapy_status = {"type": "success", "msg": t("monotherapy_success")}
    elif trough_pg < 100:
        if is_combo_therapy:
            monotherapy_status = {"type": "info", "msg": t("combo_info")}
        else:
            monotherapy_status = {"type": "warning", "msg": t("low_estrogen_warning")}
            
    bone_risk = False
    if trough_pg < 50:
        bone_risk = True

    return {
        "risks": risk_messages,
        "monotherapy": monotherapy_status,
        "bone_risk": bone_risk
    }

def get_reliability_info(rmse, unit_choice="pg/mL"):
    """
    RMSE 수치에 따른 모델 신뢰도 등급 및 색상 반환
    """
    if rmse is None:
        return "N/A", "grey"
    
    # pg/mL 기준으로 정규화하여 판단 (1 pg/mL = 3.6713 pmol/L)
    rmse_pg = rmse if unit_choice == "pg/mL" else rmse / 3.6713
    
    if rmse_pg < 20:
        return t("rel_exc"), "green"
    elif rmse_pg < 50:
        return t("rel_good"), "orange"
    else:
        return t("rel_poor"), "red"

# -----------------------------------------------------------------------------
# 3. UI Formatting Helpers
# -----------------------------------------------------------------------------

def get_risk_badge(risk_level):
    """
    위험도에 따른 색상 마크다운 배지 반환
    Streamlit에서 st.markdown(..., unsafe_allow_html=True)로 사용
    """
    colors = {
        "LOW": "green",
        "MEDIUM": "orange",
        "HIGH": "red",
        "CRITICAL": "#8B0000" # Dark Red
    }
    color = colors.get(risk_level, "grey")
    labels = {
        "LOW": t("risk_low"),
        "MEDIUM": t("risk_mod"),
        "HIGH": t("risk_high"),
        "CRITICAL": t("risk_vhigh"),
    }
    label = labels.get(risk_level, risk_level)
    return f":{color}[**{label}**]"

def format_duration(days):
    """일수를 사람이 읽기 편한 문자열로 변환"""
    if days >= 30:
        months = days / 30
        return t("fmt_months").format(months=months, days=int(days))
    elif days >= 7:
        weeks = days / 7
        return t("fmt_weeks").format(weeks=weeks, days=int(days))
    else:
        return t("fmt_days").format(days=int(days))

# -----------------------------------------------------------------------------
# 4. Date Helpers
# -----------------------------------------------------------------------------

def get_next_injection_date(start_date_str, interval_days):
    """
    마지막 투여일로부터 다음 투여 예정일 계산
    """
    try:
        start = datetime.datetime.strptime(start_date_str, "%Y-%m-%d")
        next_date = start + datetime.timedelta(days=interval_days)
        return next_date.strftime("%Y-%m-%d")
    except (TypeError, ValueError):
        return "-"

# -----------------------------------------------------------------------------
# 5. Tanner stage 계산
# -----------------------------------------------------------------------------
def predict_feminization_stage(total_hrt_months, avg_e2):
    """
    전체 치료 기간과 현재 평균 농도를 기반으로 Tanner Stage를 예측합니다.
    """
    # 1. 농도에 따른 효율성 계수 (Quality Factor)
    # WPATH 기준 100pg/mL 이상일 때 최적의 효율을 보인다고 가정
    if avg_e2 < 50:
        efficiency = 0.5  # 농도가 너무 낮으면 변화 속도를 절반으로 계산
    elif avg_e2 < 100:
        efficiency = 0.8
    else:
        efficiency = 1.0  # 적정 농도 이상
    
    # 2. 보정된 유효 개월 수 계산
    effective_months = total_hrt_months * efficiency
    
    # 3. 타임라인 데이터(data.py)와 매칭
    if effective_months < 3:
        return t("ts_1_label"), t("ts_1_desc")
    elif effective_months < 6:
        return t("ts_2_label"), t("ts_2_desc")
    elif effective_months < 12:
        return t("ts_3_label"), t("ts_3_desc")
    elif effective_months < 24:
        return t("ts_4_label"), t("ts_4_desc")
    else:
        return t("ts_5_label"), t("ts_5_desc")


# -----------------------------------------------------------------------------
# 6. Missed Dose Action Guide (50% Rule)
# -----------------------------------------------------------------------------
def calculate_missed_dose_action(last_dose_dt, interval_days, current_dt=None):
    """
    복약 잊음(Missed Dose) 시 행동 가이드 계산 (50% Rule)
    :param last_dose_dt: 마지막으로 약을 먹은/맞은 시간 (datetime)
    :param interval_days: 투여 간격 (일 단위, float)
    :param current_dt: 현재 시간 (None일 경우 현재 시각)
    :return: (권장 행동 문자열, 상세 설명, 다음 예정일)
    """
    if current_dt is None:
        current_dt = datetime.now()

    # 1. 원래 예정되었던 다음 투여 시간 계산
    # (주의: timedelta는 float 일수를 정확히 처리하기 위해 시간 단위로 변환하여 더함)
    next_scheduled_dt = last_dose_dt + timedelta(hours=interval_days * 24)
    
    # 2. 다음 예정일까지 남은 시간
    time_remaining = next_scheduled_dt - current_dt
    
    # 3. 전체 투여 간격 (timedelta)
    total_interval_delta = timedelta(hours=interval_days * 24)
    
    # 4. 판단 로직: 남은 시간이 전체 간격의 50% 미만이면 Skip
    # (이미 다음 약 먹을 때가 다 되었다는 뜻)
    threshold = total_interval_delta / 2
    
    action_type = ""
    msg = ""
    
    # 이미 예정 시간을 넘긴 경우 (Missed completely and overdue)
    if time_remaining.total_seconds() < 0:
         # 이 경우는 보통 즉시 복용하고 스케줄을 미루는 것이 일반적이나, 안전을 위해 '즉시 복용' 안내
         action_type = "TAKE_NOW"
         msg = t("missed_overdue_msg")
         
    elif time_remaining < threshold:
        # 너무 가까움 -> 건너뛰기
        action_type = "SKIP"
        hours_left = time_remaining.total_seconds() / 3600
        msg = t("missed_skip_msg").format(hours_left=hours_left)
        
    else:
        # 아직 여유 있음 -> 즉시 복용
        action_type = "TAKE_NOW"
        msg = t("missed_take_msg")

    return action_type, msg, next_scheduled_dt
