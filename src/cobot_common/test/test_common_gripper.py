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
    """보낸 문자열을 기록한다.

    `fail_at = N` 이면 **N번째 호출만** 실패 응답을 준다(1부터 센다). 명령은 `sent` 에 남는다 —
    "보내기는 했는데 성공했는지 모른다" 가 실제 상황이고, 그리퍼가 이미 움직였을 수 있다.
    호출 번호는 `calls` 로 따로 센다(시험이 `sent.clear()` 를 해도 번호가 흐트러지지 않게).
    """

    def __init__(self, ok=True, fail_at=None):
        self.sent = []
        self.calls = 0
        self._ok = ok
        self.fail_at = fail_at

    def wait_for_service(self, timeout_sec=None):
        return True

    def call(self, req):
        self.sent.append(req.command)
        self.calls += 1
        if self.fail_at is not None and self.calls == self.fail_at:
            return FakeRes(False, f'가짜 실패({self.fail_at}번째 명령)')
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


# ────────────────────────────────── 🚨 기억(_force_n)과 실제 힘이 어긋나면 안 된다
def test_set_force_updates_memory_after_each_command(fake, monkeypatch):
    """명령 한 번마다 기억을 갱신한다 — 계단마다 한 칸씩 따라 올라가야 한다.

    마지막에 한꺼번에 갱신하면 중간에 끊겼을 때 실제 힘과 기억이 갈라진다.
    """
    seen = []
    real_call = fake.client.call

    def spy(req):
        seen.append(G._force_n)                        # 이 명령을 보내기 **직전** 의 기억
        return real_call(req)

    monkeypatch.setattr(fake.client, 'call', spy)
    monkeypatch.setattr(G, '_force_n', 0.0)
    G._set_force(10.0)                                 # 0 → 10 N = 'i' 4계단
    assert seen == [0.0, 2.5, 5.0, 7.5], f'계단마다 갱신하지 않았다 — {seen}'
    assert G._force_n == pytest.approx(10.0)


def test_set_force_failure_midway_does_not_keep_stale_memory(fake, monkeypatch):
    """🚨 도중에 실패하면 기억은 **실제와 맞거나 없어야(None)** 한다.

    재현(9/20 감사): 3번째 'i' 에서 실패 → 실제는 5.0~7.5 N 인데 0.0 N 으로 기억하고 있었다.
    그러면 다음부터 힘이 계속 어긋나, NORMAL 인 줄 알고 약하게 쥐어 이송 중 낙하가 된다(SDD §8).
    """
    monkeypatch.setattr(G, '_force_n', 0.0)
    fake.client.fail_at = 3
    with pytest.raises(RuntimeError, match='그리퍼 명령'):
        G._set_force(20.0)                             # 0 → 20 N = 'i' 8계단, 3번째에서 끊긴다
    done = fake.client.sent.count('i') - 1             # 앞 2계단은 확실히 들어갔다
    low = done * G._FORCE_STEP_N                       # 5.0 N
    high = (done + 1) * G._FORCE_STEP_N                # 7.5 N — 실패한 명령이 닿았을 수도 있다
    assert G._force_n is None or low - 0.01 <= G._force_n <= high + 0.01, (
        f'기억 {G._force_n} N 이 실제(≈{low}~{high} N)와 어긋난다')


def test_memory_dropped_after_failure_keeps_protections_working(fake, monkeypatch):
    """기억을 버렸으니 9/20 보호가 그대로 작동한다 — grip_level 거부 · release 에서 다시 맞추기.

    옛 코드는 여기서 '기억 10 N / 실제 17.5 N' 로 조용히 이어 갔다.
    """
    monkeypatch.setattr(G, '_force_n', 0.0)
    monkeypatch.setattr(G, '_joint_angle', 0.83)
    fake.client.fail_at = 3
    with pytest.raises(RuntimeError, match='그리퍼 명령'):
        G._set_force(20.0)
    assert G._force_n is None, '실패한 뒤에 기억이 남으면 다음 보호가 안 걸린다'

    fake.client.fail_at = None
    fake.client.sent.clear()
    with pytest.raises(RuntimeError, match='기준'):
        G.grip_level('BOWL', 'NORMAL')                 # 쥔 채 힘 바꾸기 → 거부
    assert fake.client.sent == [], '거부했으면 아무 명령도 안 보낸다'

    G.release()                                        # 빈손이 확실한 자리에서 다시 맞춘다
    assert fake.client.sent[0] == 'o', '열기가 맨 먼저여야 한다'
    assert fake.client.sent.count('d') >= 16
    assert G._force_n == pytest.approx(0.0)


def test_anchor_force_failure_midway_leaves_no_memory(fake, monkeypatch):
    """🚨 기준 맞추기가 중간에 끊기면 0.0 N 으로도, 옛 값으로도 단정하지 않는다.

    'd' 를 17회 다 보내야 0 N 이다 — 3번째에서 끊기면 실제로는 덜 내려가 있다.
    """
    monkeypatch.setattr(G, '_force_n', 20.0)           # 옛 기억이 남아 있어도
    fake.client.fail_at = 3
    with pytest.raises(RuntimeError, match='그리퍼 명령'):
        G._anchor_force()
    assert G._force_n is None, '덜 내려갔는데 0.0 N 이나 옛 값으로 단정하면 안 된다'
