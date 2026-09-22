# PreWash-Cell — 경기장 다회용기 예비세척 · 식기세척기 팔레트 적재 자동화 셀

> ROKEY 9기 협동1 · **D그룹 2조** (한석형 팀장 · 민범진 · 박진용 · 황인재 PM)
> 두산 **M0609** + OnRobot **RG2** · ROS 2 Jazzy · Ubuntu 24.04 · **비전 없음**(판단은 파지 폭 · 하중 · 힘)
> 기능 동결 **9/23(수) 저녁** · 강사 시연 **9/29(월) 14:00** · 제출·발표 **9/30(화)**

경기장에서 반납된 **다회용 그릇·컵**을 로봇이 집어 **잔반을 털고, 안쪽을 닦고, 헹군 뒤 식기세척기 팔레트에 꽂는다.** 본세척은 식기세척기가 한다.

---

## 1. 무엇을 하는가 — 용기 1개가 도는 길

```
반납 구역 ──집기──▶ 저울 자세 ──무게──▶ (잔반 ≥ 50 g 이면 잔반통 위에서 기울여 버리고 다시 잰다)
        ──▶ 스펀지 홈에 놓기 ──▶ 수세미 툴 집기 → 세제 → 안쪽 닦기(힘 제어) → 툴 반납
        ──▶ 다시 집기 ──▶ 헹굼 담금 → 물 털기 ──▶ 식기세척기 팔레트 칸에 꽂기 ──▶ HOME
```
- **그릇**: 위 순서 전부. **컵**: 액체만 있다고 보고 **무게·잔반 버리기는 하지 않는다**(9/22 결정 E25). 나머지는 같다(컵은 솔 툴).
- 시연 계획: 그릇 2개 + 컵 2개, **정상 흐름을 끝까지 한 번**(예외 처리는 시연 목표에서 제외 · 결정 E28).
- 실패하면: 빈 구역 → 다음 구역 / 잔반이 계속 남음·안착 실패·삽입 걸림 → 격리 구역에 놓고 다음 용기 / 용기를 놓침·로봇 오류 → 멈추고 사람이 확인.

## 2. 구조 한눈에 (PC 2대 · 프로그램 2개)

| 어디 | 프로그램 | 하는 일 |
|---|---|---|
| **PC-A** (로봇 옆) | `flow_node` (`f2_sense_flow`) | 메인 프로그램. 위 순서대로 기능 함수를 차례로 부르고, 실패 정책·정지/재개/중단·기록(`records.csv`)을 맡는다. 로봇 명령은 이 프로그램의 메인 스레드에서만 나간다 |
| **PC-B** (화면) | `hmi_bridge` (`f4_hmi`) + 웹 화면 | 브라우저에서 시작·일시 정지·재개·중단 버튼, 단계 그림 카드, 팔레트 그림, 숫자 패널, 이력 |

기능은 **파이썬 함수 모듈**로 나뉘어 있고(노드가 아니다), `flow_node`가 순서대로 부른다.

| 모듈 | 담당 | 함수 | 한 줄 |
|---|---|---|---|
| `f1_handling` | 한석형 | `pick` `place` `move_to` `tool` `rack_place` | 집기 · 놓기 · 이동 · 툴 집기/반납 · 팔레트 꽂기 |
| `f2_sense_flow` | 민범진 | `weigh` `leftover_loop` `shake` `dip` + `flow.py`/`flow_node.py` | 무게 · 잔반 버리기 · 헹굼 담금 · 물 털기 + **흐름** |
| `f3_wipe` | 박진용 | `soap` `wipe_bowl` `wipe_cup` | 세제 · 그릇 닦기(나선 + 벽면 힘 제어) · 컵 닦기(솔 회전) |
| `f4_hmi` | 황인재 | `hmi_bridge` · `web/`(Next.js) · `fake_state_pub`(가짜 flow) | 운영 화면 |
| `cobot_common` | 4명 분담 | `bootstrap` `motion` `gripper` `weigh` `force` | 두산 API·그리퍼를 감싼 **공용 로봇 함수** — 두산 함수는 여기서만 부른다 |
| `cobot_api` · `cobot_msgs` | 황인재(정본) | 함수 약속(`contracts.py`) · 메시지 2개(`FlowState` `FlowEvent`) | 팀 계약 — 혼자 바꾸지 않는다 |
| `prewash_bringup` | 황인재 | `prewash.launch.py` · `prewash_mock.launch.py` | 실행 묶음 |

좌표·힘·횟수 같은 숫자는 코드가 아니라 `src/cobot_common/config/cell.yaml`(좌표·프리셋) · `params.yaml`(기능별 값)에 있다.

## 3. 지금까지 된 것 (9/22 저녁 기준)

검증 수준 표기: **자동** = pytest(로봇 없이) · **가상** = RViz 가상 로봇 · **실기** = 실제 로봇 · 🟡 = 아직 실기로 못 봄

| 영역 | 상태 | 확인 수준 | 근거 |
|---|---|---|---|
| 환경·좌표 | 4대 PC 환경 · 전 스테이션 좌표 티칭(HOME·저울·잔반통·반납 구역·스펀지 홈·툴 홀더·팔레트 6칸·격리) · 툴 무게·TCP 등록 | 실기 | `docs/test_logs/20260922_ENV-05_*` · `20260921_V-22_*`(재현 오차 0.24 mm) |
| 공용 로봇 함수 | 이동(비동기 + 즉시 정지) · 그리퍼(폭 판정) · 무게(힘센서 Fz) · 힘 제어·접촉 하강·순응 | 자동 + 실기 | Ctrl+C 즉시 정지 5/5(`20260922_V-26_*`) · 그리퍼 세션(`20260921_*그리퍼*`) |
| F1 집기·이송 | `move_to`·`place` · `tool`(수세미·솔 10/10) · `pick`·`rack_place`(한석형 실기 동선 → 함수로 이식) | 실기(tool) · 가상(pick·rack_place) 🟡 | `20260922_V-08_*` · `20260922_F1-02_F1-04_*` |
| F2 무게·털기 | 빈 그릇 기준값 −12 g(100 g 물건 오차 +3 g) · 잔반 버리기(기울여 털기 · 107 g 대용품 털림) · 헹굼 담금 3/3 · 컵 76 mm 파지 | 실기 · 물 털기 값 🟡 | `20260922_V-02_*` · `20260922_F2실기_*` · `20260921_저녁_F2실기_*` |
| F2 흐름(flow) | 상태 머신 · 실패 정책 · 정지/재개/중단 · 기록 · 컵 무게 건너뛰기 · 시작 전 툴·TCP 문지기 · 케이블 장력 경고 | 자동 + mock 기동 · 실기 🟡 | `20260921_UT-FLOW_*` · `20260920_V-20*` |
| F3 닦기 | 그릇 닦기(바닥 힘으로 찾기 → 나선 → 벽면 1.5 N) · 컵 세척(솔 ±90° 회전) · 세제 → 닦기 → 반납 **실기 1차 통합 성공** | 실기 | `20260920_V-03_*` · `20260921_V-10_*` · PR #72 |
| F4 화면 | 운영 화면(단계 카드 · 팔레트 그림 · 숫자 · 이력) · 버튼 · 가짜 flow 대본 5개 | 가짜 flow · 실제 연결 🟡 | PR #66 · `src/f4_hmi/README.md` |
| 안전 | 접촉 동작마다 힘 상한·후퇴·타임아웃 · 로봇 위치를 모르면 자동으로 안 움직임 · 툴·TCP 이름 확인 · 케이블 느슨하게 · 실기 끝나면 Ctrl+C 뒤 랜선 | 규칙 + 코드 | `AGENTS.md` §3 · `docs/00_현재상황_리마인드.md` §6 · `docs/troubleshooting/` |

**아직 남은 것(9/23)**: 안착 놓기(힘으로 홈에 앉히기) · 기능 3개를 한 흐름으로 잇는 통합(그릇 → 컵) · 화면과 실제 flow 연결 · 시연 영상.
자동 시험은 **441개**(9/22 20시 기준, 두 환경에서 통과). 시험 기록은 `docs/test_logs/`(29개), 결정은 `docs/meetings/20260919_결정기록_DSN-03.md`(E1~E28).

## 4. 직접 확인해 보는 명령 — 지금까지 된 것만

별칭(`sod` `soc` `cbc` `sodvir` `sodreal`)은 `docs/setup/M0609_환경설정.md`대로 `.bashrc`에 있다.
`sod` = 두산 드라이버 워크스페이스 source · `soc` = 두산 + 우리 워크스페이스 source · `cbc` = 우리 워크스페이스 빌드 + source.

### A. 로봇 없이 (아무 PC)
```bash
cbc                                            # 빌드 — "8 packages finished"
python3 -m pytest -q src                        # 자동 시험 441개 통과 (빌드한 뒤에 실행)
python3 src/f2_sense_flow/test/rig_int12.py check      # 함수 약속 · 빈 껍데기 여부 · 좌표 점검 (전부 "구현돼 있다" · OK)
python3 src/f2_sense_flow/test/rig_flow_once.py check  # 메인 흐름 설정(계획 · 컵 무게 건너뛰기 · 팔레트 순서) 확인
```
```bash
# 메인 프로그램 + 화면을 가짜 기능으로 (PC 1대) → 브라우저 http://localhost:8000 에서 시작·일시 정지·재개·중단
soc && ros2 launch prewash_bringup prewash_mock.launch.py
```
```bash
# 화면만: 가짜 flow 대본(normal · paused · isolate · error · empty_zone)으로 화면 반응 보기
soc && ros2 run f4_hmi hmi_bridge                  # 터미널 1 → http://localhost:8000
soc && ros2 run f4_hmi fake_state_pub normal       # 터미널 2 (실제 flow_node 와 동시에 띄우지 않는다)
```
화면(`web/out`)이 없으면 `/`에 시험 페이지가 뜬다 — 화면 PC(PC-B)에서 한 번 `cd src/f4_hmi/web && npm install && npm run build`.

### B. 가상 로봇 (RViz · 그리퍼·무게·힘은 없음 — 팔 동작·흐름만)
```bash
sod && sodvir                                   # 터미널 1: 가상 브링업 (이미 떠 있으면 다시 띄우지 않는다)
soc && python3 src/cobot_common/test/rig_coords.py --from 1     # 터미널 2: 전 좌표를 순서대로 방문
soc && python3 src/f2_sense_flow/test/rig_int12.py a --virtual --kind BOWL -n 3   # 집기 → 저울 → 잔반 처리 구간
soc && python3 src/prewash_bringup/test/rig_v20.py              # 정지 위치 확인
```

### C. 실제 로봇 🚨 담당자만 · 팀 확인 뒤 · 첫 실행은 저속
```bash
rosinfo                                          # RANGE=LOCALHOST 인지 (아니면 남의 로봇으로 명령이 간다)
sod && sodreal                                   # 터미널 1: 실기 브링업
# 움직이기 전에 툴·TCP 이름 확인 — 비어 있으면 움직이지 말고 펜던트에서 다시 고른다
ros2 service call /dsr01/dsr_controller2/tcp/get_current_tcp  dsr_msgs2/srv/GetCurrentTcp    # → GripperDA_v1
ros2 service call /dsr01/dsr_controller2/tool/get_current_tool dsr_msgs2/srv/GetCurrentTool  # → Tool Weight
```
```bash
soc && PREWASH_VEL_SCALE=0.3 python3 src/f1_handling/test/rig_f1.py tool --action CYCLE -n 10   # 툴 집기 → 반납 10회 (V-08)
soc && PREWASH_VEL_SCALE=0.3 python3 src/f2_sense_flow/test/rig_f2.py empty --kind BOWL -n 10    # 빈 그릇 기준값 (V-02)
soc && PREWASH_VEL_SCALE=0.3 python3 src/f3_wipe/test/rig_f3.py                                  # 그릇 닦기 (V-03)
soc && PREWASH_VEL_SCALE=0.3 python3 src/f2_sense_flow/test/rig_flow_once.py --kind BOWL --mock f3   # 메인 흐름으로 그릇 1개 (F3 만 가짜)
soc && ros2 launch prewash_bringup prewash.launch.py             # 메인 프로그램 (기본 vel_scale 0.3) — PC-B 는 ros2 run f4_hmi hmi_bridge
```
실기가 끝나면 **프로그램 터미널 Ctrl+C → 브링업 터미널 Ctrl+C → 그다음 랜선**. 급하면 Ctrl+C가 아니라 E-Stop.

## 5. 문서 지도

| 무엇이 궁금하면 | 여기 |
|---|---|
| 지금 무엇이 참인가(시나리오 · 분담 · 유효한 결정 · 안전 · 좌표 상태) | **[docs/00_현재상황_리마인드.md](docs/00_현재상황_리마인드.md)** |
| 요구사항 (BR · FR · NFR · SR · 추적표) | [docs/01_요구사항_BR-SR.md](docs/01_요구사항_BR-SR.md) |
| 함수·메시지 약속 (계약 정본) | [docs/02_인터페이스_IRD.md](docs/02_인터페이스_IRD.md) · [`src/cobot_api/cobot_api/contracts.py`](src/cobot_api/cobot_api/contracts.py) · [docs/interfaces/](docs/interfaces/) |
| 설계 (아키텍처 · 상태 머신 · YAML 양식 · 오류·안전 · §9 테스트 계획) | [docs/03_설계_SDD.md](docs/03_설계_SDD.md) |
| 결정 기록 (E1~E28 · 왜 그렇게 했나) | [docs/meetings/20260919_결정기록_DSN-03.md](docs/meetings/20260919_결정기록_DSN-03.md) |
| 시험 기록 (날짜_ID_내용_이름.md) | [docs/test_logs/](docs/test_logs/) |
| 트러블슈팅 (TS-01 두산 API 초기화 … TS-07 툴·TCP 설정 풀림) | [docs/troubleshooting/](docs/troubleshooting/) |
| PC 환경 설정 · 별칭 | [docs/setup/M0609_환경설정.md](docs/setup/M0609_환경설정.md) |
| 팀 규칙 (에이전트 공통) · 기여 규칙 (브랜치 · PR · 검토) | [AGENTS.md](AGENTS.md) · [CONTRIBUTING.md](CONTRIBUTING.md) |
| 일정표 (구글 시트 · 실시간 정본) | [일정표](https://docs.google.com/spreadsheets/d/1ikTAYTa8bgZofF_3RgP5jDoOipSZBPB1/edit?usp=sharing) · 터미널 `python3 tools/sched.py [담당\|taskID]` |
| 그림 (아키텍처 · 워크셀 · 노드 구조) | [docs/images/](docs/images/) |
| 팀원 온보딩 · 에이전트 프롬프트 | [docs/00_팀원_시작가이드.md](docs/00_팀원_시작가이드.md) · [docs/prompts/](docs/prompts/) |

## 6. 팀이 지키는 규칙 (요약)
1. `main` 직접 push 금지 — 브랜치 → PR → 자동 검사 + PM 검토(자동 시험 두 환경) → merge. PR 승인 코멘트에 **검증 수준(자동/가상/실기)** 을 항상 적는다.
2. 접촉 동작에는 힘 상한 · 후퇴 · 타임아웃. 로봇 위치를 모르면(정지 · 이동 미완) **자동으로 움직이지 않는다** — 사람이 복구.
3. 숫자는 YAML, 코드에 하드코딩 금지 · 두산 API는 `cobot_common` 안에서만.
4. 인터페이스(IRD)는 계약 — 혼자 바꾸지 않는다(4명 확인).
5. 단위 기능 테스트 먼저, 통합은 일정표의 통합 슬롯에서. 실기 시작 전 툴·TCP 이름 확인, 끝나면 Ctrl+C 뒤 랜선.

## 저장소 구조
```
rokey_pjt01_ws/            ← clone 폴더 = ROS 2 워크스페이스
├── README.md AGENTS.md CLAUDE.md CONTRIBUTING.md
├── docs/                  문서 · 인터페이스 정본 · 결정 기록 · 시험 기록 · 트러블슈팅 · 그림 · 프롬프트
├── src/                   ROS 2 패키지 8개 (cobot_api cobot_msgs cobot_common f1_handling f2_sense_flow f3_wipe f4_hmi prewash_bringup)
│   └── */test/            pytest(test_*.py) + 실기·가상 시험대(rig_*.py — pytest 는 모으지 않음)
├── tools/                 PR 자동 검사(pr_check.sh) · 일정표 조회(sched.py) · 일정표 생성(gen/)
└── build/ install/ log/   (.gitignore)
```
