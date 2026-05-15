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

    def _get_adjusted_ka_ke_vd(self, drug: DrugPK, route: str) -> Tuple[float, float, float]:
        """환자 임상 수치(eGFR, LFT)에 따른 ke 및 Vd 보정"""
        # 1. Base parameters
        ke_base = np.log(2) / drug.half_life_h
        r_info = drug.routes[route]
        
        # 2. Clearance Adjustment (ke = CL / Vd)
        # 2.1 Renal Adjustment
        renal_cl_factor = 1.0
        if drug.renal_elimination_fraction > 0:
            # eGFR 90 이상을 정상(1.0)으로 간주
            if self.patient.egfr < 90:
                renal_cl_factor = max(0.1, self.patient.egfr / 90.0)
                
        # 2.2 Hepatic Adjustment
        hepatic_cl_factor = 1.0
        if drug.hepatic_elimination_fraction > 0:
            limit = 40.0
            worst_lft = max(self.patient.ast_u_l, self.patient.alt_u_l)
            if worst_lft > limit:
                # LFT 상승에 비례하여 대사율 감소 가정 (매우 보수적인 단순 모델)
                # 40->1.0, 140->0.5 (최대 50% 감소)
                excess = min(worst_lft - limit, 200.0)
                hepatic_cl_factor = 1.0 - (excess / 200.0) * 0.5
                hepatic_cl_factor = max(0.2, hepatic_cl_factor)
                
        # Total Clearance Factor
        other_fraction = max(0.0, 1.0 - drug.renal_elimination_fraction - drug.hepatic_elimination_fraction)
        total_cl_factor = (
            drug.renal_elimination_fraction * renal_cl_factor +
            drug.hepatic_elimination_fraction * hepatic_cl_factor +
            other_fraction
        )
        
        ke_adj = ke_base * total_cl_factor
        
        # 3. Volume of Distribution (Vd) Adjustment
        # BMI와 체지방률 기반 보정 (단순화 모델)
        baseline_bmi = 22.0
        bmi_ratio = self.patient.bmi / baseline_bmi
        
        # 지용성 약물(대체로 Vd가 큰 약물)은 체지방 영향을 더 크게 받음
        vd_adj_factor = 1.0
        if r_info.vd_const > 1.0: # Vd가 큰 경우 (지방 조직 분포율 높음 가정)
            vd_adj_factor = 1.0 + (self.patient.body_fat_pct - 22.0) * 0.01
        else:
            vd_adj_factor = 1.0 + (bmi_ratio - 1.0) * 0.5
            
        vd_adj_factor = np.clip(vd_adj_factor, 0.8, 1.5)
        adjusted_vd_const = r_info.vd_const * vd_adj_factor
        
        # 4. Absorption Constant (ka) - 재계산
        ka_adj = self._solve_ka_newton(r_info.t_max_h, ke_adj)
        
        return ka_adj, ke_adj, adjusted_vd_const

    def bateman_function(self, t: np.ndarray, dose: float, ka: float, ke: float, f: float, ester_factor: float, vd_const: float) -> np.ndarray:
        """Bateman Function: C(t) 계산 (단위: Dose Unit / L)"""
        total_volume = self.patient.weight_kg * vd_const
        
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
                
            ka, ke, vd_const = self._get_adjusted_ka_ke_vd(drug, event.route)
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
                    r_info.bioavailability, drug.ester_factor, vd_const
                )
                
                total_conc[valid_mask] += conc
                
        return t_hours / 24, total_conc
