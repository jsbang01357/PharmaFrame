import numpy as np
import os
import yaml
from glob import glob
from core.models import DrugPK, RoutePK, PatientProfile, DoseEvent
from typing import List, Dict, Tuple, Optional, Any

class PKEngine:
    def __init__(self, patient: PatientProfile):
        self.patient = patient
        self.drug_db: Dict[str, DrugPK] = self._load_drugs()

    def _load_drugs(self) -> Dict[str, DrugPK]:
        db = {}
        # drug 폴더 내의 모든 yaml 파일 로드
        drug_files = glob(os.path.join("drugs", "*.yaml"))
        for file_path in drug_files:
            with open(file_path, "r", encoding="utf-8") as f:
                data_list = yaml.safe_load(f)
                if not data_list:
                    continue
                for item in data_list:
                    # routes 데이터 변환
                    routes = {
                        r_name: RoutePK(**r_data)
                        for r_name, r_data in item["routes"].items()
                    }
                    item["routes"] = routes
                    drug = DrugPK(**item)
                    db[drug.id] = drug
        return db

    def _solve_ka_newton(self, t_peak: float, ke: float) -> float:
        """Newton-Raphson Method를 사용한 ka 역산"""
        if t_peak <= 0:
            return 100.0

        ka = 1.0 / (t_peak / 2.5)
        if ka <= ke: 
            ka = ke * 2.0

        for _ in range(15):
            if ka <= 1e-5: ka = 1e-5
            f_val = t_peak * (ka - ke) - (np.log(ka) - np.log(ke))
            f_prime = t_peak - (1.0 / ka)
            if abs(f_prime) < 1e-7: break
            delta = f_val / f_prime
            ka = ka - delta
            if abs(delta) < 1e-5: break
        
        if ka <= ke:
            ka = ke + 0.01
        return ka

    def _get_ka_ke(self, drug: DrugPK, route: str) -> Tuple[float, float]:
        ke = np.log(2) / drug.half_life_h
        t_peak = drug.routes[route].t_max_h
        ka = self._solve_ka_newton(t_peak, ke)
        return ka, ke

    def _get_modifiers(self, drug: DrugPK) -> float:
        """환자 특성별 농도 보정 (확장 가능)"""
        # 1. 간 대사 보정
        liver_factor = 1.0
        if drug.hepatic_elimination_fraction > 0:
            limit = 40.0
            if self.patient.ast_u_l > limit or self.patient.alt_u_l > limit:
                excess = max(self.patient.ast_u_l, self.patient.alt_u_l) - limit
                liver_factor = 1.0 + (excess / 10.0) * 0.02 * drug.hepatic_elimination_fraction
                liver_factor = min(liver_factor, 1.2)
        
        # 2. Vd 보정 (BMI 기반 예시)
        baseline_bmi = 22.0
        bmi_offset = (self.patient.bmi - baseline_bmi) * 0.01
        vd_factor = 1.0 + bmi_offset
        vd_factor = np.clip(vd_factor, 0.9, 1.3)
        
        return liver_factor / vd_factor

    def bateman_function(self, t: np.ndarray, dose: float, ka: float, ke: float, f: float, ester_factor: float, vd_const: float) -> np.ndarray:
        """Bateman Function: C(t) 계산 (단위: Dose Unit / L)"""
        total_volume = self.patient.weight_kg * vd_const
        
        # 보정치 적용
        # 여기서는 단순화를 위해 모든 약물에 적용 가능하게 설계
        effective_dose = dose * f * ester_factor
        
        if ka == ke:
            ka = ke + 1e-5

        coefficient = (effective_dose * ka) / (total_volume * (ka - ke))
        conc = coefficient * (np.exp(-ke * t) - np.exp(-ka * t))
        return np.maximum(conc, 0)

    def simulate(self, events: List[DoseEvent], days: int = 30, resolution: int = 100) -> Tuple[np.ndarray, np.ndarray]:
        """DoseEvents 리스트를 기반으로 시뮬레이션 수행"""
        total_hours = days * 24
        num_points = int(days * resolution)
        t_hours = np.linspace(0, total_hours, num_points)
        total_conc = np.zeros_like(t_hours)

        if not events:
            return t_hours / 24, total_conc

        for event in events:
            if event.drug_id not in self.drug_db:
                continue
            
            drug = self.drug_db[event.drug_id]
            if event.route not in drug.routes:
                continue
                
            ka, ke = self._get_ka_ke(drug, event.route)
            r_info = drug.routes[event.route]
            
            # 실제 투여 시간 계산 (누락/지연 반영)
            actual_time = event.time_h
            if event.event_type == "missed":
                continue
            elif event.event_type == "delayed":
                actual_time += event.delay_h
            
            shifted_t = t_hours - actual_time
            valid_mask = shifted_t >= 0
            
            if np.any(valid_mask):
                conc = self.bateman_function(
                    shifted_t[valid_mask], event.dose, ka, ke, 
                    r_info.bioavailability, drug.ester_factor, r_info.vd_const
                )
                
                # 환자별 수정자 적용 (예: 간기능 등)
                mod = self._get_modifiers(drug)
                total_conc[valid_mask] += (conc * mod)
                
        return t_hours / 24, total_conc
