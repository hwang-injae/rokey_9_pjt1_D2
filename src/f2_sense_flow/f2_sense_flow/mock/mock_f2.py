# -*- coding: utf-8 -*-
"""가짜 F2 무게·털기·헹굼 — 실제는 내 f2_sense_flow.sense (IRD §4).

🔔 IRD §10·INF-03 산출물에는 mock_f1·mock_f3 만 적혀 있는데, 런치
   prewash_mock.launch.py 가 use_mock='f1,f2,f3' 로 부르고 config 의 MOCKABLE 에도
   f2 가 있어 함께 만들었다(DSN-03 에 알림). 없으면 F2-01 로 sense.py 속을 채우는 순간
   로봇 없는 런치가 깨진다 — 지금은 sense.py 가 껍데기라 안 드러날 뿐이다.

무게는 설정의 빈 용기 기준값을 그대로 돌려준다 = "잔반 없음". 잔반 상황을 만들려면
fail_on 으로 LEFTOVER 계열 코드를 주입한다.
"""
from cobot_api import LeftoverResult, Result, WeighResult

from . import code_for

_EMPTY_G = {'BOWL': 180.0, 'CUP': 120.0}         # params.yaml f2.empty_weight_g 의 예시값


def _empty(kind):
    try:
        import cobot_common as cc
        return float(cc.cfg()['f2']['empty_weight_g'][kind])
    except Exception:
        return _EMPTY_G.get(kind, 0.0)


def weigh(kind: str) -> WeighResult:
    code = code_for('weigh')
    if code:
        return WeighResult.fail(code)
    return WeighResult(weight_g=_empty(kind))     # 기준값 그대로 = 잔반 0 g


def leftover_loop(kind: str, max_rounds: int) -> LeftoverResult:
    code = code_for('leftover_loop')
    g = _empty(kind)
    if code:
        return LeftoverResult.fail(code, weight_before_g=g + 80.0, weight_after_g=g + 60.0,
                                   rounds=max_rounds)
    return LeftoverResult(weight_before_g=g, weight_after_g=g, rounds=0)


def shake(mode: str, count: int, kind: str) -> Result:
    code = code_for('shake')
    return Result.fail(code) if code else Result()


def dip(station: str, count: int, kind: str) -> Result:
    code = code_for('dip')
    return Result.fail(code) if code else Result()
