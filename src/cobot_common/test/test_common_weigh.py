"""cobot_common.weigh 시험 (INF-02c) — 🚨 로봇 없이 돈다.

두산 API(dsr())와 로거를 가짜로 바꿔 넣고 계산·거르기만 확인한다.
실기 확인(100/200 g 추, 연속 3회)은 V-02 와 한 세션에서 한다.
"""
import importlib
import sys
import types

import pytest

# 🚨 `from cobot_common import weigh` 는 **함수**를 준다 — __init__.py 의 `from .weigh import *`
#    가 함수 이름을 패키지에 올려 모듈 이름을 가린다(모듈과 함수 이름이 같아서).
#    모듈을 얻으려면 importlib 를 쓴다.
W = importlib.import_module('cobot_common.weigh')


class FakeLog:
    def __init__(self):
        self.lines = []

    def info(self, m):
        self.lines.append(('info', m))

    def warn(self, m):
        self.lines.append(('warn', m))

    def error(self, m):
        self.lines.append(('error', m))


class FakeDsr:
    """get_workpiece_weight 가 미리 정한 값을 차례로 돌려준다.

    🚨 값은 **g 로 적고** API 처럼 kg 으로 돌려준다(÷ 1000) — 시험이 g 로 읽히게. 음수·예외는 그대로.
    """

    def __init__(self, values, reset_raises=False, reset_delay=0.0):
        self.values = list(values)
        self.reset_calls = 0
        self._reset_raises = reset_raises
        self._reset_delay = reset_delay

    def get_workpiece_weight(self):
        if not self.values:
            raise RuntimeError('값이 더 없다')
        v = self.values.pop(0)
        if isinstance(v, Exception):
            raise v
        return v / 1000.0 if v >= 0 else v          # kg 으로 (실패 신호 -1 은 그대로)

    def reset_workpiece_weight(self):
        self.reset_calls += 1
        if self._reset_raises:
            raise RuntimeError('컨트롤러가 응답하지 않는다')
        if self._reset_delay:
            import time
            time.sleep(self._reset_delay)


@pytest.fixture
def fake(monkeypatch):
    """bootstrap 의 dsr·cfg·io_node 를 가짜로 바꾼다."""
    log = FakeLog()
    state = {}

    def install(dsr_obj, conf=None):
        state['dsr'] = dsr_obj
        boot = types.ModuleType('cobot_common.bootstrap')
        boot.dsr = lambda: dsr_obj
        boot.cfg = lambda: conf or {}
        boot.io_node = lambda: types.SimpleNamespace(get_logger=lambda: log)
        monkeypatch.setitem(sys.modules, 'cobot_common.bootstrap', boot)
        return log

    return install


# ────────────────────────────────── 🚨 단위 — API 는 kg, 우리는 g (9/21 실기)
def test_kg_from_api_becomes_g(fake):
    """9/21 첫 실기: 그릇 쥔 채 0.0684 · 빈손 0.0239 (kg). g 로 안 바꾸면 '0 g' 으로 보여 GRIP_FAIL 이 난다."""
    fake(FakeDsr([68.4]))                            # FakeDsr 이 0.0684 로 돌려준다
    assert W.weigh(1) == pytest.approx(68.4)
    fake(FakeDsr([23.9]))
    assert W.weigh(1) == pytest.approx(23.9)


# ────────────────────────────────── 중앙값
def test_median_ignores_one_wild_value(fake):
    """🚨 핵심 — 한 번 크게 튀어도 끌려가지 않는다.

    V-02 에서 200 g 추가 40.8 g 폭으로 흔들렸다. 평균이면 튄 값에 끌려간다.
    """
    log = fake(FakeDsr([220.0, 221.0, 500.0, 222.0, 223.0]))   # 500 이 튄 값
    g = W.weigh(5)
    assert g == 222.0                       # 평균이면 277.2 가 된다
    assert 220.0 < g < 224.0


def test_median_even_count(fake):
    fake(FakeDsr([100.0, 200.0]))
    assert W.weigh(2) == 150.0


def test_single_sample(fake):
    fake(FakeDsr([181.5]))
    assert W.weigh(1) == 181.5


# ────────────────────────────────── 🚨 음수 = 실패 신호
def test_negative_is_dropped(fake):
    """API 는 실패를 음수(-1)로 알려 준다 — 계산에 섞이면 안 된다."""
    log = fake(FakeDsr([220.0, -1.0, 222.0, -1.0, 224.0]))
    g = W.weigh(5)
    assert g == 222.0                       # 음수를 섞으면 133 쯤이 된다
    assert sum(1 for lv, _ in log.lines if lv == 'warn') >= 2


def test_all_failed_raises(fake):
    """하나도 못 읽으면 숫자를 지어내지 않고 예외를 던진다.

    숫자 하나로는 '0 g' 과 '실패' 를 구분할 수 없다.
    """
    fake(FakeDsr([-1.0, -1.0, -1.0]))
    with pytest.raises(RuntimeError, match='읽지 못했다'):
        W.weigh(3)


def test_exception_in_one_call_continues(fake):
    """한 번 예외가 나도 나머지로 이어 간다."""
    fake(FakeDsr([220.0, RuntimeError('일시 실패'), 222.0]))
    assert W.weigh(3) == 221.0


# ────────────────────────────────── 🚨 reset 은 위험하다 (TS-03)
def test_reset_not_called_unless_asked(fake):
    """🚨 기본은 0점 재설정을 하지 않는다 — TS-03 에서 컨트롤러가 전부 멈췄다."""
    d = FakeDsr([200.0])
    fake(d)
    W.weigh(1)
    assert d.reset_calls == 0


def test_reset_called_once_when_asked(fake):
    d = FakeDsr([200.0])
    fake(d)
    W.weigh(1, reset=True)
    assert d.reset_calls == 1


def test_reset_failure_does_not_stop_measurement(fake):
    """🚨 reset 이 터져도 측정은 계속한다. 그리고 다시 부르지 않는다."""
    d = FakeDsr([200.0, 201.0, 202.0], reset_raises=True)
    log = fake(d)
    g = W.weigh(3, reset=True)
    assert g == 201.0                       # 측정은 됐다
    assert d.reset_calls == 1               # 한 번만 불렀다
    assert any('0점 재설정 실패' in m for _, m in log.lines)


# ────────────────────────────────── 기록
def test_individual_values_are_logged(fake):
    """V-02 에서 회차 값을 안 남겨 평균·표준편차를 못 냈다 — 개별 값을 남긴다."""
    log = fake(FakeDsr([220.0, 221.0, 222.0]))
    W.weigh(3)
    info = [m for lv, m in log.lines if lv == 'info']
    assert any('220.0' in m and '221.0' in m and '222.0' in m for m in info)
