"""가짜 모듈 시험 (INF-03 완료 기준) — 🚨 로봇·ROS 없이 돈다.

완료 기준: cobot_api.check_api 통과 · 실패 주입 동작
"""
import pytest

from cobot_api import (F1Api, F2Api, F3Api, LeftoverResult, PickResult, PlaceResult,
                       Result, SEAT_FAIL, RACK_JAM, ToolResult, WeighResult,
                       WipeBowlResult, WipeCupResult, check_api)
from f2_sense_flow.mock import code_for, configure, parse_fail_on, reset
from f2_sense_flow.mock import mock_f1, mock_f2, mock_f3


@pytest.fixture(autouse=True)
def _clean():
    configure([])          # 설정을 읽지 않게 빈 규칙으로 고정
    yield
    reset()


# ────────────────────────────────── 약속 일치 (INF-03 완료 기준)
def test_mocks_match_api():
    assert check_api(mock_f1, F1Api) == []
    assert check_api(mock_f2, F2Api) == []
    assert check_api(mock_f3, F3Api) == []


def test_return_types():
    assert isinstance(mock_f1.pick('RET_B', 'BOWL'), PickResult)
    assert isinstance(mock_f1.place('SPONGE_BED_B'), PlaceResult)
    assert isinstance(mock_f1.tool('SPONGE', 'PICK'), ToolResult)
    assert isinstance(mock_f1.move_to('HOME', False), Result)
    assert isinstance(mock_f1.rack_place('RACK_B1', 'BOWL'), Result)
    assert isinstance(mock_f2.weigh('BOWL'), WeighResult)
    assert isinstance(mock_f2.leftover_loop('BOWL', 2), LeftoverResult)
    assert isinstance(mock_f3.wipe_bowl(), WipeBowlResult)
    assert isinstance(mock_f3.wipe_cup(), WipeCupResult)


def test_all_ok_without_injection():
    assert mock_f1.pick('RET_B', 'BOWL').ok
    assert mock_f2.weigh('CUP').ok
    assert mock_f3.soap(3).ok


# ────────────────────────────────── 실패 주입
def test_fail_on_always():
    configure(['place:SEAT_FAIL'])
    for _ in range(3):                                  # 횟수를 안 주면 매번 실패
        r = mock_f1.place('SPONGE_BED_B')
        assert not r.ok and r.code == SEAT_FAIL
    assert mock_f1.pick('RET_B', 'BOWL').ok             # 다른 함수는 멀쩡


def test_fail_on_n_times_then_ok():
    """재시도 정책(retry:1->isolate)을 시험하려면 "한 번만 실패" 가 필요하다."""
    configure(['rack_place:RACK_JAM:1'])
    assert mock_f1.rack_place('RACK_B1', 'BOWL').code == RACK_JAM
    assert mock_f1.rack_place('RACK_B1', 'BOWL').ok     # 두 번째부터 성공


def test_parse_fail_on():
    assert parse_fail_on(['place:SEAT_FAIL']) == {'place': ['SEAT_FAIL', None]}
    assert parse_fail_on(['tool:TOOL_FAIL:2']) == {'tool': ['TOOL_FAIL', 2]}
    assert parse_fail_on([]) == {}


def test_bad_fail_on_raises():
    """형식이 틀리면 조용히 넘어가지 않고 알려 준다."""
    for bad in ('place', 'a:b:c:d', ''):
        with pytest.raises(ValueError):
            parse_fail_on([bad])


def test_code_for_unknown_is_none():
    configure(['place:SEAT_FAIL'])
    assert code_for('아무거나') is None
