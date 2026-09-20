#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""🔎 Move Spiral 이 실제로 도는 인자 조합 찾기 — **공중에서**(HOME 자세) 돌린다. 그릇에 닿지 않는다.

    soc && python3 src/cobot_common/test/probe_spiral.py          # Virtual
    soc && python3 src/cobot_common/test/probe_spiral.py --real   # 실기 (🚨 E-Stop 에 손, HOME 주변 반경 2 cm 만 움직임)

왜: 9/20 실기에서 move_spiral 이
  · 속도(vel)로 주면 → 드라이버가 응답하지 않고 멈춘다
  · 시간(time)으로 주면 → 반환은 0 인데 **시작조차 하지 않는다**(시작됨=False, 실제 반지름 0.3 mm)
어느 조합이 실제로 도는지 하나씩 넣어 보고, 도는 조합을 rig_v03 에 쓴다.
각 조합마다 실제 위치를 훑어 **도달한 최대 반지름**을 찍는다. 3 mm 넘게 움직이면 '돈다'로 본다.
"""
import argparse
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
os.environ['PREWASH_CONFIG_DIR'] = os.path.join(HERE, 'rig_v03_config')
os.environ.setdefault('PREWASH_VEL_SCALE', '0.3')

import cobot_common as cc                                      # noqa: E402
from cobot_common.bootstrap import dsr                         # noqa: E402

HOME = [0.0, 0.0, 90.0, 0.0, 90.0, 0.0]
RMAX = 20.0                 # 공중이라 조금 크게 (눈으로 보이게)
REV = 3.0


def run_one(d, log, name, **kw):
    """한 조합을 비동기로 넣고 4 s 동안 실제 반지름을 훑는다 → 최대 반지름."""
    start = d.get_current_posx(ref=d.DR_BASE)[0]
    log.info(f'▶ {name}')
    try:
        ret = d.amove_spiral(**kw)
    except Exception as e:                                     # noqa: BLE001 — DR_Error 도 여기서 잡아 이름과 함께 남긴다
        log.error(f'   거부됨: {type(e).__name__}: {e}')
        return -1.0
    rmax = 0.0
    t0 = time.monotonic()
    while time.monotonic() - t0 < 4.0:
        now = d.get_current_posx(ref=d.DR_BASE)[0]
        rmax = max(rmax, math.hypot(float(now[0]) - float(start[0]), float(now[1]) - float(start[1])))
        if d.check_motion() == 0 and time.monotonic() - t0 > 0.5:
            break
        time.sleep(0.05)
    d.mwait()
    log.info(f'   반환 {ret} · 실제 최대 반지름 {rmax:.1f} mm → {"돈다 ✅" if rmax > 3.0 else "안 돈다 ❌"}')
    return rmax


def main() -> int:
    ap = argparse.ArgumentParser(description='Move Spiral 인자 조합 찾기 (공중)')
    ap.add_argument('--real', action='store_true', help='실기에서 실행')
    args = ap.parse_args()
    cc.init('probe_spiral')
    log = cc.io_node().get_logger()
    try:
        d = dsr()
        virtual = d.get_robot_system() == d.ROBOT_SYSTEM_VIRTUAL
        if not virtual and not args.real:
            log.error('실기다 → --real 을 붙인다')
            return 2
        s = cc.cfg()['run']['vel_scale']
        log.info(f'{"Virtual" if virtual else "실기"} · HOME 으로 이동 (공중에서만 돈다)')
        d.movej(HOME, vel=40 * s, acc=40)
        d.mwait()

        combos = [
            ('① 시간만 (vel·acc 0) · 툴 기준',
             dict(rev=REV, rmax=RMAX, lmax=0.0, vel=[0.0, 0.0], acc=[0.0, 0.0], time=3.0,
                  axis=d.DR_AXIS_Z, ref=d.DR_TOOL)),
            ('② 시간만 (vel·acc 0) · 베이스 기준',
             dict(rev=REV, rmax=RMAX, lmax=0.0, vel=[0.0, 0.0], acc=[0.0, 0.0], time=3.0,
                  axis=d.DR_AXIS_Z, ref=d.DR_BASE)),
            ('③ 속도 + 시간 함께 · 툴 기준',
             dict(rev=REV, rmax=RMAX, lmax=0.0, vel=[60.0 * s, 60.0 * s], acc=[200.0, 200.0], time=3.0,
                  axis=d.DR_AXIS_Z, ref=d.DR_TOOL)),
            ('④ 시간만 · 축 방향으로 1 mm 전진(lmax=1)',
             dict(rev=REV, rmax=RMAX, lmax=1.0, vel=[0.0, 0.0], acc=[0.0, 0.0], time=3.0,
                  axis=d.DR_AXIS_Z, ref=d.DR_TOOL)),
            ('⑤ 시간만 · 회전수 1바퀴',
             dict(rev=1.0, rmax=RMAX, lmax=0.0, vel=[0.0, 0.0], acc=[0.0, 0.0], time=3.0,
                  axis=d.DR_AXIS_Z, ref=d.DR_TOOL)),
        ]
        stx = cc.cfg()['cell']['force']['compliance_stx']
        extra = [
            ('⑥ 순응제어 켠 채 (task_compliance_ctrl)',
             dict(rev=REV, rmax=RMAX, lmax=0.0, vel=[0.0, 0.0], acc=[0.0, 0.0], time=3.0,
                  axis=d.DR_AXIS_Z, ref=d.DR_TOOL), 'compliance'),
            ('⑦ 힘제어 켠 채 (set_desired_force 3 N)',
             dict(rev=REV, rmax=RMAX, lmax=0.0, vel=[0.0, 0.0], acc=[0.0, 0.0], time=3.0,
                  axis=d.DR_AXIS_Z, ref=d.DR_TOOL), 'force'),
        ]
        best = []
        for name, kw in combos:
            r = run_one(d, log, name, **kw)
            best.append((r, name))
            d.movej(HOME, vel=40 * s, acc=40)                  # 다음 조합 전에 제자리로
            d.mwait()

        for name, kw, mode in extra:                               # 순응·힘제어를 켠 채로도 도는가 (공중)
            d.mwait()
            d.task_compliance_ctrl(stx)
            if mode == 'force':
                d.set_desired_force([0.0, 0.0, -3.0, 0.0, 0.0, 0.0], [0, 0, 1, 0, 0, 0], time=0,
                                    mod=d.DR_FC_MOD_ABS)
                time.sleep(0.3)
            r = run_one(d, log, name, **kw)
            best.append((r, name))
            d.release_force()
            d.release_compliance_ctrl()
            d.movej(HOME, vel=40 * s, acc=40)
            d.mwait()

        log.info('── 결과 ──')
        for r, name in best:
            log.info(f'   {name}: {"거부" if r < 0 else f"{r:.1f} mm"}')
        win = max(best)
        log.info(f'→ 쓸 조합: {win[1]}' if win[0] > 3.0 else '→ 도는 조합이 없다. 나선은 원호를 이어 붙여 직접 그린다')
        return 0
    except KeyboardInterrupt:
        return 130
    finally:
        try:
            dsr().movej(HOME, vel=12, acc=40)
        except Exception:                                      # noqa: BLE001
            pass
        cc.shutdown()


if __name__ == '__main__':
    sys.exit(main())
