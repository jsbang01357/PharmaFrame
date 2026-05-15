import numpy as np
from core.models import PatientProfile, DoseEvent
from core.pk_engine import PKEngine

def test_basic_simulation():
    # 1. 환자 프로필 생성
    patient = PatientProfile(
        name="Test User",
        age=50,
        weight_kg=70.0,
        height_cm=165.0
    )
    
    # 2. 엔진 초기화 (YAML 로드 포함)
    engine = PKEngine(patient)
    
    # 3. 투약 이벤트 생성 (Levothyroxine 100mcg 매일)
    events = []
    for d in range(10):
        events.append(DoseEvent(
            drug_id="levothyroxine",
            dose=100.0,
            time_h=d * 24.0,
            route="PO"
        ))
        
    # 4. 시뮬레이션 실행
    t, c = engine.simulate(events, days=15)
    
    print(f"Simulation completed. Max concentration: {np.max(c):.2f}")
    assert np.max(c) > 0
    print("Test passed!")

if __name__ == "__main__":
    test_basic_simulation()
