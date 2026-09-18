# 시스템 설계 문서 (SDD)
## ReWash-Cell — 다회용기 예비세척·식기세척기 팔레트 적재 자동화 셀

| 항목 | 내용 |
|---|---|
| 문서 ID | SDD-REWASH-001 · v2.0 (2026-09-18) |
| 상위 | [01_요구사항_BR-SR.md](01_요구사항_BR-SR.md) · [02_인터페이스_IRD.md](02_인터페이스_IRD.md) · 일정표(구글 드라이브 xlsx) |
| 그림 | [images/system_architecture_pc.svg](images/system_architecture_pc.svg) (편집용 [.drawio](images/system_architecture_pc.drawio)) · [images/system_design.svg](images/system_design.svg) · [images/workcell.svg](images/workcell.svg) |

이 문서는 요구사항을 "실제로 어떻게 만들 것인가"로 바꾼다. PC 배치, 노드·패키지, 통신, 워크셀 좌표, 상태 머신, 각 노드의 내부 절차, 오류 처리, 안전, 배포를 정한다. 강사 산출물(시스템 아키텍처·네트워크 구성도·동작 순서도·하드웨어 구성·인터페이스 정의서·노드 구조도·HMI 화면·예외/오류·위험요소/안전대책)은 §12 표에서 이 문서의 절로 연결한다.

---

## 1. 시스템 아키텍처 (PC 단위)

![시스템 아키텍처](images/system_architecture_pc.svg)

### 1.1 PC 배치 (통합 실행: 2대 · 개발: 4대 각자)
| PC | 역할 | 실행하는 것 | 네트워크 |
|---|---|---|---|
| **PC-A 로봇 제어 PC** (필수) | 두산 드라이버 + 동작 노드 전부 | `ws_dsr`: `m0609_rg2_bringup bringup.launch.py mode:=real host:=192.168.1.100 port:=12345` → `dsr_controller2`(/dsr01) · `rokey_pjt01_ws`: `f1_node` `f2_node` `f3_node` `flow_node` + `cobot_common` · `records.csv` | 컨트롤러와 같은 유선망 192.168.1.x, `ROS_DOMAIN_ID=60` |
| **PC-B HMI PC** (권장) | 시스템 모니터 | `rokey_pjt01_ws`: `cobot_msgs` + `f4_hmi/hmi_bridge`(FastAPI + rclpy, :8000) · `rewash.db`(SQLite) · 브라우저 | PC-A와 같은 스위치, `ROS_DOMAIN_ID=60` (DDS) |
| 개발 PC 4대 | 각자 독립 개발 | 한석형: `sodvir` + f1 + rig_f1 / 민범진: `sodvir` + f2 + flow + mock_f1_f3 / 박진용: `sodvir` + f3 + rig_f3 / 황인재: fake_state_pub + hmi_bridge + 브라우저(드라이버 불필요) | 각자 Virtual(127.0.0.1) |

동작 노드를 전부 PC-A에 두는 이유: 서비스 호출이 네트워크를 타면 지연·끊김이 로봇 동작 실패로 이어진다. HMI만 분리하면 화면을 따로 보여줄 수 있고 네트워크 구성도가 실제 내용이 된다. PC 2대 통신(V-09)이 안 되면 PC-A 1대에서 전부 실행한다(기술적으로 동일).

### 1.2 네트워크 구성도
```
[M0609 컨트롤러 192.168.1.100 :12345] ──유선── [스위치 192.168.1.0/24] ──유선── [PC-A 192.168.1.__]
                                                        │                        (DDS, DOMAIN 60)
[RG2 Compute Box 192.168.1.1 (설정 웹)]                 └────────유선────────── [PC-B 192.168.1.__] ── 브라우저/태블릿 (:8000)
```
PC-A ↔ 컨트롤러는 두산 전용 TCP(DDS 아님). PC-A ↔ PC-B는 ROS 2 DDS(멀티캐스트). 안 되면 FastDDS Discovery Server(강의 자료)로 전환.

### 1.3 통신 정의 (토픽·서비스·네트워크)
| 이름 | 타입 | 방향 | 구간 |
|---|---|---|---|
| `/flow/state` | `cobot_msgs/msg/FlowState` (2 Hz) | flow_node → hmi_bridge | PC-A → PC-B (DDS) |
| `/flow/event` | `cobot_msgs/msg/FlowEvent` | flow_node → hmi_bridge | PC-A → PC-B (DDS) |
| `/flow/start` `/flow/stop` `/flow/resume` | `std_srvs/srv/Trigger` | hmi_bridge → flow_node | PC-B → PC-A (DDS) |
| `/f1/pick` `/f1/place` `/f1/move_to` `/f1/tool` `/f1/rack_place` `/f1/home` | `cobot_msgs/srv/F1Pick` `F1Place` `F1MoveTo` `F1Tool` `F1RackPlace` · `std_srvs/Trigger` | flow_node → f1_node | PC-A 내부 |
| `/f2/weigh` `/f2/leftover_loop` `/f2/shake` `/f2/dip` | `cobot_msgs/srv/F2Weigh` `F2LeftoverLoop` `F2Shake` `F2Dip` | flow_node → f2_node | PC-A 내부 |
| `/f3/seat` `/f3/soap` `/f3/wipe` | `cobot_msgs/srv/F3Seat` `F3Soap` `F3Wipe` | flow_node → f3_node | PC-A 내부 |
| `/dsr01/motion/move_joint` · `move_line` | `dsr_msgs2/srv/MoveJoint` · `MoveLine` | cobot_common(DSR_ROBOT2) → dsr_controller2 | PC-A 내부 |
| `/dsr01/force/task_compliance_ctrl` · `set_desired_force` · `release_force` · `get_workpiece_weight` | `dsr_msgs2/srv/…` | cobot_common → dsr_controller2 | PC-A 내부 |
| `/dsr01/io/set_ctrl_box_digital_output` · `get_ctrl_box_digital_input` | `dsr_msgs2/srv/…` (RG2 DO1/DO2 · DI1/DI2) | cobot_common → dsr_controller2 | PC-A 내부 |
| `/dsr01/joint_states` | `sensor_msgs/msg/JointState` | dsr_controller2 → 모니터링 | PC-A |
| dsr_controller2 ↔ 컨트롤러 | 두산 전용 TCP, 포트 12345 | | PC-A ↔ 컨트롤러 |
| 브라우저 ↔ hmi_bridge | HTTP `GET /` · `POST /api/start|stop|resume` · `GET /api/state` · `GET /api/history` · WS `/ws/state` (JSON) | | PC-B 내부 또는 LAN |
| hmi_bridge → rewash.db | SQLite `events`(FlowEvent 필드 그대로) · `state_log` | | PC-B 내부 |

`/dsr01/*` 서비스의 정확한 이름·필드는 [두산 ROS 2 매뉴얼(jazzy)](https://doosanrobotics.github.io/doosan-robotics-ros-manual/jazzy/services/motion_services.html)로 확인 후 확정한다. 우리 코드는 `cobot_common`을 통해서만 부르므로 이름이 달라도 한 곳만 고친다.

### 1.4 서브시스템 (패키지 7 · 노드 5)
| 패키지 | 노드 | 담당 | 소유 설정 | PC |
|---|---|---|---|---|
| `f1_handling` | `f1_node` | 한석형 | `f1.yaml` | A |
| `cobot_common` | (라이브러리) 두산 API를 감싼 공용 로봇 함수 모음 | 한석형 | 속도 상한·안전 높이 | A |
| `f2_sense_flow` | `f2_node`, `flow_node` | 민범진 | `f2.yaml` `flow.yaml` | A |
| `cobot_msgs` | (srv 12 · msg 2, IRD 정본) | 민범진 | IRD | A·B |
| `f3_wipe` | `f3_node` | 박진용 | `f3.yaml` | A |
| `f4_hmi` | `hmi_bridge` (+ `fake_state_pub` 개발용) | 황인재 | `hmi.yaml` | B |
| `rewash_bringup` | (launch) `rewash.launch.py` · `rewash_mock.launch.py` | 민범진 | — | A |

### 1.5 설계 결정
| 결정 | 이유 |
|---|---|
| 흐름 제어를 flow_node 하나로 집중 | 노드 간 호출이 얽히면 통합이 불가. 기능 노드는 서비스 제공자로만 |
| 기능 단위 노드 분할 | 4명 동시 개발. 각 기능이 단독 리그에서 시험 가능 |
| 서비스(동기) 사용, 액션 미사용 | 각 동작이 짧고(≤30 s) 취소 요구가 없음. 정지는 flow가 다음 호출을 안 하는 방식 |
| 종류 = 반납 구역, 위치는 탐색 | 비전 없이 종류 판별을 없애고, 위치·겹침은 **접촉 하강 + 파지 폭**으로 흡수 |
| 물리 인계 위치 고정 | F1이 놓은 자리에서 F3 시작 → 단독 시험은 손으로 놓기만 하면 됨 |
| 힘제어는 "힘 유지", 깊이 미사용 | 스펀지가 눌리므로 깊이 기준이 흔들림 |
| 안착 실패 탐색 = Move Periodic | 비전 없이 홈을 찾는 수단. 진폭·시간 한도로 안전 |
| Virtual + mock 2단 검증 | Virtual엔 힘·무게가 없어 mock이 흐름·HMI를, 실기가 임계값을 담당 |
| HMI = FastAPI 웹 + SQLite | 브라우저 어디서나, PC-B 분리 가능. SQLite는 파이썬 내장이라 설치 없음. MQTT는 ROS 토픽과 중복이라 안 씀 |
| PC 2대 | 로봇 동작은 한 PC, 모니터만 분리. 실패 시 1대로 축소 |

---

## 2. 하드웨어·워크셀

![워크셀](images/workcell.svg)

| 스테이션 | 위치(확정 시 기입) | 좌표계 | 비고 |
|---|---|---|---|
| `RET_B` / `RET_C` 반납 구역 | 로봇 좌측 전방, 각 200×200 mm급 | UC1 `RETURN` | 기준점 1 + 탐색점 오프셋. 용기가 겹치거나 어긋나 있어도 됨 |
| `WEIGH` | 잔반통 상공 고정 자세 | base | 측정 자세 1개 |
| `WASTE` | 잔반통 | base | 털기 진폭 반경 확보 |
| `SPONGE_BED_B` / `_C` | 스펀지 고정틀 홈 | UC2 `BED` | 작업대 고정. 닦기 후 재파지 위치(고정) |
| `TOOL_SPONGE` / `TOOL_BRUSH` | 툴 홀더 | UC2 | 손잡이 방향 고정 |
| `SOAP` / `RINSE` | 수조 2개(빈) | UC3 `TUB` | 컨트롤러 반대편 |
| `RACK_B1..2` / `RACK_C1..4` | 식기세척기용 팔레트 모형 | UC4 `RACK` | 기준점 1 + 오프셋(Pallet), 칸별 각도 |
| `ISOLATE` | 격리 구역 | base | 2개 이상 |
| `HOME` | 안전 자세 | joint | 모든 이동의 시작·끝 |

하드웨어 구성: M0609 + 컨트롤러 + RG2(Compute Box) + PC-A·PC-B + 스위치 + 워크셀 기구(반납 구역 트레이, 잔반통, 스펀지 고정틀, 툴 홀더 2, 수조 2, 팔레트 모형, 격리 구역). 용기 그릇 2·컵 2, 잔반 대용품(구슬·쌀).

---

## 3. 소프트웨어 구조
```
rokey_pjt01_ws/                ← 저장소 루트 (rokey_9_pjt1_D2)
├── docs/                      문서·인터페이스 정본·이미지
├── src/
│   ├── cobot_msgs/            srv·msg (IRD 정본)
│   ├── cobot_common/          robot.py (move/grip/force/weigh 공용 함수) · presets.py · stations.py
│   ├── f1_handling/           f1_node.py · config/f1.yaml · test/rig_f1.py
│   ├── f2_sense_flow/         f2_node.py · flow_node.py · config/f2.yaml · flow.yaml · mock/mock_f1_f3.py · logger.py
│   ├── f3_wipe/               f3_node.py · config/f3.yaml · test/rig_f3.py
│   ├── f4_hmi/                app.py (FastAPI) · static/index.html · fake_state_pub.py · db.py (SQLite) · config/hmi.yaml
│   └── rewash_bringup/        launch/rewash.launch.py · rewash_mock.launch.py
└── build/ install/ log/       (.gitignore)
```
두산 드라이버는 별도 워크스페이스 `~/ws_cobot_pjt/ws_dsr`(강사 배포, 수정 안 함)에 있고, 우리 워크스페이스(clone 위치 자유, `.bashrc`의 `REWASH_WS`)가 그 위에 겹쳐진다(source 순서: ws_dsr → rokey_pjt01_ws). 상세는 [setup/M0609_환경설정.md](setup/M0609_환경설정.md).

### 3.1 `cobot_common` 공용 로봇 함수 (한석형)
| 함수 | 내용 |
|---|---|
| `move_to(station, carrying)` | 안전 높이 경유 movej/movel, carrying이면 속도 상한 |
| `move_rel(dx, dy, dz, frame)` | 기준점 대비 상대 이동(탐색점 이동용) |
| `grip(width, force) → width` | RG2 DO 제어 + DI 완료 대기 + 폭 피드백 |
| `release()` | |
| `weigh(n) → g` | reset → 정지 → get_workpiece_weight n회 평균 |
| `force_on(axis, target, limit)` / `force_off()` | task_compliance_ctrl + set_desired_force |
| `contact_down(max_depth, limit) → depth, force` | amovel 하강 + check_force_condition + stop (탐색 파지·안착·삽입 공용) |
| `periodic_search(amp, period, duration)` | Move Periodic |
| `safe_retreat()` | 툴 Z 후퇴 → 안전 높이 |

---

## 4. 데이터 흐름

### 4.1 동작 순서도 (그릇 1개)
```mermaid
sequenceDiagram
  participant H as HMI(PC-B)
  participant W as flow_node
  participant A as f1_node
  participant B as f2_node
  participant C as f3_node
  H->>W: /flow/start
  W->>A: pick(RET_B, BOWL)  — 탐색점 순회·접촉 하강·폭 판정
  A-->>W: ok, width, attempts, offset
  W->>A: move_to(WEIGH, carrying)
  W->>B: leftover_loop(BOWL, 2)
  B-->>W: ok / LEFTOVER_REMAIN
  W->>A: move_to(SPONGE_BED_B) · place
  W->>C: seat(BOWL)
  W->>A: tool(SPONGE, PICK)
  W->>C: soap(3) · wipe(BOWL)
  C-->>W: ok, force_log
  W->>A: tool(SPONGE, RETURN) · pick(SPONGE_BED_B, BOWL)
  W->>B: dip(RINSE,1) · shake(RINSE,3)
  W->>A: rack_place(RACK_B1, BOWL) · home
  W-->>H: /flow/event(DONE) · /flow/state
  H->>H: SQLite INSERT events
```

### 4.2 데이터 사전
- 서비스·메시지: IRD §3~7 (정본 `docs/interfaces/`)
- `records.csv`(PC-A) 열: `ts, kind, zone_id, attempts, rack_slot, weight_before_g, weight_after_g, leftover_rounds, seat_offset_mm, wipe_duration_s, force_log_path, result, code, duration_s`
- `rewash.db`(PC-B, SQLite): 표 `events`(FlowEvent 필드 + `id`, `received_at`) · `state_log`(step, kind, zone_id, stamp, 1 Hz 샘플)
- 힘 로그 `force_YYYYMMDD_HHMMSS.csv`: `t, fx, fy, fz, target`

### 4.3 설정 파일 스키마 (요약)
```yaml
# f1.yaml
presets:
  BOWL:   {grip_width: 62.0, grip_force: 25, width_tol: 3.0, approach_z: 40}
  CUP:    {grip_width: 70.0, grip_force: 20, width_tol: 3.0, approach_z: 40}
  SPONGE: {grip_width: 30.0, grip_force: 30, width_tol: 2.0}
  BRUSH:  {grip_width: 22.0, grip_force: 30, width_tol: 2.0}
zones:
  RET_B: {frame: RETURN, origin: [..], search: {offsets_mm: [[0,0],[40,0],[-40,0],[0,40],[0,-40],[40,40],[-40,-40]], max_attempts: 7, descend_max_mm: 80, contact_limit_n: 10}}
  RET_C: {frame: RETURN, origin: [..], search: {offsets_mm: [[0,0],[35,0],[-35,0],[0,35],[0,-35]], max_attempts: 5, descend_max_mm: 100, contact_limit_n: 10}}
  SPONGE_BED_B: {frame: BED, origin: [..], search: {offsets_mm: [[0,0]], max_attempts: 1}}
stations: {HOME: {posj: [...]}, WEIGH: {...}, ...}
rack: {origin: [...], slots: {RACK_B1: {offset: [..], tilt_deg: 30}, ..., RACK_C4: {...}}}
limits: {vel_carry: 30, vel_free: 60, safe_z: 150, insert_force_limit: 15}
# f2.yaml
empty_weight_g: {BOWL: 180, CUP: 120}
leftover_threshold_g: 50
weigh_samples: 5
shake: {WASTE: {amp_deg: 15, cycles: 4, period_s: 0.6}, RINSE: {amp_deg: 10, cycles: 3, period_s: 0.5}}
dip: {SOAP: {depth_mm: 40, hold_s: 0.5}, RINSE: {depth_mm: 60, hold_s: 1.0}}
# f3.yaml
seat: {approach_z: 30, contact_limit: 15, search: {amp_mm: 3, period_s: 0.8, max_s: 6}}
wipe_bowl: {target_force: 4.0, limit: 10.0, radius_mm: [15, 35], turns: 4, duration_s: 15}
wipe_cup:  {rot_deg: 180, cycles: 4, stroke_mm: 30, limit: 10.0}
# flow.yaml
plan: [{zone: RET_B, kind: BOWL, count: 2}, {zone: RET_C, kind: CUP, count: 2}]
rack_order: {BOWL: [RACK_B1, RACK_B2], CUP: [RACK_C1, RACK_C2, RACK_C3, RACK_C4]}
policy: {EMPTY_ZONE: next_zone, LEFTOVER_REMAIN: isolate, SEAT_FAIL: isolate,
         FORCE_LIMIT: retry:1->isolate, TIMEOUT: retry:1->isolate, RACK_JAM: retry:1->isolate, TOOL_FAIL: retry:1->isolate,
         RACK_FULL: pause, ROBOT_ERROR: pause}
consumables: {sponge_max_uses: 20, soap_max_dips: 60}
# hmi.yaml
port: 8000
state_rate_hz: 2
disconnect_after_s: 2.0
db_path: rewash.db
```
좌표·힘·횟수는 전부 여기에 둔다. 코드에 숫자를 쓰지 않는다. 경로는 항상 패키지 기준 상대경로.

---

## 5. 상세 설계

### 5.1 flow_node 상태 머신 (민범진)
```mermaid
stateDiagram-v2
  [*] --> IDLE
  IDLE --> PICK: start / plan의 다음 용기
  PICK --> WEIGH: ok
  PICK --> NEXT_ZONE: EMPTY_ZONE (기록 SKIPPED)
  WEIGH --> SHAKE: LEFTOVER
  WEIGH --> SEAT: ok
  SHAKE --> WEIGH: 재측정 (≤max_rounds)
  SHAKE --> ISOLATE: LEFTOVER_REMAIN
  SEAT --> SOAP: ok
  SEAT --> ISOLATE: SEAT_FAIL
  SOAP --> WIPE
  WIPE --> RINSE: ok
  WIPE --> WIPE: FORCE_LIMIT/TIMEOUT (≤1, 후퇴 후)
  WIPE --> ISOLATE: 재시도 초과
  RINSE --> RACK
  RACK --> NEXT: ok
  RACK --> RACK: RACK_JAM (≤1)
  RACK --> ISOLATE: 재시도 초과
  RACK --> PAUSED: RACK_FULL
  ISOLATE --> NEXT
  NEXT --> PICK: 구역 count 남음
  NEXT --> NEXT_ZONE: count 소진
  NEXT_ZONE --> PICK: 다음 구역
  NEXT_ZONE --> DONE: 구역 없음
  state "any" as ANY
  ANY --> PAUSED: stop / ROBOT_ERROR
  PAUSED --> (이전 상태): resume
```
- 각 전이에서 `/flow/state` 발행(2 Hz 타이머 + 전이 즉시), 용기 종료 시 `/flow/event` + CSV 1행.
- `stop`은 현재 서비스 완료 후 다음 호출을 보류. 하드웨어 비상정지는 로봇 E-Stop.
- 어떤 실패에서도 **툴은 홀더에 반납**(flow가 `tool(RETURN)` 호출), 로봇은 안전 높이.

### 5.2 f1_node (한석형)
**pick (탐색 파지)** — 겹치거나 어긋난 용기를 비전 없이 집는 절차:
```
for i, (dx,dy) in enumerate(zone.search.offsets_mm):        # 탐색점 순서
    move_to(zone 상공 + (dx,dy), carrying=False)             # 안전 높이
    release(); 그리퍼 열기(프리셋 폭 + 여유)
    depth, f = contact_down(descend_max_mm, contact_limit_n) # 접촉(용기 테두리/바닥) 또는 최대 깊이에서 정지
    → 겹친 용기는 위 용기 높이에서 멈춘다 (높이 적응)
    w = grip(preset.grip_width, preset.grip_force)           # 파지
    if |w - preset.grip_width| <= width_tol:  성공 → 상승 → return ok, w, i+1, (dx,dy)
    else: release(); safe_retreat()                          # 헛잡음(≤5 mm)·두 개 파지(폭 초과) → 다음 점
return EMPTY_ZONE (attempts = max_attempts)
```
- 탐색점은 구역 기준점 대비 오프셋 목록(`f1.yaml`). 처음엔 중심, 그다음 십자·대각 순.
- 폭 판정: `≤ 5 mm` 빈손, `> width + tol` 두 개 파지 또는 비스듬히 잡힘 → 둘 다 재탐색.
- 하강은 항상 힘 상한·최대 깊이·타임아웃과 함께(NFR-01).
- `zone_id`가 `SPONGE_BED_*`면 탐색점 1개(고정 위치 재파지).

**rack_place**: 팔레트 기준점 + 칸 오프셋 → 지정 각도(tilt) → 상공 → `force_on(z)` 하강 → `contact_down`으로 삽입력 감시 → 도달 시 `release` → 후퇴. 걸림(힘 > limit, 깊이 미달) → 후퇴 → `RACK_JAM`.

**tool**: 홀더 방향 고정, 픽업 후 폭 확인(범위 밖 → `TOOL_FAIL`), 반납 시 홀더 상공 → 하강 → 힘 접촉으로 바닥 확인 → release.

좌표는 전부 `f1.yaml`. 티칭: Dart Platform으로 자세 → 좌표 읽기 → YAML → ROS 재현 → 🚨 제어권 해제.

### 5.3 f2_node (민범진)
- `weigh`: `move_to(WEIGH)` → 0.5 s 정지 → `weigh(n)`. 툴 무게 사전 설정(빈 그리퍼).
- `leftover_loop`: `weigh` → 판정(임계 50 g, 미만은 OK) → `move_to(WASTE)` → `shake(WASTE)` → `weigh` … 최대 `max_rounds`.
- `shake`: J5/J6 관절 왕복(Move Periodic 또는 movej 왕복). 충돌 감지 오작동 시 진폭 축소(V-07).
- `dip`: 수조 상공 → `depth_mm` 하강 → `hold_s` → 상승.

### 5.4 f3_node (박진용)
- `seat`: 홈 상공 → `force_on(z, target=3)` 하강 → 접촉·깊이 판정. 미달·힘 이상이면 `periodic_search` 중 접촉 조건 감시 → 성공 / 한도 초과 → 후퇴 → `SEAT_FAIL`.
- `soap`: 툴 든 채 SOAP 수조 담금 `count`회.
- `wipe(BOWL)`: 홈 중심 상공 → `force_on(z, target_force, limit)` → r1→r2 나선 `turns`회 → `force_off` → 후퇴. 힘 로그 저장.
- `wipe(CUP)`: 컵 중심 상공 → 삽입 깊이까지 하강(힘 감시) → J6 ±rot_deg 회전 + Z 스트로크 `cycles` → 후퇴.

### 5.5 hmi_bridge (황인재) — 시스템 모니터
- 구조: FastAPI(uvicorn) + rclpy 스레드. rclpy는 별도 스레드에서 `spin`, 서비스 호출은 요청 스레드를 막지 않게 실행. WebSocket이 `/flow/state`·`/flow/event`를 브라우저에 밀어준다.
- SQLite(`db.py`): `/flow/event` 수신마다 `events` INSERT, 1 Hz로 `state_log` INSERT. `GET /api/history`가 최근 N건 반환.
- 화면 구성(강의 HMI 요소 반영):
  | 영역 | 내용 |
  |---|---|
  | 제어 | 시작 · 정지(소프트 E-STOP, 항상 보임, 붉은색) · 재개. 활성 조건은 §6 |
  | 상태 | 모드/단계(step), 현재 용기·구역, 진행률(done/target), 사이클 타임 |
  | 구역·팔레트 | 반납 구역 2칸(대기/처리중/완료), 팔레트 칸 6개(비어 있음/적재) |
  | 수량·소모품 | 그릇·컵 성공/격리, 수세미 사용·세제/헹굼 담금 바(임계 도달 시 색) |
  | 통신 | ROS 연결 점(초록/빨강, `/flow/state` 2 s 이상 없으면 빨강), 마지막 수신 시각 |
  | 오류·알람 | 마지막 코드 + 메시지, 오류 로그 목록(붉은 경고 우선) |
  | 이력 | 최근 이벤트 표(SQLite), 무게 전/후, 시도 횟수, 결과 |
- `fake_state_pub.py`: 시나리오(yaml)대로 정상·격리·오류·PAUSED를 발행 → 로봇·팀원 코드 없이 개발.

---

## 6. 휴먼 인터페이스
| 요소 | 동작 |
|---|---|
| 시작 | IDLE에서만 활성. plan 순서대로 처리 |
| 정지(소프트 E-STOP) | 현재 서비스 완료 후 PAUSED. 항상 표시 |
| 재개 | PAUSED에서 이전 상태로 |
| 격리 알림 | 격리 구역이 차면 경고, 비움 확인 버튼 |
| 팔레트 만재 | RACK_FULL → 교체 후 확인 버튼(resume) |
| 소모품 | 임계 도달 시 경고 |
| 연결 | 끊김 시 버튼 비활성 + 빨간 표시 |

## 7. 예외·오류 처리
| 코드 | 발생 | 처리 | 표시 |
|---|---|---|---|
| `EMPTY_ZONE` | 탐색 최대 횟수까지 파지 실패 | 구역 종료, 다음 구역 (SKIPPED 기록) | 정보 |
| `LEFTOVER_REMAIN` | 털기 후에도 임계 초과 | 격리 | 경고 |
| `SEAT_FAIL` | 탐색 한도 초과 | 격리 | 경고 |
| `TOOL_FAIL` | 툴 폭 범위 밖(툴 없음) | 재시도 1회 → 격리 | 경고 |
| `FORCE_LIMIT` / `TIMEOUT` | 닦기·삽입·하강 | 즉시 후퇴 → 재시도 1회 → 격리 | 경고 |
| `RACK_JAM` | 삽입 걸림 | 후퇴 → 재시도 1회 → 격리 | 경고 |
| `RACK_FULL` | 칸 소진 | PAUSED + 알림 | 오류 |
| `ROBOT_ERROR` | dsr 오류·충돌 정지 | PAUSED, 운영자 확인 후 resume | 오류 |
| 통신 끊김 | `/flow/state` 2 s 이상 없음 | HMI 버튼 비활성, 빨간 표시 | 오류 |
공통: 어떤 실패에서도 툴은 홀더에 반납, 로봇은 안전 높이. GRIP_FAIL은 f1 내부 재탐색으로 소화.

## 8. 위험요소·안전대책
| 위험(강의 "협동로봇 운용 시 주의사항" + 우리 셀) | 대책 |
|---|---|
| J3–J4, J1·J2–J5·J6 사이 신체 끼임 | 작업 반경 안에 사람 없음, 첫 실기 속도 20~30%, E-Stop에 손 닿는 사람 1명 상시 |
| 툴(수세미 툴·솔) 날카로운 부분, 볼트 풀림 | 툴 손잡이 모서리 처리, 매 실기 전 그리퍼·툴 볼트 확인 |
| 잘못된 그립·전원 차단으로 물체 낙하 | 파지 폭 판정, 들고 있을 때 저속, 낙하 구역에 사람 없음 |
| 접촉 동작 중 과도한 힘 | 힘 상한 + 후퇴 + 타임아웃(코드 리뷰에서 강제), 순응은 접촉 구간만 |
| 털기·물 털기 진폭 | 진폭·속도 YAML 상한, 충돌 감지 유지 |
| 비상정지 버튼 혼동 | 로봇 E-Stop 위치를 브리핑에서 매일 확인, HMI 정지는 소프트 정지임을 명시 |
| 안전 매개변수 무단 변경 | 안전 암호는 강사 관리, 충돌 감도·속도 한계 변경은 박진용(안전 담당) 승인 |
| 티치펜던트·ROS 동시 제어 | 티칭 후 제어권 해제 확인 후 브링업 |
| 액체 | 수조에 물 없음(모션만), 잔반 대용품은 고형물 |

## 9. 테스트·검증 계획
원칙: **구현 → 사전 검증(V) → L1 단위기능 테스트(녹화) → L2 단위기능 통합 → L3 노드 통합 → L4 전체 통합**. 이전 단계 통과 없이 다음 단계 금지. 날짜·담당·로봇 슬롯은 일정표(구글 드라이브 xlsx, §13)에서 관리하고 여기서는 **무엇을 어떻게 통과시키는가**만 정한다.


### 9.1 단계와 책임
| 단계 | 내용 | 주도 | 로봇 | 시기 |
|---|---|---|---|---|
| **L1 단위기능 테스트** | 각 기능 노드를 단독 리그에서 서비스별 10회, **녹화** | 각 담당 | 실기(F1·F2·F3) / 없음(F4·flow) | 9/20 |
| **L2 단위기능 통합** | 시나리오 단계 = 기능 2개 조합, flow_node로 호출 | 조합별 주도 | 실기 | 9/20 저녁~9/22 오전 |
| **L3 노드 통합** | 그릇 1·컵 1 end-to-end + 실제 HMI(PC-B) | 민범진 | 실기 | 9/22 |
| **L4 전체 통합** | 4개 연속 + 실패 주입 4종 + 측정 + 영상 + 동결 | 민범진 | 실기 | 9/23 |

### 9.2 사전 검증 (V) — "우리 하드웨어로 되는가"를 TC 전에 확인
| ID | 검증 | 담당 | 언제 | 기준 | 안 되면 |
|---|---|---|---|---|---|
| V-01 | 파지 폭으로 그릇·컵·빈손 3상태 구분 | S | 9/18 C | 세 값 간격 ≥ 6 mm | 핑거 패드 두께·프리셋 폭 조정 |
| V-02 | 하중 측정 정밀도(100/200 g 추 10회) | M | 9/18 C | ±20 g | 임계 100 g, 대용품 무겁게 |
| V-03 | 힘제어 켠 채 XY 나선 이동 | P | 9/19 B | 가능 | 닦기 = 순응 + 위치 2~3 mm 누르기 |
| V-04 | Move Periodic 탐색으로 홈 안착(2 mm 오프셋) | P | 9/19 B | 5회 중 4회 | 홈 여유 늘리기, 챔퍼 |
| V-05 | RG2 DO1/DO2 배선·DI1/DI2 완료 신호 | S | 9/18 C | 신호 왕복 | 폭 피드백만으로 판정 |
| V-06 | 팔레트 칸 삽입 각도·걸림 힘 판정 | S | 9/19 B | 걸림 시 힘 상승 식별 | 각도 삽입 → 수직 놓기 |
| V-07 | 털기 진폭·속도에서 충돌 감지 오작동 | M | 9/19 B | 10회 정지 0 | 진폭 축소, 관절 왕복 |
| V-08 | 툴 홀더 픽업·반납 10회 | S | 9/19 B | ≥9/10 | 홀더 깊이·방향 고정 보강 |
| V-09 | PC-A↔PC-B DDS 통신(DOMAIN 60) | H·M | 9/19 A | 토픽·서비스 왕복 | Discovery Server → 안 되면 PC 1대 |
| V-10 | 컵 안쪽 솔 삽입 깊이·충돌 | P | 9/19 B | 정지 0 | 스트로크 축소 |
| V-11 | 잔반 대용품 선정(구슬·쌀, ≥100 g, 털면 떨어짐) | 전원 | 9/18 | 확정 | — |
| V-12 | 스펀지 홈 치수 vs 용기 외경(여유 1~2 mm) | P | 9/18 C | 둘 다 들어감 | 재커팅 |
| V-13 | 브라우저 start → mock flow 반응 | H | 9/20 A | PAUSED/재개 반영 | 브리지 스레드 구조 수정 |
| V-14 | **겹친·어긋난 용기 탐색 파지** 성공률 | S | 9/20 A | ≥9/10, 낙하 0, 두 개 파지 0 | 탐색점 간격·하강 깊이·폭 허용치 조정 |

### 9.3 L1 단위기능 테스트 케이스
| TC | 기능 | SR | 리그(손으로 준비) | 절차 | 통과 기준 | 담당 |
|---|---|---|---|---|---|---|
| TC-01 | F1 탐색 파지 | SR-01·02 | 반납 구역에 그릇 2개를 **겹쳐/어긋나게** 배치, 컵 2개 동일, 빈 구역 1회 | `pick(RET_B)` 10회, `pick(RET_C)` 10회, 빈 구역 5회 | 각 ≥9/10, 빈 구역 `EMPTY_ZONE` 5/5, 낙하 0, 두 개 파지 0 | 한석형 |
| TC-02 | F1 툴·이송 | SR-03 | 툴 홀더 2종 | `tool PICK/RETURN` 각 10회, `move_to` 전 스테이션 | ≥9/10, 안전 높이 준수 | 한석형 |
| TC-09 | F1 팔레트 적재 | SR-12·13 | 팔레트 모형, 그릇·컵 | `rack_place` 6칸 각 5회, 걸림 유도 2회 | ≥9/10, 낙하 0, 걸림 → `RACK_JAM` 후퇴 | 한석형 |
| TC-03 | F2 무게 | SR-04 | 100 g·200 g 추 | `weigh` 각 10회 | ±20 g | 민범진 |
| TC-04 | F2 잔반 폐루프 | SR-05·06 | 대용품 용기 4, 빈 용기 4 | `leftover_loop` | 검출 100%, 오판 0, 재측정 로그 | 민범진 |
| TC-08 | F2 헹굼·물털기 | SR-11 | 수조(빈) | `dip` + `shake(RINSE)` 10회 | 충돌 정지 0 | 민범진 |
| TC-05 | F3 안착·탐색 | SR-07 | 스펀지 홈, 용기를 손으로 상공에 | `seat` 정위치 5 + 2 mm 오프셋 5 | ≥9/10, 한도 초과 → `SEAT_FAIL` | 박진용 |
| TC-06 | F3 그릇 닦기 | SR-08·10 | 홈에 그릇, 툴을 손으로 쥐여줌 | `soap(3)` → `wipe(BOWL)` 10회, 힘 로그 | 목표 ±2 N, 상한 초과 0, 강제 초과 시 후퇴 | 박진용 |
| TC-07 | F3 컵 닦기 | SR-09 | 홈에 컵, 솔 쥐여줌 | `wipe(CUP)` 10회 | 정상 10, 이탈 0 | 박진용 |
| TC-10 | flow 정책 | SR-14 | mock_f1_f3 + 실패 주입 | 코드 5종 주입 | 정책대로 재시도/격리/정지/재개, EMPTY_ZONE → 다음 구역 | 민범진 |
| TC-11 | HMI | SR-15 | fake_state_pub | 버튼 3종, 상태·연결·오류·이력 표시 | 서비스 호출 ≤1 s, 표시 지연 ≤1 s, 끊김 표시 | 황인재 |
| TC-12 | 기록 | SR-16 | mock 흐름 4개 | CSV·SQLite 확인 | 4행, 필드 누락 0 | 민범진·황인재 |

### 9.4 L2 단위기능 통합
| INT | 조합 | 시나리오 단계 | 절차 | 통과 기준 | 주도 |
|---|---|---|---|---|---|
| INT-12a | F1 + F2 | 탐색 파지 → 무게 → 털기 | `pick→move_to(WEIGH)→leftover_loop` 5회 | 5회 무개입, 판정 정확 | 민범진 |
| INT-13 | F1 + F3 | 놓기 → 안착 → 툴 → 세제 → 닦기 → 반납 | `place→seat→tool→soap→wipe→tool` 5회(그릇·컵) | 5회 무개입, 힘 로그 | 박진용 |
| INT-12b | F1 + F2 | 재파지 → 헹굼 → 물털기 → 적재 | `pick(BED)→dip→shake→rack_place` 5회 | 5회, 낙하 0 | 한석형 |
| INT-4 | flow + HMI | 시작·정지·재개 | mock에서 실제 HMI(PC-B) 연결 | 버튼 동작·상태 표시 | 황인재 |

### 9.5 L3 노드 통합
| INT | 내용 | 통과 기준 |
|---|---|---|
| INT-3a | 그릇 1개 end-to-end (실제 노드 3 + flow + HMI) | 무개입 3회 연속 |
| INT-3b | 컵 1개 end-to-end | 무개입 3회 연속 |

### 9.6 L4 전체 통합 (수락)
| INT | 내용 | 기준 |
|---|---|---|
| INT-4a | 시작 1회 → 그릇 2·컵 2 연속 | AC-1, AC-7 |
| INT-4b | 실패 주입: 빈 구역 / 잔반 과다 / 툴 미배치 / 팔레트 걸림 + 정지·재개 | AC-6 |
| INT-4c | 성공률·사이클 타임·잔반 검출률 측정 ×3 | AC-2~5 수치 |
| INT-4d | 시연 영상 원본 촬영 · `v1.0-demo` 태그 · 기능 동결 | 영상 확보 |

### 9.7 실패 주입 방법
| 주입 | 방법 |
|---|---|
| 빈 구역 | RET_C를 비워둠 → `EMPTY_ZONE` → 다음 구역/DONE |
| 잔반 과다 | 대용품 200 g → 털어도 남게 고정 → 격리 |
| 툴 미배치 | 수세미 툴을 홀더에서 빼둠 → `TOOL_FAIL` |
| 팔레트 걸림 | 칸에 방해물 → `RACK_JAM` → 후퇴·재시도 → 격리 |
| 정지·재개 | 실행 중 HMI 정지 → PAUSED → 재개 |

### 9.8 기록·녹화 규칙
- 시험 기록: `docs/test_logs/YYYYMMDD_TCxx.md` — 일시·담당·모드(Virtual/Real)·속도·결과표·로그 경로·영상 파일명·이슈 번호.
- **단위기능 테스트마다 녹화.** 영상 파일명 `YYYYMMDD_TCxx_기능_담당_시도N.mp4` (예: `20260920_TC01_pick_한석형_시도1.mp4`). 통합은 `YYYYMMDD_INTxx_…`. 영상은 저장소에 넣지 않고 드라이브·노션 링크를 기록에 적는다.
- 사전 검증(V)도 같은 양식으로 `YYYYMMDD_Vxx_…`.

### 9.9 범위 방어 (지연 시)
| 시점 | 조건 | 조치 |
|---|---|---|
| 9/18 저녁 | V-02 무게 정밀도 미달 | 잔반 임계 100 g, 대용품 무겁게 |
| 9/19 저녁 | V-03 힘제어 중 이동 불가 | 닦기를 "순응 + 위치 2~3 mm 누르기"로 |
| 9/19 저녁 | V-09 PC 통신 불가 | PC-A 1대로 통합 |
| 9/20 오전 | V-14 탐색 파지 미달 | 탐색점 축소(중심 + 십자 4), 용기 겹침 없이 어긋남만 시연 |
| 9/20 저녁 | UT-F1 적재 미통과 | 각도 삽입 → 수직 놓기 |
| 9/20 저녁 | UT-F3 컵 미통과 | 컵 닦기 도전 과제, 그릇만 MVP |
| 9/22 오전 | L2 하나라도 미통과 | L3를 9/23 오전으로, 4개 연속 → 2개(그릇1·컵1) |
| 9/23 이후 | 신규 기능 | 금지. 버그·파라미터만 |

## 10. 배포·실행
```bash
# PC-A
sod && sodreal                                     # 실기 브링업 (Virtual은 sodvir)
soc && ros2 launch rewash_bringup rewash.launch.py vel_scale:=0.3
# PC-B
soc && ros2 run f4_hmi hmi_bridge                  # http://<PC-B>:8000
# 로봇 없이 (한 PC)
soc && ros2 launch rewash_bringup rewash_mock.launch.py
```
런치 인자: `use_mock:=true|false`, `vel_scale:=0.3`. 첫 실기는 `vel_scale 0.2~0.3`.

## 11. 확인 중
| 항목 | 담당 | 기한 |
|---|---|---|
| `/dsr01/*` 서비스 정확한 이름·필드 | 한석형 | 9/19 |
| 탐색점 간격·최대 횟수(V-14) | 한석형 | 9/20 |
| 하중 측정 정밀도(V-02) | 민범진 | 9/18 |
| 힘제어 중 XY 이동(V-03) | 박진용 | 9/19 |
| PC 2대 통신(V-09) | 황인재·민범진 | 9/19 |
| 잔반 대용품(V-11) | 전원 | 9/18 |

## 12. 강사 요구 산출물 ↔ 이 문서
| 강사 산출물 | 위치 |
|---|---|
| 시스템 아키텍처 | §1 그림 + [images/system_architecture_pc.drawio](images/system_architecture_pc.drawio) |
| 네트워크 구성도 | §1.2 |
| 동작 순서도 | §4.1, §5.1 |
| 하드웨어 구성 | §2 |
| 토픽/서비스/액션 인터페이스 정의서 | §1.3 + [02_인터페이스_IRD.md](02_인터페이스_IRD.md) |
| ROS 2 노드 구조도 | §1.4, §3 |
| HMI 화면 구성 | §5.5, §6 |
| 예외/오류 리스트 및 처리 | §7 |
| 위험요소·안전대책 | §8 |
| Business Requirements | [01_요구사항_BR-SR.md](01_요구사항_BR-SR.md) |

## 13. 일정표 (정본: 구글 드라이브)
일정표 `rewash_개발일정_v2.xlsx`는 **구글 공유 드라이브**에서 팀이 함께 관리한다([팀 드라이브 폴더](https://drive.google.com/drive/folders/1t58F08_auBRa_q7c4KeNirLKR6CKa4hU?usp=sharing)). 시트: Time Line(팀별 색 간트) · 상세(산출물·완료기준) · 마일스톤·로봇 슬롯(강사 일정·마감·로봇 슬롯·제출 규칙) · 완료 목록 · 규칙 · 변경이력. 갱신은 PM(민범진)만. 저장소에는 사본을 두지 않는다.
