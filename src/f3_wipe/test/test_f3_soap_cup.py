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
            'fast_gap_mm': 10.0, 'find_max_mm': 40.0, 'insert_min_mm': 85.0,
            'lift_mm': 2.0, 'lift_vel_mm_s': 40.0,
            'stroke_mm': 20.0, 'twist_deg': 18.0,
            'lin_vel_mm_s': 80.0, 'rot_vel_deg_s': 72.0, 'blend_radius_mm': 5.0,
            'cycles': 5, 'keep_in_mm': 10.0,
            'limit_n': 10.0, 'lateral_max_n': 25.0, 'sample_s': 0.0,
            'duration_s': 120, 'log_dir': 'logs/f3',
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

    def __init__(self, up=80.0, depth=8.0, press=2.0, lateral=1.0):
        self.calls = []
        self.up, self.depth = up, depth          # up = 접근점 → 닦는 높이 · depth = 거기서 바닥까지(찾기 구간)
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

    def move_line(self, pose, vel_mm_s, vel_deg_s, radius_mm=0.0):
        self.calls.append(('line', list(pose), radius_mm))
        self.pose = list(pose)

    def contact_down(self, max_depth, limit):
        self.calls.append(('contact_down', max_depth, limit))
        self.inserted = True
        self.pose[2] -= self.depth
        return self.depth, limit                 # 바닥을 찾은 깊이(찾기 구간 안에서)

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
    for name in ('cfg', 'move_to', 'move_rel', 'move_line', 'contact_down',
                 'read_force', 'force_off', 'safe_retreat', 'io_node', 'is_halted', 'where'):
        monkeypatch.setattr(wipe.cc, name, getattr(c, name), raising=False)
    return c


# ------------------------------------------------------------------ soap
def _dips(cell):
    """담금 이동만 (접근점에서 내려가는 이동은 속도를 주지 않아 구분된다)."""
    return [c for c in cell.calls if c[0] == 'move_rel' and c[2] > 0]


def test_soap_dips_count_times(cell):
    r = wipe.soap(3, 'BOWL')
    assert r.ok and r.code == OK
    downs = [c for c in _dips(cell) if c[1] < 0]
    ups = [c for c in _dips(cell) if c[1] > 0]
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
    assert r.ok and not _dips(cell)                                        # 담그지 않는다(자리로는 간다)


def test_soap_negative_count_is_error(cell):
    assert wipe.soap(-1).code == ROBOT_ERROR


def test_soap_timeout(cell):
    CFG['cell']['limits']['timeout_s'] = -1
    try:
        r = wipe.soap(3)
    finally:
        CFG['cell']['limits']['timeout_s'] = 30.0
    assert not r.ok and r.code == TIMEOUT


def test_soap_halt_does_not_auto_move(cell):
    cell.halted = True
    with pytest.raises(wipe.cc.MotionHalted):
        wipe.soap(3)
    assert 'safe_retreat' not in [c[0] for c in cell.calls]


# ------------------------------------------------------------------ wipe_cup
# 삽입 깊이 = 솔 길이 95 − (fast_gap 10 − 실제로 찾은 거리). 가짜는 8 mm 에서 바닥을 만나니 95 − 2 = 93 mm.
DEPTH = 95.0 - (10.0 - 8.0)


def test_cup_fast_then_finds_bottom_by_force(cell):
    """① 바닥 fast_gap 위까지 빠르게 → ② 나머지는 힘으로 찾는다(시나리오 1·2)."""
    r = wipe.wipe_cup()
    assert r.ok and r.code == OK
    names = [c[0] for c in cell.calls]
    fast = [c for c in cell.calls if c[0] == 'move_rel' and c[1] < 0][0]
    assert fast[1] == pytest.approx(-(80.0 - 10.0))                        # up − fast_gap_mm
    assert ('contact_down', 40.0, 5.0) in cell.calls                       # find_max_mm · insert_limit_n
    assert names.index('contact_down') < names.index('line')
    assert r.insert_depth_mm == pytest.approx(DEPTH)                       # 솔이 컵에 들어간 길이 (내려온 거리가 아니다)
    assert names[-2:] == ['force_off', 'safe_retreat']


def _lines(cell):
    return [c for c in cell.calls if c[0] == 'line']


def test_cup_lifts_only_lift_mm_then_bounces(cell):
    """③ lift 만 띄운 자리가 왕복의 아래쪽 끝 — 바닥을 찧지 않는다(시나리오 3)."""
    wipe.wipe_cup()
    ups = [c for c in cell.calls if c[0] == 'move_rel' and c[1] > 0]
    assert ups[-1][1] == pytest.approx(2.0)                                # lift_mm 만
    bottom = POSE0[2] - 70.0 - 8.0                                         # 빠른 하강 70 + 찾기 8
    zs = [c[1][2] for c in _lines(cell)]
    assert min(zs) == pytest.approx(bottom + 2.0)                          # 가장 낮은 자리 = 바닥 + lift
    assert max(zs) == pytest.approx(bottom + 2.0 + 40.0)                   # 위아래 40 mm (stroke 20 × 2)


def test_cup_only_z_and_twist_change(cell):
    """④⑤ 위아래와 좌우 비틀기만 — x·y·기울기(a·b)는 그대로다(9/21 사용자: 손목이 기울면 안 된다)."""
    wipe.wipe_cup()
    lines = _lines(cell)
    assert len(lines) == 2 * 5                                             # cycles 5 번 오르내림
    for _n, pose, _r in lines:
        assert pose[0:2] == POSE0[0:2] and pose[3:5] == POSE0[3:5]
    twists = [round(pose[5] - POSE0[5], 6) for _n, pose, _r in lines]
    assert twists[:4] == [18.0, -18.0, 18.0, -18.0]                        # 올라가며 오른쪽 · 내려오며 왼쪽
    assert max(abs(t) for t in twists) == pytest.approx(18.0)              # 45° 같은 큰 각은 나오지 않는다


def test_cup_ends_at_bottom_with_wrist_home(cell):
    """⑥ 아래쪽 끝에서, 손목을 제자리로 돌려놓고, 이어 붙이지 않고 선다(시나리오 6)."""
    wipe.wipe_cup()
    lines = _lines(cell)
    _n, last, radius = lines[-1]
    assert last[2] == pytest.approx(min(c[1][2] for c in lines))
    assert last[5] == pytest.approx(POSE0[5]) and radius == 0.0
    assert all(r > 0 for _n, _p, r in lines[:-1])                          # 나머지는 이어 붙인다


def test_cup_strokes_blend_capped_and_c_wraps():
    """이어 붙이는 거리는 한 획의 45 % 이하 · c 는 −180~180 으로 감는다."""
    pts = wipe.cup_strokes([0, 0, 100, 0, 180, 170.0], 2.0, 18.0, 2, 5.0)
    assert pts[0][1] == pytest.approx(2 * 2.0 * 0.45)
    assert pts[0][0][5] == pytest.approx(-172.0)                           # 170 + 18 = 188 → −172


def test_insert_depth_capped_at_brush_length():
    """끝점이 실제 바닥보다 높아 gap 보다 더 내려가도 솔 길이(95)보다 더 들어갔다고 하지 않는다(9/21 Virtual 125 mm)."""
    p = CFG['f3']['wipe_cup']
    assert wipe.insert_depth(p, 38.0) == pytest.approx(95.0)
    assert wipe.insert_depth(p, 8.0) == pytest.approx(93.0)


def test_cup_stroke_shrinks_so_brush_stays_in(cell):
    """얕게 들어갔으면 솔이 컵 밖으로 나오지 않게 진폭을 줄인다."""
    cell.depth = 2.0
    CFG['f3']['wipe_cup']['tool']['clean_h_mm'] = 40.0                     # 짧은 솔이라 치고
    CFG['f3']['wipe_cup']['insert_min_mm'] = 10.0
    try:
        wipe.wipe_cup()
    finally:
        CFG['f3']['wipe_cup']['tool']['clean_h_mm'] = 95
        CFG['f3']['wipe_cup']['insert_min_mm'] = 85.0
    zs = [c[1][2] for c in _lines(cell)]
    inserted = 40.0 - (10.0 - 2.0)                                         # 32 mm 들어감
    assert max(zs) - min(zs) == pytest.approx(inserted - 2.0 - 10.0)       # 2 × (들어간 길이 − lift − keep_in)/2 = 20


def test_cup_blocked_before_bottom_is_force_limit(cell):
    """바닥에 닿기 전에 막히면 — 솔이 덜 들어갔다는 뜻이다(내려온 거리와 무관)."""
    cell.depth = 1.0                                                       # gap 10 중 1 mm 만에 막힘 → 95 − 9 = 86... 아래 참조
    CFG['f3']['wipe_cup']['insert_min_mm'] = 90.0                          # 90 mm 는 들어가야 한다고 두면
    try:
        r = wipe.wipe_cup()
    finally:
        CFG['f3']['wipe_cup']['insert_min_mm'] = 85.0
    assert not r.ok and r.code == FORCE_LIMIT
    assert 'line' not in [c[0] for c in cell.calls]                    # 문지르지 않는다
    assert r.insert_depth_mm == pytest.approx(95.0 - 9.0)                  # 어디까지 들어갔는지는 돌려준다


def test_cup_no_bottom_found_is_error(cell):
    cell.depth = 40.0                                                      # find_max_mm 까지 내려가도 못 찾음
    r = wipe.wipe_cup()
    assert not r.ok and r.code == ROBOT_ERROR
    assert 'line' not in [c[0] for c in cell.calls]


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


def test_cup_halt_does_not_auto_move(cell):
    """강제정지 뒤에는 로봇 위치를 모른다 → 힘만 끄고 움직이지 않는다(9/21 케이블 꼬임 사고)."""
    cell.halted = True
    with pytest.raises(wipe.cc.MotionHalted):
        wipe.wipe_cup()
    assert 'safe_retreat' not in [c[0] for c in cell.calls]


def test_cup_logs_depth_and_saves_force_log(cell):
    r = wipe.wipe_cup()
    assert any('바닥' in m for lvl, m in cell.logger.lines if lvl == 'info')
    assert r.force_log_path.endswith('.csv')
