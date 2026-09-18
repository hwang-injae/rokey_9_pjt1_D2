# -*- coding: utf-8 -*-
import os
import os; ROOT=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); OUT=os.path.join(ROOT,'docs/prompts')
AGENTS=open(os.path.join(ROOT,'AGENTS.md'),encoding='utf-8').read().replace('\n## ','\n### ').replace('# AGENTS.md — ','### AGENTS.md — ',1)
DOCS='`AGENTS.md` · `docs/01_요구사항_BR-SR.md` · `docs/02_인터페이스_IRD.md` · `docs/03_설계_SDD.md`(§9 테스트 계획) · 일정표(구글 드라이브 xlsx: https://drive.google.com/drive/folders/1t58F08_auBRa_q7c4KeNirLKR6CKa4hU?usp=sharing)'
COMMON_TEAM='''## 2. 팀·환경 (✅ 확정)
- D그룹 2조: 한석형(팀장·F1) · 민범진(통합 리더·F2·flow) · 박진용(안전·F3) · 황인재(**PM**·F4). 겸임: 실기 슬롯·기구·브랜치 삭제 승인 한석형 / 통합 리더(L3·L4 주도)·인터페이스 창구 민범진 / 안전 파라미터 박진용 / PM(일정표·문서·제출·강사 창구·PR 승인)·영상·발표·아키텍처 그림 황인재
- M0609 + RG2 1대, 컨트롤러 IP 192.168.1.100 · TCP 12345 · RG2 설정 웹 192.168.1.1. Ubuntu 24.04 + ROS 2 Jazzy, `ROS_DOMAIN_ID=60`. 비전·3D 프린터·액체 사용 불가
- PC: 개발 4대 각자(Virtual/mock). 통합 실행 PC-A(로봇 제어: 드라이버 + f1·f2·f3·flow) + PC-B(HMI). 워크스페이스 `~/ws_cobot_pjt/ws_dsr`(드라이버, 수정 금지) 위에 `rokey_pjt01_ws`(= 저장소, `docs/` + `src/`, 위치는 `.bashrc`의 `REWASH_WS`)
- 용기 그릇 1규격 2개 + 컵 1규격 2개. 팔레트 모형 그릇 2칸·컵 4칸. 반납 구역 2곳(그릇·컵), 구역 안 위치·겹침 자유 → 탐색 파지. 잔반 대용품 고형물(구슬·쌀) ≥100 g
- 일정: 개발 9/18(금)~9/23(수), 주말 로봇 가능. 9/21(월) 오후 중간점검 발표(로봇·개발은 저녁만). 9/23 저녁 **기능 동결**. 추석 9/24~28 로봇 불가. 9/29(화) 14:00 강사 시연. 9/30(수) 11:00 제출·발표
- 브링업: `sod` → `sodvir`(Virtual) / `sodreal`(실기, PC-A) · 우리 코드 빌드 `cbc`. 시나리오·ID·실패 코드·서비스 이름은 `AGENTS.md` §1~2와 IRD가 정본
'''
COMMON_IF='''## 3. 인터페이스 (정본 `docs/02_인터페이스_IRD.md` · `docs/interfaces/`)
- 내가 **제공**하는 서비스와 **사용**하는 것을 IRD에서 그대로 읽고 첫 응답에 표로 정리할 것. 공통 ID(`BOWL` `CUP` `SPONGE` `BRUSH`, 구역 `RET_B` `RET_C`, 칸 `RACK_B1..2` `RACK_C1..4`, 스테이션, 실패 코드)는 IRD §2 문자열 그대로.
- 호출 구조: **flow_node만** 다른 노드를 부른다. 기능 노드는 서비스 제공자다(F4는 flow의 서비스를 부르는 클라이언트).
- 동시 개발 약속: 각 노드는 정해진 위치에서 시작·끝난다 → 용기를 손으로 놓고 단독 시험. 로봇 없이 `mock_f1_f3`·`fake_state_pub`으로 flow·HMI 개발.
'''
COMMON_RULES='''## 4. 진행 규칙 (반드시)
- **규칙 0** 답하기 전 {docs}를 실제로 읽고 **읽은 파일 목록**을 먼저 밝힐 것. 못 읽었으면 추측하지 말고 말할 것. `______`는 질문할 것.
- **규칙 1** 온보딩(§0)이 끝난 뒤의 첫 응답은 계획까지: ① 읽은 파일 ② 내 기능·산출물·**하지 않는 것** ③ 제공/사용 인터페이스(IRD) ④ STEP 표(목표·산출물·완료 기준·선행·Virtual/Real·날짜). 승인 전 구현 금지.
- **규칙 2** 한 응답 = STEP 하나. STEP 전 사전 점검 표(파일·환경·로봇 슬롯·팀원 의존·가정), 후 완료 요약(한 일·산출물 상대경로·검증 명령·트러블슈팅).
- **규칙 3** 🚨 **내 기능 밖 코드를 만들지 않는다.** 다른 기능이 필요하면 mock/stub으로 명시. 다른 노드 서비스를 내 노드에서 직접 호출하지 않는다(호출은 flow_node만).
- **규칙 4** 🚨 안전: 실기 전 Virtual, 첫 실기 속도 20~30%, 접촉 동작(탐색 하강·닦기·안착·삽입)엔 **힘 상한 + 후퇴 + 타임아웃** 필수, 순응·힘제어는 접촉 구간만, `dance` Real 금지, 티치펜던트↔ROS 동시 제어 금지, E-Stop·작업 반경 확인. 실기 로봇은 사용자 확인 없이 움직이지 않는다.
- **규칙 5** 수치·좌표·탐색점은 전부 YAML(내 설정 파일), 코드에 숫자 금지. **경로는 상대경로.** DSR API 직접 호출 금지 — `cobot_common`(두산 API를 감싼 공용 로봇 함수 모음)만. 서비스는 `ok+code`, 코드 문자열은 IRD §2 그대로.
- **규칙 6** 인터페이스(IRD·`docs/interfaces/`)를 바꾸지 않는다. 바꿔야 하면 변경 요청 이슈 초안을 만들어 줄 것.
- **규칙 7** 산출물마다 💾 저장 위치(상대경로·브랜치 `{{이름}}/{{YYYYMMDD}}-{{taskID}}-{{설명}}`·커밋 예시·PR 여부)와 🔔 공유 필요 여부(인터페이스·YAML 키는 무조건).
- **규칙 8** STEP 끝에 📮 진척 보고: 진척(taskID·완료 기준 수치) / 인터페이스 변경 / 블로커 / 로봇 슬롯 / 9/30 리스크 / 복붙 문장 5줄.
- **규칙 9** 순서: **구현 → 사전 검증(V) → L1 단위기능 테스트(TC가 있는 작업은 항상; 로봇이 움직이면 녹화 권장 `YYYYMMDD_TCxx_기능_담당_시도N.mp4`) → main pull → L2 통합 → PR(제목 `<타입>(<스코프>): <taskID> <제목>`, Reviewer hwang-injae)**. 승인 조건은 main 최신 병합과 산출물 미포함 두 가지(자동 검사), 테스트는 본인 책임으로 본문에 한 줄. 개발 STEP은 **9/23 이내**, 9/24 이후는 발표 준비만. `main` 직접 push 금지, 하루 1회 push.
- **규칙 10** 설명은 ROS 2·두산 API 초보 기준으로 첫 등장 시 한 줄 풀이, 내 기능의 핵심은 가장 깊게. 명령어는 복붙 가능하게, 실행 위치 명시. 한국어.
'''.replace('{docs}',DOCS)
STEP='''## 5. STEP 출력 템플릿
```
## [STEP n] {taskID}: {작업명}   ⏱ {n}시간 | 📅 {날짜·시간대} | 🤖 {Virtual/Real}
### 1️⃣ 사전 점검 — 파일/환경/로봇 슬롯/팀원 의존 표 · ❓질문 · 🧩가정
### 2️⃣ 작업 진행 — 왜 → 개념 → 코드/명령 → 결과 예시 → 완료 기준 체크 (실기면 저속·힘상한·후퇴·타임아웃·E-Stop 포함)
### 3️⃣ 완료 요약 — 한 일 / 산출물 / 검증 명령 / 트러블슈팅
### 4️⃣ 저장 & 공유 — 💾 경로·브랜치·커밋·PR / 🔔 대상·사유·메시지 초안
### 5️⃣ 📮 진척 보고
### ➡️ 다음 STEP 예고 + "진행할까요?"
```
'''
UNDO='''## 되돌리기 문구
| 상황 | 문구 |
|---|---|
| 여러 STEP을 몰아서 씀 | `규칙 2 위반. STEP 하나만 다시.` |
| 파일 안 읽고 추측 | `규칙 0. 읽은 파일 목록부터.` |
| 내 기능 밖 코드 | `규칙 3 위반. 그건 F? 담당이야. mock으로 두고 내 기능만.` |
| 수치 하드코딩 / 절대경로 | `규칙 5. YAML·상대경로로 바꿔서 다시.` |
| 접촉 동작에 힘 상한·후퇴·타임아웃 없음 | `규칙 4. 세 개 넣어서 다시.` |
| DSR API 직접 호출 | `규칙 5. cobot_common 공용 함수로.` |
| 인터페이스를 바꿈 | `규칙 6. 변경 요청 이슈 초안으로.` |
| 비전·센서 제안 | `비전 불가. 파지 폭·하중·힘·위치로.` |
| 단위 테스트 없이 통합 | `규칙 9. TC부터, 녹화하고.` |
| 9/24 이후 개발 STEP | `규칙 9. 개발은 9/23까지. 이후는 발표 준비만.` |
'''
TOOL={
'F1':dict(tool='ChatGPT 웹',
 attach='이 파일 + `AGENTS.md` + `docs/00_팀원_시작가이드.md` + `docs/setup/M0609_환경설정.md` + `docs/01_요구사항_BR-SR.md` + `docs/02_인터페이스_IRD.md` + `docs/03_설계_SDD.md`. ChatGPT **Projects**에 "ReWash F1" 프로젝트를 만들어 파일을 올려 두면 대화마다 다시 첨부하지 않아도 된다(Instructions 칸에는 AGENTS.md 내용)',
 how='''- 너는 명령을 실행하거나 파일을 만들 수 없다. **명령은 하나씩** 주고, 내가 터미널에서 실행한 출력을 붙여넣으면 그걸 보고 판정한다. 코드는 **파일 전체 내용 + 저장할 상대경로**를 함께 주고, 내가 저장한 뒤 실행 결과를 붙여넣는다.
- git(브랜치·커밋·push·PR)도 내가 직접 한다. 매번 정확한 명령을 순서대로 준다(가이드 부록 B 루틴 카드 기준).'''),
'F2':dict(tool='VS Code의 Claude Code 확장',
 attach='없음 — VS Code에서 **`~/rokey9_pjt1/rokey_pjt01_ws` 폴더를 루트로** 열면 `CLAUDE.md`→`AGENTS.md`와 `docs/`를 네가 직접 읽는다(상위 폴더를 열면 안 됨). 채팅에 `/f2` 를 치면 이 프롬프트가 자동으로 적용된다',
 how='''- 너는 저장소 안에서 파일을 만들고 명령을 실행할 수 있다. 확인 명령(`git`, `ls`, `echo $REWASH_WS`, `ros2`)은 네가 직접 실행해 판정한다. `sudo`·설치·**로봇을 움직이는 명령**은 나에게 실행을 부탁하고 결과를 받는다.
- 아침 `/daily taskID 설명`, 저녁 `/wrap` 명령이 있다. 없으면 같은 절차를 네가 수행한다.'''),
'F3':dict(tool='Claude 데스크톱 앱의 Claude Code',
 attach='없음 — Claude 앱 **Code 탭 → 폴더 선택 → `~/rokey9_pjt1/rokey_pjt01_ws`** (이 폴더가 루트). `CLAUDE.md`→`AGENTS.md`와 `docs/`를 네가 직접 읽는다. 채팅에 `/f3` 를 치면 이 프롬프트가 자동으로 적용된다',
 how='''- 너는 저장소 안에서 파일을 만들고 명령을 실행할 수 있다. 확인 명령은 네가 직접 실행해 판정한다. `sudo`·설치·**로봇을 움직이는 명령(힘제어 검증 포함)**은 나에게 실행을 부탁하고 결과를 받는다.
- 아침 `/daily taskID 설명`, 저녁 `/wrap` 명령이 있다.'''),
'F4':dict(tool='Claude 데스크톱 앱의 Claude Code',
 attach='없음 — Claude 앱 Code 탭에서 `~/rokey9_pjt1/rokey_pjt01_ws` 를 연다. `/f4` 로 시작',
 how='''- 너는 파일 생성·명령 실행이 가능하다. 로봇 명령은 F4 범위에 없다. PC-B 역할이면 `cobot_msgs`+`f4_hmi`만 빌드한다.
- 팀원 PR 검토는 `/pr-review 번호`.'''),
}

ROLES={
'F1':dict(file='F1_한석형_프롬프트.md',name='한석형',title='F1 파지·이송·적재 (+ cobot_common 공용 로봇 함수)',
 one='그릇·컵·툴을 **찾아서 잡고·옮기고·놓고·팔레트에 꽂는** 모든 동작. 반납 구역에서 용기가 겹치거나 어긋나 있어도 **탐색 파지**로 집는다. 로봇이 "어디로 어떻게" 움직이는지는 전부 내 일이다.',
 tasks='''- `cobot_common` v0 (**9/18 저녁~9/19 오전 최우선**, 남들이 이걸로 개발): `move_to(station, carrying)` `move_rel(dx,dy,dz,frame)` `grip(width, force)→width` `release()` `weigh(n)` `force_on/off` `contact_down(max_depth, limit)` `periodic_search` `safe_retreat`
- `f1_node` 서비스: `/f1/pick`(탐색 파지) `/f1/place` `/f1/move_to` `/f1/tool` `/f1/rack_place` `/f1/home`
- **탐색 파지 `pick(zone_id, kind)`** (SDD §5.2): 구역 기준점 + `f1.yaml` 탐색점 오프셋 순회 → 각 점에서 그리퍼 열기 → `contact_down`(힘 상한·최대 깊이·타임아웃)으로 접촉 높이에 정지(겹친 용기는 위 용기 높이) → `grip` → 폭이 프리셋 ±3 mm면 성공(응답에 `attempts`, `offset`) / ≤5 mm 빈손·폭 초과(두 개 파지)면 놓고 다음 점 → 다 돌면 `EMPTY_ZONE`. `zone_id`가 `SPONGE_BED_*`면 탐색점 1개(고정 재파지)
- `f1.yaml`: 종류별 프리셋(폭·힘·허용 폭·접근 높이), 구역 기준점·탐색점 목록·최대 횟수·하강 힘 상한, 스테이션 좌표, 팔레트 기준점 + 칸 오프셋·각도(그릇 2·컵 4), 속도 상한(들고 있을 때 30%), 안전 높이, 삽입력 상한
- `rack_place`: 기준점 + 칸 오프셋 → 지정 각도 → 상공 → 순응 ON 하강 + 삽입력 감시 → 도달 시 놓기 → 후퇴. 걸림 → 후퇴 → `RACK_JAM`
- `tool`: 홀더 방향 고정, 픽업 후 폭 확인(범위 밖 `TOOL_FAIL`), 반납은 힘 접촉으로 바닥 확인
- 기구(9/18): 반납 구역 2곳 표시(트레이·테이프), 팔레트 모형 배치, 격리 구역, 핑거 실리콘 패드
- 9/18 저녁 ENV-02 로봇 접속(192.168.1.100)·RG2 웹 설정·툴/TCP 확인, V-01 파지 폭 3상태·V-05 DO/DI. 9/19 오전 **공통 좌표 티칭 세션** 진행. 9/19 오후 V-06 삽입·V-08 툴. 9/20 오전 **V-14 겹친 용기 탐색 파지**
- 겸임: 팀장, 실기 슬롯 배분, 기구 총괄, 브랜치 삭제 승인''',
 not_='잔반·닦기 판정 기준(F2·F3), 흐름 순서·정책(flow), HMI. 힘제어 닦기 궤적은 F3.',
 out='`src/cobot_common/robot.py` · `src/f1_handling/f1_node.py` · `src/f1_handling/config/f1.yaml` · `src/f1_handling/test/rig_f1.py` · 핑거 패드·반납 구역·팔레트 배치',
 rig='반납 구역에 그릇 2개를 겹쳐/어긋나게, 컵 2개 동일 + 빈 구역 1회. 툴 홀더 2종, 팔레트 모형. 손으로 놓고 서비스만 호출.',
 l1='TC-01 탐색 파지 그릇·컵 각 10회 ≥9, 빈 구역 `EMPTY_ZONE` 5/5, 낙하 0, 두 개 파지 0 · TC-02 툴 픽업/반납 각 10회, 안전 높이 · TC-09 팔레트 6칸 각 5회 ≥9, 걸림 → `RACK_JAM` 후퇴. 전부 녹화',
 sched='9/18 B~C CELL-01 기구·INF-02 공용 함수 착수, C ENV-02·V-01·V-05 → 9/19 A CELL-04 티칭, B V-06·V-08, B~C F1-01 → 9/19 C~9/20 A **F1-02 탐색 파지**·V-14, A F1-03 툴, B F1-04 적재, B~C **UT-F1** → 9/21 C **INT-12b 주도** → 9/22 A INT-13 참여, B~C L3 → 9/23 L4',
 deep='''- **탐색 파지를 가장 깊게**: 탐색점 배치(중심 → 십자 → 대각), 접촉 하강이 겹친 용기 높이에 어떻게 적응하는지, 폭으로 빈손/정상/두 개 파지를 가르는 표, 실패 시 놓고 올라가는 안전 순서, `attempts`·`offset` 기록이 KPI가 되는 이유.
- **`trans()`·Pallet**: 기준점 1개 + 오프셋으로 탐색점·팔레트 칸 6개를 만드는 계산 예시. 팔레트를 옮겨도 기준점만 재티칭.
- **팔레트 삽입**: 지정 각도 자세 만들기, 순응제어 + 삽입력 감시, 걸림 판정(힘↑ & 깊이 미달).
- **티칭 절차**: Dart Platform 자세 → 좌표 읽기 → YAML → ROS 재현 → 🚨 제어권 해제.''',
 req='''1. **역할·요구사항 분석**: 산출물, 하지 않는 것의 경계, 인터페이스(제공/사용) 표
2. **환경 준비 점검**: 내 기능에 추가로 필요한 것만 (실기 IP 192.168.1.100 접속·RG2 DO/DI·TCP·툴 무게 확인 명령)
3. **STEP 실행 계획**: 구글 드라이브 일정표의 내 taskID(CELL-01, INF-02, ENV-02, V-01/05/06/08/14, F1-01~04, UT-F1, INT-12b)에 날짜·시간대를 붙여서. 공용 함수 → 티칭 → 탐색 파지 → 툴 → 적재 → TC 순
4. **초기 코드 골격**: `cobot_common/robot.py` → `f1.yaml`(프리셋·탐색점·좌표 자리) → `f1_node.py`(pick 탐색 루프·rack_place·tool) → `rig_f1.py`. 안전 3종 포함
5. **주의사항** — 탐색점을 코드에 박기 / 접촉 하강에 최대 깊이 없음 / 폭 판정 없이 성공 처리 / 두 개 파지 미검출 / 힘만으로 삽입 성공 판정 / 티칭 후 제어권 안 풀고 브링업 / `dance` Real 실행'''),
'F2':dict(file='F2_민범진_프롬프트.md',name='민범진',title='F2 무게·털기·헹굼 + flow_node + cobot_msgs (통합 리더)',
 one='**무게로 잔반을 판정하고 털어내는 폐루프**, 헹굼·물털기 모션, 그리고 전체 공정을 **구역 계획대로 엮고 실패를 복구하는 flow_node**. L3·L4 통합 리더.',
 tasks='''- **9/18 저녁 최우선**: `cobot_msgs` srv 12·msg 2 배포(`docs/interfaces/` 그대로, F1Pick 탐색 필드·FlowState target·FlowEvent attempts 포함) + `mock_f1_f3`(실패 주입 가능) — 이게 있어야 4명이 동시에 간다
- `f2_node` 서비스: `/f2/weigh` `/f2/leftover_loop` `/f2/shake` `/f2/dip`
- `f2.yaml`: 빈 용기 기준 무게(그릇·컵), 임계(기본 50 g, 미만은 통과), 평균 횟수, 털기 진폭·속도·횟수(WASTE/RINSE), 담금 깊이·시간
- 무게: WEIGH 자세 1개 고정, 정지 후 `get_workpiece_weight` N회 평균(차동: 파지 전 0점). 9/18 저녁 V-02 100/200 g 추로 정밀도 실측(±20 g)
- 잔반 폐루프: 판정 → 잔반통 위 털기 3~5회 → 재측정 → 최대 M회 → 초과 지속 `LEFTOVER_REMAIN`
- 털기·물털기: 관절 왕복(J5/J6), 진폭·속도 제한, 9/19 V-07 충돌 감지 정지 0 확인
- `flow_node`: `flow.yaml`의 구역 계획 `plan: [{RET_B, BOWL, 2}, {RET_C, CUP, 2}]` 대로 F1→F2→F3→F2→F1 호출, 상태 머신(SDD §5.1, `EMPTY_ZONE`→다음 구역), 실패 정책, `/flow/state` 2 Hz(target 포함), `/flow/event`, `records.csv`, 소모품 카운트, `start/stop/resume`
- 겸임: 통합 리더 — L2 INT-12a 주도, L3·L4 주도(통합 체크리스트·범위 방어 발동 제안), 인터페이스 창구(`cobot_msgs` 변경 이슈 정리), 9/22 노션에 노드 구조·인터페이스 정의서 업로드. 일정표 갱신·제출은 PM(황인재)에게 진척 보고로 전달''',
 not_='파지·이송·적재 동작(F1), 닦기 힘제어(F3), HMI 화면(F4). 다른 노드 코드를 대신 만들지 않는다 — mock으로 대체.',
 out='`src/cobot_msgs/` · `src/f2_sense_flow/f2_node.py` `flow_node.py` `mock/mock_f1_f3.py` `logger.py` · `config/f2.yaml` `flow.yaml` · `records.csv` 스키마 · `src/rewash_bringup/launch/*.py`',
 rig='100/200 g 추, 대용품 용기 4·빈 용기 4, 잔반통, 빈 수조. F1 없이 손으로 용기를 쥐여주고 서비스만 호출. flow는 mock으로.',
 l1='TC-03 무게 ±20 g · TC-04 잔반 검출 100%/오판 0 · TC-08 헹굼·물털기 10회 정지 0 · TC-10 mock 실패 주입 5종 정책대로(EMPTY_ZONE → 다음 구역) · TC-12 기록 4행 누락 0. 전부 녹화',
 sched='9/18 B~C CELL-03 수조·대용품(V-11), C INF-01 msgs·INF-03 mock·V-02, C~9/19 C FLOW-01 → 9/19 B V-07, B~C F2-01 → 9/19 C~9/20 A FLOW-02 기록, A F2-02·UT-FLOW → 9/20 C **UT-F2**·**INT-12a 착수** → 9/21 C INT-12a 마무리·CR-01 → 9/22 A NOTE-01 노션, B~C **L3 주도** → 9/23 **L4 주도**·동결',
 deep='''- **하중 측정을 가장 깊게**: `reset_workpiece_weight` → 정지 → `get_workpiece_weight` 절차, 관절 토크 기반이라 자세·가감속에 민감한 이유, 평균·차동으로 ±20 g를 만드는 법, 50 g 임계와 "미만은 통과"의 근거.
- **상태 머신**: 전이표(SDD §5.1)를 코드 구조(딕셔너리 + 핸들러)로, PAUSED에서 이전 상태 복귀, 구역 count·EMPTY_ZONE 처리, 어떤 실패에서도 툴 반납.
- **mock 설계**: 같은 서비스 이름으로 즉시 응답 + 파라미터로 실패 주입 → TC-10.
- **통합 운영**: L2→L3→L4 체크리스트, 범위 방어표 발동 조건(결정은 PM·팀장과 브리핑에서).''',
 req='''1. **역할·요구사항 분석**: 산출물, 하지 않는 것의 경계, 인터페이스(제공/사용) 표
2. **환경 준비 점검**: `cobot_msgs` 빌드·배포 절차, mock 실행 명령
3. **STEP 실행 계획**: 구글 드라이브 일정표의 내 taskID(CELL-03, INF-01, INF-03, V-02, V-07, FLOW-01/02, F2-01/02, UT-FLOW, UT-F2, INT-12a, NOTE-01, INT-3a/3b, INT-4a~d)에 날짜·시간대를 붙여서
4. **초기 코드 골격**: `cobot_msgs` → `mock_f1_f3.py` → `flow_node.py`(상태 머신·plan·정책·state/event 발행) → `f2_node.py`(weigh·leftover_loop·shake·dip) → `logger.py` → 런치 2종
5. **주의사항** — msgs 배포가 늦어 4명이 대기 / flow가 F1·F3 로직을 품음 / 힘·무게를 Virtual에서 검증했다고 믿음 / EMPTY_ZONE 후 다음 구역으로 안 넘어감 / stop 중 서비스 호출 이어감 / 기록 누락'''),
'F3':dict(file='F3_박진용_프롬프트.md',name='박진용',title='F3 접촉 닦기 (스펀지 고정틀·수세미 툴·수세미 솔) + 안전 파라미터',
 one='용기를 **스펀지 홈에 안착**시키고(안 맞으면 Move Periodic으로 찾고), **툴을 쥔 채 일정한 힘으로 안쪽을 닦는** 동작. 프로젝트에서 가장 어렵고 가장 티 나는 기능. 안전 파라미터 소유.',
 tasks='''- `f3_node` 서비스: `/f3/seat` `/f3/soap` `/f3/wipe`
- `f3.yaml`: 안착 접근 높이·접촉 상한, 탐색 진폭(±2~5 mm)·주기·최대 시간, 그릇 닦기 목표 힘 3~5 N·상한 10 N·나선 반지름·회전수·시간, 컵 회전 각·스트로크·횟수
- `seat`: 홈 상공 → 순응 ON 하강 → 접촉·깊이 판정 → 미달이면 `periodic_search` 중 접촉 조건 감시 → 성공/한도 초과 `SEAT_FAIL`(후퇴)
- `soap`: 툴 든 채 세제 수조 담금 N회(모션만)
- `wipe(BOWL)`: 홈 중심 상공 → 힘제어(툴 Z, 목표 힘) → r1→r2 나선 `turns`회 → 힘 로그 저장 → OFF → 후퇴. **힘 상한·타임아웃 초과 즉시 후퇴**
- `wipe(CUP)`: 컵 중심 → 삽입 깊이(힘 감시) → J6 ±180° + Z 스트로크 반복 → 후퇴
- 기구(9/18): 대형 스펀지에 그릇·컵 홈 커팅(여유 1~2 mm, V-12), 툴 홀더 2종, 수세미 손잡이(형상 파지), 고정틀 작업대 고정
- 9/19 오후 검증: V-03 힘제어 중 XY 이동, V-04 periodic 탐색 안착, V-10 컵 솔 삽입 깊이
- 겸임: 안전 파라미터(속도·충돌 감도·힘 상한·수조 배치) 소유, 9/21 SAFE-01 위험요소·안전대책·예외/오류 리스트 노션 업로드''',
 not_='파지·이송·툴 픽업 동작 자체(F1 `/f1/tool`을 flow가 호출, 나는 툴을 쥔 상태에서 시작), 무게 판정(F2), 흐름 순서(flow), HMI.',
 out='`src/f3_wipe/f3_node.py` · `src/f3_wipe/config/f3.yaml` · `src/f3_wipe/test/rig_f3.py` · 힘 로그 `force_*.csv` · 스펀지 고정틀·툴 홀더·수세미 손잡이 · 안전 파라미터 표',
 rig='스펀지 홈에 그릇·컵을 손으로 놓고, 툴을 그리퍼에 손으로 쥐여준 뒤 서비스만 호출. F1 없이 개발 가능.',
 l1='TC-05 안착 정위치 5 + 2 mm 오프셋 5 ≥9/10, 한도 초과 `SEAT_FAIL` · TC-06 그릇 닦기 10회 목표 ±2 N·상한 초과 0·강제 초과 시 후퇴 · TC-07 컵 닦기 10회 정상. 전부 녹화',
 sched='9/18 B~C CELL-02 고정틀·홀더, C V-12 → 9/19 B **V-03·V-04·V-10**, C F3-01 seat 착수 → 9/20 A F3-01, A~B F3-02 wipe(BOWL), B F3-03 soap·cup·**UT-F3** → 9/21 C SAFE-01, C~9/22 A **INT-13 주도** → 9/22 L3 → 9/23 L4 실패 주입',
 deep='''- **힘제어를 가장 깊게**: `task_compliance_ctrl`·`set_desired_force`가 무엇을 하는지, 툴 좌표계 Z로 힘을 걸며 XY로 움직이는 구조(V-03 결과에 따라 대안), 목표 3~5 N·상한 10 N의 근거, `check_force_condition`으로 후퇴 트리거, `release_force` 순서.
- **안착 판정과 탐색**: 깊이 + 힘 AND 조건, Move Periodic 진폭·주기·시간 한도, 접촉 조건 감시로 "들어갔다"를 아는 법.
- **힘 로그**: `get_tool_force` 샘플링 → CSV → 발표 그래프.
- **안전 파라미터 표**: 속도·충돌 감도·힘 상한·타임아웃을 한 표로, 변경 승인 절차.''',
 req='''1. **역할·요구사항 분석**: 산출물, 하지 않는 것의 경계, 인터페이스(제공/사용) 표
2. **환경 준비 점검**: 힘제어 API 사용 조건(TCP·툴 무게 설정), Virtual에 힘이 없음을 전제로 한 검증 계획
3. **STEP 실행 계획**: 구글 드라이브 일정표의 내 taskID(CELL-02, V-12, V-03/04/10, F3-01~03, UT-F3, SAFE-01, INT-13)에 날짜·시간대를 붙여서
4. **초기 코드 골격**: `f3.yaml` → `f3_node.py`(seat·soap·wipe, 힘 상한·후퇴·타임아웃 공통 래핑) → `rig_f3.py` → 힘 로그 저장기
5. **주의사항** — 힘제어를 이동 전체에 켬 / 힘만으로 안착 성공 판정 / 나선을 깊이 기준으로 짬(스펀지 눌림) / 후퇴 없이 예외만 던짐 / 컵 삽입 깊이에 힘 감시 없음 / 툴 없이 wipe 시작'''),
'F4':dict(file='F4_황인재_프롬프트.md',name='황인재',title='F4 시스템 모니터 — 웹 HMI (FastAPI + rclpy + SQLite) + PM·KPI·영상·아키텍처 그림',
 one='사람이 **시작·정지·재개**하고 **단계·수량·소모품·연결·오류·이력**을 보는 웹 화면. 웹은 처음이지만 도전한다. 로봇 없이 **가짜 상태 발행기**로 먼저 완성하고, L2에서 mock flow, L3에서 실제 flow(PC-A)에 PC-B로 꽂는다.',
 tasks='''- 배우는 순서(웹 처음): ① FastAPI "안녕" 페이지 ② 버튼 3개가 서버 함수 호출 ③ 서버가 1초마다 숫자를 WebSocket으로 밀고 화면 갱신 ④ 그 숫자를 `/flow/state`로 교체(rclpy 결합) ⑤ `/flow/event`마다 SQLite 한 줄 + 이력 표. ④까지 `fake_state_pub`만 있으면 된다
- `src/f4_hmi/app.py`: FastAPI — `POST /api/start|stop|resume`(→ `/flow/*` 서비스), `GET /api/state`, `GET /api/history`(SQLite), WS `/ws/state`(`/flow/state`·`/flow/event` 중계). rclpy는 별도 스레드(spin), 서비스 호출은 요청 스레드를 막지 않게
- `src/f4_hmi/db.py`: SQLite `rewash.db` — `events`(FlowEvent 필드 그대로 + id, received_at), `state_log`(1 Hz). 파이썬 내장 `sqlite3`, 설치 없음. MQTT는 쓰지 않는다(ROS 토픽과 중복)
- `static/index.html`(HTML/JS 한 장, 프레임워크 없음): 제어(시작·**정지=소프트 E-STOP 항상 노출·붉은색**·재개) / 상태(모드·단계·현재 용기·구역·진행률 done/target) / 반납 구역 2칸·팔레트 6칸 / 수량·소모품 바 / **ROS 연결 점**(state 2 s 이상 없으면 빨강, 버튼 비활성) / 오류 코드·로그(붉은 경고 우선) / 최근 이력 표
- `fake_state_pub.py` (**9/18 최우선**): 시나리오(yaml)대로 `/flow/state`·`/flow/event` 발행(정상·격리·오류·PAUSED·EMPTY_ZONE)
- `hmi.yaml`: 포트 8000, 갱신 2 Hz, 끊김 판정 2 s, DB 경로(상대)
- 9/19 A ENV-03/V-09 PC 2대 통신 확인(민범진과), A~B ARCH-01 아키텍처 draw.io 최종 + 노션 산출물 등록. 9/22 A NOTE-02 HMI 화면 gif 노션 업로드, F4-05 KPI 스크립트(records/SQLite → 성공률·사이클 타임·탐색 시도)
- 추석: 시연 영상 편집(1분 이내), PPT(강사 5장 양식), 발표 대본 보조
- 겸임: **PM** — 구글 시트 일정표 갱신(진행·상태·완료 목록·변경이력, 매일 저녁), 팀원 진척 보고 취합, 문서 정본·노션 조별 페이지·강사 DM 창구, 제출(SUB-01, 9/30 11시 전, 파일명 규칙), PR 승인(`/pr-review`). 통합 실행 주도는 민범진''',
 not_='흐름 순서·복구 판단(flow), 로봇 동작·힘 판정(F1~F3), 칸 배정 알고리즘. HMI는 **보여주고 전달만** 한다.',
 out='`src/f4_hmi/app.py` `db.py` `static/index.html` `fake_state_pub.py` `config/hmi.yaml` · `kpi.py` · 아키텍처 `.drawio` · 시연 영상·PPT',
 rig='로봇·flow 없이 `fake_state_pub.py` + `app.py`만. 브라우저에서 확인. PC-B에서는 `cobot_msgs` + `f4_hmi`만 빌드.',
 l1='TC-11 버튼 → 서비스 호출 ≤1 s, 상태 표시 지연 ≤1 s, fake 시나리오(정상·격리·오류·재개·EMPTY_ZONE) 전부 표시, 끊김 표시 · TC-12 SQLite 4행(민범진과) · V-13 브라우저 start → mock flow 반응 · INT-4 mock flow 연결. 녹화',
 sched='9/18 B~C F4-01 fake pub·골격 → 9/19 A ENV-03 통신, A~B F4-02 브리지·버튼·ARCH-01, C~9/20 B F4-03 화면 → 9/20 A V-13, B F4-04 SQLite, C **UT-F4** → 9/21 C **INT-4** → 9/22 A NOTE-02 gif·F4-05 KPI, B~C L3 HMI(PC-B) → 9/23 INT-4c 측정·영상 촬영 → 추석 영상 편집·PPT',
 deep='''- **ROS ↔ 웹 연결을 가장 깊게**: `rclpy.spin()`과 uvicorn 이벤트 루프를 같이 돌리는 법(스레드 + 큐), 서비스 호출을 요청 스레드에서 블로킹 없이, WebSocket으로 상태를 밀어주는 구조를 코드 골격으로. 웹이 처음이므로 HTTP·WebSocket·JSON을 한 줄씩 풀어서.
- **SQLite**: 표 2개 스키마, INSERT/SELECT 최소 코드, 파일 경로는 상대경로.
- **가짜 발행기**: 실제 `FlowState`·`FlowEvent` 필드 그대로(target·attempts 포함), 시나리오 yaml로 순서·타이밍·실패 코드 재생.
- **화면 우선순위**: 시연에서 청중이 봐야 할 것(단계·구역/팔레트 칸이 차오르는 것·오류→재개·연결 상태) 중심. 화려함보다 가독성(폰트 크게).
- **KPI**: 성공률·격리율·사이클 타임 평균/편차·잔반 검출률·탐색 시도 평균을 CSV/SQLite에서 계산하는 스크립트와 표.''',
 req='''1. **역할·요구사항 분석**: 산출물, 하지 않는 것의 경계, 인터페이스(제공/사용) 표
2. **환경 준비 점검**: PC-B에 필요한 것만(`cobot_msgs`+`f4_hmi` 빌드, FastAPI·uvicorn·websockets 설치 — HMI 전용 venv, colcon은 시스템)
3. **STEP 실행 계획**: 구글 드라이브 일정표의 내 taskID(F4-01~05, ENV-03/V-09, ARCH-01, V-13, UT-F4, INT-4, NOTE-02, INT-4c, DOC-03)에 날짜·시간대를 붙여서. 웹 학습 순서 ①~⑤를 STEP에 녹일 것
4. **초기 코드 골격**: `fake_state_pub.py` → `app.py`(FastAPI + rclpy 스레드 + WS 브로드캐스트) → `index.html`(상태 바인딩, 버튼 3개, 구역 2 + 팔레트 6칸, 연결 점, 오류 로그, 이력 표) → `db.py`. **가짜 발행기부터**
5. **주의사항** — 예쁜 UI 먼저 만들다 브리지·버튼 미완성(순서: fake pub → 브리지 → 버튼 → 화면 → DB) / 메시지 필드를 IRD와 다르게 가정 / rclpy와 uvicorn을 같은 스레드에서 돌려 멈춤 / 연결 끊김 표시 없음 / 재개 버튼 없이 오류 화면만 / L3 전에 실제 flow에 한 번도 안 붙여봄 → 9/21 INT-4에서 mock flow에 먼저 연결'''),
}
for k,r in ROLES.items():
    T=TOOL[k]
    body=f'''# {r["title"]} — {r["name"]} — 개인 프롬프트

> **내 도구**: {T["tool"]}
> **에이전트에게 줄 것**: {T["attach"]}
> **사용법**: 이 파일 전문을 새 대화의 첫 메시지로 붙여넣는다(Claude Code는 `/f?` 명령이 대신 붙여넣는다). `______`(이름·수준·GitHub ID·내 PC)는 붙여넣기 전에 채우거나, 비워 두면 에이전트가 먼저 묻는다. 첨부가 안 되는 도구면 이 파일 맨 아래 **부록 A(AGENTS.md 전문)** 가 있으니 그대로 함께 붙여넣는다.

---

## 0. 시작 순서 — 문서를 내가 읽지 않아도 되게 네가 순서대로 끌고 간다

나는 GitHub·ROS 2가 처음일 수 있다. 첨부(또는 저장소)의 문서를 **네가 읽고**, 아래 순서를 **한 번에 한 단계씩** 진행한다. 한 단계가 끝나기 전에 다음 단계를 주지 않는다. 각 단계는 ① 왜 하는지 한 줄 ② 실행할 명령 하나 ③ 기대 결과 로 준다. 통과하면 "✅ n단계 완료"라고 적는다.

{T["how"]}
- 토큰(`ghp_…`)·비밀번호는 절대 채팅에 붙이지 말라고 먼저 말한다. 모르는 값은 추측하지 말고 문서에서 찾거나 나에게 묻는다.

| 단계 | 내용 | 근거 문서 | 완료 기준 |
|---|---|---|---|
| 0-1 | 내 이름·담당 기능·도구 확인, **온보딩을 이미 마쳤는지** 묻기 (마쳤으면 §1로 바로) | — | 답변 |
| 0-2 | git 설정: `user.name` `user.email` `pull.rebase false` `credential.helper store` | 가이드 ① | `git config --global --list` |
| 0-3 | GitHub 초대 수락 확인, 토큰 생성(`https://github.com/settings/tokens`, classic, repo) | 가이드 1-2 | 토큰 보관 완료(값은 안 보여 줌) |
| 0-4 | 저장소 clone `~/rokey9_pjt1/rokey_pjt01_ws`, `.bashrc`에 `REWASH_WS` | 가이드 ② | `git remote -v`, `echo $REWASH_WS` |
| 0-5 | PC 환경: ROS 2 Jazzy → `ws_dsr` 클론·빌드 → DRCF → PYTHONPATH(DR_init) → `.bashrc` 별칭 → `sodvir` → `cbc` | 환경설정 문서 1장~11장 | 문서 맨 아래 **최종 완료 체크리스트** 전부 ✅ (= 일정표 ENV-01) |
| 0-6 | 읽을 문서를 네가 요약: AGENTS.md 절대 규칙 12개, IRD에서 **내 기능의 서비스**, CONTRIBUTING §0~2 | AGENTS·IRD·CONTRIBUTING | 내가 "이해했다" |
| 0-7 | 첫 PR 실습: 브랜치 → `docs/test_logs/YYYYMMDD_ENV-01_이름.md` → 커밋 → push → PR(Reviewer **hwang-injae**, 본문 승인 조건 표) | 가이드 ④-2 | PR 링크 |
| 0-8 | "온보딩 완료" 선언 → §1 내 역할로 넘어가 **규칙 1의 첫 응답(읽은 파일 → 역할 → 인터페이스 표 → STEP 계획)** 을 낸다 | — | STEP 계획 승인 |

이후 매일: 아침 main 최신화 → 브랜치 `{{이름}}/{{YYYYMMDD}}-{{taskID}}-{{설명}}` → STEP 진행 → 단위기능 테스트(녹화) → 저녁 커밋·push(하루 1회 이상) → 통합 전 `git merge origin/main` → PR(승인 조건 표 채움). taskID·로봇 슬롯은 구글 드라이브 일정표, 완료 기준은 SDD §9.

---

## 1. 내 역할
- **기능**: {r["title"]} — {r["name"]}
- **한 줄**: {r["one"]}
- **내 이름 / 수준**: `______` / `______` (기본 가정: 파이썬은 되지만 ROS 2·두산 API는 처음)
- **GitHub ID / 내 PC**: `______` / `______`

### 담당 작업
{r["tasks"]}

### 🚫 하지 않는 것
{r["not_"]}

### 📦 산출물 (상대경로)
{r["out"]}

### 🧪 단독 시험 리그 (남의 코드 없이)
{r["rig"]}

### ✅ L1 단위기능 테스트 통과 기준 (docs/03_설계_SDD.md §9.3)
{r["l1"]}

### 📅 내 일정 (구글 드라이브 일정표 Time Line · A 오전 B 오후 C 저녁)
{r["sched"]}

---

{COMMON_TEAM}
---

{COMMON_IF}
---

{COMMON_RULES}
### 규칙 10 보충 — 내 기능에서 깊게 설명할 것
{r["deep"]}

---

{STEP}
---

## 6. 요청 사항

자료를 읽고 내가 **{r["title"]} — {r["name"]}**을 성공적으로 수행하도록 안내해 줘. **§0 온보딩(이미 마쳤으면 건너뜀) → 규칙 1에 따라 1~3은 첫 응답, 4~5는 STEP 단위.**

{r["req"]}

먼저 **읽은 파일 목록 → 역할·산출물 요약 → 인터페이스 표 → STEP 계획** 순으로 답한 뒤 내 승인을 기다려 줘.

---

{UNDO}
---

## 부록 A. AGENTS.md 전문 (첨부가 안 되는 에이전트용 — 이 아래를 그대로 같이 붙여넣는다)

{AGENTS}'''
    open(os.path.join(OUT,r['file']),'w',encoding='utf-8').write(body)
    print(r['file'], body.count('\n'))
