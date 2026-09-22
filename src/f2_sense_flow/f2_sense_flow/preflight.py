# -*- coding: utf-8 -*-
"""움직이기 전 문지기 — 컨트롤러의 툴·TCP 이름이 우리 좌표의 전제와 같은지 (민범진 · 9/22 · TS-07).

왜: 9/22 11:22 실기에서 저울 자세로 가던 그릇이 **바닥에 닿았다.** 코드·좌표는 아침에 6번 성공한 것과
    같았다. 원인은 다른 팀원이 펜던트에서 TCP 설정을 풀어 둔 것 — cell.yaml 의 posx 는 전부
    TCP `GripperDA_v1`(Z 208 mm) 기준이라, TCP 가 풀리면 같은 명령이 **208 mm 아래**를 향한다.
    여러 사람이 한 로봇을 쓰는 이상 남의 설정 실수가 내 실기를 깨뜨릴 수 있다 → 내 프로그램이
    **움직이기 전에** 확인하고 다르면 시작을 거부한다.

무엇: /dsr01/dsr_controller2/tool/get_current_tool · tcp/get_current_tcp 로 지금 이름을 읽어
      params.yaml flow.preflight 의 기대 이름과 비교한다. 로봇은 움직이지 않는다(조회만).
      기대 이름의 정본은 cell.yaml 머리말(ENV-05 · 황인재 기록) — 여기는 그것을 확인하는 데만 쓴다.

쓰는 곳: flow_node.main (robot=True 일 때) · rig_f2 · rig_int12 · rig_weigh_probe — cc.init 직후, 첫 이동 전.
🚨 통신 노드의 실행기가 다른 스레드에서 돌고 있어야 동기 호출(call)이 돌아온다 — cc.init 뒤에만 부른다(gripper._send 와 같은 조건).
"""
__all__ = ['PreflightError', 'check_controller', 'require_controller']

_SRV_PREFIX = '/dsr01/dsr_controller2/'          # 두산 드라이버 서비스 이름 (motion.py 와 같다)


class PreflightError(RuntimeError):
    """컨트롤러 설정이 기대와 다르다 — 움직이면 안 된다."""


def check_controller(node, expect, timeout_s=3.0):
    """지금 툴·TCP 이름을 읽어 기대값과 비교한다 → {'tool': (ok, 읽은 이름), 'tcp': (ok, 읽은 이름)}.

    expect : {'tool_name': 'Tool Weight', 'tcp_name': 'GripperDA_v1'} — 비어 있는 항목은 건너뛴다(검사 안 함).
    읽지 못하면(서비스 없음·응답 없음) ok=False, 이름 자리에 이유가 온다.
    """
    from dsr_msgs2.srv import GetCurrentTcp, GetCurrentTool
    plan = (('tool', 'tool_name', GetCurrentTool, 'tool/get_current_tool'),
            ('tcp', 'tcp_name', GetCurrentTcp, 'tcp/get_current_tcp'))
    out = {}
    for key, cfg_key, srv, name in plan:
        want = (expect or {}).get(cfg_key)
        if not want:
            continue
        client = node.create_client(srv, _SRV_PREFIX + name)
        try:
            if not client.wait_for_service(timeout_sec=float(timeout_s)):
                out[key] = (False, f'서비스 {_SRV_PREFIX + name} 가 안 보인다 — 브링업을 확인한다')
                continue
            res = client.call(srv.Request())
            if res is None or not getattr(res, 'success', False):
                out[key] = (False, '응답 없음 또는 success=False')
                continue
            got = str(getattr(res, 'info', ''))
            out[key] = (got == str(want), got)
        finally:
            try:
                node.destroy_client(client)
            except Exception:                        # noqa: BLE001 — 정리 실패는 결과에 영향 없다
                pass
    return out


def require_controller(node, cfg, log=None):
    """flow.preflight 설정대로 확인하고, 하나라도 다르면 PreflightError. 통과하면 읽은 이름을 돌려준다.

    설정이 없으면(flow.preflight 자체가 없음) 경고만 남기고 통과한다 — 옛 설정 파일로도 돌아가게.
    """
    pf = ((cfg or {}).get('flow') or {}).get('preflight') or {}
    if not pf:
        if log:
            log.warn('flow.preflight 가 없다 — 툴·TCP 이름을 확인하지 않고 움직인다 (TS-07)')
        return {}
    got = check_controller(node, pf, pf.get('timeout_s', 3.0))
    bad = {k: v for k, (ok, v) in got.items() if not ok}
    if bad:
        want = {k: pf.get(f'{k}_name') for k in bad}
        raise PreflightError(
            '🚨 컨트롤러 설정이 우리 좌표의 전제와 다르다 — 움직이지 않는다 (TS-07).\n'
            + '\n'.join(f'   {k}: 기대 {want[k]!r} · 지금 {v!r}' for k, v in bad.items())
            + '\n   펜던트(Dart)에서 툴·TCP 를 다시 고르고, cell.yaml 머리말의 이름과 같은지 본 뒤 다시 띄운다')
    if log:
        log.info('문지기 통과 — ' + ' · '.join(f'{k} {v!r}' for k, (_, v) in got.items()))
    return {k: v for k, (_, v) in got.items()}
