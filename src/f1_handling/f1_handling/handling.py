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
from cobot_api import (CUP, EMPTY_ZONE, FORCE_LIMIT, GRIP_FAIL, RACK_JAM, TIMEOUT,
                       PickResult, PlaceResult, Result, ToolResult)
from cobot_common.force import ForceLimitError, MotionTimeout      # 접촉 동작의 힘 상한·시간 초과 (코드로 바꿔 돌려준다)

_PLACE_POINT = 'place'          # 스펀지 홈(cell.beds.*)에서 '용기를 놓는 자리'의 point 이름 (cell.yaml 의 자세 적는 법)
_REGRIP_POINT = 'regrip'        # 컵은 놓을 때와 다른 방향에서 다시 잡는다(cell.beds.SPONGE_BED_C.regrip)


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
    CUP(E19): grip_target_mm 까지만 닫고 **판정하지 않는다** — 빈손과 구분이 안 되고(컵 77.9 vs 빈손 77.8) 눌러도 안 된다.
    """
    preset = _need(_cell().get('presets'), kind, 'cell.presets')
    where = f'cell.presets.{kind}'
    force = float(_need(preset, 'grip_force_n', where))
    zero = float(_need(preset, 'grip_zero_mm', where))
    if kind == CUP:
        target = float(_need(preset, 'grip_target_mm', where))
        return target, force, (lambda got: True), zero
    expect = float(_need(preset, 'grip_width_mm', where))
    tol = float(_need(preset, 'width_tol_mm', where))
    target = zero + max(0.0, expect - 2.0 * tol)
    return target, force, (lambda got: abs((got - zero) - expect) <= tol), zero


def _grip_here(kind):
    """지금 자리에서 쥔다 → (성공 여부, 보고할 폭). BOWL 은 영점 뺀 폭, CUP 은 드라이버 폭."""
    target, force, judge, zero = _grip_close(kind)
    got = float(cc.grip(target, force))
    ok = judge(got)
    width = got if kind == CUP else got - zero
    _log().info(f'grip({kind}) 목표 {target:.2f} mm · {force:.0f} N → 실제 {got:.2f} mm'
                + ('' if kind == CUP else f' · 영점 뺀 폭 {width:.2f} mm') + (' ✅' if ok else ' ✗ (빈손·헛잡음)'))
    return ok, width


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
    """스펀지 홈에서 다시 잡기 — pick() 의 재파지 갈래."""
    if kind == CUP:
        cc.release()
        cc.move_to(bed, False, kind, _REGRIP_POINT)                 # posj — 접근점 없음
        ok, width = _grip_here(kind)
        if not ok:                                                  # (컵은 판정이 없어 여기 오지 않는다 — 형식상)
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
