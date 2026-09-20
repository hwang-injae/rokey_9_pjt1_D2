#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V-24a 정지 가능성 시험 — 이동 **도중에** 정지·일시정지·재개가 먹는가. 🚨 Virtual 전용. 제품 코드는 바꾸지 않는다.

HMI 의 정지 방식을 정하기 위한 근거를 모은다: ① 강제정지(즉시) + HOME 복귀  ② 즉시 멈추고 재개하면 **하던 동작을 이어서** 하는 일시정지.

무엇을 흉내 내나
    메인 스레드      : 긴 관절 이동 하나(J1 0° → 90°, 약 6 s)를 실행 — flow_node 가 기능 함수를 도는 자리
    통신 노드 스레드 : 이동 시작 2 s 뒤에 서비스를 부른다 — HMI 의 버튼이 들어오는 자리 (/flow/stop 콜백이 도는 곳)
    J1 각도는 /dsr01/joint_states 를 구독해 기록한다(메인 스레드는 이동 명령에 묶여 있어 각도를 물어볼 수 없다).

실행 (저장소 루트 · rosinfo 로 RANGE=LOCALHOST 확인 · sodvir 가 떠 있어야 한다 — 이미 떠 있으면 그대로 쓴다)
    soc && python3 src/cobot_common/test/rig_stop.py t1     # 동기 이동 중 정지(move_stop)
    soc && python3 src/cobot_common/test/rig_stop.py t2     # 동기 이동 중 일시정지 → 재개 (같은 동작이 이어지는가)
    soc && python3 src/cobot_common/test/rig_stop.py t3     # 비동기 이동 + 폴링 중 일시정지 → 재개
    soc && python3 src/cobot_common/test/rig_stop.py t3s    # 비동기 이동 + 폴링 중 정지
    soc && python3 src/cobot_common/test/rig_stop.py t4     # 정지 직후 다음 이동 명령이 바로 나가면?
시험마다 프로세스를 따로 띄운다(두산 API 가 오류 때 rclpy 를 내려 버려도 다음 시험에 번지지 않게). 시험 값은 rig_stop.yaml.
"""
import math
import os
import sys
import time
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
os.environ.setdefault('PREWASH_CONFIG_DIR', str(HERE / 'config_virtual'))

import cobot_common as cc                   # noqa: E402
from cobot_common.bootstrap import dsr      # noqa: E402  cobot_common 자체 시험이라 내부 함수를 쓴다

SRV = '/dsr01/dsr_controller2/motion/'
TESTS = ('t1', 't2', 't3', 't3s', 't4')


def main(which: str) -> int:
    import rclpy
    from dsr_msgs2.srv import MovePause, MoveResume, MoveStop
    from sensor_msgs.msg import JointState

    with open(HERE / 'rig_stop.yaml', encoding='utf-8') as f:
        p = yaml.safe_load(f)
    cc.init(f'rig_stop_{which}')
    io = cc.io_node()
    log = io.get_logger()
    t0 = [0.0]                                              # 이동 시작 시각
    track = []                                              # (t, J1 deg) — 통신 노드 스레드가 채운다
    calls = []                                              # {'name', 'sent', 'done', 'ok'}

    def on_joint(msg):
        i = msg.name.index('joint_1') if 'joint_1' in msg.name else 0
        track.append((time.monotonic(), math.degrees(msg.position[i])))
    io.create_subscription(JointState, '/dsr01/joint_states', on_joint, 50)
    clients = {'stop': io.create_client(MoveStop, SRV + 'move_stop'),
               'pause': io.create_client(MovePause, SRV + 'move_pause'),
               'resume': io.create_client(MoveResume, SRV + 'move_resume')}

    def press(name, after_s):
        """after_s 뒤에 **통신 노드 스레드에서** 서비스를 부른다(HMI 버튼 흉내). 콜백은 보내고 시각만 적는다."""
        holder = {}

        def fire():
            holder['timer'].cancel()
            req = {'stop': MoveStop.Request, 'pause': MovePause.Request, 'resume': MoveResume.Request}[name]()
            if name == 'stop':
                req.stop_mode = p['stop_mode']
            rec = {'name': name, 'sent': time.monotonic(), 'done': None, 'ok': None}
            calls.append(rec)

            def done(fut):
                rec['done'] = time.monotonic()
                rec['ok'] = bool(fut.result() and fut.result().success)
            clients[name].call_async(req).add_done_callback(done)
        holder['timer'] = io.create_timer(after_s, fire)

    def j1_at(t):
        past = [d for s, d in track if s <= t]
        return past[-1] if past else float('nan')

    def still_from(t_from):
        """t_from 뒤로 J1 이 처음 멈춘 시각과 각도(still_for_s 동안 still_deg 미만)."""
        pts = [(s, d) for s, d in track if s >= t_from]
        for k, (s, d) in enumerate(pts):
            win = [x for x in pts[k:] if x[0] - s <= p['still_for_s']]
            if pts[-1][0] - s >= p['still_for_s'] and max(abs(x[1] - d) for x in win) < p['still_deg']:
                return s, d
        return None, float('nan')

    def report_calls():
        for c in calls:
            took = f"{(c['done'] - c['sent']) * 1000:.0f} ms" if c['done'] else f"응답 없음(>{p['service_timeout_s']} s)"
            log.info(f"  [{c['name']}] 누른 시각 +{c['sent'] - t0[0]:.2f} s · 응답 {took} · success={c['ok']} · 그때 J1 {j1_at(c['sent']):.1f}°")

    def wait_calls():
        end = time.monotonic() + p['service_timeout_s']
        while time.monotonic() < end and any(c['done'] is None for c in calls):
            time.sleep(0.05)

    d = dsr()
    code = 1
    try:
        if d.get_robot_system() != d.ROBOT_SYSTEM_VIRTUAL:
            log.error('Virtual 이 아니다 → 실행하지 않는다')
            return 2
        for c in clients.values():
            if not c.wait_for_service(timeout_sec=5.0):
                log.error(f'서비스가 안 보인다: {c.srv_name}')
                return 2
        kw = {'vel': p['vel_deg_s'], 'acc': p['acc_deg_s2']}
        d.movej(p['start_posj'], vel=60, acc=60)
        time.sleep(0.5)
        target = p['target_posj']
        log.info(f"── {which}: J1 {p['start_posj'][0]:g}° → {target[0]:g}° ({p['vel_deg_s']} deg/s) · {p['press_at_s']} s 에 누른다 ──")

        if which in ('t1', 't4'):
            press('stop', p['press_at_s'])
        elif which == 't2':
            press('pause', p['press_at_s'])
            press('resume', p['press_at_s'] + p['resume_after_s'])

        t0[0] = time.monotonic()
        ret, err = None, None
        if which in ('t1', 't2', 't4'):                     # 동기 이동 — 끝날 때까지 메인 스레드가 묶인다
            try:
                ret = d.movej(target, **kw)
            except BaseException as e:                      # noqa: BLE001  무엇이 올라오는지가 시험 대상
                err = repr(e)
            t_ret = time.monotonic()
            log.info(f"  동기 movej 가 돌아옴: +{t_ret - t0[0]:.2f} s · 반환 {ret!r} · 예외 {err} · rclpy.ok()={rclpy.ok()}")
        else:                                               # t3 · t3s: 비동기 이동 + 폴링 (메인 스레드는 묶이지 않는다)
            ret = d.amovej(target, **kw)
            log.info(f'  amovej 반환 {ret!r} (바로 돌아온다) → check_motion 폴링 시작')
            pressed = set()
            while True:
                now = time.monotonic() - t0[0]
                first, second = ('stop', None) if which == 't3s' else ('pause', 'resume')
                if now >= p['press_at_s'] and first not in pressed:
                    pressed.add(first)
                    press(first, 0.01)
                if second and now >= p['press_at_s'] + p['resume_after_s'] and second not in pressed:
                    pressed.add(second)
                    press(second, 0.01)
                state = d.check_motion()                    # 0 = 멈춤(IDLE) · 그 밖 = 움직이는 중
                paused_window = second and first in pressed and second not in pressed
                if state == 0 and not paused_window and now > p['press_at_s'] + 0.5:
                    break
                if now > 40:
                    log.error('  40 s 가 지나도 끝나지 않는다')
                    break
                time.sleep(p['poll_s'])
            t_ret = time.monotonic()
            log.info(f'  check_motion 이 멈춤(0)을 돌려줌: +{t_ret - t0[0]:.2f} s')

        wait_calls()
        time.sleep(1.0)
        report_calls()
        first_press = calls[0]['sent'] if calls else t0[0]
        t_still, j_still = still_from(first_press)
        if t_still:
            log.info(f"  누른 뒤 J1 이 처음 멈춘 때: +{t_still - first_press:.2f} s 뒤 · {j_still:.1f}° 에서")
        final = j1_at(time.monotonic())
        reached = abs(final - target[0]) <= p['reach_tol_deg']
        log.info(f"  마지막 J1 {final:.1f}° · 목표 {target[0]:g}° 도달 {'예' if reached else '아니오'}")

        if which == 't4':                                   # 정지 직후 다음 이동이 바로 나가면?
            t_next = time.monotonic()
            r2 = d.movej(p['start_posj'], vel=60, acc=60)
            log.info(f"  정지 직후 다음 movej: 반환 {r2!r} · {time.monotonic() - t_next:.2f} s · J1 {j1_at(time.monotonic()):.1f}° "
                     f"→ 정지 뒤에도 다음 명령이 나가면 로봇은 {'다시 움직인다' if r2 == 0 else '움직이지 않는다'}")
        elif rclpy.ok():
            r2 = d.movej(p['start_posj'], vel=60, acc=60)   # 그 뒤 다음 명령이 정상인가
            log.info(f"  이어서 시작 자세로 movej: 반환 {r2!r} · J1 {j1_at(time.monotonic()):.1f}°")
        code = 0
        return code
    except KeyboardInterrupt:
        return 130
    finally:
        cc.shutdown()


if __name__ == '__main__':
    if len(sys.argv) != 2 or sys.argv[1] not in TESTS:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1]))
