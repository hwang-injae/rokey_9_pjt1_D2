# PreWash-Cell — 경기장 다회용기 예비세척·식기세척기 팔레트 적재 자동화 셀

> ROKEY 9기 협동1 · **D그룹 2조** (한석형 팀장 · 민범진 · 박진용 · 황인재)
> 두산 **M0609** + OnRobot **RG2** · ROS 2 Jazzy · 비전 없음 · 발표 **2026-09-30(수)**

반납 구역에 놓인(겹쳐 있어도 되는) 그릇·컵을 **탐색하며 집어**, **무게로 잔반을 판정·털어내고**, **스펀지 고정틀에서 안쪽을 닦고**, **헹굼 모션 후 식기세척기용 팔레트의 정해진 칸·각도로 적재**한다. 본세척은 식기세척기가 한다.

## 처음 들어온 사람은 이 순서로
0. **[docs/00_팀원_시작가이드.md](docs/00_팀원_시작가이드.md)** — GitHub 토큰·clone·환경·에이전트 연결·매일 git 흐름을 순서대로 (GitHub 처음이면 여기부터)
1. **[AGENTS.md](AGENTS.md)** — 확정값·시나리오·역할·절대 규칙. 에이전트에게도 이 파일을 준다
2. **[docs/02_인터페이스_IRD.md](docs/02_인터페이스_IRD.md)** — 노드 간 계약 (혼자 바꾸지 않는다)
3. **[docs/setup/M0609_환경설정.md](docs/setup/M0609_환경설정.md)** — 내 PC 환경 (GPU 유무 공통)
4. **[docs/prompts/](docs/prompts/)** — 내 프롬프트 (아래 "에이전트 사용법")
5. **[CONTRIBUTING.md](CONTRIBUTING.md)** — 브랜치·커밋·PR·개발 흐름·안전

## 문서 (3개 + 일정표 + 보조)
| 파일 | 내용 |
|---|---|
| [docs/00_팀원_시작가이드.md](docs/00_팀원_시작가이드.md) | 팀원 온보딩: 토큰·clone·환경·에이전트 연결·git 흐름·자주 나는 문제 |
| [docs/01_요구사항_BR-SR.md](docs/01_요구사항_BR-SR.md) | 비즈니스·시스템 요구 (BR·FR·NFR·SR·IR·TR·AC·평가기준 대응·추적표) |
| [docs/02_인터페이스_IRD.md](docs/02_인터페이스_IRD.md) + [docs/interfaces/](docs/interfaces/) | 인터페이스 정본 (srv·msg 파일) |
| [docs/03_설계_SDD.md](docs/03_설계_SDD.md) | 설계 (PC 2대 아키텍처·네트워크·통신 표·노드·상태 머신·YAML·오류·안전) + **§9 테스트 계획**(사전 검증 V·TC·INT·실패 주입·녹화 규칙·범위 방어) + 강사 산출물 매핑 |
| **일정표 (구글 시트, 실시간 정본)** — 터미널에서 `python3 tools/sched.py [담당|taskID]` 로 조회 — [일정표(구글 시트)](https://docs.google.com/spreadsheets/d/1ikTAYTa8bgZofF_3RgP5jDoOipSZBPB1/edit?usp=sharing) | 강사 일정·마일스톤·로봇 슬롯·작업 목록(색 간트)·규칙·변경이력. 저장소에는 두지 않는다 |
| [docs/images/](docs/images/) | 시스템 아키텍처(PC 단위, `.svg` + 편집용 `.drawio`) · 설계도 · 워크셀 |
| [docs/setup/M0609_환경설정.md](docs/setup/M0609_환경설정.md) | PC 환경 설정 (ws_dsr + rokey_pjt01_ws, 별칭, 함정) |
| [docs/meetings/](docs/meetings/) | 회의록 (결정·미결·후속 작업) |
| [docs/ref/](docs/ref/) | 법규·산업 조사, 브리핑 자료, 팀원 제안서, (일정 양식은 드라이브 일정표에 반영됨) |
| `class_doc/` | 협동로봇 강의 PDF |

## 역할 (기능 단위)
| 기능 | 담당 | 노드 |
|---|---|---|
| F1 파지·이송·적재 + 좌표 | 한석형 | `f1_handling` · 좌표 계산·티칭(`config/cell.yaml`) |
| F2 무게·털기·헹굼 + 흐름 | 민범진 | `f2_sense_flow` (`f2_node`, `flow_node`, `mock_f1_f3`) · 통합 리더 |
| F3 접촉 닦기 + 공용 로봇 함수 | 박진용 | `f3_wipe` · **`cobot_common`**(이동·그리퍼·무게·힘 함수 + 설정 로더) · 안전 파라미터 |
| F4 시스템 모니터(웹 HMI) + **PM** | 황인재 | `f4_hmi` (FastAPI + SQLite) · `cobot_msgs` 정본 · `prewash_bringup` · 일정표·문서 |

## 에이전트 사용법
| 담당 | 프롬프트 |
|---|---|
| 한석형 | [docs/prompts/F1_한석형_프롬프트.md](docs/prompts/F1_한석형_프롬프트.md) |
| 민범진 | [docs/prompts/F2_민범진_프롬프트.md](docs/prompts/F2_민범진_프롬프트.md) |
| 박진용 | [docs/prompts/F3_박진용_프롬프트.md](docs/prompts/F3_박진용_프롬프트.md) |
| 황인재 | [docs/prompts/F4_황인재_프롬프트.md](docs/prompts/F4_황인재_프롬프트.md) |

| 에이전트 | 방법 |
|---|---|
| **Claude Code** | 저장소(clone한 `rokey_pjt01_ws` 폴더)를 열면 `CLAUDE.md` → `AGENTS.md`를 자동으로 읽는다. 슬래시 명령: **`/start 이름`**(온보딩 코치) · **`/f1`~`/f4`**(내 프롬프트로 작업 시작) · **`/daily taskID 설명`**(아침 브랜치) · **`/wrap`**(저녁 커밋·push·PR 초안) · `/pr-review 번호`(황인재용) |
| **ChatGPT / Gemini(웹)** | 온보딩: `docs/prompts/00_온보딩_코치_프롬프트.md` 전문 + 가이드·환경설정·AGENTS 첨부. 작업: 내 프롬프트 전문 + `AGENTS.md`·`docs/01~03` 첨부(안 되면 프롬프트 부록 A). |
| **Cursor / Codex / Gemini CLI** | 저장소 루트의 `AGENTS.md`를 자동 인식(도구에 따라 `.cursorrules`·`GEMINI.md`로 복사). 프롬프트는 채팅에 붙여넣기. |

프롬프트마다 맨 위에 **내 도구별 사용법**과 **§0 시작 순서**(git 설정 → 토큰 → clone → PC 환경 → 문서 요약 → 첫 PR → 작업)가 들어 있어, 문서를 전부 주고 프롬프트를 붙여넣으면 에이전트가 순서대로 끌고 간다. `______`(이름·수준·GitHub ID·PC)는 비워 두면 에이전트가 묻는다.

## 저장소 구조
```
rokey_pjt01_ws/        ← clone 폴더 (= 우리 ROS 2 워크스페이스). 위치는 자유, `.bashrc`의 PREWASH_WS 로 지정
├── AGENTS.md CLAUDE.md README.md CONTRIBUTING.md
├── docs/              문서·인터페이스 정본·이미지·프롬프트·환경설정
├── src/               우리 ROS 2 패키지 7개 (cobot_msgs cobot_common f1_handling f2_sense_flow f3_wipe f4_hmi prewash_bringup)
└── build/ install/ log/   (.gitignore)
```

## 🚨 5개만 기억
1. `main` 직접 push 금지 — PR + 황인재 승인(에이전트가 규칙·main 병합·통합 테스트를 먼저 검토). 브랜치 삭제는 팀장 승인
2. Virtual에서 통과한 것만 실기로, 첫 실기 저속. 접촉 동작엔 힘 상한·후퇴·타임아웃
3. 힘·좌표·횟수·탐색점은 YAML — 코드에 숫자 금지, 경로는 상대경로
4. 인터페이스(IRD)는 계약 — 혼자 바꾸지 않는다
5. 구현 → 단위 테스트(녹화) → main pull → 통합 → PR. **9/23 동결**
