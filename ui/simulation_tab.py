import streamlit as st
from datetime import datetime, timedelta
import numpy as np

from utils import utils
from core import data
from ui import plot_utils as plot
from core import pk_engine as analysis


@st.cache_data(show_spinner=False)
def run_simulation_cached(drug_schedule, user_profile, sim_duration, calibration_factors, stop_day, resume_day, surgery_mode):
    #시뮬레이션 로직 캐싱: 입력값이 동일할 경우 재계산을 방지하여 성능 최적화
    local_analyzer = analysis.HormoneAnalyzer(
        user_weight=user_profile['weight'],
        user_age=user_profile['age'],
        ast=user_profile.get('ast', 20.0),
        alt=user_profile.get('alt', 20.0),
        body_fat=user_profile.get('body_fat', 22.0),
        user_height=user_profile.get('height', 170.0)
    )
    # [최적화] resolution을 24(1시간 단위)로 설정하여 모바일 렌더링 부하 감소 (기본값 100 대비 경량화)
    return local_analyzer.simulate_schedule(
        drug_schedule, 
        days=sim_duration,
        resolution=24, 
        calibration_factors=calibration_factors,
        stop_day=stop_day if surgery_mode else None,
        resume_day=resume_day if surgery_mode else None
    )


def render_simulator_tab(analyzer):
    st.markdown(f"### {utils.t('sim_title')}")

    current_drugs = st.session_state.drug_schedule
    
    col_opt1, col_opt2, col_opt3 = st.columns([1, 2, 1])
    with col_opt1:
        unit_choice = st.radio(utils.t("unit_choice"), ["pg/mL", "pmol/L"], horizontal=True, key="unit_choice")
    with col_opt2:
        sim_duration = st.slider(utils.t("sim_days"), 7, 180, 30)
    with col_opt3:
        # 24시간 집중 보기 토글을 빈 자리로 이동하여 UI를 더 깔끔하게 만듭니다.
        intensive_view = st.toggle(
            utils.t("intensive_24h_view"),
            value=False,
            help=utils.t("intensive_24h_help"),
        )

    # 1. 그래프에 그릴 '에스트로겐' 제형만 정의
    estrogen_types = ["Injection", "Oral", "Transdermal", "Sublingual"]

    # 2. 해당 제형인 약물만 필터링하여 시뮬레이션 투입
    e2_sched = [
        d for d in st.session_state.drug_schedule 
        if d['name'] in data.DRUG_DB and data.DRUG_DB[d['name']].type in estrogen_types
    ]

    # 2. 시뮬레이션 실행 (E2)
    # [변경] 내부적으로는 항정 상태를 위해 충분히 긴 기간(180일)을 시뮬레이션
    calc_duration = 180
    t_full, y_full = run_simulation_cached(
        e2_sched,
        st.session_state.user_profile,
        calc_duration,
        st.session_state.calibration_factors,
        st.session_state.stop_day,
        st.session_state.resume_day,
        False
    )

    y_full_b = None
    if st.session_state.compare_mode:
        e2_sched_b = [
            d for d in st.session_state.drug_schedule_b 
            if d['name'] in data.DRUG_DB and data.DRUG_DB[d['name']].type in estrogen_types
        ]
        
        _, y_full_b = run_simulation_cached(
            e2_sched_b,
            st.session_state.user_profile,
            calc_duration,
            st.session_state.calibration_factors,
            st.session_state.stop_day,
            st.session_state.resume_day,
            False
        )

    # 4. 단위 변환
    if unit_choice == "pmol/L":
        y_full = utils.convert_e2_unit(y_full, "pmol/L")
        if y_full_b is not None:
            y_full_b = utils.convert_e2_unit(y_full_b, "pmol/L")

    # [날짜 변환 준비]
    start_dt = datetime.combine(st.session_state.start_date, datetime.min.time())
    # 피검사 기록 포인트 준비
    lab_dates = []
    lab_values = []
    lab_texts = []
    lab_points_for_rmse = []
    if st.session_state.lab_history:
        for route, records in st.session_state.lab_history.items():
            for record in records:
                # 날짜 변환
                d = start_dt + timedelta(days=float(record['day']))
                lab_dates.append(d)
                
                # 단위 변환
                val = record['value']
                if unit_choice == "pmol/L":
                    val = utils.convert_e2_unit(val, "pmol/L")
                lab_values.append(val)
                lab_texts.append(f"{utils.t('actual_measure')} ({route}): {val:.1f} {unit_choice}")
                lab_points_for_rmse.append((record['day'], val))


    # 5. 통계 계산 (항정 상태 분석을 위해 90일~180일 구간 데이터 사용)
    # 대부분의 약물이 90일 이전에 항정 상태(Steady State)에 도달하므로, 이 구간의 통계가 가장 정확합니다.
    steady_mask = (t_full >= 90) & (t_full <= 180)
    has_steady = np.any(steady_mask)
    
    stats_y = y_full[steady_mask] if has_steady else y_full
    stats_t = t_full[steady_mask] if has_steady else t_full

    stats = utils.calculate_stats(stats_y, stats_t)
    rmse = utils.calculate_rmse(t_full, y_full, lab_points_for_rmse)
    
    stats_b = None
    if st.session_state.compare_mode and y_full_b is not None:
        stats_y_b = y_full_b[steady_mask] if has_steady else y_full_b
        stats_b = utils.calculate_stats(stats_y_b, stats_t)

    # [그래프 표시용 데이터 슬라이싱] 사용자가 선택한 sim_duration만큼 잘라서 표시
    view_mask = t_full <= sim_duration
    t_days = t_full[view_mask]
    y_conc = y_full[view_mask]
    y_conc_b = y_full_b[view_mask] if y_full_b is not None else None

    # [날짜 변환] 슬라이싱된 t_days를 기준으로 날짜 리스트 생성
    t_dates = [start_dt + timedelta(days=float(t)) for t in t_days]

    # 24시간 집중 보기 로직 적용
    if intensive_view:
        # 마지막 48시간(2일) 데이터를 슬라이싱하여 일주기성 강조
        view_range = 2.0 
        mask = t_days >= (sim_duration - view_range)
        
        t_plot_days = t_days[mask]
        y_plot_conc = y_conc[mask]
        y_plot_conc_b = y_conc_b[mask] if y_conc_b is not None else None
        
        # 현재는 일관성을 위해 실제 날짜 객체 리스트 사용
        t_plot_dates = [start_dt + timedelta(days=float(t)) for t in t_plot_days]
    else:
        t_plot_days = t_days
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
