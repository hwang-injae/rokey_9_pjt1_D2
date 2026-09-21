# -*- coding: utf-8 -*-
"""soap · wipe_cup(F3-03) 시험 — 로봇 없이 가짜 공용 함수로 순서·판정·실패 처리를 본다.

    python3 -m pytest -q src/f3_wipe/test/test_f3_soap_cup.py

soap 은 접촉 동작이 아니다(수조가 비어 있다) → 순응·힘제어·힘 감시가 없어야 한다.
wipe_cup 은 **삽입만** 힘으로 찾고(contact_down), 문지르기는 순응을 끈 위치 제어다(관절 이동, 2.1903).
실제 깊이·회전각은 V-10(실기)에서 확정한다 — 여기서는 순서·상한 처리만 본다.
"""
import math

import pytest

from cobot_api import FORCE_LIMIT, OK, ROBOT_ERROR, TIMEOUT
from f3_wipe import wipe

CFG = {
    'run': {'vel_scale': 0.3},
    'cell': {'limits': {'insert_limit_n': 15.0, 'timeout_s': 30.0}},     # main 값 — 컵은 이것을 쓰지 않는다
    'f3': {
        'soap': {'depth_mm': 40.0, 'hold_s': 0.0, 'vel_mm_s': 80.0, 'log_dir': 'logs/f3'},
        'wipe_cup': {
            'tool': {'clean_h_mm': 95, 'd_mm': 55},
            'over_cup_up_mm': 40.0, 'over_cup_dy_mm': 140.0, 'find_limit_n': 5.0,
            'fast_down_mm': 80.0, 'find_max_mm': 40.0,
            'lift_mm': 2.0, 'lift_vel_mm_s': 40.0,
            'stroke_mm': 20.0,
            'spin_deg': 360.0, 'spin_seg_deg': 90.0, 'spin_first': -1, 'j6_limit_deg': 360.0, 'j6_margin_deg': 10.0,
            'lin_vel_mm_s': 96.0, 'rot_vel_deg_s': 180.0, 'lin_acc_mm_s2': 900.0, 'rot_acc_deg_s2': 810.0,
            'blend_radius_mm': 5.0,
            'cycles': 3, 'keep_in_mm': 10.0,
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
        self.j6 = self.j6_min = self.j6_max = 21.0      # 컵 위 자세의 6번 축 (9/21 Virtual 기록)
        self.j4 = 0.0                                    # 4번 축 — 움직이면 안 된다
        self.j6_sign = 1                                 # 자세 c + → 6번 축 + (Virtual 기록). −1 이면 반대로 도는 로봇
        self.logger = _Logger()

    def cfg(self):
        return CFG

    def move_to(self, station, carrying, kind=None, point=None):
        self.calls.append(('move_to', station, kind, point))
        self.pose = list(POSE0)
        return self.up

    def move_rel(self, dx, dy, dz, frame, **kw):
        self.calls.append(('move_rel', round(dz, 1), round(kw.get('vel_mm_s') or 0.0, 1), round(dy, 1)))
        self.pose = [self.pose[0] + dx, self.pose[1] + dy, self.pose[2] + dz] + self.pose[3:]

    def move_line(self, pose, vel_mm_s, vel_deg_s, acc_mm_s2, acc_deg_s2, radius_mm=0.0):
        self.calls.append(('line', list(pose), radius_mm))
        d = math.atan2(math.sin(math.radians(pose[5] - self.pose[5])), math.cos(math.radians(pose[5] - self.pose[5])))
        self.j6 += self.j6_sign * math.degrees(d)                        # 자세 c 가 짧은 쪽으로 돈 만큼 6번 축이 돈다
        self.j6_min, self.j6_max = min(self.j6_min, self.j6), max(self.j6_max, self.j6)
        self.pose = list(pose)

    def joints(self):
        return [0.0, 0.0, 90.0, self.j4, 90.0, self.j6]

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
                 'read_force', 'force_off', 'safe_retreat', 'io_node', 'is_halted', 'where', 'joints'):
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
# 돌려주는 insert_depth_mm = 컵 위에서 바닥까지 내려간 거리 = 빠른 하강 80 + 찾기 8 (가짜는 8 mm 에서 바닥).
DEPTH = 80.0 + 8.0
TO_CUP = [(40.0, 0.0), (0.0, 140.0), (-40.0, 0.0)]                         # HOME → 컵 위 (dz, dy)


def _rels(calls):
    return [(c[1], c[3]) for c in calls if c[0] == 'move_rel']


def _split(cell):
    """(닦기까지의 호출, 마지막 force_off 부터의 정리 호출)."""
    i = max(k for k, c in enumerate(cell.calls) if c[0] == 'force_off')
    return cell.calls[:i], cell.calls[i:]


def test_cup_starts_at_home_and_goes_up_over_down(cell):
    """⓪ 초기자세 HOME → z +40 → y +140 → z −40 — 솔이 컵에 걸리지 않게(박진용 9/21)."""
    wipe.wipe_cup()
    assert cell.calls[0][:2] == ('move_to', 'HOME')
    assert _rels(cell.calls)[:3] == TO_CUP


def test_cup_returns_up_then_reverse_to_home(cell):
    """⑦ 솔을 곧게 뽑아 컵 위 높이 → z +40 → y −140 → z −40 → HOME. 컵 위 높이에서 옆으로 바로 가지 않는다."""
    wipe.wipe_cup()
    _work, back = _split(cell)
    rels = _rels(back)
    assert rels[0][1] == 0.0 and rels[0][0] > 0                            # 먼저 곧게 뽑는다
    assert rels[1:] == [(40.0, 0.0), (0.0, -140.0), (-40.0, 0.0)]
    assert back[-1][:2] == ('move_to', 'HOME')
    assert cell.pose[2] == pytest.approx(POSE0[2] + 0.0)                   # 가짜 HOME 높이로 돌아왔다


def test_cup_fast_then_finds_bottom_by_force(cell):
    """① 컵 위에서 fast_down_mm 만큼 빠르게 → ② 나머지는 힘으로 찾는다(시나리오 1·2)."""
    r = wipe.wipe_cup()
    assert r.ok and r.code == OK
    names = [c[0] for c in cell.calls]
    fast = [c for c in cell.calls if c[0] == 'move_rel' and c[1] < 0][1]   # [0] 은 컵 위로 내려오는 −40
    assert fast[1] == pytest.approx(-80.0)                                 # fast_down_mm — 티칭 끝점(up)과 무관
    assert ('contact_down', 40.0, 5.0) in cell.calls                       # find_max_mm · find_limit_n (insert_limit_n 15 아님)
    assert names.index('contact_down') < names.index('line')
    assert r.insert_depth_mm == pytest.approx(DEPTH)                       # 잰 값 — 바닥 위치를 미리 정하지 않는다
    assert cell.calls[-1][:2] == ('move_to', 'HOME')


def _lines(cell):
    return [c for c in cell.calls if c[0] == 'line']


def test_cup_lifts_only_lift_mm_then_bounces(cell):
    """③ lift 만 띄운 자리가 왕복의 아래쪽 끝 — 바닥을 찧지 않는다(시나리오 3)."""
    wipe.wipe_cup()
    work, _back = _split(cell)
    ups = [c for c in work if c[0] == 'move_rel' and c[1] > 0]
    assert ups[-1][1] == pytest.approx(2.0)                                # lift_mm 만
    bottom = POSE0[2] - 80.0 - 8.0                                         # 빠른 하강 80 + 찾기 8
    zs = [c[1][2] for c in _lines(cell)]
    assert min(zs) == pytest.approx(bottom + 2.0)                          # 가장 낮은 자리 = 바닥 + lift
    assert max(zs) == pytest.approx(bottom + 2.0 + 40.0)                   # 위아래 40 mm (stroke 20 × 2)


def _unwrap(cs):
    out = [cs[0]]
    for c in cs[1:]:
        out.append(out[-1] + (c - out[-1] + 180.0) % 360.0 - 180.0)
    return out


def test_cup_only_z_and_spin_change(cell):
    """④⑤ 위아래와 6번 축 회전만 — x·y·기울기(a·b)는 그대로다(손목이 기울면 안 된다)."""
    wipe.wipe_cup()
    lines = _lines(cell)
    assert len(lines) == 3 * 2 * 4                                         # 3 회 × (올라가며 4 조각 + 내려오며 4 조각)
    for _n, pose, _r in lines:
        assert pose[0:2] == [POSE0[0], POSE0[1] + 140.0] and pose[3:5] == POSE0[3:5]


def test_cup_spins_360_ccw_up_and_back_down(cell):
    """올라가며 −360°(반시계, 9/21 실물 확인), 내려오며 +360° — 조각마다 z 도 같이 오른다."""
    wipe.wipe_cup()
    lines = _lines(cell)
    c = _unwrap([POSE0[5]] + [p[5] for _n, p, _r in lines])
    z = [p[2] for _n, p, _r in lines]
    assert c[4] - c[0] == pytest.approx(-360.0) and c[8] - c[4] == pytest.approx(360.0)
    assert all(b > a for a, b in zip(z[:4], z[1:4])) and z[3] - z[0] == pytest.approx(30.0)   # 올라가는 4 조각
    assert cell.j6_min == pytest.approx(21.0 - 360.0) and cell.j6_max == pytest.approx(21.0)  # 한계(±350) 안


def test_cup_ends_at_bottom_with_wrist_home(cell):
    """⑥ 아래쪽 끝 · 6번 축 제자리에서 선다. 첫 조각(방향 확인)과 꼭대기·아래쪽 끝(방향이 바뀌는 점)은 이어 붙이지 않는다."""
    wipe.wipe_cup()
    lines = _lines(cell)
    _n, last, radius = lines[-1]
    assert last[2] == pytest.approx(min(c[1][2] for c in lines))
    assert cell.j6 == pytest.approx(21.0) and radius == 0.0
    stops = [k for k, (_n, _p, r) in enumerate(lines) if r == 0.0]
    assert stops == [0, 3, 7, 11, 15, 19, 23]                              # 첫 조각 + 꼭대기 3 번 + 아래쪽 끝 3 번


def test_spin_direction_avoids_joint_limit():
    p = CFG['f3']['wipe_cup']
    assert wipe.spin_direction(21.0, p) == -1                              # 반시계 먼저 (−339° 까지)
    assert wipe.spin_direction(-20.0, p) == 1                              # −380° 는 한계 밖 → 반대로
    with pytest.raises(ValueError):
        wipe.spin_direction(0.0, dict(p, j6_margin_deg=10.0, spin_deg=355.0))


def test_cup_no_room_to_spin_is_error_and_retreats(cell):
    """6번 축이 어느 쪽으로도 360° 돌 수 없으면 돌지 않고 ROBOT_ERROR — 위치는 아니까 HOME 으로 돌아온다."""
    cell.j6 = cell.j6_min = cell.j6_max = 0.0
    CFG['f3']['wipe_cup']['j6_margin_deg'] = 360.0
    try:
        r = wipe.wipe_cup()
    finally:
        CFG['f3']['wipe_cup']['j6_margin_deg'] = 10.0
    assert not r.ok and r.code == ROBOT_ERROR
    assert _lines(cell) == [] and cell.calls[-1][:2] == ('move_to', 'HOME')


def test_cup_stops_if_j4_moves(cell):
    """🚨 첫 조각 뒤 4번 축이 1° 넘게 움직였으면 멈춘다 — 6번 축만 돌아야 한다(9/21 실기에서 4번 축이 돌아 부딪힐 뻔)."""
    real = cell.move_line

    def tilt(*a, **kw):
        real(*a, **kw)
        cell.j4 = 5.0

    cell.move_line = tilt
    wipe.cc.move_line = tilt
    r = wipe.wipe_cup()
    assert not r.ok and r.code == ROBOT_ERROR
    assert len(_lines(cell)) == 1 and cell.calls[-1][:2] == ('move_to', 'HOME')


def test_cup_wrong_spin_direction_stops_after_first_segment(cell):
    """🚨 자세 c 와 6번 축 부호가 반대인 로봇이면 첫 조각 뒤에 멈춘다 — 그대로 돌면 한계를 넘는다."""
    cell.j6_sign = -1
    r = wipe.wipe_cup()
    assert not r.ok and r.code == ROBOT_ERROR
    assert len(_lines(cell)) == 1 and cell.calls[-1][:2] == ('move_to', 'HOME')


def test_cup_strokes_segments_under_180_and_c_wraps():
    """조각은 180° 미만 · 이어 붙이는 거리는 한 조각의 45 % 이하 · c 는 −180~180 으로 감는다."""
    pts = wipe.cup_strokes([0, 0, 100, 0, 180, 170.0], 20.0, 360.0, 90.0, -1, 1, 5.0)
    assert len(pts) == 8 and pts[1][1] == pytest.approx(min(5.0, 10.0 * 0.45))
    assert pts[3][1] == 0.0 and pts[7][1] == 0.0                           # 꼭대기·아래쪽 끝은 이어 붙이지 않는다
    assert pts[3][0][5] == pytest.approx(170.0)                            # 360° 돌면 제자리 (감긴 값)
    with pytest.raises(ValueError):
        wipe.cup_strokes([0, 0, 100, 0, 180, 0.0], 20.0, 360.0, 180.0, -1, 1, 5.0)


def test_cup_stroke_shrinks_so_brush_stays_in(cell):
    """짧은 솔이면 꼭대기에서도 솔이 컵 안에 남게 진폭을 줄인다."""
    CFG['f3']['wipe_cup']['tool']['clean_h_mm'] = 40.0                     # 짧은 솔이라 치고
    try:
        wipe.wipe_cup()
    finally:
        CFG['f3']['wipe_cup']['tool']['clean_h_mm'] = 95
    zs = [c[1][2] for c in _lines(cell)]
    assert max(zs) - min(zs) == pytest.approx(40.0 - 2.0 - 10.0)           # 2 × (솔 − lift − keep_in)/2 = 28


def test_cup_bottom_found_early_still_scrubs_from_there(cell):
    """바닥이 예상(실측 90)보다 가까워도 **찾은 자리**에서 닦는다 — 바닥 위치를 미리 정하지 않는다."""
    cell.depth = 1.0
    r = wipe.wipe_cup()
    assert r.ok and r.insert_depth_mm == pytest.approx(80.0 + 1.0)
    assert min(c[1][2] for c in _lines(cell)) == pytest.approx(POSE0[2] - 81.0 + 2.0)


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
    assert [c[0] for c in cell.calls] == ['force_off']                     # 끄기만 하고 움직이지 않는다


def test_cup_logs_depth_and_saves_force_log(cell):
    r = wipe.wipe_cup()
    assert any('바닥' in m for lvl, m in cell.logger.lines if lvl == 'info')
    assert r.force_log_path.endswith('.csv')
