# -*- coding: utf-8 -*-
"""wipe_bowl(F3-02) 시험 — 로봇 없이 가짜 공용 함수로 순서·판정·실패 처리를 본다.

    python3 -m pytest -q src/f3_wipe/test/test_f3_wipe_bowl.py

**9/20 실기(V-03)로 확정한 절차 그대로**인지 본다:
빠른 접근 → 바닥 찾기(contact_down) → 순응 ON → 나선(힘제어 없이) → 힘제어 1.5 N → 벽면 원호 → 힘제어만 OFF → 중심 복귀.
벽만 찾지 않는다(반지름을 그릇·툴 지름으로 계산 — 결정 E6).
실제 힘 값·닦는 높이는 실기에서 본다 — 여기서는 "순서·반지름·비틀기·상한 처리"만 본다.
"""
import math

import pytest

from cobot_api import FORCE_LIMIT, OK, ROBOT_ERROR, TIMEOUT
from f3_wipe import wipe

WALL_R = (110.0 - 90.0) / 2 + 4.0       # 벽 반지름 = (그릇 안지름 − 툴 지름)/2 + 벽 누름 = 14 mm
UP = 167.0                              # 접근점(z 235) → 바닥(z 68, 9/20 실측) 까지 남은 높이
CFG = {
    'run': {'vel_scale': 0.3},
    'cell': {'limits': {'safe_z_mm': 235.0, 'contact_limit_n': 2.0}},
    'f3': {'wipe_bowl': {
        'tool': {'clean_h_mm': 35, 'd_mm': 90},
        'fast_down_mm': 135.0, 'fast_vel_mm_s': 180.0, 'fast_acc_mm_s2': 360.0, 'find_max_mm': 40.0,
        'target_force_n': 1.5, 'limit_n': 10.0, 'lateral_max_n': 25.0,
        'bowl_inner_d_mm': 110.0, 'wall_press_mm': 4.0,
        'spiral_pitch_mm': 5.0, 'spiral_time_s': 3.0,
        'turns': 3, 'wall_arc_deg': 90.0, 'wall_approach_vel_mm_s': 60.0,
        'twist_deg': 18.0, 'blend_radius_mm': 3.0, 'lin_vel_mm_s': 180.0, 'rot_vel_deg_s': 400.0,
        'force_every': 4, 'sample_s': 0.0, 'duration_s': 120, 'log_dir': 'logs/f3',
    }},
}
POSE0 = [400.0, 0.0, 235.0, 45.0, 180.0, 45.0]      # 접근점 (닦는 자리 상공)
FAST = 135.0                                        # 빠른 하강 = fast_down_mm (티칭 끝점과 무관)
FIND = 14.0                                         # 가짜 바닥: 빠른 접근 뒤 이만큼 더 내려가면 닿는다
CENTER = [POSE0[0], POSE0[1], POSE0[2] - FAST - FIND]   # 바닥에 닿은 자리 = 나선의 중심


class _Logger:
    def __init__(self):
        self.lines = []

    def info(self, m):
        self.lines.append(('info', m))

    def error(self, m):
        self.lines.append(('error', m))


class FakeCell:
    """가짜 셀 — 공용 함수 호출을 적어 두고, 그릇 안의 힘을 흉내 낸다."""

    def __init__(self, press=1.5, lateral=1.0, spiral_moves=True, up=UP, spiral_dir=+1, find=FIND):
        self.calls = []
        self.press, self.lateral, self.up = press, lateral, up
        self.find = find                                 # 바닥을 찾기까지 내려간 거리
        self.spiral_moves = spiral_moves                 # False = 명령은 받지만 돌지 않는다(9/20 실기 증상)
        self.spiral_dir = spiral_dir                     # BASE 에서 본 나선 방향 (+1 반시계 · −1 시계)
        self.pose = list(POSE0)
        self.poses = []
        self.spiral = None                               # 도는 중인 나선 (남은 조각 수, 반지름, 회전 수)
        self.moving = False
        self.touched = False                             # 닦는 높이까지 내려온 뒤부터 힘이 걸린 것으로 본다
        self.halted = False
        self.off = None
        self.logger = _Logger()

    # ---- cobot_common 대역
    def cfg(self):
        return CFG

    def move_to(self, station, carrying, kind=None, point=None):
        self.calls.append(('move_to', station, point))
        self.pose = list(POSE0)
        return self.up

    def move_rel(self, dx, dy, dz, frame, **kw):
        self.calls.append(('move_rel', round(dz, 2), round(kw.get('vel_mm_s') or 0.0, 1)))
        self.pose = [self.pose[0] + dx, self.pose[1] + dy, self.pose[2] + dz] + self.pose[3:]
        self.poses.append(list(self.pose))

    def contact_down(self, max_depth, limit):
        self.calls.append(('contact_down', max_depth, limit))
        found = min(self.find, max_depth)
        self.pose[2] -= found
        self.touched = found < max_depth
        return found, limit

    def compliance_on(self, stx=None):
        self.calls.append(('compliance_on',))

    def force_on(self, axis, target, limit):
        self.calls.append(('force_on', axis, round(target, 2), limit))

    def force_release(self):
        self.calls.append(('force_release',))

    def read_force(self):
        """공중 치우침 2 N. 바닥에 닿은 뒤부터 누르는 힘·옆 힘이 걸린 것으로 본다."""
        if not self.touched:
            return [0.0, 0.0, 2.0, 0.0, 0.0, 0.0]
        return [self.lateral, 0.0, 2.0 + self.press, 0.0, 0.0, 0.0]

    def force_off(self):
        self.calls.append(('force_off',))
        self.off = len(self.poses)                       # 여기까지가 닦기 — 뒤는 HOME 복귀

    def safe_retreat(self):
        self.calls.append(('safe_retreat',))

    def is_halted(self):
        return self.halted

    def io_node(self):
        return self

    def get_logger(self):
        return self.logger

    # ---- 접촉 모션 (force.py 공용 함수) 대역
    def where(self):
        return list(self.pose)

    def motion_done(self):
        """나선을 조각내어 실제로 돌려 준다 — 방향(부호)까지 흉내 내야 벽면 방향 시험이 뜻이 있다."""
        if self.spiral is None:
            return True
        k, steps, rmax, rev = self.spiral
        if k >= steps:
            self.spiral = None
            return True
        self.spiral = (k + 1, steps, rmax, rev)
        if self.spiral_moves:
            f = (k + 1) / steps                          # 반지름·각도가 같이 커진다
            th = self.spiral_dir * rev * 2 * math.pi * f
            self.pose[0] = CENTER[0] + rmax * f * math.cos(th)
            self.pose[1] = CENTER[1] + rmax * f * math.sin(th)
        return False

    def move_spiral(self, rev, rmax_mm, time_s):
        self.calls.append(('spiral', rev, rmax_mm, time_s))
        self.spiral = (0, 40, rmax_mm, rev)              # 40 조각으로 나눠 돈다

    def move_arc(self, mid, end, vel_mm_s, vel_deg_s, radius_mm):
        self.calls.append(('arc', round(radius_mm, 1)))
        self.pose = list(end)
        self.poses.append(list(end))


@pytest.fixture
def cell(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)                      # 힘 로그는 실행 위치 기준 상대경로
    c = FakeCell()
    for name in ('cfg', 'move_to', 'move_rel', 'contact_down', 'compliance_on', 'force_on', 'force_release',
                 'read_force', 'force_off', 'safe_retreat',
                 'io_node', 'is_halted', 'where', 'motion_done', 'move_spiral', 'move_arc'):
        monkeypatch.setattr(wipe.cc, name, getattr(c, name), raising=False)
    return c


def _center(c):
    """바닥에 닿은 자리 = 나선의 중심."""
    return [POSE0[0], POSE0[1], POSE0[2] - FAST - c.find]


def _wiped(c):
    """HOME 복귀 이동을 뺀 닦기 자세들."""
    return c.poses[:c.off]


def _ended_home(c):
    """힘을 끄고 → 곧게 올려 → HOME(관절)으로 끝났나."""
    names = [x[0] for x in c.calls]
    tail = names[len(names) - 1 - names[::-1].index('force_off'):]
    return c.calls[-1][:2] == ('move_to', 'HOME') and tail[0] == 'force_off' and 'move_rel' in tail


def _radii(poses, center):
    return [math.hypot(p[0] - center[0], p[1] - center[1]) for p in poses]


def test_confirmed_order(cell):
    """9/20 실기 확정 순서: 바닥 찾기 → 순응 → 나선 → 힘제어 → 벽면 → 힘제어만 OFF → 중심 복귀."""
    r = wipe.wipe_bowl()
    assert r.ok and r.code == OK
    names = [c[0] for c in cell.calls]
    assert (names.index('contact_down') < names.index('compliance_on') < names.index('spiral')
            < names.index('force_on') < names.index('arc') < names.index('force_release'))
    assert names[0] == 'move_to' and cell.calls[0][1] == 'HOME'            # 초기자세에서 시작
    assert _ended_home(cell)                                               # 어떤 경우에도 끄고 곧게 올려 HOME


def test_spiral_runs_without_force_control(cell):
    """🚨 나선은 툴 Z 축 모션이라 Z 힘제어와 같은 축 — 켜 두면 시작조차 하지 않는다(중급2 · 9/20 실기)."""
    wipe.wipe_bowl()
    names = [c[0] for c in cell.calls]
    assert names.index('spiral') < names.index('force_on')


def test_force_target_compensates_air_baseline(cell):
    """공중 기준값(센서 치우침·툴 무게)을 더해서 명령한다."""
    wipe.wipe_bowl()
    axis, target, limit = [c[1:] for c in cell.calls if c[0] == 'force_on'][0]
    assert axis == 'z' and target == pytest.approx(1.5 + 2.0) and limit == 10.0


def test_fast_approach_then_find_bottom(cell):
    """초기자세 HOME 에서 fast_down_mm(135, 9/21 실측) 만큼 빠르게, 나머지는 힘으로 — 바닥 위치를 미리 정하지 않는다."""
    wipe.wipe_bowl()
    fast = [c for c in cell.calls if c[0] == 'move_rel' and c[1] < 0][0]
    assert fast[1] == pytest.approx(-135.0)                                # 티칭 끝점(up)과 무관
    assert ('contact_down', 40.0, 2.0) in cell.calls                       # find_max_mm · cell.limits.contact_limit_n


def test_bottom_not_found_stops_before_compliance(cell):
    """바닥을 못 찾으면 순응·힘제어를 켜지 않고 중단한다."""
    cell.find = 40.0                                                       # find_max_mm 까지 내려가도 못 찾음
    r = wipe.wipe_bowl()
    assert not r.ok and r.code == ROBOT_ERROR
    assert 'compliance_on' not in [c[0] for c in cell.calls]
    assert _ended_home(cell)


def test_actual_z_is_logged(cell):
    """바닥 Z·접촉 힘·공중 기준값을 로그로 남긴다(실기에서 티칭값과 비교하려고)."""
    wipe.wipe_bowl()
    assert any('바닥' in m for lvl, m in cell.logger.lines if lvl == 'info')


def test_spiral_uses_time_and_wall_radius(cell):
    wipe.wipe_bowl()
    rev, rmax, t = [c[1:] for c in cell.calls if c[0] == 'spiral'][0]
    assert rmax == pytest.approx(WALL_R) and t == 3.0                      # 시간으로 지정(중급1 p.69)
    assert rev == pytest.approx(round(WALL_R / 5.0, 1))                    # 간격 5 mm → 약 2.8바퀴


def test_wall_laps_reverse_and_twist(cell):
    wipe.wipe_bowl()
    arcs = [c for c in cell.calls if c[0] == 'arc']
    assert len(arcs) == 12                                                 # 3바퀴 × 90° 원호 4개
    assert arcs[-1][1] == 0.0 and arcs[0][1] > 0                           # 마지막만 이어 붙이지 않는다
    lap = _wiped(cell)[-13:-1]                                             # 마지막 하나는 중심 복귀
    rr = _radii(lap, _center(cell))
    assert max(rr) - min(rr) < 0.01                                        # 반지름 고정 (벽을 찾지 않는다)
    assert max(rr) == pytest.approx(WALL_R)
    twists = sorted({round(p[5] - POSE0[5], 1) for p in lap})
    assert twists == [-18.0, 0.0, 18.0]                                    # 좌우로만 비틀고, 마지막은 제자리
    assert _arc_dir(cell) < 0                                              # 나선(반시계)과 반대 = 시계


def _arc_dir(cell):
    """벽면 원호가 도는 방향 부호 (BASE 기준, + 반시계)."""
    lap = _wiped(cell)[-13:-1]
    ang = [math.atan2(p[1] - _center(cell)[1], p[0] - _center(cell)[0]) for p in lap]
    step = [math.atan2(math.sin(b - a), math.cos(b - a)) for a, b in zip(ang, ang[1:])]
    assert all(t * step[0] > 0 for t in step), '한 바퀴 안에서 방향이 바뀐다'
    return step[0]


@pytest.mark.parametrize('spiral_dir', [+1, -1])
def test_wall_turns_opposite_to_measured_spiral(cell, spiral_dir):
    """🚨 나선 방향을 **재서** 그 반대로 돈다 — 나선은 TOOL · 원호는 BASE 기준이라 부호를 가정하면 같은 방향이 된다(9/21 실측).

    두산 API 에는 나선 방향 인자가 없고(rev > 0) 강의자료에도 설명이 없다 → 어느 쪽으로 돌든 반대가 나와야 한다.
    """
    cell.spiral_dir = spiral_dir
    r = wipe.wipe_bowl()
    assert r.ok
    assert _arc_dir(cell) * spiral_dir < 0


def test_ends_at_center_same_height(cell):
    """올리지 않고 그 높이에서 중심으로 — 들어 올리는 것은 HOME 복귀 몫."""
    wipe.wipe_bowl()
    last = _wiped(cell)[-1]
    assert _radii([last], _center(cell))[0] < 0.01
    assert last[2] == pytest.approx(_center(cell)[2])


def test_spiral_that_does_not_move_is_error(cell):
    """명령은 받았는데 돌지 않으면(9/20 실기 증상) 조용히 넘어가지 않는다."""
    cell.spiral_moves = False
    r = wipe.wipe_bowl()
    assert not r.ok and r.code == ROBOT_ERROR
    assert 'arc' not in [c[0] for c in cell.calls]                         # 벽면으로 넘어가지 않는다


def test_lateral_over_limit_is_force_limit(cell):
    cell.lateral = 99.0
    r = wipe.wipe_bowl()
    assert not r.ok and r.code == FORCE_LIMIT
    assert _ended_home(cell)


def test_press_over_limit_is_force_limit(cell):
    """닦는 중 누르는 힘이 상한을 넘으면 즉시 후퇴한다(NFR-01)."""
    cell.press = 99.0
    r = wipe.wipe_bowl()
    assert not r.ok and r.code == FORCE_LIMIT
    assert _ended_home(cell)


def test_over_time_is_timeout(cell):
    CFG['f3']['wipe_bowl']['duration_s'] = -1                              # 이미 넘은 것으로
    try:
        r = wipe.wipe_bowl()
    finally:
        CFG['f3']['wipe_bowl']['duration_s'] = 120
    assert not r.ok and r.code == TIMEOUT


def test_halt_between_steps_is_raised(cell):
    """강제정지는 코드로 바꾸지 않고 올린다 — flow 의 중단 흐름이 받는다(결정 E11).

    🚨 그리고 **로봇을 자동으로 움직이지 않는다** — 어디 있는지 모르기 때문이다.
       힘·순응 해제는 모션이 아니라서 한다.
    """
    cell.halted = True
    with pytest.raises(wipe.cc.MotionHalted):
        wipe.wipe_bowl()
    assert [c[0] for c in cell.calls][-1] == 'force_off'                   # 끄기만 하고 움직이지 않는다


def test_move_incomplete_does_not_auto_move(cell, monkeypatch):
    """🚨 이동이 도중에 섰으면(MoveIncomplete) 로봇 위치를 모른다 → 힘만 끄고 그 자리에 둔다.

    9/21 08:40 실기: 6번 관절이 163° 돌아 케이블이 꼬인 채 멈췄는데 도구가 자동으로 HOME 으로 가려 했다.
    """
    def stop_midway(*a, **kw):
        raise wipe.cc.MoveIncomplete('목표까지 122 mm 남았다')

    monkeypatch.setattr(wipe.cc, 'move_to', stop_midway)
    with pytest.raises(wipe.cc.MoveIncomplete):
        wipe.wipe_bowl()
    assert [c[0] for c in cell.calls] == ['force_off']                     # 끄기만 하고 움직이지 않는다


def test_force_limit_still_retreats(cell):
    """힘 상한은 로봇이 정상이라는 뜻 — 설계대로 후퇴한다(AGENTS 규칙 2)."""
    cell.press = 99.0
    r = wipe.wipe_bowl()
    assert r.code == FORCE_LIMIT
    assert _ended_home(cell)


def test_force_log_saved(cell):
    r = wipe.wipe_bowl()
    assert r.force_log_path.endswith('.csv')
    with open(r.force_log_path) as f:
        head = f.readline().strip().split(',')
    assert head == list(wipe.FORCE_LOG_HEADER)
    assert r.force_mean_n > 0                                              # 누르는 힘 평균 (마감 기준 TC-06)


def test_returns_straight_up_to_home_height(cell):
    """닦은 뒤 수세미를 곧게 올려 HOME 높이로 → HOME(관절). 옆으로 먼저 움직이지 않는다."""
    wipe.wipe_bowl()
    rise = cell.poses[cell.off]
    assert rise[:2] == pytest.approx(_center(cell)[:2]) and rise[2] == pytest.approx(POSE0[2])
