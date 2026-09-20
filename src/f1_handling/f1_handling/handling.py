"""F1 파지·이송·적재 — 한석형 (IRD v3.0 §3, SDD §5.2).

flow_node(메인 프로그램)나 test/rig_f1.py 가 cobot_common.init() 뒤 **메인 스레드**에서 부르는
평범한 함수다(SDD §3.2). 이름·인자·반환은 cobot_api.F1Api 그대로이고, 실패는 예외가 아니라
Result.fail(code) 로 돌려준다. 좌표·숫자는 전부 cell.yaml · params.yaml 의 f1 절에서 읽는다(AGENTS 규칙 6).

물리 인계: F1 이 놓은 자리에서 F3 가 시작한다 → 단독 시험은 용기·툴을 손으로 놓아 주면 된다.
어떤 실패에서도 로봇은 안전 높이로(cc.safe_retreat), 툴 반납은 flow 가 tool(RETURN) 을 부른다.

진행: ✅ F1-01 move_to · 일반 place (9/20 재분담 — 황인재 세션이 구현, 한석형 검토) / 🚧 pick(F1-02) · tool(F1-03) · rack_place(F1-04) · 안착 놓기(F1-05)
  🚧 표시 함수는 아직 약속된 반환 타입만 돌려준다(로봇 동작 없음, V-20 재료). **패키지 주인은 한석형**(결정 기록 W5).
  본문은 cobot_common 의 motion · gripper · force 함수로 채운다:
      import cobot_common as cc
      p = cc.cfg()['cell']['zones'][zone_id]          # 숫자는 YAML 에서
      cc.move_to(...) · cc.move_rel(...) · cc.contact_down(...) · cc.grip(...) · cc.release() · cc.safe_retreat()
  🚨 DSR_ROBOT2 를 직접 import 하지 않는다. 접촉 동작에는 힘 상한 + 후퇴 + 타임아웃(AGENTS 규칙 2).

실패를 돌려주는 방식 (F1-01 에서 정함 — flow.call() 의 실제 동작에 맞춘 것)
  · 공정에서 **있을 수 있는** 실패 = 코드로: SEAT_FAIL · TOOL_FAIL · EMPTY_ZONE · RACK_JAM · FORCE_LIMIT · TIMEOUT (Result.fail)
  · 로봇·설정이 **잘못된** 경우 = 예외를 **그대로 위로**: cc.MoveIncomplete(이동이 도중에 멈춤) · cc.MotionHalted(강제정지) ·
    cc.MoveTimeout · KeyError(cell.yaml 값이 비어 있음) · ValueError(이름·kind 가 틀림).
    flow.call() 이 받아 ROBOT_ERROR → 후퇴 → PAUSED 로 바꾸고 **오류 문구를 상태 메시지(HMI 화면)에 싣는다**
    — 여기서 삼켜 코드만 돌려주면 "왜 멈췄는지"가 사라진다. 🚨 그래서 이동이 실패한 뒤에는 **release 하지 않는다**(공중에서 놓지 않는다).
"""
import cobot_common as cc
from cobot_api import PickResult, PlaceResult, Result, ToolResult

_PLACE_POINT = 'place'          # 스펀지 홈(cell.beds.*)에서 '용기를 놓는 자리'의 point 이름 (cell.yaml 의 자세 적는 법)


def pick(zone_id: str, kind: str) -> PickResult:
    """고정 슬롯 파지(9/19 DSN-04). 코드 OK / EMPTY_ZONE / ROBOT_ERROR (빈 슬롯·헛잡음은 안에서 다음 슬롯으로 소화). — F1-02

    절차: cell.zones[zone_id].slots 의 슬롯을 1번부터 차례로 —
      그리퍼 열기 → cc.move_to(zone_id, False, point=i) (슬롯의 집는 자세 posj 까지 간다) → grip(프리셋 폭·힘)
      → 폭이 프리셋 ± width_tol_mm 이면 성공: 상승 → PickResult(width_mm, attempts=i).
      아니면(빈손 · 헛잡음) release → 상승 → 다음 슬롯.  다 돌면 PickResult.fail(EMPTY_ZONE, attempts=슬롯 수).
    zone_id 가 SPONGE_BED_* 면 고정 위치 재파지(슬롯 1개):
      그릇 = cc.move_to('SPONGE_BED_B', False, point='place') → 남은 높이만큼 하강 → grip / 컵 = cc.move_to('SPONGE_BED_C', False, point='regrip') → grip.
    좌표 양식(종류별 · point · 슬롯 · 접근점+끝점)은 src/cobot_common/config/cell.yaml 의 stations 위 설명을 본다(9/20 CELL-04).
    """
    return PickResult()


def place(station: str, kind: str = None) -> PlaceResult:
    """놓기 — 성공하면 **항상 release 까지** 한다. 코드 OK / (F1-05 에서) SEAT_FAIL · FORCE_LIMIT · TIMEOUT. — F1-01(일반) · F1-05(안착)

    일반 놓기(F1-01): ① 자리의 접근점으로(cc.move_to — 접근점이 없으면 끝점까지 곧장) ② 끝점까지 **곧게 하강**
      ③ release ④ **내려간 만큼 되올라온다**(접근점이 없던 자리는 f1.place_clear_mm 만큼 위로 — 놓은 용기를 끌지 않게). offset_mm = 0.
      kind(BOWL/CUP) = 종류별 자리(ISOLATE …)에 놓을 때. 스펀지 홈(SPONGE_BED_*)은 point='place' 자세를 쓴다.
      끝점은 티칭한 '놓는 높이'다 — 힘으로 바닥을 찾는 접촉 하강이 아니다(그건 아래 안착 놓기).
      🚨 ①·② 가 실패하면(예외) **release 하지 않고** 그대로 위로 올린다 — 머리말의 '실패를 돌려주는 방식'.
    🚧 안착 놓기(F1-05, 한석형): SPONGE_BED_B/C 에서 ② 를 force_on(z) 순응 하강 + contact_down 으로 바꾸고,
      깊이 미달이면 periodic_search(cell.beds.*.seat) → 들어가면 release(offset_mm = 보정 거리) / 한도 초과면 **들고** 후퇴 + SEAT_FAIL.
      지금은 스펀지 홈에서도 위 일반 놓기로 돈다(9/20 범위 방어: "단순 놓기부터").
    """
    point = _PLACE_POINT if station in (cc.cfg().get('cell') or {}).get('beds', {}) else None
    clear = float(cc.cfg()['f1']['place_clear_mm'])                 # 값이 없으면 움직이기 **전에** KeyError
    up = float(cc.move_to(station, True, kind, point) or 0.0)       # ① 접근점(없으면 끝점)
    if up > 0.0:
        cc.move_rel(0.0, 0.0, -up, 'BASE')                          # ② 끝점까지 곧게
    cc.release()                                                    # ③
    cc.move_rel(0.0, 0.0, up if up > 0.0 else clear, 'BASE')        # ④ 되올라오기
    return PlaceResult(offset_mm=0.0)


def move_to(station: str, carrying: bool, kind: str = None) -> Result:
    """station 의 티칭 자세로 **곧장** 이동(9/20 E7 — 안전 높이를 거치지 않는다). 들고 있으면(carrying) 저속. 복귀는 move_to('HOME', False). — F1-01

    cobot_common.move_to(station, carrying, kind) 를 감싼 것(좌표는 cell.yaml 에서, 읽기만).
    kind(BOWL/CUP): 종류별 자리(WEIGH·WASTE·SOAP·RINSE·ISOLATE)로 갈 때 flow 가 넘겨 준다. HOME 처럼 종류와 무관한 자리는 생략.
    접근점이 있는 자리(스펀지 홈·팔레트 칸)는 이 함수의 대상이 아니다 — point 를 고르는 place · tool · rack_place · pick 이 맡는다
      (여기로 부르면 cc.move_to 가 "point 를 고르라"는 ValueError 를 내고 로봇은 움직이지 않는다).
    실패는 전부 예외로 올라간다(머리말) — 이동에는 '있을 수 있는 실패' 가 없다. 도착하지 못했으면 cc.MoveIncomplete.
    """
    cc.move_to(station, carrying, kind)
    return Result()


def tool(tool: str, action: str) -> ToolResult:
    """툴 픽업/반납. tool = SPONGE/BRUSH, action = PICK/RETURN. 폭 범위 밖이면 TOOL_FAIL. — F1-03

    PICK: 홀더(TOOL_SPONGE/TOOL_BRUSH) 상공 → 하강 → grip(프리셋) → 폭 확인(범위 밖 → release·후퇴·TOOL_FAIL) → 상승.
    RETURN: 홀더 상공 → 하강 → 힘 접촉으로 바닥 확인(f1.tool_return_contact_n, 상한·타임아웃) → release → 후퇴.
    🔔 툴을 쥐면 툴 무게가 바뀐다 — 툴 무게 설정이 틀리면 힘 값이 틀어진다(CELL-02a §3-5, 박진용과 협의).
    """
    return ToolResult()


def rack_place(rack_slot: str, kind: str) -> Result:
    """팔레트 칸 삽입. 걸리면 RACK_JAM. — F1-04

    절차: up = cc.move_to(rack_slot, True) (칸의 접근점 cell.rack.slots[rack_slot].approach_posx 까지 — 칸마다 절대 자세, 9/20 CELL-04)
      → 남은 높이 up 만큼 하강: contact_down 으로 삽입력 감시(cell.limits.insert_limit_n) → 도달 시 release → 후퇴.
      (한석형 티칭 경로: HOME → HOME 의 x·y 그대로 z 338 → 접근점 → 끝점 → 놓기 → 그릇: y −25 · z +200 / 컵: 접근점으로 — cell.yaml rack 주석)
      걸림(힘 > 상한인데 깊이 미달) → 후퇴 → Result.fail(RACK_JAM). V-06 이 안 되면 각도 삽입 → 수직 놓기(SDD §9.9).
    """
    return Result()
