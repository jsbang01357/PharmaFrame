import streamlit as st
from datetime import datetime, timedelta
import numpy as np

from utils import utils
from core.pk_engine import PKEngine
from core.models import PatientProfile
from ui import plot_utils as plot
from ui.simulation_tab import run_simulation_cached

def render_procedure_tab():
    st.markdown(f"### 🏥 처치/수술 계획 (Procedure Plan)")
    st.caption("예정된 시술이나 수술을 위해 특정 기간 동안 약물 투여를 중단해야 할 경우 시뮬레이션합니다.")
    
    sched = st.session_state.get("drug_schedule", [])
    if not sched:
        st.info("사이드바에서 약물을 추가하여 시뮬레이션을 시작하세요.")
        return
        
    st.session_state.surgery_mode = st.toggle("수술/처치 모드 활성화", value=st.session_state.get("surgery_mode", False))
    
    if not st.session_state.surgery_mode:
        st.info("활성화하면 중단 기간을 설정할 수 있습니다.")
        return
        
    # 설정 UI
    st.markdown("#### 일정 설정")
    col1, col2, col3 = st.columns(3)
    
    # 1. 수술일
    surg_date = col1.date_input("수술/시술 예정일", value=st.session_state.get("surgery_date", datetime.now().date() + timedelta(days=14)))
    st.session_state.surgery_date = surg_date
    
    # 2. 중단 및 재개
    stop_days = col2.number_input("수술 전 중단일 (일)", min_value=0, value=7, help="수술 며칠 전부터 약을 끊을 것인가요?")
    resume_days = col3.number_input("수술 후 재개일 (일)", min_value=0, value=7, help="수술 며칠 후부터 약을 다시 복용하나요?")
    
    start_dt = st.session_state.get("start_date", datetime.now().date())
    stop_date = surg_date - timedelta(days=stop_days)
    resume_date = surg_date + timedelta(days=resume_days)
    
    st.caption(f"**권장 중단 기간:** {stop_date.strftime('%Y-%m-%d')} ~ {resume_date.strftime('%Y-%m-%d')}")
    
    # Simulation을 위한 상대적 일수 (start_date 기준)
    stop_day_relative = (stop_date - start_dt).days
    resume_day_relative = (resume_date - start_dt).days
    
    if stop_day_relative < 0:
        st.warning("중단 시작일이 시뮬레이션 시작일보다 과거입니다. 그래프에 반영되지 않을 수 있습니다.")
        stop_day_relative = 0

    st.markdown("---")
    st.markdown("#### 중단 기간 반영 약동학 그래프")
    
    sim_duration = st.slider("조회 기간 (일)", 14, 180, 60, key="proc_sim_duration")
    
    # 시뮬레이션 실행 (overrides를 이용해 중단 기간 이벤트를 "missed" 처리하는 방식으로 변경)
    # 기존 EstroFrame은 simulate 함수 내부에 stop_day 로직을 하드코딩 했으나,
    # PharmaFrame의 DoseEvent 구조에서는 이 기간 내의 투여를 누락(missed) 처리하는 것이 아키텍처상 올바릅니다.
    
    overrides = {}
    for item in sched:
        interval = item["interval"]
        item_id = item["id"]
        
        # 0일부터 sim_duration까지 순회하며 중단 기간(stop ~ resume)에 속하는지 확인
        current_time_h = 0.0
        max_time_h = sim_duration * 24.0
        dose_number = 1
        
        stop_h = stop_day_relative * 24.0
        resume_h = resume_day_relative * 24.0
        
        while current_time_h <= max_time_h:
            if stop_h <= current_time_h < resume_h:
                overrides[f"{item_id}_{dose_number}"] = {"type": "missed", "delay_h": 0.0}
            
            current_time_h += (interval * 24.0)
            dose_number += 1
            
    # 시뮬레이션 실행 (수술 모드 오버라이드 적용)
    t_full, y_full = run_simulation_cached(
        sched,
        st.session_state.user_profile,
        max(sim_duration, int(resume_day_relative + 30)),
        overrides
    )
    
    # 시각화 데이터 슬라이싱
    view_mask = t_full <= sim_duration
    t_days = t_full[view_mask]
    y_conc = y_full[view_mask]
    
    start_dt_combined = datetime.combine(start_dt, datetime.min.time())
    t_dates = [start_dt_combined + timedelta(days=float(t)) for t in t_days]
    
    try:
        fig = plot.create_pk_chart(
            t_dates=t_dates,
            t_days=t_days,
            y_conc=y_conc,
            unit_choice="기본 단위",
            compare_mode=False,
            surgery_mode=True,
            stop_day=stop_day_relative,
            resume_day=resume_day_relative,
            surgery_date=surg_date,
            start_date=start_dt
        )
        st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.error(f"그래프 렌더링 오류: {e}")
        
    st.info("수술/시술 모드에서는 중단 기간 내의 투여 일정이 시뮬레이션 상에서 모두 '누락' 처리됩니다.")
