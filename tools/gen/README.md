# tools/gen — 문서 생성기 (직접 편집 금지 대상의 원본)
| 스크립트 | 만드는 것 | 실행 |
|---|---|---|
| `gen_prompts2.py` | `docs/prompts/F1~F4_*.md` (개인 프롬프트 4개, 부록 A = AGENTS.md 전문) | `python3 tools/gen/gen_prompts2.py` — AGENTS.md나 역할 내용이 바뀌면 재생성 |
| `gen_sched.py` + `extra_sheets.json` | 일정표 xlsx (구글 시트 초기 업로드용, 6시트) | `python3 tools/gen/gen_sched.py 출력.xlsx` — 정본은 구글 시트이므로 보통 재생성하지 않음 |
| `gen_arch.py` | `docs/images/system_architecture_pc.svg/.drawio` | `python3 tools/gen/gen_arch.py` 후 결과를 docs/images/로 복사 |
PM(황인재)만 실행한다. 프롬프트를 손으로 고치면 다음 재생성 때 사라지므로 생성기를 고친다.
