# 교훈 및 해결 패턴 (Lessons Learned)

### 1. Plotly 시계열 축(Datetime)에서의 add_vline 어노테이션 오류
* **문제**: Plotly의 `add_vline` 호출 시, `x` 인자로 `datetime` 객체를 전달하고 동시에 `annotation_text`를 포함하면 내부적으로 좌표 계산 중 정수(int)와 datetime 간의 덧셈 연산(`+`)이 시도되어 `TypeError: unsupported operand type(s) for +: 'int' and 'datetime.datetime'` 오류가 발생합니다.
* **해결책**: `add_vline` 함수 내부에서 `annotation_text`를 제거하고, 대신 별도의 `add_annotation` 메서드를 사용하여 어노테이션을 독립적으로 렌더링해야 합니다. 이 때 `yref="paper"`를 지정해 Y축 값에 관계없이 항상 상단(예: `y=0.98`)에 위치하도록 제어합니다.
