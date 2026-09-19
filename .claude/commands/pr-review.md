PR 번호 $ARGUMENTS 를 검토한다. 평소에는 Actions가 자동 승인·merge 하므로 이 명령은 **자동 merge가 안 됐거나(체크 실패·충돌·[hold]) 로봇 안전을 사람이 봐야 할 때**만 쓴다. 저장소 루트에서 실행한다.

절차:
1. `tools/pr_check.sh $ARGUMENTS` 를 실행하고 출력을 그대로 읽는다.
2. `git diff origin/main...pr-$ARGUMENTS` 로 실제 변경을 읽는다. 특히 (a) 접촉 동작(탐색 하강·닦기·안착·삽입)에 힘 상한·후퇴·타임아웃이 **실제 로직으로** 들어 있는지 (b) 좌표·힘·횟수가 YAML 키로 읽히는지 (c) 다른 기능 패키지를 import·호출하지 않는지(호출은 flow_node만) (d) **실행 뼈대 규약(SDD §3.2)**: 기능이 노드·서비스가 아니라 `cobot_api` 서명 그대로의 함수인지, `DSR_ROBOT2`를 직접 import하지 않는지, 콜백·타이머·다른 스레드에서 로봇 함수를 부르지 않는지, 기능 함수 안에서 `rclpy.init`·`rclpy.spin*`·노드 생성을 하지 않는지, 실패를 `Result.fail(code)`로 돌려주는지 (e) `docs/interfaces/`·`src/cobot_api/`·`src/cobot_msgs/` 변경이 있으면 이슈 링크가 있는지.
3. gh 가 있으면 `gh pr view $ARGUMENTS --json title,body,headRefName,author` 로 본문의 확인 사항 표와 실기 영향 칸을 읽는다. gh 가 없으면 사용자에게 PR 화면의 그 표를 붙여 달라고 요청한다.
4. CONTRIBUTING.md §4.1대로 판정한다. **거절 사유는 두 가지뿐**: ① origin/main 최신이 PR에 병합되지 않음 ② 빌드 산출물·영상·DB·토큰이 커밋됨. 그 외(형식·하드코딩 의심·안전 단어·인터페이스 변경·테스트 기재)는 참고 코멘트로만 적는다. 예외: 로봇을 움직이는 코드에 힘 상한·후퇴·타임아웃이 실제로 없으면 사용자에게 거절을 권할 수 있다. 팀원의 테스트는 팀원 책임이므로 재검증하지 않는다.
5. 결정: 거절 사유 0이면 **승인 권고**, 있으면 **거절 권고**. 사용자(황인재)에게 결과를 보여 주고 확인을 받은 뒤에만 아래를 실행한다. 확인 없이 승인·거절을 보내지 않는다.
   - 승인: `gh pr review $ARGUMENTS --approve --body "<검토 결과 요약>"`
   - 거절: `gh pr review $ARGUMENTS --request-changes --body "<실패 항목과 수정 방법>"`
   - gh 가 없으면 검토 결과 문구만 주고 사용자가 GitHub 화면에서 Approve / Request changes 를 누른다.
6. 승인 뒤 merge 는 사용자가 GitHub 에서 Squash and merge 로 한다. 브랜치 삭제는 팀장(한석형) 승인 후.
