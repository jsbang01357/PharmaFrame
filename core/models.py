from dataclasses import dataclass, field
from typing import List, Dict, Optional, Literal
from datetime import date

@dataclass
class RoutePK:
    bioavailability: float  # 0.0 to 1.0
    t_max_h: float
    vd_const: float  # Volume of distribution constant (L/kg)

@dataclass
class DrugPK:
    id: str
    name: str
    category: str
    half_life_h: float
    routes: Dict[str, RoutePK]
    ester_factor: float = 1.0
    molecular_weight: Optional[float] = None
    protein_binding: float = 0.0
    renal_elimination_fraction: float = 0.0
    hepatic_elimination_fraction: float = 1.0
    monitoring: List[str] = field(default_factory=list)
    warning_msg: str = ""
    warning_msg_en: str = ""
    desc: str = ""
    desc_en: str = ""
    risk_level: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"] = "LOW"

@dataclass
class PatientProfile:
    name: str = "Anonymous"
    birth_date: Optional[date] = None
    age: int = 25
    sex: Literal["M", "F", "Other"] = "Other"
    weight_kg: float = 60.0
    height_cm: float = 170.0
    body_fat_pct: float = 22.0
    
    # Renal
    creatinine_mg_dl: float = 1.0
    egfr: float = 100.0
    
    # Hepatic
    ast_u_l: float = 20.0
    alt_u_l: float = 20.0
    bilirubin_mg_dl: float = 1.0
    albumin_g_dl: float = 4.0
    
    @property
    def bmi(self) -> float:
        return self.weight_kg / ((self.height_cm / 100) ** 2)

@dataclass
class DoseEvent:
    drug_id: str
    dose: float
    time_h: float
    route: str
    event_type: Literal["scheduled", "missed", "delayed"] = "scheduled"
    delay_h: float = 0.0
