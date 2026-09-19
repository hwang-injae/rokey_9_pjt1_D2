# -*- coding: utf-8 -*-
"""motion.py 시험 — 로봇 없이 돈다(두산 API 를 가짜로 바꿔 어떤 명령이 어떤 순서·속도로 나가는지만 본다).
실행: python3 -m pytest -q src/cobot_common/test/test_motion.py        Virtual 시험은 rig_motion.py
"""
import copy

import pytest

from cobot_common import motion

SAFE_Z = 300.0
CFG = {
    'run': {'vel_scale': 1.0},
    'cell': {
        'limits': {'vel_free_pct': 60, 'vel_carry_pct': 30, 'safe_z_mm': SAFE_Z},
        'motion': {'vel_tcp_max_mm_s': 500.0, 'acc_tcp_max_mm_s2': 1000.0,
                   'vel_joint_max_deg_s': 100.0, 'acc_joint_max_deg_s2': 200.0},
        'stations': {'HOME': {'posj': [0, 0, 90, 0, 90, 0]},
                     'WEIGH': {'posx': [400, 100, 450, 0, 180, 0]},          # 안전 높이보다 높다
                     'TOOL_SPONGE': {'posx': [300, -200, 120, 0, 180, 0]},   # 안전 높이보다 낮다
                     'SOAP': {'posx': None}},                                 # 아직 티칭 전
        'beds': {'SPONGE_BED_B': {'frame': None, 'origin_posx': [350, 0, 50, 0, 180, 0]},
                 'SPONGE_BED_C': {'frame': 'BED', 'origin_posx': [350, 80, 50, 0, 180, 0]}},
        'zones': {'RET_B': {'frame': None, 'origin_posx': [200, 300, 40, 0, 180, 0]}},
    },
}


class FakeDsr:
    """두산 API 흉내 — 부른 것을 적어 두기만 한다."""
    DR_BASE, DR_TOOL, DR_MV_MOD_ABS, DR_MV_MOD_REL = 0, 1, 0, 1

    def __init__(self, z=500.0, ret=0):
        self.z, self.ret, self.calls = z, ret, []

    def get_current_posx(self, ref=None):
        return [100.0, 0.0, self.z, 0.0, 180.0, 0.0], 2

    def movel(self, pos, **kw):
        self.calls.append(('movel', list(pos), kw))
        return self.ret

    def movej(self, pos, **kw):
        self.calls.append(('movej', list(pos), kw))
        return self.ret


@pytest.fixture
def robot(monkeypatch):
    cfg = copy.deepcopy(CFG)
    fake = FakeDsr()
    monkeypatch.setattr(motion, 'cfg', lambda: cfg)
    monkeypatch.setattr(motion, 'dsr', lambda: fake)
    fake.cfg = cfg
    return fake


# ------------------------------------------------------------------ move_to
def test_move_to_home_is_joint_move_at_free_speed(robot):
    assert motion.move_to('HOME', False) == 0.0
    (name, pos, kw), = robot.calls                                  # 이미 안전 높이 위 → 상승 없이 movej 한 번
    assert name == 'movej' and pos == [0, 0, 90, 0, 90, 0]
    assert (kw['vel'], kw['acc']) == (60.0, 120.0)                  # 100 × 60 % · 200 × 60 %


def test_move_to_lifts_first_when_below_safe_height(robot):
    robot.z = 120.0
    motion.move_to('WEIGH', True)
    lift, go = robot.calls
    assert lift[0] == 'movel' and lift[1] == [0, 0, SAFE_Z - 120.0, 0, 0, 0] and lift[2]['mod'] == robot.DR_MV_MOD_REL
    assert go[1] == [400, 100, 450, 0, 180, 0] and go[2]['mod'] == robot.DR_MV_MOD_ABS and go[2]['ref'] == robot.DR_BASE
    assert (go[2]['vel'], go[2]['acc']) == (150.0, 300.0)           # 들고 있으면 30 %


def test_move_to_never_goes_below_safe_height(robot):
    above = motion.move_to('TOOL_SPONGE', False)
    assert above == SAFE_Z - 120.0                                  # 남은 높이를 돌려준다 → 하강은 부르는 쪽이
    assert robot.calls[-1][1][2] == SAFE_Z
    assert motion.move_to('SPONGE_BED_B', True) == SAFE_Z - 50.0    # beds · zones 의 이름도 받는다
    assert motion.move_to('RET_B', False) == SAFE_Z - 40.0


@pytest.mark.parametrize('station,exc', [('SOAP', KeyError),                # 좌표가 비어 있다
                                         ('NOWHERE', KeyError),             # 그런 이름이 없다
                                         ('SPONGE_BED_C', NotImplementedError)])   # 사용자 좌표계는 아직
def test_move_to_refuses_without_moving(robot, station, exc):
    with pytest.raises(exc):
        motion.move_to(station, False)
    assert robot.calls == []


@pytest.mark.parametrize('section,key', [('limits', 'safe_z_mm'), ('limits', 'vel_free_pct'),
                                         ('motion', 'vel_tcp_max_mm_s'), ('motion', 'acc_joint_max_deg_s2')])
def test_empty_value_means_no_motion(robot, section, key):
    robot.cfg['cell'][section][key] = None                          # INF-04 골격처럼 비어 있다
    with pytest.raises(KeyError, match=f'cell.{section}.{key}'):
        motion.move_to('HOME', False)
    assert robot.calls == []


def test_vel_scale_slows_everything(robot):
    robot.cfg['run']['vel_scale'] = 0.3
    motion.move_to('HOME', False)
    assert robot.calls[0][2]['vel'] == pytest.approx(100.0 * 0.6 * 0.3)


def test_failed_command_raises(robot):
    robot.ret = -1
    with pytest.raises(RuntimeError, match='movej'):
        motion.move_to('HOME', False)


# ------------------------------------------------------------------ move_rel
def test_move_rel_default_speed_is_carry(robot):
    motion.move_rel(10, 0, -5, 'TOOL')
    (_, pos, kw), = robot.calls
    assert pos == [10, 0, -5, 0, 0, 0] and kw['ref'] == robot.DR_TOOL and kw['mod'] == robot.DR_MV_MOD_REL
    assert (kw['vel'], kw['acc']) == (150.0, 300.0)


def test_move_rel_explicit_speed_is_used_but_capped(robot):
    motion.move_rel(0, 0, -2, 'BASE', vel_mm_s=5.0, acc_mm_s2=20.0)     # force.py 의 접촉 하강처럼 아주 느리게
    assert (robot.calls[-1][2]['vel'], robot.calls[-1][2]['acc']) == (5.0, 20.0)
    robot.cfg['run']['vel_scale'] = 0.5
    motion.move_rel(0, 0, 50, 'BASE', vel_mm_s=9999, acc_mm_s2=99999)
    assert (robot.calls[-1][2]['vel'], robot.calls[-1][2]['acc']) == (250.0, 500.0)   # 100 % 기준 × vel_scale 을 못 넘는다


@pytest.mark.parametrize('kw', [dict(frame='WORLD'), dict(frame='BASE', vel_mm_s=0), dict(frame='BASE', acc_mm_s2=-1)])
def test_move_rel_bad_arguments(robot, kw):
    with pytest.raises(ValueError):
        motion.move_rel(0, 0, 1, kw.pop('frame'), **kw)
    assert robot.calls == []


# ------------------------------------------------------------------ move_joint_rel
def test_move_joint_rel_moves_one_joint(robot):
    motion.move_joint_rel(5, -15.0)
    (name, pos, kw), = robot.calls
    assert name == 'movej' and pos == [0, 0, 0, 0, -15.0, 0] and kw['mod'] == robot.DR_MV_MOD_REL
    assert (kw['vel'], kw['acc']) == (30.0, 60.0)                   # 기본은 들고 있는 속도
    motion.move_joint_rel(6, 10, carrying=False)
    assert robot.calls[-1][2]['vel'] == 60.0


def test_move_joint_rel_time_stretches_with_vel_scale(robot):
    robot.cfg['run']['vel_scale'] = 0.5
    motion.move_joint_rel(5, 15, time_s=0.3)
    assert robot.calls[-1][2] == {'mod': robot.DR_MV_MOD_REL, 'time': pytest.approx(0.6)}


def test_move_joint_rel_time_cannot_beat_the_speed_cap(robot, monkeypatch):
    """시간 지정 경로에도 속도 상한이 있다(PR #15 검토): 평균 속도가 100 % 기준 × vel_scale 을 넘으면 시간을 늘린다."""
    warned = []
    monkeypatch.setattr(motion, '_warn', warned.append)
    motion.move_joint_rel(5, 60, time_s=0.1)                        # 600 deg/s 를 요구 — 상한은 100 deg/s
    assert robot.calls[-1][2]['time'] == pytest.approx(0.6) and len(warned) == 1
    motion.move_joint_rel(5, -60, time_s=0.1)                       # 방향이 반대여도 같다
    assert robot.calls[-1][2]['time'] == pytest.approx(0.6)
    robot.cfg['run']['vel_scale'] = 0.5                             # 상한도 같이 낮아진다: 50 deg/s
    motion.move_joint_rel(5, 60, time_s=1.0)                        # 1.0 / 0.5 = 2.0 s → 30 deg/s, 상한 안
    assert robot.calls[-1][2]['time'] == pytest.approx(2.0) and len(warned) == 2
    motion.move_joint_rel(5, 60, time_s=0.5)                        # 1.0 s → 60 deg/s > 50 → 1.2 s 로
    assert robot.calls[-1][2]['time'] == pytest.approx(1.2) and len(warned) == 3


def test_move_joint_rel_time_within_cap_is_untouched(robot, monkeypatch):
    warned = []
    monkeypatch.setattr(motion, '_warn', warned.append)
    motion.move_joint_rel(5, 15, time_s=0.3)                        # 50 deg/s — 털기 시험 값
    assert robot.calls[-1][2]['time'] == pytest.approx(0.3) and warned == []
    motion.move_joint_rel(5, 0, time_s=0.3)                         # 0° 는 나누기 없이 그대로
    assert robot.calls[-1][2]['time'] == pytest.approx(0.3)


def test_move_joint_rel_time_needs_the_cap_value(robot):
    robot.cfg['cell']['motion']['vel_joint_max_deg_s'] = None       # 기준값이 비어 있으면 움직이지 않는다
    with pytest.raises(KeyError, match='cell.motion.vel_joint_max_deg_s'):
        motion.move_joint_rel(5, 15, time_s=0.3)
    assert robot.calls == []


@pytest.mark.parametrize('joint', [0, 7, 'J5', 5.5])
def test_move_joint_rel_bad_joint(robot, joint):
    with pytest.raises(ValueError):
        motion.move_joint_rel(joint, 10)
    assert robot.calls == []
