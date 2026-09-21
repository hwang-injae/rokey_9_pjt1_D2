# -*- coding: utf-8 -*-
"""flow — 공정의 **두뇌** (민범진). 상태 머신·구역 계획·실패 정책.

🚨 이 파일은 ROS 를 import 하지 않는다.
   통신(서비스·토픽·타이머)은 flow_node.py 가 맡는다. 여기는 "무엇을 어떤 순서로, 실패하면 어떻게"만 다룬다.
   그래서 로봇·브링업·ROS 없이 pytest 로 정책을 시험할 수 있다(TC-10).

바깥과 닿는 곳은 생성자로 주입받는 4개뿐이다:
    cfg            설정(dict) — cobot_common.config.load() 결과
    log            로그 객체 (.info/.warn/.error)
    publish_event  용기 1개가 끝날 때 부를 함수. dict 한 개를 받는다
    safe_retreat   위험할 때 물러나는 함수 (cobot_common.safe_retreat)

문서: docs/03_설계_SDD.md §5.1(상태 머신) · docs/02_인터페이스_IRD.md §8(호출 순서·실패 정책)
"""
import re
import threading
import time

from cobot_api import OK, ROBOT_ERROR, Result

# ── 실패 정책 (params.yaml flow.policy 의 값 문자열) ─────────────────────
NEXT_ZONE = 'next_zone'          # 구역 종료 → 다음 구역 (기록 SKIPPED)
ISOLATE = 'isolate'              # 격리함에 넣고 다음 용기
RETRY = 'retry'                  # 후퇴 후 N회 재시도 → 그래도 실패면 격리
PAUSE = 'pause'                  # 멈추고 사람을 기다린다

_RETRY_RE = re.compile(r'^retry:(\d+)->isolate$')   # "retry:1->isolate" (SDD §4.3 · IRD §8)

_POLL_S = 0.05                   # 깃발을 들여다보는 간격

# process_one 의 결과 — run_plan 이 다음에 뭘 할지
GO_ON = 'go_on'                  # 이 구역의 다음 용기로
SKIP_ZONE = 'skip_zone'          # 이 구역은 그만, 다음 구역으로 (EMPTY_ZONE)
HALT = 'halt'                    # 전부 중단 (Ctrl+C 등)
# wait_resume 이 돌려주는 값 — 사람이 PAUSED 에서 무엇을 눌렀나
RESUMED = 'resumed'              # 재개 (이어서)
ABORTED = 'aborted'              # 중단 (이 용기를 접고 다음 용기)
# handle_failure 만 돌려주는 값 — run_plan 까지 올라가지 않고 process_one 이 그 자리에서 쓴다
RETRY_STEP = 'retry_step'        # 재개 — **실패한 그 단계부터 다시** (IRD §8 · 9/20 PM 결정)

# 기능 이름 → (진짜 모듈 경로, 가짜 모듈 경로)
_MODULES = {
    'f1': ('f1_handling.handling', 'f2_sense_flow.mock.mock_f1'),
    'f2': ('f2_sense_flow.sense', 'f2_sense_flow.mock.mock_f2'),
    'f3': ('f3_wipe.wipe', 'f2_sense_flow.mock.mock_f3'),
}


def load_features(use_mock, log=None):
    """use_mock 에 있는 기능은 가짜 모듈을, 나머지는 진짜 모듈을 쓴다 (IRD §10).

    진짜 패키지가 아직 없으면 무엇을 해야 하는지 알려 주고 멈춘다 —
    알 수 없는 ImportError 로 끝나지 않게 한다.
    """
    import importlib
    mods = {}
    for name, (real, fake) in _MODULES.items():
        path = fake if name in use_mock else real
        try:
            mods[name] = importlib.import_module(path)
        except ModuleNotFoundError as e:
            if name in use_mock:
                raise
            raise RuntimeError(
                f'{name} 의 진짜 모듈 {path} 이 없다 ({e.name}). '
                f'아직 안 만들어졌으면 params.yaml 의 flow.use_mock 에 "{name}" 을 넣거나 '
                f'런치 인자 use_mock 에 넣는다.') from e
        if log:
            log.info(f'  {name} → {path}{" (가짜)" if name in use_mock else ""}')
    return mods


class Signals:
    """HMI 버튼이 세우는 깃발. 통신 스레드가 세우고 메인 스레드가 읽는다.

    🚨 두 스레드가 같이 만지므로 Lock 으로 감싼다(한 번에 한 스레드만).
       콜백은 여기 깃발만 세우고 로봇 함수를 부르지 않는다 (SDD §3.2 규칙 ③).
    """

    def __init__(self):
        self._lock = threading.Lock()
        self.start = False
        self.stop = False
        self.resume = False
        self.abort = False               # 🆕 중단 — PAUSED 에서만 (IRD §6 · 결정 E11)

    def raise_(self, name):
        with self._lock:
            setattr(self, name, True)

    def take(self, name):
        """깃발을 읽고 내린다(한 번만 반응하도록)."""
        with self._lock:
            v = getattr(self, name)
            setattr(self, name, False)
            return v

    def peek(self, name):
        with self._lock:
            return getattr(self, name)

    def clear(self, name):
        with self._lock:
            setattr(self, name, False)


class Flow:
    """상태 + 구역 계획 + 실패 정책."""

    def __init__(self, cfg, log, publish_event=None, safe_retreat=None, features=None,
                 force_off=None, no_retreat_errors=(),
                 is_paused=None, halt=None, clear_halt=None, halt_errors=()):
        self.cfg = (cfg or {}).get('flow', {})
        self.f = features or {}                  # {'f1': 모듈, 'f2': 모듈, 'f3': 모듈}
        self.log = log
        self._publish_event = publish_event or (lambda ev: None)
        self._safe_retreat = safe_retreat or (lambda: None)
        # 🚨 후퇴를 **하면 안 되는** 예외들 (9/21 결정 · SDD §7). flow 는 로봇을 모르므로
        #    클래스와 함수를 flow_node 가 넣어 준다 — cc.MoveIncomplete · cc.force_off.
        #    이동이 도중에 서면 로봇이 어디 있는지 모른다 → Z 를 올리는 후퇴가 더 위험하다
        #    (9/21 08:40 케이블 꼬임과 같은 길). 힘·순응만 끄고 그 자리에서 사람을 기다린다.
        self._force_off = force_off or (lambda: None)
        self._no_retreat_errors = tuple(no_retreat_errors or ())
        # 🆕 FLOW-03 — 정지·재개·중단 (IRD §6). flow 는 로봇을 모르므로 flow_node 가 넣어 준다.
        #    cc.is_paused : 이동 **도중** 멈춰 있는가 (메인 스레드는 그때 기능 함수 안에 갇혀 있다)
        #    cc.halt      : 그 자세 그대로 강제 정지 — 중단할 때 하던 이동을 끊는다
        self._is_paused = is_paused or (lambda: False)
        self._halt = halt or (lambda: None)
        self._clear_halt = clear_halt or (lambda: None)
        self.holding_tool = None         # 쥐고 있는 툴 이름 — 중단 정리에서 반납한다
        # 🚨 cc.MotionHalted — 중단을 누르면 하던 이동이 이걸로 끊긴다. 평범한 실패가 아니라
        #    **중단 흐름**으로 보낸다(PM 9/21). ROBOT_ERROR 로 처리하면 사람이 또 확인해야 한다.
        self._halt_errors = tuple(halt_errors or ())
        self._halted = False

        # 🚨 설정은 **여기서 한 번에** 읽고 검증한다.
        #    YAML 에 키만 있고 값이 비면 None 이 들어온다(`or` 로 받아야 한다).
        #    공정 도중에 KeyError·TypeError 로 죽으면 용기를 쥔 채 멈춘다.
        self.plan = self._check_plan(self.cfg.get('plan') or [])
        self.policy = self.cfg.get('policy') or {}
        self.rack_order = self.cfg.get('rack_order') or {}
        self.counts = self._check_counts(self.cfg.get('counts') or {})
        self.rounds = self._num('leftover_max_rounds', 2, int)
        # DONE 을 화면에 보여 주는 시간. /flow/state 주기(state_pub_hz)보다 길어야 한 번은 잡힌다
        self.done_hold_s = self._num('done_hold_s', 1.0, float)
        self.step_delay_s = self._num('step_delay_s', 0.0, float)
        # /flow/state 발행 주기. 0·음수면 타이머를 만들 수 없다(1/0) → 기본값으로 되돌린다
        self.state_pub_hz = self._num('state_pub_hz', 2.0, float)
        if self.state_pub_hz <= 0:
            self.log.warn(f'flow.state_pub_hz 가 {self.state_pub_hz} 다 — 0 보다 커야 한다 → 2.0 으로 본다')
            self.state_pub_hz = 2.0

        # ── 상태 (flow_node 가 2 Hz 로 읽어 /flow/state 로 내보낸다) ──
        self.step = 'IDLE'
        self.kind = ''
        self.zone_id = ''
        self.last_code = OK
        self.message = ''
        self.rack_slot = ''                      # 이번 용기가 들어간 팔레트 칸
        self.done_bowl = 0
        self.done_cup = 0
        self.isolated = 0
        self.sponge_uses = 0
        self.soap_dips = 0
        self.rinse_dips = 0
        self._prev_step = 'IDLE'

        self.target_bowl = sum(e['count'] for e in self.plan if e['kind'] == 'BOWL')
        self.target_cup = sum(e['count'] for e in self.plan if e['kind'] == 'CUP')

    # ────────────────────────────────── 설정 검증 (생성자에서만)
    def _num(self, key, default, cast):
        """숫자 설정 하나를 읽는다. 없거나 숫자가 아니면 기본값 + 경고.

        🚨 `cfg.get(k) or 기본값` 으로 쓰면 **0 을 설정할 수 없다**(0 은 거짓이라 기본값으로 바뀐다).
           그래서 None 인지만 따로 본다.
        """
        raw = self.cfg.get(key)
        if raw is None:
            return default
        try:
            return cast(raw)
        except (TypeError, ValueError):
            self.log.warn(f'flow.{key} 가 숫자가 아니다 ({raw!r}) → {default} 으로 본다')
            return default

    def _check_plan(self, plan):
        """plan 항목을 검사해 쓸 수 있는 것만 남긴다. 나쁜 항목은 버리고 알려 준다."""
        good = []
        for i, e in enumerate(plan):
            try:
                zone, kind, count = str(e['zone']), str(e['kind']), int(e['count'])
            except (TypeError, KeyError, ValueError) as err:
                self.log.error(f'flow.plan[{i}] 을 읽을 수 없다 ({err!r}) — 이 항목은 건너뛴다')
                continue
            if kind not in ('BOWL', 'CUP') or count < 0:
                self.log.error(f'flow.plan[{i}] 값이 이상하다 (kind={kind}, count={count}) — 건너뛴다')
                continue
            good.append({'zone': zone, 'kind': kind, 'count': count})
        if not good:
            self.log.warn('flow.plan 에 쓸 수 있는 항목이 없다 — start 를 눌러도 아무것도 하지 않는다')
        return good

    def _check_counts(self, counts):
        """횟수 설정이 빠졌으면 **시작할 때** 알려 주고 기본값으로 채운다."""
        out = {}
        for key, default in (('soap_dips', 3), ('rinse_dips', 1), ('rinse_shakes', 3)):
            try:
                out[key] = int(counts[key])
            except (TypeError, KeyError, ValueError):
                self.log.warn(f'flow.counts.{key} 가 없거나 숫자가 아니다 → {default} 으로 본다')
                out[key] = default
        return out

    # ────────────────────────────────── 상태 스냅샷
    def snapshot(self):
        """flow_node 가 FlowState 메시지로 옮겨 담을 값 모음.

        🟡 락이 없다. 통신 스레드가 읽는 동안 메인 스레드가 값을 바꿀 수 있어,
           한 스냅샷 안에서 step 과 카운터가 서로 다른 순간의 값일 수 있다.
           파이썬 속성 읽기는 원자적이라 깨진 값은 안 나오고, 2 Hz 로 다시 보내므로
           0.5 초 안에 맞춰진다. 표시용이라 그대로 둔다(락을 잡으면 통신 스레드가
           메인 스레드의 로봇 동작을 기다리게 되어 더 나쁘다).
        """
        # 🚨 이동 **도중** 멈추면 메인 스레드가 기능 함수 안에 갇혀 있어 step 을 못 바꾼다.
        #    그대로 두면 HMI 가 'WEIGH' 를 계속 보여 준다 → 깃발을 보고 PAUSED 로 알린다(IRD §6).
        step = 'PAUSED' if self._is_paused() else self.step
        return dict(
            step=step, kind=self.kind, zone_id=self.zone_id,
            done_bowl=self.done_bowl, done_cup=self.done_cup, isolated=self.isolated,
            target_bowl=self.target_bowl, target_cup=self.target_cup,
            sponge_uses=self.sponge_uses, soap_dips=self.soap_dips, rinse_dips=self.rinse_dips,
            last_code=self.last_code, message=self.message,
        )

    # ────────────────────────────────── 바깥 세계를 부르는 통로
    def _guard(self, fn, *args, what):
        """주입받은 콜러블(safe_retreat·publish_event)을 부르는 **유일한** 통로.

        🚨 Flow 는 이것들을 직접 부르지 않는다. 프로세스가 하나라 여기서 새어 나간
           예외 하나가 셀 전체를 멈춘다. PR #8 리뷰에서 실제로 죽는 것이 확인됐다
           (flow.py:271 → cobot_common.safe_retreat 의 NotImplementedError → 프로세스 종료).
        """
        try:
            fn(*args)
            return True
        except Exception as e:                # noqa: BLE001 — 무엇이 터지든 셀을 멈추면 안 된다
            try:
                self.log.error(f'{what} 실패 — {e!r}')
            except Exception:                 # noqa: BLE001 — 로그가 터져도 통로는 안 샌다
                pass
            return False

    def _retreat(self):
        """안전 자세로 물러난다. 실패하면 False.

        🚨 후퇴가 실패하면 **로봇이 어디 있는지 알 수 없다.** 그 상태로 같은 동작을
           다시 하면 위험하므로, 부르는 쪽은 재시도하지 말고 PAUSED 로 사람을 기다린다.
        """
        if self._guard(self._safe_retreat, what='safe_retreat'):
            return True
        self.last_code = ROBOT_ERROR
        self.message = '후퇴 실패 — 로봇 위치를 알 수 없다. 사람이 확인해야 한다'
        return False

    # ────────────────────────────────── 예외 보호 (SDD §5.1)
    def call(self, fn, *args):
        """기능 함수는 **반드시 여기를 지나서** 부른다. 항상 Result 를 돌려준다.

        프로세스가 하나라 함수 하나의 예외가 셀 전체를 멈춘다.
        예외가 나면 로그 → Result.fail(ROBOT_ERROR) 로 바꾸고 → safe_retreat() → PAUSED.
        """
        name = getattr(fn, '__name__', str(fn))
        try:
            r = fn(*args)
            # 🚨 반환값 확인도 try 안에서 한다. 뼈대 단계의 함수가 None·tuple 을 돌려주면
            #    r.code 접근이 call() **자신**을 죽인다(보호 통로가 뚫리는 셈).
            if not isinstance(r, Result):
                raise TypeError(f'Result 가 아니라 {type(r).__name__} 을 돌려줬다')
            code, ok = r.code, r.ok
        except Exception as e:                    # noqa: BLE001 — 어떤 예외든 셀을 멈추면 안 된다
            # 🚨 KeyboardInterrupt 는 BaseException 이라 여기 안 걸린다 — 그게 맞다.
            #    Ctrl+C 는 그대로 위로 올라가 main() 의 finally 가 cc.shutdown() 을 부른다.
            try:
                self.log.error(f'{name} 에서 예외 — {e!r}')
                self.message = f'{name}: {e}'
            except Exception:                     # noqa: BLE001 — 로그가 터져도 여기서 끝낸다
                self.message = f'{name}: (메시지를 만들 수 없음)'
            # 🚨 두 갈래다 (9/21 결정 · SDD §7)
            #    ① 이동이 도중에 선 예외(cc.MoveIncomplete) → **후퇴하지 않는다.**
            #       로봇이 어디 있는지 모르는데 Z 를 올리면 더 꼬인다 → 힘·순응만 끄고 사람이 확인.
            #    ② 그 밖(힘 상한 ForceLimitError 등) → 설계대로 후퇴한다. 접촉에서 벗어나야 한다.
            if self._halt_errors and isinstance(e, self._halt_errors):
                # 🆕 중단(/flow/abort)이 하던 이동을 끊었다 — 실패가 아니라 사람이 시킨 것이다.
                #    후퇴하지 않는다(곧 HOME 으로 간다). process_one 이 중단 정리로 넘긴다.
                self.log.warn(f'{name} — 중단 요청으로 끊겼다')
                self.message = '중단 요청으로 멈췄습니다'
                self._halted = True
            elif self._no_retreat_errors and isinstance(e, self._no_retreat_errors):
                self.log.error(f'{name} — 로봇 위치를 알 수 없다. 후퇴하지 않고 힘·순응만 끈다')
                self.message = f'{name}: 이동이 도중에 멈췄습니다 — 로봇 위치를 확인하세요'
                self._guard(self._force_off, what='force_off')
            else:
                self._retreat()                   # 후퇴가 또 터져도 _guard 가 삼킨다
            r = Result.fail(ROBOT_ERROR)
            code, ok = r.code, r.ok
        self.last_code = code
        if not ok:
            self.log.warn(f'{name} 실패 → {code}')
        return r

    def call_fn(self, mod_key, fn_name, *args):
        """기능 모듈에서 함수를 **찾는 것까지** 보호한다.

        🚨 getattr 을 call() 밖에서 하면, 진짜 모듈에 함수 하나가 없을 때
           AttributeError 가 그대로 프로그램을 죽인다(한석형 f1_handling 이 만들어지는 중이면 실제로 난다).
        """
        def resolve_and_call(*a):
            mod = self.f.get(mod_key)
            if mod is None:
                raise RuntimeError(f'{mod_key} 모듈이 없다 (use_mock 설정을 확인한다)')
            fn = getattr(mod, fn_name, None)
            if not callable(fn):
                raise AttributeError(f'{mod_key}.{fn_name} 이 없다')
            return fn(*a)
        resolve_and_call.__name__ = f'{mod_key}.{fn_name}'
        return self.call(resolve_and_call, *args)

    # ────────────────────────────────── 실패 정책
    def policy_for(self, code):
        """실패 코드에 대해 무엇을 할지 → (동작, 재시도 횟수).

        params.yaml 의 값 형식 (SDD §4.3 · IRD §8):
            next_zone · isolate · pause · "retry:N->isolate"
        모르는 코드·모르는 값은 **안전하게 PAUSE** 한다 — 조용히 넘어가면 안 된다.
        """
        action = self.policy.get(code)
        if action is None:
            self.log.warn(f'policy 에 없는 코드 {code} → pause 로 처리')
            return PAUSE, 0
        if action in (NEXT_ZONE, ISOLATE, PAUSE):
            return action, 0
        m = _RETRY_RE.match(str(action))
        if m:
            return RETRY, int(m.group(1))
        self.log.warn(f'policy 에 모르는 값 "{action}" (코드 {code}) → pause 로 처리')
        return PAUSE, 0

    # ────────────────────────────────── 일시 정지 / 재개
    def to_paused(self, why='', sig=None):
        """PAUSED 로 들어간다. sig 를 주면 그동안 남아 있던 resume 깃발을 함께 내린다.

        🚨 지우는 자리가 중요하다 — **step 을 'PAUSED' 로 바꾸기 전**이다.
           깃발은 take() 로 소비될 때까지 남아서, 운전 중(PAUSED 가 아닐 때) 눌렸거나
           한 번의 정지에서 두 번 눌린 resume 이 **다음** PAUSED 를 사람이 아무것도 안 했는데
           0 초 만에 풀어 버린다(SDD §7 — ROBOT_ERROR·RACK_FULL 은 사람이 확인해야 한다.
           후퇴가 실패해 로봇 위치를 모르는 상태에서도 계속 움직이게 된다).

           **왜 wait_resume 이 아니라 여기인가**: flow_node 의 /flow/resume 은
           `step == 'PAUSED'` 일 때만 깃발을 세운다(두 번째 방어선). 그래서 지우는 자리가
           'PAUSED' 로 바꾼 **뒤**이면, 그 사이에 들어온 **정당한** resume 을 지워 버린다 —
           HMI 는 '재개합니다' 를 받았는데 아무 일도 안 일어난다. 바꾸기 **전**에 지우면
           그 틈의 resume 은 노드가 'PAUSED 가 아닙니다' 로 **분명히 거절**한다.
           조용히 사라지는 것보다 거절이 낫다.
        """
        if sig is not None:
            sig.clear('resume')                       # 🚨 'PAUSED' 로 바꾸기 **전**에
        if self.step != 'PAUSED':
            self._prev_step = self.step
        self.step = 'PAUSED'
        self.log.warn(f'PAUSED — resume 을 기다린다{(" · " + why) if why else ""}')

    def wait_resume(self, sig):
        """resume 을 기다린다. 기다리는 동안에도 /flow/state 는 계속 나간다.

        Ctrl+C 로 끝내려면 여기서 KeyboardInterrupt 가 올라가 main() 의 finally 로 간다.

        🚨 재개 지점을 로그로 주장하지 않는다. `_prev_step` 은 **끝난** 단계라,
           "그 단계부터 다시" 라고 찍으면 거짓이 된다 — 부르는 자리마다 재개 지점이 다르다:
             · stop(단계 사이) → 멈춘 **다음** 단계부터   (멈출 때 "… 앞에서 정지" 로 이미 찍는다)
             · stop(용기 사이) → 다음 용기의 PICK 부터
             · 실패 PAUSE      → 이 용기를 접고 **다음 용기**부터 (handle_failure 가 GO_ON)
           self.step 복원은 HMI 가 PAUSED 에 머무르지 않게 하려는 것뿐이다.
        """
        # 🚨 여기서 resume 을 지우지 않는다 — 지우는 것은 to_paused 가 'PAUSED' 로
        #    바꾸기 **전**에 한다(이유는 to_paused 주석). 여기서 지우면 to_paused 와
        #    이 줄 사이에 들어온 **정당한** resume 이 조용히 사라진다.
        while True:
            if sig.take('abort'):                     # 🆕 사람이 "이 용기는 접자" 고 판단했다
                sig.clear('stop')
                self.log.warn('abort — 이 용기를 접고 다음 용기로 간다')
                return ABORTED
            if sig.take('resume'):
                sig.clear('stop')
                self.step = self._prev_step
                self.log.info('resume — 이어서 진행한다')
                return RESUMED
            time.sleep(_POLL_S)

    def abort_container(self, sig):
        """🆕 중단(/flow/abort) — 이 용기를 접고 **다음 용기**로 간다 (IRD §6 · 결정 E11).

        순서: 강제정지 풀기 → **HOME 먼저** → 툴 반납 → 용기를 격리 구역에 → HOME
        🚨 HOME 이 먼저인 이유: 결정 E7 로 이동에서 안전 높이 경유가 없어져 **지금 자리에서
           다음 자리로 곧장** 간다. 중단은 아무 때나 눌리므로 티칭 경로의 출발점에서 시작한다.
        🚨 한 단계가 실패해도 **멈추지 않는다** — 치우는 중이라 더 나아가는 편이 낫다.
           다만 그 결과는 로그에 남긴다. 마지막에 이벤트는 ISOLATED 다.
        """
        self.step = 'ISOLATE'
        self._clear_halt()                            # 중단 때 세운 강제정지를 푼다(안 풀면 새 이동도 거부된다)

        def step(what, mod, fname, *args):
            r = self.call_fn(mod, fname, *args)
            if not r.ok:
                self.log.error(f'중단 정리 — {what} 실패({r.code}). 그래도 계속 치운다')
            return r

        step('HOME 복귀', 'f1', 'move_to', 'HOME', True)
        if self.holding_tool:
            step('툴 반납', 'f1', 'tool', self.holding_tool, 'RETURN')
            self.holding_tool = None
        step('격리 구역에 놓기', 'f1', 'place', 'ISOLATE', self.kind)
        step('HOME 복귀', 'f1', 'move_to', 'HOME', False)

        self.isolated += 1
        self.emit_event('ISOLATED')
        return GO_ON

    # ────────────────────────────────── 메인 루프 (메인 스레드에서만)
    def run(self, sig):
        """메인 스레드. Ctrl+C 면 KeyboardInterrupt 가 올라가 main() 의 finally 가 정리한다."""
        self.log.info('IDLE — /flow/start 를 기다린다')
        while True:
            if sig.take('start'):
                self.run_plan(sig)
            time.sleep(_POLL_S)

    def run_plan(self, sig):
        """plan 대로 구역을 돈다."""
        sig.clear('stop')
        for entry in self.plan:
            self.zone_id, self.kind = entry['zone'], entry['kind']
            for _ in range(entry['count']):
                # 용기와 용기 사이. 단계 사이의 정지는 process_one 안에 따로 있다 (SDD §5.1)
                if sig.peek('stop'):
                    self.log.info('stop 요청 — 용기 사이에서 정지')
                    self.to_paused('stop 버튼', sig)
                    self.wait_resume(sig)
                outcome = self.process_one(sig)
                if outcome == HALT:
                    return
                if outcome == SKIP_ZONE:        # 구역이 비었다 → 남은 count 를 버리고 다음 구역
                    break
        self.step, self.kind, self.zone_id = 'DONE', '', ''
        self.log.info(f'plan 완료 — 그릇 {self.done_bowl} · 컵 {self.done_cup} · 격리 {self.isolated}')
        # 🚨 곧바로 IDLE 로 덮으면 2 Hz 타이머가 DONE 을 한 번도 못 보고 HMI 에 완료가 안 뜬다.
        #    발행 주기보다 길게 머무른다.
        time.sleep(self.done_hold_s)
        self.step = 'IDLE'

    def process_one(self, sig):
        """용기 1개 처리. 계속하려면 True.

        순서는 IRD §8. 모듈은 use_mock 에 따라 진짜/가짜가 들어와 있다(load_features).
        """
        bowl = self.kind == 'BOWL'
        bed = 'SPONGE_BED_B' if bowl else 'SPONGE_BED_C'
        tool_id = 'SPONGE' if bowl else 'BRUSH'
        wipe_fn = 'wipe_bowl' if bowl else 'wipe_cup'
        rounds = self.rounds
        n = self.counts
        self.rack_slot = self._next_slot()

        # (단계, 모듈, 함수이름, 인자) — 🚨 함수 객체를 미리 꺼내지 않는다.
        #    꺼내는 것까지 call_fn 안에서 해야 "함수가 없다"가 크래시가 아니라 Result 가 된다.
        steps = [
            ('PICK', 'f1', 'pick', (self.zone_id, self.kind)),
            # 🚨 kind 를 넘긴다 — WEIGH 자세는 종류별로 다르다(9/20 E8·PR #36). 없으면 ValueError
            ('WEIGH', 'f1', 'move_to', ('WEIGH', True, self.kind)),
            ('WEIGH', 'f2', 'leftover_loop', (self.kind, rounds)),
            ('SEAT', 'f1', 'place', (bed,)),
            ('SOAP', 'f1', 'tool', (tool_id, 'PICK')),
            ('SOAP', 'f3', 'soap', (n['soap_dips'], self.kind)),   # SOAP 자세도 종류별 (9/20 E8)
            ('WIPE', 'f3', wipe_fn, ()),
            ('WIPE', 'f1', 'tool', (tool_id, 'RETURN')),
            ('RINSE', 'f1', 'pick', (bed, self.kind)),
            ('RINSE', 'f2', 'dip', ('RINSE', n['rinse_dips'], self.kind)),
            ('RINSE', 'f2', 'shake', ('RINSE', n['rinse_shakes'], self.kind)),
            ('RACK', 'f1', 'rack_place', (self.rack_slot, self.kind)),
            ('RACK', 'f1', 'move_to', ('HOME', False)),
        ]
        # 🚨 for 가 아니라 while 이다 — PAUSED 에서 재개하면 **실패한 그 단계부터 다시** 해야 해서
        #    같은 자리를 한 번 더 돌 수 있어야 한다(IRD §8 · 9/20 PM 결정). for 로는 못 돌아온다.
        i = 0
        while i < len(steps):
            step, mod, fname, args = steps[i]
            # 🚨 stop 은 **단계 사이마다** 본다 (SDD §5.1 — 9/20 V-20 에서 찾은 결함).
            #    여기가 없으면 정지 버튼을 눌러도 용기 하나(실기 수십 초)를 끝까지 하고서야 멈춘다.
            #    용기·툴을 **든 채** 멈출 수 있다 → 🚨 그리퍼에 **아무 명령도 보내지 않는다**.
            #    (기능 함수가 끝날 때 HOLD → NORMAL 로 되돌리므로 단계 사이는 이미 NORMAL 이다.
            #     여기서 힘을 바꾸면 드라이버가 다시 파지하면서 놓칠 수 있다 — 황인재 9/20)
            #    resume 하면 이 단계부터 이어 간다.
            if sig.peek('stop') or self._is_paused():
                self.log.info(f'stop 요청 — {step} 앞에서 정지')
                self.to_paused('stop 버튼', sig)
                if self.wait_resume(sig) == ABORTED:  # 🆕 재개 대신 중단을 눌렀다
                    return self.abort_container(sig)
            self.step = step
            r = self.call_fn(mod, fname, *args)
            if self._halted:                          # 🆕 중단으로 끊긴 것 — 정책을 타지 않는다
                self._halted = False
                return self.abort_container(sig)
            if r.ok and fname == 'tool':               # 쥐고 있는 툴을 기억한다(중단 정리에서 반납)
                self.holding_tool = args[0] if args[1] == 'PICK' else None
            if not r.ok:
                action, retries = self.policy_for(r.code)
                # retry:N->isolate — 후퇴한 뒤 같은 동작을 N 번까지 다시 해 본다
                for i in range(retries):
                    self.log.info(f'{step} 재시도 {i + 1}/{retries} (코드 {r.code})')
                    if not self._retreat():   # 🚨 후퇴 실패 → 더 움직이지 않는다
                        action = PAUSE
                        break
                    r = self.call_fn(mod, fname, *args)
                    if r.ok:
                        break
                if not r.ok:
                    # 🚨 재시도 중에 **실패 코드가 바뀌었을 수 있다** (예: 1차 FORCE_LIMIT →
                    #    재시도에서 기능 함수가 터져 ROBOT_ERROR). 첫 실패 코드로 정한 옛 정책으로
                    #    마무리하면 params.yaml 의 ROBOT_ERROR: pause 를 무시하고 격리해 버려,
                    #    로봇 위치를 모르는 채 격리함까지 이송하게 된다.
                    #    SDD §7 은 ROBOT_ERROR 를 "그 자리 정지 → PAUSED + 알림, 사람이 복구" 로 못 박는다.
                    #    → 마무리 직전에 **최신 코드**로 정책을 다시 읽는다.
                    #    단 action 이 이미 PAUSE 면 다시 읽지 않는다 — 후퇴 실패로 강제한 PAUSE 라
                    #    (위 `if not self._retreat()`) 덮어쓰면 다시 움직이게 된다.
                    #    다시 읽은 값이 (RETRY, n) 이어도 그대로 넘긴다 — handle_failure 가
                    #    "ISOLATE, 그리고 재시도를 다 쓴 RETRY" 를 같은 갈래로 처리한다.
                    if action != PAUSE:
                        action, _ = self.policy_for(r.code)
                    outcome = self.handle_failure(sig, action)
                    if outcome != RETRY_STEP:
                        return outcome
                    continue                    # i 를 안 올린다 → 실패한 그 단계를 다시
            self.pause_between()
            i += 1

        if self.kind == 'BOWL':
            self.done_bowl += 1
        else:
            self.done_cup += 1
        self.sponge_uses += 1
        self.soap_dips += n['soap_dips']
        self.rinse_dips += n['rinse_dips']
        self.emit_event('DONE')
        return GO_ON

    def _next_slot(self):
        """팔레트 칸 배정 — rack_order 순서대로. 다 차면 마지막 칸(실제 판정은 F1 이 RACK_FULL)."""
        order = self.rack_order.get(self.kind) or []
        done = self.done_bowl if self.kind == 'BOWL' else self.done_cup
        return order[done] if done < len(order) else (order[-1] if order else '')

    def handle_failure(self, sig, action=None):
        """실패를 정책대로 마무리한다 (재시도는 process_one 이 이미 끝냈다).

        돌려주는 값: RETRY_STEP(그 단계부터 다시) · GO_ON(다음 용기) · SKIP_ZONE(이 구역 그만) · HALT(중단)
        """
        if action is None:
            action, _ = self.policy_for(self.last_code)

        if action == PAUSE:
            self.to_paused(f'코드 {self.last_code}', sig)
            answer = self.wait_resume(sig)
            if answer == ABORTED:                     # 🆕 사람이 이 용기를 접기로 했다
                return self.abort_container(sig)
            # 🚨 ROBOT_ERROR 만 예외 — 로봇이 어디 있는지 모르는 채 같은 단계를 다시 하면 위험하다.
            #    사람이 복구한 뒤 resume 하면 **다음 용기부터**이고 그 용기는 ERROR 로 기록한다
            #    (IRD §8 · SDD §7 · 9/20 PM 결정). 후퇴가 실패해 강제된 PAUSE 도 여기로 온다 —
            #    그때 last_code 는 ROBOT_ERROR 다(_retreat 실패).
            if self.last_code == ROBOT_ERROR:
                self.emit_event('ERROR')
                return GO_ON
            # 그 밖(GRIP_FAIL·RACK_FULL)은 사람이 확인·조치한 뒤 **실패한 그 단계부터** 이어 간다.
            #    끝까지 가면 DONE 으로 기록되므로 여기서는 이벤트를 내지 않는다(9/20 PM 결정).
            #    다시 실패하면 또 PAUSED 가 된다 — 풀려면 사람이 resume 을 눌러야 하므로 혼자 돌지 않는다.
            #    사람이 "이 용기는 접자" 고 판단하면 /flow/abort 다(IRD §6 — 아직 구현 전).
            self.log.info(f'재개 — {self.step} 단계부터 다시 (코드 {self.last_code})')
            return RETRY_STEP

        if action == NEXT_ZONE:                 # 구역이 비었다 — 남은 count 도 의미 없다
            self.emit_event('SKIPPED')
            return SKIP_ZONE

        # ISOLATE, 그리고 재시도를 다 쓴 RETRY
        self.step = 'ISOLATE'
        self.isolated += 1
        self.emit_event('ISOLATED')
        return GO_ON

    def pause_between(self):
        if self.step_delay_s:
            time.sleep(self.step_delay_s)

    def emit_event(self, result):
        """용기 1개가 끝날 때마다 1건 (IRD §7 FlowEvent).

        🚧 attempts·weight_*_g·duration_s·force_log_path 는 FLOW-02(기록)에서 채운다 —
           각 단계의 Result 를 모아야 해서 여기 구조가 좀 더 필요하다.
        """
        self._guard(self._publish_event,
                    dict(kind=self.kind, zone_id=self.zone_id,
                         rack_slot=self.rack_slot if result == 'DONE' else '',
                         result=result, code=self.last_code),
                    what='publish_event')      # 발행이 터져도 공정은 계속된다
