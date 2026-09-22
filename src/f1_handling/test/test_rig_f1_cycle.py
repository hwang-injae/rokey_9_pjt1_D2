"""rig_f1.py tool --action CYCLE (V-08 집기 → 반납 한 쌍 × n) 의 회차 규칙 — 로봇 없이 가짜 tool() 로 본다.

보는 것: 반납에 실패하면 **툴을 든 채 더 돌지 않는다** · 집기 실패는 세고 계속 · 1회차에만 Enter 를 기다린다 · 판정 기준 10회 ≥ 9.
"""
import importlib.util
from pathlib import Path

import pytest

from cobot_api import PICK, RETURN, ToolResult

_spec = importlib.util.spec_from_file_location('rig_f1', Path(__file__).with_name('rig_f1.py'))
rig = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rig)


class Log:
    def __init__(self):
        self.lines = []

    def info(self, m):
        self.lines.append(('info', m))

    def warn(self, m):
        self.lines.append(('warn', m))

    def error(self, m):
        self.lines.append(('error', m))


def fake_tool(fail=None, width=40.5):
    """fail = {(회차, 'PICK'|'RETURN'): 코드} — 부른 순서를 calls 에 적는다."""
    calls, count = [], {PICK: 0, RETURN: 0}

    def call(tool, action):
        count[action] += 1
        i = count[PICK]
        calls.append((i, action))
        code = (fail or {}).get((i, action))
        return ToolResult.fail(code, width_mm=34.5) if code else ToolResult(width_mm=width if action == PICK else 0.0)
    return call, calls


def asks():
    got = []
    return got, (lambda log, msg: got.append(msg))


def test_all_rounds_pick_then_return():
    call, calls = fake_tool()
    got, ask = asks()
    ok, rounds = rig.tool_cycle('SPONGE', 10, Log(), call, ask)
    assert ok == 10 and [c[1] for c in calls] == [PICK, RETURN] * 10
    assert len(got) == 2                                            # 1회차의 집기·반납 전에만 기다린다


def test_a_missed_pick_is_counted_and_the_next_round_goes_on():
    call, calls = fake_tool({(2, PICK): 'TOOL_FAIL'})
    ok, rounds = rig.tool_cycle('SPONGE', 4, Log(), call, asks()[1])
    assert ok == 3
    assert (2, RETURN) not in calls                                 # 집지 못했으면 반납하러 가지 않는다
    assert (2, PICK, 'TOOL_FAIL', 34.5) in rounds


def test_a_failed_return_stops_with_the_tool_in_hand():
    call, calls = fake_tool({(3, RETURN): 'TOOL_FAIL'})
    log = Log()
    ok, rounds = rig.tool_cycle('BRUSH', 10, log, call, asks()[1])
    assert ok == 2 and calls[-1] == (3, RETURN)                    # 남은 7회는 돌지 않는다
    assert any(kind == 'error' and '툴을 든 채' in m for kind, m in log.lines)


def test_q_before_the_first_move_moves_nothing():
    call, calls = fake_tool()

    def quit_(log, msg):
        raise KeyboardInterrupt
    with pytest.raises(KeyboardInterrupt):
        rig.tool_cycle('SPONGE', 10, Log(), call, quit_)
    assert calls == []


@pytest.mark.parametrize('ok, n, want', [(10, 10, True), (9, 10, True), (8, 10, False), (3, 3, True), (2, 3, False)])
def test_pass_rule_is_nine_of_ten(ok, n, want):
    assert rig.passed(ok, n) is want


def test_summary_reports_widths_without_the_zero():
    call, _ = fake_tool()
    ok, rounds = rig.tool_cycle('SPONGE', 3, Log(), call, asks()[1])
    log = Log()
    rig._summary(log, 'SPONGE', 3, ok, rounds, zero=10.58)
    text = ' '.join(m for _, m in log.lines)
    assert '성공 3/3 → 통과' in text and '영점 10.58 뺀 폭 29.92~29.92' in text
