"""cobot_common.gripper 시험 (INF-02d) — 🚨 로봇 없이 돈다.

드라이버 서비스·토픽을 가짜로 바꿔 넣고, 보낸 명령 문자열과 환산만 확인한다.
실기 확인은 V-05·V-23(파지 힘 전환 10회)에서.
"""
import importlib
import sys
import types

import pytest

# 모듈 이름이 함수 이름과 겹치지 않지만, weigh 와 같은 방식으로 모듈을 직접 얻는다
G = importlib.import_module('cobot_common.gripper')


class FakeLog:
    def __init__(self):
        self.lines = []

    def info(self, m):
        self.lines.append(('info', m))

    def warn(self, m):
        self.lines.append(('warn', m))

    def error(self, m):
        self.lines.append(('error', m))


class FakeRes:
    def __init__(self, ok=True, message=''):
        self.success, self.message = ok, message


class FakeClient:
    """보낸 문자열을 기록한다."""

    def __init__(self, ok=True):
        self.sent = []
        self._ok = ok

    def wait_for_service(self, timeout_sec=None):
        return True

    def call(self, req):
        self.sent.append(req.command)
        return FakeRes(self._ok, '' if self._ok else '가짜 실패')


@pytest.fixture(autouse=True)
def fake(monkeypatch):
    """드라이버 srv 타입·bootstrap·상태를 가짜로."""
    log = FakeLog()

    srv_mod = types.ModuleType('onrobot_rg_msgs.srv')
    srv_mod.SetCommand = types.SimpleNamespace(
        Request=lambda: types.SimpleNamespace(command=''))
    monkeypatch.setitem(sys.modules, 'onrobot_rg_msgs', types.ModuleType('onrobot_rg_msgs'))
    monkeypatch.setitem(sys.modules, 'onrobot_rg_msgs.srv', srv_mod)

    boot = types.ModuleType('cobot_common.bootstrap')
    boot.cfg = lambda: FAKE_CFG
    boot.io_node = lambda: types.SimpleNamespace(get_logger=lambda: log)
    monkeypatch.setitem(sys.modules, 'cobot_common.bootstrap', boot)

    client = FakeClient()
    monkeypatch.setattr(G, '_client', client)
    monkeypatch.setattr(G, '_force_n', None)
    monkeypatch.setattr(G, '_joint_angle', None)
    monkeypatch.setattr(G, '_effort', 0.0)            # 항상 '멈춤' 으로 둬서 대기가 안 걸리게
    return types.SimpleNamespace(client=client, log=log)


FAKE_CFG = {'cell': {
    'limits': {'timeout_s': 1.0},
    'presets': {
        'BOWL': {'grip_width_mm': 2.0, 'grip_force_n': 20, 'hold_force_n': 35},
        'CUP': {'grip_width_mm': 70.0, 'grip_force_n': 15, 'hold_force_n': 30},
    },
}}


# ────────────────────────────────── 폭 환산 (드라이버 식과 같아야 한다)
@pytest.mark.parametrize('mm', [0.0, 2.0, 5.0, 20.0, 62.0, 70.0, 110.0])
def test_width_conversion_round_trip(monkeypatch, mm):
    """드라이버의 widthToJointValue 로 만든 관절각을 우리 식이 같은 폭으로 되돌려야 한다."""
    import numpy as np
    th = np.arccos(((mm / 1000 / 2) - G._DY - G._L1 * np.cos(G._THETA1)) / G._L3) - G._THETA3
    monkeypatch.setattr(G, '_joint_angle', float(th))
    assert G.grip_width() == pytest.approx(mm, abs=0.01)


def test_width_before_first_message_raises():
    """아직 한 번도 못 받았으면 지어내지 않고 알려 준다."""
    with pytest.raises(RuntimeError, match='관절각'):
        G.grip_width()


# ────────────────────────────────── 🚨 힘은 2.5 N 계단 (드라이버 제약)
def test_grip_anchors_force_on_first_call(fake, monkeypatch):
    """드라이버가 현재 힘을 안 알려 준다 → grip 은 **잡으러 가기 전(빈손)** 에 기준을 맞춘다."""
    monkeypatch.setattr(G, '_joint_angle', 0.83)
    G.grip(2.0, 20.0)
    sent = fake.client.sent
    assert sent.count('d') >= 16, '0 N 까지 내리는 계단이 부족하다'
    assert sent.count('i') == 8, '0 → 20 N 은 2.5 N × 8 계단'
    assert G._force_n == pytest.approx(20.0)


def test_set_force_without_anchor_raises(fake):
    """🚨 _set_force 는 이제 몰래 0 N 으로 내리지 않는다 — 기준이 없으면 거부한다."""
    with pytest.raises(RuntimeError, match='기준'):
        G._set_force(20.0)
    assert fake.client.sent == [], '거부했으면 아무 명령도 안 보낸다'


def test_second_force_moves_only_difference(fake, monkeypatch):
    """기준이 잡힌 뒤에는 차이만큼만 움직인다."""
    monkeypatch.setattr(G, '_force_n', 20.0)
    fake.client.sent.clear()
    G._set_force(35.0)
    assert fake.client.sent == ['i'] * 6, '20 → 35 N 은 2.5 N × 6 계단'
    assert G._force_n == pytest.approx(35.0)


def test_force_down(fake, monkeypatch):
    monkeypatch.setattr(G, '_force_n', 35.0)
    fake.client.sent.clear()
    G._set_force(20.0)
    assert fake.client.sent == ['d'] * 6


def test_force_not_on_step_warns(fake, monkeypatch):
    """2.5 배수가 아니면 가장 가까운 계단 + 경고."""
    monkeypatch.setattr(G, '_force_n', 0.0)
    G._set_force(21.0)
    assert any('정확히 못 맞춘' in m for _, m in fake.log.lines)


def test_force_clamped_to_max(fake, monkeypatch):
    monkeypatch.setattr(G, '_force_n', 0.0)
    G._set_force(999.0)
    assert G._force_n <= G._MAX_FORCE_N


# ────────────────────────────────── 명령 문자열
def test_grip_sends_width_in_tenths(fake, monkeypatch):
    """폭은 0.1 mm 단위 정수 문자열이다 — 62.0 mm → '620'."""
    monkeypatch.setattr(G, '_force_n', 20.0)
    monkeypatch.setattr(G, '_joint_angle', 0.26)
    fake.client.sent.clear()
    G.grip(62.0, 20.0)
    assert '620' in fake.client.sent


def test_release_sends_open(fake, monkeypatch):
    """기준이 이미 잡혀 있으면 release 는 열기만 한다."""
    monkeypatch.setattr(G, '_force_n', 20.0)
    G.release()
    assert fake.client.sent == ['o']


def test_release_anchors_force_after_opening(fake):
    """🚨 기준이 없으면 release 가 맞춘다 — 반드시 **연 뒤에**(쥔 채 0 N 으로 내리면 놓친다)."""
    G.release()
    sent = fake.client.sent
    assert sent[0] == 'o', '열기가 맨 먼저여야 한다'
    assert sent.count('d') >= 16, '0 N 까지 내리는 계단이 부족하다'
    assert G._force_n == pytest.approx(0.0)


def test_width_out_of_range_is_clamped(fake, monkeypatch):
    monkeypatch.setattr(G, '_force_n', 20.0)
    monkeypatch.setattr(G, '_joint_angle', 0.26)
    fake.client.sent.clear()
    G.grip(999.0, 20.0)
    assert '1100' in fake.client.sent                  # max_width 110.0 mm
    assert any('범위' in m for _, m in fake.log.lines)


# ────────────────────────────────── grip_level (털기·담금이 쓴다)
def test_grip_level_uses_preset_force(fake, monkeypatch):
    """HOLD 는 프리셋의 hold_force_n 을 쓴다. 폭은 다시 명령하지 않는다."""
    monkeypatch.setattr(G, '_force_n', 20.0)
    monkeypatch.setattr(G, '_joint_angle', 0.83)
    fake.client.sent.clear()
    G.grip_level('BOWL', 'HOLD')                        # 20 → 35 N
    assert fake.client.sent == ['i'] * 6
    assert not any(c.isdigit() for c in fake.client.sent), '폭을 다시 명령하면 안 된다'


def test_grip_level_back_to_normal(fake, monkeypatch):
    monkeypatch.setattr(G, '_force_n', 35.0)
    monkeypatch.setattr(G, '_joint_angle', 0.83)
    fake.client.sent.clear()
    G.grip_level('CUP', 'NORMAL')                       # 35 → 15 N
    assert fake.client.sent == ['d'] * 8


def test_grip_level_without_anchor_refuses(fake, monkeypatch):
    """🚨 쥔 채 힘을 바꾸려는데 기준이 없으면 거부한다 — 맞추려면 0 N 을 지나야 해서 놓친다.

    PM 9/20 · #17 검토 2번. 조용히 떨어뜨리는 대신 예외 → flow 가 ROBOT_ERROR 로 멈춘다.
    """
    monkeypatch.setattr(G, '_joint_angle', 0.83)
    with pytest.raises(RuntimeError, match='기준'):
        G.grip_level('BOWL', 'HOLD')
    assert fake.client.sent == [], '거부했으면 아무 명령도 안 보낸다'


def test_grip_level_bad_level(fake):
    with pytest.raises(ValueError, match='NORMAL'):
        G.grip_level('BOWL', '세게')


def test_grip_level_unknown_kind(fake, monkeypatch):
    monkeypatch.setattr(G, '_joint_angle', 0.83)
    with pytest.raises(KeyError, match='SPOON'):
        G.grip_level('SPOON', 'HOLD')


# ────────────────────────────────── 실패
def test_service_failure_raises(fake, monkeypatch):
    monkeypatch.setattr(G, '_force_n', 20.0)
    fake.client._ok = False
    with pytest.raises(RuntimeError, match='그리퍼 명령'):
        G.release()


def test_no_client_raises(monkeypatch):
    monkeypatch.setattr(G, '_client', None)
    with pytest.raises(RuntimeError, match='init'):
        G.release()
