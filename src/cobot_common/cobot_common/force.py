# -*- coding: utf-8 -*-
"""힘 함수: force_on/off · force_reached · contact_down · periodic_search · safe_retreat — 담당 박진용. 함수 표는 docs/03_설계_SDD.md §3.1. (INF-02a 에서 만든 빈 파일 — 담당자가 채운다)

쓰는 법
    from .bootstrap import cfg, dsr, io_node

    def 함수(...):
        d = dsr()                      # 두산 API 모듈. 메인 스레드가 아니면 여기서 오류가 난다 (SDD §3.2)
        p = cfg()['cell'][...]         # 숫자는 YAML 에서
        d.movej(...)

- 모듈 맨 위에서 DSR_ROBOT2 를 import 하지 않는다(TS-01 증상 A). 항상 함수 안에서 dsr() 로 얻는다.
- 만든 함수 이름을 아래 `__all__` 에 넣으면 `cc.함수()` 로 보인다. `__init__.py` 는 고치지 않는다.
- 통신 노드에 구독·클라이언트가 필요하면 이 파일에 `setup_io(node)` 를 만든다. init 이 한 번 불러 준다.
  콜백은 값 저장만 한다.
- check_force_condition 은 만족 0 / 아니면 -1 이다 → force_reached() 가 == 0 비교를 감싼다 (TS-01 증상 D).
"""
__all__ = []
