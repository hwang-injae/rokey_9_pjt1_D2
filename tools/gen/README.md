# tools/gen — 문서 생성기 (직접 편집 금지 대상의 원본)
| 스크립트 | 만드는 것 | 실행 |
|---|---|---|
| `gen_prompts2.py` | `docs/prompts/F1~F4_*.md` (개인 프롬프트 4개, 부록 A = AGENTS.md 전문) | `python3 tools/gen/gen_prompts2.py` — AGENTS.md나 역할 내용이 바뀌면 재생성 |
| `gen_arch.py` | `docs/images/system_architecture_pc.svg/.drawio` | `python3 tools/gen/gen_arch.py` 후 결과를 docs/images/로 복사 |
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
python3 tools/gen/patch_20260919_tasks.py ../_upload/prewash_일정표_0919.xlsx   # 최신 (구조 변경 후속: 새 작업·시험 방법)
```

지금 시트를 내려받아 변경만 얹은 xlsx를 만든다. 구글 시트에서 `파일 > 가져오기 > 업로드 > 스프레드시트 바꾸기`. 내려받은 뒤에 시트를 고쳤다면 다시 실행한다. 새 변경은 `patch_날짜_이름.py`를 복사해 만든다(`Book.from_live` → `sheet().find/set/insert` → `save`).

패치는 Time Line·상세·변경이력을 고친 뒤 **`할일_*` 시트를 고친 Time Line에서 다시 채운다**(`xlsx_patch.rebuild_todo` + `gen_todo.person_entries`). 그래서 할 일 시트의 ✓ 표시는 Time Line의 상태(완료)에서 나온다 — 할 일 시트에 손으로 찍은 체크는 다음 패치 때 사라진다. `patch_20260918_s4.py`는 9/19에 시트 적용이 끝났다 — 다음 패치를 만들 때 복사해 쓰는 **예시**로 남겨 둔다(다시 실행해도 새 행이 중복되지는 않는다).
