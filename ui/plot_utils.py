import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
from datetime import datetime, timedelta
from utils import utils

def create_pk_chart(
    t_dates, t_days, y_conc, unit_choice,
    compare_mode=False, y_conc_b=None,
    surgery_mode=False, stop_day=None, resume_day=None, surgery_date=None, start_date=None,
    lab_data=None,
    sim_duration=30
):
    """
    약동학(PK) 시뮬레이션 결과를 Plotly 그래프로 생성하여 반환합니다.
    """
    # 1. Label Setup
    y_label = f"Concentration ({unit_choice})"

    # 2. Calculate Y-Axis Limit
    all_y_values = list(y_conc)
    if compare_mode and y_conc_b is not None:
        all_y_values.extend(list(y_conc_b))
    if lab_data and lab_data.get('values'):
        all_y_values.extend(lab_data['values'])
    
    y_max_limit = max(np.max(all_y_values) if len(all_y_values) > 0 else 0, 1.0) * 1.2

    # 3. Create Figure
    fig = make_subplots()

    # 4. Surgery Mode Overlays
    if surgery_mode and stop_day is not None and resume_day is not None and start_date is not None:
        start_dt = datetime.combine(start_date, datetime.min.time())
        stop_dt = start_dt + timedelta(days=float(stop_day))
        resume_dt = start_dt + timedelta(days=float(resume_day))
        
        fig.add_vrect(
            x0=stop_dt, x1=resume_dt,
            fillcolor="rgba(255, 165, 0, 0.2)",
            layer="below", line_width=0,
            annotation_text=utils.t("cessation_period"), annotation_position="top left"
        )
        
        if surgery_date is not None:
            surg_dt = datetime.combine(surgery_date, datetime.min.time())
            fig.add_vline(
                x=surg_dt, line_dash="solid", line_color="red", line_width=2,
                annotation_text=f"💉 {utils.t('surgery_day')}", annotation_position="top right"
            )

    # 5. Main Scenario A Plot
    fig.add_trace(go.Scatter(
        x=t_dates, y=y_conc,
        mode='lines',
        name=utils.t("scenario_a") if compare_mode else utils.t("sim_title"),
        line=dict(color='#4A90E2', width=2),
        fill='tozeroy' if not compare_mode else None,
        fillcolor='rgba(74, 144, 226, 0.1)',
        hovertemplate='<b>Date:</b> %{x|%Y-%m-%d %H:%M}<br><b>Conc:</b> %{y:.1f} ' + unit_choice + '<extra></extra>'
    ))

    # 6. Scenario B Plot
    if compare_mode and y_conc_b is not None:
        fig.add_trace(go.Scatter(
            x=t_dates, y=y_conc_b,
            mode='lines',
            name=utils.t("scenario_b"),
            line=dict(color='#FF69B4', width=2, dash='dash'),
            hovertemplate='<b>Date:</b> %{x|%Y-%m-%d %H:%M}<br><b>Conc:</b> %{y:.1f} ' + unit_choice + '<extra></extra>'
        ))

    # 7. Lab Data Overlay
    if lab_data and lab_data.get('dates') and lab_data.get('values'):
        fig.add_trace(go.Scatter(
            x=lab_data['dates'],
            y=lab_data['values'],
            mode='markers+text',
            name=utils.t("actual_measure"),
            text=lab_data.get('texts', []),
            textposition="top center",
            marker=dict(size=10, color="purple", symbol="diamond"),
            hovertemplate='<b>Lab Date:</b> %{x|%Y-%m-%d}<br><b>Value:</b> %{y:.1f} ' + unit_choice + '<extra></extra>'
        ))

    # 8. Layout formatting
    if sim_duration <= 2:
        fig.update_xaxes(
            dtick=3600000 * 3, # 3시간 간격 (ms 단위)
            tickformat="%H:%M\n(%b %d)",
            tickangle=0
        )
        
    fig.update_layout(
        title=dict(text="Pharmacokinetics Simulation", font=dict(size=20)),
        xaxis_title="Date",
        yaxis_title=y_label,
        hovermode="x unified",
        template="plotly_white",
        yaxis=dict(range=[0, y_max_limit], zeroline=True, zerolinecolor="lightgray", showgrid=True, gridcolor="white"),
        xaxis=dict(showgrid=True, gridcolor="white", tickformat="%b %d\n%Y"),
        margin=dict(l=40, r=40, t=60, b=40),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        dragmode='zoom',
        height=500
    )

    return fig
