# -*- coding: utf-8 -*-
"""fake_state_pub — **가짜 flow**. 대본대로 실제 flow_node 와 똑같은 토픽을 방송한다(로봇·브링업 불필요). 담당 황인재 (F4-01)

왜: 실제 flow 는 아직 만드는 중이고, 전부 mock 으로 돌리면 단계가 0 초에 끝나 화면에 안 잡힌다(F4-00 실측)
    → HMI 화면·브리지를 혼자 개발·시험할 때 이 노드를 flow 자리에 세운다.

방송하는 것 (IRD §6 그대로)
    /flow/state     cobot_msgs/FlowState  2 Hz
    /flow/event     cobot_msgs/FlowEvent  용기 1개 완료·격리·건너뜀마다 1건
    /cell/force     std_msgs/Float32      닦는 동안만 10 Hz
    /cell/gripping  std_msgs/Bool         값이 바뀔 때 1번 + 2 Hz

실행
    ros2 run f4_hmi fake_state_pub                 # 대본 normal
    ros2 run f4_hmi fake_state_pub isolate         # 대본 이름: normal · isolate · error · paused · empty_zone (scenarios/*.yaml)
    ros2 run f4_hmi fake_state_pub normal --speed 2 --once      # 2배속 · 한 바퀴만
🚨 실제 flow_node 와 **동시에 띄우지 않는다**(같은 토픽에 두 곳이 방송하면 화면 값이 뒤섞인다).
   서비스(/flow/start 등)는 아직 없다 — 버튼 시험용 응답은 F4-02 에서 붙인다.
"""
import argparse
import sys

import rclpy
from rclpy.node import Node
from rclpy.utilities import remove_ros_args
from std_msgs.msg import Bool, Float32

from cobot_msgs.msg import FlowEvent, FlowState

from . import scenario as sc


class FakeFlow(Node):
    def __init__(self, scn, speed, once):
        super().__init__('fake_state_pub')
        self.scn, self.speed, self.once = scn, float(speed), once
        self.scenes = sc.build(scn)
        self.lap_s = sc.total_s(self.scenes)
        self.t0 = self.get_clock().now()
        self.lap = 0
        self.index = -1                                     # 지금 방송 중인 장면 번호
        self.gripping = None
        self.finished = False
        rates = scn['rates']
        self.state_pub = self.create_publisher(FlowState, '/flow/state', 10)
        self.event_pub = self.create_publisher(FlowEvent, '/flow/event', 10)
        self.force_pub = self.create_publisher(Float32, '/cell/force', 10)
        self.grip_pub = self.create_publisher(Bool, '/cell/gripping', 10)
        self.create_timer(1.0 / float(rates['state_hz']), self._on_state)
        self.create_timer(1.0 / float(rates['gripping_hz']), self._on_gripping)
        self.create_timer(1.0 / float(rates['force_hz']), self._on_force)
        self.get_logger().info(f"대본 '{scn['name']}' — {scn.get('title', '')} · 한 바퀴 {self.lap_s / self.speed:.0f} s"
                               f"{' · 한 바퀴만' if once else ' · 반복'} · 장면 {len(self.scenes)}개")

    # ------------------------------------------------------------------ 시간 → 장면
    def _now_s(self):
        return (self.get_clock().now() - self.t0).nanoseconds / 1e9 * self.speed

    def _advance(self):
        """지금 시각의 장면을 돌려준다. 장면이 넘어갈 때마다 끝난 장면의 이벤트를 낸다(빠뜨리지 않게 하나씩)."""
        t = self._now_s()
        lap, in_lap = divmod(t, self.lap_s)
        if self.once and lap >= 1:
            lap, in_lap, self.finished = 0, self.lap_s - 1e-6, True
        target, _ = sc.scene_at(self.scenes, in_lap)
        target += int(lap - self.lap) * len(self.scenes)    # 바퀴가 넘어갔으면 그만큼 뒤
        while self.index < target:
            if self.index >= 0:
                self._emit(self.scenes[self.index % len(self.scenes)])
            self.index += 1
            if self.index and self.index % len(self.scenes) == 0:
                self.get_logger().info('── 한 바퀴 끝 · 처음부터 다시 ──')
            scene = self.scenes[self.index % len(self.scenes)]
            self.get_logger().info(f"[{scene.state['step']:<7}] {scene.state['kind'] or '-':<4} {scene.state['zone_id'] or '-':<5} "
                                   f"그릇 {scene.state['done_bowl']}/{scene.state['target_bowl']} 컵 {scene.state['done_cup']}/{scene.state['target_cup']} "
                                   f"격리 {scene.state['isolated']} · {scene.duration_s / self.speed:.1f} s"
                                   + (f" · {scene.state['message']}" if scene.state['message'] else ''))
        self.lap = int(lap)
        return self.scenes[self.index % len(self.scenes)]

    def _emit(self, scene):
        if scene.event is None:
            return
        m = FlowEvent()
        m.stamp = self.get_clock().now().to_msg()
        for k, v in scene.event.items():
            setattr(m, k, v)
        m.duration_s = float(scene.event['duration_s']) / self.speed
        self.event_pub.publish(m)
        self.get_logger().info(f"  ↳ 이벤트 {m.result} · {m.kind} · {m.rack_slot or '-'} · code {m.code}")

    # ------------------------------------------------------------------ 타이머 (방송)
    def _on_state(self):
        scene = self._advance()
        m = FlowState()
        for k, v in scene.state.items():
            setattr(m, k, v)
        m.stamp = self.get_clock().now().to_msg()
        self.state_pub.publish(m)
        if scene.gripping != self.gripping:                 # 값이 바뀔 때 1번 (IRD §6)
            self.gripping = scene.gripping
            self.grip_pub.publish(Bool(data=self.gripping))
        if self.finished:
            self.get_logger().info('한 바퀴를 마쳤다(--once) → 끝낸다')
            raise SystemExit(0)

    def _on_gripping(self):
        if self.gripping is not None:
            self.grip_pub.publish(Bool(data=self.gripping))

    def _on_force(self):
        if self.index >= 0 and self.scenes[self.index % len(self.scenes)].wiping:
            self.force_pub.publish(Float32(data=sc.force_at(self.scn, self._now_s() / self.speed)))


def main(argv=None):
    args = remove_ros_args(sys.argv if argv is None else argv)[1:]
    parser = argparse.ArgumentParser(prog='fake_state_pub', description='가짜 flow — 대본대로 /flow/state 등을 방송한다')
    parser.add_argument('scenario', nargs='?', default='normal', help=f'대본 이름 또는 yaml 경로 (기본 normal) — {sc.names()}')
    parser.add_argument('--speed', type=float, default=1.0, help='빨리 감기 배수 (기본 1.0)')
    parser.add_argument('--once', action='store_true', help='한 바퀴만 돌고 끝낸다')
    opt = parser.parse_args(args)
    if not opt.speed > 0:
        parser.error('--speed 는 0 보다 커야 한다')
    scn = sc.load(opt.scenario)
    if opt.once:
        scn['loop'] = False

    rclpy.init(args=sys.argv if argv is None else argv)
    node = FakeFlow(scn, opt.speed, once=not scn.get('loop', True))
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
