# -*- coding: utf-8 -*-
"""preflight — 툴·TCP 이름 문지기 (TS-07). 로봇·ROS 없이 가짜 노드로."""
import sys
import types

import pytest

from f2_sense_flow import preflight as P


class _Res:
    def __init__(self, info, success=True):
        self.info, self.success = info, success


class _Client:
    def __init__(self, res, available=True):
        self._res, self._available = res, available

    def wait_for_service(self, timeout_sec=0):
        return self._available

    def call(self, req):
        return self._res


class _Node:
    """create_client 가 서비스 이름별로 미리 정한 응답을 준다."""
    def __init__(self, answers):
        self.answers = answers            # {'tool/get_current_tool': _Client, ...}
        self.destroyed = 0

    def create_client(self, srv, name):
        return self.answers[name.replace(P._SRV_PREFIX, '')]

    def destroy_client(self, c):
        self.destroyed += 1


@pytest.fixture(autouse=True)
def fake_srv(monkeypatch):
    """dsr_msgs2 없이 돌게 — Request() 만 있으면 된다."""
    m = types.ModuleType('dsr_msgs2.srv')
    for n in ('GetCurrentTool', 'GetCurrentTcp'):
        setattr(m, n, type(n, (), {'Request': staticmethod(lambda: object())}))
    monkeypatch.setitem(sys.modules, 'dsr_msgs2', types.ModuleType('dsr_msgs2'))
    monkeypatch.setitem(sys.modules, 'dsr_msgs2.srv', m)


CFG = {'flow': {'preflight': {'tool_name': 'Tool Weight', 'tcp_name': 'GripperDA_v1', 'timeout_s': 0.1}}}


def _node(tool='Tool Weight', tcp='GripperDA_v1', tool_ok=True, tcp_avail=True):
    return _Node({'tool/get_current_tool': _Client(_Res(tool, tool_ok)),
                  'tcp/get_current_tcp': _Client(_Res(tcp), available=tcp_avail)})


def test_pass_when_names_match():
    n = _node()
    got = P.require_controller(n, CFG)
    assert got == {'tool': 'Tool Weight', 'tcp': 'GripperDA_v1'}
    assert n.destroyed == 2                                   # 클라이언트를 남기지 않는다


def test_refuse_when_tcp_unset():
    """9/22 11:22 — TCP 가 풀려 있으면 같은 좌표가 208 mm 아래로 간다. 시작을 거부한다."""
    with pytest.raises(P.PreflightError, match="tcp: 기대 'GripperDA_v1' · 지금 ''"):
        P.require_controller(_node(tcp=''), CFG)


def test_refuse_when_tool_differs():
    with pytest.raises(P.PreflightError, match='tool'):
        P.require_controller(_node(tool='NoTool'), CFG)


def test_refuse_when_service_missing():
    with pytest.raises(P.PreflightError, match='서비스'):
        P.require_controller(_node(tcp_avail=False), CFG)


def test_refuse_when_success_false():
    with pytest.raises(P.PreflightError, match='응답 없음'):
        P.require_controller(_node(tool_ok=False), CFG)


def test_skip_item_when_name_empty():
    """비워 둔 항목은 검사하지 않는다 — TCP 만 확인하고 싶을 때."""
    cfg = {'flow': {'preflight': {'tool_name': '', 'tcp_name': 'GripperDA_v1'}}}
    assert P.require_controller(_node(tool='아무거나'), cfg) == {'tcp': 'GripperDA_v1'}


def test_no_config_warns_and_passes():
    class Log:
        def __init__(self): self.w = []
        def warn(self, m): self.w.append(m)
        def info(self, m): pass
    log = Log()
    assert P.require_controller(_node(), {'flow': {}}, log) == {}
    assert any('preflight' in m for m in log.w)
