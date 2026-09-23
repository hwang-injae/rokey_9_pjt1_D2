# tools/gen — 문서 생성기 (직접 편집 금지 대상의 원본)
| 스크립트 | 만드는 것 | 실행 |
|---|---|---|
| (아키텍처 그림) | `docs/images/system_architecture_pc.html` · `.archify.json` · `.png` | 9/23 부터 **Archify**(https://github.com/tt-a1i/archify)로 그린다 — 명세 `.archify.json` 을 고친 뒤 `node bin/archify.mjs deliver architecture <명세> <html> --quality showcase` · 캡처는 `google-chrome --headless=new --screenshot` |
PM(황인재)만 실행한다. 프롬프트를 손으로 고치면 다음 재생성 때 사라지므로 생성기를 고친다.

## gen_todo.py — 담당별 할 일 시트

구글 시트(정본)의 **현재 내용**을 읽어 사람별·날짜별 체크리스트 4장(`할일_이름`)을 만든다. PM이 시트에서 고친 내용이 그대로 반영된다.

```bash
python3 tools/gen/gen_todo.py ../_upload/prewash_담당별_할일.xlsx
```

구글 시트에서 `파일 > 가져오기 > 업로드 > 새 시트 삽입`으로 넣는다. 기존 시트는 바뀌지 않는다. 일정이 바뀌면 다시 만들어 `할일_*` 시트만 지우고 다시 넣는다. 쉬운 말 설명은 `gen_todo.py`의 `EASY` 사전에 있다. 새 ID는 사전에 없으면 작업명이 그대로 나온다.

## xlsx_patch.py · patch_YYYYMMDD_*.py — 일정표를 "그 자리에서" 고치기

PM이 구글 시트에서 직접 고친 내용(행 추가·날짜 이동·상태)을 그대로 둔 채 몇 개 셀·행만 바꿀 때 쓴다. 일정표 정본은 구글 시트이고 PM이 직접 고친다. 초기 업로드용 생성기(`gen_sched.py`)는 9/19에 삭제했다 — 일정 변경은 항상 이 방식으로 한다.

```bash
python3 tools/gen/patch_20260919_weekend.py ../_upload/prewash_일정표_0919n.xlsx   # 최신 (9/19 오후 재계획 v5.0: 주말 저녁 없음 · 재분담 · 게이트) → tools/gen/sheet_push.sh 로 올린다
```

지금 시트를 내려받아 변경만 얹은 xlsx를 만든다. **올리기(PM PC, 9/19~)**: `tools/gen/sheet_push.sh ../_upload/prewash_일정표_XXXX.xlsx` — rclone(remote `gdrive`, 황인재가 1회 로그인)으로 드라이브의 **같은 파일·같은 주소**에 새 버전으로 올린다. 올리기 전에 정본 ID 확인·현재 시트 백업(`../_upload/backup/`)·"xlsx를 만든 뒤 시트가 바뀌었으면 중단", 올린 뒤에 파일 ID·내용 검증을 한다. 되돌리기는 드라이브의 버전 기록 또는 백업 파일. rclone이 없으면 예전처럼 구글 시트에서 `파일 > 가져오기 > 업로드 > 스프레드시트 바꾸기`. 내려받은 뒤에 시트를 고쳤다면 다시 실행한다. PM이 시트에서 직접 고친 것은 `python3 tools/sched_diff.py`로 본다(지난 확인 뒤로 바뀐 담당·상태·진행·칸). 새 변경은 `patch_날짜_이름.py`를 복사해 만든다(`Book.from_live` → `sheet().find/set/insert` → `save`).

패치는 Time Line·상세·변경이력을 고친 뒤 **`할일_*` 시트를 고친 Time Line에서 다시 채운다**(`xlsx_patch.rebuild_todo` + `gen_todo.person_entries`). 그래서 할 일 시트의 ✓ 표시는 Time Line의 상태(완료)에서 나온다 — 할 일 시트에 손으로 찍은 체크는 다음 패치 때 사라진다. `patch_20260918_s4.py`는 9/19에 시트 적용이 끝났다 — 다음 패치를 만들 때 복사해 쓰는 **예시**로 남겨 둔다(다시 실행해도 새 행이 중복되지는 않는다).



`patch_20260919_weekend.py` 가 9/19 오후 이후의 **유일한** 일정표 패치다(v5.0 → v22.x · 변경이력은 이 파일 안 HISTORY). 옛 패치(s4·audit·rebalance)와 프롬프트·아키텍처 생성기는 9/23 정리 때 지웠다(git 이력에 있음). `patch_20260919_audit.py`(v4.3~4.14)와 `patch_20260919_rebalance.py`는 시트 적용이 끝났다 — **다시 실행하지 않는다**(재계획에서 옮긴 칸·담당이 되돌아간다). 진행 상태는 PM이 시트에서 직접 고치거나 최신 패치의 `EDIT`에 `status`를 넣는다.
