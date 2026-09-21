PR 번호 $ARGUMENTS 를 검토한다(번호가 없으면 `python3 tools/pr_open.py` 로 열린 PR을 찾는다 — 로그인 없이 된다). 9/19부터 Actions는 **문서만 바뀐 PR**만 자동 승인·merge 하고, **코드·설정·도구·인터페이스 정본이 포함된 PR**은 이 절차로 PM 에이전트가 바뀐 것을 전부 읽고 **직접 승인·Squash merge 또는 거절한다**(황인재 위임, 9/19 — 끝난 뒤 한 줄 보고). PM 폴더(`rokey_pjt01_ws`, 항상 main)의 저장소 루트에서 실행한다.

절차:
1. `tools/pr_check.sh $ARGUMENTS` 를 실행하고 출력을 그대로 읽는다.
2. `git diff origin/main...pr-$ARGUMENTS` 로 실제 변경을 읽는다. 특히 (a) 접촉 동작(탐색 하강·닦기·안착·삽입)에 힘 상한·후퇴·타임아웃이 **실제 로직으로** 들어 있는지 (b) 좌표·힘·횟수가 YAML 키로 읽히는지 (c) 다른 기능 패키지를 import·호출하지 않는지(호출은 flow_node만) (d) **실행 뼈대 규약(SDD §3.2)**: 기능이 노드·서비스가 아니라 `cobot_api` 서명 그대로의 함수인지, `DSR_ROBOT2`를 직접 import하지 않는지, 콜백·타이머·다른 스레드에서 로봇 함수를 부르지 않는지, 기능 함수 안에서 `rclpy.init`·`rclpy.spin*`·노드 생성을 하지 않는지, 실패를 `Result.fail(code)`로 돌려주는지 (e) `docs/interfaces/`·`src/cobot_api/`·`src/cobot_msgs/` 변경이 있으면 이슈 링크가 있는지.
3. gh 가 있으면 `gh pr view $ARGUMENTS --json title,body,headRefName,author` 로 본문의 확인 사항 표와 실기 영향 칸을 읽는다. gh 가 없으면 사용자에게 PR 화면의 그 표를 붙여 달라고 요청한다.
4. CONTRIBUTING.md §4.1대로 판정한다. **막는 사유**: ① origin/main 과 충돌 ② 빌드 산출물·영상·DB·토큰 ③ 접촉 동작에 힘 상한·후퇴·타임아웃이 **실제 로직으로** 없음(단어가 아니라 흐름을 읽는다) ④ 실행 뼈대 규약(SDD §3.2) 위반 — `DSR_ROBOT2` 직접 import(`cobot_common` 사람별 파일의 맨 위 import 포함)·콜백·타이머·스레드에서 로봇 함수·기능 함수 안 `rclpy.init`/`spin*`/노드 생성·`signal.signal` ⑤ 남의 것을 고침(`cobot_common` 의 남의 파일: `bootstrap.py`·`config.py`·`__init__.py`·`motion.py` 황인재·`gripper.py`·`weigh.py` 민범진·`force.py` 박진용 / `cell.yaml` 은 한석형만(단 `cell.force` 절은 박진용이 값만) / `params.yaml` 남의 절 / 남의 기능 패키지·다른 기능 패키지 import) ⑥ 인터페이스 정본을 이슈·4명 확인 없이 변경 ⑦ 안전 규칙(AGENTS §3) 위반 ⑧ 명백히 깨진 코드(`cobot_api` 서명과 다름, 실패를 예외로 보고 등). 그 외(형식·하드코딩 의심·`print()`·시험 기록·실기 영향 칸·오탈자)는 참고 코멘트로만 적는다. 팀원의 테스트는 팀원 책임이므로 재검증하지 않는다.
5. 결정 (9/19 황인재 지시: "개인 브랜치 → main PR 은 PM 에이전트가 검토 후 승인/거절한다. 나한테 승인받지 않아도 된다"): 막는 사유 0이면 **승인 + Squash merge**, 있으면 **거절(Request changes)**. 실행한 뒤 황인재에게 한 줄로 보고한다.
   - 🆕 승인 코멘트에는 **검증 수준 표**를 꼭 넣는다(9/21 결정 E20): | 바뀐 것 | 확인한 것(자동 시험 두 환경 · Virtual · 실기) | 실기 — ✅ 또는 🟡 미확인(어느 V-·INT-·UT- 에서) |. PM 은 로봇을 돌리지 않으므로 PM 이 확인한 것은 코드·자동 시험까지다. 작성자가 실기 기록을 붙였으면 그 기록 파일을 적는다.
   - 승인: `gh pr review $ARGUMENTS --approve --body "<읽은 범위 · 확인한 것 · 참고 코멘트>"` → `gh pr merge $ARGUMENTS --squash --admin --subject "<PR 제목> (#번호)"`. 작성자가 `hwang-injae`(F4 세션의 PR)면 GitHub 이 자기 승인을 막으므로 검토 결과를 `gh pr comment` 로 남기고 merge 한다.
   - 거절: `gh pr review $ARGUMENTS --request-changes --body "<사유 번호 · 파일:줄 · 고치는 방법>"` (작성자가 `hwang-injae` 면 코멘트로). 황인재에게도 바로 알린다.
   - 제목에 `[hold]` · 라벨 `hold` · draft: 검토 코멘트만 남기고 merge 하지 않는다.
   - 실행 직전에 head SHA 가 읽은 것과 같은지, Actions 체크가 통과했는지 다시 본다. 다르면 다시 읽는다.
   - **위임 범위 밖 → merge 하지 않고 황인재에게 묻는다**: main 이 아닌 곳으로 가는 PR · 저장소 설정/권한/비밀값(`.github/workflows` 의 권한·토큰 변경 포함) · 안전에 걸리는데 확신이 없는 것 · 팀 규칙을 새로 정해야 하는 것 · PM 에이전트 자신이 만든 변경.
   - gh 로그인이 안 되어 있으면 검토 결과만 보고하고 황인재가 GitHub 화면에서 누른다. 로그인(`gh auth login`)은 사용자가 직접 한다.
6. merge 뒤: PM 폴더에서 `git fetch origin && git merge --ff-only origin/main`. 작성자와 영향받는 사람에게 알릴 것(참고 코멘트·후속 작업)을 황인재에게 보고한다. 일정표 상태는 다음 패치에 반영한다. **브랜치는 삭제하지 않는다**(팀장 한석형 승인 후).
