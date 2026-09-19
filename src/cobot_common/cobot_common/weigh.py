# -*- coding: utf-8 -*-
"""무게 — 담당 민범진 (INF-02c). 함수 표는 docs/03_설계_SDD.md §3.1.

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
- reset(0점 재설정)은 선택 동작 · 응답 상한 3 s · 실패해도 반복하지 않는다 (TS-03).
"""
__all__ = ['weigh']

_TODO = '아직 구현 전이다 — 담당 민범진 (INF-02c). 급하면 같은 이름의 임시 stub 으로 먼저 짠다 (AGENTS.md §2)'


def weigh(n, reset=False):
    """정지 → get_workpiece_weight n회 평균 → g"""
    raise NotImplementedError(_TODO)
