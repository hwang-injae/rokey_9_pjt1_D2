"""F1-01 move_to · 일반 place — 가짜 cobot_common 으로 로봇 없이 돈다.  실행: python3 -m pytest -q src/f1_handling

보는 것: 공용 함수를 **어떤 순서·인자로** 부르는가 · 이동이 실패하면 release 하지 않는가 · 예외를 삼키지 않는가.
"""
import pytest

from cobot_api import PlaceResult, Result
from f1_handling import handling


class MoveIncomplete(RuntimeError):
    pass


class FakeCC:
    """cobot_common 흉내 — 부른 것을 순서대로 적어 둔다."""
    MoveIncomplete = MoveIncomplete

    def __init__(self):
        self.calls = []
        self.up = {('SPONGE_BED_B', 'place'): 147.7, ('SPONGE_BED_C', 'place'): 188.2}      # 접근점 → 끝점 높이(cell.yaml 값)
        self.fail_on = None                                                                 # 이 이름의 호출에서 예외
        self.conf = {'f1': {'place_clear_mm': 100}, 'cell': {'beds': {'SPONGE_BED_B': {}, 'SPONGE_BED_C': {}}}}

    def cfg(self):
        return self.conf

    def _note(self, name, *args):
        self.calls.append((name, *args))
        if self.fail_on == name or self.fail_on == (name, len([c for c in self.calls if c[0] == name])):
            raise MoveIncomplete(f'{name} 이 도중에 멈췄다')

    def move_to(self, station, carrying, kind=None, point=None):
        self._note('move_to', station, carrying, kind, point)
        return self.up.get((station, point), 0.0)

    def move_rel(self, dx, dy, dz, frame):
        self._note('move_rel', dx, dy, dz, frame)

    def release(self):
        self._note('release')


@pytest.fixture
def cc(monkeypatch):
    fake = FakeCC()
    monkeypatch.setattr(handling, 'cc', fake)
    return fake


# ------------------------------------------------------------------ move_to
def test_move_to_wraps_cc_move_to(cc):
    r = handling.move_to('WEIGH', True, 'CUP')
    assert type(r) is Result and r.ok and r.code == 'OK'
    assert cc.calls == [('move_to', 'WEIGH', True, 'CUP', None)]
    handling.move_to('HOME', False)                                         # kind 는 생략할 수 있다
    assert cc.calls[-1] == ('move_to', 'HOME', False, None, None)


def test_move_to_lets_motion_errors_through(cc):
    """도착하지 못했으면(cc.MoveIncomplete) 삼키지 않는다 — flow.call() 이 ROBOT_ERROR 로 바꾸고 문구를 HMI 에 싣는다."""
    cc.fail_on = 'move_to'
    with pytest.raises(MoveIncomplete):
        handling.move_to('WASTE', True, 'BOWL')


# ------------------------------------------------------------------ place
def test_place_on_sponge_bed_descends_releases_and_comes_back_up(cc):
    r = handling.place('SPONGE_BED_B')
    assert isinstance(r, PlaceResult) and r.ok and r.offset_mm == 0.0
    assert cc.calls == [('move_to', 'SPONGE_BED_B', True, None, 'place'),   # ① 접근점 — 스펀지 홈은 point='place', 들고 있으니 저속
                        ('move_rel', 0.0, 0.0, -147.7, 'BASE'),             # ② 끝점까지 곧게
                        ('release',),                                       # ③
                        ('move_rel', 0.0, 0.0, 147.7, 'BASE')]              # ④ 내려간 만큼 되올라온다


def test_place_without_approach_point_lifts_by_clear_height(cc):
    r = handling.place('ISOLATE', 'CUP')                                    # 종류별 자리 · 접근점 없음 → 끝점까지 곧장
    assert r.ok
    assert cc.calls == [('move_to', 'ISOLATE', True, 'CUP', None), ('release',), ('move_rel', 0.0, 0.0, 100.0, 'BASE')]


@pytest.mark.parametrize('fail_on', ['move_to', ('move_rel', 1)])
def test_place_never_releases_after_a_failed_move(cc, fail_on):
    """접근이나 하강이 도중에 멈추면 **쥔 채로** 예외를 올린다 — 공중에서 놓지 않는다."""
    cc.fail_on = fail_on
    with pytest.raises(MoveIncomplete):
        handling.place('SPONGE_BED_C')
    assert ('release',) not in cc.calls


def test_place_checks_its_setting_before_moving(cc):
    del cc.conf['f1']['place_clear_mm']
    with pytest.raises(KeyError):
        handling.place('ISOLATE', 'BOWL')
    assert cc.calls == []                                                   # 값이 없으면 로봇에 손대지 않는다


def test_place_works_three_times_in_a_row(cc):
    for _ in range(3):                                                      # SDD §3.2 ⑧ — "첫 번째만 되는" 결함 방지
        assert handling.place('SPONGE_BED_B').ok
    assert [c[0] for c in cc.calls] == ['move_to', 'move_rel', 'release', 'move_rel'] * 3
