# -*- coding: utf-8 -*-
"""motion.py 시험 — 로봇 없이 돈다(두산 API 를 가짜로 바꿔 어떤 명령이 어떤 순서·속도로 나가는지만 본다).
실행: python3 -m pytest -q src/cobot_common/test/test_motion.py        Virtual 시험은 rig_motion.py
"""
import copy
import threading
import time

import pytest

from cobot_common import motion

SAFE_Z = 300.0
CFG = {
    'run': {'vel_scale': 1.0},
    'cell': {
        'limits': {'vel_free_pct': 60, 'vel_carry_pct': 30, 'safe_z_mm': SAFE_Z},
        'motion': {'vel_tcp_max_mm_s': 500.0, 'acc_tcp_max_mm_s2': 1000.0,
                   'vel_joint_max_deg_s': 100.0, 'acc_joint_max_deg_s2': 200.0, 'move_timeout_s': 5.0},
        'stations': {'HOME': {'posj': [0, 0, 90, 0, 90, 0]},
                     'WEIGH': {'posx': [400, 100, 450, 0, 180, 0]},          # 안전 높이보다 높다
                     'TOOL_SPONGE': {'posx': [300, -200, 120, 0, 180, 0]},   # 안전 높이보다 낮다
                     'SOAP': {'posx': None},                                  # 아직 티칭 전
                     'WASTE': {'BOWL': {'posx': [600, -170, 240, 0, 180, 0]},          # 종류별 자세 (9/20 CELL-04)
                               'CUP': {'posx': [110, -400, 240, 90, -160, -160]}},
                     'ISOLATE': {'BOWL': {'posx': None}, 'CUP': {'posx': None}},         # 종류별인데 아직 티칭 전
                     'TOOL_BRUSH': {'pick': {'posj': [-28, 17, 84, 0, 79, -28]},         # 용도별 자세
                                    'return': {'posx': [420, -220, 130, 0, 180, 0]}}},
        'beds': {'SPONGE_BED_B': {'place': {'approach_posx': [350, 0, 450, 0, 180, 0],   # 접근점이 안전 높이보다 높다
                                            'posx': [350, 0, 50, 0, 180, 0]},
                                  'wash': {'approach_posx': [300, 0, 235, 0, 180, 0],     # 접근점이 안전 높이보다 낮다
                                           'posx': [300, 0, 47, 0, 180, 0]},
                                  'seat': {'contact_limit_n': None}},                     # 자세가 아닌 값 — point 로 고를 수 없다
                 'SPONGE_BED_C': {'place': {'frame': 'BED', 'posx': [350, 80, 50, 0, 180, 0]}}},
        'zones': {'RET_B': {'slots': [{'posj': [0, 23, 68, 0, 88, 0]}, {'posj': None}]}},
        'rack': {'slots': {'RACK_B1': {'posx': [300, 600, 310, 90, 95, 7]},
                           'RACK_C1': {'approach_posx': [331, 401, 411, 80, 72, -91], 'posx': [331, 401, 279, 80, 72, -91]}}},
    },
}


class FakeDsr:
    """두산 API 흉내 — 부른 것을 적어 두기만 한다."""
    DR_BASE, DR_TOOL, DR_MV_MOD_ABS, DR_MV_MOD_REL = 0, 1, 0, 1

    def __init__(self, z=500.0, ret=0, busy_polls=2):
        self.z, self.ret, self.calls = z, ret, []
        self.busy_polls = busy_polls            # 이동 하나가 끝나기까지 check_motion 이 '움직이는 중'을 몇 번 돌려주나
        self.left = 0
        self.paused = False                     # 드라이버가 일시정지 상태인가 (그동안은 계속 '움직이는 중')

    def get_current_posx(self, ref=None):
        return [100.0, 0.0, self.z, 0.0, 180.0, 0.0], 2

    def amovel(self, pos, **kw):                # 비동기: 보내고 바로 돌아온다 (기록 이름은 그대로 movel — 나가는 명령은 같다)
        self.calls.append(('movel', list(pos), kw))
        self.left = self.busy_polls
        return self.ret

    def amovej(self, pos, **kw):
        self.calls.append(('movej', list(pos), kw))
        self.left = self.busy_polls
        return self.ret

    def check_motion(self):
        if self.left > 0 and not self.paused:
            self.left -= 1
        return 2 if self.left > 0 else 0


@pytest.fixture
def robot(monkeypatch):
    cfg = copy.deepcopy(CFG)
    fake = FakeDsr()
    fake.services = []                          # 드라이버로 나간 move_pause · move_resume · move_stop

    def call(name):
        fake.services.append(name)
        if name == 'pause':
            fake.paused = True
        elif name == 'resume':
            fake.paused = False
        elif name == 'stop':
            fake.left, fake.paused = 0, False
    monkeypatch.setattr(motion, 'cfg', lambda: cfg)
    monkeypatch.setattr(motion, 'dsr', lambda: fake)
    monkeypatch.setattr(motion, '_call', call)
    monkeypatch.setattr(motion, '_POLL_S', 0.001)
    motion.clear_halt()
    fake.cfg = cfg
    yield fake
    motion.clear_halt()


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


def test_move_to_picks_pose_by_kind(robot):
    assert motion.move_to('WASTE', True, 'CUP') == SAFE_Z - 240.0
    assert robot.calls[-1][1] == [110, -400, SAFE_Z, 90, -160, -160]        # 컵용 자세(옆에서 잡는 방향)의 상공
    motion.move_to('WASTE', True, kind='BOWL')
    assert robot.calls[-1][1][:2] == [600, -170]
    motion.move_to('HOME', False, 'BOWL')                                   # 종류별이 아닌 자리에서는 kind 를 무시한다
    assert robot.calls[-1][0] == 'movej'


def test_move_to_picks_pose_by_point(robot):
    assert motion.move_to('TOOL_BRUSH', False, point='pick') == 0.0         # 관절 자세 → 그 자세까지
    assert robot.calls[-1][:2] == ('movej', [-28, 17, 84, 0, 79, -28])
    assert motion.move_to('TOOL_BRUSH', True, point='return') == SAFE_Z - 130.0
    assert motion.move_to('RET_B', False, point=1) == 0.0                   # 반납 구역은 슬롯 번호(1 부터)
    assert robot.calls[-1][:2] == ('movej', [0, 23, 68, 0, 88, 0])


def test_move_to_goes_to_approach_point_and_returns_height_to_end(robot):
    up = motion.move_to('SPONGE_BED_B', True, point='place')
    assert robot.calls[-1][1] == [350, 0, 450, 0, 180, 0] and up == 450.0 - 50.0     # 접근점까지 가고, 끝점까지 남은 높이
    up = motion.move_to('SPONGE_BED_B', True, point='wash')
    assert robot.calls[-1][1][2] == SAFE_Z and up == SAFE_Z - 47.0                  # 접근점이 낮으면 안전 높이에서 멈춘다
    up = motion.move_to('RACK_C1', True, 'CUP')                                     # 팔레트 칸 이름도 받는다
    assert robot.calls[-1][1][2] == 411 and up == 411.0 - 279.0
    assert motion.move_to('RACK_B1', True) == 0.0                                   # 접근점이 없고 안전 높이보다 높다 → 그 자세까지


@pytest.mark.parametrize('args,exc', [(('SOAP',), KeyError),                          # 좌표가 비어 있다
                                      (('NOWHERE',), KeyError),                       # 그런 이름이 없다
                                      (('SPONGE_BED_C', None, 'place'), NotImplementedError),   # 사용자 좌표계는 못 쓴다
                                      (('WASTE',), ValueError),                       # 종류별인데 kind 를 안 줬다
                                      (('WASTE', 'PLATE'), ValueError),               # 없는 종류
                                      (('ISOLATE', 'CUP'), KeyError),                 # 종류별인데 아직 안 찍었다
                                      (('TOOL_BRUSH',), ValueError),                  # 자세가 여러 개인데 point 를 안 줬다
                                      (('SPONGE_BED_B', None, 'seat'), ValueError),   # 자세가 아닌 것을 골랐다
                                      (('WEIGH', None, 'pick'), ValueError),          # 자세가 하나인데 point 를 줬다
                                      (('RET_B',), ValueError),                       # 슬롯 번호를 안 줬다
                                      (('RET_B', None, 0), ValueError),               # 슬롯 번호는 1 부터
                                      (('RET_B', None, 3), ValueError),               # 없는 슬롯
                                      (('RET_B', None, 2), KeyError)])                # 슬롯은 있는데 아직 안 찍었다
def test_move_to_refuses_without_moving(robot, args, exc):
    station, kind, point = (list(args) + [None, None])[:3]
    with pytest.raises(exc):
        motion.move_to(station, False, kind, point)
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


# ------------------------------------------------------------------ 일시정지 · 재개 · 강제정지 (V-24)
def _later(delay_s, fn):
    t = threading.Timer(delay_s, fn)
    t.start()
    return t


def test_motion_is_sent_async_and_polled(robot):
    robot.busy_polls = 5
    motion.move_joint_rel(5, 10)
    assert robot.left == 0 and robot.services == []                 # 끝날 때까지 기다렸고, 아무것도 누르지 않았다


def test_pause_during_motion_then_resume_continues(robot):
    robot.busy_polls = 40
    _later(0.01, motion.pause)                                      # 통신 노드 콜백이 깃발을 세우는 자리
    _later(0.08, motion.resume)
    t0 = time.monotonic()
    motion.move_joint_rel(5, 10)                                    # 일시정지 동안에는 돌아오지 않는다
    assert robot.services == ['pause', 'resume']                    # 드라이버에는 한 번씩만
    assert robot.left == 0 and time.monotonic() - t0 >= 0.07        # 재개 뒤 **같은 이동**이 끝났다(새 이동 명령 없음)
    assert [c[0] for c in robot.calls] == ['movej']


def test_pause_while_idle_holds_the_next_move(robot):
    motion.pause()
    _later(0.05, motion.resume)
    motion.move_joint_rel(5, 10)
    assert robot.services == []                                     # 멈출 이동이 없었으니 드라이버에는 아무것도 안 보냈다
    assert len(robot.calls) == 1


def test_halt_stops_and_blocks_until_cleared(robot):
    robot.busy_polls = 1000
    _later(0.01, motion.halt)
    with pytest.raises(motion.MotionHalted):
        motion.move_to('WEIGH', False)
    assert robot.services == ['stop'] and motion.is_halted()
    sent = len(robot.calls)
    with pytest.raises(motion.MotionHalted):                        # 정지 뒤 다음 명령이 나가면 로봇이 다시 움직인다(V-24a T4) → 막는다
        motion.move_rel(0, 0, 10, 'BASE')
    assert len(robot.calls) == sent
    motion.clear_halt()
    motion.move_rel(0, 0, 10, 'BASE')
    assert len(robot.calls) == sent + 1


def test_move_timeout_sends_stop(robot):
    robot.busy_polls = 10 ** 9
    robot.cfg['cell']['motion']['move_timeout_s'] = 0.02
    with pytest.raises(motion.MoveTimeout):
        motion.move_joint_rel(5, 10)
    assert robot.services == ['stop']


def test_paused_time_does_not_count_toward_timeout(robot):
    robot.busy_polls = 5
    robot.cfg['cell']['motion']['move_timeout_s'] = 0.05
    _later(0.002, motion.pause)
    _later(0.15, motion.resume)                                     # 상한(0.05 s)보다 오래 서 있어도
    motion.move_joint_rel(5, 10)                                    # 시간 초과가 아니다
    assert robot.left == 0


def test_missing_timeout_value_means_no_motion(robot):
    robot.cfg['cell']['motion']['move_timeout_s'] = None
    with pytest.raises(KeyError, match='cell.motion.move_timeout_s'):
        motion.move_joint_rel(5, 10)
    assert robot.calls == []
