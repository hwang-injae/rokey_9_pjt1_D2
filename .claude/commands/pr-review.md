PR 번호 $ARGUMENTS 를 팀 규칙대로 검토하고 승인/거절을 결정한다. 저장소 루트에서 실행한다.

절차:
1. `tools/pr_check.sh $ARGUMENTS` 를 실행하고 출력을 그대로 읽는다.
2. `git diff origin/main...pr-$ARGUMENTS` 로 실제 변경을 읽는다. 특히 (a) 접촉 동작(탐색 하강·닦기·안착·삽입)에 힘 상한·후퇴·타임아웃이 **실제 로직으로** 들어 있는지 (b) 좌표·힘·횟수가 YAML 키로 읽히는지 (c) 다른 기능 노드의 서비스를 직접 부르지 않는지(호출은 flow_node만) (d) `docs/interfaces/`·`cobot_msgs` 변경이 있으면 이슈 링크가 있는지.
3. gh 가 있으면 `gh pr view $ARGUMENTS --json title,body,headRefName,author` 로 본문의 승인 조건 표(main 병합 해시·영상 파일명·통합 테스트·실기 영향)를 확인한다. gh 가 없으면 사용자에게 PR 화면의 그 표를 붙여 달라고 요청한다.
4. CONTRIBUTING.md §4.1 검토표의 8개 항목을 통과/실패로 표시한 검토 결과를 한국어로 작성한다. 실패 항목마다 "무엇을 어떻게 고쳐서 같은 브랜치에 push하라"를 한 줄로 적는다.
5. 결정: 실패 0이면 **승인 권고**, 하나라도 실패면 **거절 권고**. 사용자(황인재)에게 결과를 보여 주고 확인을 받은 뒤에만 아래를 실행한다. 확인 없이 승인·거절을 보내지 않는다.
   - 승인: `gh pr review $ARGUMENTS --approve --body "<검토 결과 요약>"`
   - 거절: `gh pr review $ARGUMENTS --request-changes --body "<실패 항목과 수정 방법>"`
   - gh 가 없으면 검토 결과 문구만 주고 사용자가 GitHub 화면에서 Approve / Request changes 를 누른다.
6. 승인 뒤 merge 는 사용자가 GitHub 에서 Squash and merge 로 한다. 브랜치 삭제는 팀장(한석형) 승인 후.
