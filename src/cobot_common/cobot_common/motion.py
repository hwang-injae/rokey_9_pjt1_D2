# -*- coding: utf-8 -*-
"""이동 함수(저수준) — 담당 황인재 (INF-02, 9/19 재분담 — 결정 기록 W3). 함수 표는 docs/03_설계_SDD.md §3.1.

    import cobot_common as cc
    up = cc.move_to('TOOL_SPONGE', carrying=False)     # 안전 높이를 거쳐 홀더 **상공**까지. up = 티칭 자세까지 남은 높이(mm)
    cc.move_rel(0, 0, -up, 'BASE')                     # 내려가는 것은 부르는 쪽이 한다 (접촉이면 cc.contact_down)
    cc.move_joint_rel(5, +15.0, time_s=0.3)            # 관절 하나만 상대 이동 (털기·물 털기)

규칙
- 🚨 **값이 비어 있으면 로봇을 움직이지 않고 KeyError** — 어느 키가 없는지 알려 준다(force.py 와 같은 방식).
  필요한 값을 **전부 읽은 뒤에** 첫 명령을 보낸다.
- 🚨 move_to 는 **안전 높이(cell.limits.safe_z_mm) 아래로 내려가지 않는다.** 티칭 자세가 더 낮으면 그 상공에서 멈추고
  남은 높이를 돌려준다. 하강은 move_rel(자유 공간) 또는 contact_down(접촉)으로 — 접촉 동작의 힘 상한·후퇴·타임아웃은 그쪽 몫이다.
- 속도 = (100 % 기준 속도 cell.motion.*_max_*) × (cell.limits.vel_free_pct 또는 vel_carry_pct) × cfg()['run']['vel_scale'].
  move_rel 에 속도를 직접 주면 그 값을 쓰되(부르는 쪽이 vel_scale 을 곱한다 — force.py 방식), 위 상한은 넘지 못한다.
- 실패(두산 함수 반환이 0 이 아님)는 RuntimeError. 기능 함수가 코드로 바꾸고, 새어 나가면 flow 가 ROBOT_ERROR 로 바꾼다.
- 그리퍼 함수는 여기 두지 않는다 → gripper.py (민범진, INF-02d).

🟡 아직 없는 것(PR 본문 참고): 사용자 좌표계(frame: RETURN·BED …)의 좌표 — 지금은 BASE 좌표만 · 팔레트 칸(RACK_*) 이동 · 회전을 포함한 상대 이동.
"""
from .bootstrap import cfg, dsr

__all__ = ['move_to', 'move_rel', 'move_joint_rel']

FRAMES = ('BASE', 'TOOL')
_POSE_KEYS = ('posj', 'posx', 'origin_posx')        # 자세를 담는 키 (SDD §4.3)
_GROUPS = ('stations', 'beds', 'zones')             # move_to 가 이름을 찾는 곳 (IRD §2 의 station · zone_id)
_Z = 2


# ------------------------------------------------------------------ 공개 함수
def move_to(station, carrying):
    """안전 높이를 거쳐 station(상공)으로 간다. 들고 있으면(carrying) 느린 속도. → 티칭 자세까지 남은 높이 mm (0.0 이면 그 자세)

    station: cell.stations(HOME·WEIGH·…) · cell.beds(SPONGE_BED_*) · cell.zones(RET_*) 의 이름.
    경로: ① 지금 높이가 안전 높이보다 낮으면 곧게 위로 ② posj 목표면 관절 이동 / posx 목표면 안전 높이 이상에서 목표 XY 로.
    안전 자세 복귀는 move_to('HOME', False).
    """
    pose_key, pose = _named_pose(station)
    safe_z = float(_limit('safe_z_mm'))
    pct = _limit('vel_carry_pct' if carrying else 'vel_free_pct')
    vel_l, acc_l = _tcp_speed(pct)
    vel_j, acc_j = _joint_speed(pct)
    d = dsr()                                       # 여기까지 오류가 없을 때만 로봇에 손댄다

    now, _ = d.get_current_posx(ref=d.DR_BASE)
    if float(now[_Z]) < safe_z:                     # ① 곧게 위로
        _ok(d.movel([0.0, 0.0, safe_z - float(now[_Z]), 0.0, 0.0, 0.0], vel=vel_l, acc=acc_l,
                    ref=d.DR_BASE, mod=d.DR_MV_MOD_REL), f'movel(안전 높이 {safe_z:g} mm 로 상승)')
    if pose_key == 'posj':                          # ② 관절 자세 (HOME)
        _ok(d.movej([float(v) for v in pose], vel=vel_j, acc=acc_j), f'movej({station})')
        return 0.0
    target = [float(v) for v in pose]
    above = max(0.0, safe_z - target[_Z])           # 티칭 자세가 안전 높이보다 낮으면 그만큼 위에서 멈춘다
    target[_Z] += above
    _ok(d.movel(target, vel=vel_l, acc=acc_l, ref=d.DR_BASE, mod=d.DR_MV_MOD_ABS), f'movel({station})')
    return above


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
    d = dsr()
    ref = {'BASE': d.DR_BASE, 'TOOL': d.DR_TOOL}[frame]
    _ok(d.movel([float(dx), float(dy), float(dz), 0.0, 0.0, 0.0], vel=vel, acc=acc, ref=ref, mod=d.DR_MV_MOD_REL),
        f'movel(move_rel {frame} {dx:g},{dy:g},{dz:g})')


def move_joint_rel(joint, delta_deg, *, time_s=None, carrying=True):
    """관절 하나(joint = 1~6)를 지금 각도에서 delta_deg 만큼 돌린다. 나머지 관절은 그대로. (DSN-03 B11 — 털기·물 털기의 J5/J6 왕복)

    time_s 를 주면 그 시간에 맞춰 움직인다(왕복 주기를 맞출 때) — vel_scale < 1 이면 시간을 그만큼 늘린다.
    안 주면 cell.limits 속도(carrying 이면 vel_carry_pct, 아니면 vel_free_pct) × vel_scale.
    🚨 순응·힘제어가 켜져 있으면 관절 이동이 안 된다(두산 오류 2.1903) → force_off() 뒤에 부른다.
    """
    if joint not in (1, 2, 3, 4, 5, 6):
        raise ValueError(f'move_joint_rel: joint={joint!r} — 1~6 (J1~J6)')
    delta = [0.0] * 6
    delta[joint - 1] = float(delta_deg)
    if time_s is not None:
        kwargs = {'time': _positive('time_s', time_s) / _vel_scale()}
    else:
        vel, acc = _joint_speed(_limit('vel_carry_pct' if carrying else 'vel_free_pct'))
        kwargs = {'vel': vel, 'acc': acc}
    d = dsr()
    _ok(d.movej(delta, mod=d.DR_MV_MOD_REL, **kwargs), f'movej(move_joint_rel J{joint} {delta_deg:+g}°)')


# ------------------------------------------------------------------ 내부
def _ok(ret, what):
    if ret != 0:
        raise RuntimeError(f'{what} 실패 (반환 {ret!r})')


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


def _named_pose(name):
    """이름 → ('posj'|'posx', 값 6개). 값이 비어 있거나 BASE 좌표가 아니면 오류(로봇을 움직이지 않는다)."""
    cell = cfg().get('cell') or {}
    for group in _GROUPS:
        entry = (cell.get(group) or {}).get(name)
        if entry is None:
            continue
        frame = entry.get('frame')
        if frame not in (None, 'BASE'):
            raise NotImplementedError(f'cell.{group}.{name}.frame={frame!r} — 사용자 좌표계 좌표는 아직 못 쓴다. '
                                      'BASE 좌표로 적거나 frame 을 비운다(티칭 방식은 한석형과 정한다)')
        for key in _POSE_KEYS:
            pose = entry.get(key)
            if pose is None:
                continue
            if len(pose) != 6 or any(v is None for v in pose):
                raise KeyError(f'cell.yaml 의 cell.{group}.{name}.{key} 는 값 6개여야 한다: {pose!r}')
            return ('posj' if key == 'posj' else 'posx'), pose
        raise KeyError(f'cell.yaml 의 cell.{group}.{name} 에 좌표(posj·posx·origin_posx)가 없거나 비어 있다 — '
                       '한석형(cell.yaml) 에 요청. 값이 없으면 로봇을 움직이지 않는다')
    raise KeyError(f'{name!r} 는 cell.yaml 의 {_GROUPS} 어디에도 없다 (이름은 IRD §2 그대로)')
