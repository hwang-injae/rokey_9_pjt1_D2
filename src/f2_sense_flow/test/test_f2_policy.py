"""실패 정책이 params.yaml 설정대로 동작하는지 — TC-10 의 바탕.

🚨 로봇·브링업·ROS 없이 돈다. flow.py 가 ROS 를 import 하지 않게 나눠 둔 덕분이다.
실제 TC-10 은 flow_node 를 띄워 HMI·Ctrl+C 까지 확인한다(9/22 UT-FLOW).
"""
import threading
import types

import pytest

from cobot_api import F1Api, F2Api, F3Api, GRIP_FAIL, Result
from f2_sense_flow import mock
from f2_sense_flow.flow import _POLL_S, Flow, Signals, load_features

# 깃발을 들여다보는 간격(_POLL_S)의 몇 배만 기다려 보고 "아직 안 풀렸다" 를 판정한다.
SETTLE_S = _POLL_S * 6
# 🚨 스레드를 쓰는 시험은 **반드시** 상한을 둔다 — 안 풀리는 버그가 무한 대기가 되면 안 된다.
TIMEOUT_S = _POLL_S * 100

CFG = {'flow': {
    'plan': [{'zone': 'RET_B', 'kind': 'BOWL', 'count': 2},
             {'zone': 'RET_C', 'kind': 'CUP', 'count': 2}],
    'rack_order': {'BOWL': ['RACK_B1', 'RACK_B2'],
                   'CUP': ['RACK_C1', 'RACK_C2']},
    'policy': {'EMPTY_ZONE': 'next_zone', 'LEFTOVER_REMAIN': 'isolate', 'SEAT_FAIL': 'isolate',
               'FORCE_LIMIT': 'retry:1->isolate', 'TIMEOUT': 'retry:1->isolate',
               'RACK_JAM': 'retry:1->isolate', 'TOOL_FAIL': 'retry:1->isolate',
               'RACK_FULL': 'pause', 'ROBOT_ERROR': 'pause',
               'GRIP_FAIL': 'pause'},          # 9/20 결정 E12 — params.yaml 과 같은 값
    'counts': {'soap_dips': 3, 'rinse_dips': 1, 'rinse_shakes': 3},
    'step_delay_s': 0.0,
    'done_hold_s': 0.0,     # 시험에서는 기다리지 않는다
}}


class Quiet:
    def info(self, m): pass
    def warn(self, m): pass
    def error(self, m): pass


class AutoResume(Signals):
    """시험용 — resume 을 자동으로 눌러 준다.

    운영 중에는 PAUSED 에서 사람이 재개할 때까지 기다리는 게 맞다(SDD §5.1).
    하지만 시험에서는 예상 못 한 PAUSE 가 **무한 대기**가 되어 버그를 숨긴다.
    자동으로 재개시켜 두면 "왜 멈췄나"가 assert 실패로 드러난다.
    """

    def take(self, name):
        if name == 'resume':
            return True
        return super().take(name)


def run(fail_on):
    """가짜 기능으로 plan 한 바퀴. (이벤트 결과들, flow) 를 돌려준다."""
    mock.configure(fail_on)
    events = []
    f = Flow(CFG, Quiet(), publish_event=events.append)
    f.f = load_features(['f1', 'f2', 'f3'])
    f.run_plan(AutoResume())
    return [e['result'] for e in events], f


@pytest.fixture(autouse=True)
def _clean():
    yield
    mock.reset()


def test_no_failure_completes_all():
    results, f = run([])
    assert results == ['DONE'] * 4
    assert (f.done_bowl, f.done_cup, f.isolated) == (2, 2, 0)


def test_seat_fail_isolates():
    """SEAT_FAIL → isolate. 격리하고 다음 용기로 간다."""
    results, f = run(['place:SEAT_FAIL'])
    assert results == ['ISOLATED'] * 4
    assert f.isolated == 4 and f.done_bowl == 0


def test_empty_zone_skips_rest_of_zone():
    """🚨 EMPTY_ZONE 은 용기 1개가 아니라 **구역 전체**를 포기한다 (IRD §8).

    구역이 2개이므로 SKIPPED 는 4건이 아니라 2건이어야 한다.
    """
    results, f = run(['pick:EMPTY_ZONE'])
    assert results == ['SKIPPED', 'SKIPPED']
    assert f.isolated == 0


def test_retry_recovers():
    """retry:1->isolate — 한 번 실패해도 재시도가 성공하면 정상 완료."""
    results, f = run(['rack_place:RACK_JAM:1'])
    assert results == ['DONE'] * 4
    assert f.isolated == 0


def test_retry_exhausted_isolates():
    """재시도를 다 써도 실패하면 격리."""
    results, f = run(['rack_place:RACK_JAM'])
    assert results == ['ISOLATED'] * 4
    assert f.isolated == 4


def test_retreat_failure_stops_retry_and_pauses():
    """🚨 후퇴가 실패하면 **재시도하지 않는다** — 로봇이 어디 있는지 모르는 채로
    같은 동작을 다시 하면 위험하다. 격리(옮기기)도 하지 않고 사람을 기다린다.
    """
    def boom():
        raise NotImplementedError('아직 구현 전이다')

    mock.configure(['rack_place:RACK_JAM'])          # 재시도 정책을 타게 만든다
    f = Flow(CFG, Quiet(), safe_retreat=boom)
    f.f = load_features(['f1', 'f2', 'f3'])
    f.run_plan(AutoResume())                         # 예외가 새면 여기서 깨진다
    assert f.last_code == 'ROBOT_ERROR'
    assert f.isolated == 0, '로봇 위치를 모르는데 격리로 옮기면 안 된다'


def test_rack_slot_assignment():
    """팔레트 칸은 rack_order 순서대로 배정된다."""
    f = Flow(CFG, Quiet())
    f.kind = 'BOWL'
    assert f._next_slot() == 'RACK_B1'
    f.done_bowl = 1
    assert f._next_slot() == 'RACK_B2'


def _recorder(mod, api, called):
    """약속(F?Api)에 있는 함수만 감싸서 호출 이름을 기록한다.

    모듈의 모든 callable 을 감싸면 클래스·상수까지 건드려 깨진다 — 약속된 이름만 쓴다.
    """
    ns = types.SimpleNamespace()
    for name in (n for n in dir(api) if not n.startswith('_')):
        fn = getattr(mod, name)
        setattr(ns, name, (lambda n, g: lambda *a: (called.append(n), g(*a))[1])(name, fn))
    return ns


def test_full_order_calls_every_function():
    """IRD §8 순서대로 f1·f2·f3 함수가 모두 불린다 (빠뜨린 단계가 없는지)."""
    called = []
    mock.configure([])
    mods = load_features(['f1', 'f2', 'f3'])
    f = Flow(CFG, Quiet())
    f.f = {'f1': _recorder(mods['f1'], F1Api, called),
           'f2': _recorder(mods['f2'], F2Api, called),
           'f3': _recorder(mods['f3'], F3Api, called)}
    f.plan = [{'zone': 'RET_B', 'kind': 'BOWL', 'count': 1}]
    f.run_plan(AutoResume())
    assert f.step != 'PAUSED', '예상 못 한 PAUSE — 어딘가에서 예외가 났다'
    for need in ('pick', 'move_to', 'leftover_loop', 'place', 'tool',
                 'soap', 'wipe_bowl', 'dip', 'shake', 'rack_place'):
        assert need in called, f'{need} 가 안 불렸다'


# ────────────────────────────────── stop 위치 (9/20 V-20 결함 · SDD §5.1)
class StopAfter(AutoResume):
    """resume 을 눌러 줄 때 "그때까지 몇 단계가 갔는지" 를 기록하는 시험용 깃발."""

    def __init__(self):
        super().__init__()
        self.calls = []
        self.calls_at_pause = None

    def take(self, name):
        if name == 'resume' and self.calls_at_pause is None:
            self.calls_at_pause = len(self.calls)
        return super().take(name)


def test_stop_pauses_between_steps():
    """🚨 정지 버튼은 **단계 사이마다** 먹어야 한다 — 용기 하나를 끝까지 하고서가 아니라.

    V-20(황인재 9/20)에서 "stop 뒤에도 RINSE·RACK 을 더 갔다" 로 드러난 결함.
    실기에서는 함수 하나가 수십 초라, 이게 없으면 정지 버튼이 소프트 E-STOP 이 못 된다.
    """
    mock.configure([])
    f = Flow(CFG, Quiet())
    f.f = load_features(['f1', 'f2', 'f3'])
    f.plan = [{'zone': 'RET_B', 'kind': 'BOWL', 'count': 1}]

    sig = StopAfter()
    orig = f.call_fn

    def counting(mod_key, fn_name, *args):
        r = orig(mod_key, fn_name, *args)
        sig.calls.append(fn_name)
        if len(sig.calls) == 3:              # 용기 중간(3단계째)에서 정지 버튼을 누른다
            sig.raise_('stop')
        return r

    f.call_fn = counting
    f.run_plan(sig)

    assert sig.calls_at_pause is not None, 'stop 을 눌렀는데 PAUSED 가 안 됐다'
    assert sig.calls_at_pause == 3, \
        f'stop 뒤에 {sig.calls_at_pause - 3} 단계를 더 갔다 — 단계 사이에서 멈춰야 한다'
    assert f.step != 'PAUSED', 'resume 뒤 끝까지 가야 한다'
    assert len(sig.calls) == 13, f'resume 뒤 남은 단계를 다 못 갔다 ({len(sig.calls)}/13)'


def test_stop_does_not_touch_the_gripper():
    """🚨 멈출 때 그리퍼에 **아무 명령도 보내지 않는다** (SDD §5.1 · 황인재 9/20).

    든 채 멈추는 구간이 생기는데, 힘을 바꾸면 드라이버가 다시 파지하면서 놓칠 수 있다.
    기능 함수가 끝날 때 HOLD → NORMAL 로 되돌리므로 단계 사이는 이미 NORMAL 이다.
    """
    import inspect

    from f2_sense_flow import flow as flow_mod

    src = inspect.getsource(flow_mod.Flow.process_one) + inspect.getsource(flow_mod.Flow.run_plan)
    body = '\n'.join(ln for ln in src.splitlines() if not ln.lstrip().startswith('#'))
    for banned in ('grip_level', 'release(', 'grip('):
        assert banned not in body, f'정지 경로에서 그리퍼를 건드린다: {banned}'


# ────────────────────────────────── 미리 눌린 resume (감사 결함 A)
def _in_thread(fn):
    """fn 을 딴 스레드에서 돌리고 (끝났는지 알려 주는 Event, 반환값 리스트) 를 준다.

    🚨 시험용이다. 운영에서 로봇 함수는 메인 스레드에서만 부른다(SDD §3.2) —
       여기서는 가짜 모듈만 돌리고, "기다리는 쪽" 을 시험이 붙잡지 않으려고 쓴다.
    """
    done, out = threading.Event(), []

    def body():
        try:
            out.append(fn())
        finally:
            done.set()

    threading.Thread(target=body, daemon=True).start()
    return done, out


def test_pre_pressed_resume_does_not_release_next_pause():
    """🚨 **멈추기 전에** 눌린 resume 이 다음 PAUSED 를 풀면 안 된다.

    resume 깃발은 소비될 때까지 남는다. 운전 중에 눌렸거나 한 번의 정지에서 두 번 눌린
    resume 이 그대로 걸려 있다가, 다음에 진짜로 PAUSED 가 되는 순간 사람이 아무것도 안 했는데
    재개시켜 버린다. ROBOT_ERROR·RACK_FULL 처럼 사람이 확인해야 하는 정지(SDD §7)가
    0 초 만에 풀리면 안 된다 — wait_resume 은 **멈춘 뒤에 눌린** 재개만 받는다.
    """
    f = Flow(CFG, Quiet())
    sig = Signals()
    sig.raise_('resume')                     # 운전 중(아직 PAUSED 가 아닐 때) 눌린 재개

    # 실제 코드가 부르는 방식 그대로 — to_paused 가 'PAUSED' 로 바꾸기 **전**에 resume 을 지운다.
    # (지우는 자리를 wait_resume 으로 옮기면 그 사이에 들어온 정당한 resume 이 조용히 사라진다)
    f.to_paused('시험', sig)
    done, _ = _in_thread(lambda: f.wait_resume(sig))

    assert not done.wait(SETTLE_S), '미리 눌린 resume 으로 정지가 풀렸다 — 사람이 누르지 않았다'
    assert f.step == 'PAUSED'

    sig.raise_('resume')                     # 이제 사람이 진짜로 누른다
    assert done.wait(TIMEOUT_S), '사람이 resume 을 눌렀는데도 재개되지 않았다'
    assert f.step != 'PAUSED'


def test_pre_pressed_resume_does_not_skip_stop_between_steps():
    """미리 눌린 resume 이 **단계 사이 stop**(9/20 V-20 수정)까지 무력화하면 안 된다.

    운전 중에 resume, 그 뒤에 stop 을 누른 상황 — 정지 버튼이 소프트 E-STOP 노릇을 하려면
    사람이 다시 누를 때까지 그 자리에 서 있어야 한다.
    """
    mock.configure([])
    f = Flow(CFG, Quiet())
    f.f = load_features(['f1', 'f2', 'f3'])
    f.zone_id, f.kind = 'RET_B', 'BOWL'

    sig = Signals()
    sig.raise_('resume')                     # 운전 중에 미리 눌린 재개
    sig.raise_('stop')                       # 그 뒤에 정지 버튼

    done, out = _in_thread(lambda: f.process_one(sig))

    assert not done.wait(SETTLE_S), '미리 눌린 resume 이 stop 을 그냥 통과시켰다'
    assert f.step == 'PAUSED'

    sig.raise_('resume')
    assert done.wait(TIMEOUT_S), 'resume 을 눌렀는데 용기를 끝까지 처리하지 않았다'
    assert out == ['go_on'] and f.done_bowl == 1


# ────────────────────────────────── 재시도 중 코드가 바뀐 경우 (감사 결함 B)
class PauseWatcher(AutoResume):
    """PAUSED 를 몇 번 거쳤는지 세는 시험용 깃발 (resume 은 AutoResume 처럼 눌러 준다)."""

    def __init__(self):
        super().__init__()
        self.resumes = 0

    def take(self, name):
        if name == 'resume':
            self.resumes += 1
        return super().take(name)


def test_new_code_in_retry_uses_new_policy():
    """🚨 재시도에서 **다른 코드**로 실패하면 그 코드의 정책으로 마무리한다.

    1차 RACK_JAM(retry:1->isolate) → 재시도에서 기능 함수가 예외를 던져 ROBOT_ERROR.
    첫 실패 코드로 정한 옛 정책(isolate)을 그대로 쓰면 params.yaml 의 ROBOT_ERROR: pause 를
    무시하고 격리해 버린다 — 로봇 위치를 모르는 채 격리함까지 이송하게 된다.
    SDD §7 은 ROBOT_ERROR 를 "그 자리 정지 → PAUSED + 알림, 사람이 복구" 로 못 박는다.
    """
    mock.configure(['rack_place:RACK_JAM'])          # 1차는 RACK_JAM 으로 실패
    mods = load_features(['f1', 'f2', 'f3'])
    tries = []

    def rack_place(rack_slot, kind):
        tries.append(rack_slot)
        if len(tries) > 1:                           # 재시도에서 드라이버가 터진다 → ROBOT_ERROR
            raise RuntimeError('드라이버 응답 없음')
        return mods['f1'].rack_place(rack_slot, kind)

    f1 = types.SimpleNamespace(**{n: getattr(mods['f1'], n)
                                  for n in dir(F1Api) if not n.startswith('_')})
    f1.rack_place = rack_place

    events = []
    f = Flow(CFG, Quiet(), publish_event=events.append)
    f.f = {'f1': f1, 'f2': mods['f2'], 'f3': mods['f3']}
    f.plan = [{'zone': 'RET_B', 'kind': 'BOWL', 'count': 1}]

    sig = PauseWatcher()
    f.run_plan(sig)

    assert len(tries) == 2, f'재시도 정책(retry:1)을 안 탔다 (시도 {len(tries)}회)'
    assert f.last_code == 'ROBOT_ERROR'
    assert f.isolated == 0, 'ROBOT_ERROR 를 격리로 처리하면 안 된다 — 로봇 위치를 모른다'
    assert sig.resumes >= 1, 'ROBOT_ERROR 인데 PAUSED 를 거치지 않았다 (SDD §7)'
    # 9/20 PM 결정: ROBOT_ERROR 로 멈춘 용기**만** ERROR 로 기록한다
    # (GRIP_FAIL·RACK_FULL 은 재개하면 마저 해서 DONE 이 된다 — 아래 시험)
    assert [e['result'] for e in events] == ['ERROR'], 'ROBOT_ERROR 로 멈춘 용기는 ERROR 로 남는다'


def test_resume_redoes_the_failed_step():
    """🚨 GRIP_FAIL 로 멈춘 뒤 재개하면 **실패한 그 단계부터 다시** 한다 (IRD §8 · 9/20 결정 E12).

    전에는 재개해도 GO_ON(다음 용기)이라 **그 용기를 버렸다** — 사람이 가서 다시 쥐여 줬는데도
    버리는 셈이라, 재개 버튼과 중단 버튼이 똑같이 동작했다.
    """
    mock.configure([])
    mods = load_features(['f1', 'f2', 'f3'])
    tries = []

    def dip(station, count, kind):
        tries.append(station)
        if len(tries) == 1:                          # 첫 담금에서 미끄러짐
            return Result.fail(GRIP_FAIL)
        return mods['f2'].dip(station, count, kind)

    f2 = types.SimpleNamespace(**{n: getattr(mods['f2'], n)
                                  for n in dir(F2Api) if not n.startswith('_')})
    f2.dip = dip

    events = []
    f = Flow(CFG, Quiet(), publish_event=events.append)
    f.f = {'f1': mods['f1'], 'f2': f2, 'f3': mods['f3']}
    f.plan = [{'zone': 'RET_B', 'kind': 'BOWL', 'count': 1}]

    sig = PauseWatcher()
    f.run_plan(sig)

    assert sig.resumes >= 1, 'GRIP_FAIL 인데 PAUSED 를 거치지 않았다 (E12)'
    assert len(tries) == 2, f'재개 뒤 같은 단계를 다시 하지 않았다 (dip {len(tries)}회)'
    assert f.isolated == 0, 'GRIP_FAIL 은 격리가 아니다 — 놓친 용기는 손에 없을 수 있다 (E12)'
    assert [e['result'] for e in events] == ['DONE'], '마저 해서 끝났으면 DONE 이다'


def test_resume_after_robot_error_goes_to_next_container():
    """🚨 ROBOT_ERROR 만은 재개해도 **그 단계를 다시 하지 않는다** (IRD §8 · SDD §7).

    로봇이 어디 있는지 모르는 채 같은 동작을 다시 하면 위험하다 → 다음 용기부터, 그 용기는 ERROR.
    """
    mods = load_features(['f1', 'f2', 'f3'])
    tries = []

    def dip(station, count, kind):
        tries.append(station)
        raise RuntimeError('드라이버 응답 없음')       # 기능 함수에서 샌 예외 → ROBOT_ERROR

    f2 = types.SimpleNamespace(**{n: getattr(mods['f2'], n)
                                  for n in dir(F2Api) if not n.startswith('_')})
    f2.dip = dip

    events = []
    f = Flow(CFG, Quiet(), publish_event=events.append)
    f.f = {'f1': mods['f1'], 'f2': f2, 'f3': mods['f3']}
    f.plan = [{'zone': 'RET_B', 'kind': 'BOWL', 'count': 1}]

    f.run_plan(PauseWatcher())

    assert len(tries) == 1, 'ROBOT_ERROR 인데 같은 단계를 다시 했다 — 위험하다'
    assert [e['result'] for e in events] == ['ERROR']
    assert f.isolated == 0, 'ROBOT_ERROR 를 격리로 옮기면 안 된다'
