"""F1 골격 시험 — 로봇 없이 돈다.  실행: python3 -m pytest -q src/f1_handling
파일 이름에 패키지 이름을 넣는다(CONTRIBUTING — 같은 이름이 두 패키지에 있으면 한 번에 돌릴 때 수집이 깨진다)."""
from cobot_api import F1Api, PickResult, PlaceResult, Result, ToolResult, check_api
from f1_handling import handling


def test_handling_matches_f1api():
    assert check_api(handling, F1Api) == []


def test_return_types():
    assert isinstance(handling.pick('RET_B', 'BOWL'), PickResult)
    assert isinstance(handling.place('SPONGE_BED_B'), PlaceResult)
    assert type(handling.move_to('HOME', False)) is Result
    assert isinstance(handling.tool('SPONGE', 'PICK'), ToolResult)
    assert type(handling.rack_place('RACK_B1', 'BOWL')) is Result


def test_skeleton_returns_ok():
    """골격은 전부 ok=True · code='OK' 를 돌려준다 — V-20 에서 flow 가 끝까지 돌 수 있게."""
    results = [handling.pick('RET_C', 'CUP'), handling.place('WEIGH'), handling.move_to('WEIGH', True),
               handling.tool('BRUSH', 'RETURN'), handling.rack_place('RACK_C4', 'CUP')]
    assert all(r.ok and r.code == 'OK' for r in results)
