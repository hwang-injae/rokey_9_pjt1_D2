# -*- coding: utf-8 -*-
"""힘 함수 — 담당 박진용 (INF-02b). 함수 표는 docs/03_설계_SDD.md §3.1.

    import cobot_common as cc
    depth, f = cc.contact_down(max_depth=40, limit=cfg['cell']['limits']['contact_limit_n'])
    cc.force_on('z', target=4.0, limit=10.0) → (닦기) → cc.force_off() → cc.safe_retreat()

약속
- 좌표계는 BASE. axis 는 'x'·'y'·'z'. target·limit·min·max 는 **양수 크기(N)** 이고, 누르는 방향(−axis)은 여기서 붙인다.
- 숫자는 인자로 받거나 cfg()['cell'] 에서 읽는다(AGENTS 규칙 6). 필요한 키가 없으면 로봇을 움직이지 않고 KeyError.
    cell.limits : safe_z_mm · timeout_s
    cell.force  : compliance_stx · contact_step_mm · contact_vel_mm_s · contact_acc_mm_s2 ·
                  retreat_vel_mm_s · retreat_acc_mm_s2 · force_max_n · search_y_period_ratio
- 실패는 예외다: ForceLimitError(힘 상한) · MotionTimeout(시간 초과) · RuntimeError(두산 함수가 -1).
  기능 함수(f1·f3)가 받아서 FORCE_LIMIT · TIMEOUT · ROBOT_ERROR 코드로 바꾸고, 후퇴는 safe_retreat().
- 두산 함수는 함수 안에서 dsr() 로 얻는다(메인 스레드 검사 포함). 모듈 맨 위에서 DSR_ROBOT2 를 import 하지 않는다.
- check_force_condition 은 만족 0 / 아니면 -1 이다(DRL 매뉴얼과 다름, TS-01 증상 D) → force_reached() 만 쓴다.
- 순응 중에는 관절 이동(movej) 금지 · 비동기 이동 중 순응 ON 금지(오류 2.1903, 중급교육2) → 켜기 전에 mwait().
"""
import time

from .bootstrap import cfg, dsr

__all__ = ['force_on', 'force_off', 'force_reached', 'contact_down', 'periodic_search', 'safe_retreat',
           'read_force', 'ForceLimitError', 'MotionTimeout']

_AXES = ('x', 'y', 'z')
_state = {'compliance': False, 'force': False, 'limit': None}   # 지금 켜져 있는 것 (safe_retreat 가 본다)


class ForceLimitError(RuntimeError):
    """접촉 힘이 상한을 넘었다 → 기능 함수는 FORCE_LIMIT."""


class MotionTimeout(RuntimeError):
    """접촉 동작이 cell.limits.timeout_s 안에 끝나지 않았다 → 기능 함수는 TIMEOUT."""


# ------------------------------------------------------------------ 공개 함수
def force_on(axis, target, limit):
    """순응 ON(강성 cell.force.compliance_stx) → 목표 힘 ON(−axis 방향으로 target N 누름, 상대 모드)."""
    i = _axis_index(axis)
    _check_force_args(target=target, limit=limit)
    if target >= limit:
        raise ValueError(f'force_on: target {target} N 이 limit {limit} N 보다 작아야 한다')
    d = dsr()
    stx = _force_cfg('compliance_stx')
    d.mwait()                                              # 비동기 이동 중 순응 ON 은 2.1903
    _ok(d.task_compliance_ctrl(stx), 'task_compliance_ctrl')
    _state['compliance'] = True
    fd = [0.0] * 6
    direction = [0] * 6
    fd[i] = -float(target)
    direction[i] = 1
    try:
        _ok(d.set_desired_force(fd, direction, mod=d.DR_FC_MOD_REL), 'set_desired_force')
    except BaseException:
        force_off()
        raise
    _state['force'] = True
    _state['limit'] = float(limit)


def force_off():
    """힘 해제 → 순응 해제 (이 순서). 켜져 있지 않아도 불러도 된다."""
    d = dsr()
    if _state['force']:
        _ok(d.release_force(), 'release_force')
    if _state['compliance']:
        _ok(d.release_compliance_ctrl(), 'release_compliance_ctrl')
    _state.update(compliance=False, force=False, limit=None)


def force_reached(axis, min=None, max=None):
    """BASE 기준 axis 의 힘 크기가 [min, max] 안이면 True. check_force_condition(...) == 0 을 감싼 것."""
    if min is None and max is None:
        raise ValueError('force_reached: min 과 max 중 하나는 준다')
    for name, v in (('min', min), ('max', max)):
        if v is not None and v < 0:
            raise ValueError(f'force_reached: {name}={v} — 힘 크기(0 이상)로 준다')
    d = dsr()
    ret = d.check_force_condition(_axis_const(d, axis),
                                  min=d.DR_COND_NONE if min is None else float(min),
                                  max=d.DR_COND_NONE if max is None else float(max),
                                  ref=d.DR_BASE)
    return ret == 0


def read_force():
    """툴에 걸린 외력 [fx, fy, fz, mx, my, mz] (힘은 BASE 기준 N, 모멘트는 TOOL 기준 Nm)."""
    d = dsr()
    f = d.get_tool_force(ref=d.DR_BASE)
    if not isinstance(f, (list, tuple)) or len(f) != 6:
        raise RuntimeError(f'get_tool_force 실패: {f!r}')
    return [float(x) for x in f]


def contact_down(max_depth, limit):
    """순응 ON 상태로 contact_step_mm 씩 내려가며 Z 힘이 limit 에 닿을 때까지 → (depth_mm, force_n).

    멈추는 조건: 힘 ≥ limit(접촉) · 깊이 ≥ max_depth(바닥 못 찾음) — 둘을 가르는 건 부르는 쪽(depth < max_depth 면 접촉).
    순응을 켜 두어 단단한 작업대에 닿아도 한 단계만큼의 힘만 걸린다. 끝나면 순응을 끄고 그 자리에 선다.
    힘이 cell.force.force_max_n 을 넘으면 ForceLimitError, cell.limits.timeout_s 를 넘으면 MotionTimeout.
    """
    if max_depth <= 0:
        raise ValueError(f'contact_down: max_depth={max_depth} mm — 0 보다 커야 한다')
    _check_force_args(limit=limit)
    d = dsr()
    step = _force_cfg('contact_step_mm')
    vel = _force_cfg('contact_vel_mm_s')
    acc = _force_cfg('contact_acc_mm_s2')
    stx = _force_cfg('compliance_stx')
    f_max = _force_cfg('force_max_n')
    timeout = _limits_cfg('timeout_s')

    d.mwait()
    z0 = _current_z(d)
    _ok(d.task_compliance_ctrl(stx), 'task_compliance_ctrl')
    _state['compliance'] = True
    t0 = time.monotonic()
    try:
        while True:
            depth = z0 - _current_z(d)
            f = abs(read_force()[2])
            if f > f_max:
                raise ForceLimitError(f'contact_down: |Fz| {f:.1f} N > force_max_n {f_max} N (깊이 {depth:.1f} mm)')
            if force_reached('z', min=limit) or depth >= max_depth:
                return depth, f
            if time.monotonic() - t0 > timeout:
                raise MotionTimeout(f'contact_down: {timeout} s 안에 접촉·최대 깊이에 닿지 않았다 (깊이 {depth:.1f} mm)')
            dz = min(step, max_depth - depth)
            _ok(d.movel([0.0, 0.0, -dz, 0.0, 0.0, 0.0], vel=vel, acc=acc, ref=d.DR_BASE, mod=d.DR_MV_MOD_REL),
                'movel(contact_down)')
    finally:
        force_off()


def periodic_search(amp, period, duration):
    """Move Periodic 으로 TOOL 기준 X·Y 왕복 탐색(홈 안착). X 주기 period, Y 주기 period × search_y_period_ratio.

    두 축의 주기를 다르게 해서 한 선이 아니라 면을 훑는다(중급교육1 Move Periodic 실습 3). duration(s) 이 시간 한도.
    동기 동작이라 도는 도중에는 멈추지 않는다 — 들어갔는지는 끝난 뒤 부르는 쪽이 깊이·힘으로 판정한다.
    """
    if amp <= 0 or period <= 0 or duration <= 0:
        raise ValueError(f'periodic_search: amp={amp} mm, period={period} s, duration={duration} s — 모두 0 보다 커야 한다')
    d = dsr()
    ratio = _force_cfg('search_y_period_ratio')
    period_y = period * ratio
    repeat = max(1, int(duration // period_y))
    d.mwait()
    _ok(d.move_periodic(amp=[float(amp), float(amp), 0.0, 0.0, 0.0, 0.0],
                        period=[float(period), float(period_y), 0.0, 0.0, 0.0, 0.0],
                        repeat=repeat, ref=d.DR_TOOL), 'move_periodic')


def safe_retreat():
    """켜져 있는 힘·순응을 끄고 → X·Y 는 그대로 Z 만 cell.limits.safe_z_mm(BASE) 까지 올린다. 이미 위면 움직이지 않는다."""
    d = dsr()
    safe_z = _limits_cfg('safe_z_mm')
    vel = _force_cfg('retreat_vel_mm_s')
    acc = _force_cfg('retreat_acc_mm_s2')
    force_off()
    pos, _ = d.get_current_posx(ref=d.DR_BASE)
    if pos[2] >= safe_z:
        return
    target = [float(v) for v in pos]
    target[2] = float(safe_z)
    _ok(d.movel(target, vel=vel, acc=acc, ref=d.DR_BASE), 'movel(safe_retreat)')


# ------------------------------------------------------------------ 내부
def _ok(ret, what):
    if ret != 0:
        raise RuntimeError(f'{what} 실패 (반환 {ret!r})')


def _axis_index(axis):
    if axis not in _AXES:
        raise ValueError(f"axis={axis!r} — 'x'·'y'·'z' 중 하나")
    return _AXES.index(axis)


def _axis_const(d, axis):
    return (d.DR_AXIS_X, d.DR_AXIS_Y, d.DR_AXIS_Z)[_axis_index(axis)]


def _check_force_args(**kw):
    f_max = _force_cfg('force_max_n')
    for name, v in kw.items():
        if not 0 < v <= f_max:
            raise ValueError(f'{name}={v} N — 0 보다 크고 cell.force.force_max_n({f_max} N) 이하여야 한다')


def _current_z(d):
    pos, _ = d.get_current_posx(ref=d.DR_BASE)
    return float(pos[2])


def _force_cfg(key):
    return _cell_key('force', key)


def _limits_cfg(key):
    return _cell_key('limits', key)


def _cell_key(section, key):
    try:
        return cfg()['cell'][section][key]
    except (KeyError, TypeError):
        raise KeyError(f'cell.yaml 에 cell.{section}.{key} 가 없다 — 한석형(cell.yaml)·INF-04 에 요청. '
                       '값이 없으면 로봇을 움직이지 않는다') from None
