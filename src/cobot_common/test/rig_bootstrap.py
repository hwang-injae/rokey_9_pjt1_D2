#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""INF-02a 단독 시험 — 실행 뼈대(cobot_common.init · io_node · cfg · shutdown) 확인. 🚨 기본은 Virtual 전용(--real 은 저속 키).

실행 (저장소 루트에서)
    터미널 1:  sod && sodvir
    터미널 2:  soc && python3 src/cobot_common/test/rig_bootstrap.py

확인하는 것 (완료 기준)
    ① movej 연속 3회 이상 — "첫 번째만 되는" 결함(TS-01 B′)을 본다
    ② 모션 중에도 통신 노드 타이머가 2 Hz 로 돈다
    ③ 도는 중에 Ctrl+C → 정지 명령을 보내고 끝난다 → 다시 실행해도 정상

시험 값은 같은 폴더의 rig_bootstrap.yaml. 끝나면 종료 코드 0(통과) / 1(실패) / 2(실행 거부) / 130(Ctrl+C).
"""
import argparse
import sys
import time
from pathlib import Path

import yaml

import cobot_common as cc
from cobot_common.bootstrap import dsr      # cobot_common 자체 시험이라 내부 함수를 쓴다. 기능 패키지는 쓰지 않는다


def main() -> int:
    ap = argparse.ArgumentParser(description='cobot_common 실행 뼈대 시험 (Virtual 전용)')
    ap.add_argument('--real', action='store_true', help='Virtual 이 아니어도 실행한다 (🚨 실기는 팀 확인 뒤에만)')
    args = ap.parse_args()
    with open(Path(__file__).with_suffix('.yaml'), encoding='utf-8') as f:
        p = yaml.safe_load(f)

    cc.init('rig_bootstrap')                                        # ① 맨 앞에서 한 번
    log = cc.io_node().get_logger()
    ticks = []
    cc.io_node().create_timer(1.0 / p['timer_hz'], lambda: ticks.append(time.monotonic()))   # 콜백은 값 저장만
    code = 1
    try:
        d = dsr()
        virtual = d.get_robot_system() == d.ROBOT_SYSTEM_VIRTUAL
        if not virtual and not args.real:
            log.error('Virtual 이 아니다 → 실행하지 않는다. 실기에서 돌리려면 팀 확인 뒤 --real')
            return 2
        speed = p['virtual' if virtual else 'real']                 # 실기는 저속 키만 쓴다
        scale = cc.cfg()['run']['vel_scale']                        # 런치 인자 vel_scale / PREWASH_VEL_SCALE
        vel, acc = speed['vel_deg_s'] * scale, speed['acc_deg_s2'] * scale
        log.info(f"{'Virtual' if virtual else '🚨 실기'} · vel {vel:g} deg/s · acc {acc:g} deg/s² (vel_scale {scale:g})")
        log.info(f"설정 확인: cfg() 절 = {sorted(cc.cfg())} · hmi.port = {cc.cfg()['hmi'].get('port')}")

        first_tick = len(ticks)
        bad = 0
        n = 0
        for rnd in range(p['rounds']):                              # ② 같은 함수를 연속으로
            for posj in p['posj_list']:
                n += 1
                t0 = time.monotonic()
                ret = d.movej(posj, vel=vel, acc=acc)
                j1 = d.get_current_posj()[0]
                ok = ret == 0 and abs(j1 - posj[0]) <= p['posj_tol_deg']
                bad += 0 if ok else 1
                log.info(f"movej {n}회째(바퀴 {rnd + 1}) → J1 목표 {posj[0]:.1f} 실제 {j1:.1f} · ret={ret} · "
                         f"{time.monotonic() - t0:.1f} s · {'OK' if ok else 'FAIL'}")

        gaps = [b - a for a, b in zip(ticks[first_tick:], ticks[first_tick + 1:])]
        hz = len(gaps) / sum(gaps) if gaps else 0.0
        hz_ok = bool(gaps) and abs(hz - p['timer_hz']) <= p['timer_tol_hz'] and max(gaps) < 2.0 / p['timer_hz']
        log.info(f"통신 노드 타이머: 모션 중 {hz:.3f} Hz (목표 {p['timer_hz']} Hz, 최대 간격 "
                 f"{max(gaps) if gaps else 0:.2f} s, {len(gaps) + 1}틱) · {'OK' if hz_ok else 'FAIL'}")
        code = 0 if (bad == 0 and n >= 3 and hz_ok) else 1
        log.info(f"결과: movej {n - bad}/{n} · 타이머 {'OK' if hz_ok else 'FAIL'} → {'통과' if code == 0 else '실패'}")
        return code
    except KeyboardInterrupt:
        log.warn('Ctrl+C — 정지 명령을 보내고 끝낸다')
        return 130
    finally:
        cc.shutdown()                                               # ③ 끝낼 때 (Ctrl+C 포함)


if __name__ == '__main__':
    sys.exit(main())
