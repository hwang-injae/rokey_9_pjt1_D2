# -*- coding: utf-8 -*-
"""힘 함수 — 담당 박진용 (INF-02b). 함수 표는 docs/03_설계_SDD.md §3.1.

    import cobot_common as cc
    depth, f = cc.contact_down(max_depth=40, limit=cfg['cell']['limits']['contact_limit_n'])
    cc.force_on('z', target=4.0, limit=10.0) → (닦기) → cc.force_off() → cc.safe_retreat()
    cc.move_spiral(rev=2.8, rmax_mm=14, time_s=3) → while not cc.motion_done(): (힘 확인)   # 바닥 나선 (비동기)
    cc.move_arc(mid, end, vel_mm_s=180, vel_deg_s=400, radius_mm=3)                        # 벽면 원호 (이어 붙임)
    cc.move_periodic([0,0,20,0,0,180], [0,0,6.3,0,0,6.3], repeat=3, ref='TOOL', scale=False)   # 컵: 위아래 + 6번 조인트 (TOOL rz)

약속
- 좌표계는 BASE. axis 는 'x'·'y'·'z'. target·limit·min·max 는 **양수 크기(N)** 이고, 누르는 방향(−axis)은 여기서 붙인다.
- 숫자는 인자로 받거나 cfg()['cell'] 에서 읽는다(AGENTS 규칙 6). 키가 없거나 비어 있으면(null) 로봇을 움직이지 않고 KeyError.
    cell.limits : safe_z_mm · timeout_s
    cell.force  : compliance_stx · contact_step_mm · contact_vel_mm_s · contact_acc_mm_s2 ·
                  retreat_vel_mm_s · retreat_acc_mm_s2 · force_max_n · search_y_period_ratio   (이슈 #7 ①, 키 골격 황인재)
    cell.motion : 이동 속도 상한 — move_rel · move_arc 가 읽는다
- 실행 인자 cfg()['run']['vel_scale'](0 초과 1 이하, 첫 실기 0.3)를 이동 속도에 곱한다 — 하강·후퇴 속도, 탐색은 주기를 나눠 느리게.
- 실패는 예외다: ForceLimitError(힘 상한) · MotionTimeout(시간 초과) · RuntimeError(두산 함수가 -1).
  기능 함수(f1·f3)가 받아서 FORCE_LIMIT · TIMEOUT · ROBOT_ERROR 코드로 바꾸고, 후퇴는 safe_retreat().
- 두산 함수는 함수 안에서 dsr() 로 얻는다(메인 스레드 검사 포함). 모듈 맨 위에서 DSR_ROBOT2 를 import 하지 않는다.
- check_force_condition 은 만족 0 / 아니면 -1 이다(DRL 매뉴얼과 다름, TS-01 증상 D) → force_reached() 만 쓴다.
- 순응 중에는 관절 이동(movej) 금지 · 비동기 이동 중 순응 ON 금지(오류 2.1903, 중급교육2) → 켜기 전에 mwait().
- 이동(contact_down 의 한 단계 하강, safe_retreat 의 상승)은 motion.move_rel(황인재, 속도 선택 인자 = 이슈 #7 ②) 을 쓴다.
  그 속도도 cell.motion 의 100 % 기준 × vel_scale 을 넘지 못한다. 순응·힘제어·move_periodic 처럼 힘 함수 자체의 두산 호출만
  dsr() 로 직접 한다.
- 닦기 접촉 모션(move_spiral · move_arc)과 where · motion_done 도 여기 둔다 — 순응·힘제어를 켠 채 도는 동작이라
  힘 상한·해제와 같이 봐야 하고, 기능 함수(f3)는 두산 함수를 직접 부르지 않는다(AGENTS §3 규칙 4).
  이 둘에는 **일시정지 폴링이 없다**(move_periodic 과 같다) → 일시정지는 구간이 끝난 뒤 다음 이동에서 먹는다.
"""
import time

from .bootstrap import cfg, dsr
from . import motion as _motion
from .motion import is_paused, move_rel

__all__ = ['force_on', 'force_off', 'force_release', 'force_reached', 'force_check', 'compliance_on', 'compliance_off',
           'contact_down', 'periodic_search', 'safe_retreat', 'read_force',
           'where', 'joints', 'stop_now', 'motion_done', 'move_spiral', 'move_arc', 'move_periodic',
           'ForceLimitError', 'MotionTimeout']

_AXES = ('x', 'y', 'z')
_state = {'compliance': False, 'force': False, 'limit': None}   # 지금 켜져 있는 것 (safe_retreat 가 본다)


class ForceLimitError(RuntimeError):
    """접촉 힘이 상한을 넘었다 → 기능 함수는 FORCE_LIMIT."""


class MotionTimeout(RuntimeError):
    """접촉 동작이 cell.limits.timeout_s 안에 끝나지 않았다 → 기능 함수는 TIMEOUT."""


# ------------------------------------------------------------------ 공개 함수
def force_on(axis, target, limit):
    """순응 ON(강성 cell.force.compliance_stx) → 목표 힘 ON(−axis 방향으로 target N 누름).

    목표 힘은 절대값(DR_FC_MOD_ABS) — target = 실제로 누르는 힘. 보통 contact_down 으로 닿은 **뒤** 켠다.
    (상대값 REL 은 켜는 순간의 힘에 target 을 더한다 → 닿은 채 켜면 그만큼 더 누른다. 9/19 V-03 에서 닿은 채 ABS 로 확인)
    """
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
        _ok(d.set_desired_force(fd, direction, mod=d.DR_FC_MOD_ABS), 'set_desired_force')
    except BaseException:
        force_off()
        raise
    _state['force'] = True
    _state['limit'] = float(limit)


def compliance_on(stx=None):
    """순응제어만 켠다(힘제어는 켜지 않는다) — 닦기의 나선 구간처럼 **힘 방향과 같은 축으로 움직이는** 동작에 쓴다.

    중급2: 힘제어는 힘 방향과 같은 방향의 모션을 막는다 · 순응제어 중에는 Task 모션만 가능(Move J 계열 2.1903) ·
    비동기·블렌딩 모션이 도는 중에 켜면 2.1903 → 켜기 전 mwait · 목표 자리 근처에서 켜는 것을 권장.
    stx 를 안 주면 cell.force.compliance_stx 를 쓴다.
    """
    d = dsr()
    stx = _force_cfg('compliance_stx') if stx is None else stx
    d.mwait()
    _ok(d.task_compliance_ctrl(stx), 'task_compliance_ctrl')
    _state['compliance'] = True


def compliance_off():
    """순응제어를 끈다(힘제어가 켜져 있으면 함께 끝난다 — 중급2). 켜져 있지 않아도 부를 수 있다."""
    force_off()


def force_off():
    """힘 해제 → 순응 해제 (이 순서). 켜져 있지 않아도 부를 수 있다.

    🚨 하나가 실패해도 **둘 다 시도한 뒤에** 예외를 낸다 — 첫 줄이 force_off() 인 safe_retreat() 의 후퇴까지 막히면 안 된다(#20 검토 1).
    """
    d = dsr()
    failed = []
    if _state['force']:
        try:
            _ok(d.release_force(), 'release_force')
        except BaseException as e:                       # 순응 해제는 반드시 시도한다
            failed.append(e)
    if _state['compliance']:
        try:
            _ok(d.release_compliance_ctrl(), 'release_compliance_ctrl')
        except BaseException as e:
            failed.append(e)
    _state.update(compliance=False, force=False, limit=None)
    if failed:
        raise failed[0]


def force_release():
    """**힘제어만** 끈다 — 순응은 켜 둔 채로. 켜져 있지 않아도 부를 수 있다.

    닦기에서 벽면 구간이 끝난 뒤, 순응을 유지한 채 중심으로 돌아올 때 쓴다(V-03 확정 절차).
    둘 다 끄려면 force_off()/compliance_off(). 중급2: 순응을 끄면 힘제어도 같이 끝난다.
    """
    if not _state['force']:
        return
    d = dsr()
    d.mwait()
    _ok(d.release_force(), 'release_force')
    _state['force'] = False
    _state['limit'] = None


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

    멈추는 조건: **시작할 때보다 Z 힘이 limit 만큼 커짐**(접촉) · 깊이 ≥ max_depth(바닥 못 찾음) —
    둘을 가르는 건 부르는 쪽(depth < max_depth 면 접촉). 돌려주는 force_n 도 시작 대비 변화량이다.
    🚨 절대값으로 보면 안 된다: 툴 무게 설정에 없는 무게(솔·수세미)가 있으면 공중에서도 Fz 가 2 N 쯤 나와서
    내려가기도 전에 "바닥"이 된다(9/20 실기: 깊이 0.1 mm 에서 접촉 오판).
    순응을 켜 두어 단단한 작업대에 닿아도 한 단계만큼의 힘만 걸린다. 끝나면 순응을 끄고 그 자리에 선다.
    힘이 cell.force.force_max_n 을 넘으면 ForceLimitError, cell.limits.timeout_s 를 넘으면 MotionTimeout.
    """
    if max_depth <= 0:
        raise ValueError(f'contact_down: max_depth={max_depth} mm — 0 보다 커야 한다')
    _check_force_args(limit=limit)
    d = dsr()
    step = _force_cfg('contact_step_mm')
    vel = _force_cfg('contact_vel_mm_s') * _vel_scale()
    acc = _force_cfg('contact_acc_mm_s2')
    stx = _force_cfg('compliance_stx')
    f_max = _force_cfg('force_max_n')
    timeout = _limits_cfg('timeout_s')

    d.mwait()
    z0 = _current_z(d)
    f0 = read_force()[2]                                # 내려가기 전 Z 힘 = 기준(툴 무게·옵셋 포함)
    _ok(d.task_compliance_ctrl(stx), 'task_compliance_ctrl')
    _state['compliance'] = True
    waited = 0.0                                        # 🚨 일시정지한 시간은 세지 않는다(PM 요청 9/20 — 사람이 멈춰 둔 동안 TIMEOUT 나면 안 된다)
    last = time.monotonic()
    try:
        while True:
            now = time.monotonic()
            if not is_paused():
                waited += now - last
            last = now
            depth = z0 - _current_z(d)
            f = abs(read_force()[2] - f0)               # 시작 대비 변화량 (누르는 힘)
            if f > f_max:
                raise ForceLimitError(f'contact_down: 누르는 힘 {f:.1f} N > force_max_n {f_max} N (깊이 {depth:.1f} mm)')
            if f >= limit or depth >= max_depth:
                return depth, f
            if waited > timeout:
                raise MotionTimeout(f'contact_down: {timeout} s 안에 접촉·최대 깊이에 닿지 않았다 (깊이 {depth:.1f} mm)')
            dz = min(step, max_depth - depth)
            move_rel(0.0, 0.0, -dz, 'BASE', vel_mm_s=vel, acc_mm_s2=acc)
    finally:
        force_off()


def force_check(axis='z', baseline=None):
    """지금 걸린 힘을 돌려주고, force_on 에 준 limit(과 cell.force.force_max_n)을 넘었으면 ForceLimitError.

    닦기·문지르기 루프에서 **한 걸음마다** 부른다(force_on 의 limit 은 저장만 되므로 — #20 검토 2).
    baseline 을 주면 그 값 대비 변화량으로 본다(툴 무게 옵셋 제거, contact_down 과 같은 방식).
    → (누르는 힘, 옆 힘) — 누르는 힘 = axis 성분, 옆 힘 = 나머지 두 축의 크기.
    """
    i = _axis_index(axis)
    f = read_force()
    base = [0.0, 0.0, 0.0] if baseline is None else [float(v) for v in baseline[:3]]
    fx, fy, fz = (f[k] - base[k] for k in range(3))
    press = abs((fx, fy, fz)[i])
    lateral = (fx ** 2 + fy ** 2 + fz ** 2 - press ** 2) ** 0.5
    f_max = _force_cfg('force_max_n')
    limit = _state['limit']
    if press > f_max:
        raise ForceLimitError(f'force_check: 누르는 힘 {press:.1f} N > force_max_n {f_max} N')
    if limit is not None and press > limit:
        raise ForceLimitError(f'force_check: 누르는 힘 {press:.1f} N > force_on 의 limit {limit} N')
    return press, lateral


def periodic_search(amp, period, duration):
    """Move Periodic 으로 TOOL 기준 X·Y 왕복 탐색(홈 안착). X 주기 period, Y 주기 period × search_y_period_ratio.

    두 축의 주기를 다르게 해서 한 선이 아니라 면을 훑는다(중급교육1 Move Periodic 실습 3). duration(s) 이 시간 한도.
    동기 동작이라 도는 도중에는 멈추지 않는다 — 들어갔는지는 끝난 뒤 부르는 쪽이 깊이·힘으로 판정한다.
    vel_scale < 1 이면 주기를 그만큼 늘려 느리게 한다(진폭·시간 한도는 그대로).
    """
    if amp <= 0 or period <= 0 or duration <= 0:
        raise ValueError(f'periodic_search: amp={amp} mm, period={period} s, duration={duration} s — 모두 0 보다 커야 한다')
    d = dsr()
    ratio = _force_cfg('search_y_period_ratio')
    period = period / _vel_scale()
    period_y = period * ratio
    repeat = max(1, int(duration // period_y))
    d.mwait()
    _ok(d.move_periodic(amp=[float(amp), float(amp), 0.0, 0.0, 0.0, 0.0],
                        period=[float(period), float(period_y), 0.0, 0.0, 0.0, 0.0],
                        repeat=repeat, ref=d.DR_TOOL), 'move_periodic')


def safe_retreat():
    """켜져 있는 힘·순응을 끄고 → X·Y 는 그대로 Z 만 cell.limits.safe_z_mm(BASE) 까지 올린다. 이미 위면 움직이지 않는다.

    🚨 force_off() 가 실패해도 **후퇴는 반드시 시도한다** — 힘이 안 꺼졌다고 툴을 용기 안에 두고 오면 더 위험하다.
       (끄기 실패는 후퇴한 뒤에 올린다. PM 검토 9/20)
    """
    d = dsr()
    safe_z = _limits_cfg('safe_z_mm')
    vel = _force_cfg('retreat_vel_mm_s') * _vel_scale()
    acc = _force_cfg('retreat_acc_mm_s2')
    off_error = None
    try:
        force_off()
    except BaseException as e:                       # noqa: BLE001 — 후퇴가 먼저다
        off_error = e
    z = _current_z(d)
    if z < safe_z:
        move_rel(0.0, 0.0, float(safe_z) - z, 'BASE', vel_mm_s=vel, acc_mm_s2=acc)
    if off_error is not None:
        raise off_error


# ------------------------------------------------------------------ 닦기 이동 (나선 · 원호) — 접촉 동작 전용
# 🔸 여기 두는 이유: 순응·힘제어를 켠 채 도는 접촉 모션이라 힘 함수와 같이 봐야 한다(AGENTS §3 규칙 4 — f3 는 cc.* 만 부른다).
#    자유 공간 이동은 motion.py(황인재) 몫이다. 두 함수 모두 **일시정지 폴링이 없다** — move_periodic 과 같은 취급이라
#    일시정지는 이 구간이 끝난 뒤 다음 이동에서 먹는다. 부르는 쪽이 구간 사이에서 is_halted() 를 본다.
def where():
    """지금 TCP 자세 [x, y, z, a, b, c] (BASE). 닦는 높이·나선이 실제로 돌았는지 확인에 쓴다."""
    d = dsr()
    pos, _ = d.get_current_posx(ref=d.DR_BASE)
    return [float(v) for v in pos]


def joints():
    """지금 관절 각도 [j1 … j6] (deg). 컵 닦기가 6번 축 360° 회전 전에 한계(±360°)를 확인하는 데 쓴다."""
    return [float(v) for v in dsr().get_current_posj()]


def stop_now():
    """지금 하던 동작을 **즉시 정지**(QSTOP · Stop Category 2 — 서보 전원 유지). 멈출 때까지 최대 3 s 기다린다.
    비동기 모션(Periodic 등)이 도는 중에 감시하다 이상을 보면 부른다. 정지는 통신 노드가 보낸다.
    🟡 motion.py(황인재)의 내부 함수 _call('stop') 을 쓴다 — 공개 함수가 생기면 그것으로 바꾼다(PR #56 리뷰)."""
    _motion._call('stop')
    t0 = time.monotonic()
    while not motion_done() and time.monotonic() - t0 < 3.0:
        time.sleep(0.01)


def motion_done():
    """비동기 이동이 끝났나 (check_motion() == 0). move_spiral 이 도는 동안 힘을 보려고 쓴다."""
    return dsr().check_motion() == 0


def move_spiral(rev, rmax_mm, time_s, axis='z', ref='TOOL'):
    """나선(Move Spiral)을 **비동기로 시작**한다 — 끝을 기다리지 않는다(부르는 쪽이 motion_done() 으로 본다).

    🚨 속도(vel)로 부르면 드라이버(dsr_controller2)가 통째로 멈춘다(브링업 재시작). **vel·acc 0 + time** 으로만 부른다
       — 중급교육1 p.69 "[속도] → [시간] 지정 옵션을 이용하여 속도 설정", 9/20 실기로 확인.
    🚨 최대 반경에 비해 회전 수가 많으면 **시작조차 하지 않는다**(같은 쪽 경고) — 반경 14 mm 에 7바퀴·1.5 s 는 안 돌고
       2.8바퀴·3 s 는 돈다. 돌았는지는 부르는 쪽이 where() 로 확인한다.
    비동기라 순응이 이미 켜져 있어야 하고(중급1 p.69 "순응제어 및 비동기 제어를 활용하는 경우가 많다"),
    켤 때는 도는 중이 아니어야 한다(2.1903) → 여기서 먼저 mwait 한다.
    """
    if rev <= 0 or rmax_mm <= 0 or time_s <= 0:
        raise ValueError(f'move_spiral: rev={rev} · rmax={rmax_mm} mm · time={time_s} s — 모두 0 보다 커야 한다')
    d = dsr()
    axis_c = _axis_const(d, axis)
    ref_c = {'BASE': d.DR_BASE, 'TOOL': d.DR_TOOL}[ref]
    d.mwait()
    _ok(d.amove_spiral(rev=float(rev), rmax=float(rmax_mm), lmax=0.0, vel=[0.0, 0.0], acc=[0.0, 0.0],
                       time=float(time_s) / _vel_scale(), axis=axis_c, ref=ref_c), 'amove_spiral')


def move_periodic(amp, period, repeat, ref='TOOL', atime=None, scale=True):
    """Move Periodic 을 **비동기로 시작**한다 — 끝을 기다리지 않는다(부르는 쪽이 motion_done() 으로 본다).

    amp · period 는 **[x, y, z, rx, ry, rz]** 6개. 길이 mm · 회전 deg · 주기 s.
    한 명령으로 **이동과 회전을 같이** 왕복한다(중급교육1 p.71 "일정한 진폭과 주기로 왕복 이동/회전 모션",
    p.73~75 실습 50 mm/2 s · 15°/2 s · 축마다 다른 주기).
    🚨 9/21: ref=TOOL 의 회전 칸은 TCP 설정에 따라 도는 조인트가 달라진다 — 실기(TCP GripperDA_v1)에서 TOOL rx 가
       **4번 조인트**를 돌렸다 — 두산 정의대로다(rx 는 옆으로 누운 축). **그리퍼 축 회전 = TOOL rz = 6번 조인트.**
       🚨 Virtual 은 rx ↔ rz 를 뒤바꿔 움직이고, BASE rz 는 1·4번 조인트를 돌렸다 → Periodic 회전은 Virtual 결과를 믿지 않는다.
       부르는 쪽이 도는 동안 조인트를 감시한다(wipe_cup).
    🚨 어떤 축에 진폭을 주면 **같은 축의 주기도 줘야 한다**(반대도 마찬가지) — 빠지면 두산 오류 2.1218 (p.71~72).
    repeat = 왕복 횟수. 한 번 왕복하면 출발한 자리로 돌아온다(진폭은 편진폭 — 총 이동거리는 2배, p.71 그림).
    vel_scale < 1 이면 주기를 그만큼 늘려 느리게 한다(진폭은 그대로 — periodic_search 와 같은 방식).
    scale=False 면 주기를 그대로 쓴다 — 컵 세척은 vel_scale 예외(결정 E17).
    """
    if len(amp) != 6 or len(period) != 6:
        raise ValueError('move_periodic: amp · period 는 [x, y, z, rx, ry, rz] 6개로 준다')
    for i, (a, t) in enumerate(zip(amp, period)):
        if (a != 0) != (t != 0):                           # 한쪽만 준 축 → 2.1218
            raise ValueError(f'move_periodic: {i}번 축은 진폭({a})과 주기({t}) 중 하나만 있다 — '
                             '같은 축의 둘을 함께 준다(중급1 p.71, 두산 오류 2.1218)')
    if repeat < 1:
        raise ValueError(f'move_periodic: repeat={repeat} — 1 이상')
    d = dsr()
    slow = 1.0 / _vel_scale() if scale else 1.0
    d.mwait()
    _ok(d.amove_periodic(amp=[float(v) for v in amp], period=[float(v) * slow for v in period],
                         atime=0.0 if atime is None else float(atime),
                         repeat=int(repeat), ref={'BASE': d.DR_BASE, 'TOOL': d.DR_TOOL}[ref]), 'amove_periodic')


def move_arc(mid, end, vel_mm_s, vel_deg_s, radius_mm=0.0):
    """원호(Move C) — BASE 절대 자세 두 개(가운데·끝)를 지나는 호. 회전(a·b·c)도 같이 간다.

    radius_mm > 0 이면 다음 모션으로 **이어 붙는다**(중첩 가능한 모션은 Move L·C·J·JX 뿐 — 중급교육1 p.79).
    0 이면 그 자리에서 멈춘다 — 0 으로 이어 붙이면 원호마다 서서 작업대가 울린다(9/20 실기).
    속도에는 vel_scale 을 곱하고, cell.motion 의 100 % 기준을 넘지 못한다.
    """
    d = dsr()
    s = _vel_scale()
    top_v, top_a = float(_cell_key('motion', 'vel_tcp_max_mm_s')), float(_cell_key('motion', 'acc_tcp_max_mm_s2'))
    vel = [min(_positive('vel_mm_s', vel_mm_s) * s, top_v * s), _positive('vel_deg_s', vel_deg_s) * s]
    acc = [top_a * s, top_a * s]
    _ok(d.movec([float(v) for v in mid], [float(v) for v in end], vel=vel, acc=acc,
                radius=float(radius_mm), ref=d.DR_BASE, mod=d.DR_MV_MOD_ABS), 'movec')


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


def _positive(name, v):
    if v is None or float(v) <= 0:
        raise ValueError(f'{name}={v} — 0 보다 커야 한다')
    return float(v)


def _current_z(d):
    pos, _ = d.get_current_posx(ref=d.DR_BASE)
    return float(pos[2])


def _force_cfg(key):
    return _cell_key('force', key)


def _limits_cfg(key):
    return _cell_key('limits', key)


def _vel_scale():
    """실행 인자 vel_scale (config.load 가 0 초과 1 이하로 검사한다). 없으면 1.0."""
    return float(cfg().get('run', {}).get('vel_scale', 1.0))


def _cell_key(section, key):
    try:
        value = cfg()['cell'][section][key]
    except (KeyError, TypeError):
        value = None
    if value is None:                   # 키가 없거나 INF-04 골격처럼 비어 있음(null)
        raise KeyError(f'cell.yaml 의 cell.{section}.{key} 가 없거나 비어 있다 — 한석형(cell.yaml) 에 요청. '
                       '값이 없으면 로봇을 움직이지 않는다')
    return value
