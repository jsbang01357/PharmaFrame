import streamlit as st
import os
import yaml
from glob import glob
import uuid

from utils import utils
from core.pk_engine import PKEngine
from core.models import PatientProfile
from io import emr_manager as EMR

def render_emr_section(is_offline=False):
    if is_offline:
        EMR.render_sidebar_selector()
        col_id1, col_id2 = st.columns([2, 1])
        with col_id1:
            p_name = st.text_input("환자 이름", value=st.session_state.user_profile.get("name", "Anonymous"))
        with col_id2:
            p_id = st.text_input("ID", value=st.session_state.user_profile.get("patient_id", "0000"))
        st.session_state.user_profile["name"] = p_name
        st.session_state.user_profile["patient_id"] = p_id

def render_profile_section():
    with st.expander("👤 신체/생리적 정보", expanded=True):
        age = st.number_input("연령 (Age)", min_value=15, max_value=100, value=int(st.session_state.user_profile.get("age", 50)))
        
        col_body1, col_body2 = st.columns(2)
        with col_body1:
            height = st.number_input("신장 (cm)", min_value=100.0, max_value=250.0, value=float(st.session_state.user_profile.get("height", 165.0)), step=0.5)
        with col_body2:
            weight = st.number_input("체중 (kg)", min_value=30.0, max_value=250.0, value=float(st.session_state.user_profile.get("weight", 65.0)), step=0.5)

        bmi = weight / ((height / 100) ** 2)
        st.caption(f"계산된 BMI: {bmi:.1f}")
        
        show_details = st.toggle("상세 임상 수치 입력", value=False)
        
        if show_details:
            st.markdown("##### 🧪 간 기능 (Hepatic)")
            col_liver1, col_liver2 = st.columns(2)
            with col_liver1:
                ast_val = st.number_input("AST (U/L)", min_value=0.0, value=float(st.session_state.user_profile.get("ast", 20.0)))
            with col_liver2:
                alt_val = st.number_input("ALT (U/L)", min_value=0.0, value=float(st.session_state.user_profile.get("alt", 20.0)))
            
            st.markdown("##### 💧 신장 기능 (Renal)")
            egfr_val = st.number_input("eGFR (mL/min/1.73m²)", min_value=5.0, max_value=150.0, value=float(st.session_state.user_profile.get("egfr", 100.0)))
            
            st.markdown("##### 🏃 체성분 (Body Composition)")
            body_fat = st.slider("체지방률 (%)", 5.0, 50.0, value=float(st.session_state.user_profile.get("body_fat", 22.0)), step=0.5)
        else:
            estimated_body_fat = 1.20 * bmi + 0.23 * age - 5.4
            body_fat = float(st.session_state.user_profile.get("body_fat", estimated_body_fat))
            ast_val = float(st.session_state.user_profile.get("ast", 20.0))
            alt_val = float(st.session_state.user_profile.get("alt", 20.0))
            egfr_val = float(st.session_state.user_profile.get("egfr", 100.0))

        st.session_state.user_profile.update({
            "age": age, "height": height, "weight": weight,
            "body_fat": body_fat, "ast": ast_val, "alt": alt_val, "egfr": egfr_val
        })

def get_available_categories():
    categories = set()
    for file_path in glob(os.path.join("drugs", "*.yaml")):
        with open(file_path, "r", encoding="utf-8") as f:
            data_list = yaml.safe_load(f)
            if data_list:
                for item in data_list:
                    categories.add(item.get("category", "general"))
    return sorted(list(categories))

def render_module_selector():
    st.markdown("---")
    st.subheader("🏥 임상 모듈 선택")
    categories = get_available_categories()
    
    category_display_map = {
        "thyroid": "갑상선 질환 (Thyroid)",
        "menopausal_hrt": "폐경 후 호르몬 요법 (MHRT)",
        "opioids": "마약성 진통제 (Opioids)",
        "nsaids": "항염증제 (NSAIDs)",
        "puberty_induction": "사춘기 유도 (Puberty Induction)",
        "cardiovascular": "심혈관 질환 (Cardiovascular)",
        "general": "기타 (General)"
    }
    
    display_options = [category_display_map.get(c, c.capitalize()) for c in categories]
    
    current_cat = st.session_state.get("current_module", "thyroid")
    current_idx = 0
    if current_cat in categories:
        try:
            current_idx = display_options.index(category_display_map.get(current_cat, current_cat.capitalize()))
        except ValueError:
            current_idx = 0
            
    selected_display = st.selectbox("모듈 선택", display_options, index=current_idx, label_visibility="collapsed")
    
    selected_cat = "general"
    for k, v in category_display_map.items():
        if v == selected_display:
            selected_cat = k
            break
            
    if st.session_state.get("current_module") != selected_cat:
        st.session_state.current_module = selected_cat
        st.session_state.drug_schedule = []
        st.session_state.drug_schedule_b = []
        st.rerun()

def render_medication_section():
    with st.expander("💊 약물 스케줄 관리", expanded=True):
        st.checkbox("A/B 시나리오 비교", key="compare_mode")

        target_sched_key = "drug_schedule"
        if st.session_state.compare_mode:
            scenario_choice = st.radio("편집할 시나리오", ["시나리오 A", "시나리오 B"], horizontal=True, key="edit_scenario_choice")
            target_sched_key = "drug_schedule" if scenario_choice == "시나리오 A" else "drug_schedule_b"
            
            if st.button("A 스케줄 복사 -> B"):
                st.session_state.drug_schedule_b = [d.copy() for d in st.session_state.drug_schedule]
                st.rerun()

        dummy_patient = PatientProfile(
            name=st.session_state.user_profile.get("name", "User"),
            age=st.session_state.user_profile.get("age", 50),
            weight_kg=st.session_state.user_profile.get("weight", 65.0),
            height_cm=st.session_state.user_profile.get("height", 165.0),
            body_fat_pct=st.session_state.user_profile.get("body_fat", 22.0),
            ast_u_l=st.session_state.user_profile.get("ast", 20.0),
            alt_u_l=st.session_state.user_profile.get("alt", 20.0),
            egfr=st.session_state.user_profile.get("egfr", 100.0)
        )
        engine = PKEngine(dummy_patient)
        
        module_cat = st.session_state.get("current_module", "thyroid")
        available_drugs = [drug for drug in engine.drug_db.values() if drug.category == module_cat]
        
        if not available_drugs:
            st.warning("선택한 모듈에 등록된 약물이 없습니다.")
            return

        drug_options = {d.id: d.name for d in available_drugs}
        
        with st.container(border=True):
            selected_drug_id = st.selectbox("약물 선택", options=list(drug_options.keys()), format_func=lambda x: drug_options[x])
            selected_drug = engine.drug_db[selected_drug_id]
            
            desc = utils.get_localized_field(selected_drug, "desc")
            if desc:
                st.caption(f"ℹ️ {desc}")
            
            warn = utils.get_localized_field(selected_drug, "warning_msg")
            if warn:
                st.warning(f"⚠️ {warn}")
            
            route_options = list(selected_drug.routes.keys())
            selected_route = st.selectbox("투여 경로", route_options)
            
            c1, c2 = st.columns(2)
            dose = c1.number_input("1회 투여량", value=10.0, step=1.0)
            interval = c2.number_input("투여 간격 (일)", value=1.0, step=0.1)
            
            if st.button("➕ 스케줄 추가", type="primary", use_container_width=True):
                new_item = {
                    "id": str(uuid.uuid4())[:8],
                    "drug_id": selected_drug_id,
                    "name": selected_drug.name,
                    "type": selected_route,
                    "dose": float(dose),
                    "interval": float(interval)
                }
                st.session_state[target_sched_key].append(new_item)
                st.rerun()

        st.markdown("#### 현재 스케줄")
        schedule_list = st.session_state[target_sched_key]
        if not schedule_list:
            st.caption("등록된 약물이 없습니다.")
        else:
            for i, item in enumerate(schedule_list):
                with st.container(border=True):
                    st.write(f"**{item['name']}** ({item['type']})")
                    st.write(f"💊 {item['dose']} / 매 {item['interval']}일")
                    if st.button("🗑️ 삭제", key=f"del_{item['id']}_{target_sched_key}_{i}"):
                        st.session_state[target_sched_key].pop(i)
                        st.rerun()

def render_sidebar(is_offline=False):
    st.header("🧬 Settings")
    
    # 랜딩 언어 선택 
    lang_options = ["KO", "EN"]
    lang_index = 0 if st.session_state.lang == "KO" else 1
    selected_lang = st.radio("Language", options=lang_options, index=lang_index, horizontal=True, key="lang_radio")
    if selected_lang != st.session_state.lang:
        st.session_state.lang = selected_lang
        st.query_params["lang"] = selected_lang
        st.rerun()

    render_module_selector()
    render_emr_section(is_offline)
    render_profile_section()
    render_medication_section()
    
    st.markdown("---")
    
    is_offline_override = os.getenv("PHARMAFRAME_FORCE_OFFLINE") in ("1", "true", "yes", "on")
    if is_offline_override:
        st.info("🔒 오프라인 모드 강제됨")
    else:
        new_offline = st.toggle("🔒 오프라인 모드 (EMR 활성화)", value=is_offline)
        if new_offline != is_offline:
            is_offline = new_offline
            if new_offline:
                os.environ["PHARMAFRAME_FORCE_OFFLINE"] = "1"
            else:
                os.environ.pop("PHARMAFRAME_FORCE_OFFLINE", None)
            st.rerun()

    if st.button("데이터 전체 초기화"):
        st.session_state.clear()
        st.rerun()

    st.caption("PharmaFrame · Ver 2.0.0")
    
    return is_offline
