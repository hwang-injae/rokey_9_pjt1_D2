# -*- coding: utf-8 -*-
"""기능 함수의 약속 — IRD v3.0 §2~5 와 같은 내용. 이 파일과 문서가 다르면 이 파일이 정본.

구조(9/18 결정): flow_node(메인 프로그램)가 f1·f2·f3 의 **파이썬 함수**를 차례로 부른다.
서비스가 아니므로 .srv 대신 여기의 반환 타입(dataclass)과 함수 서명(Protocol)이 약속이다.

규칙
- 모든 기능 함수는 Result(또는 그 하위 타입)를 돌려준다. 실패는 예외가 아니라 ok=False + code.
- 문자열 ID·코드는 아래 상수를 쓴다(오타 방지). 값은 ROS 메시지·YAML·기록·HMI 에서도 같다.
- mock 모듈도 같은 서명을 지킨다 → check_api(모듈, F1Api) 로 검사.
"""
from dataclasses import dataclass, asdict
from typing import Protocol, List
import inspect

# ------------------------------------------------------------------ §2 공통 ID
BOWL, CUP = 'BOWL', 'CUP'                                   # kind
SPONGE, BRUSH = 'SPONGE', 'BRUSH'                           # tool
PICK, RETURN = 'PICK', 'RETURN'                             # tool action
RET_B, RET_C = 'RET_B', 'RET_C'                             # zone_id (반납 구역)
RACK_SLOTS = ('RACK_B1', 'RACK_B2', 'RACK_C1', 'RACK_C2', 'RACK_C3', 'RACK_C4')
STATIONS = ('HOME', 'WEIGH', 'WASTE', 'SPONGE_BED_B', 'SPONGE_BED_C',
            'TOOL_SPONGE', 'TOOL_BRUSH', 'SOAP', 'RINSE', 'ISOLATE')
NORMAL, HOLD = 'NORMAL', 'HOLD'                             # 파지 힘 2단계
WASTE, RINSE = 'WASTE', 'RINSE'                             # shake mode / dip station
STEPS = ('IDLE', 'PICK', 'WEIGH', 'SHAKE', 'SEAT', 'SOAP', 'WIPE', 'RINSE',
         'RACK', 'ISOLATE', 'DONE', 'ERROR', 'PAUSED')      # FlowState.step

# ------------------------------------------------------------------ §2 실패 코드
OK = 'OK'
GRIP_FAIL = 'GRIP_FAIL'
EMPTY_ZONE = 'EMPTY_ZONE'
LEFTOVER = 'LEFTOVER'
LEFTOVER_REMAIN = 'LEFTOVER_REMAIN'
SEAT_FAIL = 'SEAT_FAIL'
TOOL_FAIL = 'TOOL_FAIL'
FORCE_LIMIT = 'FORCE_LIMIT'
TIMEOUT = 'TIMEOUT'
RACK_JAM = 'RACK_JAM'
RACK_FULL = 'RACK_FULL'
ROBOT_ERROR = 'ROBOT_ERROR'
STOPPED = 'STOPPED'
CODES = (OK, GRIP_FAIL, EMPTY_ZONE, LEFTOVER, LEFTOVER_REMAIN, SEAT_FAIL, TOOL_FAIL,
         FORCE_LIMIT, TIMEOUT, RACK_JAM, RACK_FULL, ROBOT_ERROR, STOPPED)


# ------------------------------------------------------------------ 반환 타입
@dataclass
class Result:
    """모든 기능 함수의 공통 반환. 실패면 ok=False 와 code."""
    ok: bool = True
    code: str = OK

    def as_dict(self):
        return asdict(self)

    @classmethod
    def fail(cls, code, **kw):
        assert code in CODES, f'IRD §2 에 없는 코드: {code}'
        return cls(ok=False, code=code, **kw)


@dataclass
class PickResult(Result):           # f1.pick
    width_mm: float = 0.0           # 파지 후 그리퍼 폭
    attempts: int = 0               # 시도한 탐색점 수
    offset_x_mm: float = 0.0        # 성공한 탐색점 오프셋(구역 기준점 기준)
    offset_y_mm: float = 0.0


@dataclass
class PlaceResult(Result):          # f1.place
    offset_mm: float = 0.0          # 안착 놓기에서 탐색으로 보정된 거리(일반 놓기는 0)


@dataclass
class ToolResult(Result):           # f1.tool
    width_mm: float = 0.0


@dataclass
class WeighResult(Result):          # f2.weigh
    weight_g: float = 0.0


@dataclass
class LeftoverResult(Result):       # f2.leftover_loop
    weight_before_g: float = 0.0
    weight_after_g: float = 0.0
    rounds: int = 0


@dataclass
class WipeBowlResult(Result):       # f3.wipe_bowl
    force_log_path: str = ''        # 힘 로그 CSV 상대경로
    duration_s: float = 0.0
    force_mean_n: float = 0.0       # 닦는 동안 평균 접촉 힘


@dataclass
class WipeCupResult(Result):        # f3.wipe_cup
    force_log_path: str = ''
    duration_s: float = 0.0
    insert_depth_mm: float = 0.0    # 실제 삽입된 깊이


# ------------------------------------------------------------------ 함수 서명
class F1Api(Protocol):
    """F1 파지·이송·적재 — 한석형 · 모듈 f1_handling.handling"""

    def pick(self, zone_id: str, kind: str) -> PickResult:
        """탐색 파지. zone_id 가 SPONGE_BED_* 면 고정 위치 재파지(탐색점 1개). 코드 OK/EMPTY_ZONE/ROBOT_ERROR"""

    def place(self, station: str) -> PlaceResult:
        """놓기(항상 release 까지). SPONGE_BED_* 면 안착 놓기. 코드 OK/SEAT_FAIL/FORCE_LIMIT/TIMEOUT/ROBOT_ERROR"""

    def move_to(self, station: str, carrying: bool) -> Result:
        """안전 높이 경유 이동. 들고 있으면 저속. 안전 자세 복귀는 move_to('HOME', False)"""

    def tool(self, tool: str, action: str) -> ToolResult:
        """툴 픽업/반납. tool=SPONGE/BRUSH, action=PICK/RETURN. 폭 범위 밖이면 TOOL_FAIL"""

    def rack_place(self, rack_slot: str, kind: str) -> Result:
        """팔레트 칸 삽입. 걸리면 RACK_JAM"""


class F2Api(Protocol):
    """F2 무게·털기·헹굼 — 민범진 · 모듈 f2_sense_flow.sense"""

    def weigh(self, kind: str) -> WeighResult:
        """WEIGH 자세 정지 후 N회 평균"""

    def leftover_loop(self, kind: str, max_rounds: int) -> LeftoverResult:
        """판정→털기→재측정 반복. 초과 지속이면 LEFTOVER_REMAIN"""

    def shake(self, mode: str, count: int, kind: str) -> Result:
        """털기(WASTE)·물 털기(RINSE). 시작 HOLD, 끝 NORMAL. 미끄러지면 GRIP_FAIL"""

    def dip(self, station: str, count: int, kind: str) -> Result:
        """헹굼 수조 담금(HOLD)"""


class F3Api(Protocol):
    """F3 접촉 닦기 — 박진용 · 모듈 f3_wipe.wipe"""

    def soap(self, count: int) -> Result:
        """툴 든 채 세제 수조 담금"""

    def wipe_bowl(self) -> WipeBowlResult:
        """그릇: 힘제어 나선 닦기. 상한 초과 FORCE_LIMIT"""

    def wipe_cup(self) -> WipeCupResult:
        """컵: 솔 삽입 → J6 회전 + Z 스트로크"""


def check_api(module, api) -> List[str]:
    """module 이 api(F1Api 등)의 함수를 같은 이름·같은 인자로 모두 갖고 있는지 검사. 문제 목록을 돌려준다(없으면 [])."""
    problems = []
    for name, want in inspect.getmembers(api, inspect.isfunction):
        if name.startswith('_'):
            continue
        got = getattr(module, name, None)
        if not callable(got):
            problems.append(f'{name}: 함수가 없다')
            continue
        w = [p for p in inspect.signature(want).parameters if p != 'self']
        g = [p for p in inspect.signature(got).parameters if p != 'self']
        if w != g:
            problems.append(f'{name}: 인자 {g} ≠ 약속 {w}')
    return problems


__all__ = [n for n in dir() if not n.startswith('_') and n not in
           ('dataclass', 'asdict', 'Protocol', 'List', 'inspect')]
