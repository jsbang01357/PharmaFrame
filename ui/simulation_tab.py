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
            # 기본 이벤트 속성
            e_type = "scheduled"
            e_delay = 0.0
            
            # 오버라이드 확인
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
        unit_choice = st.radio("그래프 단위", ["기본 단위", "상대적 단위 (%)"], horizontal=True, key="unit_choice")
    with col_opt2:
        sim_duration = st.slider("시뮬레이션 기간 (일)", 7, 365, 30)
    with col_opt3:
        intensive_view = st.toggle("최근 48시간 집중 보기", value=False)

    sched = st.session_state.get("drug_schedule", [])
    
    if not sched:
        st.info("사이드바에서 약물을 추가하여 시뮬레이션을 시작하세요.")
        return None

    # Missed/Delayed Dose Override UI
    st.markdown("---")
    with st.expander("⏱️ 특정 투여일 조정 (누락/지연)", expanded=False):
        st.caption("특정 회차의 투여를 건너뛰거나 지연시킬 수 있습니다.")
        if "dose_overrides" not in st.session_state:
            st.session_state.dose_overrides = {}
            
        overrides = st.session_state.dose_overrides
        
        c1, c2, c3, c4 = st.columns(4)
        
        # 1. 스케줄된 약물 선택
        target_item = c1.selectbox("적용 대상 약물", options=sched, format_func=lambda x: f"{x['name']} ({x['dose']}mg)")
        
        if target_item:
            # 2. 회차 선택
            max_doses = int(sim_duration / target_item["interval"]) + 1
            dose_num = c2.number_input("조정할 회차 (N번째)", min_value=1, max_value=max_doses, value=1)
            
            # 3. 상태 변경
            ovr_type = c3.selectbox("상태 변경", ["지연 (Delayed)", "누락 (Missed)"])
            
            # 4. 지연 시간
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

    # 시뮬레이션 실행 (장기 예측을 위해 실제 보여줄 기간보다 여유있게 계산)
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

    # 단위 변환 로직 보류 (범용화)
    # y_full 값은 기본적으로 약물 데이터베이스에 따른 상대 농도 혹은 pg/mL. 
    # 현재는 기본 농도로 출력.

    start_dt = datetime.combine(st.session_state.get("start_date", datetime.now().date()), datetime.min.time())

    # 통계 계산 (항정 상태 분석)
    steady_mask = (t_full >= min(30, sim_duration/2)) & (t_full <= calc_duration)
    has_steady = np.any(steady_mask)
    
    stats_y = y_full[steady_mask] if has_steady else y_full
    stats_t = t_full[steady_mask] if has_steady else t_full

    stats = utils.calculate_stats(stats_y, stats_t)
    
    stats_b = None
    if st.session_state.compare_mode and y_full_b is not None:
        stats_y_b = y_full_b[steady_mask] if has_steady else y_full_b
        stats_b = utils.calculate_stats(stats_y_b, stats_t)

    # 그래프 표시용 슬라이싱
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

    # 임시: plot_utils.py 업데이트 전까지는 기존 create_hormone_chart 사용 시도
    # (추후 plot_utils.py도 범용화 리팩토링 예정)
    try:
        fig = plot.create_hormone_chart(
            t_dates=t_dates_plot,
            t_days=t_plot_days,
            y_conc=y_plot_conc,
            unit_choice="기본 단위", # 강제 고정
            compare_mode=st.session_state.compare_mode,
            y_conc_b=y_plot_b,
            surgery_mode=False,
            start_date=start_dt.date()
        )
        st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.error(f"그래프 렌더링 오류 (Plot Utils 리팩토링 대기 중): {e}")

    # 주요 지표 UI
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

        y_plot_conc = y_conc
        y_plot_conc_b = y_conc_b
        t_plot_dates = t_dates

    # 6. 시각화 (Plotly Chart)
    # plot.py의 create_hormone_chart 함수를 사용하여 그래프 생성
    # PDF 리포트 생성을 위해 시뮬레이션 데이터를 세션에 저장
    sim_data = {
        "t_dates": t_plot_dates,
        "t_days": t_plot_days,
        "y_conc": y_plot_conc,
        "unit_choice": unit_choice,
        "compare_mode": st.session_state.compare_mode,
        "y_conc_b": y_plot_conc_b,
        # 시뮬레이션 탭에서는 수술 중단/재개 오버레이를 표시하지 않음
        "surgery_mode": False,
        "stop_day": None,
        "resume_day": None,
        "surgery_date": None,
        "start_date": None,
        "anesthesia_type": None,
        "lab_data": {'dates': lab_dates, 'values': lab_values, 'texts': lab_texts},
        "stats": stats,
        "stats_b": stats_b,
        "rmse": rmse,
        "sim_duration": 2 if intensive_view else sim_duration
    }
    st.session_state.last_sim_data = sim_data
    
    chart_keys = [
        "t_dates", "t_days", "y_conc", "unit_choice",
        "compare_mode", "y_conc_b",
        "surgery_mode", "stop_day", "resume_day",
        "surgery_date", "start_date", "anesthesia_type",
        "lab_data", "stats", "sim_duration",
    ]
    chart_payload = {k: sim_data.get(k) for k in chart_keys}
    fig = plot.create_hormone_chart(**chart_payload)
    st.plotly_chart(fig, width="stretch")

    # 스타일링된 메트릭 표시
    st.markdown(f"#### 📊 {utils.t('stats_title')}")
    st.caption(utils.t("stats_steady_caption"))
    
    # 첫 번째 줄: Peak, Trough, Average
    r1c1, r1c2, r1c3 = st.columns(3)
    # 두 번째 줄: Fluctuation, Max Slope, RMSE
    r2c1, r2c2, r2c3 = st.columns(3)
    
    if st.session_state.compare_mode and y_conc_b is not None:
        r1c1.metric(utils.t("peak"), f"{stats['peak']:.1f} {unit_choice}", delta=f"{(stats['peak'] - stats_b['peak']):.1f}")
        r1c2.metric(utils.t("trough"), f"{stats['trough']:.1f} {unit_choice}", delta=f"{(stats['trough'] - stats_b['trough']):.1f}")
        r1c3.metric(utils.t("avg"), f"{stats['avg']:.1f} {unit_choice}", delta=f"{(stats['avg'] - stats_b['avg']):.1f}")
        r2c1.metric(utils.t("fluctuation"), f"{stats['fluctuation']:.1f}%", delta=f"{(stats['fluctuation'] - stats_b['fluctuation']):.1f}%", delta_color="inverse")
        r2c2.metric(
            utils.t("max_slope"),
            f"{stats['max_slope']:.1f}",
            delta=f"{(stats['max_slope'] - stats_b['max_slope']):.1f}",
            delta_color="inverse",
            help=utils.t("max_slope_help").format(unit=unit_choice),
        )
    else:
        r1c1.metric(utils.t("peak"), f"{stats['peak']:.1f} {unit_choice}")
        r1c2.metric(utils.t("trough"), f"{stats['trough']:.1f} {unit_choice}")
        r1c3.metric(utils.t("avg"), f"{stats['avg']:.1f} {unit_choice}")
        r2c1.metric(utils.t("fluctuation"), f"{stats['fluctuation']:.1f}%", help=utils.t("fluctuation_help"))
        r2c2.metric(
            utils.t("max_slope"),
            f"{stats['max_slope']:.1f}",
            help=utils.t("max_slope_risk_help").format(unit=unit_choice),
        )

    if rmse is not None:
        r2c3.metric(
            utils.t("rmse_label"),
            f"{rmse:.1f} {unit_choice}",
            help=utils.t("rmse_help"),
        )
    else:
        r2c3.metric(utils.t("rmse_label"), "N/A", help=utils.t("rmse_na_help"))

    if st.session_state.compare_mode and y_conc_b is not None:
        st.caption(utils.t("delta_caption"))

    # RMSE 기반 모델 신뢰도 표시 및 보정 권고
    rel_text, rel_color = None, None
    if rmse is not None:
        rel_text, rel_color = utils.get_reliability_info(rmse, unit_choice)
        st.markdown(f"**{utils.t('model_rel')}:** :{rel_color}[**{rel_text}**]")
        
        # 오차가 큰 경우(재보정 필요 등급) 경고 표시
        rmse_pg = rmse if unit_choice == "pg/mL" else rmse / 3.6713
        if rmse_pg >= 50:
            st.warning(utils.t("rmse_warning_msg"))

    # 보정 상태 알림
    # 계수가 1.0이 아닌(실제 보정이 적용된) 항목만 추출하여 표시
    active_calibrations = [f"{k}: {v:.2f}x" for k, v in st.session_state.calibration_factors.items() if v != 1.0]
    if active_calibrations:
        cal_info = ", ".join(active_calibrations)
        st.info(f"{utils.t('calib_notice')} ({cal_info})")

    # -----------------------------------------------------------------------------
    # 7. 임상 안전성 분석 (Clinical Safety Check) - 시뮬레이션 탭 하단으로 이동
    # -----------------------------------------------------------------------------
    st.markdown("---")
    st.markdown(f"### {utils.t('safety_check_title')}")

    # 안전성 분석 수행
    # main.py에서 설정된 has_migraine 값을 세션에서 가져옴
    has_migraine = st.session_state.get("has_migraine", False)

    checklist = {
        "has_spiro": st.session_state.has_spiro,
        "has_cpa": st.session_state.has_cpa,
        "has_p4": st.session_state.has_p4,
        "has_gnrh": st.session_state.has_gnrh
    }
    
    # 시뮬레이션 탭 내부에 있으므로 현재 계산된 stats 사용 가능
    sim_stats = stats
    
    analysis_res = utils.perform_safety_analysis(
        current_drugs,
        st.session_state.user_profile,
        st.session_state.is_smoker,
        st.session_state.history_vte,
        has_migraine,
        sim_stats,
        None, # stats_b는 생략
        st.session_state.unit_choice,
        False, # compare_mode 생략
        checklist=checklist,
        interactors=st.session_state.selected_interactors
    )
    
    # 1. 위험 경고 출력
    for risk in analysis_res['risks']:
        if risk['level'] == "CRITICAL":
            st.error(risk['msg'], icon="🚨")
        elif risk['level'] == "HIGH":
            st.error(risk['msg'], icon="🚫")
        elif risk['level'] == "MEDIUM":
            st.warning(risk['msg'], icon="⚠️")
    
    # 2. 단독 요법 상태 피드백
    mono = analysis_res['monotherapy']
    if mono:
        if mono['type'] == "success":
            st.success(mono['msg'])
        elif mono['type'] == "info":
            st.info(mono['msg'])
        elif mono['type'] == "warning":
            st.warning(mono['msg'])
    
    # 3. 골밀도 위험
    if analysis_res['bone_risk']:
        st.error(utils.t("bone_risk"))

    # -------------------------------------------------------------------------
    # 🩺 정기 추적검사 가이드라인 (Clinical Monitoring Guide)
    # -------------------------------------------------------------------------
    st.markdown("---")
    st.subheader(utils.t("monitoring_guide_title"))

    st.info(utils.t("monitoring_guide_info"))
    
    monitoring_table = utils.get_monitoring_messages(current_drugs, checklist)
    if monitoring_table:
        st.markdown(monitoring_table)

    # PDF 리포트를 위해 시뮬레이션 결과 요약을 세션에 저장
    st.session_state.last_sim_data.update({
        "reliability": {"text": rel_text, "color": rel_color},
        "active_calibrations": active_calibrations,
        "analysis_res": analysis_res,
        "monitoring_table": monitoring_table,
        "checklist": checklist,
        "selected_interactors": list(st.session_state.selected_interactors),
        "calibration_factors": dict(st.session_state.calibration_factors),
        "lab_history": dict(st.session_state.lab_history),
        "unit_choice": unit_choice,
        "compare_mode": st.session_state.compare_mode,
        "scenario_a_count": len(e2_sched),
        "scenario_b_count": len(e2_sched_b) if st.session_state.compare_mode else 0,
    })

    return stats
