오늘 작업 시작 루틴을 대신 진행한다. 인자 $ARGUMENTS = taskID와 짧은 설명 (예: `F1-02 pick-search`). 비어 있으면 묻는다.

1. `git status`·`git branch`로 현재 상태를 확인한다. 커밋 안 한 변경이 있으면 먼저 어떻게 할지(커밋/stash) 묻는다.
2. `git fetch origin && git checkout main && git pull origin main` 실행.
3. 브랜치 이름을 `{이름}/{오늘 YYYYMMDD}-{taskID}-{설명}` 형식으로 만들어(이름은 GitHub ID 소문자, 설명은 영문 kebab-case) `git checkout -b`로 생성한다. 이미 그 taskID 브랜치가 있으면 그리로 이동하고 `git merge origin/main`.
4. 이 taskID의 완료 기준을 `docs/03_설계_SDD.md` §9(TC/INT/V 표)에서 찾아 한 줄로 보여 주고, 필요한 로봇 슬롯(R 표시)이면 오늘 슬롯이 맞는지 사용자에게 확인시킨다.
5. "이제 `/f?`로 STEP을 이어가거나, 끝나면 `/wrap`으로 마무리" 안내.
