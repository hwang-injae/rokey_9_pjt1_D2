#!/usr/bin/env bash
# 패치로 만든 xlsx 를 구글 드라이브의 일정표(정본) **같은 파일·같은 주소**에 새 버전으로 올린다. PM(황인재) PC 전용.
#   사용:  tools/gen/sheet_push.sh ../_upload/prewash_일정표_XXXX.xlsx
#   준비:  rclone 에 remote "gdrive" 가 있어야 한다(sudo apt install rclone → rclone config, 황인재가 1회 로그인). 토큰은 이 스크립트가 읽거나 출력하지 않는다.
#   하는 일: ① 드라이브의 파일 ID 가 정본과 같은지 ② 지금 시트를 백업 ③ xlsx 를 만든 뒤에 시트가 바뀌었으면 중단(그 사이의 수정을 덮어쓰지 않게)
#           ④ 업로드(드라이브에 버전 기록이 남아 되돌릴 수 있다) ⑤ 파일 ID 가 그대로인지 ⑥ 시트를 다시 읽어 올린 것과 같은지 확인
#   올린 뒤: 시트를 브라우저에 열어 둔 사람은 새로고침한다(열린 화면에서 계속 고치면 옛 내용으로 덮어쓸 수 있다).
set -euo pipefail
SID='1ikTAYTa8bgZofF_3RgP5jDoOipSZBPB1'            # 일정표 파일 ID (tools/gen/livesheet.py 의 SID 와 같다)
FOLDER='1t58F08_auBRa_q7c4KeNirLKR6CKa4hU'         # 그 파일이 들어 있는 드라이브 폴더
NAME='prewash_개발일정.xlsx'
REMOTE="${PREWASH_RCLONE_REMOTE:-gdrive}"
XLSX="${1:?올릴 xlsx 경로를 준다. 예: tools/gen/sheet_push.sh ../_upload/prewash_일정표_0919g.xlsx}"
FORCE="${2:-}"                                      # --force : ③ 을 건너뛴다(시트가 바뀐 것을 알고도 덮어쓸 때만)
ROOT="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
BACKUP_DIR="${PREWASH_SCHED_BACKUP:-$ROOT/../_upload/backup}"
RC=(rclone --drive-root-folder-id "$FOLDER")

[ -f "$XLSX" ] || { echo "❌ 파일이 없다: $XLSX"; exit 2; }
python3 - "$XLSX" <<'PY' || { echo "❌ xlsx 가 아니거나 시트 구성이 다르다"; exit 2; }
import sys, zipfile
z = zipfile.ZipFile(sys.argv[1]); wb = z.read('xl/workbook.xml').decode()
need = ['Time Line', '상세(산출물·완료기준)', '마일스톤·로봇 슬롯', '완료 목록', '규칙', '변경이력']
sys.exit(0 if all(n in wb for n in need) else 1)
PY

remote_info() {   # 출력: "<ID> <ModTime(epoch)> <이름이 같은 파일 수>"
  "${RC[@]}" lsjson "$REMOTE:" --files-only | python3 -c "
import sys, json, datetime
fs = [f for f in json.load(sys.stdin) if f['Name'] == '$NAME']
f = fs[0] if fs else {'ID': '-', 'ModTime': '1970-01-01T00:00:00Z'}
t = datetime.datetime.fromisoformat(f['ModTime'].replace('Z', '+00:00')).timestamp()
print(f['ID'], int(t), len(fs))"
}

read -r RID RMOD RCOUNT < <(remote_info)
[ "$RCOUNT" = 1 ] && [ "$RID" = "$SID" ] || { echo "❌ ① 드라이브 폴더에 '$NAME' 이 $RCOUNT 개이고 ID 는 $RID — 정본($SID)과 다르다. 올리지 않는다"; exit 3; }
echo "① 정본 확인: $NAME ($RID)"

mkdir -p "$BACKUP_DIR"
BK="$BACKUP_DIR/prewash_개발일정_$(date +%Y%m%d_%H%M%S).xlsx"
"${RC[@]}" copyto "$REMOTE:$NAME" "$BK"
echo "② 백업: $BK"

LMOD=$(stat -c %Y "$XLSX")
if [ "$RMOD" -gt "$LMOD" ] && [ "$FORCE" != "--force" ]; then
  echo "❌ ③ xlsx 를 만든 뒤($(date -d @"$LMOD" '+%H:%M:%S'))에 시트가 바뀌었다($(date -d @"$RMOD" '+%H:%M:%S')). 패치를 다시 실행해 새로 만든 뒤 올린다 (바뀐 내용: python3 tools/sched_diff.py --keep)"; exit 4
fi
echo "③ xlsx 를 만든 뒤 시트 변경 없음"

"${RC[@]}" copyto "$XLSX" "$REMOTE:$NAME" --ignore-times
read -r RID2 RMOD2 RCOUNT2 < <(remote_info)
[ "$RCOUNT2" = 1 ] && [ "$RID2" = "$SID" ] || { echo "❌ ⑤ 올린 뒤 파일 ID·개수가 달라졌다(ID $RID2, $RCOUNT2 개). 드라이브를 직접 확인한다. 백업: $BK"; exit 5; }
echo "④⑤ 업로드 완료 · 파일 ID 그대로 ($RID2)"

sleep 5
if python3 "$ROOT/tools/sched_diff.py" "$XLSX" | tee /dev/stderr | grep -qE '^  [~+-] |^== .* == \(행'; then
  echo "⚠ ⑥ 시트를 다시 읽은 내용이 올린 파일과 다르다(구글 쪽 반영이 늦을 수 있다 — 1분 뒤 python3 tools/sched_diff.py \"$XLSX\" 로 다시 확인). 백업: $BK"; exit 6
fi
echo "⑥ 검증: 시트 = 올린 파일  ✅  (열어 둔 브라우저는 새로고침)"
