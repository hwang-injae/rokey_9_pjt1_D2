# TS-08 · 헹굼 뒤 **수조 안 자세**에서 HOME 으로 가다 그리퍼가 테이블을 쓸었다 (9/22)

| | |
|---|---|
| 날짜 | 2026-09-22 17:07 · 실기 · 민범진 세션 (속도 30 %) |
| 하던 일 | `rig_f2.py dip --kind BOWL --count 2` 3회 성공(헹굼 담금) → 이어서 `rig_shake_tune.py --mode RINSE --kind BOWL` 실행 |
| 증상 | 리모컨이 뜨자마자 `E15 — 먼저 HOME 으로 간다` 이동 중 **그리퍼가 테이블 상판에 닿음** → 비상정지. 34 s 뒤 그리퍼 드라이버가 죽고(`exit code 1`), 다음 동작에서 `RuntimeError: /onrobot/sendCommand 가 안 보인다` |
| 원인 | `f2.dip` 은 **수조 안 자세에서 끝난다**(`cell.stations.RINSE.BOWL.posx` z = **−13.6 mm**, 받침면보다 아래). 그 자리에서 `cc.move_to('HOME')` 은 **관절 이동**이라 팔이 테이블 높이를 가로지른다 → 그리퍼·그릇이 상판을 쓴다 |
| 왜 흐름에서는 안 났나 | `flow` 의 헹굼 다음은 `f1.rack_place` 이고, 그 함수는 **먼저 수조 위로 곧게 올라온다**(IRD §8 순서 전제). 시험대는 **직전에 어디 있었는지 모른다** — `dip` 을 돌린 터미널과 다음 시험대가 다른 프로세스다 |
| 그리퍼 드라이버가 같이 죽은 이유 | 비상정지가 **툴 전원**을 끊는다 → RG2 컴퓨트박스와의 연결이 끊겨 `OnRobotRGControllerServer` 가 종료. 증상이 "그리퍼 서비스가 사라졌다" 로 나타나 원인을 착각하기 쉽다. 이 PC 의 옛 로그에도 같은 종료가 35회 |
| 복구 | 비상정지 해제 → 펜던트 알람 리셋·Servo On → 브링업 재시작(`sod && sodreal`) → 시험대는 이제 알아서 곧게 올라온 뒤 HOME 으로 간다 |
| 피해 | 없음(30 % 속도 · 충돌 감지 정지). 로봇 슬롯 약 15분 |

## 재발 방지 — 코드가 막는다
`f2_sense_flow/preflight.py` 의 **`go_home_safely(kind, log, carrying)`** 로 바꿨다. 하는 일:
1. `cc.safe_retreat()` — 힘·순응을 끄고 **XY 는 그대로 Z 만** `cell.limits.safe_z_mm`(235)까지 올린다. 이미 위면 움직이지 않는다
2. 그 다음에 `cc.move_to('HOME', ...)`

새 설정값을 만들지 않았다 — 팀이 이미 정한 후퇴 높이(`cell.limits.safe_z_mm`)를 그대로 쓴다(AGENTS §3 규칙 6).

연결된 곳(전부 `cc.move_to('HOME')` 을 직접 부르던 자리):
`rig_f2` (2곳) · `rig_shake_tune` · `rig_jog` · `rig_int12` · `rig_flow_once`

**`flow.abort_container`** 도 같이 고쳤다 — 중단(`/flow/abort`)은 **아무 때나** 눌리고 헹굼 구간이면 수조 안이다. HOME 복귀 앞에 `self._retreat()`(= `cc.safe_retreat`)를 넣었다.

시험: `test_f2_preflight.py` 2건(후퇴가 HOME 보다 먼저 · 높이를 못 읽어도 후퇴는 한다) · `test_f2_policy.py` 1건(중단 정리의 순서).

## 사람이 기억할 것
- **낮은 자리에서 끝나는 함수**: `f2.dip` · `f2.shake`(RINSE) — 수조 안에서 끝난다. 다음에 무엇을 하든 **먼저 곧게 위로**.
- 그리퍼 명령이 갑자기 `sendCommand 가 안 보인다` 로 실패하면 **그리퍼가 아니라 비상정지·툴 전원**을 먼저 의심한다. 로봇이 어디 부딪혔는지 본다.
- 브링업 재시작은 그리퍼 드라이버를 되살리는 유일한 방법이다(강사 배포본 · 우리가 고치지 않는다).
