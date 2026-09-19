# 인터페이스 요구사항 문서 (IRD)
## PreWash-Cell — 기능 함수·메시지 약속 정본

| 항목 | 내용 |
|---|---|
| 문서 ID | IRD-PREWASH-001 · **v3.0** (2026-09-18) |
| 구조 | **스크립트형(9/18 저녁 결정)**: `flow_node`(메인 프로그램)가 f1·f2·f3의 **파이썬 함수**를 차례로 부른다. 기능 사이에 ROS 서비스는 없다. ROS 통신은 flow ↔ HMI와 그리퍼·두산 드라이버뿐이다. 배경은 [TS-01](troubleshooting/TS-01_두산API_초기화_실행기_교착.md), 결정은 [회의록 DSN-02b](meetings/20260918_결정기록_구조_인터페이스.md) |
| 확정 상태 | ✅ 확정: PC 2대 · **노드 2개(`flow_node`·`hmi_bridge`)** · F1↔F3 경계(툴 픽업 F1 / 세제 담금 F3) · 닦기 분리(`wipe_bowl`/`wipe_cup`) · `place`가 안착 놓기 · 복귀는 `move_to('HOME')` · 파지 힘 2단계 · 설정 파일 2개. **🟡 미확정**: §2 반납 구역·`EMPTY_ZONE`, §3 `pick` 탐색·재파지(V-15 뒤), §6~7 HMI·`FlowState`/`FlowEvent` 필드·추가 토픽(F4-00 뒤), §8 실패 정책, §9 YAML 키 규칙 → **DSN-03** |
| 상위 | [01_요구사항_BR-SR.md](01_요구사항_BR-SR.md) §5.4 |
| 정본 파일 | **함수 약속** [`src/cobot_api/cobot_api/contracts.py`](../src/cobot_api/cobot_api/contracts.py) · **메시지** [interfaces/](interfaces/) 의 `*.msg`(→ `src/cobot_msgs`). 이 문서와 파일이 다르면 **파일이 정본** |
| 변경 규칙 | 함수 이름·인자·반환 필드·코드, 메시지 필드의 추가·삭제·타입 변경은 `.github/ISSUE_TEMPLATE/interface_change.md` 이슈 → 4명 확인 → PR. 혼자 바꾸지 않는다. |

🚨 **이 문서가 4명 동시 개발의 약속이다.** 이 약속이 있어서 남의 코드가 없어도 내 함수를 만들고 시험할 수 있다. v2.1의 서비스 12개가 **같은 이름·같은 인자·같은 반환 필드의 함수 12개**로 바뀌었을 뿐 내용은 같다.

---

## 1. 원칙
1. 기능 패키지(f1·f2·f3)는 **함수 제공자**다. 부르는 쪽은 `flow_node` 하나뿐이다. 기능 패키지끼리는 서로의 함수를 부르지 않는다(import 금지).
2. 모든 기능 함수는 `cobot_api`의 **`Result`(또는 하위 타입)** 를 돌려준다: `ok(bool)` + `code(str)` + 기능별 필드. **실패는 예외가 아니라 `ok=False` + `code`.** 예외가 새어 나오면 flow가 `ROBOT_ERROR`로 바꾸고 안전 자세로 간다(SDD §5.1).
3. 물리 인계는 **정해진 스테이션 위치**로만 한다. F1이 놓은 자리에서 F3가 시작한다. 그래서 각자 용기를 손으로 놓아 두고 자기 함수를 단독으로 시험할 수 있다.
4. 로봇 API는 `cobot_common`(두산 API를 감싼 공용 로봇 함수 모음)만 쓴다. 기능 패키지가 `DSR_ROBOT2`를 직접 import하지 않는다.
5. 🚨 **두산 함수(=`cobot_common`의 로봇 함수)는 메인 스레드에서만 부른다.** 콜백·타이머·다른 스레드에서 부르지 않는다. 기능 함수 안에서 노드를 만들거나 `rclpy.spin*`을 부르지 않는다(SDD §3.2).
6. 모든 ID는 아래 §2 문자열을 그대로 쓴다(대문자, 코드·YAML·기록·메시지·HMI 동일). 코드에서는 `cobot_api`의 상수를 쓴다(`from cobot_api import BOWL, EMPTY_ZONE`).

## 2. 공통 ID (IR-05)
| 분류 | 값 | 설명 |
|---|---|---|
| 용기 종류 `kind` | `BOWL` `CUP` | |
| 툴 `tool` | `SPONGE`(그릇용 수세미 툴) `BRUSH`(컵용 수세미 솔) | |
| 반납 구역 `zone_id` | `RET_B` `RET_C` | 공정 입구. 구역 안 위치·겹침 자유 → 탐색 파지 |
| 팔레트 칸 `rack_slot` | `RACK_B1` `RACK_B2` / `RACK_C1` `RACK_C2` `RACK_C3` `RACK_C4` | 공정 출구. 그릇 2칸·컵 4칸 |
| 스테이션 `station` | `HOME` `WEIGH` `WASTE` `SPONGE_BED_B` `SPONGE_BED_C` `TOOL_SPONGE` `TOOL_BRUSH` `SOAP` `RINSE` `ISOLATE` | 작업대 위 고정 위치 |
| 실패 코드 `code` | `OK` `GRIP_FAIL` `EMPTY_ZONE` `LEFTOVER` `LEFTOVER_REMAIN` `SEAT_FAIL` `TOOL_FAIL` `FORCE_LIMIT` `TIMEOUT` `RACK_JAM` `RACK_FULL` `ROBOT_ERROR` `STOPPED` | |
| 흐름 상태 `step` | `IDLE` `PICK` `WEIGH` `SHAKE` `SEAT` `SOAP` `WIPE` `RINSE` `RACK` `ISOLATE` `DONE` `ERROR` `PAUSED` | `PICK` 안에 탐색 포함 |

## 3. F1 파지·이송·적재 (IR-01) · 한석형 · 모듈 `f1_handling.handling`
| 함수 | 인자 | 반환 | 비고 |
|---|---|---|---|
| `pick(zone_id, kind)` | `RET_B`/`RET_C`/`SPONGE_BED_*`, `BOWL`/`CUP` | `PickResult`: `ok, code, width_mm, attempts, offset_x_mm, offset_y_mm` | **탐색 파지**: 구역 탐색점 순회 → 힘 감시 하강 → 파지 → 폭 판정. 폭 범위 밖이면 놓고 다음 점. 최대 횟수 초과 → `EMPTY_ZONE`. `SPONGE_BED_*`면 고정 위치 재파지(탐색점 1개) |
| `place(station)` | 스테이션 | `PlaceResult`: `ok, code, offset_mm` | 상공 → 하강 → 놓기 → 후퇴. **항상 놓기(release)까지 한다.** **`SPONGE_BED_B/C`면 안착 놓기**: 쥔 채 순응 하강 → 깊이+힘으로 홈에 들어갔는지 판정 → 안 들어가면 Move Periodic 탐색 → 들어가면 놓기 / 한도 초과 → 들고 후퇴 + `SEAT_FAIL` |
| `move_to(station, carrying)` | 스테이션, `bool` | `Result` | 안전 높이 경유, 들고 있으면 저속. 안전 자세 복귀 = `move_to('HOME', False)` |
| `tool(tool, action)` | `SPONGE`/`BRUSH`, `PICK`/`RETURN` | `ToolResult`: `ok, code, width_mm` | 홀더에서 툴 픽업·반납. 폭 범위 밖 → `TOOL_FAIL` |
| `rack_place(rack_slot, kind)` | 칸, 종류 | `Result` | 지정 각도 삽입, 순응 + 삽입력 감시, 걸림 → `RACK_JAM` |

`GRIP_FAIL`은 `pick` 내부 재탐색으로 소화된다. flow가 받는 코드는 `OK` 또는 `EMPTY_ZONE`(또는 `ROBOT_ERROR`)이다.

## 4. F2 무게·털기·헹굼 (IR-02) · 민범진 · 모듈 `f2_sense_flow.sense`
| 함수 | 인자 | 반환 | 비고 |
|---|---|---|---|
| `weigh(kind)` | 종류 | `WeighResult`: `ok, code, weight_g` | WEIGH 자세 정지 후 N회 평균. 0점 재설정(`reset`)은 **선택 동작**(응답 상한 3 s, 실패해도 계속 — [TS-03](troubleshooting/TS-03_하중_reset_제어권_교착.md)). 판정은 `측정값 − 빈 용기 기준값`이라 고정 옵셋은 상쇄된다 |
| `leftover_loop(kind, max_rounds)` | 종류, 최대 반복 | `LeftoverResult`: `ok, code, weight_before_g, weight_after_g, rounds` | 판정→털기→재측정 반복. 초과 지속 → `LEFTOVER_REMAIN`. 임계 미만은 `OK` |
| `shake(mode, count, kind)` | `WASTE`/`RINSE`, 횟수, 종류 | `Result` | 진폭·속도는 `params.yaml`의 `f2` 절. **시작 시 강한 파지(HOLD) → 끝나면 보통 파지(NORMAL)**. 털다가 폭이 변하면(미끄러짐) `GRIP_FAIL` |
| `dip(station, count, kind)` | `RINSE`, 횟수, 종류 | `Result` | 담금 모션. 담그는 동안 **강한 파지(HOLD)** |

### 파지 힘 2단계 (9/18 V-17 검증 결과)
컵 옆면 파지는 들고 옮길 때는 충분하지만, **털기·헹굼·물 털기처럼 흔드는 동작에서는 더 꽉 잡아야 한다.** 파지 힘을 두 단계로 둔다: `NORMAL`(집기·이송·놓기) / `HOLD`(털기·담금·물 털기). 값은 `cell.yaml`의 `presets.<kind>.grip_force_n`·`hold_force_n`. 전환은 `cobot_common.grip_level(kind, 'HOLD'|'NORMAL')`. **흔드는 함수(F2 `shake`·`dip`·`leftover_loop`)가 시작할 때 HOLD, 끝날 때 NORMAL**로 되돌린다. 그래서 이 함수들은 `kind`를 받는다.

## 5. F3 접촉 닦기 (IR-03) · 박진용 · 모듈 `f3_wipe.wipe`
| 함수 | 인자 | 반환 | 비고 |
|---|---|---|---|
| `soap(count)` | 횟수 | `Result` | 툴 든 채 세제 수조 담금 |
| `wipe_bowl()` | — | `WipeBowlResult`: `ok, code, force_log_path, duration_s, force_mean_n` | **그릇**: 수세미 툴로 힘제어(목표 힘 유지) 나선 닦기. 상한 초과 → `FORCE_LIMIT` |
| `wipe_cup()` | — | `WipeCupResult`: `ok, code, force_log_path, duration_s, insert_depth_mm` | **컵**: 수세미 솔을 컵 안에 삽입(힘 감시) → J6 회전 + Z 상하 스트로크. 동작이 그릇과 달라 함수를 분리(9/18 팀 결정) |

툴 픽업·반납과 **스펀지 홈 안착 놓기**는 F1(`tool`, `place`)을 flow가 부른다. F3는 "용기는 홈에 안착돼 있고 툴을 쥔 상태"에서 시작한다.

## 6. flow ↔ HMI (IR-04) · 민범진(flow) · 황인재(HMI) — **ROS 통신은 여기뿐**
| 인터페이스 | 형식 | 내용 |
|---|---|---|
| `/flow/start` | srv `std_srvs/Trigger` | 구역 계획대로 전부 처리 시작 (IDLE에서만). **즉시 응답**하고 실행은 메인 스레드가 한다 |
| `/flow/stop` | srv `std_srvs/Trigger` | 현재 기능 함수가 끝난 뒤 정지 → `PAUSED` (HMI의 소프트 정지 버튼) |
| `/flow/resume` | srv `std_srvs/Trigger` | 정지·오류 지점부터 재개 |
| `/flow/state` | msg `cobot_msgs/FlowState` @2 Hz | 아래 정의. HMI는 2 s 이상 안 오면 "연결 끊김" 표시 |
| `/flow/event` | msg `cobot_msgs/FlowEvent` | 용기 1개 완료·격리·오류마다 1건 → HMI가 SQLite에 저장 |
| 🟡 `/cell/force` | msg `std_msgs/Float32` @10 Hz(닦는 동안만) | 접촉 힘(N) → HMI 힘 그래프. **제안, DSN-03에서 확정** |
| 🟡 `/cell/grip_width` | msg `std_msgs/Float32` (파지·놓기마다) | 그리퍼 폭(mm) → HMI 표시. **제안, DSN-03에서 확정** |
| HMI 브리지 | REST `POST /api/start` `/api/stop` `/api/resume`, `GET /api/state`, `GET /api/history`, WS `/ws/state` | FastAPI가 rclpy로 중계 (PC-B) |

이 서비스·토픽은 `flow_node`의 **통신 노드**(백그라운드 실행기)가 맡는다. 콜백은 값 저장·깃발 세우기만 하고 로봇 함수를 부르지 않는다(SDD §3.2). 하드웨어 비상정지는 로봇 E-Stop이다. HMI 버튼은 소프트 정지이며 화면에 항상 보이게 둔다.

외부 ROS 인터페이스(우리가 정의하지 않음, `cobot_common`만 사용): 두산 드라이버 `/dsr01/dsr_controller2/*`(DSR_ROBOT2 API 경유), 그리퍼 드라이버 `/onrobot/sendCommand`(srv) + 🟡 현재 폭을 읽는 경로(**V-05에서 확정**). 드라이버(`OnRobotRGControllerServer`)는 `OnRobotRGInput`을 **발행하지 않는다**(9/19 소스 확인: 나가는 것은 `/joint_states`→`/onrobot_joint_states` remap의 `JointState`뿐, 서비스는 `/onrobot/sendCommand`·`/onrobot/pose`·`/onrobot/restartPower`). 후보: `/onrobot_joint_states`의 관절각을 폭으로 환산 / 드라이버의 그리퍼 action 결과.

## 7. 메시지 정의 (정본: [interfaces/](interfaces/))
```
# FlowState.msg
string step            # §2 흐름 상태
string kind            # 현재 용기 BOWL/CUP/""
string zone_id         # 현재 반납 구역
uint16 done_bowl
uint16 done_cup
uint16 isolated
uint16 target_bowl     # 계획 수량 (진행률 계산용)
uint16 target_cup
uint16 sponge_uses
uint16 soap_dips
uint16 rinse_dips
string last_code
string message
builtin_interfaces/Time stamp

# FlowEvent.msg
builtin_interfaces/Time stamp
string kind
string zone_id
string rack_slot
uint8 attempts          # 탐색 파지 시도 횟수
float32 weight_before_g
float32 weight_after_g
string result           # DONE / ISOLATED / ERROR / SKIPPED
string code
float32 duration_s
string force_log_path
```
`cobot_msgs` v3.0은 이 메시지 2개만 담는다(서비스 12개 삭제). `/flow/*` 서비스는 `std_srvs/Trigger`.

## 8. 호출 순서 (flow_node)
```python
from f1_handling import handling as f1          # mock 이면 f2_sense_flow.mock.mock_f1
from f2_sense_flow import sense as f2
from f3_wipe import wipe as f3                  # mock 이면 f2_sense_flow.mock.mock_f3

# plan (params.yaml flow 절): [{zone: RET_B, kind: BOWL, count: 2}, {zone: RET_C, kind: CUP, count: 2}]
# 구역마다 count 회 또는 EMPTY_ZONE 까지 반복:
# BOWL
f1.pick('RET_B', 'BOWL') → f1.move_to('WEIGH', True) → f2.leftover_loop('BOWL', 2)
→ f1.place('SPONGE_BED_B')                      # 안착 놓기(순응 하강·탐색, 실패 SEAT_FAIL)
→ f1.tool('SPONGE', 'PICK') → f3.soap(3) → f3.wipe_bowl() → f1.tool('SPONGE', 'RETURN')
→ f1.pick('SPONGE_BED_B', 'BOWL')               # 홈에 놓인 그릇 재파지(고정 위치, 탐색점 1개)
→ f2.dip('RINSE', 1, 'BOWL') → f2.shake('RINSE', 3, 'BOWL')
→ f1.rack_place('RACK_Bn', 'BOWL') → f1.move_to('HOME', False)
# CUP: 동일, SPONGE_BED_C · tool('BRUSH') · wipe_cup() · RACK_Cn
```

**실패 정책 (`params.yaml` flow 절 `policy`)**
| 코드 | 처리 |
|---|---|
| `EMPTY_ZONE` | 구역 종료 → 다음 구역 (기록 SKIPPED) |
| `LEFTOVER_REMAIN` `SEAT_FAIL` | ISOLATE 후 다음 용기 |
| `FORCE_LIMIT` `TIMEOUT` `RACK_JAM` `TOOL_FAIL` | 후퇴 후 재시도 1회 → ISOLATE |
| `RACK_FULL` | PAUSED + HMI 알림 → 팔레트 교체 후 resume |
| `ROBOT_ERROR` (기능 함수에서 새어 나온 예외 포함) | PAUSED → 운영자 확인 후 resume |
| stop 버튼 | 현재 기능 함수가 끝난 뒤 PAUSED → resume |

## 9. 설정 파일 (IR-07) — 파일 2개
설정은 `src/cobot_common/config/`의 **파일 2개**로 둔다(9/18 최종 결정).

| 파일 | 주인 | 내용 | 읽는 쪽 |
|---|---|---|---|
| **`cell.yaml`** (공용) | **한석형 혼자** | 속도·안전 높이·공통 힘 상한·타임아웃, 프리셋(종류별 폭·`grip_force_n`·`hold_force_n`), 스테이션·반납 구역(탐색점)·스펀지 홈(안착 파라미터)·팔레트 칸 좌표 | 전부 (읽기만) |
| **`params.yaml`** (기능별 절) | 절마다 주인 | `f1:` 한석형 · `f2:` 민범진(기준 무게·잔반 임계·털기·담금) · `f3:` 박진용(세제 담금·`wipe_bowl`·`wipe_cup`) · `flow:` 민범진(구역 계획·실패 정책·칸 배정·소모품·`use_mock`) · `hmi:` 황인재(포트·갱신 주기·끊김 판정·DB 경로) | 각 패키지는 자기 절 + `cell.yaml` |

왜 2개인가: ① 공용 값(좌표·속도·프리셋)은 한 곳, 주인 한 명 — F1의 `place`와 F3의 `wipe_bowl`이 같은 `cell.yaml`을 읽으므로 값이 갈라질 수 없다. ② 나머지는 한 파일에서 한눈에 — 절이 떨어져 있어 git이 자동으로 합친다. 규칙은 하나, **자기 절만 고친다.** ③ 코드는 `cobot_common.config.load()`가 두 파일을 읽어 하나의 설정(`cfg['cell']`, `cfg['f3']` …)으로 합쳐 준다. 키 이름 규칙은 SDD §4.3.

## 10. 시험용 가짜 구현
- **`f2_sense_flow.mock.mock_f1` · `mock_f3`**: 실제 모듈과 **같은 함수 이름·같은 인자**로 즉시 `Result(ok=True)`를 돌려주고, 설정으로 실패 코드를 주입한다(`flow.mock.fail_on: ["place:SEAT_FAIL"]`). flow는 `params.yaml`의 `flow.use_mock: [f1, f3]`로 어느 쪽을 import할지 고른다. 전부 mock이면 두산 드라이버 없이 돈다 — flow·HMI 개발용, 민범진 제공. 서명 일치는 `cobot_api.check_api(mock_f1, F1Api)`로 검사한다.
- **`fake_state_pub`**: `/flow/state`·`/flow/event`를 시나리오대로 발행 — HMI 개발용, 황인재 제작.
- **단독 시험 스크립트** `rig_f1.py`·`rig_f2.py`·`rig_f3.py`: `cobot_common.init('rig_f1')` 뒤 자기 함수만 직접 부른다(SDD §3.2). 용기·툴은 손으로 놓아 준다.
