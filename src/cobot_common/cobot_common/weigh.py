# -*- coding: utf-8 -*-
"""무게 — 담당 민범진 (INF-02c). 함수 표는 docs/03_설계_SDD.md §3.1.

로봇 관절의 토크로 **들고 있는 물건의 무게**를 역산해 컨트롤러가 알려 준다.
우리는 계산하지 않고 받기만 한다. 다만 그냥 받으면 안 되는 이유가 있다:

① 값이 넓게 퍼진다 — 9/18 V-02 실측에서 200 g 추가 **40.8 g 폭**으로 흔들렸다
   ([기록](../../../docs/test_logs/20260918_V-02.md)). → 여러 번 재서 **중앙값**을 쓴다.
      평균은 한 번 크게 튄 값에 끌려가지만 중앙값은 안 끌려간다.
② 움직이는 중에 재면 가속도가 섞인다 → 부르는 쪽(f2.weigh)이 먼저 멈춘다.
③ 🚨 실패를 **음수로** 알려 준다 — 설치된 DSR_ROBOT2.py 의 get_workpiece_weight 는
   서비스가 실패하면 예외 대신 **-1** 을 돌려준다(srv 주석: "Negative value if error").
   그대로 쓰면 "무게 -1 g" 으로 계산이 돈다 → 음수는 버린다.
④ 🚨 0점 재설정(reset)은 컨트롤러를 멈출 수 있다 — TS-03 에서 실제로 모든 서비스가
   응답하지 않았고 브링업을 다시 해야 했다. → 선택 동작, 응답 상한, **실패하면 다시 부르지 않는다.**

🚨 옵셋에 대해: V-02 에서 하중과 무관하게 **+42~45 g** 이 더해져 읽혔다(원인 미확정 —
   그리퍼 무게 미보정 또는 0점 미설정). 잔반 판정은 `측정값 − 빈 용기 기준값` 이라
   **두 값을 같은 경로·같은 자세로 재면 옵셋이 상쇄된다.**
   그래서 `params.yaml` 의 `f2.empty_weight_g` 는 **저울 무게가 아니라 이 함수로 읽은 값**이어야 한다.
   저울로 잰 진짜 무게를 넣으면 빈 용기가 잔반 43 g 으로 보인다.
"""
import time

# 🚨 이 모듈은 이름이 함수 이름과 같다(weigh.py 안의 weigh()). __init__.py 의
#    `from .weigh import *` 가 함수를 패키지에 올려 **모듈 이름을 가린다.**
#    `from cobot_common import weigh` 는 함수를, 모듈이 필요하면
#    `importlib.import_module('cobot_common.weigh')` 를 쓴다(시험 코드 참고).
__all__ = ['weigh']

_MIN_SAMPLES = 1


def weigh(n, reset=False):
    """정지 상태에서 n 번 재서 중앙값을 g 로 돌려준다.

    n     : 잴 횟수 (params.yaml 의 f2.weigh_samples)
    reset : 0점 재설정을 먼저 할지 — **기본 끔**. TS-03 참고
    반환  : 무게(g)

    🚨 잴 수 없으면 **예외를 던진다.** 숫자 하나로는 "0 g" 과 "실패" 를 구분할 수 없기 때문이다.
       부르는 쪽(flow 의 Flow.call)이 잡아서 ROBOT_ERROR 로 바꾼다.
    🚨 멈춘 뒤에 불러야 한다. 움직이는 중에는 가속도가 섞인다.
    """
    from .bootstrap import cfg, dsr

    d = dsr()                              # init() 전이거나 메인 스레드가 아니면 여기서 막는다
    n = max(_MIN_SAMPLES, int(n))

    if reset:
        _try_reset(d, cfg())

    samples = []
    for _ in range(n):
        try:
            v = d.get_workpiece_weight()
        except Exception as e:             # noqa: BLE001 — 한 번 실패해도 나머지로 이어 간다
            _log().warn(f'get_workpiece_weight 실패 — {e!r}')
            continue
        if v is None or v < 0:             # 🚨 API 는 실패를 음수(-1)로 알려 준다
            _log().warn(f'하중 읽기 실패값 {v} — 버린다')
            continue
        samples.append(float(v))

    if not samples:
        raise RuntimeError(f'하중을 {n}회 모두 읽지 못했다 — 브링업·제어권을 확인한다')
    if len(samples) < n:
        _log().warn(f'하중 {n}회 중 {len(samples)}회만 읽었다')

    g = _median(samples)
    # 개별 값도 남긴다 — V-02 에서 회차 값을 안 남겨 평균·표준편차를 못 냈다(그 기록 §2)
    _log().info(f'weigh n={n} → {g:.1f} (읽음: {", ".join(f"{s:.1f}" for s in samples)})')
    return g


# ------------------------------------------------------------------ 내부
def _median(values):
    """중앙값. 튄 값 하나에 끌려가지 않는다(V-02 에서 폭 40.8 g)."""
    s = sorted(values)
    mid = len(s) // 2
    return s[mid] if len(s) % 2 else (s[mid - 1] + s[mid]) / 2.0


def _try_reset(d, conf):
    """0점 재설정 — 🚨 선택 동작. 실패해도 **다시 부르지 않고** 그냥 진행한다.

    TS-03: reset_workpiece_weight 가 반환하지 않으면 컨트롤러의 서비스 처리가 그 한 건에
    물려 뒤따르는 요청이 전부 대기한다. 반복 호출하면 계속 막힌다.
    판정식이 차동(측정값 − 빈 용기 기준값)이라 0점이 없어도 옵셋은 상쇄된다.
    """
    limit = float((conf.get('f2') or {}).get('weigh_reset_timeout_s') or 3.0)
    t0 = time.monotonic()
    try:
        d.reset_workpiece_weight()
    except Exception as e:                 # noqa: BLE001 — reset 실패로 측정을 포기하지 않는다
        _log().warn(f'0점 재설정 실패 — {e!r} · 그대로 진행한다 (TS-03)')
        return False
    took = time.monotonic() - t0
    if took > limit:
        _log().warn(f'0점 재설정이 {took:.1f}s 걸렸다 (상한 {limit}s) — 다시 부르지 않는다 (TS-03)')
        return False
    return True


def _log():
    from .bootstrap import io_node
    return io_node().get_logger()
