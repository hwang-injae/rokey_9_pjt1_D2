# -*- coding: utf-8 -*-
"""그리퍼 함수(RG2) — 담당 민범진 (INF-02d, 9/19 재분담 — 결정 기록 W3). 함수 표는 docs/03_설계_SDD.md §3.1.

INF-02 가 올린 뼈대다: 이름·인자는 SDD §3.1 그대로, 속은 NotImplementedError. 담당자가 **이 파일만** 채운다.

쓰는 법
    from .bootstrap import cfg, io_node

    def grip(width, force):
        p = cfg()['cell']['presets'][...]      # 숫자는 YAML 에서
        ...

- 그리퍼 명령: srv /onrobot/sendCommand (onrobot_rg_msgs/srv/SetCommand) — 통신 노드(io_node())의 클라이언트로 부른다.
  통신 노드는 다른 스레드에서 돌고 있으므로 메인 스레드에서 `client.call(req)`(동기 호출)을 써도 된다.
- 🚨 강사 배포 OnRobotRGControllerServer 는 OnRobotRGInput 토픽을 발행하지 않는다(9/19 확인 — 나가는 것은
  /onrobot_joint_states 의 JointState 뿐). 현재 폭을 읽는 경로는 V-05 에서 정한다(DSN-03 D2: 관절각 → 폭 환산이 먼저).
- 통신 노드에 구독·클라이언트를 달 자리: 이 파일에 `setup_io(node)` 를 만들면 init() 이 한 번 불러 준다. 콜백은 값 저장만.
- 함수를 더 만들면 아래 `__all__` 에 이름을 넣는다 → `cc.함수()` 로 보인다. `__init__.py` 는 고치지 않는다.
"""
__all__ = ['grip', 'grip_level', 'release', 'grip_width']

_TODO = '아직 구현 전이다 — 담당 민범진 (INF-02d). 급하면 같은 이름의 임시 stub 으로 먼저 짠다 (AGENTS.md §2)'


def grip(width, force):
    """RG2 파지(목표 폭 mm · 힘 N) + 완료 대기 → 실제 폭(mm)"""
    raise NotImplementedError(_TODO)


def grip_level(kind, level):
    """파지 힘 2단계 전환 NORMAL ↔ HOLD. 같은 폭 목표로 힘만 바꿔 다시 파지, 전환 후 폭 재확인 (V-23)"""
    raise NotImplementedError(_TODO)


def release():
    """그리퍼 열기"""
    raise NotImplementedError(_TODO)


def grip_width():
    """현재 그리퍼 폭(mm). 읽는 경로는 V-05 에서 정한다"""
    raise NotImplementedError(_TODO)
