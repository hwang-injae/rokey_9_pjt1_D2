"""flow(두뇌) 시험 — 🚨 로봇·브링업·ROS 없이 돈다.

flow.py 가 ROS 를 import 하지 않게 나눠 둔 덕분이다(SDD 산출물 분리).
TC-10(실패 정책)의 바탕이 된다.
"""
import pytest

from cobot_api import (EMPTY_ZONE, FORCE_LIMIT, OK, RACK_FULL, ROBOT_ERROR, SEAT_FAIL,
                       TIMEOUT, Result)
from f2_sense_flow.flow import ISOLATE, NEXT_ZONE, PAUSE, RETRY, Flow, Signals


class FakeLog:
    def __init__(self):
        self.lines = []

    def info(self, m):
        self.lines.append(('info', m))

    def warn(self, m):
        self.lines.append(('warn', m))

    def error(self, m):
        self.lines.append(('error', m))


CFG = {'flow': {
    'plan': [{'zone': 'RET_B', 'kind': 'BOWL', 'count': 2},
             {'zone': 'RET_C', 'kind': 'CUP', 'count': 2}],
    'policy': {'EMPTY_ZONE': 'next_zone', 'SEAT_FAIL': 'isolate', 'RACK_FULL': 'pause',
               'FORCE_LIMIT': 'retry:1->isolate', 'TIMEOUT': 'retry:3->isolate'},
    'step_delay_s': 0.0,
}}


@pytest.fixture
def flow():
    return Flow(CFG, FakeLog())


# ────────────────────────────────── 실패 정책
def test_policy_from_yaml(flow):
    assert flow.policy_for(EMPTY_ZONE) == (NEXT_ZONE, 0)
    assert flow.policy_for(SEAT_FAIL) == (ISOLATE, 0)
    assert flow.policy_for(RACK_FULL) == (PAUSE, 0)


def test_retry_policy_parses_count(flow):
    """params.yaml 형식 "retry:N->isolate" 를 (RETRY, N) 으로 읽는다 (SDD §4.3)."""
    assert flow.policy_for(FORCE_LIMIT) == (RETRY, 1)
    assert flow.policy_for(TIMEOUT) == (RETRY, 3)


def test_unknown_code_is_pause(flow):
    """모르는 코드는 **안전하게 멈춘다**. 조용히 넘어가면 안 된다."""
    assert flow.policy_for('아무거나') == (PAUSE, 0)
    assert any('pause' in m for _, m in flow.log.lines)


def test_bad_policy_value_is_pause():
    """오타·형식 오류도 멈춘다. retry 형식이 살짝 틀려도 그냥 넘어가면 안 된다."""
    for bad in ('오타난값', 'retry:1', 'retry->isolate', 'retry:x->isolate'):
        f = Flow({'flow': {'policy': {'SEAT_FAIL': bad}}}, FakeLog())
        assert f.policy_for(SEAT_FAIL) == (PAUSE, 0), bad


# ────────────────────────────────── 예외 보호 (SDD §5.1)
def test_call_returns_result_on_success(flow):
    r = flow.call(lambda: Result())
    assert r.ok and r.code == OK and flow.last_code == OK


def test_call_converts_exception_to_result(flow):
    """예외가 나도 None 이 아니라 Result.fail(ROBOT_ERROR) 를 돌려준다."""
    retreated = []
    f = Flow(CFG, FakeLog(), safe_retreat=lambda: retreated.append(1))

    def 터지는함수():
        raise RuntimeError('드라이버 응답 없음')

    r = f.call(터지는함수)
    assert r is not None                       # 🚨 None 이면 호출부가 매번 분기해야 한다
    assert not r.ok and r.code == ROBOT_ERROR
    assert retreated == [1]                    # 안전 자세로 물러났다
    assert '터지는함수' in f.message


def test_call_does_not_crash_the_cell(flow):
    """함수 하나의 예외가 셀 전체를 멈추면 안 된다 — 다음 호출이 정상이어야 한다."""
    flow.call(lambda: 1 / 0)
    assert flow.call(lambda: Result()).ok


# ────────────────────────────────── 상태
def test_snapshot_has_all_flowstate_fields(flow):
    """FlowState.msg 의 13개 필드가 빠짐없이 있어야 HMI 가 안 깨진다."""
    s = flow.snapshot()
    for k in ('step', 'kind', 'zone_id', 'done_bowl', 'done_cup', 'isolated',
              'target_bowl', 'target_cup', 'sponge_uses', 'soap_dips', 'rinse_dips',
              'last_code', 'message'):
        assert k in s


def test_targets_from_plan(flow):
    assert flow.target_bowl == 2 and flow.target_cup == 2


def test_paused_remembers_previous_step(flow):
    flow.step = 'WEIGH'
    flow.to_paused()
    assert flow.step == 'PAUSED' and flow._prev_step == 'WEIGH'


# ────────────────────────────────── 깃발
def test_signal_take_clears_once():
    sig = Signals()
    sig.raise_('start')
    assert sig.take('start') is True
    assert sig.take('start') is False          # 한 번만 반응한다


def test_signal_peek_keeps():
    sig = Signals()
    sig.raise_('stop')
    assert sig.peek('stop') and sig.peek('stop')
    sig.clear('stop')
    assert not sig.peek('stop')
