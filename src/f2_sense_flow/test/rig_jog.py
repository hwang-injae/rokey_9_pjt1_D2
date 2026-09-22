"""관절 조그 시험대 — 키 하나에 관절 하나를 조금씩 (민범진 · 9/22 · V-07 기울이기 각도 찾기).

    soc && PREWASH_VEL_SCALE=0.3 python3 src/f2_sense_flow/test/rig_jog.py                # 지금 자리에서 시작
    soc && PREWASH_VEL_SCALE=0.3 python3 src/f2_sense_flow/test/rig_jog.py --goto WASTE --kind BOWL   # 자세로 간 뒤 조그

키 (누르면 **바로** 그만큼 움직이고 끝날 때까지 기다린다 — 한 번에 하나):
    1~6        움직일 관절 고르기 (기본 5)
    d / →      + step         a / ←      − step
    ]  [       step 두 배 / 절반  (0.5 ~ 10°)
    p          지금 posj · posx 를 찍는다 (cell.yaml 에 옮길 값)
    r          시작 자세로 되돌린다 (조그한 만큼 반대로 — 관절 이동 1번)
    q          끝 (안 움직임 · 그리퍼도 그대로)

🚨 안전
    · 한 번에 최대 10° · 시작 자세에서 관절당 누적 ±max-total(기본 120°)까지만 — 넘으면 거절
    · 이동 중엔 키를 안 받는다(블로킹). 손은 E-Stop.
    · 시작 전 문지기(툴·TCP 이름 · TS-07). 힘제어는 시작할 때 끈다.
    · 이 시험대는 **그리퍼를 만지지 않는다** — 쥔 것은 쥔 채, 빈손은 빈손.
파일 이름이 test_* 가 아니라서 pytest 는 모으지 않는다.
"""
import argparse
import sys
import termios
import tty

import cobot_common as cc
from f2_sense_flow.preflight import require_controller

STEP_MIN, STEP_MAX, STEP_CAP = 0.5, 10.0, 10.0


def _key():
    """키 하나. 화살표(ESC [ C/D)는 'RIGHT'/'LEFT' 로."""
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        ch = sys.stdin.read(1)
        if ch == '\x1b':
            seq = sys.stdin.read(2)
            return {'[C': 'RIGHT', '[D': 'LEFT'}.get(seq, 'ESC')
        return ch
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def _fmt(v):
    return '[' + ', '.join(f'{x:7.1f}' for x in v) + ']'


def main():
    ap = argparse.ArgumentParser(description='관절 조그 시험대')
    ap.add_argument('--joint', type=int, default=5, choices=range(1, 7), help='처음 고를 관절')
    ap.add_argument('--step', type=float, default=2.0, help='한 번에 움직일 각도(°)')
    ap.add_argument('--max-total', type=float, default=120.0, help='시작 자세에서 관절당 누적 한계(°)')
    ap.add_argument('--goto', metavar='STATION', help='먼저 이 자세로 간 뒤 조그 (HOME 경유 · E15)')
    ap.add_argument('--kind', default='BOWL', choices=['BOWL', 'CUP'])
    ap.add_argument('--carrying', action='store_true', help='용기를 쥔 채 → 들고 가는 속도 (--goto 에만)')
    a = ap.parse_args()
    if not sys.stdin.isatty():
        sys.exit('터미널에서 직접 실행한다 (키 입력이 필요하다)')

    cc.init('rig_jog')
    log = cc.io_node().get_logger()
    require_controller(cc.io_node(), cc.cfg(), log)          # TS-07
    joint, step = a.joint, min(max(a.step, STEP_MIN), STEP_MAX)
    moved = [0.0] * 6
    try:
        cc.force_off()
        if a.goto:
            log.info(f'E15 — HOME 을 거쳐 {a.goto}.{a.kind} 로 간다')
            cc.move_to('HOME', a.carrying, a.kind)
            cc.move_to(a.goto, a.carrying, a.kind)
        start = cc.joints()
        log.info(f'시작 posj {_fmt(start)}')
        log.info(f'J{joint} 선택 · step {step:g}° · 1~6 관절 · d/→ + · a/← − · ]/[ step · p 자세 · r 시작 자세 · q 끝')
        while True:
            k = _key()
            if k == 'q':
                log.info('끝 — 로봇은 그 자리 · 누적 ' + _fmt(moved))
                return
            if k in '123456' and k:
                joint = int(k)
                log.info(f'J{joint} 선택 (누적 {moved[joint - 1]:+.1f}°)')
                continue
            if k == ']':
                step = min(STEP_MAX, step * 2); log.info(f'step {step:g}°'); continue
            if k == '[':
                step = max(STEP_MIN, step / 2); log.info(f'step {step:g}°'); continue
            if k == 'p':
                from cobot_common.bootstrap import dsr
                d = dsr()
                x = [round(float(v), 2) for v in d.get_current_posx(ref=d.DR_BASE)[0]]
                log.info(f'posj {_fmt(cc.joints())} · posx {x}')
                continue
            if k == 'r':
                back = [-m for m in moved]
                if any(abs(v) > 1e-9 for v in back):
                    log.info(f'시작 자세로 — J1~6 {_fmt(back)}')
                    for j, dv in enumerate(back, start=1):
                        if abs(dv) > 1e-9:
                            cc.move_joint_rel(j, dv, carrying=True)
                    moved = [0.0] * 6
                log.info(f'posj {_fmt(cc.joints())}')
                continue
            delta = {'d': +step, 'RIGHT': +step, 'a': -step, 'LEFT': -step}.get(k)
            if delta is None:
                continue
            delta = max(-STEP_CAP, min(STEP_CAP, delta))
            if abs(moved[joint - 1] + delta) > a.max_total:
                log.warn(f'J{joint} 누적 {moved[joint - 1]:+.1f}° + {delta:+g} 는 한계 ±{a.max_total:g}° 를 넘는다 — 거절')
                continue
            cc.move_joint_rel(joint, delta, carrying=True)
            moved[joint - 1] += delta
            log.info(f'J{joint} {delta:+g}° → 누적 {moved[joint - 1]:+.1f}° · posj {_fmt(cc.joints())}')
    except KeyboardInterrupt:
        log.warn('Ctrl+C — 로봇은 그 자리에 선다')
    finally:
        cc.shutdown()


if __name__ == '__main__':
    main()
