# -*- coding: utf-8 -*-
"""wipe_bowl(F3-02) 시험 — 로봇 없이 가짜 공용 함수로 순서·판정·실패 처리를 본다.

    python3 -m pytest -q src/f3_wipe/test/test_f3_wipe_bowl.py

**고정 좌표 방식**(결정 E6 · SDD §5.4)을 본다: 바닥·벽을 찾지 않고(contact_down·force_on 없음),
티칭한 닦는 높이까지 내려가 나선 → 벽면 원호. 힘은 유지하지 않고 **상한만** 본다.
실제 힘 값·닦는 높이는 실기에서 본다 — 여기서는 "순서·반지름·비틀기·상한 처리"만 본다.
"""
import math

import pytest

from cobot_api import FORCE_LIMIT, OK, ROBOT_ERROR, TIMEOUT
from f3_wipe import wipe

WALL_R = (110.0 - 90.0) / 2 + 4.0       # 벽 반지름 = (그릇 안지름 − 툴 지름)/2 + 벽 누름 = 14 mm
UP = 188.0                              # 접근점(z 235) → 닦는 높이(z 47) 까지 남은 높이
CFG = {
    'run': {'vel_scale': 0.3},
    'cell': {'limits': {'safe_z_mm': 235.0}},
    'f3': {'wipe_bowl': {
        'tool': {'clean_h_mm': 35, 'd_mm': 90},
        'slow_mm': 15.0, 'slow_step_mm': 3.0, 'slow_vel_mm_s': 20.0,
        'limit_n': 10.0, 'lateral_max_n': 25.0,
        'bowl_inner_d_mm': 110.0, 'wall_press_mm': 4.0,
        'spiral_pitch_mm': 5.0, 'spiral_time_s': 3.0,
        'turns': 3, 'wall_arc_deg': 90.0, 'wall_approach_vel_mm_s': 60.0,
        'twist_deg': 18.0, 'blend_radius_mm': 3.0, 'lin_vel_mm_s': 180.0, 'rot_vel_deg_s': 400.0,
        'force_every': 4, 'sample_s': 0.0, 'duration_s': 120, 'log_dir': 'logs/f3',
    }},
}
POSE0 = [400.0, 0.0, 235.0, 45.0, 180.0, 45.0]      # 접근점 (닦는 자리 상공)


class _Logger:
    def __init__(self):
        self.lines = []

    def info(self, m):
        self.lines.append(('info', m))

    def error(self, m):
        self.lines.append(('error', m))


class FakeCell:
    """가짜 셀 — 공용 함수 호출을 적어 두고, 그릇 안의 힘을 흉내 낸다."""

    def __init__(self, press=1.5, lateral=1.0, spiral_moves=True, up=UP):
        self.calls = []
        self.press, self.lateral, self.up = press, lateral, up
        self.spiral_moves = spiral_moves                 # False = 명령은 받지만 돌지 않는다(9/20 실기 증상)
        self.pose = list(POSE0)
        self.poses = []
        self.moving = False
        self.touched = False                             # 닦는 높이까지 내려온 뒤부터 힘이 걸린 것으로 본다
        self.halted = False
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
        if self.pose[2] <= POSE0[2] - self.up + 1e-6:
            self.touched = True

    def read_force(self):
        """공중 치우침 2 N. 닦는 높이에 닿은 뒤부터 누르는 힘·옆 힘이 걸린 것으로 본다."""
        if not self.touched:
            return [0.0, 0.0, 2.0, 0.0, 0.0, 0.0]
        return [self.lateral, 0.0, 2.0 + self.press, 0.0, 0.0, 0.0]

    def force_off(self):
        self.calls.append(('force_off',))

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
        was, self.moving = self.moving, False
        return not was

    def move_spiral(self, rev, rmax_mm, time_s):
        self.calls.append(('spiral', rev, rmax_mm, time_s))
        self.moving = True
        if self.spiral_moves:                            # 나선 끝: 중심에서 rmax 만큼 나간 자리
            self.pose[0] += rmax_mm
            self.poses.append(list(self.pose))

    def move_arc(self, mid, end, vel_mm_s, vel_deg_s, radius_mm):
        self.calls.append(('arc', round(radius_mm, 1)))
        self.pose = list(end)
        self.poses.append(list(end))


@pytest.fixture
def cell(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)                      # 힘 로그는 실행 위치 기준 상대경로
    c = FakeCell()
    for name in ('cfg', 'move_to', 'move_rel', 'read_force', 'force_off', 'safe_retreat',
                 'io_node', 'is_halted', 'where', 'motion_done', 'move_spiral', 'move_arc'):
        monkeypatch.setattr(wipe.cc, name, getattr(c, name), raising=False)
    return c


def _center(c):
    """닦는 높이에 닿은 자리 = 나선의 중심."""
    return [POSE0[0], POSE0[1], POSE0[2] - c.up]


def _radii(poses, center):
    return [math.hypot(p[0] - center[0], p[1] - center[1]) for p in poses]


def test_does_not_search_bottom_or_hold_force(cell):
    """고정 좌표 방식(E6): 바닥 찾기·목표 힘 유지를 쓰지 않는다."""
    r = wipe.wipe_bowl()
    assert r.ok and r.code == OK
    names = [c[0] for c in cell.calls]
    assert 'contact_down' not in names and 'force_on' not in names and 'compliance_on' not in names
    assert names[-2:] == ['force_off', 'safe_retreat']                     # 어떤 경우에도 끄고 안전 높이


def test_descends_fast_then_slow_with_force_watch(cell):
    """앞은 한 번에, 마지막 slow_mm 만 slow_step_mm 씩 천천히 (SDD §5.4)."""
    wipe.wipe_bowl()
    downs = [c for c in cell.calls if c[0] == 'move_rel' and c[1] < 0]
    assert downs[0][1] == pytest.approx(-(UP - 15.0)) and downs[0][2] == 0.0      # 빠른 구간은 속도를 주지 않는다
    slow = downs[1:6]
    assert [d[1] for d in slow] == [pytest.approx(-3.0)] * 5                      # 15 mm 를 3 mm 씩
    assert slow[0][2] == pytest.approx(20.0 * 0.3)                                # 느린 속도 × vel_scale
    assert sum(d[1] for d in downs) == pytest.approx(-UP)                         # 티칭한 높이까지 정확히


def test_actual_z_is_logged(cell):
    """순응을 끄고 내려가므로 명령한 Z = 실제 Z — 실기에서 확인하라고 로그에 남긴다(PM 요청)."""
    wipe.wipe_bowl()
    assert any('닦는 높이' in m for lvl, m in cell.logger.lines if lvl == 'info')


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
    lap = cell.poses[-13:-1]                                               # 마지막 하나는 중심 복귀
    rr = _radii(lap, _center(cell))
    assert max(rr) - min(rr) < 0.01                                        # 반지름 고정 (벽을 찾지 않는다)
    assert max(rr) == pytest.approx(WALL_R)
    twists = sorted({round(p[5] - POSE0[5], 1) for p in lap})
    assert twists == [-18.0, 0.0, 18.0]                                    # 좌우로만 비틀고, 마지막은 제자리
    ang = [math.atan2(p[1] - _center(cell)[1], p[0] - _center(cell)[0]) for p in lap]
    step = [math.atan2(math.sin(b - a), math.cos(b - a)) for a, b in zip(ang, ang[1:])]
    assert all(t < 0 for t in step)                                        # 나선과 반대 방향(시계)


def test_ends_at_center_same_height(cell):
    """올리지 않고 그 높이에서 중심으로 — 들어 올리는 것은 safe_retreat 몫."""
    wipe.wipe_bowl()
    last = cell.poses[-1]
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
    assert [c[0] for c in cell.calls][-2:] == ['force_off', 'safe_retreat']


def test_press_over_limit_stops_while_descending(cell):
    """느린 구간에서 세게 눌리면(그릇·툴 높이가 다르다) 나선으로 넘어가지 않는다."""
    cell.press = 99.0
    r = wipe.wipe_bowl()
    assert not r.ok and r.code == FORCE_LIMIT
    assert 'spiral' not in [c[0] for c in cell.calls]


def test_over_time_is_timeout(cell):
    CFG['f3']['wipe_bowl']['duration_s'] = -1                              # 이미 넘은 것으로
    try:
        r = wipe.wipe_bowl()
    finally:
        CFG['f3']['wipe_bowl']['duration_s'] = 120
    assert not r.ok and r.code == TIMEOUT


def test_halt_between_steps_is_raised(cell):
    """강제정지는 코드로 바꾸지 않고 올린다 — flow 의 중단 흐름이 받는다(결정 E11)."""
    cell.halted = True
    with pytest.raises(wipe.cc.MotionHalted):
        wipe.wipe_bowl()
    assert [c[0] for c in cell.calls][-2:] == ['force_off', 'safe_retreat']


def test_force_log_saved(cell):
    r = wipe.wipe_bowl()
    assert r.force_log_path.endswith('.csv')
    with open(r.force_log_path) as f:
        head = f.readline().strip().split(',')
    assert head == list(wipe.FORCE_LOG_HEADER)
    assert r.force_mean_n > 0                                              # 누르는 힘 평균 (마감 기준 TC-06)
