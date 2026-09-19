# -*- coding: utf-8 -*-
"""flow_node — PreWash-Cell 의 **메인 프로그램** (민범진). 통신 **배선**만 맡는다.

이 셀에서 노드는 둘뿐이다: flow_node(여기)와 hmi_bridge(황인재).
f1·f2·f3 는 노드가 아니라 그냥 함수이고, 이 파일의 **메인 스레드**가 차례로 부른다.

왜 이렇게 하나 (TS-01 · SDD §3.2):
    두산 API 는 "혼자 위에서 아래로 도는 스크립트"를 전제로 만들어졌다. 로봇 명령마다 자기가
    실행기를 돌려 응답을 기다리므로, **서비스 콜백 안에서 부르면 교착**한다.
    그래서 로봇을 움직이는 코드는 전부 메인 스레드에서 차례로 실행한다.

     ┌ 메인 스레드      : flow.run() → 기능 함수 호출        ← 로봇은 여기서만
     ├ 통신 노드 스레드 : Io — 서비스·타이머·발행기
     │                    🚨 콜백은 **깃발만** 세운다 (규칙 ③)
     └ DSR 전용 노드    : cobot_common 이 관리 (우리는 안 건드린다)

Ctrl+C 는 cobot_common.init() 이 단독으로 맡는다 (SDD §3.1, PR #3).
  → 여기서는 signal.signal 을 걸지 않고 **try/finally 로 cc.shutdown() 만** 부른다.

실행 (SDD §10):
    ros2 launch prewash_bringup prewash.launch.py vel_scale:=0.3      # 실기
    ros2 launch prewash_bringup prewash_mock.launch.py                # 전부 가짜, 드라이버 없이
    PREWASH_USE_MOCK=f1,f3 ros2 run f2_sense_flow flow_node           # 손으로 돌릴 때

🚨 flow_node 에는 name=·namespace=·--ros-args -r __node:= 를 주지 않는다 (SDD §10).
   프로세스 안의 두 노드(flow_node · flow_node_dsr)에 모두 걸려 이름이 같아진다.
"""
import functools
import logging

import cobot_common as cc
from cobot_common import config as cc_config
from cobot_msgs.msg import FlowEvent, FlowState
from std_srvs.srv import Trigger

from f2_sense_flow.flow import Flow, Signals, load_features

FEATURES = ('f1', 'f2', 'f3')


def safe_cb(what):
    """ROS 콜백을 감싼다 — 🚨 콜백에서 예외가 나가면 **통신이 영구히 죽는다.**

    rclpy 의 SingleThreadedExecutor 는 콜백 예외를 spin() 밖으로 다시 던지고,
    cobot_common 의 spin 스레드는 그것을 잡아 로그만 남기고 **스레드를 끝낸다.**
    그러면 프로세스는 살아 있는데 /flow/state 가 멈추고 start·stop·resume 이
    영원히 응답하지 않는다 — 메인 스레드는 로봇을 계속 움직이는데 정지 버튼이 안 먹는다.
    """
    def deco(fn):
        @functools.wraps(fn)
        def wrapped(self, *a, **kw):
            try:
                return fn(self, *a, **kw)
            except Exception as e:                # noqa: BLE001 — 통신 스레드를 죽이면 안 된다
                try:
                    self.log.error(f'{what} 콜백에서 예외 — {e!r} (통신은 계속한다)')
                except Exception:                 # noqa: BLE001
                    pass
                return a[1] if len(a) > 1 else None   # 서비스면 응답 객체를 그대로 돌려준다
        return wrapped
    return deco


class Io:
    """통신 배선 — /flow/* 서비스 3개, /flow/state 타이머, /flow/event 발행기.

    🚨 콜백에서 하는 일은 **깃발 세우기와 값 읽기뿐**이다. 로봇 함수를 부르지 않는다.
       콜백에서 로봇을 움직이면 TS-01 의 교착이 그대로 되살아난다.
    """

    def __init__(self, node, flow, sig):
        self.node, self.flow, self.sig = node, flow, sig
        self.log = node.get_logger()

        node.create_service(Trigger, '/flow/start', self._on_start)
        node.create_service(Trigger, '/flow/stop', self._on_stop)
        node.create_service(Trigger, '/flow/resume', self._on_resume)
        self.state_pub = node.create_publisher(FlowState, '/flow/state', 10)
        self.event_pub = node.create_publisher(FlowEvent, '/flow/event', 10)

        self.rate_hz = flow.state_pub_hz          # Flow 가 이미 검증했다(0·음수·문자열 → 2.0)
        node.create_timer(1.0 / self.rate_hz, self._on_state_timer)

    # ────────────────────────────────── 서비스 콜백 (깃발만!)
    @safe_cb('/flow/start')
    def _on_start(self, req, res):
        if self.flow.step == 'IDLE':
            self.sig.raise_('start')
            res.success, res.message = True, '시작합니다'
        else:
            res.success, res.message = False, f'IDLE 이 아닙니다 (현재 {self.flow.step})'
        return res                                   # 즉시 응답. 실행은 메인 스레드가 한다

    @safe_cb('/flow/stop')
    def _on_stop(self, req, res):
        self.sig.raise_('stop')
        res.success, res.message = True, '현재 동작이 끝나면 정지합니다'
        return res

    @safe_cb('/flow/resume')
    def _on_resume(self, req, res):
        self.sig.raise_('resume')
        res.success, res.message = True, '재개합니다'
        return res

    # ────────────────────────────────── 상태 발행 (메시지만 만든다)
    @safe_cb('/flow/state 타이머')
    def _on_state_timer(self):
        s = self.flow.snapshot()
        m = FlowState()
        for k, v in s.items():
            setattr(m, k, v)
        m.stamp = self.node.get_clock().now().to_msg()
        self.state_pub.publish(m)

    @safe_cb('/flow/event')
    def publish_event(self, ev):
        """flow(두뇌)가 용기 1개를 끝낼 때마다 부른다. dict → 메시지로 옮긴다."""
        m = FlowEvent()
        m.stamp = self.node.get_clock().now().to_msg()
        for k, v in ev.items():
            setattr(m, k, v)
        self.event_pub.publish(m)


def main():
    # ── init 전에 설정을 읽어 robot 여부를 정한다 (SDD §4.3·§5.1) ──
    #    런치 인자 use_mock 은 환경변수 PREWASH_USE_MOCK 으로 와서 로더가 이미 얹어 준다.
    #    cc.cfg() 는 init() 뒤에만 되므로 여기서는 config.load() 를 직접 부른다.
    #    기능이 전부 가짜면 두산 드라이버 없이 돈다 → 브링업 없이 flow·HMI 개발 가능
    cfg = cc_config.load()
    use_mock = cfg.get('flow', {}).get('use_mock') or []
    if isinstance(use_mock, str):
        # 🚨 YAML 에 use_mock: "f1,f3" 처럼 문자열로 적으면 set() 이 글자 단위가 되어
        #    'f1' in use_mock 이 부분문자열 매칭으로 조용히 틀린 선택을 한다
        use_mock = cc_config.parse_use_mock(use_mock)
    use_mock = [m for m in use_mock if m in FEATURES]
    robot = not set(FEATURES) <= set(use_mock)

    cc.init('flow_node', robot=robot)                # ① 맨 앞에서 한 번 (SDD §3.2)
    try:
        node = cc.io_node()
        log = node.get_logger()
        sig = Signals()
        log.info('기능 모듈:')
        features = load_features(use_mock, log)      # 진짜/가짜 선택 (IRD §10)
        # 전부 가짜면 물러날 로봇이 없다 → 후퇴를 부르지 않는다(cc.safe_retreat 는 뼈대라 예외를 낸다)
        flow = Flow(cc.cfg(), log, features=features,
                    safe_retreat=cc.safe_retreat if robot else None)
        io = Io(node, flow, sig)
        flow._publish_event = io.publish_event       # 두뇌 → 배선 (두뇌는 ROS 를 모른다)

        log.info(f'flow 준비됨 — plan 그릇 {flow.target_bowl} · 컵 {flow.target_cup} · '
                 f'state {io.rate_hz} Hz · use_mock={use_mock or "없음"} · robot={robot}')
        unfilled = cc_config.unfilled(cc.cfg())      # 아직 안 채운 YAML 키 (티칭 전이면 많다)
        if unfilled:
            log.warn(f'설정에 안 채워진 키 {len(unfilled)}개 — 좌표가 필요한 동작은 아직 못 한다')
        flow.run(sig)                                # ② 메인 스레드에서 실행
    except KeyboardInterrupt:                        # Ctrl+C — 처리기는 cobot_common 이 건다
        pass
    except Exception:                                # noqa: BLE001
        # 여기까지 온 예외는 flow 의 보호를 모두 지나온 것이다(설정·초기화·구조 문제).
        # 트레이스백을 그대로 남겨 원인을 알 수 있게 하고, 정리는 finally 가 한다.
        logging.getLogger('flow_node').exception('flow_node 를 계속할 수 없다')
        raise
    finally:
        cc.shutdown()                                # ⑦ 어떤 경우에도 정리


if __name__ == '__main__':
    main()
