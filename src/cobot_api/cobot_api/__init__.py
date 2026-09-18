"""PreWash-Cell 기능 함수의 약속(정본). 문서: docs/02_인터페이스_IRD.md v3.0

    from cobot_api import PickResult, EMPTY_ZONE, BOWL, check_api, F1Api

이 패키지에는 로봇 코드가 없다. 바꾸려면 인터페이스 변경 요청 이슈 → 4명 확인 → PR.
"""
from .contracts import *          # noqa: F401,F403
from .contracts import __all__    # noqa: F401
