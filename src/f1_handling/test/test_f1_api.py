"""F1 골격 시험 — 로봇 없이 돈다.  실행: python3 -m pytest -q src/f1_handling
파일 이름에 패키지 이름을 넣는다(CONTRIBUTING — 같은 이름이 두 패키지에 있으면 한 번에 돌릴 때 수집이 깨진다)."""
from cobot_api import F1Api, PickResult, Result, ToolResult, check_api
from f1_handling import handling


def test_handling_matches_f1api():
    assert check_api(handling, F1Api) == []


def test_return_types_of_skeleton_functions():
    """아직 골격인 함수(🚧 pick · tool · rack_place)는 약속된 타입만 돌려준다. move_to · place 는 test_f1_handling.py."""
    assert isinstance(handling.pick('RET_B', 'BOWL'), PickResult)
    assert isinstance(handling.tool('SPONGE', 'PICK'), ToolResult)
    assert type(handling.rack_place('RACK_B1', 'BOWL')) is Result


def test_skeleton_returns_ok():
    """골격은 전부 ok=True · code='OK' 를 돌려준다 — V-20 에서 flow 가 끝까지 돌 수 있게."""
    results = [handling.pick('RET_C', 'CUP'), handling.tool('BRUSH', 'RETURN'), handling.rack_place('RACK_C2', 'CUP')]
    assert all(r.ok and r.code == 'OK' for r in results)
