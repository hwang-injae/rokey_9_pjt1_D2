# tools/gen — 문서 생성기 (직접 편집 금지 대상의 원본)
| 스크립트 | 만드는 것 | 실행 |
|---|---|---|
| `gen_prompts2.py` | `docs/prompts/F1~F4_*.md` (개인 프롬프트 4개, 부록 A = AGENTS.md 전문) | `python3 tools/gen/gen_prompts2.py` — AGENTS.md나 역할 내용이 바뀌면 재생성 |
| `gen_sched.py` + `extra_sheets.json` | 일정표 xlsx (구글 시트 초기 업로드용, 6시트) | `python3 tools/gen/gen_sched.py 출력.xlsx` — 정본은 구글 시트이므로 보통 재생성하지 않음 |
| `gen_arch.py` | `docs/images/system_architecture_pc.svg/.drawio` | `python3 tools/gen/gen_arch.py` 후 결과를 docs/images/로 복사 |
PM(황인재)만 실행한다. 프롬프트를 손으로 고치면 다음 재생성 때 사라지므로 생성기를 고친다.

## gen_todo.py — 담당별 할 일 시트

구글 시트(정본)의 **현재 내용**을 읽어 사람별·날짜별 체크리스트 4장(`할일_이름`)을 만든다. PM이 시트에서 고친 내용이 그대로 반영된다.

```bash
python3 tools/gen/gen_todo.py ../_upload/prewash_담당별_할일.xlsx
```

구글 시트에서 `파일 > 가져오기 > 업로드 > 새 시트 삽입`으로 넣는다. 기존 시트는 바뀌지 않는다. 일정이 바뀌면 다시 만들어 `할일_*` 시트만 지우고 다시 넣는다. 쉬운 말 설명은 `gen_todo.py`의 `EASY` 사전에 있다. 새 ID는 사전에 없으면 작업명이 그대로 나온다.

## xlsx_patch.py · patch_YYYYMMDD_*.py — 일정표를 "그 자리에서" 고치기

PM이 구글 시트에서 직접 고친 내용(행 추가·날짜 이동·상태)을 그대로 둔 채 몇 개 셀·행만 바꿀 때 쓴다. `gen_sched.py`로 다시 만들면 PM의 수정이 사라지므로, 9/18 이후 일정 변경은 이 방식으로 한다.

```bash
python3 tools/gen/patch_20260918_ts01.py ../_upload/prewash_일정표_TS01반영.xlsx
```

지금 시트를 내려받아 변경만 얹은 xlsx를 만든다. 구글 시트에서 `파일 > 가져오기 > 업로드 > 스프레드시트 바꾸기`. 내려받은 뒤에 시트를 고쳤다면 다시 실행한다. 새 변경은 `patch_날짜_이름.py`를 복사해 만든다(`Book.from_live` → `sheet().find/set/insert` → `save`).
