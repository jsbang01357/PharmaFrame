import streamlit as st
from utils import utils
from core.pk_engine import PKEngine
from core.models import PatientProfile

def render_safety_tab():
    st.markdown(f"### 안전성 및 모니터링 (Safety & Monitoring)")
    st.caption("현재 스케줄에 등록된 약물들을 기반으로 생성된 임상 가이드라인입니다.")
    
    sched = st.session_state.get("drug_schedule", [])
    if not sched:
        st.info("사이드바에서 약물을 추가하여 확인하세요.")
        return
        
    engine = PKEngine(PatientProfile()) # 약물 정보 조회용 더미 엔진
    
    # 중복 제거 (같은 약물 여러 번 등록 시 한 번만 표시)
    unique_drugs = {}
    for item in sched:
        d_id = item["drug_id"]
        if d_id not in unique_drugs:
            if d_id in engine.drug_db:
                unique_drugs[d_id] = engine.drug_db[d_id]
                
    if not unique_drugs:
        return
        
    # 약물별 안전성 정보 렌더링
    for d_id, drug in unique_drugs.items():
        with st.expander(f"💊 {drug.name} 안전성 가이드", expanded=True):
            st.markdown(f"**약물 범주:** {drug.category.capitalize()}")
            st.markdown(f"**반감기 (t1/2):** {drug.half_life_h} 시간")
            
            # 위험도 뱃지
            color = "green"
            if drug.risk_level == "MEDIUM": color = "orange"
            elif drug.risk_level in ["HIGH", "CRITICAL"]: color = "red"
            st.markdown(f"**위험도:** <span style='color:{color}; font-weight:bold;'>{drug.risk_level}</span>", unsafe_allow_html=True)
            
            # 설명
            st.markdown(f"**설명:** {drug.desc}")
            
            # 경고 메시지
            if drug.warning_msg:
                st.warning(f"⚠️ **경고:** {drug.warning_msg}")
                
            # 모니터링 지표
            if drug.monitoring:
                st.markdown("**필수 모니터링 지표:**")
                for mon in drug.monitoring:
                    st.markdown(f"- {mon}")
            
    st.markdown("---")
    st.subheader("⚠️ 응급 자가 체크")
    st.info("다음과 같은 심각한 이상 증상이 발생할 경우 즉시 투약을 중단하고 응급실을 방문하세요.")
    st.markdown("""
    - 갑작스럽고 설명되지 않는 가슴 통증 또는 호흡 곤란
    - 한쪽 다리의 심한 통증, 붓기, 발적
    - 심한 두통, 시야 흐림, 언어 장애
    - 아나필락시스 (심한 알레르기 반응: 얼굴/목 붓기, 호흡 곤란)
    """)
