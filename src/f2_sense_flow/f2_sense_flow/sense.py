# -*- coding: utf-8 -*-
"""F2 무게·털기·헹굼 — 민범진 · 모듈 f2_sense_flow.sense

약속(정본) : src/cobot_api/cobot_api/contracts.py 의 F2Api
설계       : docs/02_인터페이스_IRD.md §4 · docs/03_설계_SDD.md §5.3

이 파일이 하는 일 (용기 하나가 씻기는 과정에서 F2 가 맡은 네 조각)
  weigh          WEIGH 자세로 가서 **잔반 무게**를 잰다 (저울이 아니라 로봇 하중으로 잰다)
  leftover_loop  잰다 → 임계 넘으면 털고 다시 잰다 → 반복 (F2 의 핵심)
  shake          잔반통/수조 **위에서** 관절을 왕복시켜 턴다
  dip            수조 위에서 내려갔다 올라온다 (🚨 물은 안 쓴다 — 모션만)

지킨 것 (SDD §3.2 · AGENTS.md §3·§4)
  · 로봇은 `import cobot_common as cc` 로만 부른다. DSR_ROBOT2 직접 import 금지
  · 🚨 숫자(임계·횟수·진폭·깊이)를 **코드에 쓰지 않는다** — 값은 params.yaml
    → 실기에서 값이 바뀌어도 **YAML 만 고치면 되고 이 파일은 안 바뀐다**
  · 실패는 예외가 아니라 Result.fail(코드) 로 돌려준다 (@_as_result 가 보장)
  · 🚨 **어떤 실패에서도 안전 높이로 물러난다** (AGENTS §4). @_as_result 와 _fail() 이 같이 한다 —
    flow.call() 은 **예외가 올라올 때만** 후퇴하는데 우리는 예외를 삼키기 때문이다
  · 이 함수들은 flow_node 의 메인 스레드에서만 불린다. 여기서 노드를 만들지 않는다

고칠 때 볼 곳
  · 값을 바꾸고 싶다        → params.yaml 의 f2 절
    🔔 단, **횟수 일부는 flow 절**이다: rinse_shakes · rinse_dips · leftover_max_rounds.
       f2 절에 있는 횟수는 shake.WASTE.cycles 하나뿐이다(leftover_loop 이 스스로 부르므로)
  · 이동 방식을 바꾸고 싶다  → _goto()
  · 파지 되돌리기를 바꾸고 싶다 → _release_hold()   ← PR #32 D2("HOLD 유지")가 정해지면 **이 함수 본문만**
  · 미끄러짐 판정을 바꾸고 싶다 → _slipped()
  · 새 실패 코드를 쓰고 싶다  → cobot_api.contracts 의 CODES 에 먼저 있어야 한다
"""
import functools
import time
import traceback

# cobot_api = 팀이 정한 "함수 약속" 패키지(황인재 관리). 우리는 읽어 쓰기만 한다.
from cobot_api import (GRIP_FAIL, HOLD, LEFTOVER_REMAIN, NORMAL, ROBOT_ERROR,
                       LeftoverResult, Result, WeighResult)

import cobot_common as cc

# 스테이션 이름 = shake 의 mode 이름과 같다(WASTE·RINSE). WEIGH 는 contracts 에 상수가 없어 여기 하나만 둔다.
_WEIGH_STATION = 'WEIGH'

# 🚨 이 예외들은 Result 로 바꾸지 **않고** 위로 그대로 올린다 (9/21 PM 요청 · SDD §7)
#    MoveIncomplete : 이동이 도중에 섰다 → **로봇이 어디 있는지 모른다.** 여기서 코드로 바꾸면
#                     flow 가 평범한 실패로 보고 재시도하거나 이어서 내려간다 — 그러면 안 된다.
#    MotionHalted   : 강제정지(중단) — flow 의 중단 흐름이 받아야 한다(FLOW-03).
#    flow.call() 이 받아서 ROBOT_ERROR(그 자리 정지 → PAUSED)로 마무리한다.
_PASS_THROUGH = (cc.MoveIncomplete, cc.MotionHalted)


# ────────────────────────────────────────────────────────── 설정 읽기
def _log():
    return cc.io_node().get_logger()


def _f2():
    """params.yaml 의 f2 절. 없으면 빈 dict 가 아니라 **에러**여야 한다 — 조용히 기본값으로
    돌면 '왜 안 되지' 를 실기에서 찾게 된다."""
    conf = (cc.cfg() or {}).get('f2')
    if not conf:
        raise KeyError('params.yaml 에 f2 절이 없다 — 설정 파일을 확인한다')
    return conf


def _need(conf, key, cast=float, where='f2', lo=None, hi=None):
    """설정값 하나를 **반드시** 읽는다. 없으면 예외 — 기본값으로 조용히 돌지 않는다.

    🚨 `conf.get(key) or 기본값` 으로 쓰면 **0 을 설정할 수 없다**(0 은 거짓이라 기본값이 나간다).
       그래서 'None 인가' 만 따로 본다. flow.py 의 `_num` 과 **같은 점은 이것뿐**이고,
       **다른 점은 여기엔 기본값이 없다는 것**이다 — 임계·진폭이 조용히 기본값으로 돌면 더 위험하다.

    lo/hi 를 주면 범위를 검사한다. 🚨 자릿수 오타(15 → 150)가 그대로 로봇 명령이 되는 것을 막는다.
    """
    v = conf.get(key) if isinstance(conf, dict) else None
    if v is None:
        raise KeyError(f'params.yaml 의 {where}.{key} 가 비어 있다 — 값을 채운다')
    v = cast(v)
    if lo is not None and v < lo:
        raise ValueError(f'{where}.{key} = {v} 가 최소 {lo} 보다 작다 — 값을 확인한다')
    if hi is not None and v > hi:
        raise ValueError(f'{where}.{key} = {v} 가 상한 {hi} 를 넘는다 (f2.limits) — 값을 확인한다')
    return v


def _group(conf, group, name):
    """f2.<group>.<name> 묶음(예: f2.shake.WASTE)을 꺼낸다."""
    g = conf.get(group)
    if not isinstance(g, dict) or name not in g or not isinstance(g[name], dict):
        raise KeyError(f'params.yaml 의 f2.{group}.{name} 이 없다 — 값을 채운다')
    return g[name]


def shake_params(conf, mode, kind):
    """f2.shake.<mode> 의 값 묶음 — 🆕 9/22 **종류별**: 그 안에 BOWL/CUP 묶음이 있으면 kind 것을, 없으면 공용 묶음을 쓴다.

        shake:
          RINSE:                      # 종류별 (컵과 그릇의 까딱임이 다르다 — 민범진 9/22)
            BOWL: {joint: 5, amp_deg: 10, period_s: 0.5}
            CUP:  {joint: 5, amp_deg: 6, period_s: 0.6}
          WASTE: {joint: 5, amp_deg: 15, cycles: 4, period_s: 0.6, tilt_deg: -90}   # 공용(그릇만 쓴다 · E25)

    종류별 묶음이 있는데 kind 것이 없으면 KeyError — 조용히 다른 종류 값으로 돌지 않는다.
    시험대(rig_f2 · rig_shake_tune)도 이 함수로 같은 묶음을 집어 덮어쓴다.
    """
    g = _group(conf, 'shake', mode)
    per_kind = {k: v for k, v in g.items() if k in ('BOWL', 'CUP') and isinstance(v, dict)}
    if per_kind:
        if kind not in per_kind:
            raise KeyError(f'params.yaml 의 f2.shake.{mode}.{kind} 가 없다 — 종류별로 나눴으면 둘 다 채운다')
        return per_kind[kind]
    return g


def _limits(conf):
    lim = conf.get('limits')
    if not isinstance(lim, dict):
        raise KeyError('params.yaml 의 f2.limits 가 없다 — 오타 방어 상한을 채운다')
    return lim


# ────────────────────────────────────────────────────────── 안전 도구
def _quietly(what, fn, *args):
    """실패해도 삼키는 호출. 되돌리기(finally)·후퇴처럼 '해 보고 안 되면 어쩔 수 없는' 자리에 쓴다."""
    try:
        fn(*args)
        return True
    except Exception as e:                           # noqa: BLE001 — 여기서 더 번지면 안 된다
        try:
            _log().error(f'{what} 실패 — {e!r}')
        except Exception:                            # noqa: BLE001
            pass
        return False


def _retreat():
    """🚨 실패로 끝나기 전에 **안전 높이로 물러난다** (AGENTS §4 · SDD §7).

    flow.call() 은 **예외가 올라올 때만** safe_retreat 를 부른다. 우리는 예외를 Result 로
    바꿔서 돌려주므로(@_as_result) flow 쪽 후퇴가 안 걸린다 → 여기서 직접 해야 한다.
    """
    _quietly('safe_retreat', cc.safe_retreat)


def _fail(result_cls, code, **kw):
    """실패를 돌려주기 전에 후퇴까지 한다. 성공 경로에서는 쓰지 않는다."""
    _retreat()
    return result_cls.fail(code, **kw)


def _as_result(result_cls):
    """기능 함수의 껍데기 — 예외를 **Result.fail(ROBOT_ERROR)** 로 바꾸고 안전 높이로 물러난다.

    🚨 기능 함수는 예외를 밖으로 내보내지 않는다(AGENTS §4 · SDD §5.1).
       KeyboardInterrupt 는 BaseException 이라 여기 안 걸린다 — Ctrl+C 는 그대로 올라가는 게 맞다.
    """
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            try:
                return fn(*args, **kwargs)
            except _PASS_THROUGH:                    # 🚨 삼키지 않는다 — 위 _PASS_THROUGH 주석
                raise
            except Exception as e:                   # noqa: BLE001 — 코드로 바꿔 보고한다
                try:
                    # 🚨 traceback 까지 남긴다 — finally 에서 난 예외가 원래 원인을 덮을 수 있고,
                    #    TS-05(두산 DR_Error) 복구에 "어느 함수에 어떤 인자" 가 꼭 필요하다.
                    _log().error(f'{fn.__name__} 실패 — {type(e).__name__}: {e}\n'
                                 f'{traceback.format_exc()}')
                except Exception:                    # noqa: BLE001 — 로그가 죽어도 결과는 돌려준다
                    pass
                _retreat()
                return result_cls.fail(ROBOT_ERROR)
        return wrapper
    return deco


# ────────────────────────────────────────────────────────── 동작 도구
def _goto(station, carrying=True, kind=None):
    """station 의 **티칭 자세까지** 간다.

    🚨 kind('BOWL'·'CUP')를 반드시 넘긴다 — 9/20 결정 E8·PR #36 으로 WEIGH·WASTE·RINSE·ISOLATE 는
       cell.yaml 에서 **종류별로 자세가 갈렸다**(그릇은 위에서·컵은 옆에서 잡아 자세가 다르다).
       안 넘기면 cc.move_to 가 "골라야 하는데 안 줬다"로 ValueError 를 낸다(로봇은 움직이지 않는다).

    🚨 cc.move_to 는 접근점이 있으면 **접근점까지만** 가고 끝점까지 남은 높이를 돌려준다
       (9/20 결정 E7 — 안전 높이를 거치지 않는다. 접근점이 없으면 끝점까지 가고 0 을 돌려준다).
       티칭 자세 = 그 기능이 **동작을 시작하는 자세**다(SDD §5.3, 황인재 9/20 확정)
       → 남은 높이를 여기서 마저 내려가야 각 함수의 depth_mm 같은 값이 '티칭 자세 기준' 이 된다.
       🟡 접근점이 끝점 바로 위가 아닌 자리는 이 값만으로 끝점에 못 간다 — F2 의 네 자리는
          모두 접근점이 없어(0 이 온다) 해당 없지만, 접근점이 생기면 여기를 다시 본다.

    🚨 먼저 force_off() 를 부른다. 순응·힘제어가 켜진 채면 ① 관절 이동이 거부되고
       (오류 2.1903 — 설치본 DRFC.py:528 RC_ERROR_DRCL_STATE_INVALID_EVENT, RobotError group MOTION=2)
       ② 직교 이동은 되더라도 **힘제어가 계속 눌러서** 지령한 거리만큼 안 간다(조용한 실패라 더 나쁘다).
       앞 단계(F3 닦기)가 껐어야 정상이지만 실패로 끝났으면 켜진 채일 수 있다.
       꺼져 있어도 부를 수 있게 만들어져 있다(force.py force_off 머리말).
    """
    cc.force_off()
    up = float(cc.move_to(station, carrying, kind) or 0.0)
    if up > 0.0:
        _log().info(f'{station} 상공에서 {up:.1f} mm 더 내려간다 (티칭 자세까지)')
        cc.move_rel(0.0, 0.0, -up, 'BASE')
    return up


def _via_home():
    """🚨 잔반통(로봇 **뒤**) ↔ 저울·스펀지 홈·반납 구역(**앞**) 사이는 HOME 을 거친다 (9/21 결정 E15).

    잔반통 그릇 자세를 뒤쪽으로 옮기면서 생긴 제약이다 — 앞쪽 자세가 팔이 쭉 펴진 특이점이라
    9/21 08:40 실기에서 6번 관절이 163° 돌아 그리퍼 케이블이 꼬였다.
    앞뒤로 곧장 가면 로봇 몸통을 가로지른다. E7 로 안전 높이 경유가 없어져 더 그렇다.
    """
    _goto('HOME', carrying=True)


def _hold(kind, level):
    """파지 힘 전환.

    🚨 드라이버에 '힘만 바꾸는 명령' 이 없어서 이건 **다시 잡기**다(RG2 매뉴얼 §6.2.3,
       gripper.py 머리말). 그래서 **힘을 낮추는 쪽(HOLD → NORMAL)에서만 미끄러진다** —
       미끄러짐 판정이 그 전환까지 덮도록 폭을 NORMAL 상태에서 재는 이유다(_slipped 참고).
    """
    cc.grip_level(kind, level)


def _release_hold(kind):
    """동작이 끝나면 파지 힘을 NORMAL 로 되돌린다.

    🔔 PR #32 D2 가 "HOLD 유지" 로 정해지면 **이 함수 본문만** 바꾼다(호출부는 그대로).
       flow 는 "단계 사이는 이미 NORMAL" 을 전제로 멈추므로(SDD §5.1) 그때 flow.py 주석과
       test_f2_sense.py 의 관련 시험도 같이 고쳐야 한다.
    """
    _quietly('grip_level(NORMAL)', _hold, kind, NORMAL)


def _slipped(label, w_before, w_after, tol):
    """동작 전후 그리퍼 폭이 tol 보다 변했으면 미끄러진 것. 🚨 기준은 여기 한 곳.

    🚨 두 폭은 **같은 힘(NORMAL) 상태에서** 재야 비교가 된다 — HOLD 는 더 세게 쥐어 폭이 다르다.
       그래서 w_before 는 HOLD 로 바꾸기 **전**, w_after 는 NORMAL 로 되돌린 **뒤**에 잰다.
       이렇게 하면 두 번의 힘 전환(올림·내림)이 **둘 다 검사 범위 안**에 들어온다.
    🚨 abs() 다 — 실제 낙하는 그리퍼가 닫히며 폭이 **줄어든다**(≈2 mm → 0). 늘어나는 쪽만 보면 못 잡는다.
    """
    changed = abs(w_after - w_before)
    if changed > tol:
        _log().warn(f'{label} — 폭이 {w_before:.2f} → {w_after:.2f} mm '
                    f'({changed:.2f} mm 변함 > 허용 {tol:.2f}) · 미끄러진 것으로 본다')
        return True
    return False


def _held_by_width(kind):
    """폭으로 **지금 용기를 쥐고 있나** 를 본다 → True / False / None(판정 불가).

    🚨 왜 무게가 아니라 폭인가 (9/22 18:11 실기): 무게는 **영점이 통째로 밀린다** —
       툴 무게 등록·TCP·브링업·케이블이 바뀌면 같은 자세에서 100 g 넘게 달라진다
       (그날 빈 그릇 기준값 −12 g 로 잰 자리에서 −117.5 g 이 읽혔다 · 그릇 자체는 47 g).
       그래서 "무게가 너무 가볍다 = 놓쳤다" 는 **기준값이 낡으면 거짓으로 뜬다**(그날 통합이 여기서 막혔다).
       그리퍼 폭은 영점(grip_zero_mm)이 기계의 성질이라 그 흔들림을 타지 않는다 —
       쥐었으면 벽 두께(2.15 mm)만큼 벌어져 있고, 놓쳤으면 빈손 영점까지 닫힌다.
    🚨 컵은 판정하지 않는다(결정 E19 ①) — 고정 폭 76 mm 까지만 닫아서 빈손과 구분이 안 된다 → None.
    """
    preset = ((cc.cfg().get('cell') or {}).get('presets') or {}).get(kind) or {}
    if preset.get('grip_target_mm') is not None:      # 컵 — E19
        return None
    zero, expect, tol = preset.get('grip_zero_mm'), preset.get('grip_width_mm'), preset.get('width_tol_mm')
    if None in (zero, expect, tol):
        return None
    try:
        got = float(cc.grip_width()) - float(zero)
    except Exception as e:                            # noqa: BLE001 — 못 읽으면 판정하지 않는다
        _log().warn(f'폭을 못 읽었다({e!r}) — 파지 판정을 건너뛴다')
        return None
    held = abs(got - float(expect)) <= float(tol)
    _log().info(f'폭으로 본 파지 — {got:.2f} mm (기대 {float(expect):.2f} ± {float(tol):.2f}) → '
                + ('쥐고 있다' if held else '빈손'))
    return held


# ────────────────────────────────────────────────────────── 공개 함수
@_as_result(WeighResult)
def weigh(kind: str) -> WeighResult:
    """무게를 잰다. 돌려주는 것은 **잔반 무게**(측정값 − 빈 용기 기준값)다.

    kind : 'BOWL'(그릇) 또는 'CUP'(컵)  ← IRD §2 의 문자열 그대로
    반환 : WeighResult (ok, code, weight_g = 잔반 g) · 용기를 놓쳤으면 GRIP_FAIL

    🚨 왜 '측정값' 이 아니라 '잔반 무게' 인가: 이 함수가 kind 를 받는 이유가
       **빈 용기 기준값을 고르기 위해서**다(SDD §5.3). 로봇 하중에는 원인 모를 옵셋이 있는데
       (V-02: +42~45 g), 같은 경로·같은 자세로 잰 빈 용기 값을 빼면 **옵셋이 상쇄된다**.
       그래서 params.yaml 의 empty_weight_g 는 저울 무게가 아니라 **이 경로로 읽은 값**이어야 한다.
    """
    conf = _f2()
    lim = _limits(conf)
    empties = conf.get('empty_weight_g')
    if not isinstance(empties, dict):
        raise KeyError('params.yaml 의 f2.empty_weight_g 가 없다 — 값을 채운다')
    empty = _need(empties, kind, where='f2.empty_weight_g')
    samples = _need(conf, 'weigh_samples', cast=int, lo=1)
    settle_s = _need(conf, 'weigh_settle_s', lo=0.0,
                     hi=_need(lim, 'max_settle_s', where='f2.limits'))
    min_net = _need(lim, 'min_net_g', where='f2.limits')

    _goto(_WEIGH_STATION, carrying=True, kind=kind)
    time.sleep(settle_s)                      # 🚨 움직이는 중에 재면 가속도가 섞인다(SDD §5.3)
    raw = float(cc.weigh(samples))            # cobot_common/weigh.py — 중앙값, 음수는 버린다

    net = raw - empty
    _log().info(f'weigh({kind}) — 읽음 {raw:.1f} g − 빈 용기 {empty:.1f} g = 잔반 {net:.1f} g')

    if net < min_net:
        # 🔄 9/22 저녁 변경: 여기서 **바로** GRIP_FAIL 하지 않는다. 무게는 영점이 밀리면 통째로 틀어지고
        #    (그날 −12 g 자리에서 −117.5 g), 그러면 멀쩡히 쥔 그릇을 "놓쳤다" 고 막는다 → 통합이 멈췄다.
        #    놓쳤는지는 **폭**이 곧바로 답한다(_held_by_width 머리말) → 폭에게 먼저 묻는다.
        held = _held_by_width(kind)
        if held is False:
            _log().warn(f'weigh({kind}) — 잔반 {net:.1f} g 이 하한 {min_net:.1f} g 보다 작고 '
                        '폭도 빈손이다 · 용기를 놓쳤다')
            return _fail(WeighResult, GRIP_FAIL, weight_g=net)
        if held is True:
            # 쥐고 있는데 무게만 이상하다 = **빈 용기 기준값이 낡았다**(툴 무게 등록·브링업·자세가 바뀌었다).
            _log().warn(
                f'weigh({kind}) — 잔반 {net:.1f} g 이 하한 {min_net:.1f} g 보다 작지만 **폭으로는 쥐고 있다** → '
                f'용기를 놓친 게 아니라 **빈 용기 기준값(f2.empty_weight_g.{kind} = {empty:.0f} g)이 틀어졌다.** '
                f'다시 잰다: rig_f2.py empty --kind {kind} · '
                '🚨 이번 잔반 판정은 믿을 수 없다 — 잔반 없음으로 지나간다')
            return WeighResult(weight_g=net)
        # 판정 불가(컵 E19 · 폭을 못 읽음) → 예전대로 무게만 보고 막는다
        _log().warn(f'weigh({kind}) — 잔반 {net:.1f} g 이 하한 {min_net:.1f} g 보다 작다 · '
                    '폭으로 확인할 수 없어(E19) 용기를 놓친 것으로 본다')
        return _fail(WeighResult, GRIP_FAIL, weight_g=net)
    return WeighResult(weight_g=net)


@_as_result(LeftoverResult)
def leftover_loop(kind: str, max_rounds: int) -> LeftoverResult:
    """잔반이 남았으면 털고 다시 재는 것을 반복한다(폐루프). **F2 의 핵심**.

    kind       : 'BOWL' / 'CUP'
    max_rounds : 최대 몇 번까지 털어볼지 (flow 가 params.yaml 의 flow.leftover_max_rounds 를 넘긴다)
    반환       : LeftoverResult (ok, code, weight_before_g, weight_after_g, rounds)

    흐름:  잰다 → 임계 미만이면 통과 → 넘으면 [털고 다시 잰다] × max_rounds → 그래도 넘으면
           LEFTOVER_REMAIN (flow 의 정책이 격리로 보낸다)

    🔔 알려진 한계: 이 함수 한 덩어리가 flow 기준 **한 단계**라, 도는 동안 정지 버튼을 못 본다
       (flow 는 단계 사이마다 본다 — SDD §5.1). 중단 훅을 받으려면 서명이 바뀌므로
       인터페이스 논의가 필요하다(AGENTS §3 규칙 5). 민범진이 이슈로 올림.
    """
    conf = _f2()
    threshold = _need(conf, 'leftover_threshold_g')
    cycles = _need(shake_params(conf, 'WASTE', kind), 'cycles', cast=int, lo=1,
                   where='f2.shake.WASTE')
    rounds_max = max(0, int(max_rounds))

    first = weigh(kind)
    if not first.ok:                                  # 재는 것부터 실패하면 그대로 올린다
        return LeftoverResult.fail(first.code, weight_before_g=first.weight_g)
    before = first.weight_g

    if before <= threshold:                           # SR-05·FR-04: 임계를 **초과**해야 잔반이다
        _log().info(f'leftover_loop({kind}) — {before:.1f} g ≤ 임계 {threshold:.1f} g · 통과')
        return LeftoverResult(weight_before_g=before, weight_after_g=before, rounds=0)

    after = before
    done = 0                                          # 🚨 **끝난** 회차 수 (실패한 회차는 안 센다)
    for r in range(1, rounds_max + 1):
        _log().info(f'leftover_loop({kind}) — 잔반 {after:.1f} g · 털기 {r}/{rounds_max}')
        _via_home()                                   # 🚨 E15: 저울(앞) → 잔반통(뒤)
        shaken = shake('WASTE', cycles, kind)
        if not shaken.ok:
            return LeftoverResult.fail(shaken.code, weight_before_g=before,
                                       weight_after_g=after, rounds=done)
        _via_home()                                   # 🚨 E15: 잔반통(뒤) → 저울(앞)
        again = weigh(kind)
        if not again.ok:
            return LeftoverResult.fail(again.code, weight_before_g=before,
                                       weight_after_g=after, rounds=done)
        done = r
        after = again.weight_g                        # weight_after_g = 마지막으로 **성공한** 측정값
        if after <= threshold:
            _log().info(f'leftover_loop({kind}) — {done}회 만에 {after:.1f} g · 통과')
            return LeftoverResult(weight_before_g=before, weight_after_g=after, rounds=done)

    _log().warn(f'leftover_loop({kind}) — {done}회 털었는데 아직 {after:.1f} g · 격리로 보낸다')
    return _fail(LeftoverResult, LEFTOVER_REMAIN, weight_before_g=before,
                 weight_after_g=after, rounds=done)


@_as_result(Result)
def shake(mode: str, count: int, kind: str) -> Result:
    """흔들어 턴다. 잔반통/수조 **위에서** 관절 하나를 왕복시킨다.

    mode  : 'WASTE'(잔반 털기) 또는 'RINSE'(물 털기) — **스테이션 이름과 같다**
    count : 흔들 횟수 (부르는 쪽이 정한다. leftover_loop 는 f2.shake.WASTE.cycles 를,
            flow 는 flow.counts.rinse_shakes 를 넘긴다)
    kind  : 'BOWL' / 'CUP'  ← 파지 힘 프리셋을 고르려고 받는다
    반환  : Result (미끄러지면 GRIP_FAIL)

    한 번 왕복 = 가운데 → +amp → −amp → 가운데. 🚨 **항상 가운데에서 끝난다** —
    도중에 실패해도 finally 가 남은 각도를 되돌린다(자세가 밀린 채 다음 용기로 가면 안 된다).

    🆕 9/22 물 털기 — **직선 왕복(axis · amp_mm)**: f2.shake.<mode> 에 `joint` 대신 `axis: x|y|z` 와 `amp_mm` 를 주면
       BASE 기준 그 축으로 ±amp_mm 왕복한다(가운데 → +amp → −amp → 가운데 · cc.move_rel). 관절 왕복과 같은 모양이고
       단위만 mm 다. 속도는 period_s 에 맞춘다(구간 거리 ÷ 구간 시간 · 상한은 move_rel 이 건다). 상한 f2.limits.max_amp_mm.
       `acc_mm_s2`(선택)를 주면 그 가속도로 — 짧은 왕복은 가속도가 "임팩트" 를 정한다(안 주면 move_rel 기본 = 들고 가는 30 %).
       상한은 cell.motion.acc_tcp_max_mm_s2 × vel_scale 로 move_rel 이 자른다.
       RINSE(물 털기) 가 이 방식 — 민범진 9/22 결정(그릇 입은 위 · 손목 회전 없이 앞뒤로).
    🆕 9/22 V-07 실기 — **기울이기(tilt_deg)**: 똑바로 든 채 ±15° 흔들면 그릇 입이 계속 위를 봐서 고형 잔반이
       안 쏟아진다. f2.shake.<mode>.tilt_deg 가 있으면 흔들기 **전에** 같은 관절을 그만큼 기울여(입이 잔반통 쪽으로)
       그 자세를 가운데 삼아 흔들고, 끝나면 되돌린다. 없거나 0 이면 예전 그대로(RINSE 물 털기는 안 기울인다).
       부호는 실기에서 정한다(어느 쪽이 잔반통 쪽인지는 자세마다 다르다). 상한 f2.limits.max_tilt_deg.
    """
    conf = _f2()
    lim = _limits(conf)
    p = shake_params(conf, mode, kind)                       # 🆕 종류별(BOWL/CUP) 묶음이 있으면 그것
    linear = p.get('axis') is not None                       # 🆕 직선 왕복(axis·amp_mm) 인가, 관절 왕복(joint·amp_deg) 인가
    if linear:
        axis = str(p.get('axis')).lower()
        if axis not in ('x', 'y', 'z'):
            raise ValueError(f'f2.shake.{mode}.axis = {p.get("axis")!r} — x·y·z 중 하나')
        amp = _need(p, 'amp_mm', lo=0.0, hi=_need(lim, 'max_amp_mm', where='f2.limits'),
                    where=f'f2.shake.{mode}')
        acc = _need(p, 'acc_mm_s2', lo=0.0, where=f'f2.shake.{mode}') if p.get('acc_mm_s2') is not None else None
        joint = None
    else:
        joint = _need(p, 'joint', cast=int, lo=1, hi=6, where=f'f2.shake.{mode}')
        amp = _need(p, 'amp_deg', lo=0.0, hi=_need(lim, 'max_amp_deg', where='f2.limits'),
                    where=f'f2.shake.{mode}')
    period = _need(p, 'period_s', lo=0.0, where=f'f2.shake.{mode}')
    slip_tol = _need(conf, 'slip_tol_mm')
    tilt = 0.0
    if p.get('tilt_deg') is not None:                        # 🆕 선택 — 있으면 상한까지 검사 (관절 왕복에만)
        if linear:
            raise ValueError(f'f2.shake.{mode}: 직선 왕복(axis)에는 tilt_deg 를 쓸 수 없다 — 기울일 관절이 없다')
        max_tilt = _need(lim, 'max_tilt_deg', where='f2.limits')
        tilt = _need(p, 'tilt_deg', lo=-max_tilt, hi=max_tilt, where=f'f2.shake.{mode}')
    n = int(count)

    if n <= 0:
        _log().warn(f'shake({mode}) — count={count} 라 아무것도 안 한다')
        return Result()

    _goto(mode, carrying=True, kind=kind)       # force_off 는 _goto 안에서 먼저 부른다

    # 🚨 폭은 **HOLD 로 바꾸기 전**에 잰다 — 두 번의 힘 전환을 모두 검사 범위에 넣으려고(_slipped).
    w_before = float(cc.grip_width())

    # 🚨 period_s 는 **한 주기** 시간이다. move_joint_rel 의 time_s 는 **한 번 움직이는 구간**의
    #    시간이라 나눠 줘야 한다(황인재 9/20): 가운데↔끝 = period/4, 끝↔반대끝 = period/2.
    #    그대로 넘기면 4배 느려진다.
    t_quarter = period / 4.0
    t_half = period / 2.0

    if linear:
        # 🆕 직선 왕복 — move_rel 은 시간이 아니라 속도를 받는다 → 구간 거리 ÷ 구간 시간. 상한은 move_rel 이 건다(100 % × vel_scale).
        vel = (amp / t_quarter) if t_quarter > 0 else None
        vec = {'x': (1.0, 0.0, 0.0), 'y': (0.0, 1.0, 0.0), 'z': (0.0, 0.0, 1.0)}[axis]

        def _step(d):                           # BASE 기준 d mm 만큼 그 축으로
            cc.move_rel(vec[0] * d, vec[1] * d, vec[2] * d, 'BASE', vel_mm_s=vel, acc_mm_s2=acc)
        what = f'{axis.upper()} ±{amp:.0f} mm' + (f' · 가속 {acc:.0f}' if acc else '')
    else:
        def _step(d, t=None):
            cc.move_joint_rel(joint, d, time_s=t, carrying=True)
        what = f'J{joint} ±{amp:.0f}°'

    moved = 0.0                                 # 가운데에서 얼마나 벗어나 있나 (실패 복구용)
    _hold(kind, HOLD)                           # 흔들 때는 더 꽉 잡는다 (IRD §4)
    try:
        if tilt:                                # 🆕 기울이기 — 들고 가는 속도(시간 지정 없음), 흔들기의 새 가운데
            _log().info(f'shake({mode}) — J{joint} {tilt:+.0f}° 기울인다 (입이 잔반통 쪽으로)')
            cc.move_joint_rel(joint, tilt, carrying=True)
            moved += tilt
        for i in range(1, n + 1):
            if linear:
                _step(+amp); moved += amp                                          # 가운데 → 끝
                _step(-2 * amp); moved -= 2 * amp                                  # 끝 → 반대쪽 끝
                _step(+amp); moved += amp                                          # 끝 → 가운데
            else:
                cc.move_joint_rel(joint, +amp, time_s=t_quarter, carrying=True)   # 가운데 → 끝
                moved += amp
                cc.move_joint_rel(joint, -2 * amp, time_s=t_half, carrying=True)  # 끝 → 반대쪽 끝
                moved -= 2 * amp
                cc.move_joint_rel(joint, +amp, time_s=t_quarter, carrying=True)   # 끝 → 가운데
                moved += amp
            _log().info(f'shake({mode}) {i}/{n} — {what} · 주기 {period:.2f} s')
        if tilt:                                # 🆕 아직 꽉 쥔 채 똑바로 되돌린다 (finally 는 실패용)
            cc.move_joint_rel(joint, -tilt, carrying=True)
            moved -= tilt
    finally:
        if abs(moved) > 1e-9:                   # 🚨 도중에 실패했으면 가운데로 되돌린다
            if linear:
                _quietly('가운데 복귀', cc.move_rel, -vec[0] * moved, -vec[1] * moved, -vec[2] * moved, 'BASE')
            else:
                _quietly('가운데 복귀', cc.move_joint_rel, joint, -moved)
        _release_hold(kind)

    w_after = float(cc.grip_width())            # NORMAL 로 되돌린 뒤 — w_before 와 같은 힘 상태
    if _slipped(f'shake({mode})', w_before, w_after, slip_tol):
        return _fail(Result, GRIP_FAIL)
    return Result()


@_as_result(Result)
def dip(station: str, count: int, kind: str) -> Result:
    """수조에 담갔다 뺀다. 🚨 **물은 쓰지 않는다 — 모션만**(로봇 보호등급 IP54).

    station : 'RINSE'(헹굼 수조) — f2.dip 아래의 이름과 같다
    count   : 담글 횟수
    kind    : 'BOWL' / 'CUP'
    반환    : Result (미끄러지면 GRIP_FAIL)

    티칭 자세(수조 위, 담그기 시작 자세)에서 **아래로 depth_mm** → hold_s 유지 → 같은 만큼 위로.
    🚨 **매번 올라와서 끝난다** — 도중에 실패해도 finally 가 내려간 만큼 되올린다.
       용기가 수조에 걸린 채 다음 이동으로 가면 안 된다(SDD §5.3).

    🔔 알려진 한계: 이 하강은 힘 감시가 없는 자유 공간 이동이다(물 없음 전제). 티칭이 어긋나거나
       수조가 밀리면 용기 바닥이 수조 바닥을 찍는다. cc.contact_down 으로 바꾸면 힘 상한·최대 깊이·
       타임아웃이 한꺼번에 붙지만 설계 변경이라 팀 확인이 필요하다. 지금은 max_depth_mm 상한으로만 막는다.
    """
    conf = _f2()
    lim = _limits(conf)
    p = _group(conf, 'dip', station)
    depth = _need(p, 'depth_mm', lo=0.0, hi=_need(lim, 'max_depth_mm', where='f2.limits'),
                  where=f'f2.dip.{station}')
    hold_s = _need(p, 'hold_s', lo=0.0, hi=_need(lim, 'max_hold_s', where='f2.limits'),
                   where=f'f2.dip.{station}')
    slip_tol = _need(conf, 'slip_tol_mm')
    n = int(count)

    if n <= 0:
        _log().warn(f'dip({station}) — count={count} 라 아무것도 안 한다')
        return Result()

    _goto(station, carrying=True, kind=kind)    # force_off 는 _goto 안에서 먼저 부른다

    w_before = float(cc.grip_width())           # HOLD 로 바꾸기 전 (shake 와 같은 이유)

    down = 0.0                                  # 지금 얼마나 내려가 있나 (실패 복구용)
    _hold(kind, HOLD)                           # 담그는 동안 더 꽉 잡는다 (IRD §4)
    try:
        for i in range(1, n + 1):
            cc.move_rel(0.0, 0.0, -depth, 'BASE')
            down = depth
            time.sleep(hold_s)
            cc.move_rel(0.0, 0.0, +depth, 'BASE')
            down = 0.0
            _log().info(f'dip({station}) {i}/{n} — {depth:.0f} mm 내려갔다 {hold_s:.1f} s 뒤 올라옴')
    finally:
        # 🚨 순서가 중요하다 — **아직 꽉 쥔 채** 먼저 올라오고, 그 다음에 힘을 되돌린다.
        if down > 0.0:
            _quietly('수조에서 올라오기', cc.move_rel, 0.0, 0.0, +down, 'BASE')
        _release_hold(kind)

    w_after = float(cc.grip_width())
    if _slipped(f'dip({station})', w_before, w_after, slip_tol):
        return _fail(Result, GRIP_FAIL)
    return Result()
