# -*- coding: utf-8 -*-
"""wipe_bowl(F3-02) 시험 — 로봇 없이 가짜 공용 함수로 순서·판정·실패 처리를 본다.

    python3 -m pytest -q src/f3_wipe/test/test_f3_wipe_bowl.py

가짜 그릇: 반지름 WALL_R 에 벽이 있고, 로봇은 순응 때문에 벽 너머로는 20 %만 들어간다(실기와 같은 성질).
실제 힘 값·벽 위치는 실기(V-03)에서 본다 — 여기서는 "막히면 벽으로 보고 반대로 도는가" 만 본다.
"""
import math

import pytest

from cobot_api import FORCE_LIMIT, OK, ROBOT_ERROR, TIMEOUT
from f3_wipe import wipe

WALL_R = 27.5                       # 그릇 벽 (툴 중심 기준) — 그릇 안지름 110, 툴 Ø55 일 때
CFG = {
    'run': {'vel_scale': 0.3},
    'cell': {'limits': {'contact_limit_n': 3.0}},
    'f3': {'wipe_bowl': {
        'tool': {'clean_h_mm': 45, 'd_mm': 90},
        'target_force_n': 4.0, 'limit_n': 10.0, 'lateral_max_n': 15.0,
        'contact_max_depth_mm': 30.0,
        'step_mm': 15.0, 'pitch_mm': 15.0, 'twist_deg': 18.0, 'twist_every': 2,
        'blend_radius_mm': 4.0, 'lin_vel_mm_s': 450.0, 'lin_acc_mm_s2': 1200.0,
        'rot_vel_deg_s': 740.0, 'rot_acc_deg_s2': 1500.0,
        'bowl_r_max_mm': 150.0, 'r_max_margin_mm': 5.0,
        'wall_gap_mm': 2.0, 'climb_max_mm': 8.0, 'wall_confirm': 1,
        'circle_margin_mm': 0.0,
        'turns': 2, 'duration_s': 120, 'log_dir': 'logs/f3',
    }},
}
POSE0 = [400.0, 0.0, 120.0, 45.0, 180.0, 45.0]      # 바닥에 닿은 자리


class FakeCell:
    """가짜 셀 — 공용 함수 호출을 적어 두고, 벽이 있는 그릇을 흉내 낸다."""

    def __init__(self, wall_r=WALL_R, depth=8.0, press=4.0, lateral=1.0):
        self.calls = []
        self.wall_r, self.depth = wall_r, depth
        self.press, self.lateral = press, lateral
        self.cmd = [0.0, 0.0]                        # 마지막으로 명령한 중심 기준 X·Y
        self.poses = []

    # ---- cobot_common 대역
    def cfg(self):
        return CFG

    def move_to(self, station, carrying):
        self.calls.append(('move_to', station, carrying))
        return 0.0

    def move_rel(self, dx, dy, dz, frame, **kw):
        self.calls.append(('move_rel', dz, frame))

    def contact_down(self, max_depth, limit):
        self.calls.append(('contact_down', max_depth, limit))
        return self.depth, limit

    def read_force(self):
        return [0.0, 0.0, 2.0, 0.0, 0.0, 0.0]        # 공중에서도 잡히는 치우침 2 N

    def force_on(self, axis, target, limit):
        self.calls.append(('force_on', axis, target, limit))

    def force_check(self, axis='z', baseline=None):
        return self.press, self.lateral

    def force_off(self):
        self.calls.append(('force_off',))

    def safe_retreat(self):
        self.calls.append(('safe_retreat',))

    def io_node(self):
        raise AssertionError('로그는 실패할 때만 쓴다')

    # ---- wipe.where / wipe.move_pose 대역 (motion.py 에 요청한 함수들)
    def move_pose(self, pose, frame, **kw):
        assert frame == 'BASE' and kw['radius_mm'] >= 0
        self.cmd = [pose[0] - POSE0[0], pose[1] - POSE0[1]]
        self.poses.append(list(pose))

    def where(self):
        x, y = self.cmd
        r = math.hypot(x, y)
        if r > self.wall_r > 0:                      # 벽 너머는 20 % 만 들어간다(순응)
            k = (self.wall_r + (r - self.wall_r) * 0.2) / r
            x, y = x * k, y * k
        return [POSE0[0] + x, POSE0[1] + y, POSE0[2], POSE0[3], POSE0[4], POSE0[5]]


@pytest.fixture
def cell(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)                      # 힘 로그는 실행 위치 기준 상대경로
    c = FakeCell()
    for name in ('cfg', 'move_to', 'move_rel', 'contact_down', 'read_force',
                 'force_on', 'force_check', 'force_off', 'safe_retreat', 'io_node'):
        # raising=False: force_check 는 PR #24 가 merge 되면 cobot_common 에 생긴다
        monkeypatch.setattr(wipe.cc, name, getattr(c, name), raising=False)
    monkeypatch.setattr(wipe, 'where', c.where)
    monkeypatch.setattr(wipe, 'move_pose', c.move_pose)
    return c


def _radii(c):
    return [math.hypot(p[0] - POSE0[0], p[1] - POSE0[1]) for p in c.poses]


def test_circle_radius_is_fixed(cell):
    """벽을 만난 뒤 2바퀴는 반지름을 고정해서 돈다 (9/20 결정)."""
    wipe.wipe_bowl()
    rr = _radii(cell)
    lap = rr[-20:]                                                         # 마지막 20 걸음 = 벽 따라 도는 중
    assert max(lap) - min(lap) < 0.01


def test_wall_found_and_two_laps_in_reverse(cell):
    r = wipe.wipe_bowl()
    assert r.ok and r.code == OK
    assert r.force_log_path.endswith('.csv') and not r.force_log_path.startswith('/')
    assert r.force_mean_n == pytest.approx(4.0)     # force_check 가 돌려준 누르는 힘의 평균

    names = [c[0] for c in cell.calls]
    assert names.index('contact_down') < names.index('force_on')          # 닿은 뒤에 힘을 켠다
    assert names[-2:] == ['force_off', 'safe_retreat']                    # 끝나면 끄고 안전 높이

    rr = _radii(cell)
    assert max(rr) == pytest.approx(WALL_R, abs=4.0)                      # 벽 근처에서 멈춘다(그릇 밖으로 안 나감)
    ang = [math.atan2(p[1] - POSE0[1], p[0] - POSE0[0]) for p in cell.poses]
    turn = [math.atan2(math.sin(b - a), math.cos(b - a)) for a, b in zip(ang, ang[1:])]
    assert sum(1 for t in turn if t > 0) > 5 and sum(1 for t in turn if t < 0) > 5   # 나선과 반대 방향 두 구간


def test_twist_alternates_every_two_steps(cell):
    wipe.wipe_bowl()
    c_angles = [p[5] for p in cell.poses]
    assert set(round(a - POSE0[5], 1) for a in c_angles) == {18.0, -18.0}  # ± 비틀기만, 그 사이 값 없음
    flips = sum(1 for a, b in zip(c_angles, c_angles[1:]) if a != b)
    assert flips == pytest.approx(len(c_angles) / 2, rel=0.3)              # 두 걸음에 한 번 방향 전환


def test_no_wall_is_timeout_not_endless(cell):
    cell.wall_r = 0.0                                                      # 벽이 없는 셈(막히지 않는다)
    r = wipe.wipe_bowl()
    assert not r.ok and r.code == TIMEOUT
    assert max(_radii(cell)) <= 150.0 - 45.0 + 5.0 + 1.0                   # 최대 반지름에서 멈춘다


def test_lateral_over_limit_is_force_limit(cell):
    cell.lateral = 99.0                                                    # 벽을 세게 밀었다
    r = wipe.wipe_bowl()
    assert not r.ok and r.code == FORCE_LIMIT
    assert [c[0] for c in cell.calls][-2:] == ['force_off', 'safe_retreat']


def test_bottom_not_found_stops_before_force_on(cell):
    cell.depth = CFG['f3']['wipe_bowl']['contact_max_depth_mm']            # 끝까지 내려가도 안 닿음
    r = wipe.wipe_bowl()
    assert not r.ok and r.code == ROBOT_ERROR
    assert 'force_on' not in [c[0] for c in cell.calls]                    # 힘제어를 켜지 않는다
    assert 'safe_retreat' in [c[0] for c in cell.calls]


def test_force_limit_from_common_function(cell, monkeypatch):
    def boom(axis='z', baseline=None):
        raise wipe.cc.ForceLimitError('누르는 힘 상한')
    monkeypatch.setattr(wipe.cc, 'force_check', boom, raising=False)
    r = wipe.wipe_bowl()
    assert not r.ok and r.code == FORCE_LIMIT
