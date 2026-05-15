import numpy as np
from core import data  # core/data.py에서 약물 DB 로드
from typing import List, Dict, Tuple, Optional, Any

class HormoneAnalyzer:
    def __init__(self, user_weight=60.0, user_age=25, ast=20.0, alt=20.0, body_fat=22.0, user_height=170.0):
        self.weight = max(float(user_weight), 30.0) # 최소 30kg 보장
        self.height = max(float(user_height), 100.0) # 최소 100cm 보장
        self.age = int(user_age)
        self.ast = float(ast)
        self.alt = float(alt)
        self.body_fat = float(body_fat)
        self.bmi = self.weight / ((self.height / 100) ** 2)
        
        # 투여 경로별 Vd 상수 (data.py에서 로드)
        self.ROUTE_CONSTANTS = data.ROUTE_CONSTANTS

    def _solve_ka_newton(self, t_peak, ke):
        """
        Newton-Raphson Method를 사용한 ka 정밀 역산
        목표식: Tmax = (ln(ka) - ln(ke)) / (ka - ke)
        변형식 F(ka): Tmax * (ka - ke) - (ln(ka) - ln(ke)) = 0
        도함수 F'(ka): Tmax - (1 / ka)
        """
        if t_peak <= 0:
            return 100.0 # Instant absorption (IV Bolus-like)

        # 1. 초기 추정값 (Initial Guess)
        # 기존 Heuristic을 사용하여 근사한 값에서 시작 (수렴 속도 향상)
        ka = 1.0 / (t_peak / 2.5)
        
        # ka가 ke보다 작거나 같으면 수식이 깨지므로 강제 보정
        if ka <= ke: 
            ka = ke * 2.0

        # 2. 뉴턴-랩슨 반복 (일반적으로 5~10회 내외로 수렴)
        for _ in range(15):
            # ka가 0 이하로 떨어지는 것 방지
            if ka <= 1e-5: 
                ka = 1e-5
            
            # F(ka) 계산
            f_val = t_peak * (ka - ke) - (np.log(ka) - np.log(ke))
            
            # F'(ka) 계산
            f_prime = t_peak - (1.0 / ka)
            
            # 기울기가 0에 가까우면 발산 위험 -> 루프 중단
            if abs(f_prime) < 1e-7:
                break
                
            # Delta 계산
            delta = f_val / f_prime
            ka = ka - delta
            
            # 수렴 판정 (오차가 매우 작으면 종료)
            if abs(delta) < 1e-5:
                break
        
        # 최종 안전장치: Flip-flop kinetics 방지
        # ka가 ke보다 작아지면 그래프 개형이 이상해지므로 보정
        if ka <= ke:
            ka = ke + 0.01

        return ka

    def _get_ka_ke(self, drug_info):
        """
        약물 정보(반감기, Tmax)를 이용해 흡수상수(ka)와 제거상수(ke)를 계산
        """
        half_life_hours = drug_info.half_life
        t_peak_hours = drug_info.t_peak

        # 1. 제거 상수 (ke) = ln(2) / t_1/2
        ke = np.log(2) / half_life_hours

        # 2. 흡수 상수 (ka) - 수치해석 적용
        ka = self._solve_ka_newton(t_peak_hours, ke)

        return ka, ke

    def _get_liver_metabolism_factor(self):
        """
        간 수치(AST/ALT)에 따른 대사 효율 보정.
        """
        limit = 40.0
        if self.ast > limit or self.alt > limit:
            excess = max(self.ast, self.alt) - limit
            # 10단위 초과당 2% 농도 상승 가정 (최대 20% 보정)
            factor = 1.0 + (excess / 10.0) * 0.02
            return min(factor, 1.2)
        return 1.0

    def _get_body_fat_adjustment(self):
        """체지방률에 따른 Vd 보정 (지용성 약물)"""
        baseline_fat = 22.0
        fat_offset = (self.body_fat - baseline_fat) * 0.008
        adjustment = 1.0 + fat_offset
        return np.clip(adjustment, 0.8, 1.5)

    def _get_bmi_adjustment(self):
        """BMI에 따른 Vd 보정"""
        baseline_bmi = 22.0
        bmi_offset = (self.bmi - baseline_bmi) * 0.01
        adjustment = 1.0 + bmi_offset
        return np.clip(adjustment, 0.9, 1.3)

    def _get_first_pass_adjustment(self, route_type):
        """나이에 따른 간 대사(First-pass) 효율 변화 보정"""
        oral_routes = ["Oral", "Anti-Androgen"]
        
        if route_type in oral_routes:
            age_offset = (self.age - 25) * 0.002
            adjustment = 1.0 + age_offset
            return np.clip(adjustment, 0.85, 1.15)
        return 1.0

    def bateman_function(self, t, dose, ka, ke, f, ester_factor, route_type):
        """
        Bateman Function: C(t) 계산
        """
        vd_const = self.ROUTE_CONSTANTS.get(route_type, 4.0)
        
        fat_mod = self._get_body_fat_adjustment()
        bmi_mod = self._get_bmi_adjustment()
        
        current_total_volume = self.weight * vd_const * fat_mod * bmi_mod

        first_pass_mod = self._get_first_pass_adjustment(route_type)
        liver_func_mod = self._get_liver_metabolism_factor()
        
        adjusted_f = f * first_pass_mod * liver_func_mod
        effective_dose_ng = dose * adjusted_f * ester_factor * 1_000_000
        
        if ka == ke:
            ka = ke + 1e-5

        coefficient = (effective_dose_ng * ka) / (current_total_volume * (ka - ke))
        
        conc = coefficient * (np.exp(-ke * t) - np.exp(-ka * t))
        conc = np.maximum(conc, 0)
        
        return conc

    def simulate_schedule(
        self, 
        schedule_list: List[Dict[str, Any]], 
        days: int = 30, 
        resolution: int = 100, 
        calibration_factors: Optional[Dict[str, float]] = None, 
        stop_day: Optional[int] = None, 
        resume_day: Optional[int] = None
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        전체 스케줄 시뮬레이션 (중첩 원리)
        :param resume_day: 투약 재개일 (중단 후 다시 시작하는 날짜)
        """
        if calibration_factors is None:
            calibration_factors = {}

        total_hours = days * 24
        num_points = int(days * resolution)
        
        t_hours = np.linspace(0, total_hours, num_points)
        total_conc = np.zeros_like(t_hours)

        if not schedule_list:
            return t_hours / 24, total_conc

        for item in schedule_list:
            drug_name = item['name']
            dose = item['dose']
            interval_days = float(item['interval'])
            
            # [Safety Check] interval이 0이거나 너무 작으면 연산량 폭증으로 앱이 멈출 수 있음
            if interval_days < 0.01:
                continue
            
            is_cycling = item.get('is_cycling', False)
            offset_days = item.get('offset', 0.0)
            duration_days = item.get('duration', 1.0)
            
            if drug_name not in data.DRUG_DB:
                continue
                
            drug_info = data.DRUG_DB[drug_name]
            route_type = drug_info.type
            
            cf = calibration_factors.get(route_type, 1.0)

            # [핵심] 여기서 Newton Method가 적용된 값을 받아옵니다.
            ka, ke = self._get_ka_ke(drug_info)
            f = drug_info.bioavailability
            ef = drug_info.ester_factor

            cycle_starts = np.arange(0, total_hours, interval_days * 24)
            all_dose_times = []
            
            for start_time in cycle_starts:
                if is_cycling:
                    for d in range(int(duration_days)):
                        dose_time = start_time + (offset_days * 24) + (d * 24)
                        if dose_time < total_hours:
                            all_dose_times.append(dose_time)
                else:
                    all_dose_times.append(start_time)

            if stop_day is not None:
                if resume_day is not None:
                    all_dose_times = [dt for dt in all_dose_times if dt <= stop_day * 24 or dt >= resume_day * 24]
                else:
                    all_dose_times = [dt for dt in all_dose_times if dt <= stop_day * 24]

            for dose_t in all_dose_times:
                shifted_t = t_hours - dose_t
                valid_mask = shifted_t >= 0
                
                if np.any(valid_mask):
                    conc = self.bateman_function(
                        shifted_t[valid_mask], dose, ka, ke, f, ef,
                        route_type=route_type
                    )
                    total_conc[valid_mask] += (conc * cf)
        
        return t_hours / 24, total_conc

    def calculate_calibration_factor(self, schedule_list, lab_day, lab_value, target_route="Injection", current_factors=None):
        if lab_value <= 0:
            return 1.0
        if current_factors is None:
            current_factors = {}
        
        calc_factors = current_factors.copy()
        calc_factors[target_route] = 1.0

        other_schedule = [d for d in schedule_list if d['name'] in data.DRUG_DB and data.DRUG_DB[d['name']].type != target_route]
        t_sim, c_other = self.simulate_schedule(other_schedule, days=lab_day + 1, resolution=24, calibration_factors=calc_factors)
        
        target_schedule = [d for d in schedule_list if d['name'] in data.DRUG_DB and data.DRUG_DB[d['name']].type == target_route]
        _, c_target = self.simulate_schedule(target_schedule, days=lab_day + 1, resolution=24, calibration_factors={target_route: 1.0})
        
        # [핵심] 잔류 농도(Trough) 탐색 로직 추가
        # lab_day 근처(0.5일 전 ~ 0.1일 후)에서 전체 농도가 가장 낮은 지점을 찾습니다.
        window_mask = (t_sim >= max(0, lab_day - 0.5)) & (t_sim <= lab_day + 0.1)
        
        if np.any(window_mask):
            c_total = c_other + c_target
            # 윈도우 내에서 가장 낮은 농도 시점의 인덱스 추출
            trough_rel_idx = np.argmin(c_total[window_mask])
            actual_idx = np.where(window_mask)[0][trough_rel_idx]
            conc_other = c_other[actual_idx]
            conc_target = c_target[actual_idx]
        else:
            idx = (np.abs(t_sim - lab_day)).argmin()
            conc_other = c_other[idx]
            conc_target = c_target[idx]
        
        if conc_target < 0.1:
            return 1.0
            
        new_factor = (lab_value - conc_other) / conc_target
        return np.clip(new_factor, 0.1, 5.0)

    def calculate_weighted_calibration_factor(self, schedule_list, lab_history, target_route="Injection", current_factors=None):
        if not lab_history:
            return 1.0

        factors = []
        weights = []

        for record in lab_history:
            k = self.calculate_calibration_factor(schedule_list, record['day'], record['value'], target_route, current_factors)
            factors.append(k)
            weights.append(np.exp(record['day'] / 14.0))

        if not factors:
            return 1.0

        return np.average(factors, weights=weights)

# 단위 변환 유틸리티
def convert_pg_to_pmol(pg_ml):
    return pg_ml * 3.671

def convert_pmol_to_pg(pmol_l):
    return pmol_l / 3.671