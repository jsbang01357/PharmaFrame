import json
import os
import numpy as np
from datetime import datetime, timedelta

"""
PharmaFrame Utilities Module
- Unit conversion logic
- Formatting helpers for UI
- Mathematical / Statistical calculators
- Internationalization (i18n)
"""

# -----------------------------------------------------------------------------
# 0. Internationalization (i18n)
# -----------------------------------------------------------------------------

def _load_translations():
    """Load translation data from i18n.json"""
    try:
        # utils/utils.py 기준 utils/i18n.json 로드
        base_path = os.path.dirname(__file__)
        file_path = os.path.join(base_path, "i18n.json")
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        # 로깅 대신 간단한 프린트 (서버 로그 확인용)
        return {}

TRANSLATIONS = _load_translations()

def t(key):
    """
    Translate a key based on the current session language.
    Default to KO if not set.
    """
    import streamlit as st
    lang = st.session_state.get("lang", "KO")
    lang_dict = TRANSLATIONS.get(lang, TRANSLATIONS.get("KO", {}))
    return lang_dict.get(key, key)

# -----------------------------------------------------------------------------
# 1. Statistics & Analysis Helpers
# -----------------------------------------------------------------------------

def calculate_stats(concentration_array, t_days=None):
    """
    농도 배열에서 임상적으로 의미 있는 통계 추출 (Steady State 기준)
    """
    if len(concentration_array) == 0:
        return {"peak": 0, "trough": 0, "avg": 0, "fluctuation": 0, "max_slope": 0}

    peak = np.max(concentration_array)
    if peak <= 0:
        return {"peak": 0, "trough": 0, "avg": 0, "fluctuation": 0, "max_slope": 0}

    # 최대 변화율(Slope) 계산
    max_slope = 0
    if t_days is not None and len(t_days) > 1:
        dy = np.diff(concentration_array)
        dt = np.diff(t_days)
        # 0 나누기 방지
        dt = np.where(dt == 0, 1e-9, dt)
        max_slope = np.max(np.abs(dy / dt))

    # 유지기(Steady State) 추정: 전체 데이터의 후반 50%를 기준으로 계산 (단순화)
    # 실제로는 첫 피크 이후를 찾아야 하지만, 범용 엔진에서는 투약 주기가 다양하므로
    # 슬라이싱 범위를 안정적인 구간으로 잡음.
    start_idx = len(concentration_array) // 2
    steady_state_array = concentration_array[start_idx:]

    if len(steady_state_array) == 0:
        steady_state_array = concentration_array

    trough = np.min(steady_state_array)
    avg = np.mean(steady_state_array)
    
    # 변동 지수 (Fluctuation Index)
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
    예측 곡선과 실제 측정 데이터(lab_points) 사이의 오차(RMSE) 계산
    """
    if not lab_points:
        return None
    
    sq_errors = []
    for day, val in lab_points:
        idx = (np.abs(t_days - day)).argmin()
        prediction = y_conc[idx]
        sq_errors.append((prediction - val) ** 2)
    
    return np.sqrt(np.mean(sq_errors)) if sq_errors else None

# -----------------------------------------------------------------------------
# 2. UI Formatting & Helpers
# -----------------------------------------------------------------------------

def get_risk_badge(risk_level):
    """위험도 레벨에 따른 스타일링된 텍스트 반환"""
    colors = {
        "LOW": "green",
        "MEDIUM": "orange",
        "HIGH": "red",
        "CRITICAL": "#8B0000"
    }
    color = colors.get(risk_level, "grey")
    # i18n 키가 없을 경우를 대비해 fallback
    label = risk_level
    return f":{color}[**{label}**]"

def format_duration(days):
    """일수를 읽기 편한 형식으로 변환"""
    if days >= 30:
        return f"{days/30:.1f}개월 ({int(days)}일)"
    if days >= 7:
        return f"{days/7:.1f}주 ({int(days)}일)"
    return f"{int(days)}일"

# -----------------------------------------------------------------------------
# 3. Clinical Calculation Helpers
# -----------------------------------------------------------------------------

def calculate_missed_dose_action(last_dose_dt, interval_days, current_dt=None):
    """
    복약 누락(Missed Dose) 가이드 (50% Rule)
    """
    if current_dt is None:
        current_dt = datetime.now()

    next_scheduled_dt = last_dose_dt + timedelta(hours=interval_days * 24)
    time_remaining = next_scheduled_dt - current_dt
    total_interval_delta = timedelta(hours=interval_days * 24)
    threshold = total_interval_delta / 2
    
    if time_remaining.total_seconds() < 0:
         return "TAKE_NOW", "예정 시간을 지났습니다. 즉시 복용하고 다음 일정을 조정하세요.", next_scheduled_dt
         
    if time_remaining < threshold:
        return "SKIP", "다음 복용 시간이 너무 가깝습니다. 이번 회차는 건너뛰세요.", next_scheduled_dt
        
    return "TAKE_NOW", "지금 즉시 복용하세요. 다음 복용은 예정대로 진행합니다.", next_scheduled_dt

# -----------------------------------------------------------------------------
# 4. Drug Localized Accessors
# -----------------------------------------------------------------------------

def get_localized_field(obj, field_name):
    """다국어 필드 안전 접근 (예: desc vs desc_en)"""
    import streamlit as st
    lang = st.session_state.get("lang", "KO")
    
    if lang == "EN":
        en_field = f"{field_name}_en"
        if hasattr(obj, en_field) and getattr(obj, en_field):
            return getattr(obj, en_field)
        # Dictionary case
        if isinstance(obj, dict) and obj.get(en_field):
            return obj.get(en_field)
            
    if hasattr(obj, field_name):
        return getattr(obj, field_name)
    if isinstance(obj, dict):
        return obj.get(field_name, "")
    return ""
