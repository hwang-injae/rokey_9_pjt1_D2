# 인터페이스 정의서 — PreWash-Cell (D그룹 2조)

> 기준: 2026-09-22 · GitHub `main` · 원문 `docs/02_인터페이스_IRD.md`
> **정본 파일**: 함수 약속 `src/cobot_api/cobot_api/contracts.py` · 메시지 `src/cobot_msgs/msg/*.msg` — 문서와 파일이 다르면 **파일이 정본**
> 변경 규칙: 이름·인자·반환 필드·코드·메시지 필드를 바꾸려면 이슈 → 4명 확인 → PR (혼자 바꾸지 않는다)

## 0. 한눈에 보기

| 구분 | 무엇 | 개수 |
|---|---|---|
| **ROS 토픽** (우리가 정의) | `/flow/state` · `/flow/event` | 2 |
| **ROS 서비스** (우리가 정의) | `/flow/start` · `/flow/stop` · `/flow/resume` · `/flow/abort` | 4 |
| **ROS 액션** | 없음 — 긴 동작은 flow_node 안의 함수로 돌고, 진행 상황은 `/flow/state` 로 알린다 | 0 |
| **기능 함수** (파이썬 · ROS 아님) | F1 5 · F2 4 · F3 3 — `flow_node` 가 부른다 | 12 |
| 드라이버 인터페이스 (두산·강사 배포 — 우리는 부르기만) | 두산 `dsr_controller2` 서비스 · 그리퍼 `/onrobot/*` | — |
| HMI 웹 (브라우저 ↔ `hmi_bridge`) | REST 5 · WebSocket 1 | — |

## 1. ROS 토픽

| 토픽 | 메시지 | 주기 | 보내는 쪽 → 받는 쪽 | 용도 |
|---|---|---|---|---|
| `/flow/state` | `cobot_msgs/msg/FlowState` | **2 Hz** | `flow_node` → `hmi_bridge` | 지금 단계·진행 수량·소모품 — 화면 갱신. HMI 는 2 s 넘게 안 오면 "연결 끊김" |
| `/flow/event` | `cobot_msgs/msg/FlowEvent` | **용기 1개가 끝날 때마다 1건** | `flow_node` → `hmi_bridge` | 완료·격리·오류·건너뜀 기록 — 이력 표 |

### `FlowState.msg`
| 필드 | 타입 | 뜻 |
|---|---|---|
| `step` | string | 흐름 단계 (§4 `step` 값) |
| `kind` | string | 지금 처리 중인 용기 `BOWL` / `CUP` / `""` |
| `zone_id` | string | 지금 반납 구역 `RET_B` / `RET_C` |
| `done_bowl` · `done_cup` | uint16 | 적재까지 끝낸 그릇·컵 수 |
| `isolated` | uint16 | 격리 구역으로 뺀 용기 수 |
| `target_bowl` · `target_cup` | uint16 | 계획 수량 (진행률) |
| `sponge_uses` · `soap_dips` · `rinse_dips` | uint16 | 소모품 사용 횟수 (수세미·세제 담금·헹굼 담금) |
| `last_code` | string | 마지막 결과 코드 (§4) — 경고·오류 표시 |
| `message` | string | 사람이 읽는 설명 (오류 원인 등) |
| `stamp` | builtin_interfaces/Time | 보낸 시각 |

### `FlowEvent.msg`
| 필드 | 타입 | 뜻 |
|---|---|---|
| `stamp` | builtin_interfaces/Time | 끝난 시각 |
| `kind` · `zone_id` | string | 용기 종류 · 꺼낸 반납 구역 |
| `rack_slot` | string | 넣은 팔레트 칸 `RACK_B1`… (격리면 빈칸) |
| `attempts` | uint8 | 집기 시도 횟수 |
| `weight_before_g` · `weight_after_g` | float32 | 털기 전·후 무게 (g) |
| `result` | string | `DONE`(완료) · `ISOLATED`(격리) · `ERROR`(오류) · `SKIPPED`(빈 구역 건너뜀) |
| `code` | string | 원인 코드 (§4) |
| `duration_s` | float32 | 용기 1개 처리 시간 = 사이클 타임 |
| `force_log_path` | string | 닦기 힘 기록 CSV 경로 |

## 2. ROS 서비스 — HMI 버튼 4개 (`std_srvs/srv/Trigger`)

| 서비스 | 받는 때 | 하는 일 | 응답 |
|---|---|---|---|
| `/flow/start` | `IDLE` 일 때만 | 구역 계획대로 전부 처리 시작. **바로 응답**하고 실행은 메인 스레드가 한다 | `success` · `message` |
| `/flow/stop` | 동작 중 | **즉시 일시 정지** — 하던 이동을 그 자리에서 멈추고 `PAUSED` (두산 `move_pause`) | 〃 |
| `/flow/resume` | `PAUSED` 일 때만 | 일시 정지였으면 **하던 이동을 이어서**(`move_resume`), 실패로 멈췄으면 그 단계부터 다시 | 〃 |
| `/flow/abort` | `PAUSED` 일 때만 (로봇 오류는 거절) | 지금 용기를 접는다 — HOME → 쥔 툴 반납 → 용기를 격리 구역에 → 다음 용기 | 〃 |

- 서비스 콜백은 **깃발만 세운다**. 로봇 명령은 메인 스레드가 보낸다 → 버튼 응답 1 s 이내.
- 하드웨어 **비상정지는 로봇 E-Stop** 이다. HMI 버튼은 소프트 정지이며 화면에 항상 보인다.
- 터미널 **Ctrl+C** 도 로봇을 즉시 세운다(프로그램 종료 시 정지 명령 · 9/22 실기 5/5).

## 3. 흐름 — 용기 1개 (`flow_node` 가 부르는 순서)

```
그릇: f1.pick('RET_B','BOWL') → f1.move_to('WEIGH', True, 'BOWL') → f2.leftover_loop('BOWL', 2)
   → f1.place('SPONGE_BED_B') → f1.tool('SPONGE','PICK') → f3.soap(3,'BOWL') → f3.wipe_bowl() → f1.tool('SPONGE','RETURN')
   → f1.pick('SPONGE_BED_B','BOWL') → f2.dip('RINSE', 1, 'BOWL') → f2.shake('RINSE', 3, 'BOWL')
   → f1.rack_place('RACK_B1','BOWL') → f1.move_to('HOME', False)
컵  : 같은 순서 · SPONGE_BED_C · tool('BRUSH') · wipe_cup() · RACK_C1
계획: RET_B 그릇 2개 → RET_C 컵 2개 (params.yaml flow.plan)
```

## 4. 공통 ID · 코드 (코드·설정·메시지·HMI 에서 같은 문자열)

| 분류 | 값 |
|---|---|
| 용기 `kind` | `BOWL`(그릇) · `CUP`(컵) |
| 툴 `tool` | `SPONGE`(그릇용 수세미 툴) · `BRUSH`(컵용 솔) |
| 반납 구역 `zone_id` | `RET_B` · `RET_C` — 내리막 공급이라 **구역마다 집는 자리 1개**(하나를 꺼내면 뒤 용기가 같은 자리로 내려온다) |
| 팔레트 칸 `rack_slot` | `RACK_B1` · `RACK_B2`(그릇) · `RACK_C1` · `RACK_C2`(컵) |
| 스테이션 `station` | `HOME` `WEIGH` `WASTE` `SPONGE_BED_B` `SPONGE_BED_C` `TOOL_SPONGE` `TOOL_BRUSH` `SOAP` `RINSE` `ISOLATE` |
| 흐름 단계 `step` | `IDLE` `PICK` `WEIGH` `SHAKE` `SEAT` `SOAP` `WIPE` `RINSE` `RACK` `ISOLATE` `DONE` `ERROR` `PAUSED` |

| 결과 코드 `code` | 뜻 | flow 의 처리 (`params.yaml` `flow.policy`) |
|---|---|---|
| `OK` | 정상 | 다음 단계 |
| `EMPTY_ZONE` | 반납 구역에 용기가 없다 | 다음 구역으로 (`SKIPPED` 기록) |
| `LEFTOVER` | 잔반 있음(털기 필요) | 털기 반복 안에서 처리 |
| `LEFTOVER_REMAIN` | 털어도 잔반이 남는다 | 격리 → 다음 용기 |
| `GRIP_FAIL` | 놓쳤다(털기·담금 중 미끄러짐 · 빈손) | 일시 정지 → 사람이 확인 |
| `SEAT_FAIL` | 스펀지 홈에 안착 안 됨 | 격리 → 다음 용기 |
| `TOOL_FAIL` | 툴 집기·반납 실패 | 한 번 재시도 → 격리 |
| `FORCE_LIMIT` | 힘 상한 초과 | 후퇴 · 한 번 재시도 → 격리 |
| `TIMEOUT` | 시간 초과 | 한 번 재시도 → 격리 |
| `RACK_JAM` | 팔레트 칸에 걸림 | 한 번 재시도 → 격리 |
| `RACK_FULL` | 팔레트가 가득 참 | 일시 정지 → 팔레트 교체 뒤 재개 |
| `ROBOT_ERROR` | 로봇 오류(새어 나온 예외 포함) | 그 자리 정지 → 사람이 복구 (`abort` 거절) |
| `STOPPED` | 사람이 멈춤 | — |

## 5. 기능 함수 12개 (파이썬 · `cobot_api` 약속)

모든 함수는 **`Result`**(`ok` + `code` + 기능별 필드)를 돌려준다. 실패는 예외가 아니라 `ok=False` + `code`.

| 모듈 (담당) | 함수 | 반환 (기능별 필드) | 하는 일 |
|---|---|---|---|
| **F1** `f1_handling.handling` (한석형) | `pick(zone_id, kind)` | `PickResult`: `width_mm` · `attempts` · `offset_x_mm` · `offset_y_mm` | 반납 구역(또는 스펀지 홈)의 정해진 자리에서 집는다. 그릇은 옆면(벽)을 세로로, 컵은 몸통을 잡는다 |
| | `place(station, kind=None)` | `PlaceResult`: `offset_mm` | 놓기. 스펀지 홈이면 **안착 놓기**(순응 하강 → 들어갔는지 판정 → 안 되면 `SEAT_FAIL`) |
| | `move_to(station, carrying, kind=None)` | `Result` | 티칭한 자세로 이동 (들고 있으면 저속). 종류별 자리는 `kind` |
| | `tool(tool, action)` (황인재) | `ToolResult`: `width_mm` | 홀더에서 툴 집기(`PICK`) · 반납(`RETURN` — 힘으로 바닥 확인 뒤 놓기) → `TOOL_FAIL` |
| | `rack_place(rack_slot, kind)` | `Result` | 팔레트 칸 바로 위 → 수직 하강 → 놓기 → 빠져나오기 → `RACK_JAM` |
| **F2** `f2_sense_flow.sense` (민범진) | `weigh(kind)` | `WeighResult`: `weight_g` | 무게 자세에서 멈춘 뒤 N회 평균 (로봇 관절 힘으로 추정 · 빈 용기 기준값을 뺀다) |
| | `leftover_loop(kind, max_rounds)` | `LeftoverResult`: `weight_before_g` · `weight_after_g` · `rounds` | 잔반 50 g 이상이면 잔반통 위 털기 → 다시 재기 반복 → 남으면 `LEFTOVER_REMAIN` |
| | `shake(mode, count, kind)` | `Result` | 털기(`WASTE` 잔반 · `RINSE` 물). 강하게 쥔 채(HOLD) — 미끄러지면 `GRIP_FAIL` |
| | `dip(station, count, kind)` | `Result` | 헹굼 수조에 담그기 |
| **F3** `f3_wipe.wipe` (박진용) | `soap(count, kind=None)` | `Result` | 툴을 든 채 툴 홀더의 비눗물 컵에 담그기 |
| | `wipe_bowl()` | `WipeBowlResult`: `force_log_path` · `duration_s` · `force_mean_n` | 그릇 안쪽 닦기 — 바닥은 힘으로 찾고, 벽면은 힘제어로 1.5 N 유지 · 상한 초과 `FORCE_LIMIT` |
| | `wipe_cup()` | `WipeCupResult`: `force_log_path` · `duration_s` · `insert_depth_mm` | 컵 안쪽 닦기 — 솔을 넣고 Move Periodic(위아래 + 손목 회전) · 1·4번 관절이 1° 넘게 흔들리면 즉시 정지 |

- 기능 패키지끼리는 서로 부르지 않는다(부르는 쪽은 `flow_node` 하나).
- 물건은 정해진 스테이션에서만 넘긴다 → 각자 용기를 손으로 놓아 두고 **자기 함수만 단독 시험**(`rig_f*.py`)할 수 있다.
- 로봇 없이 시험할 때는 `f2_sense_flow.mock` 이 같은 이름·인자의 가짜 함수를 준다(실패 주입 가능).

## 6. 드라이버 인터페이스 (우리가 정의하지 않음 — `cobot_common` 안에서만 부른다)

| 대상 | 인터페이스 | 쓰는 곳 |
|---|---|---|
| 두산 `dsr_controller2` | 서비스 `/dsr01/dsr_controller2/motion/*`(move_joint · move_line · move_pause · move_resume · move_stop …) · `force/*`(task_compliance_ctrl · set_desired_force · release_force) · 무게(get_workpiece_weight) — `dsr_msgs2/srv/*` (두산 API `DSR_ROBOT2` 경유) | 이동 · 일시 정지 · 힘제어 · 무게 |
| 두산 상태 | 토픽 `/dsr01/joint_states` (`sensor_msgs/JointState`) | 관절 각도 (시험 스크립트·모니터링) |
| 그리퍼 드라이버 | 서비스 `/onrobot/sendCommand` (명령 문자열 1개) · 토픽 `/onrobot_joint_states` (`JointState` — 관절각으로 **폭**, effort 로 **힘** 환산) | 쥐기 · 놓기 · 폭 확인 |
| 컨트롤러 ↔ PC | 두산 전용 TCP 12345 (DDS 아님) · RG2 Compute Box Modbus TCP | 드라이버 내부 |

로봇 쪽 설정(컨트롤러에 등록, 9/22 재측정): 툴 무게 `Tool Weight` 1.440 kg · TCP `GripperDA_v1`(Z 208 mm).

## 7. HMI 웹 인터페이스 (브라우저 ↔ `hmi_bridge`, PC-B)

| 주소 | 방식 | 내용 |
|---|---|---|
| `/` | GET | 운영 화면 (Next.js 정적 파일) |
| `/api/state` | GET | 지금 상태 전체 (JSON — FlowState + 최근 이벤트 + 계획) |
| `/api/start` · `/api/stop` · `/api/resume` · `/api/abort` | POST | 버튼 → 같은 이름의 flow 서비스 → `{ok, message, latency_ms}` |
| `/ws/state` | WebSocket | 붙자마자 전체 1번, 그 뒤 상태·이벤트·연결 변화를 밀어 준다 |
| `/api/history` | GET | 🟡 예정(F4-04 — SQLite 저장) |
| `/test` | GET | 점검용 시험 페이지 |

- 기본은 **이 PC 에서만** 접속(`127.0.0.1:8000`) — 같은 와이파이의 다른 기기가 버튼을 누르지 못하게(결정 E10).

## 8. 설정 파일 2개 (`src/cobot_common/config/`) — 숫자는 코드에 쓰지 않는다

| 파일 | 내용 | 고치는 사람 |
|---|---|---|
| `cell.yaml` (공용) | 스테이션·반납 구역·팔레트 칸 **좌표** · 속도 · 힘 상한 · 타임아웃 · 그리퍼 프리셋(종류별 폭·힘) | 좌표는 황인재(9/21 부터), 프리셋은 측정한 사람 — 모두 읽기 |
| `params.yaml` (절마다 주인) | `f1` 한석형 · `f2` 민범진(빈 용기 기준·잔반 50 g·털기) · `f3` 박진용(닦기 힘·속도) · `flow` 민범진(구역 계획·실패 정책·칸 순서·소모품) · `hmi` 황인재(주소·포트·끊김 판정) | 자기 절만 |

코드는 `cobot_common.config.load()` 로 두 파일을 하나처럼 읽고, 좌표는 설정 키 이름(예 `RACK_B1`)으로 부른다.
