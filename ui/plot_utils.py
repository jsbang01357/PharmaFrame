import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
from datetime import datetime, timedelta
from utils import utils
from core import data

def create_hormone_chart(
    t_dates, t_days, y_conc, unit_choice,
    compare_mode=False, y_conc_b=None,
    surgery_mode=False, stop_day=None, resume_day=None, surgery_date=None, start_date=None, anesthesia_type=None,
    lab_data=None,
    stats=None,
    sim_duration=30
):
    """
    호르몬 시뮬레이션 결과를 Plotly 그래프로 생성하여 반환합니다.
    """
    # 1. Label & Threshold Setup
    if unit_choice == "pmol/L":
        y_label = "Estradiol (pmol/L)"
        guideline_min, guideline_max = 370, 740
        safety_threshold = 50.0 * 3.6713
    else:
        y_label = "Estradiol (pg/mL)"
        guideline_min, guideline_max = 100, 200
        safety_threshold = 50.0

    # 2. Calculate Y-Axis Limit
    all_y_values = list(y_conc)
    if compare_mode and y_conc_b is not None:
        all_y_values.extend(list(y_conc_b))
    if lab_data and lab_data.get('values'):
        all_y_values.extend(lab_data['values'])
    
    y_max_limit = max(np.max(all_y_values) if len(all_y_values) > 0 else 0, guideline_max) * 1.2

    # 3. Create Figure
    fig = make_subplots()
    
    # Guidelines (Target Range)
    fig.add_shape(
        type="rect",
        x0=0, x1=1, xref="paper",
        y0=guideline_min, y1=guideline_max, yref="y",
        fillcolor="rgba(0, 255, 0, 0.2)",
        line_width=0,
        layer="below"
    )
    fig.add_annotation(
        x=1, y=guideline_max, text=utils.t("target_range"),
        xref="paper", yref="y",
        showarrow=False, xanchor="right", yanchor="bottom",
        font=dict(color="green", size=10)
    )
    fig.add_hline(y=guideline_min, line_dash="dash", line_color="rgba(0, 128, 0, 0.4)", yref="y")
    fig.add_hline(y=guideline_max, line_dash="dash", line_color="rgba(0, 128, 0, 0.4)", yref="y")

    # Dose Dumping Warning (현재 표시 데이터 기준으로 판정)
    spike_limit_pg = data.GUIDELINES["ACUTE_SPIKE"]["e2_max"]
    spike_limit_current = spike_limit_pg
    if unit_choice == "pmol/L":
        spike_limit_current = utils.convert_e2_unit(spike_limit_pg, "pmol/L")

    peak_visible = max(all_y_values) if len(all_y_values) > 0 else 0.0
    if peak_visible > spike_limit_current:
        fig.add_hline(
            y=spike_limit_current,
            line_dash="dot", line_color="red",
            annotation_text=f"{utils.t('spike_warning')} (> {spike_limit_pg} pg/mL)",
            annotation_position="top left",
            yref="y"
        )
        # 임계선 위 위험 영역을 약하게 강조
        fig.add_hrect(
            y0=spike_limit_current,
            y1=max(y_max_limit, peak_visible * 1.05),
            fillcolor="rgba(255, 0, 0, 0.08)",
            line_width=0,
            layer="below",
            yref="y",
        )
        y_max_limit = max(y_max_limit, spike_limit_current * 1.1, peak_visible * 1.08)

    # High Slope Warning
    def _mark_high_slope_regions(series_y, series_name, marker_color):
        if series_y is None or t_days is None or len(series_y) <= 1:
            return
        dy = np.diff(series_y)
        dt = np.diff(t_days)
        # dt=0 보호
        safe_dt = np.where(dt == 0, np.nan, dt)
        slopes = dy / safe_dt
        slope_threshold = 100.0 if unit_choice == "pg/mL" else 100.0 * 3.6713

        high_slope_indices = np.where(np.abs(slopes) > slope_threshold)[0]
        if len(high_slope_indices) == 0:
            return

        # 배경 영역 강조
        start_idx = high_slope_indices[0]
        for i in range(1, len(high_slope_indices)):
            if high_slope_indices[i] != high_slope_indices[i - 1] + 1:
                fig.add_vrect(
                    x0=t_dates[start_idx], x1=t_dates[high_slope_indices[i - 1] + 1],
                    fillcolor="rgba(255, 193, 7, 0.22)", opacity=1.0, line_width=0,
                    layer="below"
                )
                start_idx = high_slope_indices[i]
        fig.add_vrect(
            x0=t_dates[start_idx], x1=t_dates[high_slope_indices[-1] + 1],
            fillcolor="rgba(255, 193, 7, 0.22)", opacity=1.0, line_width=0,
            layer="below",
            annotation_text=utils.t("high_slope_risk"), annotation_position="top left"
        )

        # 눈에 띄는 마커 추가 (급경사 시작점)
        marker_idx = sorted(set(int(i) for i in high_slope_indices.tolist()))
        fig.add_trace(go.Scatter(
            x=[t_dates[i] for i in marker_idx if i < len(t_dates)],
            y=[series_y[i] for i in marker_idx if i < len(series_y)],
            mode="markers",
            name=f"{utils.t('high_slope_risk')} ({series_name})",
            marker=dict(color=marker_color, size=7, symbol="x"),
            showlegend=False,
            hovertemplate=f"{utils.t('high_slope_risk')}<extra></extra>",
        ))

    # 수술 계획 그래프에서는 급격한 변화 강조를 숨김
    if not surgery_mode:
        _mark_high_slope_regions(y_conc, "A", "#FF8C00")
        if compare_mode and y_conc_b is not None:
            _mark_high_slope_regions(y_conc_b, "B", "#B8860B")

    # Surgery Threshold
    if surgery_mode and anesthesia_type == utils.t("anesthesia_gen"):
        fig.add_hline(
            y=safety_threshold, 
            line_dash="dot", line_color="red",
            annotation_text=f"{utils.t('surgery_threshold')} ({safety_threshold:.1f} {unit_choice})",
            annotation_position="bottom right",
            yref="y"
        )

    # Main Traces (Estradiol)
    fig.add_trace(go.Scatter(
        x=t_dates, y=y_conc,
        mode='lines',
        name=f"E2: {utils.t('scenario_a')}" if compare_mode else f"{utils.t('predicted_e2')} ({unit_choice})",
        line=dict(color='#FF69B4', width=2),
        fill='tozeroy' if not compare_mode else None,
        fillcolor='rgba(255, 105, 180, 0.1)'
    ), secondary_y=False)
    
    if compare_mode and y_conc_b is not None:
        fig.add_trace(go.Scatter(
            x=t_dates, y=y_conc_b,
            mode='lines',
            name=f"E2: {utils.t('scenario_b')}",
            line=dict(color='#4169E1', width=2, dash='dash'),
        ), secondary_y=False)

    # Surgery Lines
    if surgery_mode and start_date:
        start_dt = datetime.combine(start_date, datetime.min.time())
        if stop_day is not None:
            stop_date = start_dt + timedelta(days=stop_day)
            fig.add_vline(x=stop_date, line_width=2, line_dash="dash", line_color="orange")
            fig.add_annotation(
                x=stop_date, y=max(y_conc) if len(y_conc)>0 else 100,
                text=utils.t("cessation_label"), showarrow=True, arrowhead=1,
                ax=40, ay=-30, bgcolor="orange", font=dict(color="white")
            )

        if resume_day is not None and stop_day is not None and resume_day > stop_day:
            resume_date = start_dt + timedelta(days=resume_day)
            fig.add_vline(x=resume_date, line_width=2, line_dash="dash", line_color="green")
            fig.add_annotation(
                x=resume_date, y=max(y_conc) if len(y_conc)>0 else 100,
                text=utils.t("resumption_label"), showarrow=True, arrowhead=1,
                ax=40, ay=-30, bgcolor="green", font=dict(color="white")
            )

        if surgery_date:
            fig.add_vline(x=surgery_date, line_width=2, line_dash="dash", line_color="red")
            fig.add_annotation(
                x=surgery_date, y=y_max_limit * 0.8,
                text=utils.t("surgery_date_label"), showarrow=True, arrowhead=1,
                ax=-40, ay=-30, bgcolor="red", font=dict(color="white")
            )

    # Lab Points
    if lab_data and lab_data.get('dates'):
        fig.add_trace(go.Scatter(
            x=lab_data['dates'],
            y=lab_data['values'],
            mode='markers',
            name=utils.t('actual_lab_results'),
            marker=dict(color='black', size=10, symbol='diamond', line=dict(width=1, color='white')),
            text=lab_data.get('texts', []),
            hoverinfo='text'
        ))

    # Surgery Safe Zone Highlight (Below Threshold)
    if surgery_mode:
        y_arr = np.array(y_conc)
        is_safe = y_arr < safety_threshold
        # Find continuous segments
        is_safe_padded = np.concatenate(([False], is_safe, [False]))
        diff = np.diff(is_safe_padded.astype(int))
        starts = np.where(diff == 1)[0]
        ends = np.where(diff == -1)[0]
        
        for i in range(len(starts)):
            s_idx = starts[i]
            e_idx = ends[i] - 1
            
            if s_idx < len(t_dates) and e_idx < len(t_dates):
                x0 = t_dates[s_idx]
                x1 = t_dates[e_idx]
                
                fig.add_shape(
                    type="rect",
                    x0=x0, x1=x1,
                    y0=0, y1=safety_threshold,
                    fillcolor="rgba(0, 255, 0, 0.2)",
                    line_width=0,
                    layer="below",
                    yref="y"
                )
                
                # Label if surgery date falls within this safe zone
                if surgery_date:
                    s_date = x0.date() if isinstance(x0, datetime) else x0
                    e_date = x1.date() if isinstance(x1, datetime) else x1
                    if s_date <= surgery_date <= e_date:
                        fig.add_annotation(
                            x=x0, y=safety_threshold,
                            text=utils.t("safe_zone"),
                            showarrow=False,
                            yshift=10,
                            xanchor="left",
                            font=dict(color="green", size=10)
                        )

    # 집중 보기일 경우 X축 눈금 간격 조정
    if sim_duration <= 2:
        fig.update_xaxes(
            dtick=3600000 * 3, # 3시간 간격 (ms 단위)
            tickformat="%H:%M\n(%b %d)",
            tickangle=0
        )

    fig.update_layout(
        title=f"{utils.t('graph_title')} ({sim_duration} {utils.t('sim_days')})",
        xaxis_title=utils.t("xaxis_title"),
        yaxis_title=y_label,
        yaxis=dict(range=[0, y_max_limit]),
        template="plotly_white",
        hovermode="x unified",
        height=500
    )
    
    return fig
