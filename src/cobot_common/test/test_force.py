# -*- coding: utf-8 -*-
"""힘 함수(force.py) 시험 — 로봇·ROS 없이 가짜 두산 모듈로 호출 순서와 안전 동작을 본다.

    python3 -m pytest src/cobot_common/test/test_force.py

실제 힘 값은 Virtual 에 없으므로 실기(V-03)에서 본다. 여기서는 순서·판정·예외·설정 누락만.
"""
import copy

import pytest

from cobot_common import force

CFG = {'cell': {
    'limits': {'safe_z_mm': 300.0, 'timeout_s': 10.0},
    'force': {'compliance_stx': [3000, 3000, 500, 200, 200, 200], 'contact_step_mm': 2.0,
              'contact_vel_mm_s': 10.0, 'contact_acc_mm_s2': 50.0, 'retreat_vel_mm_s': 50.0,
              'retreat_acc_mm_s2': 100.0, 'force_max_n': 20.0, 'search_y_period_ratio': 2.0},
}}


class FakeDsr:
    """DSR_ROBOT2 흉내. 반환 규칙은 설치본과 같다: 성공 0 / 실패 -1, check_force_condition 은 만족 0 / 아니면 -1."""
    DR_BASE, DR_TOOL = 0, 1
    DR_AXIS_X, DR_AXIS_Y, DR_AXIS_Z = 0, 1, 2
    DR_COND_NONE = -10000
    DR_FC_MOD_REL = 1
    DR_MV_MOD_REL = 1

    def __init__(self, z=400.0, surface_z=None, k_n_per_mm=2.0, fail=()):
        self.calls = []
        self.pos = [100.0, 50.0, z, 0.0, 180.0, 0.0]
        self.surface_z = surface_z          # 이 높이 아래로 내려가면 힘이 생긴다 (None 이면 바닥 없음)
        self.k = k_n_per_mm
        self.fail = set(fail)

    def _r(self, name, *a, **kw):
        self.calls.append(name)
        return -1 if name in self.fail else 0

    def mwait(self, time=0):
        return self._r('mwait')

    def task_compliance_ctrl(self, stx, time=0):
        self.stx = stx
        return self._r('task_compliance_ctrl')

    def set_desired_force(self, fd, dir, time=0, mod=0):
        self.fd, self.dir, self.fmod = fd, dir, mod
        return self._r('set_desired_force')

    def release_force(self, time=0):
        return self._r('release_force')

    def release_compliance_ctrl(self):
        return self._r('release_compliance_ctrl')

    def _fz(self):
        if self.surface_z is None or self.pos[2] >= self.surface_z:
            return 0.0
        return -(self.surface_z - self.pos[2]) * self.k

    def get_tool_force(self, ref=None):
        self.calls.append('get_tool_force')
        return -1 if 'get_tool_force' in self.fail else [0.0, 0.0, self._fz(), 0.0, 0.0, 0.0]

    def check_force_condition(self, axis, min=-10000, max=-10000, ref=None):
        self.calls.append('check_force_condition')
        f = abs(self._fz())
        ok = (min == self.DR_COND_NONE or f >= min) and (max == self.DR_COND_NONE or f <= max)
        return 0 if ok else -1

    def get_current_posx(self, ref=None):
        return list(self.pos), 2

    def movel(self, pos, vel=None, acc=None, time=None, radius=None, ref=None, mod=0):
        self.last_movel = dict(pos=list(pos), vel=vel, acc=acc, ref=ref, mod=mod)
        if mod == self.DR_MV_MOD_REL:
            self.pos = [p + dp for p, dp in zip(self.pos, pos)]
        else:
            self.pos = list(pos)
        return self._r('movel')

    def move_periodic(self, amp, period, atime=None, repeat=None, ref=None):
        self.periodic = dict(amp=amp, period=period, repeat=repeat, ref=ref)
        return self._r('move_periodic')


@pytest.fixture
def robot(monkeypatch):
    """가짜 로봇 + 설정을 force 모듈에 끼운다. 반환된 함수로 다른 가짜 로봇·설정을 만들 수 있다."""
    state = {}

    def make(cfg=CFG, **kw):
        d = FakeDsr(**kw)
        monkeypatch.setattr(force, 'dsr', lambda: d)
        monkeypatch.setattr(force, 'cfg', lambda: cfg)
        state['d'] = d
        return d

    force._state.update(compliance=False, force=False, limit=None)
    yield make
    force._state.update(compliance=False, force=False, limit=None)


def test_force_on_order_and_direction(robot):
    d = robot()
    force.force_on('z', 4.0, 10.0)
    assert d.calls == ['mwait', 'task_compliance_ctrl', 'set_desired_force']     # 이동 끝 → 순응 → 힘
    assert d.fd == [0.0, 0.0, -4.0, 0.0, 0.0, 0.0] and d.dir == [0, 0, 1, 0, 0, 0]   # −Z 로 누름
    assert d.fmod == d.DR_FC_MOD_REL and d.stx == CFG['cell']['force']['compliance_stx']


@pytest.mark.parametrize('target,limit', [(10.0, 10.0), (12.0, 10.0), (0.0, 10.0), (4.0, 25.0), (-1.0, 10.0)])
def test_force_on_rejects_bad_values_without_moving(robot, target, limit):
    d = robot()
    with pytest.raises(ValueError):
        force.force_on('z', target, limit)
    assert d.calls == []


def test_force_on_rolls_back_when_force_fails(robot):
    d = robot(fail={'set_desired_force'})
    with pytest.raises(RuntimeError):
        force.force_on('z', 4.0, 10.0)
    assert d.calls[-1] == 'release_compliance_ctrl' and not force._state['compliance']


def test_force_off_order_and_idempotent(robot):
    d = robot()
    force.force_on('z', 4.0, 10.0)
    d.calls.clear()
    force.force_off()
    assert d.calls == ['release_force', 'release_compliance_ctrl']              # 힘 해제 → 순응 해제
    d.calls.clear()
    force.force_off()
    assert d.calls == []                                                        # 켜진 게 없으면 아무것도 안 부름


def test_force_reached_uses_zero_as_true(robot):
    d = robot(z=100.0, surface_z=110.0)                                         # 10 mm 눌림 → |Fz| 20 N
    assert force.force_reached('z', min=5.0) is True                            # 설치본 반환 0 → True (TS-01 D)
    assert force.force_reached('z', max=5.0) is False                           # 반환 -1 → False
    with pytest.raises(ValueError):
        force.force_reached('z')
    with pytest.raises(ValueError):
        force.force_reached('z', min=-1.0)
    assert d.calls.count('check_force_condition') == 2


def test_contact_down_stops_at_contact(robot):
    d = robot(z=400.0, surface_z=390.0)
    depth, f = force.contact_down(max_depth=40.0, limit=3.0)
    assert 10.0 <= depth < 40.0 and f >= 3.0                                    # 표면(10 mm) 지나 한두 단계 안에서 멈춤
    assert d.calls[:2] == ['mwait', 'task_compliance_ctrl']                      # 순응 켜고 내려간다
    assert d.calls[-1] == 'release_compliance_ctrl' and not force._state['compliance']
    assert d.last_movel['mod'] == d.DR_MV_MOD_REL and d.last_movel['ref'] == d.DR_BASE


def test_contact_down_stops_at_max_depth_without_surface(robot):
    d = robot(z=400.0, surface_z=None)
    depth, f = force.contact_down(max_depth=15.0, limit=3.0)
    assert depth == pytest.approx(15.0) and f == 0.0                            # 마지막 단계는 남은 깊이만큼
    assert d.pos[2] == pytest.approx(385.0)


def test_contact_down_force_over_max_raises_and_releases(robot):
    d = robot(z=400.0, surface_z=390.0, k_n_per_mm=50.0)                        # 단단한 면: 2 mm 에 100 N
    with pytest.raises(force.ForceLimitError):
        force.contact_down(max_depth=40.0, limit=15.0)
    assert d.calls[-1] == 'release_compliance_ctrl'


def test_contact_down_timeout(robot, monkeypatch):
    robot(z=400.0, surface_z=None)
    ticks = iter(range(0, 1000, 20))                                            # 한 번 볼 때마다 20 s 흐름
    monkeypatch.setattr(force.time, 'monotonic', lambda: next(ticks))
    with pytest.raises(force.MotionTimeout):
        force.contact_down(max_depth=40.0, limit=3.0)
    assert not force._state['compliance']


def test_missing_config_refuses_before_moving(robot):
    cfg = copy.deepcopy(CFG)
    del cfg['cell']['force']['contact_step_mm']
    d = robot(cfg=cfg)
    with pytest.raises(KeyError, match='contact_step_mm'):
        force.contact_down(max_depth=10.0, limit=3.0)
    assert 'movel' not in d.calls and 'task_compliance_ctrl' not in d.calls


def test_safe_retreat_goes_straight_up_to_safe_z(robot):
    d = robot(z=150.0)
    force.force_on('z', 4.0, 10.0)
    force.safe_retreat()
    assert d.calls[-3:] == ['release_force', 'release_compliance_ctrl', 'movel']  # 끄고 → 올린다
    assert d.last_movel['pos'][:3] == [100.0, 50.0, 300.0]                      # X·Y 그대로, Z 만 safe_z
    assert d.last_movel['mod'] == 0 and d.last_movel['vel'] == 50.0


def test_safe_retreat_does_nothing_above_safe_z(robot):
    d = robot(z=350.0)
    force.safe_retreat()
    assert 'movel' not in d.calls


def test_periodic_search_axes_and_repeat(robot):
    d = robot()
    force.periodic_search(amp=3.0, period=0.8, duration=6.0)
    p = d.periodic
    assert p['amp'] == [3.0, 3.0, 0.0, 0.0, 0.0, 0.0] and p['ref'] == d.DR_TOOL
    assert p['period'][:2] == [0.8, pytest.approx(1.6)] and p['repeat'] == 3   # 6 s // 1.6 s


def test_read_force_failure(robot):
    robot(fail={'get_tool_force'})
    with pytest.raises(RuntimeError):
        force.read_force()


def test_exports():
    import cobot_common as cc
    for name in ('force_on', 'force_off', 'force_reached', 'contact_down', 'periodic_search', 'safe_retreat',
                 'read_force', 'ForceLimitError', 'MotionTimeout'):
        assert hasattr(cc, name), name
