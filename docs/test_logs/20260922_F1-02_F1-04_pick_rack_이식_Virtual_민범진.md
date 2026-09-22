# F1-02 pick · F1-04 rack_place 이식 — Virtual 검증 (민범진 · 9/22 16:1x · PM 승인 이식)

| | |
|---|---|
| 무엇 | 한석형 실기 대본 `rig_bowl_scenario_real.py`(9/21~22 실기 검증)의 집기·재파지·적재 동작을 `f1.pick()`·`f1.rack_place()` 로 옮김 |
| 분담 | 한석형 담당 함수 — **PM(황인재) 9/22 15:5x 승인**으로 민범진이 이식(저녁 INT-12a·12b 전제). 결정기록 E27 요청 |
| 검증 수준 (E20) | 🟢 **가상**(이동·순서·도달 — `_must_arrive` 통과 = 좌표 도달) · 자동 시험 385 · 🔴 **실기 미확인** |
| 브랜치 | `beomjin/20260922-F1-02-pick-rack-port` |

## 1. 가상 로봇 결과 — `rig_int12.py --virtual` (무게·그리퍼·접촉만 가짜, 이동은 진짜)

| 구간 | 회차 | 결과 | 회차 시간 |
|---|---|---|---|
| **12a 그릇** pick(RET_B) → move_to(WEIGH) → leftover_loop | 2/2 | ✅ 접근점 → 하강 → grip 판정(영점 뺀 2.15 ✅) → 되올라옴 → 저울 → 무게 | 11.0 s |
| **12b 그릇** pick(SPONGE_BED_B) → dip ×2 → shake → rack_place(RACK_B1) → HOME | 2/2 | ✅ 재파지 → 헹굼 → **RINSE 접근점 → HOME → RACK_B1_VIA(J6 72) → RACK_B1(C −172.6) → 70 mm 자유 하강 → 30 mm 감시 → 놓기 → y −25 · z +100** | 57.0 s |
| **12b 컵** pick(SPONGE_BED_C) → dip ×2 → shake → rack_place(RACK_C1) → HOME | 1/1 | ✅ regrip(posj) → z 250 → 헹굼 → RINSE 접근점 → z 250 → RACK_C_VIA → RACK_C1 → 놓기 → z +92 · y −117 | 53.5 s |

- 이동 실패(`MoveIncomplete`) 0 — 새로 넣은 자세(RACK_B_VIA · RACK_B1_VIA · RACK_C_VIA · RET_B 접근점 x 531.78 · RACK_B1 C −172.6) 전부 도달
- `rig_int12.py check`: pick · rack_place **"구현돼 있다"** → 점검 통과
- 문지기(TS-07)는 에뮬레이터에서 건너뛴다(툴·TCP 이름이 실기 등록값과 달라서) — 실기에서는 그대로 확인

## 2. 가상에서 확인 **안 된** 것 — 전부 실기로 (첫 실기 vel_scale 0.3 · 손은 E-Stop)

| 무엇 | 왜 | 볼 것 |
|---|---|---|
| 그릇 실제 파지·폭 판정 | 가상엔 그리퍼 없음 | 영점 뺀 폭 2.15 ± 0.6 · 빈 구역이면 EMPTY_ZONE |
| RET_B 접근점 x 529 → 531.78 (곧게 내려가 2.8 mm 안 어긋나게) | 파일 주석 처방 적용 · 실기 0회 | 하강 끝에서 그릇 벽이 손가락 사이에 오는지 |
| **RACK_B1 손목 반전 경유점**(J6 72 · C −172.6) | 한석형 대본 9/22 경로 · 함수로는 첫 실기 | 경유점에서 손목이 돌 때 케이블 · 칸 진입 방향 |
| 삽입 감시 30 mm(`contact_down` 15 N) | 가상엔 힘 없음 | 정상 삽입이 RACK_JAM 으로 오판되지 않는지(seat_tol 3 mm) |
| 컵 재파지 뒤 z 250 상승 · 컵 칸 진입 | | 컵 낙하(눈으로 · E19) |
| RINSE → HOME(그릇) 이동 | 수조(오른쪽)에서 HOME 관절 이동 | 수조 벽 |

## 3. 옮기면서 결정한 것 (PM · 한석형 확인 요청)

| # | 결정 | 근거 |
|---|---|---|
| ① | 재파지가 빈손이면 **GRIP_FAIL**(pause) — EMPTY_ZONE 이 아님 | EMPTY_ZONE → next_zone 은 구역을 건너뛰어 **홈에 있는 용기를 잃는다**. GRIP_FAIL 은 CODES 에 있고 정책 pause(E12) |
| ② | `rack_place` 는 **RINSE 에서 시작**한다고 전제 — 먼저 RINSE 접근점으로 곧게 올라온다 | IRD §8 순서(헹굼 뒤 적재). 수조 안에서 곧장 관절 이동하면 용기가 수조 벽을 친다 |
| ③ | RACK_B1 은 `via: RACK_B1_VIA`(J6 +180) + approach/posx **C +180** | 한석형 대본 800~880줄 — "접근 뒤 J6 180°" 를 자세에 넣은 것. 황인재 9/21 값(C 7.4)은 회전 전 값 |
| ④ | 그릇 적재 전 **HOME 경유** · 컵은 z 250 만 | 한석형 대본(home_keep_j6). 🟡 대본의 "J6 유지" 는 못 옮김(cc 에 그런 이동이 없다) — HOME J6 0 으로 간다 · 첫 실기에서 케이블 확인 |
| ⑤ | 삽입 = (up − `f1.insert_approach_mm` 30) 자유 하강 + 마지막 30 mm `contact_down(insert_limit_n 15)` · `rack.seat_tol_mm` 3 | 규칙 2(힘 상한·후퇴·타임아웃) · 100 mm 를 전부 감시하면 timeout_s 10 을 넘는다 |
| ⑥ | RACK_FULL 은 판정하지 않음 | 센서 없음 — 찬 칸에 넣으면 걸려 RACK_JAM → retry:1 → isolate |

## 4. 다시 돌리기
```bash
python3 src/f2_sense_flow/test/rig_int12.py check                                   # 로봇 없이
터미널 1: sod && sodvir      터미널 2: soc && python3 src/f2_sense_flow/test/rig_int12.py b --virtual --kind BOWL -n 2 < /dev/null
실기:     PREWASH_VEL_SCALE=0.3 python3 src/f2_sense_flow/test/rig_int12.py a --kind BOWL -n 1   # 문지기 → 진짜 집기
```
