# TS-01 두산 API 초기화 누락 · 서비스 콜백 안 로봇 명령 교착

| 항목 | 내용 |
|---|---|
| 날짜 | 2026-09-18 |
| 발견 | 박진용 (V-21 사전 검증 중, 소스 정적 분석 + 최소 재현) — [원본 보고](TS-01_원본보고_박진용.md) |
| 확인 | 황인재(PM): 실제 `DSR_ROBOT2` + 가짜 드라이버로 재현, 수정안 2종 비교 |
| 영향 | `f1_node` `f2_node` `f3_node` 전부. **문서대로 다 만들어도 통합 실행에서 로봇이 움직이지 않는다** |
| 관련 검증 | SDD §9.2 V-20 · V-21 |
| 상태 | 원인·해법 확정(가짜 드라이버 기준). **Virtual에서 실제 드라이버로 재확인 필요 → V-20(9/19 오전)** |
| 반영 | SDD §3.1(`init` `spin` `force_reached`) · §3.2(노드 뼈대 규약) · §5.1(flow 실행 구조) · AGENTS.md §4·§5 · 환경설정 §12 |

## 1. 증상
| # | 상황 | 증상 |
|---|---|---|
| A | 기능 노드 기동 | `AttributeError: 'NoneType' object has no attribute 'create_client'` — 노드가 뜨자마자 죽는다 |
| B | 서비스 콜백 안에서 첫 로봇 명령 | `RuntimeError: Executor is already spinning` 또는 **무한 대기**(타임아웃 없음). flow는 응답을 영영 못 받는다 |
| B′ | 1차 수정안(MultiThreadedExecutor + 기본 콜백 그룹 교체) 적용 후 | **첫 호출은 성공, 두 번째 호출부터 응답 없음.** 단독 시험에서 한 번만 불러 보면 통과해 버린다 |
| D | 힘 조건 판정 | `if check_force_condition(...):` 로 쓰면 판정이 **반대로** 동작 |

## 2. 원인 — 두산 API는 "혼자 도는 스크립트"를 전제로 만들어졌다
ROS 노드에는 **실행기**(executor)가 붙어 있다. 실행기는 노드로 들어오는 서비스 요청·서비스 응답·타이머를 받아 해당 함수를 실행해 주는 담당자이고, 기본적으로 **한 번에 하나만** 처리한다.

**A.** `DSR_ROBOT2.py`는 **import되는 순간** `g_node = DR_init.__dsr__node`를 한 번 읽어 고정하고 곧바로 `g_node.create_client(...)`를 수백 번 부른다(`DSR_ROBOT2.py:38~`). 노드를 넣기 전에 import하면 `g_node`가 `None`이라 그 자리에서 죽는다. 두산 예제는 `main()` 안에서 노드를 만든 뒤 import하므로 문제가 없다. 우리는 공용 모듈 맨 위에서 import하게 되므로 걸린다.

**B.** `DSR_ROBOT2`의 모든 로봇 명령은 안에서 이렇게 한다(241곳, 타임아웃 지정은 24곳뿐).
```python
future = _ros2_movej.call_async(req)
rclpy.spin_until_future_complete(g_node, future)   # 응답이 올 때까지 "직접" 실행기를 돌린다
```
스크립트에서는 실행기를 돌리는 사람이 없으니 괜찮다. 우리 구조에서는 flow가 `/f1/pick`을 부르면 **실행기가 pick 콜백을 실행하는 중**에 `movej`가 같은 실행기를 또 돌리려 한다 → 이미 도는 중이라 오류, 또는 응답을 열어 줄 사람이 없어 무한 대기.
> 창구 직원이 한 명인 은행에서, 직원이 손님 일을 처리하다 본점 회신을 기다리는데 그 회신도 같은 창구로 온다.

**B′.** `rclpy.spin_until_future_complete(node, …)`는 노드를 **전역 실행기에 넣었다가 끝나면 뺀다.** 그런데 rclpy는 노드를 새 실행기에 넣을 때 **원래 실행기에서 빼 버린다**(`rclpy/node.py`의 `executor` setter: `current_executor.remove_node(self)`). 그래서 기능 노드 자신을 `DR_init.__dsr__node`로 주면, 첫 `movej`가 끝난 뒤 그 노드는 **어느 실행기에도 속하지 않게 되고** 다음 서비스 요청을 아무도 받지 않는다.

**D.** DRL 매뉴얼은 `check_force_condition`이 `True/False`를 돌려준다고 하지만, 실제 `DSR_ROBOT2.py:5478`은 **조건 만족 `0` / 아니면 `-1`**을 돌려준다(`check_position_condition`도 같다). 파이썬에서 `0`은 거짓이다.

## 3. 재현 (로봇 없이, 실제 `DSR_ROBOT2` + 가짜 드라이버)
스크립트: [ts01_repro/](ts01_repro/) — `fake_ctrl.py`(2초 걸리는 가짜 `move_joint` 서비스), `feat.py`(구성별 기능 노드), `flowlike.py`(flow 흉내).

| 구성 | 결과 |
|---|---|
| `A_noinit` 초기화 없이 import | 기동 즉시 `AttributeError` |
| `B_plain` 초기화 + `rclpy.spin(node)` | 첫 호출에서 `Executor is already spinning`, 응답 없음 |
| `C_fix` 1차 수정안(자기 노드 + MultiThreadedExecutor + 기본 그룹 교체) | 1회 성공 → **2회째 응답 없음**(2번 실행, 2번 동일) |
| **`D_sepnode` DSR 전용 노드 분리 + 기능 노드는 자체 실행기** | **연속 5회 성공**. 타이머를 별도 콜백 그룹에 두면 모션 중에도 2.000 Hz |
| `flowlike` 작업 스레드에서 동기 호출 + 상태 타이머 | 연속 호출 성공, 모션 중 상태 2.000 Hz, **모션 중 stop 요청 즉시 수락 → 현재 호출 끝난 뒤 보류** |

```bash
cd docs/troubleshooting/ts01_repro
bash run.sh    # 결함 A·B 재현
bash run2.sh   # 수정안 C vs D (연속 호출·겹친 호출)
bash run3.sh   # C 재확인 + D에서 상태 2 Hz
bash run4.sh   # flow 구조
```

## 4. 해결
**① `cobot_common.init(node)`** — 기능 노드 `__init__` **맨 앞**에서 한 번. 안에서 **DSR 전용 노드**(`<노드이름>_dsr`, 네임스페이스 `dsr01`)를 만들어 `DR_init.__dsr__node`에 넣고, **그 다음에** `DSR_ROBOT2`를 import한다. 전용 노드는 어떤 실행기에도 넣지 않는다(두산 API가 필요할 때만 전역 실행기에 넣었다 뺀다).

**② `cobot_common.spin(node)`** — `main()`에서 `rclpy.spin(node)` 대신. 기능 노드를 **자체 `MultiThreadedExecutor`**로 돌린다. `rclpy.spin()`은 전역 실행기를 쓰므로 두산 API와 부딪힌다 → **`rclpy.spin()` 금지**.

**③ 동시 실행 방지** — 기능 노드의 서비스는 기본 콜백 그룹(한 번에 하나)에 그대로 둔다. 로봇은 하나이므로 한 노드 안에서 동작이 겹치면 안 된다. 타이머·상태 발행이 필요하면 **별도 콜백 그룹**에 둔다.

**④ `cobot_common.force_reached(...)`** — `check_force_condition(...) == 0`을 감싼 bool 함수. 기능 노드는 두산 함수를 직접 부르지 않으므로(규칙 5) 이 함정을 몰라도 된다.

**⑤ flow_node** — 두산 API를 쓰지 않는다. `/flow/start`는 **즉시 응답**하고 순서 실행은 **작업 스레드**에서 `client.call()`(동기)로 한다. 노드는 `MultiThreadedExecutor`, 상태 타이머·start/stop/resume 서비스는 `ReentrantCallbackGroup`.

노드 뼈대(정본은 SDD §3.2):
```python
class F3Node(Node):
    def __init__(self):
        super().__init__('f3_node')
        cobot_common.init(self)                 # ← 맨 앞. 이 뒤에 create_service
        self.create_service(F3WipeBowl, '/f3/wipe_bowl', self.on_wipe_bowl)

def main(args=None):
    rclpy.init(args=args)
    node = F3Node()
    try:
        cobot_common.spin(node)                 # ← rclpy.spin(node) 금지
    finally:
        node.destroy_node(); rclpy.shutdown()
```

## 5. 재발 방지
- **서비스는 한 번이 아니라 연속 3회 이상 불러서 시험한다.** 이번 B′처럼 "첫 번째만 되는" 결함은 한 번 호출로는 보이지 않는다(SDD §9.3 공통 규칙).
- 노드가 멈췄을 때 Ctrl+C로 죽이면 `dsr_controller2`가 그 요청 안에 갇힐 수 있다 → 브링업까지 다시 띄운다.
- 두산 함수의 반환값은 DRL 매뉴얼이 아니라 **설치된 `DSR_ROBOT2.py`**에서 확인한다.

## 6. 확인한 범위와 남은 확인
- 확인함: 노드 기동, 서비스 호출 체인의 응답, 연속 호출, 모션 중 상태 발행·정지 요청(가짜 드라이버, 이 PC).
- **남음**: ① Virtual의 실제 `dsr_controller2`로 세 노드가 번갈아 `movej`(노드당 연속 3회) → **V-20** ② flow 구조를 mock으로 → **V-21** ③ 전용 노드가 노드마다 1개씩(총 3개) 같은 드라이버에 붙어도 되는가 → V-20에서 함께. 안 되면 SDD §9.2의 대안(로봇 명령을 한 노드로 모음).
