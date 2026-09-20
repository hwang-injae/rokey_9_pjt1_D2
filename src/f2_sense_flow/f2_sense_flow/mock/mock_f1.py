# -*- coding: utf-8 -*-
"""가짜 F1 파지·이송·적재 — 실제는 한석형의 f1_handling.handling (IRD §3).

이름·인자·반환은 cobot_api.F1Api 그대로. 로봇을 움직이지 않고 즉시 돌려준다.
숫자는 "그럴듯한 값"일 뿐 측정값이 아니다.
"""
from cobot_api import PickResult, PlaceResult, Result, ToolResult

from . import code_for

_WIDTH_MM = {'BOWL': 62.0, 'CUP': 70.0}          # cell.yaml presets 의 예시값과 맞춰 둔 표시용
_TOOL_WIDTH_MM = {'SPONGE': 30.0, 'BRUSH': 22.0}


def pick(zone_id: str, kind: str) -> PickResult:
    code = code_for('pick')
    if code:
        return PickResult.fail(code, attempts=5)
    return PickResult(width_mm=_WIDTH_MM.get(kind, 60.0), attempts=1,
                      offset_x_mm=0.0, offset_y_mm=0.0)


def place(station: str, kind: str = None) -> PlaceResult:
    code = code_for('place')
    if code:
        return PlaceResult.fail(code)
    return PlaceResult(offset_mm=0.0)


def move_to(station: str, carrying: bool, kind: str = None) -> Result:
    code = code_for('move_to')
    return Result.fail(code) if code else Result()


def tool(tool: str, action: str) -> ToolResult:
    code = code_for('tool')
    if code:
        return ToolResult.fail(code)
    return ToolResult(width_mm=_TOOL_WIDTH_MM.get(tool, 25.0))


def rack_place(rack_slot: str, kind: str) -> Result:
    code = code_for('rack_place')
    return Result.fail(code) if code else Result()
