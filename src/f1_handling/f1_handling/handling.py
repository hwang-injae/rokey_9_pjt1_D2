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
from cobot_api import (BRUSH, CUP, EMPTY_ZONE, FORCE_LIMIT, GRIP_FAIL, PICK, RACK_JAM, RETURN, SPONGE, TIMEOUT, TOOL_FAIL,
                       PickResult, PlaceResult, Result, ToolResult)
from cobot_common.force import ForceLimitError, MotionTimeout      # 접촉 동작의 힘 상한·시간 초과 (코드로 바꿔 돌려준다)

_PLACE_POINT = 'place'          # 스펀지 홈(cell.beds.*)에서 '용기를 놓는 자리'의 point 이름 (cell.yaml 의 자세 적는 법)
_REGRIP_POINT = 'regrip'        # 컵은 놓을 때와 다른 방향에서 다시 잡는다(cell.beds.SPONGE_BED_C.regrip)
_TOOL_STATION = {SPONGE: 'TOOL_SPONGE', BRUSH: 'TOOL_BRUSH'}    # 툴 이름 → 홀더 자리 이름 (IRD §2 · F1-03)


def _log():
    return cc.io_node().get_logger()


def _cell():
    return (cc.cfg() or {}).get('cell') or {}


def _need(node, key, where):
    """설정값 하나를 **반드시** 읽는다 — 비어 있으면 KeyError(로봇을 움직이기 전에)."""
    v = (node or {}).get(key) if isinstance(node, dict) else None
    if v is None:
        raise KeyError(f'{where}.{key} 가 비어 있다 — cell.yaml/params.yaml 을 채운 뒤에 쓴다')
    return v


def _grip_close(kind):
    """종류별 닫는 목표 폭·힘 → (목표 폭 mm · 힘 N · 판정 함수 · 영점).

    BOWL(SDD §5.2 · E16): 목표 = 영점 + max(0, 기대 − 2 × 허용오차) — 기대 폭을 그대로 주면 **빈손으로도 그 폭에서 멈춘다**.
        판정 = |(실제 폭 − 영점) − 기대| ≤ 허용오차.
    고정 폭(E19 · 프리셋에 `grip_target_mm` 이 있을 때): 그 폭까지만 닫고 **판정하지 않는다** — 9/21 컵 옆면 파지(빈손과 구분 불가 · 눌림).
        🔄 9/22 저녁(황인재 · CELL-05): 컵도 **그릇처럼 테두리 벽을 위에서 집는다** → presets.CUP 에서 grip_target_mm 을 빼고 폭 판정으로.
        종류가 아니라 **프리셋 키**로 방식을 고른다 — 나중에 다시 옆면 파지로 돌리려면 grip_target_mm 만 넣으면 된다.
    돌려주는 마지막 값 fixed: 고정 폭이면 True(보고 폭 = 드라이버 값) · 아니면 False(보고 폭 = 영점 뺀 값).
    """
    preset = _need(_cell().get('presets'), kind, 'cell.presets')
    where = f'cell.presets.{kind}'
    force = float(_need(preset, 'grip_force_n', where))
    zero = float(_need(preset, 'grip_zero_mm', where))
    fixed = preset.get('grip_target_mm')
    if fixed is not None:
        return float(fixed), force, (lambda got: True), zero, True
    expect = float(_need(preset, 'grip_width_mm', where))
    tol = float(_need(preset, 'width_tol_mm', where))
    target = zero + max(0.0, expect - 2.0 * tol)
    return target, force, (lambda got: abs((got - zero) - expect) <= tol), zero, False


def _grip_here(kind):
    """지금 자리에서 쥔다 → (성공 여부, 보고할 폭). 폭 판정이면 영점 뺀 폭, 고정 폭(E19)이면 드라이버 폭."""
    target, force, judge, zero, fixed = _grip_close(kind)
    got = float(cc.grip(target, force))
    ok = judge(got)
    width = got if fixed else got - zero
    _log().info(f'grip({kind}) 목표 {target:.2f} mm · {force:.0f} N → 실제 {got:.2f} mm'
                + ('' if fixed else f' · 영점 뺀 폭 {width:.2f} mm') + (' ✅' if ok else ' ✗ (빈손·헛잡음)'))
    return ok, width


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
    """고정 슬롯 파지(9/19 DSN-04). 코드 OK / EMPTY_ZONE / GRIP_FAIL(재파지) / 예외(로봇 이상). — F1-02

    ✅ 9/22 구현(민범진 · PM 승인으로 이식 — 동작은 한석형 rig_bowl_scenario_real.py 실기 검증 경로 그대로, 좌표는 cell.yaml).
    절차(반납 구역 RET_*): 그리퍼 열기 → 슬롯 1번부터 —
      cc.move_to(zone_id, False, point=i) (접근점) → 남은 높이만큼 곧게 하강 → grip(프리셋)
      → 그릇: 영점 뺀 폭이 기대 ± 허용오차면 성공 · 컵: 판정 없음(E19) → **접근 높이로 되올라와** PickResult(width_mm, attempts=i)
      → 실패(빈손·헛잡음)면 release → 되올라와 → 다음 슬롯. 다 돌면 PickResult.fail(EMPTY_ZONE, attempts=슬롯 수).
    재파지(SPONGE_BED_*): 그릇 = point='place' 접근점 → 하강 → grip → 되올라옴 / 컵 = point='regrip'(posj) → grip
      → rack.cup_entry_z_mm 까지 올린다(한석형 9/22 경로 — 낮은 자세에서 곧장 다음 자리로 가지 않게).
      재파지가 빈손이면 **GRIP_FAIL**(flow 정책 pause — 사람이 확인 · E12). EMPTY_ZONE 으로 하면 구역을 건너뛰어 홈에 있는 용기를 잃는다.
    🚨 이동이 실패하면(예외) release 하지 않고 그대로 올린다(머리말). 쥔 뒤의 이동 실패도 마찬가지(용기를 든 채 멈춘다).
    """
    cell = _cell()
    _grip_close(kind)                                               # 🚨 프리셋이 비었으면 **움직이기 전에** KeyError
    if zone_id in (cell.get('beds') or {}):
        return _regrip(zone_id, kind)
    zone = _need(cell.get('zones'), zone_id, 'cell.zones')
    slots = zone.get('slots') or []
    if not slots:
        raise KeyError(f'cell.zones.{zone_id}.slots 가 비어 있다')
    cc.release()                                                    # 🚨 빈손으로 시작 (현재상황 §2 PICK)
    for i in range(1, len(slots) + 1):
        up = float(cc.move_to(zone_id, False, kind, i) or 0.0)      # 접근점 (없으면 끝점 · 0)
        if up > 0.0:
            cc.move_rel(0.0, 0.0, -up, 'BASE')                      # 끝점(집는 자세)까지 곧게
        ok, width = _grip_here(kind)
        if ok:
            if up > 0.0:
                cc.move_rel(0.0, 0.0, up, 'BASE')                   # 쥔 채 접근 높이로 (다음 이동은 여기서 출발)
            return PickResult(width_mm=width, attempts=i)
        cc.release()                                                # 헛잡음 — 놓고 다음 슬롯
        if up > 0.0:
            cc.move_rel(0.0, 0.0, up, 'BASE')
    _log().warn(f'pick({zone_id}, {kind}) — 슬롯 {len(slots)}개 모두 빈손 → EMPTY_ZONE')
    return PickResult.fail(EMPTY_ZONE, attempts=len(slots))


def _regrip(bed: str, kind: str) -> PickResult:
    """스펀지 홈에서 다시 잡기 — pick() 의 재파지 갈래.

    🔄 9/22 저녁(황인재 · E29): 종류가 아니라 **홈에 `regrip` 자세가 있는지**로 고른다 —
      · regrip(posj) 이 있으면 그 자세에서 잡는다(옆면 파지 · 한석형 9/22 컵 방식 · 잡은 뒤 rack.cup_entry_z_mm 까지 올림)
      · 없으면 그릇처럼 **놓은 자리(place 접근점 → 하강)에서 그대로 다시 잡는다** — 컵도 벽 집기로 바뀌어 이 갈래
    """
    bed_spec = ((_cell().get('beds') or {}).get(bed) or {})
    if bed_spec.get(_REGRIP_POINT):
        cc.release()
        cc.move_to(bed, False, kind, _REGRIP_POINT)                 # posj — 접근점 없음
        ok, width = _grip_here(kind)
        if not ok:
            return PickResult.fail(GRIP_FAIL, attempts=1)
        entry_z = float(_need(_cell().get('rack'), 'cup_entry_z_mm', 'cell.rack'))
        dz = entry_z - float(cc.where()[2])
        if dz > 0.0:
            cc.move_rel(0.0, 0.0, dz, 'BASE')                       # 한석형 9/22: 재파지 뒤 z 250 까지 올린 뒤 다음 자리로
        return PickResult(width_mm=width, attempts=1)
    cc.release()
    up = float(cc.move_to(bed, False, kind, _PLACE_POINT) or 0.0)
    if up > 0.0:
        cc.move_rel(0.0, 0.0, -up, 'BASE')
    ok, width = _grip_here(kind)
    if not ok:
        cc.release()
        if up > 0.0:
            cc.move_rel(0.0, 0.0, up, 'BASE')
        _log().warn(f'pick({bed}, {kind}) — 재파지가 빈손 → GRIP_FAIL (사람이 확인 · E12)')
        return PickResult.fail(GRIP_FAIL, attempts=1)
    if up > 0.0:
        cc.move_rel(0.0, 0.0, up, 'BASE')
    return PickResult(width_mm=width, attempts=1)


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

    PICK  : 홀더의 집는 자세(cell.stations.TOOL_*.pick)로 → 접근점이 있으면 끝점까지 하강 → grip(프리셋 힘)
            → 폭 판정이 맞으면 OK 로 홀더에서 빼낸다. 어긋나면 release(툴을 홀더에 두고) → 후퇴 → TOOL_FAIL.
            폭은 결정 E16 D-A 대로 **영점(grip_zero_mm)을 빼고** 본다: 명령 = 영점 + (기대 폭 − 2 × 허용오차)(SDD §5.2 "기대보다 작게"),
            판정 = |읽은 폭 − 영점 − 기대 폭| ≤ 허용오차.
            프리셋에 `grip_target_mm` 이 있으면 컵(결정 E19)처럼 **그 폭까지만 닫고 폭 판정을 하지 않는다** —
            툴이 물러서 끝까지 닫으면 눌리는 경우(민범진 9/21 주의). 어느 쪽인지는 V-08 에서 재 보고 정한다(E23 · 황인재).
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
    force = float(_need(preset, 'grip_force_n', where))
    fixed = preset.get('grip_target_mm')
    if fixed is not None:                                           # 고정 폭(E19 방식) — 폭으로 판정하지 않는다
        target, check = float(fixed), None
    else:                                                           # 폭 판정(E16 D-A) — 값을 **전부 읽은 뒤에** 로봇에 손댄다
        want = float(_need(preset, 'grip_width_mm', where))
        tol = float(_need(preset, 'width_tol_mm', where))
        zero = float(_need(preset, 'grip_zero_mm', where))
        target, check = zero + max(0.0, want - 2 * tol), (want, tol, zero)
    up = float(cc.move_to(station, False, point='pick') or 0.0)     # 빈손으로 간다
    if up > 0.0:
        cc.move_rel(0.0, 0.0, -up, 'BASE')
    width = float(cc.grip(target, force))
    if check and abs(width - check[2] - check[0]) > check[1]:       # 헛잡음 — 툴을 홀더에 두고 물러난다
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
    """팔레트 칸 삽입. 걸리면 RACK_JAM · 힘 상한 FORCE_LIMIT · 시간 초과 TIMEOUT. — F1-04

    ✅ 9/22 구현(민범진 · PM 승인으로 이식 — 경로는 한석형 rig_bowl_scenario_real.py 9/22 검증 그대로, 좌표는 cell.yaml).
    전제: IRD §8 순서대로 **헹굼(RINSE) 뒤에** 불린다 — 수조 안(낮은 자세)에서 시작하므로 먼저 수조 위로 빠져나온다.
    절차:
      ① cc.move_to('RINSE', True, kind) — 접근점(수조 바로 위)으로 **곧게 올라온다** · 컵은 rack.cup_entry_z_mm 까지 더 올린다
      ② 경유점 cell.rack.slots[slot].via (관절 자세 · 손목이 도는 동안 아래가 허공이게 — 9/21 J4 충돌 · 9/22 B1 손목 반전은 경유점에서)
      ③ up = cc.move_to(rack_slot, True) — 칸 **바로 위**(접근점) · 그릇은 그 앞에 HOME 을 거친다(수조 → 팔레트 · E15)
      ④ 하강 = (up − f1.insert_approach_mm) 자유 하강 → 마지막 insert_approach_mm 는 cc.contact_down(insert_limit_n) 으로 **삽입력 감시**
         · 깊이가 남았는데 힘이 먼저 닿음 = 걸림 → 내려간 만큼 되올라와 RACK_JAM
         · ForceLimitError → FORCE_LIMIT · MotionTimeout → TIMEOUT (둘 다 되올라온 뒤)
      ⑤ release → cell.rack.slots[slot].exit_rel_mm 순서대로 빠져나온다(그릇 y −25 → z +100 · 컵 z → y)
    RACK_FULL 은 여기서 판정하지 않는다(칸이 차 있으면 삽입이 걸려 RACK_JAM → 정책 retry:1 → isolate).
    """
    cell = _cell()
    slot = _need(cell.get('rack', {}).get('slots'), rack_slot, 'cell.rack.slots')
    where = f'cell.rack.slots.{rack_slot}'
    via = _need(slot, 'via', where)
    exits = slot.get('exit_rel_mm') or []
    f1 = (cc.cfg() or {}).get('f1') or {}
    approach_mm = float(_need(f1, 'insert_approach_mm', 'f1'))
    limit_n = float(_need(cell.get('limits'), 'insert_limit_n', 'cell.limits'))

    cc.force_off()
    cc.move_to('RINSE', True, kind)                                 # ① 수조 위로 (접근점 — 같은 x·y 라 곧게 올라온다)
    if kind == CUP:
        entry_z = float(_need(cell.get('rack'), 'cup_entry_z_mm', 'cell.rack'))
        dz = entry_z - float(cc.where()[2])
        if dz > 0.0:
            cc.move_rel(0.0, 0.0, dz, 'BASE')
    else:
        cc.move_to('HOME', True)                                    # 그릇: 수조(오른쪽) → 팔레트(왼쪽) 사이 HOME 경유 (E15)
    cc.move_to(via, True)                                           # ② 경유점 (관절 자세)
    up = float(cc.move_to(rack_slot, True) or 0.0)                  # ③ 칸 바로 위
    free = max(0.0, up - approach_mm)
    watch = min(up, approach_mm) if up > 0.0 else 0.0
    if free > 0.0:
        cc.move_rel(0.0, 0.0, -free, 'BASE')                        # ④-1 자유 하강
    depth = 0.0
    try:
        if watch > 0.0:
            depth, force = cc.contact_down(watch, limit_n)          # ④-2 삽입력 감시 (순응 ON · 상한 · 타임아웃은 안에서)
            seated = depth >= watch - float(_need(cell.get('rack'), 'seat_tol_mm', 'cell.rack'))
            if not seated:
                _log().warn(f'rack_place({rack_slot}) — {depth:.1f}/{watch:.1f} mm 에서 {force:.1f} N 걸림 → RACK_JAM')
                cc.move_rel(0.0, 0.0, free + depth, 'BASE')         # 들고 접근점으로
                return Result.fail(RACK_JAM)
    except ForceLimitError as e:
        _log().error(f'rack_place({rack_slot}) — 힘 상한: {e}')
        cc.move_rel(0.0, 0.0, free + depth, 'BASE')
        return Result.fail(FORCE_LIMIT)
    except MotionTimeout as e:
        _log().error(f'rack_place({rack_slot}) — 시간 초과: {e}')
        cc.move_rel(0.0, 0.0, free + depth, 'BASE')
        return Result.fail(TIMEOUT)
    cc.release()                                                    # ⑤ 놓고
    for dx, dy, dz in exits:
        cc.move_rel(float(dx), float(dy), float(dz), 'BASE')        #    칸에서 빠져나온다 (순서 그대로)
    return Result()
