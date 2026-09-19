#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""🛟 복구 전용(시험 아님) — 컨트롤러에 남은 힘제어·순응을 끈다. --home 이면 HOME 이 아닐 때만 곧게 올린 뒤 HOME.

언제: 프로그램이 오류로 끝났는데 로봇 팔을 손으로 밀면 스프링처럼 눌릴 때(순응이 켜진 채 남음).
  두산 파이썬 API 의 DR_Error 는 만들어지는 순간 rclpy.shutdown() 을 부른다(설치된 DR_error2.py) →
  그 프로세스는 더 이상 로봇에 명령을 못 보내서, 켜 둔 힘·순응을 끄지 못한 채 끝난다. 새 프로세스인 이 스크립트로 끈다.

    soc && python3 src/cobot_common/test/release_force.py            # 힘·순응 끄기만
    soc && python3 src/cobot_common/test/release_force.py --home     # + 위로 up_mm → HOME (🚨 E-Stop 에 손)

끈 뒤 손으로 밀어 딱딱하면 풀린 것이다. 안 풀리면 E-Stop → 브링업 재시작.
"""
import argparse
import sys

import cobot_common as cc
from cobot_common.bootstrap import dsr

HOME_POSJ = [0.0, 0.0, 90.0, 0.0, 90.0, 0.0]   # 시험 HOME (rig_v03.yaml 과 같다) — 팀 값은 cell.yaml stations.HOME


def main() -> int:
    ap = argparse.ArgumentParser(description='남은 힘제어·순응 끄기 (복구)')
    ap.add_argument('--home', action='store_true', help='끈 뒤 위로 올리고 HOME 으로 (0.3배 속도)')
    ap.add_argument('--up-mm', type=float, default=80.0, help='HOME 전에 곧게 올릴 거리 mm')
    args = ap.parse_args()
    cc.init('release_force')
    log = cc.io_node().get_logger()
    try:
        d = dsr()
        rf, rc = d.release_force(), d.release_compliance_ctrl()
        log.info(f'release_force={rf} · release_compliance_ctrl={rc}  (0 = 끔, -1 = 이미 꺼져 있었을 수 있음)')
        if args.home:
            s = 0.3
            now = d.get_current_posj()
            if max(abs(a - b) for a, b in zip(now, HOME_POSJ)) < 1.0:     # 이미 HOME 이면 움직이지 않는다
                log.info('이미 HOME — 움직이지 않는다')
                return 0
            up = d.movel([0, 0, args.up_mm, 0, 0, 0], vel=50 * s, acc=50, ref=d.DR_BASE, mod=d.DR_MV_MOD_REL)
            log.info(f'위로 {args.up_mm:.0f} mm = {up}')
            log.info(f'HOME = {d.movej(HOME_POSJ, vel=20 * s, acc=20)}')
        return 0
    finally:
        cc.shutdown()


if __name__ == '__main__':
    sys.exit(main())
