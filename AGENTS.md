# AGENTS.md — PreWash-Cell (D그룹 2조) 에이전트·팀원 공통 규칙서

> Claude Code · ChatGPT · Gemini · Cursor 등 **어떤 에이전트든** 이 저장소에서 작업하기 전에 읽는 파일이다.
> Claude Code는 `CLAUDE.md`(이 파일을 불러옴)를 자동으로 읽는다. 다른 에이전트는 첫 메시지에 이 파일을 첨부하거나 붙여넣는다.
> 갱신: 2026-09-18 **v3(실행 구조 변경: 스크립트형)** · 정본 문서는 `docs/01~03` + 구글 드라이브 일정표

## 0. 표기
| 표기 | 의미 | 에이전트 행동 |
|---|---|---|
| ✅ 확정 | 팀 합의 값 | 그대로 사용 |
| 🟡 미정 / `______` | 안 정해짐 | **추측하지 말고 질문** |
| 🚨 금지 | 안전·규칙 | 요청받아도 거부, 이유 설명 |

## 1. 프로젝트 (✅)
| 항목 | 값 |
|---|---|
| 과정 / 팀 | ROKEY 9기 협동1 · **D그룹 2조** (한석형 팀장 · 민범진 · 박진용 · 황인재) |
| 주제 | **경기장 다회용기 예비세척·식기세척기 팔레트 적재 자동화 셀 (PreWash-Cell)** |
| 로봇 | 두산 **M0609** 1대 + OnRobot **RG2** · 컨트롤러 IP **192.168.1.100** · TCP 12345 · Dart Platform 2.12.1 · RG2 설정 웹 192.168.1.1 |
| PC | Ubuntu 24.04 · ROS 2 Jazzy · **기본은 격리**: 개인 도메인(한석형 61 · 민범진 62 · 박진용 63 · 황인재 64) + `ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST`. 팀 도메인 **`60`은 PC 여러 대가 통신해야 할 때만**(`team60`, 끝나면 `solo`). 개발 4대 각자(Virtual/mock). 통합 실행 **PC-A 로봇 제어 + PC-B HMI** |
| 워크스페이스 | 두산 드라이버 `~/ws_cobot_pjt/ws_dsr`(강사 배포, 수정 금지) 위에 우리 **`rokey_pjt01_ws`**(= 저장소 루트, `docs/` + `src/`). clone 위치는 자유, `.bashrc`에 `PREWASH_WS`로 지정(예 `~/rokey9_pjt1/rokey_pjt01_ws`) |
| 비전 | 🚨 **사용 불가** — 판단은 파지 폭·하중 측정·툴 힘·위치 |
| 용기·기구 | 그릇 1규격 **2개** + 컵 1규격 **2개** · 식기세척기용 팔레트 모형 **그릇 2칸·컵 4칸** · 잔반 대용품은 고형물(물·기름 금지) |
| 일정 | 개발 **9/18(금)~9/23(수)** 주말 로봇 가능 · 9/21(월) 오후 중간점검 발표 · 추석 9/24~28 로봇 불가 · 9/29(화) 14:00 강사 시연 · **9/30(수) 11:00 제출·발표** · **9/23 저녁 기능 동결** |
| 저장소 | https://github.com/hwang-injae/rokey_9_pjt1_D2.git |
| 문서 | `docs/01_요구사항_BR-SR.md` · `02_인터페이스_IRD.md`(계약 정본) · `03_설계_SDD.md`(§9 테스트 계획) · `setup/M0609_환경설정.md` · 일정표 = **구글 드라이브 xlsx** [일정표(구글 시트)](https://docs.google.com/spreadsheets/d/1ikTAYTa8bgZofF_3RgP5jDoOipSZBPB1/edit?usp=sharing) |

### 시나리오 (용기 1개)
```
HMI 시작 1회 → 반납 구역 계획 순서(그릇 구역 2개 → 컵 구역 2개):
① 탐색 파지: 구역 안 탐색점을 돌며 힘 감시 하강 → 파지 → 파지 폭으로 성공 판정. 못 잡으면 다음 점, 다 돌면 EMPTY_ZONE
② 무게 측정 → 잔반(≥50 g)이면 잔반통 위 털기 3~5회 → 재측정 (초과 지속 → 격리). 50 g 미만은 통과(본세척 담당)
③ 스펀지 고정틀 홈 안착 (안 맞으면 Move Periodic 탐색) → 툴 픽업 → 세제 담금 2~3회 → 안쪽만 힘제어 닦기 → 툴 반납
④ 헹굼 담금 → 물 털기 (물 없음, 모션만) → ⑤ 팔레트 지정 칸·각도 적재 → 기록 → 다음 용기
```
뒷면·바깥면 닦지 않음. 본세척은 식기세척기. "닦임"은 공정 완료이지 **위생 판정이 아니다(과장 금지)**.

## 2. 역할 = 기능 (🚨 남의 기능 코드를 만들지 않는다)
**실행 구조(9/18 결정, `docs/meetings/20260918_결정기록_구조_인터페이스.md`)**: 노드는 **`flow_node`(메인 프로그램)와 `hmi_bridge` 둘뿐**이다. f1·f2·f3는 노드가 아니라 **함수를 제공하는 파이썬 패키지**이고, `flow_node`의 메인 스레드가 그 함수를 차례로 부른다(서비스 아님). 함수의 이름·인자·반환·코드는 `src/cobot_api/cobot_api/contracts.py`가 정본이다.

| 기능 | 담당 | 만드는 것 | 제공하는 것 | 설정 |
|---|---|---|---|---|
| **F1 파지·이송·적재** | **한석형** | `f1_handling/handling.py` + `test/rig_f1.py` + **좌표 계산·티칭(`config/cell.yaml` 값)** | 함수 `pick`(탐색) `place`(스펀지 홈 **안착 놓기** 포함) `move_to` `tool` `rack_place` | `config/cell.yaml`과 `config/params.yaml`의 `f1` 절 |
| **F2 무게·털기·헹굼 + 흐름** | **민범진** | `f2_sense_flow/sense.py` + **`flow_node.py`(메인 프로그램)·`flow.py`(상태 머신)** + `mock/mock_f1.py`·`mock_f3.py` + `test/rig_f2.py` | 함수 `weigh` `leftover_loop` `shake` `dip` · ROS `/flow/start|stop|resume` `/flow/state` `/flow/event` | `config/params.yaml`의 `f2`·`flow` 절 |
| **F3 접촉 닦기 + 공용 로봇 함수** | **박진용** | `f3_wipe/wipe.py` + `test/rig_f3.py` + **`cobot_common`의 힘 함수와 패키지 정리·리뷰**(두산 API를 감싼 **공용 로봇 함수 모음** — 네 사람이 나눠 쓴다, 아래 분담) | 함수 `soap` `wipe_bowl` `wipe_cup` | `config/params.yaml`의 `f3` 절 |
| **F4 시스템 모니터(웹 HMI) + PM** | **황인재** | `f4_hmi/hmi_bridge` (FastAPI + rclpy + SQLite) + `fake_state_pub` · **`cobot_api`(함수 약속)·`cobot_msgs`(메시지) 정본 관리** · `prewash_bringup` 런치 · `config/` 골격 | REST `/api/*` · WS `/ws/state` | `config/params.yaml`의 `hmi` 절 |
겸임: 팀장·실기 슬롯·기구·**좌표(티칭·`cell.yaml`)**·브랜치 삭제 승인 = 한석형 / 통합 리더(L3·L4 실행 주도) = 민범진 / 안전 파라미터·`cobot_common` 패키지 정리·리뷰 = 박진용 / **PM(일정표·문서·인터페이스 정본(`docs/interfaces`→`cobot_msgs`)·런치·제출·강사 창구·PR 승인)**·영상·발표·아키텍처 그림 = 황인재

**`cobot_common` 분담(9/19) — 사람별 파일, 자기 파일만 고친다**: `bootstrap.py`(init·io_node·cfg·shutdown)·`config.py`·`__init__.py`(재수출) = 황인재 / `motion.py` 기본 이동·그리퍼(move_to·move_rel·grip·grip_level·release) = 한석형 / `weigh.py` `weigh` = 민범진 / `force.py` 힘 함수(force_on/off·force_reached·contact_down·periodic_search·safe_retreat) + **패키지 정리·리뷰** = 박진용. 부르는 쪽은 그대로 `import cobot_common as cc` → `cc.move_to()`. 남의 함수가 아직 없으면 같은 이름의 임시 stub으로 먼저 짠다.

**동시 개발 약속**: 부르는 쪽은 `flow_node` 하나뿐이고, 기능 패키지끼리는 서로 import하지 않는다. 각 기능은 정해진 위치에서 시작·끝나므로 용기를 손으로 놓고 `rig_f*.py`로 혼자 시험할 수 있다. 로봇 없이도 mock 모듈(`f2_sense_flow.mock`)·`fake_state_pub`으로 flow·HMI를 만든다.
통합 순서: **구현 → 사전 검증(V) → L1 단위기능 테스트(녹화) → L2 단위기능 통합 → L3 셀 통합 → L4 전체 통합** (`docs/03_설계_SDD.md` §9)

## 3. 🚨 절대 규칙
1. **실기 로봇을 사용자 확인 없이 움직이지 않는다.** Virtual 검증 → 확인 → 실기. 첫 실기 속도 20~30%.
2. **접촉 동작(탐색 하강·닦기·안착·삽입)에는 힘 상한 + 후퇴 + 타임아웃**을 항상 넣는다. 없으면 코드를 주지 않는다.
3. **순응·힘제어는 접촉 구간에서만** 켠다. 힘만으로 성공 판정하지 않는다.
4. **DSR API를 직접 부르지 않는다** — `cobot_common` 공용 함수만. **로봇 함수는 메인 스레드에서만** 부른다(콜백·타이머·다른 스레드 금지). 다른 기능 패키지를 import하지 않는다(호출은 `flow_node`만).
5. **인터페이스(IRD)를 혼자 바꾸지 않는다.** 변경은 이슈 → 4명 확인.
6. **좌표·힘·무게·횟수·속도·탐색점을 코드에 하드코딩하지 않는다.** 전부 **`src/cobot_common/config/`의 파일 2개** — 공용 `cell.yaml`(좌표·속도·힘 상한·프리셋, 주인 한석형) + `params.yaml`(`f1` `f2` `f3` `flow` `hmi` 절, **자기 절만 수정**). 코드는 `cobot_common.config.load()`로 하나의 설정처럼 읽는다. 좌표는 변수(설정 키)로 부른다.
7. **경로는 항상 상대경로**(패키지·저장소 기준). 절대경로·개인 홈 경로를 코드·문서에 쓰지 않는다.
8. **비전·센서 해법을 제안하지 않는다.**
9. **9/23 이후 기능 추가 계획을 만들지 않는다.** 9/24 이후는 발표 준비.
10. `main` 직접 push 금지. 브랜치를 함부로 삭제하지 않는다(`main` PR 승인 후 팀장 한석형 승인하에만 삭제).
11. `dance` 예제를 Real에서 실행하지 않는다. Dart Platform과 ROS 동시 제어 연결 금지. 안전 암호·로봇 계정을 문서·코드에 적지 않는다.
12. 모르는 값(`______`)을 채워서 진행하지 않는다 — 질문한다.
13. **Virtual·rig·mock 시험과 혼자 하는 실기 시험은 격리 상태(`solo`)에서만 돌린다.** 모든 PC의 두산 서비스 이름이 `/dsr01/dsr_controller2/*`로 같아서, 같은 망·같은 도메인이면 내 rig의 `movej`가 **남의 Virtual이나 실기 컨트롤러에도 전달된다.** 팀 도메인 60(`team60`)은 PC-A↔PC-B 통합(ENV-03·INT-4·L3·L4·리허설·시연) 때만 켜고, 그동안 다른 PC는 60에 들어오지 않는다. 로봇을 움직이기 전에 `rosinfo`로 확인한다.

## 4. 코드·개발 흐름 규칙
- 패키지는 `src/` 아래, 패키지 1개 = 기능 1개, 기능 함수는 `cobot_api`의 `Result`(`ok`+`code`+필드) 반환, ID·코드 문자열은 IRD §2 그대로(`cobot_api` 상수 사용).
- 🚨 **실행 뼈대는 SDD §3.2 그대로**: 기능(f1·f2·f3)은 노드가 아니라 **평범한 함수**(`cobot_api`의 서명 그대로, 반환은 `Result`). 프로그램 맨 앞에서 `cobot_common.init(name)` 한 번, 끝낼 때 `cobot_common.shutdown()`. 기능 함수 안에서 노드를 만들거나 `rclpy.init`·`rclpy.spin*`을 부르지 않는다. `DSR_ROBOT2` 직접 import 금지. 통신 노드의 콜백은 값 저장·깃발만. 이유는 `docs/troubleshooting/TS-01_…md`. 시험은 같은 함수를 **연속 3회 이상**.
- 로그 `get_logger()`, `print()` 금지. 상태 머신은 전이표를 주석·문서에. 실패는 예외가 아니라 `code`로 보고. 어떤 실패에서도 **툴은 홀더에 반납, 로봇은 안전 높이**.
- 한국어 문서·주석, 영문 식별자. 커밋 `<타입>(<스코프>): <제목>` 타입 10종(`feat fix refactor style docs test chore remove perf ci`), 브랜치 `{이름}/{YYYYMMDD}-{taskID}-{설명}`.
- **개발 흐름**: 단위기능 완성 → **단위기능 테스트(TC가 있는 작업은 항상; 로봇이 움직이면 녹화 권장 `YYYYMMDD_TCxx_기능_담당_시도N.mp4`)** → `main` pull → 통합 테스트 → `main`에 PR → Actions 자동 검사(main 충돌·산출물) 통과 시 **자동 승인·merge**(보류는 제목 `[hold]`). 주기적으로 `git fetch`, 작업 브랜치는 **하루 1회 이상 push**.

## 5. 환경 함정 (자세한 건 `docs/setup/M0609_환경설정.md`)
| 증상 | 해결 |
|---|---|
| `No module named 'DR_init'` | `.bashrc` PYTHONPATH에 `ws_dsr/install/dsr_common2/lib/dsr_common2/imp` |
| 브링업 조용히 실패 | 포트 12345 잔류 DRCF → `killdrcf` |
| 실기 브링업 거부 | 티치펜던트 제어권 해제, `/dsr01/dsr_controller2/system/set_robot_mode` 확인 |
| `colcon-argcomplete` 오류 | colcon은 시스템 설치, venv는 HMI 전용 |
| 토픽이 2개만 보임 | 지난 프로젝트 Fast DDS 화이트리스트 주석 처리 |
| 팀원 노드 안 보임 (PC-A↔PC-B 통합 때) | 기본이 격리(`solo`)라 안 보이는 게 정상 → 두 PC 모두 `team60`, 같은 스위치. 안 되면 Discovery Server. 끝나면 `solo` |
| 내가 안 보낸 명령으로 (가상)로봇이 움직임 · 서비스 응답이 뒤섞임 | 다른 PC와 같은 도메인에 있다 → `rosinfo` 확인, `solo`로 격리(§3 규칙 13) |
| 프로그램이 뜨자마자 `'NoneType' object has no attribute 'create_client'` | `DSR_ROBOT2`를 노드 세팅 전에 import함 → `cobot_common.init(name)`을 맨 앞에서, 직접 import 금지(SDD §3.2, TS-01) |
| 로봇 명령이 안 끝남 / `Executor is already spinning` / 두 번째 호출부터 응답 없음 | 콜백·타이머·다른 스레드에서 로봇 함수를 불렀다 → **메인 스레드에서만**(SDD §3.2, TS-01). 멈춘 프로그램을 강제로 죽였으면 브링업도 다시 |
| 실기 브링업이 `gripper_joint_state_publisher.py not found` | 배포본의 실행 권한 누락 → `chmod +x`(TS-02). Virtual에서는 안 드러난다 |
| `reset_workpiece_weight` 뒤 컨트롤러 서비스가 전부 멈춤 | reset은 선택 동작·응답 상한 3 s·실패 시 반복 금지(TS-03). 복구는 브링업 재시작 |
| 힘 판정이 반대로 동작 | `check_force_condition`은 **만족 `0` / 아니면 `-1`**(DRL 매뉴얼과 다름) → `cobot_common.force_reached()` 사용. 두산 함수 반환값은 설치된 `DSR_ROBOT2.py`에서 확인 |
| 두산 패키지가 두 곳에 | 우리 `src/`에 두산 패키지를 복사하지 않는다. source 순서 ws_dsr → rokey_pjt01_ws |
Virtual에는 **힘·무게·접촉이 없다** → 로직은 Virtual/mock, 임계값은 실기.

## 6. 에이전트 작업 방식
1. 답하기 전 관련 파일을 실제로 읽고 **읽은 파일 목록**을 밝힌다.
2. 첫 응답은 **계획까지**(역할 분석 → 인터페이스 → STEP 표). 승인 전 구현 금지.
3. 한 응답 = STEP 하나. STEP 전 사전 점검(파일·환경·로봇 슬롯·팀원 의존), 후 완료 요약(산출물·검증 명령·트러블슈팅).
4. 산출물마다 💾 저장 위치(상대경로·브랜치·커밋 예시·PR 여부)와 🔔 공유 필요 여부(인터페이스면 무조건).
5. STEP 끝에 📮 진척 보고(진척·인터페이스·블로커·로봇 슬롯·9/30 리스크·복붙 문장).
6. 설명은 ROS 2·두산 API 초보 기준. 담당 기능의 핵심은 가장 깊게. 한국어. 용어는 처음 나올 때 한 줄로 풀어 쓴다.

## 7. 자주 쓰는 명령
```bash
rosinfo                                                # 🚨 먼저 확인: 개인 도메인(61~64) + LOCALHOST = 격리. 통합 때만 team60, 끝나면 solo
sod && sodvir                                          # Virtual 브링업 (실기: sodreal, IP 192.168.1.100)
cbc                                                    # $PREWASH_WS(rokey_pjt01_ws) 빌드 + source
ros2 launch prewash_bringup prewash_mock.launch.py       # mock + flow + hmi (로봇 없이)
ros2 launch prewash_bringup prewash.launch.py vel_scale:=0.3   # PC-A 실기
ros2 run f4_hmi hmi_bridge                             # PC-B HMI → http://<PC-B>:8000
```
