오늘 작업 마무리 루틴을 대신 진행한다.

1. `git status`로 변경 파일을 보여 주고, `build/ install/ log/ *.mp4 rewash.db`가 섞여 있으면 제외한다.
2. 커밋 메시지를 `<타입>(<스코프>): <제목>` 형식으로 제안하고(타입 10종, 스코프 f1 f2 flow f3 f4 common msgs cell bringup docs setup), 사용자 확인 후 `git add <파일들>`·`git commit`.
3. `git push -u origin <현재 브랜치>` 실행(하루 1회 이상 규칙). 거부되면 가이드 5-8 표로 해결.
4. 단위기능 테스트를 했으면 `docs/test_logs/YYYYMMDD_TCxx.md` 기록이 있는지, 영상 파일명(`YYYYMMDD_TCxx_기능_담당_시도N.mp4`)이 적혔는지 확인한다. 없으면 양식을 만들어 준다.
5. PR을 올릴 단계면(단위 테스트 통과 + `git merge origin/main` + 통합 테스트 완료) PR 제목과 본문 "승인 조건" 표를 채운 초안을 만들어 준다. Reviewer는 hwang-injae.
6. 마지막으로 진척 보고 5줄(taskID·완료 기준 수치 / 인터페이스 변경 / 블로커 / 로봇 슬롯 / 9/30 리스크)을 팀 채널 복붙용으로 만든다.
