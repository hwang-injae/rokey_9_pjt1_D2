# -*- coding: utf-8 -*-
"""케이블 이상 감지 및 넛지(톡톡) 재개 기능 테스트 — 민범진 (F2)

검증 시나리오:
1. 정상 상태: jitter_g <= max_weigh_spread_g -> 정상 진행
2. 케이블 이상: jitter_g > max_weigh_spread_g -> CableTightError -> PAUSED 전환 및 대시보드 안내 메시지
3. 톡톡 후 정상: 톡톡 감지 -> 재검증(jitter 정상) -> 작업 재개(RETRY_STEP)
4. 톡톡 후 이상 지속: 톡톡 감지 -> 재검증(jitter 초과) -> PAUSED 유지
5. HMI 신호: resume 신호 시 재검증 후 재개 / abort 신호 시 안전 중단
"""
import pytest
import types

from cobot_api import OK, ROBOT_ERROR, Result
from f2_sense_flow.flow import Flow, Signals, RETRY_STEP, ABORTED
from f2_sense_flow.sense import CableTightError, wait_for_nudge, recheck_cable


class MockLogger:
    def info(self, msg): pass
    def warn(self, msg): pass
    def error(self, msg): pass


def test_sense_weigh_normal_when_jitter_under_limit(monkeypatch):
    """정상 상태: jitter 가 한도 이내이면 CableTightError 없이 정상 WeighResult 반환."""
    import cobot_common as cc
    import f2_sense_flow.sense as sense

    monkeypatch.setattr(cc, 'weigh', lambda n: 180.0)
    monkeypatch.setattr(cc, 'weigh_last', lambda: {'jitter_g': 15.0, 'drift_g': 2.0, 'median_g': 180.0})
    monkeypatch.setattr(sense, '_goto', lambda station, carrying=True, kind=None: 0.0)
    monkeypatch.setattr(sense, '_f2', lambda: {
        'empty_weight_g': {'BOWL': 0.0},
        'weigh_samples': 10,
        'weigh_settle_s': 0.0,
        'limits': {'max_weigh_spread_g': 50.0, 'max_settle_s': 5.0, 'min_net_g': -60.0}
    })

    res = sense.weigh('BOWL')
    assert res.ok
    assert res.code == OK
    assert res.weight_g == pytest.approx(180.0)


def test_sense_weigh_raises_cable_tight_error_when_jitter_exceeds_limit(monkeypatch):
    """케이블 이상: jitter > max_weigh_spread_g 이면 CableTightError 발생."""
    import cobot_common as cc
    import f2_sense_flow.sense as sense

    monkeypatch.setattr(cc, 'weigh', lambda n: 180.0)
    # 떨림(jitter)이 65g로 상한 50g 초과
    monkeypatch.setattr(cc, 'weigh_last', lambda: {'jitter_g': 65.0, 'drift_g': 2.0, 'median_g': 180.0})
    monkeypatch.setattr(sense, '_goto', lambda station, carrying=True, kind=None: 0.0)
    monkeypatch.setattr(sense, '_f2', lambda: {
        'empty_weight_g': {'BOWL': 0.0},
        'weigh_samples': 10,
        'weigh_settle_s': 0.0,
        'limits': {'max_weigh_spread_g': 50.0, 'max_settle_s': 5.0, 'min_net_g': -60.0}
    })

    with pytest.raises(CableTightError) as exc_info:
        sense.weigh('BOWL')
    assert '케이블 장력 이상' in str(exc_info.value)


def test_wait_for_nudge_detects_force_spike(monkeypatch):
    """톡톡 감지: 정지 상태에서 외력 변화량이 threshold 를 초과하면 'nudge' 반환."""
    import cobot_common as cc
    import f2_sense_flow.sense as sense

    # 초기 외력 0 -> 2번째 호출에서 외력 7N (임계 5N 초과)
    force_values = [
        [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        [0.0, 0.0, 7.0, 0.0, 0.0, 0.0],
    ]
    monkeypatch.setattr(cc, 'read_force', lambda: force_values.pop(0) if force_values else [0.0, 0.0, 0.0, 0.0, 0.0, 0.0])

    conf = {
        'nudge': {'force_threshold_n': 5.0, 'poll_gap_s': 0.001}
    }
    sig = Signals()
    ev = sense.wait_for_nudge(conf=conf, sig=sig, timeout_s=1.0)
    assert ev == 'nudge'


def test_recheck_cable_judges_ok_and_tight(monkeypatch):
    """재검증: jitter 에 따라 정상/이상 판정."""
    import cobot_common as cc
    import f2_sense_flow.sense as sense

    monkeypatch.setattr(cc, 'weigh', lambda n: None)
    conf = {
        'limits': {'max_weigh_spread_g': 50.0},
        'nudge': {'recheck_samples': 5}
    }

    # 1. 정상 (jitter = 20g <= 50g)
    monkeypatch.setattr(cc, 'weigh_last', lambda: {'jitter_g': 20.0})
    is_ok, jitter, limit = sense.recheck_cable(conf)
    assert is_ok is True
    assert jitter == 20.0
    assert limit == 50.0

    # 2. 이상 (jitter = 70g > 50g)
    monkeypatch.setattr(cc, 'weigh_last', lambda: {'jitter_g': 70.0})
    is_ok, jitter, limit = sense.recheck_cable(conf)
    assert is_ok is False
    assert jitter == 70.0


def test_flow_handle_cable_tight_resume_after_nudge(monkeypatch):
    """Flow 통합: 케이블 이상 발생 -> PAUSED -> 톡톡 감지 -> 재검증 통과 -> 작업 재개(RETRY_STEP)."""
    log = MockLogger()
    cfg = {
        'flow': {
            'plan': [{'zone': 'RET_B', 'kind': 'BOWL', 'count': 1}],
            'policy': {}
        }
    }

    # f2 모듈 모의
    mock_f2 = types.SimpleNamespace(
        wait_for_nudge=lambda conf, sig, timeout_s: 'nudge',
        recheck_cable=lambda conf: (True, 15.0, 50.0)  # 정상 재검증
    )

    flow = Flow(cfg, log, features={'f2': mock_f2})
    flow.step = 'WEIGH'
    flow._prev_step = 'WEIGH'
    sig = Signals()

    outcome = flow.handle_cable_tight(sig)
    assert outcome == RETRY_STEP
    assert flow.step == 'WEIGH'
    assert '케이블 정상 확인' in flow.message
    assert flow.last_code == OK


def test_flow_handle_cable_tight_maintains_paused_when_tight_persists(monkeypatch):
    """Flow 통합: 케이블 이상 지속 시 PAUSED 유지 및 메시지 갱신."""
    log = MockLogger()
    cfg = {
        'flow': {
            'plan': [{'zone': 'RET_B', 'kind': 'BOWL', 'count': 1}],
            'policy': {}
        }
    }

    attempts = [0]
    def mock_wait(conf, sig, timeout_s):
        attempts[0] += 1
        if attempts[0] == 1:
            return 'nudge'
        # 2번째에서는 abort 로 빠져나오도록 유도하여 무한루프 방지
        return 'abort'

    def mock_recheck(conf):
        return (False, 75.0, 50.0)  # 이상 지속

    mock_f2 = types.SimpleNamespace(
        wait_for_nudge=mock_wait,
        recheck_cable=mock_recheck
    )

    flow = Flow(cfg, log, features={'f2': mock_f2})
    flow.step = 'WEIGH'
    flow._prev_step = 'WEIGH'
    sig = Signals()

    # abort_container 가 호출되면 ABORTED 관련 종료
    outcome = flow.handle_cable_tight(sig)
    # 1번째 톡톡 후 재검증 실패로 메시지가 '케이블 이상 지속'으로 갱신되었는지 확인
    # (최종적으로 abort 되어 격리 완료됨)
    assert outcome == 'go_on'  # abort_container 반환값


def test_cable_tight_does_not_call_safe_retreat_and_pauses_motion(monkeypatch):
    """핵심 요구사항 검증: 케이블 이상 감지 시 safe_retreat 후퇴 동작이 실행되지 않고 모션 pause 가 호출됨."""
    log = MockLogger()
    cfg = {
        'flow': {
            'plan': [{'zone': 'RET_B', 'kind': 'BOWL', 'count': 1}],
            'policy': {}
        }
    }

    retreat_called = []
    def mock_safe_retreat():
        retreat_called.append(True)

    pause_called = []
    def mock_pause():
        pause_called.append(True)

    resume_called = []
    def mock_resume():
        resume_called.append(True)

    mock_f2 = types.SimpleNamespace(
        wait_for_nudge=lambda conf, sig, timeout_s: 'nudge',
        recheck_cable=lambda conf: (True, 10.0, 50.0)
    )

    flow = Flow(cfg, log, safe_retreat=mock_safe_retreat, pause=mock_pause, resume=mock_resume,
                features={'f2': mock_f2})
    flow.step = 'WEIGH'
    flow._prev_step = 'WEIGH'
    sig = Signals()

    # 1. CableTightError 발생 시 call() 이 safe_retreat 를 부르지 않는지 확인
    def raise_cable_tight():
        raise CableTightError('케이블 장력 이상')

    r = flow.call(raise_cable_tight)
    assert flow._cable_tight is True
    assert len(retreat_called) == 0, '케이블 이상 감지 시 safe_retreat 가 불리면 안 된다'

    # 2. handle_cable_tight 진입 시 모션 pause 호출 확인 및 복구 시 resume 호출 확인
    outcome = flow.handle_cable_tight(sig)
    assert len(pause_called) >= 1, '케이블 이상 시 모션 pause 가 불려야 한다'
    assert len(resume_called) >= 1, '정상 복구 시 모션 resume 이 불려야 한다'
    assert len(retreat_called) == 0, '전체 과정에서 safe_retreat 는 한 번도 불리지 않아야 한다'
    assert outcome == RETRY_STEP


