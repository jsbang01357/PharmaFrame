import streamlit as st
from datetime import datetime, timedelta

from utils import utils
from core import data
from io import emr_manager as EMR

# -----------------------------------------------------------------------------
# 0. EMR 섹션 (오프라인 전용)
# -----------------------------------------------------------------------------
def render_emr_section(is_offline=False):
    """EMR 환자 선택 및 기본 식별 정보"""
    if is_offline:
        # 1. 환자 검색 (DB 로드)
        EMR.render_sidebar_selector()
        
        # 2. 환자 식별 정보
        col_id1, col_id2 = st.columns([2, 1])
        with col_id1:
            p_name = st.text_input(
                utils.t("patient_name"), 
                value=st.session_state.user_profile.get("name", utils.t("default_user"))
            )
        with col_id2:
            p_id = st.text_input(
                utils.t("patient_id_label"), 
                value=st.session_state.user_profile.get("patient_id", "0000")
            )
        
        # 세션 업데이트
        st.session_state.user_profile["name"] = p_name
        st.session_state.user_profile["patient_id"] = p_id
        st.session_state.user_name = p_name

# -----------------------------------------------------------------------------
# 1. 신체 정보 (Profile)
# -----------------------------------------------------------------------------
def render_profile_section():
    """신체 계측 정보 및 상세 설정"""
    with st.expander(utils.t('sidebar_profile'), expanded=True):
        # 필수 정보
        age = st.number_input(utils.t("age_label"), min_value=15, max_value=80, 
                              value=int(st.session_state.user_profile.get("age", 25)))
        
        col_body1, col_body2 = st.columns(2)
        with col_body1:
            height = st.number_input(utils.t("height_label"), min_value=100.0, max_value=250.0, 
                                     value=float(st.session_state.user_profile.get("height", 170.0)), step=0.5)
        with col_body2:
            weight = st.number_input(utils.t("weight_label"), min_value=30.0, max_value=250.0, 
                                     value=float(st.session_state.user_profile.get("weight", 60.0)), step=0.5)

        # BMI 자동 계산 및 표시
        bmi = weight / ((height / 100) ** 2)
        st.caption(utils.t("calculated_bmi").format(bmi=bmi))
        
        # 상세 설정 (토글)
        show_details = st.toggle(utils.t("profile_details_toggle"), value=False)
        
        if show_details:
            # 간수치 입력
            col_liver1, col_liver2 = st.columns(2)
            with col_liver1:
                ast_val = st.number_input(utils.t("ast_label"), min_value=0.0, value=float(st.session_state.user_profile.get("ast", 20.0)))
            with col_liver2:
                alt_val = st.number_input(utils.t("alt_label"), min_value=0.0, value=float(st.session_state.user_profile.get("alt", 20.0)))
            
            # 체지방률 입력
            body_fat = st.slider(utils.t("body_fat_label"), 5.0, 50.0, 
                                 value=float(st.session_state.user_profile.get("body_fat", 22.0)), step=0.5)
            
        else:
            # 숨겨졌을 때 기본값 유지 (또는 기존 값 유지)
            # 체지방률 자동 추정 (Heuristic)
            estimated_body_fat = 1.20 * bmi + 0.23 * age - 5.4
            body_fat = float(st.session_state.user_profile.get("body_fat", estimated_body_fat))
            ast_val = float(st.session_state.user_profile.get("ast", 20.0))
            alt_val = float(st.session_state.user_profile.get("alt", 20.0))

        # 세션 업데이트
        st.session_state.user_profile.update({
            "age": age, "height": height, "weight": weight,
            "body_fat": body_fat, "ast": ast_val, "alt": alt_val
        })

# -----------------------------------------------------------------------------
# 2. 약물 추가 (Protocol)
# -----------------------------------------------------------------------------
def render_medication_section():
    with st.expander(utils.t('sidebar_add'), expanded=True):
        """약물 추가 및 스케줄 관리 섹션"""

        # [Fix] 비교 모드 토글을 사이드바(항상 렌더링되는 곳)로 이동하여 
        # 탭 전환 시 상태가 초기화되는 문제와 '두 번 클릭' 문제를 해결합니다.
        st.checkbox(utils.t("compare_mode"), key="compare_mode")

        # [위치 이동] 시나리오 선택 UI를 최상단으로 배치
        target_sched_key = "drug_schedule"
        if st.session_state.compare_mode:
            # [Fix] key를 추가하여 약물 추가/삭제(rerun) 시에도 선택한 시나리오(A/B)가 유지되도록 합니다.
            scenario_choice = st.radio(utils.t("edit_scenario"), [utils.t("scenario_a"), utils.t("scenario_b")], horizontal=True, key="edit_scenario_choice")
            target_sched_key = "drug_schedule" if scenario_choice == utils.t("scenario_a") else "drug_schedule_b"
            
            if st.button(utils.t("clone_a_to_b")):
                st.session_state.drug_schedule_b = [d.copy() for d in st.session_state.drug_schedule]
                st.rerun()

        # ---------------------------------------------------------
        # [NEW] 🐣 입문 세트 버튼 (체크리스트 연동 적용)
        # ---------------------------------------------------------
        st.caption(utils.t("starter_set_caption"))
        
        col_set1, col_set2 = st.columns(2)
        
        # 버튼 1: 경구 (2mg BID) + CPA 체크박스 ON
        with col_set1:
            if st.button(
                utils.t("starter_oral_cpa_btn"),
                use_container_width=True,
                help=utils.t("starter_oral_cpa_help"),
            ):
                # 1. 약물 리스트 세팅 (에스트로겐만)
                st.session_state.drug_schedule = [
                    {"name": "Estradiol Valerate (Progynova)", "type": "Oral", "dose": 2.0, "interval": 0.5, "id": "set1_e2"}
                ]
                
                # 2. 체크리스트 상태 동기화 (CPA 켜기!)
                st.session_state.has_cpa = True   # <--- 핵심: CPA 체크박스 ON
                st.session_state.has_spiro = False
                st.session_state.has_p4 = False
                st.session_state.has_gnrh = False
                
                st.toast(utils.t("starter_oral_cpa_toast"), icon="💊")
                st.rerun()

        # 버튼 2: 주사 (10mg 2주) + 모든 체크박스 OFF (단독 요법 가정)
        with col_set2:
            if st.button(
                utils.t("starter_injection_btn"),
                use_container_width=True,
                help=utils.t("starter_injection_help"),
            ):
                # 1. 약물 리스트 세팅
                st.session_state.drug_schedule = [
                    {"name": "Estradiol Valerate (Progynon Depot)", "type": "Injection", "dose": 10.0, "interval": 14.0, "id": "set2_inj"}
                ]
                
                # 2. 체크리스트 초기화 (주사 단독이라 가정)
                st.session_state.has_cpa = False
                st.session_state.has_spiro = False
                st.session_state.has_p4 = False
                st.session_state.has_gnrh = False
                
                st.toast(utils.t("starter_injection_toast"), icon="💉")
                st.rerun()

        st.header("💉 Protocol 1: Estrogen")
        

        route_options = ["Injection", "Oral", "Transdermal", "Sublingual"]
        
        route_translation_keys = {
            "Injection": "route_injection",
            "Oral": "route_oral",
            "Transdermal": "route_transdermal",
            "Sublingual": "route_sublingual",
        }

        drug_type_label = st.selectbox(
            utils.t("select_route"), 
            route_options,
            format_func=lambda x: utils.t(route_translation_keys[x])
        )
        
        available_drugs = data.get_drug_list_by_type(drug_type_label)
        selected_drug_name = st.selectbox(utils.t("select_drug"), available_drugs)
        
        default_dose = 0.0
        if selected_drug_name:
            default_dose = data.DRUG_DB[selected_drug_name].default_dose

        dose = st.number_input(utils.t("dose_label"), value=default_dose, step=0.1, format="%.2f")
        
        is_oral_route = any(x in drug_type_label for x in ["Oral", "Sublingual", "Anti-Androgen"])
        
        if is_oral_route:
            freq_col1, freq_col2 = st.columns([2, 1])
            with freq_col1:
                freq_mode = st.selectbox(utils.t("freq_mode"), [utils.t("freq_qd"), utils.t("freq_bid"), utils.t("freq_tid"), utils.t("freq_custom")])
            
            if freq_mode == utils.t("freq_qd"):
                interval = 1.0
            elif freq_mode == utils.t("freq_bid"):
                interval = 0.5
            elif freq_mode == utils.t("freq_tid"):
                interval = 1/3
            else:
                with freq_col2:
                    interval = st.number_input(utils.t("interval_days"), value=1.0, min_value=0.1, step=0.1)
        else:
            col_cyc1, col_cyc2 = st.columns([3, 1])
            with col_cyc1:
                interval = st.number_input(utils.t("cycle_interval"), value=14, min_value=1, help=utils.t("cycle_interval_help"))
            with col_cyc2:
                st.write("") 
                st.write("")

        is_cycling = st.checkbox(utils.t("cycling_mode"), help=utils.t("cycling_mode_help"))
        
        offset = 0.0
        duration = 1.0
        
        if is_cycling:
            st.info(utils.t("cycling_example"))
            c_sub1, c_sub2 = st.columns(2)
            with c_sub1:
                offset = st.number_input(utils.t("cycle_start_day"), min_value=0.0, max_value=float(interval), value=11.0, step=1.0)
            with c_sub2:
                duration = st.number_input(utils.t("cycle_duration"), min_value=1.0, max_value=float(interval), value=3.0, step=1.0)
        
        # 간 수치 체크 (세션에서 다시 로드)
        ast_val = float(st.session_state.user_profile.get("ast", 20.0))
        alt_val = float(st.session_state.user_profile.get("alt", 20.0))
        is_liver_critical = ast_val >= 100 or alt_val >= 100
        
        if is_liver_critical and is_oral_route:
            st.error(utils.t("liver_critical_title"))
            st.info(utils.t("liver_critical_msg"))
            st.warning(utils.t("liver_critical_advice"))

        if st.button(utils.t("add_schedule_btn"), type="primary"):
            if is_liver_critical and is_oral_route:
                st.toast(utils.t("liver_block_toast"), icon="🚨")
            else:
                new_drug = {
                    "name": selected_drug_name,
                    "type": drug_type_label,
                    "dose": dose,
                    "interval": interval,
                    "is_cycling": is_cycling,
                    "offset": offset,
                    "duration": duration,
                    "id": datetime.now().strftime("%H%M%S")
                }
                st.session_state[target_sched_key].append(new_drug)
                st.success(utils.t("added_toast").format(name=selected_drug_name))
                st.rerun()

        current_sched = st.session_state[target_sched_key]
        if current_sched:
            header_label = 'A' if target_sched_key == 'drug_schedule' else 'B'
            st.markdown(f"### {utils.t('current_schedule_header').format(label=header_label)}")
            for i, drug in enumerate(current_sched):
                with st.expander(f"{drug['name']} ({drug['dose']}mg)"):
                    if drug['interval'] == 1.0: freq_label = utils.t("freq_qd")
                    elif drug['interval'] == 0.5: freq_label = utils.t("freq_bid")
                    elif abs(float(drug['interval']) - 1/3) < 0.01: freq_label = utils.t("freq_tid")
                    else: freq_label = f"Every {drug['interval']} days"
                    
                    st.caption(freq_label)
                    if st.button(utils.t("delete_btn"), key=f"del_{drug['id']}"):
                        st.session_state[target_sched_key].pop(i)
                        st.rerun()

        st.markdown("---")
        st.header(utils.t("protocol2_header"))
        st.caption(utils.t("protocol2_caption"))

        st.checkbox(utils.t("check_spiro"), key="has_spiro")
        st.checkbox(utils.t("check_cpa"), key="has_cpa")
        st.checkbox(utils.t("check_p4"), key="has_p4")
        st.checkbox(utils.t("check_gnrh"), key="has_gnrh")

# -----------------------------------------------------------------------------
# 3. 위험 평가 (Risk Assessment)
# -----------------------------------------------------------------------------
def render_risk_assessment_section():
    """환자 리스크 평가 섹션"""
    with st.expander(utils.t('sidebar_risk'), expanded=False):
        st.header(utils.t("sidebar_risk"))
        st.session_state.is_smoker = st.checkbox(utils.t("smoker_label"), value=st.session_state.is_smoker)
        st.checkbox(utils.t("migraine_label"), key="has_migraine") # Key binding for main.py access
        st.session_state.history_vte = st.checkbox(utils.t("vte_hist_label"), value=st.session_state.history_vte)

        st.markdown("---")
        st.markdown(utils.t("interactors_header"))
        st.caption(utils.t("interactors_caption"))

        # data.INTERACTION_DB의 키 값들을 옵션으로 제공
        st.multiselect(
            utils.t("interactors_select"),
            options=list(data.INTERACTION_DB.keys()),
            key="selected_interactors"
        )

def render_risk_summary():
    """리스크 요약 배지 (접힘 섹션 위/아래에서 빠르게 확인)"""
    try:
        bmi = st.session_state.user_profile["weight"] / ((st.session_state.user_profile["height"] / 100) ** 2)
    except (KeyError, TypeError, ZeroDivisionError):
        bmi = 0.0
    flags = []
    if bmi >= 25:
        flags.append(utils.t("bmi_high"))
    if st.session_state.get("is_smoker"):
        flags.append(utils.t("smoker"))
    if st.session_state.get("history_vte"):
        flags.append(utils.t("vte_history"))
    if st.session_state.get("has_migraine"):
        flags.append(utils.t("migraine_label"))

    if flags:
        st.caption(utils.t("risk_summary_some").format(items=", ".join(flags[:3])))
    else:
        st.caption(utils.t("risk_summary_none"))

# -----------------------------------------------------------------------------
# 4. 언어 설정 (Language)
# -----------------------------------------------------------------------------
def render_language_selector():
    """언어 선택 UI"""
    def update_lang_url():
        st.query_params["lang"] = st.session_state.lang
        
        # 현재 이름이 기본값 중 하나라면, 새 언어의 기본값으로 업데이트
        defaults = {
            "KO": utils.TRANSLATIONS.get("KO", {}).get("default_user", "사용자"),
            "EN": utils.TRANSLATIONS.get("EN", {}).get("default_user", "user"),
        }
        current_name = st.session_state.user_profile.get("name")
        
        if current_name in defaults.values():
            new_default = defaults.get(st.session_state.lang, "user")
            st.session_state.user_profile["name"] = new_default
            st.session_state.user_name = new_default
        
    st.radio(utils.t("settings_lang_label"), ["KO", "EN"], horizontal=True, key="lang", on_change=update_lang_url)

def render_settings_section(initial_offline=False):
    """언어/개발 설정 섹션"""
    if "force_offline_mode" not in st.session_state:
        # 기본값은 항상 OFF로 시작 (특히 웹 환경)
        st.session_state.force_offline_mode = False

    with st.expander(utils.t("sidebar_settings"), expanded=False):
        st.caption(utils.t("settings_caption"))
        st.toggle(
            utils.t("force_offline_label"),
            key="force_offline_mode",
            help=utils.t("force_offline_help"),
        )
        render_language_selector()

    return bool(st.session_state.force_offline_mode)


def render_sidebar_credit():
    """사이드바 하단 크레딧"""
    st.markdown("---")
    st.caption("Ver 1.0.0(260214)")

# -----------------------------------------------------------------------------
# [통합] 사이드바 메인 렌더링 함수
# -----------------------------------------------------------------------------
def render_sidebar(is_offline=False):
    """정리된 사이드바 전체 렌더링"""
    st.title("🧬 EstroFrame")
    st.caption("Architecting Your Biology")

    effective_offline = bool(st.session_state.get("force_offline_mode", is_offline))
    
    # 0. EMR 섹션
    render_emr_section(effective_offline)
    
    st.markdown("---")
    
    # 1. 신체 정보
    render_profile_section()

    # 2. 약물 프로토콜
    render_medication_section()
    
    # 3. 위험 평가
    render_risk_summary()
    render_risk_assessment_section()
    
    # 4. 설정 (언어/오프라인 모드)
    st.markdown("---")
    effective_offline = render_settings_section(is_offline)
    render_sidebar_credit()

    return effective_offline



def render_calibration_tab(analyzer):
    """보정 탭 렌더링"""
    st.header(utils.t("cal_header"))
    active_routes = set(data.DRUG_DB[d['name']].type for d in st.session_state.drug_schedule if d['name'] in data.DRUG_DB)

    if not active_routes:
        st.warning(utils.t("cal_no_drugs"))
    else:
        col_c1, col_c2 = st.columns(2)
        with col_c2:
            target_route = st.selectbox(
                utils.t("cal_target_route"), 
                list(active_routes),
                format_func=lambda x: utils.t("route_" + x.lower().replace("-", "_")),
                help=utils.t("cal_target_help")
            )
        with col_c1:
            lab_day = st.number_input(utils.t("cal_lab_day"), value=14)
            lab_val = st.number_input(utils.t("cal_lab_val"), value=0.0)
            # 투여 경로에 따라 다른 안내 문구 표시
            if target_route == "Injection":
                st.caption(utils.t("cal_injection_caption"))
            else:
                st.caption(utils.t("cal_oral_caption"))

        if st.button(utils.t("cal_add_record")):
            if lab_val <= 0:
                st.error(utils.t("cal_invalid_val"))
            else:
                if target_route not in st.session_state.lab_history:
                    st.session_state.lab_history[target_route] = []
                st.session_state.lab_history[target_route].append({"day": lab_day, "value": lab_val})
                st.session_state.lab_history[target_route].sort(key=lambda x: x['day'])
                
                new_k = analyzer.calculate_weighted_calibration_factor(
                    st.session_state.drug_schedule,
                    st.session_state.lab_history[target_route],
                    target_route=target_route,
                    current_factors=st.session_state.calibration_factors
                )
                st.session_state.calibration_factors[target_route] = new_k
                route_name = utils.t("route_" + target_route.lower().replace("-", "_"))
                st.success(utils.t("cal_success_msg").format(route=route_name, k=new_k))
                st.rerun()

        if st.session_state.lab_history.get(target_route):
            route_name = utils.t("route_" + target_route.lower().replace("-", "_"))
            st.markdown(utils.t("cal_history_title").format(route=route_name))
            for i, record in enumerate(st.session_state.lab_history[target_route]):
                col_rec1, col_rec2, col_rec3 = st.columns([2, 2, 1])
                col_rec1.write(utils.t("day_format").format(day=record['day']))
                col_rec2.write(f"{record['value']} pg/mL")
                if col_rec3.button("🗑️", key=f"del_lab_{target_route}_{i}"):
                    st.session_state.lab_history[target_route].pop(i)
                    new_k = analyzer.calculate_weighted_calibration_factor(
                        st.session_state.drug_schedule,
                        st.session_state.lab_history[target_route],
                        target_route=target_route,
                        current_factors=st.session_state.calibration_factors
                    )
                    st.session_state.calibration_factors[target_route] = new_k
                    st.rerun()

        st.markdown(utils.t("cal_current_factors"))
        c_show = st.columns(len(active_routes))
        for i, r in enumerate(active_routes):
            val = st.session_state.calibration_factors.get(r, 1.0)
            route_name = utils.t("route_" + r.lower().replace("-", "_"))
            c_show[i].metric(f"{route_name} {utils.t('factor_label')}", f"x {val:.2f}")
            
    if st.button(utils.t("cal_reset_btn")):
        st.session_state.calibration_factors = {
            "Injection": 1.0, "Oral": 1.0, "Transdermal": 1.0, "Sublingual": 1.0
        }
        st.session_state.lab_history = {}
        st.rerun()

def render_missed_dose_checker():
    """복약 잊음 계산기 UI"""
    st.markdown(f"### {utils.t('missed_title')}")
    st.caption(utils.t("missed_caption"))

    # 1. 현재 스케줄에 있는 약물 불러오기
    if not st.session_state.drug_schedule:
        st.info(utils.t("missed_add_drug_first"))
        return

    # 약물 이름 리스트 생성
    drug_map = {d['name']: d for d in st.session_state.drug_schedule}
    selected_drug_name = st.selectbox(utils.t("missed_select_drug"), list(drug_map.keys()), key="missed_drug_select")
    
    target_drug = drug_map[selected_drug_name]
    interval = float(target_drug['interval'])

    # 2. 마지막 복용 시점 입력 (디폴트: 어제 같은 시간)
    col_md1, col_md2 = st.columns(2)
    with col_md1:
        last_date = st.date_input(
            utils.t("missed_last_date"),
            value=datetime.now().date() - timedelta(days=1),
            key="missed_date",
        )
    with col_md2:
        last_time = st.time_input(utils.t("missed_last_time"), value=datetime.now().time(), key="missed_time")

    if st.button(utils.t("missed_calc_btn"), type="primary", use_container_width=True):
        last_dt = datetime.combine(last_date, last_time)
        current_dt = datetime.now()
        
        # 미래의 시간을 입력한 경우 예외처리
        if last_dt > current_dt:
            st.error(utils.t("missed_future_error"))
        else:
            action, msg, next_dt = utils.calculate_missed_dose_action(last_dt, interval, current_dt)
            
            st.markdown("---")
            if action == "TAKE_NOW":
                st.success(utils.t("missed_take_now_label"))
                st.write(msg)
            else:
                st.warning(utils.t("missed_skip_label"))
                st.write(msg)
                
            st.caption(utils.t("missed_next_due").format(next=next_dt.strftime("%Y-%m-%d %H:%M")))

def render_faq():
    st.header(utils.t("faq_title"))
    st.markdown(utils.t("faq_intro"))

    cat_tabs = st.tabs([
        utils.t("faq_cat_core"),
        utils.t("faq_cat_changes"),
        utils.t("faq_cat_safety"),
        utils.t("faq_cat_practical"),
    ])

    with cat_tabs[0]:
        with st.expander(utils.t("faq_algo_q")):
            st.markdown(utils.t("faq_algo_a"))
            st.caption(utils.t("faq_algo_summary"))
        with st.expander(utils.t("faq_ref_q")):
            st.markdown(utils.t("faq_ref_a"))
            st.caption(utils.t("faq_ref_summary"))
        with st.expander(utils.t("faq_guide_q")):
            st.markdown(utils.t("faq_guide_a"))
            st.caption(utils.t("faq_guide_summary"))

    with cat_tabs[1]:
        with st.expander(utils.t("faq_timeline_q")):
            st.markdown(utils.t("faq_timeline_intro"))
            col_t1, col_t2, col_t3 = st.columns(3)
            with col_t1:
                st.markdown(f"#### {utils.t('timeline_3_6m')}")
                st.write(utils.t("timeline_3_6m_desc"))
            with col_t2:
                st.markdown(f"#### {utils.t('timeline_6_12m')}")
                st.write(utils.t("timeline_6_12m_desc"))
            with col_t3:
                st.markdown(f"#### {utils.t('timeline_1_2y')}")
                st.write(utils.t("timeline_1_2y_desc"))
            st.caption(utils.t("faq_timeline_summary"))

        with st.expander(utils.t("faq_tanner_q")):
            st.markdown(f"""
            {utils.t('faq_tanner_intro')}
            
            | {utils.t('tanner_stage')} | {utils.t('tanner_desc')} | {utils.t('tanner_meaning')} |
            | :---: | :--- | :--- |
            | **1** | {utils.t('tanner_s1_desc')} | - |
            | **2** | {utils.t('tanner_s2_desc')} | {utils.t('tanner_s2_meaning')} |
            | **3** | {utils.t('tanner_s3_desc')} | - |
            | **4** | {utils.t('tanner_s4_desc')} | - |
            | **5** | {utils.t('tanner_s5_desc')} | {utils.t('tanner_s5_meaning')} |
            """)
            st.caption(utils.t("faq_tanner_summary"))

    with cat_tabs[2]:
        with st.expander(utils.t("faq_monitor_q")):
            st.markdown(f"""
            | {utils.t('monitor_table_header_drug')} | {utils.t('monitor_table_header_exams')} | {utils.t('monitor_table_header_desc')} |
            | :--- | :--- | :--- |
            | **{utils.t('monitor_row_common_drug')}** | {utils.t('monitor_row_common_exams')} | {utils.t('monitor_row_common_desc')} |
            | **{utils.t('monitor_row_gnrh_drug')}** | {utils.t('monitor_row_gnrh_exams')} | {utils.t('monitor_row_gnrh_desc')} |
            | **{utils.t('monitor_row_spiro_drug')}** | {utils.t('monitor_row_spiro_exams')} | {utils.t('monitor_row_spiro_desc')} |
            | **{utils.t('monitor_row_cpa_drug')}** | {utils.t('monitor_row_cpa_exams')} | {utils.t('monitor_row_cpa_desc')} |
            | **{utils.t('monitor_row_p4_drug')}** | {utils.t('monitor_row_p4_exams')} | {utils.t('monitor_row_p4_desc')} |
            """)
            st.caption(utils.t("faq_monitor_summary"))
        with st.expander(utils.t("faq_slope_q")):
            st.write(utils.t("faq_slope_a"))
            st.caption(utils.t("faq_slope_summary"))
        with st.expander(utils.t("faq_high_e2_q")):
            st.markdown(utils.t("faq_high_e2_a"))
            st.caption(utils.t("faq_high_e2_summary"))
        with st.expander(utils.t("faq_surgery_plan_q")):
            st.markdown(utils.t("faq_surgery_plan_a"))
            st.caption(utils.t("faq_surgery_plan_summary"))

    with cat_tabs[3]:
        with st.expander(utils.t("faq_units_q")):
            st.markdown(utils.t("faq_units_a"))
            st.caption(utils.t("faq_units_summary"))
        with st.expander(utils.t("faq_compare_q")):
            st.markdown(utils.t("faq_compare_a"))
            st.caption(utils.t("faq_compare_summary"))
        with st.expander(utils.t("faq_diff_q")):
            st.write(utils.t("faq_diff_a"))
            st.caption(utils.t("faq_diff_summary"))
        with st.expander(utils.t("faq_doctor_q")):
            st.write(utils.t("faq_doctor_a"))
            st.caption(utils.t("faq_doctor_summary"))
        with st.expander(utils.t("faq_data_privacy_q")):
            st.markdown(utils.t("faq_data_privacy_a"))
            st.caption(utils.t("faq_data_privacy_summary"))

    st.markdown("---")
    st.caption(utils.t("dev_credit"))

def render_footer():
    """푸터 렌더링"""
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; color: grey; font-size: 0.8em;'>
        © 2026 <b>EstroFrame Project</b> | Designed by Jisong (Medical Student)<br>
        This tool provides mathematical simulations for educational and harm-reduction purposes only.<br>
        It does NOT replace professional medical advice. Always consult with your endocrinologist.
    </div>
    """, unsafe_allow_html=True)

def apply_custom_theme():
    """
    [Theme Hack] config.toml 없이 CSS 주입으로 테마 색상 변경.
    이 방식을 써야 시스템(Light/Dark) 설정에 따라 배경이 자동으로 바뀝니다.
    """
    st.markdown("""
        <style>
        /* 1. 메인 포인트 컬러 (브랜드 색상) 변경 */
        :root {
            --primary-color: #FF69B4;
        }
        
        /* 2. Primary 버튼 (채우기 버튼) 색상 강제 지정 */
        div.stButton > button[kind="primary"] {
            background-color: #FF69B4 !important;
            border-color: #FF69B4 !important;
            color: white !important;
        }
        div.stButton > button[kind="primary"]:hover {
            background-color: #FF1493 !important; /* 호버 시 조금 더 진한 핑크 */
            border-color: #FF1493 !important;
        }
        div.stButton > button[kind="primary"]:focus:not(:active) {
            border-color: #FF1493 !important;
            color: white !important;
        }

        /* 3. 라디오 버튼, 체크박스 등 선택 시 색상 */
        div[role="radiogroup"] > label > div:first-child {
            background-color: #FF69B4 !important;
            border-color: #FF69B4 !important;
        }
        
        /* 4. 링크 색상 등 기타 강조색 */
        a {
            color: #FF69B4 !important;
        }
        
        /* [NEW] 5. 탭(Tabs) 스타일링 추가 */
        /* 선택된 탭의 텍스트 색상 */
        button[data-baseweb="tab"][aria-selected="true"] {
            color: #FF69B4 !important;
        }
        /* 탭 아래의 움직이는 강조선 (Underline) 색상 */
        div[data-baseweb="tab-highlight"] {
            background-color: #FF69B4 !important;
        }
        /* 마우스 올렸을 때(Hover) 텍스트 색상 */
        button[data-baseweb="tab"]:hover {
            color: #FF1493 !important;
        }
        /* 탭 글씨 조금 더 굵게 (가독성 UP) */
        button[data-baseweb="tab"] {
            font-weight: 600 !important;
        }
        /* =========================================
           4. 체크박스 (st.checkbox) & 라디오 (st.radio)
           ========================================= */
        /* 체크된 상태의 박스 배경색 */
        div[data-baseweb="checkbox"] div[aria-checked="true"],
        div[data-baseweb="radio"] div[aria-checked="true"] {
            background-color: #FF69B4 !important;
            border-color: #FF69B4 !important;
        }
        
        /* =========================================
           5. 토글 스위치 (st.toggle)
           ========================================= */
        /* 체크된 상태의 트랙 색상 */
        div[data-baseweb="switch"] input:checked + div {
            background-color: #FF69B4 !important;
        }

        /* =========================================
           6. 슬라이더 (st.slider)
           ========================================= */
        /* 슬라이더 손잡이 (Thumb) */
        div[data-baseweb="slider"] div[role="slider"] {
            background-color: #FF69B4 !important;
            box-shadow: 0 0 6px rgba(255, 105, 180, 0.4) !important; /* 핑크색 광채 */
        }
        /* 슬라이더 채워진 트랙 (Filled Track) */
        /* 구조가 복잡하여 첫 번째 자식 div를 타겟팅합니다 */
        div[data-baseweb="slider"] > div > div > div:first-child {
            background-color: #FF69B4 !important;
        }
        
        /* =========================================
           7. 숫자 입력창 (st.number_input) 포커스
           ========================================= */
        div[data-baseweb="input"]:focus-within {
            border-color: #FF69B4 !important;
        }
        </style>
    """, unsafe_allow_html=True)
