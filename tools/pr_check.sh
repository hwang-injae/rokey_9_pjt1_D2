#!/usr/bin/env bash
# PR 자동 검토 — 사용: tools/pr_check.sh <PR번호>   (저장소 안 어디서든)
# GitHub CLI(gh)가 있으면 제목·본문·브랜치명·작성자까지 검사, 없으면 git 기반 항목만 검사한다.
set -u
N="${1:?PR 번호를 주세요. 예: tools/pr_check.sh 12}"
cd "$(git rev-parse --show-toplevel)" || exit 1
PASS=0; FAIL=0; WARN=0
ok(){ echo "  ✅ $1"; PASS=$((PASS+1)); }
ng(){ echo "  ❌ $1"; FAIL=$((FAIL+1)); }
wn(){ echo "  ⚠️  $1"; WARN=$((WARN+1)); }

echo "== PR #$N 검토 ($(date '+%Y-%m-%d %H:%M')) =="
if [ -n "${PR_REF:-}" ]; then git branch -f "pr-$N" "$PR_REF" >/dev/null 2>&1; else
  git fetch -q origin main && git fetch -q -f origin "pull/$N/head:pr-$N" || { echo "PR #$N 을 받지 못했습니다 (번호·네트워크 확인)"; exit 2; }
fi   # PR_REF=<브랜치> 로 로컬 브랜치를 PR 대신 검사(시험용)
HEAD_SHA=$(git rev-parse --short "pr-$N"); MAIN_SHA=$(git rev-parse --short origin/main)
echo "  PR head $HEAD_SHA · origin/main $MAIN_SHA"

# 1. main 최신 병합 여부
if git merge-base --is-ancestor origin/main "pr-$N"; then ok "main 최신($MAIN_SHA)이 PR에 병합되어 있음"; else ng "origin/main 이 PR 브랜치에 없음 → 작성자가 'git merge origin/main' 후 push 해야 함"; fi

# 2. 변경 파일
FILES=$(git diff --name-only "origin/main...pr-$N")
COUNT=$(echo "$FILES" | grep -c . || true)
echo "  변경 파일 $COUNT 개"; echo "$FILES" | sed 's/^/     /'

# 3. 빌드 산출물·대용량·비밀값
if echo "$FILES" | grep -qE '^(build|install|log)/|/__pycache__/|\.(mp4|webm|mov|bag|db3|db|sqlite)$'; then ng "빌드 산출물·영상·DB 파일이 포함됨"; else ok "빌드 산출물·영상·DB 없음"; fi
if git diff "origin/main...pr-$N" | grep -qE '^\+.*(ghp_[A-Za-z0-9]{20,}|ntn_[A-Za-z0-9]{20,}|password\s*[:=])'; then ng "토큰·비밀번호로 보이는 문자열이 추가됨"; else ok "토큰·비밀번호 없음"; fi

# 4. 인터페이스 변경
if echo "$FILES" | grep -qE '^docs/interfaces/|^src/cobot_msgs/|^docs/02_'; then wn "인터페이스(IRD·cobot_msgs) 변경 포함 → 인터페이스 변경 이슈 링크와 4명 확인이 PR 본문에 있어야 함"; else ok "인터페이스 파일 변경 없음"; fi

# 5. 코드 변경이면 시험 기록 요구
if echo "$FILES" | grep -qE '^src/.*\.py$'; then
  if echo "$FILES" | grep -qE '^docs/test_logs/'; then ok "docs/test_logs/ 기록이 함께 추가됨"; else ng "src/ 코드 변경인데 docs/test_logs/ 기록이 없음 (단위기능 테스트 결과·영상 파일명)"; fi
fi

# 6. 하드코딩 의심 (파이썬 코드에서 로봇 명령 인자에 숫자 리터럴)
HC=$(git diff "origin/main...pr-$N" -- 'src/**/*.py' | grep -E '^\+' | grep -vE '^\+\+\+' | grep -E '(posx|posj|movej|movel|amovel|set_desired_force|grip|move_periodic|task_compliance_ctrl|set_velx|set_accx)\s*\(\s*\[?\s*-?[0-9]+(\.[0-9]+)?' || true)
if [ -n "$HC" ]; then wn "로봇 명령에 숫자 리터럴이 직접 들어간 줄 (YAML로 뺐는지 확인):"; echo "$HC" | head -8 | sed 's/^/     /'; else ok "로봇 명령 숫자 하드코딩 의심 없음"; fi
AP=$(git diff "origin/main...pr-$N" -- 'src/**' 'docs/**' | grep -E '^\+' | grep -vE '^\+\+\+' | grep -E '/home/[a-z]+/' || true)
if [ -n "$AP" ]; then ng "절대경로(/home/...) 추가됨:"; echo "$AP" | head -5 | sed 's/^/     /'; else ok "절대경로 없음"; fi

# 7. 접촉 동작 안전 3종 (힘제어·접촉 하강 추가 시 limit/timeout/retreat 단어 존재)
if git diff "origin/main...pr-$N" -- 'src/**/*.py' | grep -E '^\+' | grep -qE 'set_desired_force|task_compliance_ctrl|contact_down|check_force_condition|rack_place|seat|wipe'; then
  ADDED=$(git diff "origin/main...pr-$N" -- 'src/**/*.py' | grep -E '^\+')
  MISSING=""
  echo "$ADDED" | grep -qiE 'limit|max_force|force_limit' || MISSING="$MISSING 힘상한"
  echo "$ADDED" | grep -qiE 'timeout|max_s|duration' || MISSING="$MISSING 타임아웃"
  echo "$ADDED" | grep -qiE 'retreat|safe_retreat|release_force|force_off' || MISSING="$MISSING 후퇴"
  if [ -z "$MISSING" ]; then ok "접촉 동작 코드에 힘 상한·타임아웃·후퇴 단어 존재 (내용은 사람이 확인)"; else ng "접촉 동작 코드인데 다음이 안 보임:$MISSING"; fi
fi

# 8. 커밋 메시지 타입
BAD=$(git log --format='%s' "origin/main..pr-$N" | grep -vE '^(feat|fix|refactor|style|docs|test|chore|remove|perf|ci)(\([a-z0-9_-]+\))?: .+' | grep -vE '^Merge ' || true)
if [ -n "$BAD" ]; then wn "커밋 메시지 형식 벗어남 (squash merge 시 제목만 맞추면 됨):"; echo "$BAD" | head -5 | sed 's/^/     /'; else ok "커밋 메시지 타입 형식 준수"; fi

# 9. gh 가 있으면 제목·본문·브랜치명
if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
  J=$(gh pr view "$N" --json title,body,headRefName,author,baseRefName 2>/dev/null || true)
  if [ -n "$J" ]; then
    BR=$(echo "$J" | python3 -c 'import sys,json;d=json.load(sys.stdin);print(d["headRefName"])')
    TI=$(echo "$J" | python3 -c 'import sys,json;d=json.load(sys.stdin);print(d["title"])')
    BO=$(echo "$J" | python3 -c 'import sys,json;d=json.load(sys.stdin);print(d["body"] or "")')
    echo "  브랜치 $BR · 제목 '$TI' · 작성자 $(echo "$J" | python3 -c 'import sys,json;print(json.load(sys.stdin)["author"]["login"])')"
    echo "$BR" | grep -qE '^[a-z0-9-]+/[0-9]{8}-[A-Za-z0-9-]+-[a-z0-9-]+$' && ok "브랜치 이름 형식 준수" || ng "브랜치 이름이 {이름}/{YYYYMMDD}-{taskID}-{설명} 형식이 아님"
    echo "$TI" | grep -qE '^(feat|fix|refactor|style|docs|test|chore|remove|perf|ci)(\([a-z0-9_-]+\))?: .+' && ok "PR 제목 형식 준수" || ng "PR 제목이 <타입>(<스코프>): <제목> 형식이 아님"
    echo "$BO" | grep -qE '_______|________' && ng "PR 본문 승인 조건 표에 빈칸(____)이 남아 있음" || ok "PR 본문 승인 조건 표 채움"
    echo "$BO" | grep -qE '[0-9]{8}_(TC|INT|V)[0-9a-z-]+_.+\.mp4' && ok "영상 파일명 기재" || ng "본문에 영상 파일명(YYYYMMDD_TCxx_기능_담당_시도N.mp4)이 없음"
    echo "$BO" | grep -qiE '통합 테스트.*(mock|실기|INT)' && ok "통합 테스트 결과 기재" || wn "본문에 통합 테스트 결과(mock/실기·INT 번호)가 안 보임"
    echo "$BO" | grep -qE '\[x\].*(Virtual 모드에서 동작 확인|실기\(Real\) 동작에 영향 없음|실기 동작에 영향 있음)' && ok "실기 영향 칸 체크됨" || ng "실기 영향 칸이 비어 있음"
  fi
else
  wn "gh CLI 미설치/미로그인 → 브랜치명·제목·본문(영상 파일명·통합 테스트·실기 영향)은 GitHub 화면에서 직접 확인"
fi

echo "== 결과: 통과 $PASS · 실패 $FAIL · 확인 필요 $WARN =="
if [ "$FAIL" -gt 0 ]; then echo "→ 거절(Request changes) 권고"; exit 1; else echo "→ 승인 가능 (⚠️ 항목은 사람이 확인)"; fi
