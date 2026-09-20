# -*- coding: utf-8 -*-
"""soap · wipe_cup(F3-03) 시험 — 로봇 없이 가짜 공용 함수로 순서·판정·실패 처리를 본다.

    python3 -m pytest -q src/f3_wipe/test/test_f3_soap_cup.py

soap 은 접촉 동작이 아니다(수조가 비어 있다) → 순응·힘제어·힘 감시가 없어야 한다.
wipe_cup 은 **삽입만** 힘으로 찾고(contact_down), 문지르기는 순응을 끈 위치 제어다(관절 이동, 2.1903).
실제 깊이·회전각은 V-10(실기)에서 확정한다 — 여기서는 순서·상한 처리만 본다.
"""
import pytest

from cobot_api import FORCE_LIMIT, OK, ROBOT_ERROR, TIMEOUT
from f3_wipe import wipe

CFG = {
    'run': {'vel_scale': 0.3},
    'cell': {'limits': {'insert_limit_n': 5.0, 'timeout_s': 30.0}},
    'f3': {
        'soap': {'depth_mm': 40.0, 'hold_s': 0.0, 'vel_mm_s': 80.0, 'log_dir': 'logs/f3'},
        'wipe_cup': {
            'tool': {'clean_h_mm': 95, 'd_mm': 55},
            'insert_depth_mm': 90.0, 'insert_min_mm': 40.0,
            'rot_deg': 180.0, 'rot_time_s': 1.0, 'cycles': 4,
            'stroke_mm': 30.0, 'stroke_vel_mm_s': 60.0,
            'limit_n': 10.0, 'lateral_max_n': 25.0, 'duration_s': 120, 'log_dir': 'logs/f3',
        },
    },
}
POSE0 = [400.0, 100.0, 235.0, 45.0, 180.0, 45.0]


class _Logger:
    def __init__(self):
        self.lines = []

    def info(self, m):
        self.lines.append(('info', m))

    def error(self, m):
        self.lines.append(('error', m))


class FakeCell:
    """가짜 셀 — 공용 함수 호출을 순서대로 적어 둔다."""

    def __init__(self, up=0.0, depth=85.0, press=2.0, lateral=1.0):
        self.calls = []
        self.up, self.depth = up, depth
        self.press, self.lateral = press, lateral
        self.pose = list(POSE0)
        self.inserted = False
        self.halted = False
        self.logger = _Logger()

    def cfg(self):
        return CFG

    def move_to(self, station, carrying, kind=None, point=None):
        self.calls.append(('move_to', station, kind, point))
        self.pose = list(POSE0)
        return self.up

    def move_rel(self, dx, dy, dz, frame, **kw):
        self.calls.append(('move_rel', round(dz, 1), round(kw.get('vel_mm_s') or 0.0, 1)))
        self.pose = [self.pose[0] + dx, self.pose[1] + dy, self.pose[2] + dz] + self.pose[3:]

    def move_joint_rel(self, joint, delta_deg, *, time_s=None, carrying=True):
        self.calls.append(('joint', joint, delta_deg, time_s))

    def contact_down(self, max_depth, limit):
        self.calls.append(('contact_down', max_depth, limit))
        self.inserted = True
        self.pose[2] -= self.depth
        return self.depth, limit

    def read_force(self):
        if not self.inserted:
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

    def where(self):
        return list(self.pose)


@pytest.fixture
def cell(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    c = FakeCell()
    for name in ('cfg', 'move_to', 'move_rel', 'move_joint_rel', 'contact_down', 'read_force',
                 'force_off', 'safe_retreat', 'io_node', 'is_halted', 'where'):
        monkeypatch.setattr(wipe.cc, name, getattr(c, name), raising=False)
    return c


# ------------------------------------------------------------------ soap
def test_soap_dips_count_times(cell):
    r = wipe.soap(3, 'BOWL')
    assert r.ok and r.code == OK
    downs = [c for c in cell.calls if c[0] == 'move_rel' and c[1] < 0]
    ups = [c for c in cell.calls if c[0] == 'move_rel' and c[1] > 0]
    assert len(downs) == len(ups) == 3                                     # 넣은 만큼 뺀다
    assert downs[0][1] == pytest.approx(-40.0) and ups[0][1] == pytest.approx(40.0)
    assert downs[0][2] == pytest.approx(80.0 * 0.3)                        # 담금 속도 × vel_scale


def test_soap_passes_kind_to_move_to(cell):
    """SOAP 은 종류별 자리다 — kind 를 그대로 넘긴다(결정 E8)."""
    wipe.soap(1, 'CUP')
    assert ('move_to', 'SOAP', 'CUP', None) in cell.calls


def test_soap_is_not_a_contact_motion(cell):
    """수조가 비어 있다 → 순응·힘제어·힘 감시가 없어야 한다(AGENTS 규칙 3)."""
    wipe.soap(2)
    names = [c[0] for c in cell.calls]
    assert 'contact_down' not in names and 'force_on' not in names and 'compliance_on' not in names
    assert names[-2:] == ['force_off', 'safe_retreat']                     # 정리는 그대로 한다


def test_soap_zero_count_is_ok(cell):
    r = wipe.soap(0)
    assert r.ok and not [c for c in cell.calls if c[0] == 'move_rel']


def test_soap_negative_count_is_error(cell):
    assert wipe.soap(-1).code == ROBOT_ERROR


def test_soap_timeout(cell):
    CFG['cell']['limits']['timeout_s'] = -1
    try:
        r = wipe.soap(3)
    finally:
        CFG['cell']['limits']['timeout_s'] = 30.0
    assert not r.ok and r.code == TIMEOUT


def test_soap_halt_is_raised(cell):
    cell.halted = True
    with pytest.raises(wipe.cc.MotionHalted):
        wipe.soap(3)


# ------------------------------------------------------------------ wipe_cup
def test_cup_inserts_by_force_then_scrubs_by_position(cell):
    """삽입은 힘으로(contact_down), 문지르기는 관절 이동 — 순응 중에는 관절 이동이 안 된다(2.1903)."""
    r = wipe.wipe_cup()
    assert r.ok and r.code == OK and r.insert_depth_mm == pytest.approx(85.0)
    names = [c[0] for c in cell.calls]
    assert names.index('contact_down') < names.index('joint')
    assert ('contact_down', 90.0, 5.0) in cell.calls                       # 최대 깊이 · insert_limit_n
    assert names[-2:] == ['force_off', 'safe_retreat']


def test_cup_scrub_cycles_rotate_both_ways_and_stroke(cell):
    wipe.wipe_cup()
    joints = [c for c in cell.calls if c[0] == 'joint']
    assert len(joints) == 8                                                # 4 회 × (정방향 + 역방향)
    assert all(j[1] == 6 for j in joints)                                  # J6 만 돌린다
    assert [j[2] for j in joints[:2]] == [180.0, -180.0]                   # 돌린 만큼 되돌린다
    assert sum(j[2] for j in joints) == pytest.approx(0.0)                 # 손목이 풀린 채 끝나지 않는다
    strokes = [c for c in cell.calls if c[0] == 'move_rel']
    assert len(strokes) == 8 and sum(s[1] for s in strokes) == pytest.approx(0.0)
    assert strokes[0][1] == pytest.approx(30.0)                            # 삽입 85 mm 라 30 mm 그대로


def test_cup_stroke_shrinks_when_shallow(cell):
    """얕게 들어갔으면 솔이 빠지지 않게 스트로크를 줄인다 (설정이 서로 안 맞을 때의 안전장치)."""
    CFG['f3']['wipe_cup']['insert_min_mm'] = 10.0                          # 기본값(40)에서는 걸릴 일이 없다
    cell.depth = 25.0
    try:
        wipe.wipe_cup()
    finally:
        CFG['f3']['wipe_cup']['insert_min_mm'] = 40.0
    strokes = [c for c in cell.calls if c[0] == 'move_rel' and c[1] > 0]
    assert strokes[0][1] == pytest.approx(20.0)                            # 25 − 여유 5 (30 이 아니라)


def test_cup_blocked_too_shallow_is_force_limit(cell):
    cell.depth = 20.0                                                      # insert_min_mm 40 보다 얕다
    r = wipe.wipe_cup()
    assert not r.ok and r.code == FORCE_LIMIT
    assert 'joint' not in [c[0] for c in cell.calls]                       # 문지르지 않는다
    assert r.insert_depth_mm == pytest.approx(20.0)                        # 어디서 막혔는지는 돌려준다


def test_cup_press_over_limit_is_force_limit(cell):
    cell.press = 99.0
    r = wipe.wipe_cup()
    assert not r.ok and r.code == FORCE_LIMIT


def test_cup_lateral_over_limit_is_force_limit(cell):
    cell.lateral = 99.0
    r = wipe.wipe_cup()
    assert not r.ok and r.code == FORCE_LIMIT


def test_cup_over_time_is_timeout(cell):
    CFG['f3']['wipe_cup']['duration_s'] = -1
    try:
        r = wipe.wipe_cup()
    finally:
        CFG['f3']['wipe_cup']['duration_s'] = 120
    assert not r.ok and r.code == TIMEOUT


def test_cup_logs_depth_and_saves_force_log(cell):
    r = wipe.wipe_cup()
    assert any('삽입 깊이' in m for lvl, m in cell.logger.lines if lvl == 'info')
    assert r.force_log_path.endswith('.csv')
