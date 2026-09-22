"""F1 골격 시험 — 로봇 없이 돈다.  실행: python3 -m pytest -q src/f1_handling
파일 이름에 패키지 이름을 넣는다(CONTRIBUTING — 같은 이름이 두 패키지에 있으면 한 번에 돌릴 때 수집이 깨진다)."""
from cobot_api import F1Api, PickResult, Result, ToolResult, check_api
from f1_handling import handling


def test_handling_matches_f1api():
    assert check_api(handling, F1Api) == []


def test_return_types_of_skeleton_functions():
    """아직 골격인 함수(🚧 tool)는 약속된 타입만 돌려준다. pick · rack_place 는 9/22 구현 → test_f1_pick_rack.py."""
    assert isinstance(handling.tool('SPONGE', 'PICK'), ToolResult)


def test_skeleton_returns_ok():
    """골격은 ok=True · code='OK' 를 돌려준다 — V-20 에서 flow 가 끝까지 돌 수 있게."""
    assert handling.tool('BRUSH', 'RETURN').ok
