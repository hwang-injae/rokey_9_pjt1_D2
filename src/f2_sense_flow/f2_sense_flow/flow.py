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

    def __init__(self, cfg, log, publish_event=None, safe_retreat=None, features=None):
        self.cfg = (cfg or {}).get('flow', {})
        self.f = features or {}                  # {'f1': 모듈, 'f2': 모듈, 'f3': 모듈}
        self.log = log
        self._publish_event = publish_event or (lambda ev: None)
        self._safe_retreat = safe_retreat or (lambda: None)

        self.plan = self.cfg.get('plan', [])
        self.policy = self.cfg.get('policy', {})
        self.step_delay_s = self.cfg.get('step_delay_s', 0.0)

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

        self.target_bowl = sum(p['count'] for p in self.plan if p['kind'] == 'BOWL')
        self.target_cup = sum(p['count'] for p in self.plan if p['kind'] == 'CUP')

    # ────────────────────────────────── 상태 스냅샷
    def snapshot(self):
        """flow_node 가 FlowState 메시지로 옮겨 담을 값 모음."""
        return dict(
            step=self.step, kind=self.kind, zone_id=self.zone_id,
            done_bowl=self.done_bowl, done_cup=self.done_cup, isolated=self.isolated,
            target_bowl=self.target_bowl, target_cup=self.target_cup,
            sponge_uses=self.sponge_uses, soap_dips=self.soap_dips, rinse_dips=self.rinse_dips,
            last_code=self.last_code, message=self.message,
        )

    # ────────────────────────────────── 예외 보호 (SDD §5.1)
    def call(self, fn, *args):
        """기능 함수는 **반드시 여기를 지나서** 부른다. 항상 Result 를 돌려준다.

        프로세스가 하나라 함수 하나의 예외가 셀 전체를 멈춘다.
        예외가 나면 로그 → Result.fail(ROBOT_ERROR) 로 바꾸고 → safe_retreat() → PAUSED.
        """
        name = getattr(fn, '__name__', str(fn))
        try:
            r = fn(*args)
        except Exception as e:                    # noqa: BLE001 — 어떤 예외든 셀을 멈추면 안 된다
            # 🚨 KeyboardInterrupt 는 BaseException 이라 여기 안 걸린다 — 그게 맞다.
            #    Ctrl+C 는 그대로 위로 올라가 main() 의 finally 가 cc.shutdown() 을 부른다.
            self.log.error(f'{name} 에서 예외 — {e!r}')
            self._safe_retreat()
            self.message = f'{name}: {e}'
            r = Result.fail(ROBOT_ERROR)
        self.last_code = r.code
        if not r.ok:
            self.log.warn(f'{name} 실패 → {r.code}')
        return r

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
    def to_paused(self, why=''):
        if self.step != 'PAUSED':
            self._prev_step = self.step
        self.step = 'PAUSED'
        self.log.warn(f'PAUSED — resume 을 기다린다{(" · " + why) if why else ""}')

    def wait_resume(self, sig):
        """resume 을 기다린다. 기다리는 동안에도 /flow/state 는 계속 나간다.

        Ctrl+C 로 끝내려면 여기서 KeyboardInterrupt 가 올라가 main() 의 finally 로 간다.
        """
        while not sig.take('resume'):
            time.sleep(_POLL_S)
        sig.clear('stop')
        self.step = self._prev_step
        self.log.info(f'resume — {self.step} 부터 다시')
        return True

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
                # 🚨 기능 함수 호출 **사이**에서만 정지한다 (IRD §6)
                if sig.peek('stop'):
                    self.log.info('stop 요청 — 정지')
                    self.to_paused('stop 버튼')
                    self.wait_resume(sig)
                outcome = self.process_one(sig)
                if outcome == HALT:
                    return
                if outcome == SKIP_ZONE:        # 구역이 비었다 → 남은 count 를 버리고 다음 구역
                    break
        self.step, self.kind, self.zone_id = 'DONE', '', ''
        self.log.info(f'plan 완료 — 그릇 {self.done_bowl} · 컵 {self.done_cup} · 격리 {self.isolated}')
        self.step = 'IDLE'

    def process_one(self, sig):
        """용기 1개 처리. 계속하려면 True.

        순서는 IRD §8. 모듈은 use_mock 에 따라 진짜/가짜가 들어와 있다(load_features).
        """
        f1, f2, f3 = self.f.get('f1'), self.f.get('f2'), self.f.get('f3')
        bed = 'SPONGE_BED_B' if self.kind == 'BOWL' else 'SPONGE_BED_C'
        tool_id = 'SPONGE' if self.kind == 'BOWL' else 'BRUSH'
        wipe = f3.wipe_bowl if self.kind == 'BOWL' else f3.wipe_cup
        rounds = self.cfg.get('leftover_max_rounds') or 2
        self.rack_slot = self._next_slot()

        # (단계, 부를 함수, 인자)
        steps = [
            ('PICK', f1.pick, (self.zone_id, self.kind)),
            ('WEIGH', f1.move_to, ('WEIGH', True)),
            ('WEIGH', f2.leftover_loop, (self.kind, rounds)),
            ('SEAT', f1.place, (bed,)),
            ('SOAP', f1.tool, (tool_id, 'PICK')),
            ('SOAP', f3.soap, (self.cfg.get('soap_dips_per_item', 3),)),
            ('WIPE', wipe, ()),
            ('WIPE', f1.tool, (tool_id, 'RETURN')),
            ('RINSE', f1.pick, (bed, self.kind)),
            ('RINSE', f2.dip, ('RINSE', 1, self.kind)),
            ('RINSE', f2.shake, ('RINSE', 3, self.kind)),
            ('RACK', f1.rack_place, (self.rack_slot, self.kind)),
            ('RACK', f1.move_to, ('HOME', False)),
        ]
        for step, fn, args in steps:
            self.step = step
            r = self.call(fn, *args)
            if not r.ok:
                action, retries = self.policy_for(r.code)
                # retry:N->isolate — 후퇴한 뒤 같은 동작을 N 번까지 다시 해 본다
                for i in range(retries):
                    self.log.info(f'{step} 재시도 {i + 1}/{retries} (코드 {r.code})')
                    self._safe_retreat()
                    r = self.call(fn, *args)
                    if r.ok:
                        break
                if not r.ok:
                    return self.handle_failure(sig, action)
            self.pause_between()

        if self.kind == 'BOWL':
            self.done_bowl += 1
        else:
            self.done_cup += 1
        self.sponge_uses += 1
        self.rinse_dips += 1
        self.emit_event('DONE')
        return GO_ON

    def _next_slot(self):
        """팔레트 칸 배정 — rack_order 순서대로. 다 차면 마지막 칸(실제 판정은 F1 이 RACK_FULL)."""
        order = (self.cfg.get('rack_order') or {}).get(self.kind) or []
        done = self.done_bowl if self.kind == 'BOWL' else self.done_cup
        return order[done] if done < len(order) else (order[-1] if order else '')

    def handle_failure(self, sig, action=None):
        """실패를 정책대로 마무리한다 (재시도는 process_one 이 이미 끝냈다).

        돌려주는 값: GO_ON(다음 용기) · SKIP_ZONE(이 구역 그만) · HALT(중단)
        """
        if action is None:
            action, _ = self.policy_for(self.last_code)

        if action == PAUSE:
            self.to_paused(f'코드 {self.last_code}')
            return GO_ON if self.wait_resume(sig) else HALT

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
        self._publish_event(dict(kind=self.kind, zone_id=self.zone_id,
                                 rack_slot=self.rack_slot if result == 'DONE' else '',
                                 result=result, code=self.last_code))
