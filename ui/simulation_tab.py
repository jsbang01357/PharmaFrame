import streamlit as st
from datetime import datetime, timedelta
import numpy as np

from utils import utils
from core.pk_engine import PKEngine
from core.models import PatientProfile, DoseEvent
from ui import plot_utils as plot

@st.cache_data(show_spinner=False)
def run_simulation_cached(drug_schedule, user_profile, sim_duration, overrides=None):
    if overrides is None:
        overrides = {}
        
    patient = PatientProfile(
        name=user_profile.get("name", "User"),
        age=user_profile.get("age", 50),
        weight_kg=user_profile.get("weight", 60.0),
        height_cm=user_profile.get("height", 170.0),
        body_fat_pct=user_profile.get("body_fat", 22.0),
        ast_u_l=user_profile.get("ast", 20.0),
        alt_u_l=user_profile.get("alt", 20.0),
        egfr=user_profile.get("egfr", 100.0)
    )
    engine = PKEngine(patient)
    
    events = []
    for item in drug_schedule:
        drug_id = item["drug_id"]
        dose = item["dose"]
        interval = item["interval"]
        route = item["type"]
        item_id = item["id"]
        
        current_time_h = 0.0
        max_time_h = sim_duration * 24.0
        dose_number = 1
        
        while current_time_h <= max_time_h:
            e_type = "scheduled"
            e_delay = 0.0
            
            override_key = f"{item_id}_{dose_number}"
            if override_key in overrides:
                ovr = overrides[override_key]
                e_type = ovr["type"]
                e_delay = ovr.get("delay_h", 0.0)
            
            events.append(DoseEvent(
                drug_id=drug_id,
                dose=dose,
                time_h=current_time_h,
                route=route,
                event_type=e_type,
                delay_h=e_delay
            ))
            current_time_h += (interval * 24.0)
            dose_number += 1
            
    return engine.simulate(events, days=sim_duration, resolution=24)


def render_simulator_tab():
    st.markdown(f"### 시뮬레이션 대시보드")

    col_opt1, col_opt2, col_opt3 = st.columns([1, 2, 1])
    with col_opt1:
        unit_choice = st.radio("그래프 단위", ["기본 단위", "상대적 단위 (%)"], horizontal=True, key="unit_choice_sim")
    with col_opt2:
        sim_duration = st.slider("시뮬레이션 기간 (일)", 7, 365, 30)
    with col_opt3:
        intensive_view = st.toggle("최근 48시간 집중 보기", value=False)

    sched = st.session_state.get("drug_schedule", [])
    
    if not sched:
        st.info("사이드바에서 약물을 추가하여 시뮬레이션을 시작하세요.")
        return None

    # Missed/Delayed Dose Override UI
    with st.expander("⏱️ 특정 투여일 조정 (누락/지연)", expanded=False):
        st.caption("특정 회차의 투여를 건너뛰거나 지연시킬 수 있습니다.")
        if "dose_overrides" not in st.session_state:
            st.session_state.dose_overrides = {}
            
        overrides = st.session_state.dose_overrides
        
        c1, c2, c3, c4 = st.columns(4)
        target_item = c1.selectbox("적용 대상 약물", options=sched, format_func=lambda x: f"{x['name']} ({x['dose']}mg)")
        
        if target_item:
            max_doses = int(sim_duration / target_item["interval"]) + 1
            dose_num = c2.number_input("조정할 회차 (N번째)", min_value=1, max_value=max_doses, value=1)
            ovr_type = c3.selectbox("상태 변경", ["지연 (Delayed)", "누락 (Missed)"])
            
            delay_hours = 0.0
            if ovr_type == "지연 (Delayed)":
                delay_hours = c4.number_input("지연 시간 (시간)", min_value=0.5, value=12.0, step=1.0)
                
            if st.button("적용"):
                key = f"{target_item['id']}_{dose_num}"
                overrides[key] = {
                    "type": "missed" if ovr_type == "누락 (Missed)" else "delayed",
                    "delay_h": delay_hours
                }
                st.rerun()
                
        if overrides:
            st.markdown("**현재 적용된 예외:**")
            to_delete = []
            for k, v in overrides.items():
                item_id, d_num = k.rsplit("_", 1)
                match = next((i for i in sched if i["id"] == item_id), None)
                if match:
                    desc = f"**{match['name']}** {d_num}회차: "
                    if v["type"] == "missed": desc += "누락"
                    else: desc += f"{v['delay_h']}시간 지연"
                    
                    cc1, cc2 = st.columns([3,1])
                    cc1.write(desc)
                    if cc2.button("삭제", key=f"del_ovr_{k}"):
                        to_delete.append(k)
            
            if to_delete:
                for k in to_delete:
                    del overrides[k]
                st.rerun()

    calc_duration = max(sim_duration, 180)
    t_full, y_full = run_simulation_cached(
        sched,
        st.session_state.user_profile,
        calc_duration,
        st.session_state.get("dose_overrides", {})
    )

    y_full_b = None
    if st.session_state.compare_mode:
        sched_b = st.session_state.get("drug_schedule_b", [])
        if sched_b:
            _, y_full_b = run_simulation_cached(
                sched_b,
                st.session_state.user_profile,
                calc_duration,
                st.session_state.get("dose_overrides", {})
            )

    start_dt = datetime.combine(st.session_state.get("start_date", datetime.now().date()), datetime.min.time())

    steady_mask = (t_full >= min(30, sim_duration/2)) & (t_full <= calc_duration)
    has_steady = np.any(steady_mask)
    
    stats_y = y_full[steady_mask] if has_steady else y_full
    stats_t = t_full[steady_mask] if has_steady else t_full
    stats = utils.calculate_stats(stats_y, stats_t)
    
    stats_b = None
    if st.session_state.compare_mode and y_full_b is not None:
        stats_y_b = y_full_b[steady_mask] if has_steady else y_full_b
        stats_b = utils.calculate_stats(stats_y_b, stats_t)

    view_mask = t_full <= sim_duration
    t_days = t_full[view_mask]
    y_conc = y_full[view_mask]
    y_conc_b = y_full_b[view_mask] if y_full_b is not None else None

    if intensive_view:
        view_range = 2.0 
        mask = t_days >= (sim_duration - view_range)
        t_plot_days = t_days[mask]
        y_plot_conc = y_conc[mask]
        y_plot_b = y_conc_b[mask] if y_conc_b is not None else None
        t_dates_plot = [start_dt + timedelta(days=float(t)) for t in t_plot_days]
    else:
        t_plot_days = t_days
        y_plot_conc = y_conc
        y_plot_b = y_conc_b
        t_dates_plot = [start_dt + timedelta(days=float(t)) for t in t_days]

    # Save to session for export
    st.session_state.last_sim_data = {
        "t_dates": t_dates_plot,
        "t_days": t_plot_days,
        "y_conc": y_plot_conc,
        "unit_choice": "기본 단위",
        "compare_mode": st.session_state.compare_mode,
        "y_conc_b": y_plot_b,
        "surgery_mode": False,
        "start_date": start_dt.date(),
        "sim_duration": sim_duration
    }

    try:
        fig = plot.create_pk_chart(
            t_dates=t_dates_plot,
            t_days=t_plot_days,
            y_conc=y_plot_conc,
            unit_choice="기본 단위",
            compare_mode=st.session_state.compare_mode,
            y_conc_b=y_plot_b,
            surgery_mode=False,
            start_date=start_dt.date()
        )
        st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.error(f"그래프 렌더링 오류: {e}")

    st.markdown("---")
    st.markdown("#### 예상 약동학(PK) 지표")
    st.caption("안정 상태(Steady State) 도달 이후의 예상 농도입니다.")
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("최고 농도 (Peak)", f"{stats['peak']:.1f}")
    col2.metric("최저 농도 (Trough)", f"{stats['trough']:.1f}")
    col3.metric("평균 농도 (Avg)", f"{stats['avg']:.1f}")
    col4.metric("변동폭 (Fluctuation)", f"{stats['fluctuation']:.1f}%")

    if st.session_state.compare_mode and stats_b:
        st.markdown("##### 시나리오 B 지표")
        cb1, cb2, cb3, cb4 = st.columns(4)
        cb1.metric("최고 농도 (Peak)", f"{stats_b['peak']:.1f}", delta=f"{stats_b['peak']-stats['peak']:.1f}")
        cb2.metric("최저 농도 (Trough)", f"{stats_b['trough']:.1f}", delta=f"{stats_b['trough']-stats['trough']:.1f}")
        cb3.metric("평균 농도 (Avg)", f"{stats_b['avg']:.1f}", delta=f"{stats_b['avg']-stats['avg']:.1f}")
        cb4.metric("변동폭", f"{stats_b['fluctuation']:.1f}%", delta=f"{stats_b['fluctuation']-stats['fluctuation']:.1f}%")

    return stats
