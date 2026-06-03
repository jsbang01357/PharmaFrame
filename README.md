# 💊 PharmaFrame: Personalized Pharmacokinetics Simulator

PharmaFrame은 환자의 고유한 신체·생리적 지표와 약물의 약동학적(PK) 특성을 결합하여 환자 맞춤형 복약 계획 및 수술 전후 복약 중단/재개 시뮬레이션을 수행하는 학술 및 교육용 **개인화 약동학 시뮬레이터**입니다.

---

## 🌟 주요 특징 (Key Features)

1. **다중 임상 모듈 지원 (Multi-Module Support)**
   - 다양한 질환군 및 임상 환경에 따른 약물 데이터베이스를 탑재하고 있습니다.
   - 지원 모듈: 갑상선 질환(Thyroid), 폐경 후 호르몬 요법(MHRT), 마약성 진통제(Opioids), 항염증제(NSAIDs), 사춘기 유도(Puberty Induction), 심혈관 질환(Cardiovascular) 등.

2. **개인화 약동학 보정 알고리즘 (Personalized PK Calibration)**
   - 환자의 연령, 체중, 신장, 체지방률뿐만 아니라 **신장 기능(eGFR)** 및 **간 기능(AST/ALT)** 수치를 반영하여 약물 청소율($CL$, $k_e$) 및 분포용적($V_d$)을 실시간으로 보정합니다.

3. **복약 순응도 및 조정 시뮬레이션 (Adherence & Deviation Modeling)**
   - 특정 회차의 투여를 지연(Delayed)시키거나 누락(Missed)시켰을 때 혈중 농도 변화를 예측하는 오버라이드 UI를 지원합니다.
   - 복약 누락 시 대처 방안을 안내하는 **50% Rule 임상 가이드라인** 기능이 내장되어 있습니다.

4. **시나리오 비교 (A/B Comparison Mode)**
   - 두 가지 복약 일정(시나리오 A vs 시나리오 B)을 동시에 시뮬레이션하여 최고/최저/평균 농도 및 변동폭(Fluctuation Index) 등의 핵심 지표 변화를 직관적으로 비교할 수 있습니다.

5. **처치 및 수술 계획 시뮬레이터 (Procedure/Surgery Cessation Planner)**
   - 예정된 수술/시술로 인해 약물 투여를 중단해야 하는 경우, 중단 기간 내 일정을 자동으로 누락(Missed) 처리하여 수술 당일 및 전후의 잔류 약물 농도 추이를 그래프로 제공합니다.

6. **병원 EMR 오프라인 연동 (Offline EMR Mode & Database Management)**
   - 오프라인 환경을 인식하여 로컬 EMR 연동 기능을 활성화합니다.
   - 환자 정보(JSON/CSV) 마운트 및 병합(Merge)이 가능하며, 통합된 병원 데이터베이스를 엑셀 호환 CSV 형식으로 일괄 다운로드할 수 있습니다.

7. **리포트 발행 및 캘린더 동기화 (Report & Calendar Integration)**
   - 시뮬레이션 결과와 환자 프로필, 안전성 가이드를 포함하는 PDF 리포트(ReportLab 기반)를 한글 글꼴(NanumGothic)이 적용된 고품질 파일로 자동 생성합니다.
   - 복약 일정을 스마트폰이나 캘린더 앱에 등록할 수 있는 iCalendar(.ics) 내보내기 기능을 지원합니다.

8. **다국어 지원 (Internationalization)**
   - 한국어(KO) 및 영어(EN)의 완전한 인터페이스 현지화를 지원합니다.

---

## 📂 디렉토리 구조 (Directory Structure)

```text
PharmaFrame/
├── app.py                  # Streamlit 메인 애플리케이션 진입점 및 탭 구조 정의
├── requirements.txt        # 패키지 의존성 파일
├── LICENSE                 # MIT 라이선스
├── AGENTS.md               # AI 개발 에이전트 가이드라인 및 규칙
│
├── core/                   # 약동학 핵심 시뮬레이션 및 데이터 모델
│   ├── models.py           # PatientProfile, DrugPK, DoseEvent 등 데이터 클래스 정의
│   ├── pk_engine.py        # Bateman 식 기반 PK 계산 및 신장·간 기능 보정 엔진
│   └── data.py             # 에스트로겐 등 기준 범위 가이드라인 및 레퍼런스 데이터
│
├── ui/                     # Streamlit 웹 UI 렌더링 모듈
│   ├── sidebar.py          # 신체 정보, 임상 모듈 선택, 약물 일정 등록 사이드바
│   ├── simulation_tab.py   # 시뮬레이션 대시보드 및 복약 누락/지연 조정 탭
│   ├── procedure_tab.py    # 수술 전후 약물 중단 일정 시뮬레이션 탭
│   ├── safety_tab.py       # 약물별 위험도 뱃지, 경고 및 필수 모니터링 가이드 탭
│   └── plot_utils.py       # Plotly 라이브러리를 활용한 대화형 그래프 드로잉 유틸
│
├── app_io/                 # 파일 입출력 및 EMR 연동 모듈
│   ├── data_manager.py     # JSON 백업/복원, ics 캘린더 생성, ReportLab 기반 PDF 리포트 발행
│   └── emr_manager.py      # EMR 환자 DB 검색, 불러오기, 일괄 CSV 병합 관리
│
├── utils/                  # 다국어 및 유틸리티 헬퍼
│   ├── utils.py            # 수학/통계(Peak/Trough/RMSE) 연산, 50% Rule 가이드, 다국어 헬퍼
│   └── i18n.json           # 다국어(한국어, 영어) 번역 사전 데이터
│
├── drugs/                  # 임상 모듈별 약물 PK 데이터베이스 (YAML 형식)
│   ├── thyroid.yaml        # 갑상선 호르몬 제제 (Levothyroxine, Liothyronine 등)
│   ├── mhrt.yaml           # 폐경 후 호르몬 요법 치료제 (Estradiol 등)
│   ├── nsaids.yaml         # 비스테로이드성 소염진통제 (Ibuprofen 등)
│   ├── opioids.yaml        # 마약성 진통제 (Fentanyl, Morphine 등)
│   ├── puberty_induction.yaml # 사춘기 유도 호르몬 제제
│   └── cardiovascular.yaml # 심혈관계 약물
│
└── tests/                  # 테스트 스위트
    └── test_pk_engine.py   # PK 엔진의 시뮬레이션 동작 검증 유닛 테스트
```

---

## ⚙️ 설치 및 실행 방법 (Installation & Usage)

### 1. 환경 구축 및 의존성 패키지 설치
이 프로젝트는 Python 3.9 이상에서 가장 잘 작동합니다. 가상환경 활성화 후 필요한 패키지들을 설치하세요.

```bash
# 가상환경 생성 및 활성화
python3 -m venv .venv
source .venv/bin/activate  # macOS/Linux 기준

# 의존성 패키지 설치
pip install -r requirements.txt
```

### 2. 애플리케이션 실행
```bash
streamlit run app.py
```
실행 후 기본 브라우저를 통해 `http://localhost:8501` 주소로 시뮬레이터 대시보드에 접속할 수 있습니다.

### 3. 테스트 실행
PK 계산 엔진의 기본 동작을 검증하기 위한 간단한 유닛 테스트가 포함되어 있습니다.
```bash
python -m pytest tests/  # pytest 설치 시
# 또는 일반 파이썬 실행
python tests/test_pk_engine.py
```

---

## 🧮 약동학(PK) 모델링 메커니즘 (Modeling Methodology)

### 1. Bateman Equation 기반 흡수-소실 모델
경구(PO), 설하(Sublingual) 등의 약물 흡수 및 소실 과정을 모사하기 위해 다음의 **Bateman Equation** 1구획 모델을 활용합니다.

$$C(t) = \frac{D \cdot F \cdot \text{EsterFactor} \cdot k_a}{V_d \cdot (k_a - k_e)} \left( e^{-k_e \cdot t} - e^{-k_a \cdot t} \right)$$

* $D$: 투여 용량 (Dose)
* $F$: 생체이용률 (Bioavailability)
* $\text{EsterFactor}$: 활성 약물 분자 질량비 (에스터 형태 보정)
* $k_a$: 흡수 속도 상수 (Absorption rate constant)
* $k_e$: 배설 속도 상수 (Elimination rate constant, $k_e = \frac{\ln(2)}{t_{1/2}}$)
* $V_d$: 분포용적 (Volume of distribution, 체중 보정 적용)

### 2. 수치해석을 통한 $k_a$ 역산 (Newton-Raphson Method)
약물 데이터베이스(YAML)에는 일반적으로 최고 농도 도달 시간인 $t_{\text{max}}$($t_{\text{peak}}$) 정보만 존재합니다. 엔진은 이를 모델 매개변수인 $k_a$로 변환하기 위해 아래의 $t_{\text{max}}$ 공식 관계식에 **Newton-Raphson 법**을 적용해 수치적으로 $k_a$를 역산합니다.

$$t_{\text{max}} = \frac{\ln(k_a) - \ln(k_e)}{k_a - k_e}$$

### 3. 환자 임상 지표 연동 청소율($CL$) 및 분포용적($V_d$) 보정
* **신장 기능 보정**: 약물의 신장 배설 분율(`renal_elimination_fraction`)에 따라 환자의 eGFR 수치를 정상(90 이상) 기준비율로 적용하여 $k_e$를 보정합니다.
* **간 기능 보정**: 약물의 간 대사 분율(`hepatic_elimination_fraction`)에 따라 환자의 AST/ALT 수치가 정상 범위(40 이하)를 초과할 경우 대사율을 최대 50%까지 감소시킵니다.
* **분포용적 보정**: 환자의 BMI 및 체지방률(`body_fat_pct`)을 정상 분포(기준 22.0)와 비교하여 지용성 약물의 지방 조직 분포량 또는 수용성 분포 보정을 수행합니다.

---

## 🛡️ 면책 조항 (Disclaimer)

1. PharmaFrame에서 산출되는 약물 농도 추이는 임상 문헌 데이터 및 일반적인 약동학 모델링 기법을 적용한 시뮬레이션 결과로, 환자 개인의 유전적 요인, 대사 속도 차이, 병용 약물 상호작용 등에 따라 실제 혈중 농도와 큰 차이가 발생할 수 있습니다.
2. 본 시뮬레이터는 **의료기기가 아니며, 임상적 진단이나 약물 처방 조정을 대체할 수 없습니다**. 실제 약물 복용 일정이나 용량을 변경할 때는 반드시 전문의 또는 약사와 상담하십시오.
