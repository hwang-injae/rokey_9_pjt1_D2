# -*- coding: utf-8 -*-
"""hmi_bridge 의 ROS 쪽 귀 — 토픽 4개를 듣고 StateStore 에 넣는다. 별도 스레드에서 spin 한다(웹 서버와 섞지 않는다).

콜백은 **값 저장만** 한다(SDD §3.2 규칙 ③과 같은 원칙). 두산 API 를 쓰지 않으므로 cobot_common.init() 을 부르지 않는다.
버튼용 서비스 클라이언트(/flow/start·stop·resume·abort)는 F4-02 에서 붙인다.
"""
import threading

import rclpy
from rclpy.executors import SingleThreadedExecutor
from rclpy.signals import SignalHandlerOptions
from std_msgs.msg import Bool, Float32

from cobot_msgs.msg import FlowEvent, FlowState


def to_dict(msg) -> dict:
    """메시지 → dict. stamp 는 초(float)로 바꾼다 — 나머지 필드는 이름·값 그대로(IRD §7)."""
    out = {}
    for name in msg.get_fields_and_field_types():
        value = getattr(msg, name)
        out[name] = round(value.sec + value.nanosec / 1e9, 3) if name == 'stamp' else value
    return out


class RosLink:
    def __init__(self, store):
        self.store = store
        self.node = None
        self._executor = None
        self._thread = None
        self._stopping = False

    def start(self):
        rclpy.init(signal_handler_options=SignalHandlerOptions.NO)      # Ctrl+C 는 웹 서버(uvicorn)가 받는다
        self.node = rclpy.create_node('hmi_bridge')
        n, s = self.node, self.store
        n.create_subscription(FlowState, '/flow/state', lambda m: s.put_state(to_dict(m)), 10)
        n.create_subscription(FlowEvent, '/flow/event', lambda m: s.put_event(to_dict(m)), 50)
        n.create_subscription(Float32, '/cell/force', lambda m: s.put_force(m.data), 10)
        n.create_subscription(Bool, '/cell/gripping', lambda m: s.put_gripping(m.data), 10)
        self._executor = SingleThreadedExecutor()
        self._executor.add_node(n)
        self._thread = threading.Thread(target=self._spin, name='hmi_ros', daemon=True)
        self._thread.start()

    def _spin(self):
        while rclpy.ok() and not self._stopping:
            try:
                self._executor.spin()
                return
            except Exception:                                # noqa: BLE001 — 콜백 하나가 터져도 듣기를 멈추지 않는다
                import traceback
                self.node.get_logger().error('ROS 콜백 예외 — 계속 듣는다\n' + traceback.format_exc())

    def stop(self):
        """순서가 중요하다: 듣기를 멈추고 → **스레드가 끝나기를 기다린 뒤** → 노드·rclpy 를 닫는다.
        스레드가 spin 중인 채로 닫으면 프로그램이 끝날 때 'terminate called' 로 비정상 종료한다."""
        self._stopping = True
        if self._executor is not None:
            self._executor.shutdown(timeout_sec=1.0)
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        if self.node is not None:
            self.node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
