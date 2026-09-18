# 인터페이스 요구사항 문서 (IRD)
## ReWash-Cell — 노드 간 계약 정본

| 항목 | 내용 |
|---|---|
| 문서 ID | IRD-REWASH-001 · v2.0 (2026-09-18) |
| 상위 | [01_요구사항_BR-SR.md](01_요구사항_BR-SR.md) §5.4 |
| 정본 파일 | [interfaces/](interfaces/) 의 `*.srv` `*.msg` — 이 문서와 파일이 다르면 **파일이 정본** |
| 변경 규칙 | 필드 추가·삭제·타입 변경은 `.github/ISSUE_TEMPLATE/interface_change.md` 이슈 → 4명 확인 → PR. 혼자 바꾸지 않는다. |

🚨 **이 문서가 4명 동시 개발의 약속이다.** 이 약속이 있어서 남의 코드가 없어도 내 노드를 만들고 시험할 수 있다.

---

## 1. 원칙
1. 기능 노드(f1·f2·f3)는 **서비스 제공자**다. 부르는 쪽은 `flow_node` 하나뿐이다. 기능 노드끼리는 서로 부르지 않는다.
2. 모든 서비스는 `ok(bool)` + `code(string)`를 반환한다. `ok=false`면 `code`에 실패 코드.
3. 물리 인계는 **정해진 스테이션 위치**로만 한다. F1이 놓은 자리에서 F3가 시작한다. 그래서 각 노드는 용기를 손으로 놓아 두고 단독으로 시험할 수 있다.
4. 로봇 API는 `cobot_common`(두산 API를 감싼 공용 로봇 함수 모음)만 쓴다. 각 노드가 DSR API를 직접 부르지 않는다.
5. 모든 ID는 아래 §2 문자열을 그대로 쓴다(대문자, ROS·YAML·기록·HMI 동일).

## 2. 공통 ID (IR-05)
| 분류 | 값 | 설명 |
|---|---|---|
| 용기 종류 `kind` | `BOWL` `CUP` | |
| 툴 `tool` | `SPONGE`(그릇용 수세미 툴) `BRUSH`(컵용 수세미 솔) | |
| 반납 구역 `zone_id` | `RET_B` `RET_C` | 공정 입구. 구역 안 위치·겹침 자유 → 탐색 파지 |
| 팔레트 칸 `rack_slot` | `RACK_B1` `RACK_B2` / `RACK_C1` `RACK_C2` `RACK_C3` `RACK_C4` | 공정 출구. 그릇 2칸·컵 4칸 |
| 스테이션 `station` | `HOME` `WEIGH` `WASTE` `SPONGE_BED_B` `SPONGE_BED_C` `TOOL_SPONGE` `TOOL_BRUSH` `SOAP` `RINSE` `ISOLATE` | 작업대 위 고정 위치 |
| 실패 코드 `code` | `OK` `GRIP_FAIL` `EMPTY_ZONE` `LEFTOVER` `LEFTOVER_REMAIN` `SEAT_FAIL` `TOOL_FAIL` `FORCE_LIMIT` `TIMEOUT` `RACK_JAM` `RACK_FULL` `ROBOT_ERROR` `STOPPED` | |
| 흐름 상태 `step` | `IDLE` `PICK` `WEIGH` `SHAKE` `SEAT` `SOAP` `WIPE` `RINSE` `RACK` `ISOLATE` `DONE` `ERROR` `PAUSED` | `PICK` 안에 탐색 포함 |

## 3. F1 파지·이송·적재 (IR-01) · 한석형
| 서비스 | 요청 | 응답 | 비고 |
|---|---|---|---|
| `/f1/pick` | `zone_id`, `kind` | `ok, code, width_mm, attempts, offset_x_mm, offset_y_mm` | **탐색 파지**: 구역 탐색점 순회 → 힘 감시 하강 → 파지 → 폭 판정. 폭 범위 밖이면 놓고 다음 점. 최대 횟수 초과 → `EMPTY_ZONE` |
| `/f1/place` | `station` | `ok, code` | 상공 → 하강 → 놓기 → 후퇴 |
| `/f1/move_to` | `station`, `carrying` | `ok, code` | 안전 높이 경유, 들고 있으면 저속 |
| `/f1/tool` | `tool`, `action`(`PICK`/`RETURN`) | `ok, code, width_mm` | 홀더에서 툴 픽업·반납. 폭 범위 밖 → `TOOL_FAIL` |
| `/f1/rack_place` | `rack_slot`, `kind` | `ok, code` | 지정 각도 삽입, 순응 + 삽입력 감시, 걸림 → `RACK_JAM` |
| `/f1/home` | — (Trigger) | `ok, code` | 안전 자세 복귀 |

`GRIP_FAIL`은 pick 내부 재탐색으로 소화된다. flow가 받는 코드는 `OK` 또는 `EMPTY_ZONE`(또는 `ROBOT_ERROR`)이다.

## 4. F2 무게·털기·헹굼 (IR-02) · 민범진
| 서비스 | 요청 | 응답 | 비고 |
|---|---|---|---|
| `/f2/weigh` | `kind` | `ok, code, weight_g` | WEIGH 자세 정지 후 N회 평균 |
| `/f2/leftover_loop` | `kind`, `max_rounds` | `ok, code, weight_before_g, weight_after_g, rounds` | 판정→털기→재측정 반복. 초과 지속 → `LEFTOVER_REMAIN`. 임계 미만은 `OK` |
| `/f2/shake` | `mode`(`WASTE`/`RINSE`), `count` | `ok, code` | 진폭·속도는 f2.yaml |
| `/f2/dip` | `station`(`SOAP`/`RINSE`), `count` | `ok, code` | 담금 모션 |

## 5. F3 접촉 닦기 (IR-03) · 박진용
| 서비스 | 요청 | 응답 | 비고 |
|---|---|---|---|
| `/f3/seat` | `kind` | `ok, code, offset_mm` | 홈 안착 + Move Periodic 탐색. 한도 초과 → `SEAT_FAIL` |
| `/f3/soap` | `count` | `ok, code` | 툴 든 채 세제 수조 담금 |
| `/f3/wipe` | `kind` | `ok, code, force_log_path, duration_s` | BOWL: 힘제어 나선 / CUP: 회전·상하. 상한 초과 → `FORCE_LIMIT` |

툴 픽업·반납은 F1 `/f1/tool`을 flow가 호출한다. F3는 "툴을 쥔 상태"에서 시작한다.

## 6. flow ↔ HMI (IR-04) · 민범진(flow) · 황인재(HMI)
| 인터페이스 | 형식 | 내용 |
|---|---|---|
| `/flow/start` | srv `std_srvs/Trigger` | 구역 계획대로 전부 처리 시작 (IDLE에서만) |
| `/flow/stop` | srv `std_srvs/Trigger` | 현재 서비스 완료 후 정지 → `PAUSED` (HMI의 소프트 정지 버튼) |
| `/flow/resume` | srv `std_srvs/Trigger` | 정지·오류 지점부터 재개 |
| `/flow/state` | msg `FlowState` @2 Hz | 아래 정의. HMI는 2 s 이상 안 오면 "연결 끊김" 표시 |
| `/flow/event` | msg `FlowEvent` | 용기 1개 완료·격리·오류마다 1건 → HMI가 SQLite에 저장 |
| HMI 브리지 | REST `POST /api/start` `/api/stop` `/api/resume`, `GET /api/state`, `GET /api/history`, WS `/ws/state` | FastAPI가 rclpy로 중계 (PC-B) |

하드웨어 비상정지는 로봇 E-Stop이다. HMI 버튼은 소프트 정지이며 화면에 항상 보이게 둔다.

## 7. 메시지 정의 (정본: [interfaces/](interfaces/))
```
# FlowState.msg
string step            # §2 흐름 상태
string kind            # 현재 용기 BOWL/CUP/""
string zone_id         # 현재 반납 구역
uint16 done_bowl
uint16 done_cup
uint16 isolated
uint16 target_bowl     # 계획 수량 (진행률 계산용)
uint16 target_cup
uint16 sponge_uses
uint16 soap_dips
uint16 rinse_dips
string last_code
string message
builtin_interfaces/Time stamp

# FlowEvent.msg
builtin_interfaces/Time stamp
string kind
string zone_id
string rack_slot
uint8 attempts          # 탐색 파지 시도 횟수
float32 weight_before_g
float32 weight_after_g
string result           # DONE / ISOLATED / ERROR / SKIPPED
string code
float32 duration_s
string force_log_path
```
서비스 파일: `F1Pick.srv` `F1Place.srv` `F1MoveTo.srv` `F1Tool.srv` `F1RackPlace.srv` `F2Weigh.srv` `F2LeftoverLoop.srv` `F2Shake.srv` `F2Dip.srv` `F3Seat.srv` `F3Soap.srv` `F3Wipe.srv` (`/f1/home`과 `/flow/*`는 `std_srvs/Trigger`).

## 8. 호출 순서 (flow_node)
```
plan (flow.yaml): [ {zone: RET_B, kind: BOWL, count: 2}, {zone: RET_C, kind: CUP, count: 2} ]
구역마다 count 회 또는 EMPTY_ZONE 까지 반복:
BOWL: pick(RET_B) → move_to(WEIGH) → leftover_loop → move_to(SPONGE_BED_B) → place → seat
      → tool(SPONGE,PICK) → soap(2~3) → wipe(BOWL) → tool(SPONGE,RETURN)
      → pick 대신 place 역순: move_to(SPONGE_BED_B)에서 그릇 재파지(프리셋 위치) → dip(RINSE) → shake(RINSE)
      → rack_place(RACK_Bn) → home
CUP : 동일, SPONGE_BED_C · tool(BRUSH) · wipe(CUP) · RACK_Cn
```
스펀지 홈에서의 재파지는 위치가 고정이므로 탐색 없이 `/f1/pick`에 `zone_id=SPONGE_BED_B/C`를 주면 f1이 고정 프리셋으로 잡는다(탐색점 1개).

**실패 정책 (flow.yaml)**
| 코드 | 처리 |
|---|---|
| `EMPTY_ZONE` | 구역 종료 → 다음 구역 (기록 SKIPPED) |
| `LEFTOVER_REMAIN` `SEAT_FAIL` | ISOLATE 후 다음 용기 |
| `FORCE_LIMIT` `TIMEOUT` `RACK_JAM` `TOOL_FAIL` | 후퇴 후 재시도 1회 → ISOLATE |
| `RACK_FULL` | PAUSED + HMI 알림 → 팔레트 교체 후 resume |
| `ROBOT_ERROR` | PAUSED → 운영자 확인 후 resume |
| stop 버튼 | 현재 서비스 완료 후 PAUSED → resume |

## 9. 설정 파일 소유 (IR-07)
| 파일 | 소유 | 내용 |
|---|---|---|
| `f1.yaml` | 한석형 | 프리셋(kind별 폭·힘·접근 자세), 스테이션·구역·칸 좌표, **탐색점 목록·최대 횟수·하강 힘 상한**, 속도 상한, 안전 높이 |
| `f2.yaml` | 민범진 | 빈 용기 기준 무게, 임계, 평균 횟수, 털기 진폭·속도·횟수, 담금 깊이·시간 |
| `f3.yaml` | 박진용 | 목표 힘·상한, 궤적, 탐색 진폭·주기·한도, 컵 회전·스트로크 |
| `flow.yaml` | 민범진 | 구역 계획(plan), 실패 정책, 칸 배정, 소모품 임계 |
| `hmi.yaml` | 황인재 | 포트, 갱신 주기, 연결 끊김 판정 시간, SQLite 경로 |

## 10. 시험용 가짜 노드
- `mock_f1_f3`: 같은 서비스 이름으로 즉시 `ok=true` 응답, 파라미터로 실패 코드 주입(`mock.fail_on: ["seat:SEAT_FAIL"]`) — flow 개발용, 민범진 제공
- `fake_state_pub`: `/flow/state`·`/flow/event`를 시나리오대로 발행 — HMI 개발용, 황인재 제작
