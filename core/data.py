"""
EstroFrame Data Module
- Pharmacokinetics parameters based on clinical literature (e.g., Kuhl H. Pharmakokinetik der Östrogene).
- WPATH & Endocrine Society Guidelines.
- Expected physical changes timeline.
"""

from dataclasses import dataclass
from typing import List, Literal, Optional, Dict

@dataclass
class DrugInfo:
    type: Literal["Injection", "Oral", "Transdermal", "Sublingual", "Anti-Androgen", "Progesterone", "GnRH-Agonist"]
    half_life: float
    t_peak: float
    bioavailability: float
    ester_factor: float
    default_dose: float
    max_safe_dose: float
    monitoring: List[str]
    warning_msg: str
    risk_level: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    desc: str
    desc_en: Optional[str] = None
    metabolism: Optional[str] = None

    def __post_init__(self):
        if not (0 <= self.bioavailability <= 1.0):
            raise ValueError(f"Bioavailability must be between 0 and 1. Got {self.bioavailability}")

# -----------------------------------------------------------------------------
# 0. Pharmacokinetics Constants (Volume of Distribution Factors)
# -----------------------------------------------------------------------------
ROUTE_CONSTANTS = {
    "Injection": 117.0,     # Depot 효과
    "Oral": 12.0,           # First-pass 고려
    "Transdermal": 30.0,    # 젤/패치
    "Anti-Androgen": 4.0,
    "Sublingual": 12.0,
    "Progesterone": 12.0,   # 경구 프로게스테론 (First-pass 고려)
    "GnRH-Agonist": 117.0   # Depot 주사제와 유사한 Vd 설정
}

# -----------------------------------------------------------------------------
# 1. Guideline & Reference Ranges (Target Levels)
# -----------------------------------------------------------------------------
GUIDELINES = {
    "WPATH_SOC8": {
        "source": "WPATH SOC 8 (Standard)",
        "e2_min": 100.0,  # pg/mL
        "e2_max": 200.0,  # pg/mL
        "t_max": 50.0,    # ng/dL (Total Testosterone)
        "color": "green"
    },
    "ENDOCRINE_SOCIETY": {
        "source": "Endocrine Society (Conservative)",
        "e2_min": 100.0,
        "e2_max": 200.0,
        "color": "blue"
    },
    "MONOTHERAPY": {
        "source": "E2 Monotherapy (High Dose)",
        "e2_min": 200.0,
        "e2_max": 300.0,  # T suppression을 위해 더 높은 농도 필요
        "color": "purple"
    },
    "SURGERY_SAFETY": {
        "source": "Pre-op Safety (General)",
        "e2_max": 50.0,   # pg/mL (수술 전 권장 안전 수치)
        "desc": "혈전증 위험을 최소화하기 위한 수술 전 목표 수치",
        "color": "red"
    },
    "ACUTE_SPIKE": {
        "source": "Clinical Safety (Dose Dumping)",
        "e2_max": 800.0,  # pg/mL
        "desc": "급격한 농도 상승으로 인한 부작용 위험 수치",
        "color": "red"
    },
    "LIVER_HEALTH": {
        "ast_max": 40.0,
        "alt_max": 40.0,
        "unit": "U/L"
    }
}

# -----------------------------------------------------------------------------
# 2. Drug Database (Pharmacokinetics)
# -----------------------------------------------------------------------------
# Key Terms:
# - type: administration route (affects absorption model)
# - half_life: elimination half-life in hours (t1/2)
# - t_peak: time to reach peak concentration (hours)
# - bioavailability: F (fraction of dose reaching systemic circulation)
# - ester_factor: molecular weight ratio (Active E2 / Total Molecule). 
#                 e.g., EV is heavier than E2, so 1mg EV != 1mg E2.
#                 EV (0.76), EC (0.70), EEn (0.72)
# - risk_level: Safety flag (LOW, MEDIUM, HIGH, CRITICAL)

DRUG_DB_RAW = {
    "Estradiol Valerate (Progynon Depot)": {
        "type": "Injection",
        "half_life": 72.0,
        "t_peak": 36.0,
        "bioavailability": 1.0,
        "ester_factor": 0.76,
        "default_dose": 10.0,
        "desc_en": "Most common injectable. Short half-life may cause mood swings if intervals are too long.",
        "max_safe_dose": 20.0,
        "monitoring": ["E2", "T"],
        "warning_msg": "주사 간격이 너무 길면 호르몬 수치 변동으로 인한 기분 변화가 심할 수 있습니다.",
        "risk_level": "LOW",
        "desc": "가장 흔한 주사제. 반감기가 짧아 주기가 길어지면 기분 변화(mood swing)가 클 수 있음."
    },
    "Estradiol Enanthate": {
        "type": "Injection",
        "half_life": 144.0,
        "t_peak": 72.0,
        "bioavailability": 1.0,
        "ester_factor": 0.72,
        "default_dose": 10.0,
        "max_safe_dose": 20.0,
        "monitoring": ["E2", "T"],
        "warning_msg": "안정적인 혈중 농도 유지에 유리합니다.",
        "risk_level": "LOW",
        "desc": "반감기가 길어 주 1회 혹은 2주 1회 투여에 적합."
    },
    "Estradiol Cypionate": {
        "type": "Injection",
        "half_life": 240.0,
        "t_peak": 96.0,
        "bioavailability": 1.0,
        "ester_factor": 0.70,
        "default_dose": 5.0,
        "max_safe_dose": 10.0,
        "monitoring": ["E2", "T"],
        "warning_msg": "투여 초기 농도 상승이 완만합니다.",
        "risk_level": "LOW",
        "desc": "반감기가 가장 긴 편. 수급이 어려울 수 있음."
    },
    "Estradiol Valerate (Progynova)": {
        "type": "Oral",
        "half_life": 14.0,
        "t_peak": 6.0,
        "bioavailability": 0.05,
        "ester_factor": 0.76,
        "default_dose": 2.0,
        "max_safe_dose": 8.0,
        "monitoring": ["E2", "T", "LFT (간수치)"],
        "warning_msg": "경구 투여 시 간 대사를 거치므로 간 기능 모니터링이 권장됩니다.",
        "risk_level": "MEDIUM",
        "metabolism": "CYP3A4_SUBSTRATE",
        "desc": "복용 후 2~3시간 내에 급격한 피크 도달 후 빠르게 소실됨."
    },
    "Estradiol Hemihydrate (Estrofem)": {
        "type": "Oral",
        "half_life": 18.0,
        "t_peak": 3.0,
        "bioavailability": 0.05,
        "ester_factor": 0.97,
        "default_dose": 2.0,
        "max_safe_dose": 8.0,
        "monitoring": ["E2", "T", "LFT"],
        "warning_msg": "경구 투여 시 간 대사를 거치므로 간 기능 모니터링이 권장됩니다.",
        "risk_level": "MEDIUM",
        "metabolism": "CYP3A4_SUBSTRATE",
        "desc": "반감기가 짧으나 흡수가 빠름. 설하(Sublingual) 투여 시 스파이크가 매우 큼."
    },
    "Sublingual Estradiol (Estrofem)": {
        "type": "Sublingual",
        "half_life": 12.0,
        "t_peak": 1.0,
        "bioavailability": 0.25,
        "ester_factor": 1.0,
        "default_dose": 1.0,
        "max_safe_dose": 6.0,
        "monitoring": ["E2", "T"],
        "warning_msg": "설하 투여는 혈중 농도가 매우 급격히 상승했다가 빠르게 떨어집니다. 안정적인 농도 유지를 위해 하루 2~3회 분할 복용이 권장됩니다.",
        "risk_level": "LOW",
        "desc": "혀 밑 흡수 방식. 효율은 높으나 수치 변동(Fluctuation)이 매우 큽니다."
    },
    "Estrogel (Pump)": {
        "type": "Transdermal",
        "half_life": 36.0,
        "t_peak": 4.0,
        "bioavailability": 0.10,
        "ester_factor": 1.0,
        "default_dose": 1.5,
        "max_safe_dose": 5.0,
        "monitoring": ["E2", "T"],
        "warning_msg": "도포 부위를 깨끗이 유지하고 완전히 건조시켜야 합니다.",
        "risk_level": "LOW",
        "desc": "간을 거치지 않아 혈전 위험이 가장 낮음. 매일 발라야 하는 번거로움."
    },
    "Cyproterone Acetate (Androcur)": {
        "type": "Anti-Androgen",
        "half_life": 40.0,
        "t_peak": 3.0,
        "bioavailability": 1.0,
        "ester_factor": 1.0,
        "default_dose": 12.5,
        "max_safe_dose": 12.5,
        "risk_level": "MEDIUM",
        "monitoring": ["Prolactin", "Liver Function (LFT)"],
        "warning_msg": "장기간 고용량(25-50mg+) 복용 시 뇌수막종(Meningioma) 및 프로락틴 혈증 위험이 증가합니다.",
        "desc": "강력한 항안드로겐제. 소량으로도 효과적입니다.",
        "metabolism": "CYP3A4_SUBSTRATE"
    },
    "Spironolactone": {
        "type": "Anti-Androgen",
        "half_life": 2.0,
        "t_peak": 1.0,
        "bioavailability": 1.0,
        "ester_factor": 1.0,
        "default_dose": 50.0,
        "max_safe_dose": 200.0,
        "risk_level": "LOW",
        "monitoring": ["Potassium (K+)", "Renal Function (eGFR)", "Blood Pressure"],
        "warning_msg": "이뇨 작용이 있습니다. 고칼륨혈증 주의(바나나 과섭취 등). 정기적인 전해질 검사가 필요합니다.",
        "desc": "칼륨 보존성 이뇨제 겸 항안드로겐제."
    },
    "Micronized Progesterone (Utrogestan)": {
        "type": "Progesterone",
        "half_life": 18.0,
        "t_peak": 2.5,
        "bioavailability": 0.08,
        "ester_factor": 1.0,
        "default_dose": 100.0,
        "max_safe_dose": 200.0,
        "monitoring": ["Lipid Profile (HDL)", "Blood Pressure", "Weight"],
        "warning_msg": "WPATH SOC 8: 유방 발달 및 성욕 증진에 대한 이득은 임상적으로 입증되지 않았으며(근거 불충분), 장기 복용 시 심혈관계 질환 및 혈전 위험이 있을 수 있습니다.",
        "risk_level": "MEDIUM",
        "metabolism": "CYP3A4_SUBSTRATE",
        "desc": "천연 프로게스테론 제제. 주로 취침 전 복용하며 졸음이나 부종을 유발할 수 있습니다."
    },
    "Leuprorelin (Lupron Depot - 1M)": {
        "type": "GnRH-Agonist",
        "half_life": 336.0,
        "t_peak": 4.0,
        "bioavailability": 1.0,
        "ester_factor": 1.0,
        "default_dose": 3.75,
        "max_safe_dose": 11.25,
        "monitoring": ["LH", "FSH", "Testosterone", "Estradiol", "Bone Density (DXA)"],
        "warning_msg": "투여 초기 1~2주간 호르몬 수치가 일시적으로 상승(Flare effect)할 수 있습니다.",
        "risk_level": "LOW",
        "desc": "1개월 지속형 사춘기 억제제. 성선자극호르몬 방출호르몬 작용제."
    },
    "Triptorelin (Decapeptyl - 1M)": {
        "type": "GnRH-Agonist",
        "half_life": 336.0,
        "t_peak": 3.0,
        "bioavailability": 1.0,
        "ester_factor": 1.0,
        "default_dose": 3.75,
        "max_safe_dose": 11.25,
        "monitoring": ["LH", "FSH", "Testosterone", "Estradiol"],
        "warning_msg": "안정적인 사춘기 지연을 위해 정해진 주기에 맞춘 투여가 중요합니다.",
        "risk_level": "LOW",
        "desc": "1개월 지속형 GnRH 작용제. 사춘기 발달을 효과적으로 억제합니다."
    }
}

# Pydantic 모델을 사용하여 데이터 유효성 검사 및 객체화
DRUG_DB: Dict[str, DrugInfo] = {name: DrugInfo(**data) for name, data in DRUG_DB_RAW.items()}

# -----------------------------------------------------------------------------
# 4. Surgery Specific Guidelines
# -----------------------------------------------------------------------------
SURGERY_TYPES = {
    "성확정 수술 (Vaginoplasty/SRS)": {
        "risk": "HIGH",
        "cessation_weeks": "2-4주",
        "min_hrt_months": 6,
        "desc": "장시간 수술 및 수술 후 부동 자세로 인해 혈전(VTE) 위험이 매우 높습니다. WPATH SOC 8에 따라 최소 6개월 이상의 호르몬 요법이 권장됩니다.",
        "desc_en": "High VTE risk due to long duration and immobility. WPATH SOC 8 recommends at least 6 months of HRT prior."
    },
    "가슴 성형 (Breast Augmentation)": {
        "risk": "MEDIUM",
        "cessation_weeks": "1-2주",
        "min_hrt_months": 12,
        "desc": "전신마취가 동반되나 수술 시간이 상대적으로 짧고 조기 보행이 가능합니다. 일반적으로 수술 1-2주 전 중단을 권장합니다.",
        "desc_en": "General anesthesia is used, but early mobilization is possible. Cessation 1-2 weeks prior is generally recommended."
    },
    "안면 여성화 수술 (FFS)": {
        "risk": "MEDIUM",
        "cessation_weeks": "1-2주",
        "desc": "수술 범위에 따라 다르나, 일반적으로 전신마취 가이드라인을 따릅니다. 부종 관리를 위해 의료진에 따라 지침이 다를 수 있습니다.",
        "desc_en": "Follows general anesthesia guidelines. Instructions may vary by surgeon for edema management."
    },
    "고환 절제술 (Orchiectomy)": {
        "risk": "LOW",
        "cessation_weeks": "0-1주",
        "min_hrt_months": 6,
        "desc": "수술 시간이 짧으나, WPATH SOC 8 가이드라인에 따라 최소 6개월 이상의 호르몬 요법이 권장됩니다.",
        "desc_en": "Short duration, but WPATH SOC 8 recommends at least 6 months of HRT prior."
    },
    "기타 전신마취 수술": {
        "risk": "MEDIUM",
        "cessation_weeks": "2주",
        "desc": "일반적인 전신마취 가이드라인에 따라 수술 2주 전 중단을 권장합니다.",
        "desc_en": "Cessation 2 weeks prior is recommended following general anesthesia guidelines."
    }
}

# -----------------------------------------------------------------------------
# 4. Helper Functions for Main UI
# -----------------------------------------------------------------------------
def get_drug_list_by_type(drug_type_label):
    """
    UI의 Selectbox에서 선택한 제형(Label)에 맞는 약물 이름 리스트를 반환
    Input: "Injection (주사)" -> Output: ["Estradiol Valerate...", ...]
    """
    mapping = {
        "Injection": "Injection",
        "Oral": "Oral",
        "Transdermal": "Transdermal",
        "Sublingual": "Sublingual",
        "Anti-Androgen": "Anti-Androgen",
        "Progesterone": "Progesterone",
        "GnRH-Agonist": "GnRH-Agonist",
        "Injection (주사)": "Injection",
        "Oral (경구)": "Oral",
        "Transdermal (패치/젤)": "Transdermal",
        "Sublingual (설하)": "Sublingual",
        "Anti-Androgen (항안드로겐)": "Anti-Androgen",
        "Progesterone (프로게스테론)": "Progesterone",
        "GnRH-Agonist (사춘기 억제제)": "GnRH-Agonist"
    }
    target_type = mapping.get(drug_type_label)
    
    if not target_type:
        return []
    
    return [name for name, drug in DRUG_DB.items() if drug.type == target_type]

# -----------------------------------------------------------------------------
# 5. Drug Interaction Database
# -----------------------------------------------------------------------------
INTERACTION_DB = {
    # [CYP3A4 Inhibitors] -> 에스트로겐 농도 상승 (부작용 위험)
    "Grapefruit (자몽)": {"type": "CYP3A4_INHIBITOR", "potency": 1.3, "desc": "장관 내 CYP3A4 억제로 혈중 농도 상승 가능"},
    "Ketoconazole (항진균제)": {"type": "CYP3A4_INHIBITOR", "potency": 1.5, "desc": "강력한 CYP3A4 억제제"},
    "Erythromycin (항생제)": {"type": "CYP3A4_INHIBITOR", "potency": 1.2, "desc": "대사 억제로 인한 농도 증가 주의"},
    
    # [CYP3A4 Inducers] -> 에스트로겐 농도 하락 (효과 감소)
    "Rifampin (결핵약)": {"type": "CYP3A4_INDUCER", "potency": 0.5, "desc": "초강력 대사 유도제. 호르몬 효과가 급격히 떨어질 수 있음"},
    "Carbamazepine (항경련제)": {"type": "CYP3A4_INDUCER", "potency": 0.7, "desc": "간 효소 유도로 호르몬 대사 촉진"},
    "St. John's Wort (세인트존스워트)": {"type": "CYP3A4_INDUCER", "potency": 0.8, "desc": "우울증 보조제. 에스트로겐 농도 감소 유발"},

    # [Hyperkalemia Risk] -> 스피로노락톤 병용 시 위험
    "ACE Inhibitors (혈압약)": {"type": "K_SPARING", "desc": "스피로노락톤 병용 시 고칼륨혈증 위험 증가"},
    "NSAIDs (진통제 - 장기복용)": {"type": "RENAL_STRESS", "desc": "신장 기능 저하 시 칼륨 배설 감소 가능성"},
}

def get_interaction_list():
    return list(INTERACTION_DB.keys())
