# CONTRIBUTING — D-2팀 협업 규칙

> 저장소: https://github.com/hwang-injae/rokey_9_pjt1_D2 · 팀 노션: [D그룹 2조 협동1](https://app.notion.com/p/D-2-1-f336d4401b6782c49a4a81e00842a32b)
> 로봇: 두산 M0609 + OnRobot RG2 · ROS 2 Jazzy · `ROS_DOMAIN_ID=60` · **최종 발표 2026-09-30(수)**
>
> 4명이 2주 안에 로봇 하나를 공유하며 만드는 프로젝트다. 규칙의 목적은 ① 남의 작업을 덮어쓰지 않기 ② 인터페이스 깨지지 않기 ③ 발표 전날 통합 지옥 피하기 세 가지다.

---

## 0. 30초 요약

```bash
git fetch origin && git checkout main && git pull origin main   # ① 항상 최신 main에서 시작
git checkout -b seokhyung/20260919-F1-02-pick-search             # ② 브랜치 {이름}/{YYYYMMDD}-{taskID}-{설명}
# 작업 → 단위기능 테스트(녹화) …
git add <바꾼 파일만>
git commit -m "feat(f1): pick 탐색 파지 — 접촉 하강·폭 판정·재탐색"
git push -u origin seokhyung/20260919-F1-02-pick-search          # ③ 하루 1회 이상 push
# ④ main pull → 통합 테스트 → GitHub에서 PR (Reviewer: hwang-injae) → 에이전트 검토 → 황인재 승인 → Squash merge
```

**🚨 `main`에 직접 push 금지. 예외 없음.**

---

## 1. 개발 흐름 (단위기능 → 통합)
```
단위기능 구현 → 단위기능 테스트(항상, 녹화) → git fetch + main pull(merge) → 통합 테스트 → main에 PR → 1명 승인 → merge
```
- **단위기능 테스트는 건너뛰지 않는다.** 기준은 [docs/03_설계_SDD.md](docs/03_설계_SDD.md) §9.3 (TC-xx). 결과는 `docs/test_logs/YYYYMMDD_TCxx.md`.
- **녹화 필수.** 영상 파일명 `YYYYMMDD_TCxx_기능_담당_시도N.mp4` (예: `20260920_TC01_pick_한석형_시도1.mp4`). 통합은 `INTxx`, 사전 검증은 `Vxx`. 영상은 저장소에 넣지 않고 드라이브·노션 링크를 기록에 적는다.
- 통합 테스트 전에 반드시 최신 `main`을 내 브랜치에 합친다(`git merge main`). 통합이 깨지면 PR을 올리지 않는다.
- `git fetch`는 수시로, 작업 브랜치 push는 **하루 1회 이상**(퇴근 전). 로컬에만 있는 코드는 없는 코드다.

## 2. 브랜치 규칙

### 이름 형식 (엄수)
```
{이름}/{YYYYMMDD}-{taskID}-{간단설명}
```
- 전부 **영문 kebab-case**. taskID는 [구글 드라이브 일정표](https://drive.google.com/drive/folders/1t58F08_auBRa_q7c4KeNirLKR6CKa4hU?usp=sharing)의 ID 열(`F1-02`, `INT-12a` …).
- 예: `seokhyung/20260919-F1-02-pick-search`, `beomjin/20260920-FLOW-01-state-machine`, `injae/20260918-F4-01-fake-pub`

### 고정 브랜치
| 브랜치 | 용도 | 규칙 |
|---|---|---|
| `main` | 언제나 **동작하는** 상태 | PR + **황인재 승인**(에이전트 사전 검토: 규칙·main 병합·통합 테스트 확인)이면 merge. 직접 push 금지(GitHub 규칙으로 차단) |
| `integration` (선택) | L2~L4 통합 시험용 | 9/20 저녁부터 사용. 여기서 통과한 것만 `main` PR |

### 브랜치 삭제
- **브랜치를 함부로 삭제하지 않는다.** `main`에 PR이 merge된 브랜치만, **팀장(한석형) 승인 후** 삭제한다. 남의 브랜치는 절대 삭제하지 않는다.
- 하루~이틀 안에 PR을 올린다. 작업이 커지면 쪼갠다.

## 3. 커밋 규칙

### 형식 (Conventional Commits, 본문 한국어)
```
<타입>(<스코프>): <제목(명령조 요약)>

[본문: 무엇을, 왜 바꿨는지]

[꼬리말: Resolves #123]
```

### 타입 (이 10개만)
| 태그 | 설명 |
|---|---|
| `feat` | 새로운 기능 추가 |
| `fix` | 버그 수정 |
| `refactor` | 기능 변경 없는 코드 구조 개선 |
| `style` | 코드 포맷팅 |
| `docs` | 문서 추가·수정 |
| `test` | 테스트 코드·시험 기록 |
| `chore` | 빌드 스크립트·패키지 설정·잡무 |
| `remove` | 코드·파일 삭제 |
| `perf` | 성능 개선 |
| `ci` | CI/CD 설정 |

> 🚨 좌표·임계값 등 YAML 변경은 `chore`가 아니라 `fix`(동작 교정) 또는 `feat`(새 조건)로 쓰고, 본문에 "무엇을 왜 바꿨는지"를 남긴다. 임계값은 값보다 이유가 자산이다.

### 스코프
`f1`(파지·이송·적재) · `f2`(무게·털기·헹굼) · `flow`(흐름·정책·기록) · `f3`(닦기) · `f4`(HMI) · `common`(공용 로봇 함수) · `msgs` · `cell`(기구) · `bringup` · `docs` · `setup`

### 예시
```
feat(f1): pick 탐색 파지 — 탐색점 순회·접촉 하강·폭 판정·EMPTY_ZONE
fix(f3): seat 탐색 한도 초과 시 SEAT_FAIL 미반환 수정
fix(flow): EMPTY_ZONE 후 다음 구역으로 넘어가지 않는 문제 수정
docs(setup): PYTHONPATH 누락 시 DR_init import 오류 함정 추가
```

### 🚨 커밋하지 말아야 할 것
`build/ install/ log/`, `__pycache__/`, `.venv/`, `*.bag`, `*.mp4`, `rewash.db`, 개인 `.bashrc`, **로봇 계정·안전 암호**(공개 저장소다). IP 192.168.1.100은 문서에 적어도 된다.

## 4. Pull Request 규칙

### 올리기 전 체크
- [ ] `colcon build` 통과
- [ ] **단위기능 테스트 통과 + 녹화** (파일명 규칙)
- [ ] **최신 `main`을 합치고 통합 테스트**를 했다
- [ ] Virtual 모드에서 동작 확인(실기 전 필수)
- [ ] 수치·좌표를 코드에 하드코딩하지 않았다(YAML), 경로는 상대경로
- [ ] 인터페이스(IRD·`docs/interfaces/`)를 임의로 바꾸지 않았다
- [ ] 빌드 산출물이 diff에 없다

### 제목·본문
제목은 커밋 규칙과 같다(`feat(f1): …`). 본문은 `.github/PULL_REQUEST_TEMPLATE.md`가 채워진다. **"실기 영향" 칸을 비우지 말 것.** 단위 테스트 영상 파일명을 적는다.

### 4.1 승인 전 자동 검토 (에이전트 — `tools/pr_check.sh <PR번호>` + `/pr-review`)
| 검토 항목 | 통과 기준 | 실패 시 |
|---|---|---|
| main 병합 | `origin/main` 최신이 PR 브랜치에 포함됨(`git merge origin/main` 후 push) | 거절: "main 병합 후 다시" |
| 통합 테스트 | PR 본문에 통합 테스트 결과(mock 또는 실기)와 단위 테스트 영상 파일명, `docs/test_logs/` 기록 | 거절 |
| 브랜치·커밋 | `{이름}/{YYYYMMDD}-{taskID}-{설명}`, 타입 10종 | 거절(이름은 새 브랜치로) |
| 산출물 | `build/ install/ log/ *.mp4 rewash.db` 없음 | 거절 |
| 하드코딩·경로 | 코드에 좌표·힘·횟수 숫자 없음(YAML), 절대경로 없음 | 거절 |
| 안전 | 접촉 동작 추가 시 힘 상한·후퇴·타임아웃 3종 | 거절 |
| 인터페이스 | `docs/interfaces/`·`cobot_msgs` 변경 시 인터페이스 변경 이슈 링크 + 4명 확인 | 거절 |
| 실기 영향 칸 | PR 템플릿 "실기 영향" 채움 | 거절 |
검토 결과는 PR 코멘트로 남기고(통과/실패 항목), 통과면 황인재가 Approve, 실패면 Request changes.

### 리뷰·merge
| 항목 | 규칙 |
|---|---|
| 필요 승인 | **황인재 1명** (GitHub 규칙: Code Owner 승인 필수). 승인 전에 에이전트가 §4.1 검토표로 확인하고 결과를 PR 코멘트로 남긴다. 팀원 코멘트는 환영하지만 승인 권한은 없음 |
| 응답 시간 | 4시간 안에 코멘트 또는 승인 |
| Merge 방식 | Squash and merge |
| Merge 후 | 브랜치 삭제는 팀장 승인 후 (§2) |
| 리뷰 없이 merge | 실기 중 급한 수정만. merge 후 팀 채널에 알린다 |

리뷰어가 볼 것: ① 안전(힘 상한·속도·타임아웃·후퇴) ② 인터페이스 변경 여부 ③ 하드코딩·절대경로 ④ 실행 방법이 적혀 있는가.

## 5. 이슈 규칙
작업은 **이슈 → 브랜치 → PR** 순.
| 템플릿 | 쓸 때 |
|---|---|
| `작업(Task)` | 계획된 담당 작업. 담당자·완료 기준·실기 필요 여부 |
| `버그(Bug)` | 재현 절차 + Virtual/Real 여부 |
| `인터페이스 변경 요청` | 서비스·메시지·YAML 키 변경. **혼자 바꾸지 말고 여기로** → 4명 확인 |
라벨: `P0-블로커` `P1-중요` `P2-보통` / `실기필요` `virtual가능` / `f1` `f2` `flow` `f3` `f4` `문서` `안전`

## 6. 코드 위치
| 무엇 | 어디에 |
|---|---|
| 우리 ROS 2 패키지 | `src/` (저장소 = `rokey_pjt01_ws`, 위치는 `$REWASH_WS`) |
| 두산 드라이버 | `~/ws_cobot_pjt/ws_dsr` — **수정 금지**, 우리 `src/`에 복사 금지 |
| 좌표·임계값·속도·탐색점 | `src/<패키지>/config/*.yaml` — 코드에 숫자 금지 |
| 런치 | `src/rewash_bringup/launch/` |
| 메시지·서비스 | `src/cobot_msgs/` — 변경은 인터페이스 변경 요청 이슈 |
| 시험 기록 | `docs/test_logs/` |

## 7. 충돌을 줄이는 규칙
1. 파일 소유자를 정한다. YAML은 특히 담당자 1명만 고친다.
2. 아침에 `git fetch` + `main` pull. 저녁에 push.
3. 큰 리팩터링·파일 이동은 팀 공지 후.
4. 실기 당일에는 merge 하지 않는다. **9/29 리허설 전 `main`을 건드리지 않는다.**

## 8. 안전 규칙 (코드 리뷰에서도 강제)
- 새 모션은 **Virtual → 저속 실기(20~30%) → 정상 속도** 순.
- 접촉 동작(탐색 하강·닦기·안착·삽입)은 **힘 상한 + 후퇴 + 타임아웃** 없이 merge하지 않는다.
- `dance` 예제 Real 실행 금지. Dart Platform과 ROS 브링업 동시 제어 연결 금지(티칭 후 제어권 해제).
- 실기 중 E-Stop에 손이 닿는 사람 1명 상시. 작업 반경 안에 사람 없음.
- 안전 파라미터(충돌 감도·속도 한계) 변경은 박진용(안전 담당) 승인.

## 9. 공유 규칙
**무조건 팀 전체 공유**: 서비스·토픽·메시지 필드, YAML 키 이름, 좌표계·TCP 설정, REST 엔드포인트·DB 스키마, IP·도메인 ID.
```
[공유] {무엇} 확정/변경
- 내용: {구체적으로}
- 영향: {누구의 어떤 모듈}
- 반영 필요: {상대가 해야 할 일}
- 근거: PR #{번호}
```

## 10. 릴리스·발표
| 시점 | 할 일 |
|---|---|
| 9/20(일) 저녁 | L1 단위기능 테스트 통과, `integration` 브랜치 생성 |
| 9/22(화) 오전 | L2 통합, 노션에 노드 구조·HMI 화면 업로드, GitHub 최신 |
| **9/23(수) 저녁** | 🚨 L4 전체 통합 + 시연 영상 + **기능 동결**. `main` 태그 `v1.0-demo` |
| 9/24~28 | 추석 — 발표 준비만. 코드는 치명 버그 PR만 |
| 9/29(화) | 오전 리허설, 14:00 강사 입회 시연, 최종 push |
| 9/30(수) 11:00 | 제출(영상·PDF·zip·README, 파일명 `D-2_협동1_한석형_민범진_박진용_황인재.ext`) → 발표 |

```bash
git tag -a v1.0-demo -m "최종 발표 시연 버전" && git push origin v1.0-demo
```

## 11. 막혔을 때
1. `AGENTS.md` §5 환경 함정 표 → 2. `docs/setup/M0609_환경설정.md` 하단 빠른 문제 참조 → 3. 30분 넘게 막히면 팀 채널에 증상 + 명령어 + 오류 전문 → 4. 해결했으면 함정 표에 한 줄 추가해서 PR.
