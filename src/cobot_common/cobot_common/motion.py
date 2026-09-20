# -*- coding: utf-8 -*-
"""이동 함수(저수준) — 담당 황인재 (INF-02, 9/19 재분담 — 결정 기록 W3). 함수 표는 docs/03_설계_SDD.md §3.1.

    import cobot_common as cc
    up = cc.move_to('WASTE', True, 'BOWL')             # 안전 높이를 거쳐 잔반통 앞(그릇용 자세)의 **상공**까지. up = 끝점까지 남은 높이(mm)
    cc.move_rel(0, 0, -up, 'BASE')                     # 내려가는 것은 부르는 쪽이 한다 (접촉이면 cc.contact_down)
    cc.move_to('TOOL_SPONGE', False, point='pick')     # 한 자리에 자세가 여러 개면 point 로 고른다 (pick·return / place·regrip·wash)
    cc.move_to('RET_B', False, point=1)                # 반납 구역은 슬롯 번호(1 부터)
    cc.move_to('RACK_C1', True)                        # 팔레트 칸 — **접근점**까지 가고, 끝점까지 남은 높이를 돌려준다
    cc.move_joint_rel(5, +15.0, time_s=0.3)            # 관절 하나만 상대 이동 (털기·물 털기)

    cc.pause() · cc.resume()                           # 이동 **도중에** 즉시 멈췄다가 하던 동작을 이어서 (HMI 일시정지·재개, 9/20 결정)
    cc.halt()  · cc.clear_halt()                       # 강제정지: 그 자세 그대로 멈추고, 풀기 전까지 새 이동을 내보내지 않는다

이동을 보내는 방식 (9/20 V-24a 결과 → docs/test_logs/20260920_V-24a_정지가능성_황인재.md)
    두산의 동기 이동(movej·movel)은 끝날 때까지 드라이버의 통로를 붙잡아 **일시정지 요청이 이동이 끝난 뒤에야** 처리된다.
    그래서 세 함수 모두 **비동기 이동(amovej·amovel)을 보내고 check_motion() 을 짧게 반복해서 물어본다(폴링).**
    부르는 쪽에서는 달라진 것이 없다 — 이동이 끝나야 함수가 돌아온다. 일시정지 중에는 돌아오지 않고 재개를 기다린다.
  pause()·resume()·halt() 는 **깃발만 세운다**(통신 노드 콜백에서 불러도 된다 — SDD §3.2 규칙 ③).
    실제 move_pause·move_resume·move_stop 요청은 이동을 기다리는 **메인 스레드의 폴링 루프**가 보낸다(늦어도 폴링 간격 안에).
    이동이 없을 때 누른 일시정지는 다음 이동을 **출발시키지 않고** 재개를 기다린다.
  🚨 폴링 루프가 없는 동작에는 먹지 않는다: 힘 함수의 move_periodic·순응 중 동작, 그리퍼·무게 대기 — 그 동작이 끝난 뒤 다음 이동에서 멈춘다.

규칙
- 🚨 **값이 비어 있으면 로봇을 움직이지 않고 KeyError** — 어느 키가 없는지 알려 준다(force.py 와 같은 방식).
  필요한 값을 **전부 읽은 뒤에** 첫 명령을 보낸다.
- 🚨 move_to 는 **안전 높이(cell.limits.safe_z_mm) 아래로 내려가지 않는다.** 티칭 자세가 더 낮으면 그 상공에서 멈추고
  남은 높이를 돌려준다. 하강은 move_rel(자유 공간) 또는 contact_down(접촉)으로 — 접촉 동작의 힘 상한·후퇴·타임아웃은 그쪽 몫이다.
  접근점(approach_posx)이 있는 자세는 **접근점까지** 간다(안전 높이보다 낮으면 안전 높이에서) — 돌려주는 값은 끝점(posx)까지 남은 높이.
- 자세 적는 법(종류별 · point · 슬롯 · 접근점+끝점)은 src/cobot_common/config/cell.yaml 의 stations 위 설명이 정본이다 (9/20 CELL-04, 결정 E4).
- 속도 = (100 % 기준 속도 cell.motion.*_max_*) × (cell.limits.vel_free_pct 또는 vel_carry_pct) × cfg()['run']['vel_scale'].
  move_rel 에 속도를 직접 주면 그 값을 쓰되(부르는 쪽이 vel_scale 을 곱한다 — force.py 방식), 위 상한은 넘지 못한다.
- 실패(두산 함수 반환이 0 이 아님)는 RuntimeError. 기능 함수가 코드로 바꾸고, 새어 나가면 flow 가 ROBOT_ERROR 로 바꾼다.
- 그리퍼 함수는 여기 두지 않는다 → gripper.py (민범진, INF-02d).

🟡 아직 없는 것: 사용자 좌표계의 좌표(9/20 부터 전부 BASE 절대 자세로 적는다) · 회전을 포함한 상대 이동 · 관절 자세(posj)의 접근점.
"""
import threading
import time

from .bootstrap import cfg, dsr, io_node

__all__ = ['move_to', 'move_rel', 'move_joint_rel',
           'pause', 'resume', 'is_paused', 'halt', 'clear_halt', 'is_halted', 'MotionHalted', 'MoveTimeout']

FRAMES = ('BASE', 'TOOL')
KINDS = ('BOWL', 'CUP')                             # 종류별 자세의 키 (IRD §2 kind)
_POSE_KEYS = ('posj', 'posx', 'approach_posx')      # 자세 1개를 이루는 키 (cell.yaml 의 '자세 적는 법')
_GROUPS = ('stations', 'beds', 'zones', 'rack.slots')   # move_to 가 이름을 찾는 곳 (IRD §2 의 station · zone_id · rack_slot)
_Z = 2
_POLL_S = 0.05                                      # check_motion 을 물어보는 간격 = 일시정지·정지가 먹는 데 걸리는 최대 지연
_SRV = '/dsr01/dsr_controller2/motion/'             # 두산 드라이버의 이동 제어 서비스
_STOP_MODE = 1                                      # DR_QSTOP — bootstrap.shutdown() 과 같은 값(박진용 확인 대상)

_pause_flag = threading.Event()                     # HMI 가 일시정지를 눌렀다
_halt_flag = threading.Event()                      # 강제정지 — clear_halt() 전까지 새 이동을 막는다
_clients = {}                                       # 통신 노드의 서비스 클라이언트 (setup_io 가 만든다)


class MotionHalted(RuntimeError):
    """강제정지(halt)로 이동이 끊겼거나, 강제정지 중이라 이동을 내보내지 않았다."""


class MoveTimeout(RuntimeError):
    """이동이 cell.motion.move_timeout_s 안에 끝나지 않았다(일시정지한 시간은 빼고 잰다) — 정지 명령을 보내고 올린다."""


# ------------------------------------------------------------------ 공개 함수
def move_to(station, carrying, kind=None, point=None):
    """안전 높이를 거쳐 station(상공)으로 간다. 들고 있으면(carrying) 느린 속도. → 끝점까지 남은 높이 mm (0.0 이면 그 자세)

    station: cell.stations(HOME·WEIGH·…) · cell.beds(SPONGE_BED_*) · cell.zones(RET_*) · cell.rack.slots(RACK_*) 의 이름.
    kind   : 'BOWL'·'CUP' — 종류별로 자세가 다른 자리(WEIGH·WASTE·SOAP·RINSE·ISOLATE)에서 고른다. 종류별이 아닌 자리에서는 무시한다.
    point  : 한 자리에 자세가 여러 개일 때 고른다 — 툴 홀더 'pick'·'return' / 스펀지 홈 'place'·'regrip'·'wash' / 반납 구역은 슬롯 번호(1 부터).
             골라야 하는데 안 주거나 없는 이름을 주면 ValueError(고를 수 있는 이름을 알려 준다) — 로봇은 움직이지 않는다.
    경로: ① 지금 높이가 안전 높이보다 낮으면 곧게 위로 ② posj 목표면 관절 이동 / posx 목표면 안전 높이 이상에서 목표 XY 로.
          접근점(approach_posx)이 있으면 **접근점으로** 간다(안전 높이보다 낮으면 안전 높이에서 멈춘다) — 돌려주는 값은 끝점(posx)까지 남은 높이.
    안전 자세 복귀는 move_to('HOME', False).
    """
    where, spec = _named_pose(station, kind, point)
    safe_z = float(_limit('safe_z_mm'))
    pct = _limit('vel_carry_pct' if carrying else 'vel_free_pct')
    vel_l, acc_l = _tcp_speed(pct)
    vel_j, acc_j = _joint_speed(pct)
    timeout = _move_timeout()
    d = dsr()                                       # 여기까지 오류가 없을 때만 로봇에 손댄다

    now, _ = d.get_current_posx(ref=d.DR_BASE)
    if float(now[_Z]) < safe_z:                     # ① 곧게 위로
        lift = [0.0, 0.0, safe_z - float(now[_Z]), 0.0, 0.0, 0.0]
        _run(f'amovel(안전 높이 {safe_z:g} mm 로 상승)', timeout,
             lambda: d.amovel(lift, vel=vel_l, acc=acc_l, ref=d.DR_BASE, mod=d.DR_MV_MOD_REL))
    if 'posj' in spec:                              # ② 관절 자세 (HOME · 집는 자세)
        joints = spec['posj']
        _run(f'amovej({where})', timeout, lambda: d.amovej(joints, vel=vel_j, acc=acc_j))
        return 0.0
    end = spec.get('posx') or spec['approach_posx']                 # 끝점을 아직 안 찍었으면 접근점이 끝점 노릇을 한다
    target = list(spec.get('approach_posx') or end)                 # 가는 곳 = 접근점(없으면 끝점)
    target[_Z] = max(target[_Z], safe_z)                            # 안전 높이보다 낮으면 그 상공에서 멈춘다
    _run(f'amovel({where})', timeout, lambda: d.amovel(target, vel=vel_l, acc=acc_l, ref=d.DR_BASE, mod=d.DR_MV_MOD_ABS))
    return target[_Z] - end[_Z]


def move_rel(dx, dy, dz, frame, *, vel_mm_s=None, acc_mm_s2=None):
    """지금 자세에서 (dx, dy, dz) mm 만큼 곧게 이동. frame = 'BASE'(로봇 기준) · 'TOOL'(툴 기준). 방향(자세)은 그대로.

    탐색점 이동·하강의 한 단계·후퇴에 쓴다. 속도를 안 주면 cell.limits.vel_carry_pct(느린 쪽) × vel_scale.
    속도를 주면 그 값을 쓴다(vel_scale 은 부르는 쪽이 곱한다). 어느 쪽이든 100 % 기준 속도 × vel_scale 을 넘지 못한다.
    """
    if frame not in FRAMES:
        raise ValueError(f"move_rel: frame={frame!r} — {FRAMES} 중 하나")
    vel, acc = _tcp_speed(_limit('vel_carry_pct'))
    top_v, top_a = _tcp_speed(100)
    if vel_mm_s is not None:
        vel = min(_positive('vel_mm_s', vel_mm_s), top_v)
    if acc_mm_s2 is not None:
        acc = min(_positive('acc_mm_s2', acc_mm_s2), top_a)
    timeout = _move_timeout()
    d = dsr()
    ref = {'BASE': d.DR_BASE, 'TOOL': d.DR_TOOL}[frame]
    step = [float(dx), float(dy), float(dz), 0.0, 0.0, 0.0]
    _run(f'amovel(move_rel {frame} {dx:g},{dy:g},{dz:g})', timeout,
         lambda: d.amovel(step, vel=vel, acc=acc, ref=ref, mod=d.DR_MV_MOD_REL))


def move_joint_rel(joint, delta_deg, *, time_s=None, carrying=True):
    """관절 하나(joint = 1~6)를 지금 각도에서 delta_deg 만큼 돌린다. 나머지 관절은 그대로. (DSN-03 B11 — 털기·물 털기의 J5/J6 왕복)

    time_s 를 주면 그 시간에 맞춰 움직인다(왕복 주기를 맞출 때) — vel_scale < 1 이면 시간을 그만큼 늘린다.
      🚨 그래도 **평균 속도(|delta_deg| / 시간)가 100 % 기준 × vel_scale 을 넘지 못한다** — 넘으면 시간을 늘리고 경고를 남긴다
      (move_rel 의 속도 상한과 같은 규칙. 시간 지정 이동의 순간 최고 속도는 평균보다 높다 → 기준값은 여유 있게 잡는다).
    안 주면 cell.limits 속도(carrying 이면 vel_carry_pct, 아니면 vel_free_pct) × vel_scale.
    🚨 순응·힘제어가 켜져 있으면 관절 이동이 안 된다(두산 오류 2.1903) → force_off() 뒤에 부른다.
    """
    if joint not in (1, 2, 3, 4, 5, 6):
        raise ValueError(f'move_joint_rel: joint={joint!r} — 1~6 (J1~J6)')
    delta = [0.0] * 6
    delta[joint - 1] = float(delta_deg)
    if time_s is not None:
        move_time = _positive('time_s', time_s) / _vel_scale()
        top_v, _ = _joint_speed(100)
        shortest = abs(float(delta_deg)) / top_v            # 상한 속도로 갈 때 걸리는 시간
        if move_time < shortest:
            _warn(f'move_joint_rel J{joint} {delta_deg:+g}° 를 {move_time:.2f} s 에 가면 평균 {abs(delta_deg) / move_time:.0f} deg/s — '
                  f'상한 {top_v:g} deg/s(cell.motion.vel_joint_max_deg_s × vel_scale)를 넘어 {shortest:.2f} s 로 늘린다')
            move_time = shortest
        kwargs = {'time': move_time}
    else:
        vel, acc = _joint_speed(_limit('vel_carry_pct' if carrying else 'vel_free_pct'))
        kwargs = {'vel': vel, 'acc': acc}
    timeout = _move_timeout()
    d = dsr()
    _run(f'amovej(move_joint_rel J{joint} {delta_deg:+g}°)', timeout, lambda: d.amovej(delta, mod=d.DR_MV_MOD_REL, **kwargs))


# ------------------------------------------------------------------ 일시정지 · 재개 · 강제정지 (깃발만 — 어느 스레드에서 불러도 된다)
def pause():
    """즉시 일시정지. 이동 중이면 그 자리에서 멈추고(늦어도 폴링 간격 안), 이동이 없으면 다음 이동이 출발하지 않는다."""
    _pause_flag.set()


def resume():
    """재개 — 멈춘 이동을 **이어서** 끝까지 한다."""
    _pause_flag.clear()


def is_paused() -> bool:
    return _pause_flag.is_set()


def halt():
    """강제정지 — 그 자세 그대로 멈춘다. 하던 이동은 MotionHalted 로 끝나고, clear_halt() 전까지 새 이동도 MotionHalted."""
    _halt_flag.set()


def clear_halt():
    """강제정지를 푼다(운영자가 확인한 뒤 — 예: HOME 복귀 전에). 일시정지 깃발도 같이 내린다."""
    _halt_flag.clear()
    _pause_flag.clear()


def is_halted() -> bool:
    return _halt_flag.is_set()


def setup_io(node):
    """init() 이 불러 준다: 이동 제어 서비스의 클라이언트를 통신 노드에 단다(응답은 통신 노드의 실행기가 받는다)."""
    from dsr_msgs2.srv import MovePause, MoveResume, MoveStop
    for name, srv in (('pause', MovePause), ('resume', MoveResume), ('stop', MoveStop)):
        _clients[name] = (node.create_client(srv, _SRV + 'move_' + name), srv)


# ------------------------------------------------------------------ 내부
def _run(what, timeout_s, send):
    """비동기 이동 하나를 보내고 끝날 때까지 기다린다. 기다리는 동안 일시정지·재개·강제정지 깃발을 본다(메인 스레드)."""
    while _pause_flag.is_set() and not _halt_flag.is_set():        # 이동이 없을 때 누른 일시정지 → 출발하지 않고 기다린다
        time.sleep(_POLL_S)
    if _halt_flag.is_set():
        raise MotionHalted(f'강제정지 중이라 {what} 을 내보내지 않았다 — clear_halt() 뒤에 다시')
    d = dsr()
    _ok(send(), what)
    driver_paused = False
    waited = 0.0                                                    # 일시정지한 시간은 세지 않는다
    while d.check_motion() != 0:                                    # 0 = 끝남. 일시정지 중에는 드라이버가 계속 '움직이는 중'이라고 답한다
        if _halt_flag.is_set():
            _call('stop')
            while d.check_motion() != 0:
                time.sleep(_POLL_S)
            raise MotionHalted(f'{what} 도중 강제정지')
        if _pause_flag.is_set() != driver_paused:                   # 깃발이 바뀌었다 → 드라이버에 전한다
            driver_paused = _pause_flag.is_set()
            _call('pause' if driver_paused else 'resume')
        time.sleep(_POLL_S)
        if not driver_paused:
            waited += _POLL_S
            if waited > timeout_s:
                _call('stop')
                raise MoveTimeout(f'{what} 이 {timeout_s:g} s 안에 끝나지 않았다 — 정지 명령을 보냈다')
    if _halt_flag.is_set():                                         # 끝나는 순간에 눌린 강제정지도 놓치지 않는다
        raise MotionHalted(f'{what} 직후 강제정지')


def _call(name):
    """move_pause·move_resume·move_stop 을 보낸다(기다리지 않는다 — 결과는 통신 노드가 받아 실패만 경고로 남긴다)."""
    client, srv = _clients.get(name) or _make_client(name)
    req = srv.Request()
    if name == 'stop':
        req.stop_mode = _STOP_MODE

    def done(fut):
        if not (fut.result() and fut.result().success):
            _warn(f'드라이버가 move_{name} 을 받아들이지 않았다')
    client.call_async(req).add_done_callback(done)


def _make_client(name):
    setup_io(io_node())                                             # setup_io 가 안 불린 경우(시험 등)
    return _clients[name]


def _move_timeout():
    return float(_cell_key('motion', 'move_timeout_s'))


def _ok(ret, what):
    if ret != 0:
        raise RuntimeError(f'{what} 실패 (반환 {ret!r})')


def _warn(text):
    from rclpy.logging import get_logger
    get_logger('cobot_common').warn(text)


def _positive(name, value):
    value = float(value)
    if not value > 0:
        raise ValueError(f'{name}={value} — 0 보다 커야 한다')
    return value


def _vel_scale():
    """실행 인자 vel_scale (config.load 가 0 초과 1 이하로 검사한다). 없으면 1.0."""
    return float(cfg().get('run', {}).get('vel_scale', 1.0))


def _limit(key):
    return _cell_key('limits', key)


def _tcp_speed(pct):
    """직선 이동 (속도 mm/s, 가속도 mm/s²) = 100 % 기준 × pct × vel_scale."""
    k = float(pct) / 100.0 * _vel_scale()
    return float(_cell_key('motion', 'vel_tcp_max_mm_s')) * k, float(_cell_key('motion', 'acc_tcp_max_mm_s2')) * k


def _joint_speed(pct):
    """관절 이동 (속도 deg/s, 가속도 deg/s²) = 100 % 기준 × pct × vel_scale."""
    k = float(pct) / 100.0 * _vel_scale()
    return float(_cell_key('motion', 'vel_joint_max_deg_s')) * k, float(_cell_key('motion', 'acc_joint_max_deg_s2')) * k


def _cell_key(section, key):
    try:
        value = cfg()['cell'][section][key]
    except (KeyError, TypeError):
        value = None
    if value is None:                   # 키가 없거나 골격처럼 비어 있음(null)
        raise KeyError(f'cell.yaml 의 cell.{section}.{key} 가 없거나 비어 있다 — 한석형(cell.yaml) 에 요청. '
                       '값이 없으면 로봇을 움직이지 않는다')
    return value


def _named_pose(name, kind=None, point=None):
    """이름(+ kind · point) → ('cell.…' 경로, {'posj': 값6} 또는 {'posx': 값6, 'approach_posx': 값6}). 비어 있으면 오류(로봇을 움직이지 않는다)."""
    cell = cfg().get('cell') or {}
    for group in _GROUPS:
        node = cell
        for part in group.split('.'):
            node = (node or {}).get(part) or {}
        if name in node:
            where, spec = _select(f'cell.{group}.{name}', node[name], kind, point)
            return where, _checked(where, spec)
    raise KeyError(f'{name!r} 는 cell.yaml 의 {_GROUPS} 어디에도 없다 (이름은 IRD §2 그대로)')


def _is_pose(node):
    return isinstance(node, dict) and any(k in node for k in _POSE_KEYS)


def _select(where, node, kind, point):
    """종류별 → 슬롯·용도별 순서로 자세 1개를 고른다. 고를 수 없으면 ValueError(무엇을 줄 수 있는지 알려 준다)."""
    if isinstance(node, dict) and any(k in node for k in KINDS):            # 종류별 (WASTE: {BOWL: …, CUP: …})
        if kind not in node:
            raise ValueError(f'{where} 는 종류별 자세다 — kind 를 준다: {[k for k in KINDS if k in node]} (받은 값 {kind!r})')
        where, node = f'{where}.{kind}', node[kind]
    if isinstance(node, dict) and 'slots' in node:                          # 슬롯별 (RET_B: {slots: [...]})
        slots = node['slots'] or []
        if isinstance(point, bool) or not isinstance(point, int) or not 1 <= point <= len(slots):
            raise ValueError(f'{where} 는 슬롯이 {len(slots)}개다 — point 에 슬롯 번호(1~{len(slots)})를 준다 (받은 값 {point!r})')
        return f'{where}.slots[{point}]', slots[point - 1]
    if _is_pose(node):
        if point is not None:
            raise ValueError(f'{where} 는 자세가 하나다 — point={point!r} 를 빼고 부른다')
        return where, node
    names = [k for k, v in (node or {}).items() if _is_pose(v)] if isinstance(node, dict) else []
    if not names:
        raise KeyError(f'cell.yaml 의 {where} 에 자세(posj·posx)가 없다 — 한석형(cell.yaml) 에 요청. 값이 없으면 로봇을 움직이지 않는다')
    if point not in names:
        raise ValueError(f'{where} 에는 자세가 여러 개다 — point 로 고른다: {names} (받은 값 {point!r})')
    return f'{where}.{point}', node[point]


def _checked(where, spec):
    """자세 1개의 값을 검사해 실수 목록으로 돌려준다. 비어 있는 키는 뺀다 — 쓸 수 있는 값이 하나도 없으면 KeyError."""
    frame = spec.get('frame')
    if frame not in (None, 'BASE'):
        raise NotImplementedError(f'{where}.frame={frame!r} — 사용자 좌표계 좌표는 못 쓴다. BASE 기준 절대 자세로 적는다')
    out = {}
    for key in _POSE_KEYS:
        pose = spec.get(key)
        if pose is None:
            continue
        if not isinstance(pose, (list, tuple)) or len(pose) != 6 or any(v is None for v in pose):
            raise KeyError(f'cell.yaml 의 {where}.{key} 는 값 6개여야 한다: {pose!r}')
        out[key] = [float(v) for v in pose]
    if not out:
        raise KeyError(f'cell.yaml 의 {where} 가 비어 있다(아직 안 찍은 자세) — 한석형(cell.yaml) 에 요청. 값이 없으면 로봇을 움직이지 않는다')
    return out
