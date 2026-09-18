"""
ReWash-Cell 공용 로봇 함수.

현재 단계:
- 함수 이름과 역할만 정의한다.
- 좌표 티칭과 실제 로봇 검증 후 내부 동작을 구현한다.
"""


def move_to(station, carrying=False):
    """지정된 스테이션으로 이동."""
    raise NotImplementedError("좌표 티칭 후 구현")


def move_rel(dx, dy, dz, frame):
    """현재 위치 기준 상대 이동."""
    raise NotImplementedError("좌표계 검증 후 구현")


def grip(width, force):
    """RG2로 물체를 잡고 실제 파지 폭을 반환."""
    raise NotImplementedError("RG2 파지 폭/DO·DI 검증 후 구현")


def release():
    """RG2 그리퍼를 연다."""
    raise NotImplementedError("RG2 DO·DI 검증 후 구현")


def weigh(n):
    """작업물 무게를 n회 측정해 평균값을 반환."""
    raise NotImplementedError("실기 하중 측정 검증 후 구현")


def force_on(axis, target, limit):
    """지정 축의 순응/힘 제어 시작."""
    raise NotImplementedError("힘 제어 검증 후 구현")


def force_off():
    """힘 제어를 종료."""
    raise NotImplementedError("힘 제어 검증 후 구현")


def contact_down(max_depth, limit):
    """힘을 감시하면서 아래로 내려가 접촉점을 찾는다."""
    raise NotImplementedError("접촉 하강 검증 후 구현")


def periodic_search(amp, period, duration):
    """Move Periodic 방식으로 주변을 탐색."""
    raise NotImplementedError("Move Periodic 검증 후 구현")


def safe_retreat():
    """접촉 실패나 오류 발생 시 안전 방향으로 후퇴."""
    raise NotImplementedError("안전 후퇴 거리/좌표 확정 후 구현")
