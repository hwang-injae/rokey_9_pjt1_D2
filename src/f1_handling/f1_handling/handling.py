"""F1 파지·이송·적재 — 한석형 (IRD v3.0 §3, SDD §5.2).

flow_node(메인 프로그램)나 test/rig_f1.py 가 cobot_common.init() 뒤 **메인 스레드**에서 부르는
평범한 함수다(SDD §3.2). 이름·인자·반환은 cobot_api.F1Api 그대로이고, 실패는 예외가 아니라
Result.fail(code) 로 돌려준다. 좌표·숫자는 전부 cell.yaml · params.yaml 의 f1 절에서 읽는다(AGENTS 규칙 6).

물리 인계: F1 이 놓은 자리에서 F3 가 시작한다 → 단독 시험은 용기·툴을 손으로 놓아 주면 된다.
어떤 실패에서도 로봇은 안전 높이로(cc.safe_retreat), 툴 반납은 flow 가 tool(RETURN) 을 부른다.

진행: ✅ F1-01 move_to · 일반 place · ✅ F1-03 tool (9/20 재분담 — 황인재 세션이 구현, 한석형 검토) / 🚧 pick(F1-02) · rack_place(F1-04) · 안착 놓기(F1-05)
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
from cobot_api import (BRUSH, FORCE_LIMIT, PICK, RETURN, SPONGE, TIMEOUT, TOOL_FAIL,
                       PickResult, PlaceResult, Result, ToolResult)

_PLACE_POINT = 'place'          # 스펀지 홈(cell.beds.*)에서 '용기를 놓는 자리'의 point 이름 (cell.yaml 의 자세 적는 법)
_TOOL_STATION = {SPONGE: 'TOOL_SPONGE', BRUSH: 'TOOL_BRUSH'}    # 툴 이름 → 홀더 자리 이름 (IRD §2)


def _need(mapping, key, where):
    """값이 없거나 **비어 있으면**(골격의 None) 로봇을 움직이기 전에 KeyError — 어느 키인지 알려 준다(motion.py 와 같은 방식)."""
    value = (mapping or {}).get(key)
    if value is None:
        raise KeyError(f'{where}.{key} 가 없거나 비어 있다 — 채운 뒤에 쓴다. 값이 없으면 로봇을 움직이지 않는다')
    return value


def _retreat():
    """실패를 돌려주기 전에 안전 높이로 물러난다. 후퇴가 실패해도 **원래 실패 코드를 잃지 않게** 로그만 남긴다.

    (f2 sense.py 와 같은 방식 — flow.call() 의 후퇴는 예외가 올라올 때만 걸리는데, 우리는 코드로 돌려주기 때문에 여기서 해야 한다.)
    """
    try:
        cc.safe_retreat()
    except Exception as e:                                          # noqa: BLE001 — 후퇴 실패가 실패 코드를 덮으면 안 된다
        try:
            cc.io_node().get_logger().error(f'safe_retreat 실패 — {type(e).__name__}: {e}')
        except Exception:                                           # noqa: BLE001 — 로그가 죽어도 결과는 돌려준다
            pass


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
    clear = float(_need(cc.cfg().get('f1'), 'place_clear_mm', 'params.yaml 의 f1'))   # 값이 없으면 움직이기 **전에** KeyError
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
    """툴 픽업/반납. tool = SPONGE/BRUSH, action = PICK/RETURN. 코드 OK / TOOL_FAIL / FORCE_LIMIT / TIMEOUT. — F1-03

    PICK  : 홀더의 집는 자세(cell.stations.TOOL_*.pick)로 → 접근점이 있으면 끝점까지 하강 → grip(프리셋 폭·힘)
            → 폭이 프리셋 ± width_tol_mm 이면 OK 로 홀더에서 빼낸다. 범위 밖이면 release(툴을 홀더에 두고) → 후퇴 → TOOL_FAIL.
    RETURN: 홀더의 반납 자세(cell.stations.TOOL_*.return)로 **툴을 들고** → cc.contact_down 으로 홀더 바닥을 찾는다
            (접촉 힘 f1.tool_return_contact_n · 최대 깊이 = 접근점까지의 높이 또는 f1.tool_return_depth_mm ·
             힘 상한과 타임아웃은 contact_down 이 본다 — AGENTS 규칙 2) → release → 되올라오기.
            🚨 **바닥을 못 찾으면 release 하지 않는다**(공중에서 툴을 떨어뜨리지 않는다) → 후퇴 + TOOL_FAIL.
    🔔 툴을 쥐면 툴 무게가 바뀐다 — 툴 무게 설정이 틀리면 힘 값이 틀어진다(CELL-02a §3-5, 박진용과 협의).
       contact_down 은 **시작할 때 대비 힘 변화량**으로 본다(절대값 아님)라 이 함정은 이미 피해 간다.
    🟡 폭 판정: grip() 머리말의 "목표 폭을 기대보다 작게" 함정 — 명령한 폭과 기대 폭이 같으면 **빈손으로 닫아도 통과**할 수 있다.
       툴(수세미 손잡이·솔)은 그릇(벽 파지 ≈ 2 mm)과 달리 두께가 커서 빈손(≈ 0 mm)과 간격이 충분할 것으로 본다 →
       프리셋 값을 그렇게 정한다(한석형). **V-08(집기·반납 10회)에서 빈손을 실제로 넣어 확인한다.**
    """
    station = _TOOL_STATION.get(tool)
    if station is None:
        raise ValueError(f'tool: tool={tool!r} — {tuple(_TOOL_STATION)} 중 하나')
    if action not in (PICK, RETURN):
        raise ValueError(f'tool: action={action!r} — {PICK!r} 또는 {RETURN!r}')
    conf = cc.cfg()
    f1 = conf.get('f1')
    clear = float(_need(f1, 'tool_clear_mm', 'params.yaml 의 f1'))   # 필요한 값을 **전부 읽은 뒤에** 로봇에 손댄다
    if action == PICK:
        preset = ((conf.get('cell') or {}).get('presets') or {}).get(tool)
        if not preset:
            raise KeyError(f'cell.presets.{tool} 가 없다 — 툴 파지 폭·힘을 cell.yaml 에 채운다(한석형)')
        return _tool_pick(station, tool, preset, clear)
    return _tool_return(station, f1, clear)


def _tool_pick(station, tool, preset, clear) -> ToolResult:
    where = f'cell.presets.{tool}'
    want = float(_need(preset, 'grip_width_mm', where))
    tol = float(_need(preset, 'width_tol_mm', where))
    force = float(_need(preset, 'grip_force_n', where))
    up = float(cc.move_to(station, False, point='pick') or 0.0)     # 빈손으로 간다
    if up > 0.0:
        cc.move_rel(0.0, 0.0, -up, 'BASE')
    width = float(cc.grip(want, force))
    if abs(width - want) > tol:                                     # 헛잡음 — 툴을 홀더에 두고 물러난다
        cc.release()
        _retreat()
        return ToolResult.fail(TOOL_FAIL, width_mm=width)
    cc.move_rel(0.0, 0.0, up if up > 0.0 else clear, 'BASE')        # 홀더에서 빼낸다
    return ToolResult(width_mm=width)


def _tool_return(station, f1, clear) -> ToolResult:
    limit = float(_need(f1, 'tool_return_contact_n', 'params.yaml 의 f1'))
    depth_budget = float(_need(f1, 'tool_return_depth_mm', 'params.yaml 의 f1'))   # 🚨 값을 **전부 읽은 뒤에** 로봇에 손댄다
    up = float(cc.move_to(station, True, point='return') or 0.0)    # 툴을 들고 간다
    budget = up if up > 0.0 else depth_budget
    try:
        depth, _force = cc.contact_down(budget, limit)               # 힘 상한·타임아웃은 contact_down 안에서 본다
    except cc.ForceLimitError:
        _retreat()
        return ToolResult.fail(FORCE_LIMIT)
    except cc.MotionTimeout:
        _retreat()
        return ToolResult.fail(TIMEOUT)
    if depth >= budget:                                             # 🚨 바닥을 못 찾았다 → 놓지 않는다
        _retreat()
        return ToolResult.fail(TOOL_FAIL)
    cc.release()
    cc.move_rel(0.0, 0.0, depth + (0.0 if up > 0.0 else clear), 'BASE')   # 접근점이 있으면 접근점까지, 없으면 그 위로
    return ToolResult()


def rack_place(rack_slot: str, kind: str) -> Result:
    """팔레트 칸 삽입. 걸리면 RACK_JAM. — F1-04

    절차: up = cc.move_to(rack_slot, True) (칸의 접근점 cell.rack.slots[rack_slot].approach_posx 까지 — 칸마다 절대 자세, 9/20 CELL-04)
      → 남은 높이 up 만큼 하강: contact_down 으로 삽입력 감시(cell.limits.insert_limit_n) → 도달 시 release → 후퇴.
      (한석형 티칭 경로: HOME → HOME 의 x·y 그대로 z 338 → 접근점 → 끝점 → 놓기 → 그릇: y −25 · z +200 / 컵: 접근점으로 — cell.yaml rack 주석)
      걸림(힘 > 상한인데 깊이 미달) → 후퇴 → Result.fail(RACK_JAM). V-06 이 안 되면 각도 삽입 → 수직 놓기(SDD §9.9).
    """
    return Result()
