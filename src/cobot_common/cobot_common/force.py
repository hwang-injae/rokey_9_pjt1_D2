# -*- coding: utf-8 -*-
"""힘 함수 — 담당 박진용 (INF-02b). 함수 표는 docs/03_설계_SDD.md §3.1.

INF-02a 가 올린 뼈대다: 이름·인자는 SDD §3.1 그대로, 속은 NotImplementedError. 담당자가 **이 파일만** 채운다.

쓰는 법
    from .bootstrap import cfg, dsr, io_node

    def move_to(station, carrying):
        d = dsr()                      # 두산 API 모듈(init 뒤에만). 메인 스레드가 아니면 여기서 오류가 난다 (SDD §3.2)
        p = cfg()['cell'][...]         # 숫자는 YAML 에서
        d.movej(...)

- 🚨 모듈 맨 위에서 DSR_ROBOT2 를 import 하지 않는다 — `import cobot_common` 은 init() 보다 먼저 일어난다(TS-01 증상 A).
  두산 함수는 항상 함수 안에서 dsr() 로 얻는다.
- 함수를 더 만들면 아래 `__all__` 에 이름을 넣는다 → `cc.함수()` 로 보인다. `__init__.py` 는 고치지 않는다.
- 통신 노드에 구독·클라이언트가 필요하면 이 파일에 `setup_io(node)` 를 만든다. init() 이 한 번 불러 준다. 콜백은 값 저장만.
- check_force_condition 은 만족 0 / 아니면 -1 이다(DRL 매뉴얼과 다름) → force_reached() 가 == 0 비교를 감싼다 (TS-01 증상 D).
- 접촉 동작에는 힘 상한 + 후퇴 + 타임아웃을 항상 넣는다 (AGENTS.md §3 규칙 2).
"""
__all__ = ['force_on', 'force_off', 'force_reached', 'contact_down', 'periodic_search', 'safe_retreat']

_TODO = '아직 구현 전이다 — 담당 박진용 (INF-02b). 급하면 같은 이름의 임시 stub 으로 먼저 짠다 (AGENTS.md §2)'


def force_on(axis, target, limit):
    """task_compliance_ctrl + set_desired_force"""
    raise NotImplementedError(_TODO)


def force_off():
    """힘제어·순응 해제"""
    raise NotImplementedError(_TODO)


def force_reached(axis, min, max):
    """check_force_condition(...) == 0 을 감싼 것 → bool"""
    raise NotImplementedError(_TODO)


def contact_down(max_depth, limit):
    """amovel 하강 + force_reached 감시 + 정지 → (depth, force)"""
    raise NotImplementedError(_TODO)


def periodic_search(amp, period, duration):
    """Move Periodic 탐색"""
    raise NotImplementedError(_TODO)


def safe_retreat():
    """툴 Z 후퇴 → 안전 높이"""
    raise NotImplementedError(_TODO)
