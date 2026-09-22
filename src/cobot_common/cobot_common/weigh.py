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

⑤ 🚨 **단위는 kg 이다** — 9/21 첫 실기(이 경로로 읽은 첫 값)에서 그릇을 쥔 채 0.0684,
   빈손 0.0239 가 읽혔다. g 로 보면 "0.1 g" 이라 말이 안 되고, kg 으로 보면 68.4 g · 23.9 g
   (그릇 ≈ 44.5 g)으로 딱 맞는다. 9/18 V-02 는 펜던트 화면(N)을 손으로 읽은 것이라 이 경로의 단위를 몰랐다.

⑥ 🚨 **get_workpiece_weight 는 |Fz| 다 — 부호를 버린다.** 그래서 안 쓴다 (9/22 실기 · 민범진 R2).
   툴 힘센서 Fz(get_tool_force · BASE)와 나란히 읽어 보니 하중 추정치 = |Fz| / g 였다:
     빈손 Fz +0.87 N → 하중 89 g · 그릇 +0.05 → 10 g · 그릇+43 g −0.10 → 13 g · 그릇+107 g −0.79 → 80 g
   무게가 늘수록 Fz 는 **마이너스**로 가는데(중력 = −Z) 절댓값이라 0 근처에서 거울처럼 되튄다 —
   9/21 "0 에 잘린다" 고 본 것이 이것이었다. 등록된 툴 무게가 실제보다 무거워 빈손이 +0.87 N 인 것도
   (편향 — 기준값 빼기로 상쇄) 절댓값 때문에 "그릇을 쥐면 가벼워지는" 것처럼 보였다.
   → 이 함수는 **−Fz × 101.97 (g/N)** 을 돌려준다. 부호가 있어 편향이 음수여도 상쇄가 된다.
   같은 자세·같은 이동 속도에서 그릇+107 g 이 +86 g 으로 읽혔다(폭 29 g) — 잔반 대용품 ≥100 g(CELL-03)은 잡는다.
   43 g 은 +15~26 g 으로 반쯤 묻힌다(흔들림 ±25 g) — 임계 50 g 밑이라 어차피 잔반이 아니다.
   API 는 BR-SR §5.2 "사용 로봇 기능" 에 있는 get_tool_force (force.read_force 와 같은 호출).

🚨 옵셋에 대해: 값에 편향이 있다 — 빈손 −89 g(9/22 · 툴 무게 등록 뒤) 처럼 **음수**일 수도 있다.
   게다가 **이동 속도·이력에 따라 수십 g 씩 달라진다**(빈손 빠른 이동 −89 · 그릇 느린 이동 −5).
   잔반 판정은 `측정값 − 빈 용기 기준값` 이라 **두 값을 같은 경로·같은 자세·같은 속도로 재면 상쇄된다.**
   🚨 흔들림: 정지해 있어도 ±25 g 가 10~20 s 주기로 오르내린다(9/22) → 표본을 10 개(≈ 7 s) 이상 잡아 중앙값.
   그래서 `params.yaml` 의 `f2.empty_weight_g` 는 **저울 무게가 아니라 이 함수로 읽은 값**이어야 한다.
   저울로 잰 진짜 무게를 넣으면 빈 용기가 잔반 24 g 으로 보인다.
"""
import time

# 🚨 이 모듈은 이름이 함수 이름과 같다(weigh.py 안의 weigh()). __init__.py 의
#    `from .weigh import *` 가 함수를 패키지에 올려 **모듈 이름을 가린다.**
#    `from cobot_common import weigh` 는 함수를, 모듈이 필요하면
#    `importlib.import_module('cobot_common.weigh')` 를 쓴다(시험 코드 참고).
__all__ = ['weigh']

_MIN_SAMPLES = 1
KG_TO_G = 1000.0                           # ⑤ get_workpiece_weight 는 kg (지금은 안 쓴다 — ⑥)
N_TO_G = 101.97                            # ⑥ 1 N ≈ 101.97 g (g = 9.807)
_FZ = 2                                    # get_tool_force → [fx, fy, fz, mx, my, mz] 의 fz


def weigh(n, reset=False):
    """정지 상태에서 n 번 재서 중앙값을 g 로 돌려준다.

    n     : 잴 횟수 (params.yaml 의 f2.weigh_samples)
    reset : 0점 재설정을 먼저 할지 — **기본 끔**. TS-03 참고
    반환  : 무게(g) = −Fz × 101.97 — 툴 힘센서 Z(BASE) 를 부호 그대로 (⑥). 편향이 있어 음수일 수 있다

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
            f = d.get_tool_force(ref=d.DR_BASE)        # ⑥ 부호 있는 Fz — |Fz| 인 get_workpiece_weight 는 안 쓴다
        except Exception as e:             # noqa: BLE001 — 한 번 실패해도 나머지로 이어 간다
            _log().warn(f'get_tool_force 실패 — {e!r}')
            continue
        if not isinstance(f, (list, tuple)) or len(f) != 6:   # 🚨 API 는 실패를 -1 하나로 알려 준다
            _log().warn(f'툴 힘 읽기 실패값 {f!r} — 버린다')
            continue
        samples.append(-float(f[_FZ]) * N_TO_G)       # ⑥ 중력은 −Z → 무게 = −Fz

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
