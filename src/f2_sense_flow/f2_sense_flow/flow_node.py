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

실행:
    ros2 run f2_sense_flow flow_node
    ros2 run f2_sense_flow flow_node --use-mock f1,f3     # f1·f3 를 가짜로
    ros2 run f2_sense_flow flow_node --use-mock f1,f2,f3  # 전부 가짜 → 드라이버 없이
"""
import argparse
import sys

import cobot_common as cc
from cobot_common import config as cc_config
from cobot_msgs.msg import FlowEvent, FlowState
from std_srvs.srv import Trigger

from f2_sense_flow.flow import Flow, Signals

FEATURES = ('f1', 'f2', 'f3')


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

        rate_hz = flow.cfg.get('state_pub_hz', 2.0)
        node.create_timer(1.0 / rate_hz, self._on_state_timer)
        self.rate_hz = rate_hz

    # ────────────────────────────────── 서비스 콜백 (깃발만!)
    def _on_start(self, req, res):
        if self.flow.step == 'IDLE':
            self.sig.raise_('start')
            res.success, res.message = True, '시작합니다'
        else:
            res.success, res.message = False, f'IDLE 이 아닙니다 (현재 {self.flow.step})'
        return res                                   # 즉시 응답. 실행은 메인 스레드가 한다

    def _on_stop(self, req, res):
        self.sig.raise_('stop')
        res.success, res.message = True, '현재 동작이 끝나면 정지합니다'
        return res

    def _on_resume(self, req, res):
        self.sig.raise_('resume')
        res.success, res.message = True, '재개합니다'
        return res

    # ────────────────────────────────── 상태 발행 (메시지만 만든다)
    def _on_state_timer(self):
        s = self.flow.snapshot()
        m = FlowState()
        for k, v in s.items():
            setattr(m, k, v)
        m.stamp = self.node.get_clock().now().to_msg()
        self.state_pub.publish(m)

    def publish_event(self, ev):
        """flow(두뇌)가 용기 1개를 끝낼 때마다 부른다. dict → 메시지로 옮긴다."""
        m = FlowEvent()
        m.stamp = self.node.get_clock().now().to_msg()
        for k, v in ev.items():
            setattr(m, k, v)
        self.event_pub.publish(m)


def _parse_args(argv):
    ap = argparse.ArgumentParser(description='PreWash-Cell 메인 프로그램')
    ap.add_argument('--use-mock', default=None,
                    help='가짜로 돌릴 기능(쉼표). 예: f1,f3 · 전부면 드라이버 없이 돈다. '
                         'params.yaml 의 flow.use_mock 을 덮어쓴다')
    args, _ = ap.parse_known_args(argv)             # --ros-args 등은 그대로 흘려보낸다
    return args


def main(argv=None):
    args = _parse_args(sys.argv[1:] if argv is None else argv)

    # ── init 전에 설정을 읽어 robot 여부를 정한다 (SDD §5.1) ──
    #    전부 가짜면 두산 드라이버 없이 돈다 → 브링업 없이 flow·HMI 개발 가능
    cfg = cc_config.load()
    use_mock = ([m.strip() for m in args.use_mock.split(',') if m.strip()]
                if args.use_mock is not None else (cfg.get('flow', {}).get('use_mock') or []))
    robot = not set(FEATURES) <= set(use_mock)

    cc.init('flow_node', robot=robot)                # ① 맨 앞에서 한 번 (SDD §3.2)
    try:
        node = cc.io_node()
        log = node.get_logger()
        sig = Signals()
        flow = Flow(cc.cfg(), log, safe_retreat=cc.safe_retreat)
        io = Io(node, flow, sig)
        flow._publish_event = io.publish_event       # 두뇌 → 배선 (두뇌는 ROS 를 모른다)

        log.info(f'flow 준비됨 — plan 그릇 {flow.target_bowl} · 컵 {flow.target_cup} · '
                 f'state {io.rate_hz} Hz · use_mock={use_mock or "없음"} · robot={robot}')
        flow.run(sig)                                # ② 메인 스레드에서 실행
    except KeyboardInterrupt:                        # Ctrl+C — 처리기는 cobot_common 이 건다
        pass
    finally:
        cc.shutdown()                                # ⑦ 어떤 경우에도 정리


if __name__ == '__main__':
    main()
