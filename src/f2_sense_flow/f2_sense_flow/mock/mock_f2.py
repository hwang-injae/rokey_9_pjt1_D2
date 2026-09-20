# -*- coding: utf-8 -*-
"""가짜 F2 무게·털기·헹굼 — 실제는 내 f2_sense_flow.sense (IRD §4).

🔔 IRD §10·INF-03 산출물에는 mock_f1·mock_f3 만 적혀 있는데, 런치
   prewash_mock.launch.py 가 use_mock='f1,f2,f3' 로 부르고 config 의 MOCKABLE 에도
   f2 가 있어 함께 만들었다(DSN-03 에 알림). 없으면 F2-01 로 sense.py 속을 채우는 순간
   로봇 없는 런치가 깨진다 — 지금은 sense.py 가 껍데기라 안 드러날 뿐이다.

🚨 무게는 **0 g(잔반 없음)** 을 돌려준다 — 진짜 sense.weigh 가 돌려주는 것이
   "측정값" 이 아니라 **"잔반 무게"(측정값 − 빈 용기 기준값)** 이기 때문이다(SDD §5.3).
   F2-01 전에는 여기서 빈 용기 기준값(180 g)을 돌려줬는데, 그러면 같은 상황에서
   가짜는 180, 진짜는 0 이 되어 **가짜가 진짜와 다르게 동작한다.**
   잔반 상황을 만들려면 fail_on 으로 LEFTOVER 계열 코드를 주입한다.
"""
from cobot_api import LeftoverResult, Result, WeighResult

from . import code_for


def weigh(kind: str) -> WeighResult:
    code = code_for('weigh')
    if code:
        return WeighResult.fail(code)
    return WeighResult(weight_g=0.0)              # 잔반 0 g (진짜 sense.weigh 와 같은 뜻)


def leftover_loop(kind: str, max_rounds: int) -> LeftoverResult:
    # 🚨 무게는 weigh 와 같은 뜻(잔반 g)이다 — 통과는 0 g, 실패는 임계(50 g)를 넘긴 값.
    code = code_for('leftover_loop')
    if code:
        return LeftoverResult(ok=False, code=code, weight_before_g=80.0,
                              weight_after_g=60.0, rounds=max_rounds)
    return LeftoverResult(weight_before_g=0.0, weight_after_g=0.0, rounds=0)


def shake(mode: str, count: int, kind: str) -> Result:
    code = code_for('shake')
    return Result.fail(code) if code else Result()


def dip(station: str, count: int, kind: str) -> Result:
    code = code_for('dip')
    return Result.fail(code) if code else Result()
