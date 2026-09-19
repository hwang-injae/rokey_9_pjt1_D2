"""F2 함수가 cobot_api 의 약속(F2Api)과 같은지 자동으로 지킨다 (PKG-01 완료 기준).

손으로 확인하면 나중에 누가 인자를 바꿔도 모른다. colcon test 가 계속 지켜 준다.
"""
from cobot_api import F2Api, LeftoverResult, Result, WeighResult, check_api
from f2_sense_flow import sense


def test_sense_matches_f2api():
    assert check_api(sense, F2Api) == []


def test_return_types():
    assert isinstance(sense.weigh('BOWL'), WeighResult)
    assert isinstance(sense.leftover_loop('BOWL', 2), LeftoverResult)
    assert isinstance(sense.shake('WASTE', 4, 'BOWL'), Result)
    assert isinstance(sense.dip('RINSE', 1, 'CUP'), Result)


def test_results_default_ok():
    """껍데기 단계에서는 전부 ok=True · code='OK' 여야 한다."""
    for r in (sense.weigh('BOWL'), sense.leftover_loop('CUP', 1),
              sense.shake('RINSE', 3, 'CUP'), sense.dip('RINSE', 1, 'BOWL')):
        assert r.ok and r.code == 'OK'
