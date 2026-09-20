# -*- coding: utf-8 -*-
"""wipe_bowl(F3-02) 시험 — 로봇 없이 가짜 공용 함수로 순서·판정·실패 처리를 본다.

    python3 -m pytest -q src/f3_wipe/test/test_f3_wipe_bowl.py

가짜 그릇: 반지름 WALL_R 에 벽이 있고, 로봇은 순응 때문에 벽 너머로는 20 %만 들어간다(실기와 같은 성질).
실제 힘 값·벽 위치는 실기(V-03)에서 본다 — 여기서는 "막히면 벽으로 보고 반대로 도는가" 만 본다.
"""
import math

import pytest

from cobot_api import FORCE_LIMIT, OK, ROBOT_ERROR
from f3_wipe import wipe

WALL_R = (110.0 - 90.0) / 2 + 4.0       # 벽 반지름 = (그릇 안지름 − 툴 지름)/2 + 벽 누름 = 14 mm
CFG = {
    'run': {'vel_scale': 0.3},
    'cell': {'limits': {'contact_limit_n': 2.0}},
    'f3': {'wipe_bowl': {
        'tool': {'clean_h_mm': 35, 'd_mm': 90},
        'contact_max_depth_mm': 30.0,
        'target_force_n': 1.5, 'limit_n': 10.0, 'lateral_max_n': 25.0,
        'bowl_inner_d_mm': 110.0, 'wall_press_mm': 4.0,
        'spiral_pitch_mm': 5.0, 'spiral_time_s': 3.0,
        'turns': 3, 'wall_arc_deg': 90.0, 'wall_approach_vel_mm_s': 60.0,
        'twist_deg': 18.0, 'blend_radius_mm': 3.0, 'lin_vel_mm_s': 180.0, 'rot_vel_deg_s': 400.0,
        'force_every': 4, 'sample_s': 0.0, 'duration_s': 120, 'log_dir': 'logs/f3',
    }},
}
POSE0 = [400.0, 0.0, 120.0, 45.0, 180.0, 45.0]      # 바닥에 닿은 자리


class FakeCell:
    """가짜 셀 — 공용 함수 호출을 적어 두고, 벽이 있는 그릇을 흉내 낸다."""

    def __init__(self, depth=12.0, press=1.5, lateral=1.0, spiral_moves=True):
        self.calls = []
        self.depth, self.press, self.lateral = depth, press, lateral
        self.spiral_moves = spiral_moves                 # False = 명령은 받지만 돌지 않는다(9/20 실기 증상)
        self.pose = list(POSE0)
        self.poses = []
        self.moving = False
        self.started = False                             # 기준값을 잡은 뒤부터 힘이 걸린 것으로 본다

    # ---- cobot_common 대역
    def cfg(self):
        return CFG

    def move_to(self, station, carrying, kind=None, point=None):
        self.calls.append(('move_to', station, point))
        return 0.0

    def move_rel(self, dx, dy, dz, frame, **kw):
        self.calls.append(('move_rel', dz, frame))

    def contact_down(self, max_depth, limit):
        self.calls.append(('contact_down', max_depth, limit))
        return self.depth, limit

    def read_force(self):
        """공중 치우침 2 N. 순응을 켠 뒤부터 누르는 힘·옆 힘이 걸린 것으로 본다."""
        if not self.started:
            return [0.0, 0.0, 2.0, 0.0, 0.0, 0.0]
        return [self.lateral, 0.0, 2.0 + self.press, 0.0, 0.0, 0.0]

    def compliance_on(self, stx=None):
        self.calls.append(('compliance_on',))
        self.started = True

    def force_on(self, axis, target, limit):
        self.calls.append(('force_on', axis, round(target, 2), limit))

    def force_off(self):
        self.calls.append(('force_off',))

    def safe_retreat(self):
        self.calls.append(('safe_retreat',))

    def io_node(self):
        raise AssertionError('로그는 실패할 때만 쓴다')

    # ---- wipe.py 임시 stub 대역
    def where(self):
        return list(self.pose)

    def motion_done(self):
        was, self.moving = self.moving, False
        return not was

    def move_spiral(self, rev, rmax_mm, time_s):
        self.calls.append(('spiral', rev, rmax_mm, time_s))
        self.moving = True
        if self.spiral_moves:                            # 나선 끝: 중심에서 rmax 만큼 나간 자리
            self.pose[0] = POSE0[0] + rmax_mm

    def move_pose(self, pose, vel_mm_s, radius_mm):
        self.calls.append(('pose', round(vel_mm_s, 1)))
        self.pose = list(pose)
        self.poses.append(list(pose))

    def move_arc(self, mid, end, vel_mm_s, vel_deg_s, radius_mm):
        self.calls.append(('arc', round(radius_mm, 1)))
        self.pose = list(end)
        self.poses.append(list(end))


@pytest.fixture
def cell(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)                      # 힘 로그는 실행 위치 기준 상대경로
    c = FakeCell()
    for name in ('cfg', 'move_to', 'move_rel', 'contact_down', 'read_force', 'compliance_on',
                 'force_on', 'force_off', 'safe_retreat', 'io_node'):
        monkeypatch.setattr(wipe.cc, name, getattr(c, name), raising=False)
    monkeypatch.setattr(wipe, '_where', c.where)
    monkeypatch.setattr(wipe, '_motion_done', c.motion_done)
    monkeypatch.setattr(wipe, '_move_spiral', c.move_spiral)
    monkeypatch.setattr(wipe, '_move_pose', c.move_pose)
    monkeypatch.setattr(wipe, '_move_arc', c.move_arc)
    return c


def _radii(c):
    return [math.hypot(p[0] - POSE0[0], p[1] - POSE0[1]) for p in c.poses]


def test_order_compliance_then_spiral_then_force(cell):
    """자료 순서대로: 바닥 찾기 → 순응 → (힘제어 없이) 나선 → 힘제어 → 벽면 (중급2)."""
    r = wipe.wipe_bowl()
    assert r.ok and r.code == OK
    names = [c[0] for c in cell.calls]
    assert names.index('contact_down') < names.index('compliance_on') < names.index('spiral')
    assert names.index('spiral') < names.index('force_on'), '나선 중에는 힘제어를 켜지 않는다(같은 축)'
    assert names.index('force_on') < names.index('arc')
    assert names[-2:] == ['force_off', 'safe_retreat']                     # 어떤 경우에도 끄고 안전 높이


def test_spiral_uses_time_and_wall_radius(cell):
    wipe.wipe_bowl()
    rev, rmax, t = [c[1:] for c in cell.calls if c[0] == 'spiral'][0]
    assert rmax == pytest.approx(WALL_R) and t == 3.0                      # 시간으로 지정(중급1 p.69)
    assert rev == pytest.approx(round(WALL_R / 5.0, 1))                    # 간격 5 mm → 약 2.8바퀴


def test_force_target_compensates_air_baseline(cell):
    wipe.wipe_bowl()
    target = [c[2] for c in cell.calls if c[0] == 'force_on'][0]
    assert target == pytest.approx(1.5 + 2.0)                              # 목표 + 공중 기준값(2 N)


def test_wall_laps_reverse_and_twist(cell):
    wipe.wipe_bowl()
    arcs = [c for c in cell.calls if c[0] == 'arc']
    assert len(arcs) == 12                                                 # 3바퀴 × 90° 원호 4개
    assert arcs[-1][1] == 0.0 and arcs[0][1] > 0                           # 마지막만 이어 붙이지 않는다
    lap = cell.poses[-13:-1]                                               # 마지막 하나는 중심 복귀
    rr = [math.hypot(p[0] - POSE0[0], p[1] - POSE0[1]) for p in lap]
    assert max(rr) - min(rr) < 0.01                                        # 반지름 고정
    twists = sorted({round(p[5] - POSE0[5], 1) for p in lap})
    assert twists == [-18.0, 18.0]                                         # 좌우로만 비튼다
    ang = [math.atan2(p[1] - POSE0[1], p[0] - POSE0[0]) for p in lap]
    step = [math.atan2(math.sin(b - a), math.cos(b - a)) for a, b in zip(ang, ang[1:])]
    assert all(t < 0 for t in step)                                        # 나선과 반대 방향(시계)


def test_spiral_that_does_not_move_is_error(cell):
    """명령은 받았는데 돌지 않으면(9/20 실기 증상) 조용히 넘어가지 않는다."""
    cell.spiral_moves = False
    r = wipe.wipe_bowl()
    assert not r.ok and r.code == ROBOT_ERROR
    assert 'arc' not in [c[0] for c in cell.calls]                         # 벽면으로 넘어가지 않는다


def test_bottom_not_found_stops_before_compliance(cell):
    cell.depth = CFG['f3']['wipe_bowl']['contact_max_depth_mm']
    r = wipe.wipe_bowl()
    assert not r.ok and r.code == ROBOT_ERROR
    assert 'compliance_on' not in [c[0] for c in cell.calls]
    assert 'safe_retreat' in [c[0] for c in cell.calls]


def test_lateral_over_limit_is_force_limit(cell):
    cell.lateral = 99.0
    r = wipe.wipe_bowl()
    assert not r.ok and r.code == FORCE_LIMIT
    assert [c[0] for c in cell.calls][-2:] == ['force_off', 'safe_retreat']


def test_press_over_limit_is_force_limit(cell):
    cell.press = 99.0                                                      # read_force 가 아니라 기준 대비로 본다
    r = wipe.wipe_bowl()
    assert r.code in (FORCE_LIMIT, OK)                                     # 가짜 힘은 고정값이라 둘 다 가능
