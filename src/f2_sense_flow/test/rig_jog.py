"""로봇을 **키보드로 조금씩 움직여 좌표를 찾는 도구** — 민범진 · 9/22

═══════════════════════════════════════════════════════════════════════════════════════
🔰 이게 무슨 프로그램인가
═══════════════════════════════════════════════════════════════════════════════════════
  "그릇 입이 잔반통 쪽을 보려면 손목을 몇 도 돌려야 하나", "수조 위 자리는 어디인가" 처럼
  **자세와 좌표를 눈으로 찾을 때** 쓴다. 키를 한 번 누르면 그만큼만 움직이고 멈춘다.
  원하는 자세가 나오면 **p 키**를 누른다. 지금 자세가 숫자로 찍히고, 그 숫자를 cell.yaml 에 옮겨 적으면 된다.

  움직이는 방법이 두 가지다. 아무 때나 서로 바꿀 수 있다.
    관절 모드   1~6 키로 관절 하나를 고르고 각도(°)로 돌린다.   손목만 까딱 돌려 보고 싶을 때
    직선 모드   x · y · z 키로 축을 고르고 밀리미터(mm)로 민다.  위로 10 mm 만 올려 보고 싶을 때

  🚨 이 프로그램은 **그리퍼를 만지지 않는다.** 쥐고 있으면 쥔 채로, 빈손이면 빈손으로 움직인다.

───────────────────────────────────────────────────────────────────────────────────────
🔰 두 가지 자세 표현 (p 를 누르면 둘 다 찍힌다)
───────────────────────────────────────────────────────────────────────────────────────
  posj   관절 6개가 각각 몇 도인가.  예) [-180, 0, 90, 0, 0, 180]
         🔔 **로봇의 모양**을 그대로 적는 방법이다. 손목이 어느 쪽으로 감겼는지까지 똑같이 재현된다.
  posx   손끝이 공간의 어느 점에 있나(x y z mm)와 어느 방향을 보는가.  예) [205.8, -445.7, -13.6, …]
         🔔 **위치**를 적는 방법이다. 같은 점이라도 팔이 다른 모양으로 갈 수 있다.
  어느 쪽을 cell.yaml 에 적을지는 그 자리 주석을 따른다. 손목이 크게 감긴 자세는 posj 로 적는다.

───────────────────────────────────────────────────────────────────────────────────────
🔰 하는 순서
───────────────────────────────────────────────────────────────────────────────────────
  ① 터미널 1 에서 로봇을 켠다       sod && sodreal
  ② 터미널 2 에서 빌드             cbc
  ③ 띄운다 (처음에는 꼭 30 % 속도로)
       지금 서 있는 자리에서 그대로 시작
         PREWASH_VEL_SCALE=0.3 python3 src/f2_sense_flow/test/rig_jog.py
       정해진 자리로 먼저 간 다음 시작 (예: 잔반통 자세)
         PREWASH_VEL_SCALE=0.3 python3 src/f2_sense_flow/test/rig_jog.py --goto WASTE --kind BOWL
       용기를 쥔 채 그 자리로 가야 하면 --carrying 을 더 붙인다 (천천히 간다)
  ④ 1~6 으로 관절을 고르고 d / a 로 조금씩 움직인다. 한 번에 움직이는 양은 ] 와 [ 로 바꾼다
  ⑤ 원하는 자세가 되면 **p** → 찍힌 숫자를 cell.yaml 에 옮겨 적는다
  ⑥ r 을 누르면 시작 자세로 되돌아간다. q 로 끝낸다

───────────────────────────────────────────────────────────────────────────────────────
🔰 키 (누르면 **바로** 그만큼 움직이고, 다 움직일 때까지 다음 키를 안 받는다)
───────────────────────────────────────────────────────────────────────────────────────
    1 ~ 6      움직일 관절 고르기 (처음에는 5번 = 손목 까딱)
    x  y  z    직선 이동으로 바꾸기 (BASE 기준 · 단위가 mm 로 바뀐다 · 관절로 돌아가려면 1~6)
    d 또는 →   고른 방향으로 + 만큼
    a 또는 ←   고른 방향으로 − 만큼
    ]  [       한 번에 움직이는 양을 두 배 / 절반 (관절 0.5~10° · 직선 1~50 mm)
    p          **지금 자세를 숫자로 찍는다** (posj · posx 둘 다 · cell.yaml 에 옮길 값)
    r          시작 자세로 되돌린다 (움직인 만큼 반대로 한 번에)
    q          끝낸다 (로봇은 그 자리 · 그리퍼도 그대로)

───────────────────────────────────────────────────────────────────────────────────────
🔰 안전
───────────────────────────────────────────────────────────────────────────────────────
  · 한 번에 최대 10° 까지만. 시작 자세에서 관절 하나가 ±120° 넘게 움직이려 하면 거절한다(--max-total 로 조절)
  · 움직이는 동안에는 키를 안 받는다. 연타해도 쌓이지 않는다
  · 시작할 때 컨트롤러의 툴·TCP 이름을 확인한다(다르면 시작 거부 · TS-07). 힘제어는 시작할 때 끈다
  · 낮은 자세면 곧게 위로 올라온 뒤 HOME 으로 간다(TS-08). 위험하면 Ctrl+C · 손은 비상정지 근처에

파일 이름이 test_ 로 시작하지 않아서 자동 시험(pytest)이 이 파일을 모으지 않는다.
"""
import argparse
import sys
import termios
import tty

import cobot_common as cc
from f2_sense_flow.preflight import go_home_safely, require_controller

STEP_MIN, STEP_MAX, STEP_CAP = 0.5, 10.0, 10.0          # 관절(°)
MM_MIN, MM_MAX, MM_CAP, MM_TOTAL = 1.0, 20.0, 20.0, 150.0  # 직선(mm) — 한 번 20 mm · 누적 ±150 mm


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
    axis, mm_step, mm_moved = None, 5.0, {'x': 0.0, 'y': 0.0, 'z': 0.0}   # 직선 모드
    try:
        cc.force_off()
        if a.goto:
            log.info(f'E15 — HOME 을 거쳐 {a.goto}.{a.kind} 로 간다')
            go_home_safely(a.kind, log, a.carrying)
            up = float(cc.move_to(a.goto, a.carrying, a.kind) or 0.0)
            if up > 0.0:                                   # 접근점이 있는 자리(RINSE 등) — 티칭 자세까지 마저 내려간다 (sense._goto 와 같게)
                log.info(f'{a.goto} 상공에서 {up:.1f} mm 더 내려간다 (티칭 자세까지)')
                cc.move_rel(0.0, 0.0, -up, 'BASE')
        start = cc.joints()
        log.info(f'시작 posj {_fmt(start)}')
        log.info(f'J{joint} 선택 · 한 번에 {step:g}° · 키: 1~6 관절 고르기 · d/→ 더하기 · a/← 빼기 · '
                 ']/[ 움직이는 양 · x·y·z 직선 이동 · p 지금 자세 찍기 · r 시작 자세로 · q 끝')
        while True:
            k = _key()
            if k == 'q':
                log.info('끝낸다 — 로봇은 그 자리에 선다 · 시작 자세에서 움직인 양 ' + _fmt(moved))
                return
            if k in '123456' and k:
                joint, axis = int(k), None
                log.info(f'J{joint} 선택 (누적 {moved[joint - 1]:+.1f}°)')
                continue
            if k in 'xyz' and k:
                axis = k
                log.info(f'BASE {axis.upper()} 축 직선 이동 · step {mm_step:g} mm (누적 {mm_moved[axis]:+.1f} mm)')
                continue
            if k == ']':
                if axis: mm_step = min(MM_MAX, mm_step * 2); log.info(f'step {mm_step:g} mm')
                else: step = min(STEP_MAX, step * 2); log.info(f'step {step:g}°')
                continue
            if k == '[':
                if axis: mm_step = max(MM_MIN, mm_step / 2); log.info(f'step {mm_step:g} mm')
                else: step = max(STEP_MIN, step / 2); log.info(f'step {step:g}°')
                continue
            if k == 'p':
                from cobot_common.bootstrap import dsr
                d = dsr()
                x = [round(float(v), 2) for v in d.get_current_posx(ref=d.DR_BASE)[0]]
                log.info(f'posj {_fmt(cc.joints())} · posx {x}')
                continue
            if k == 'r':
                if any(abs(v) > 1e-9 for v in mm_moved.values()):       # 직선으로 움직인 것부터 되돌린다
                    log.info(f'직선 이동 되돌림 — {mm_moved}')
                    cc.move_rel(-mm_moved['x'], -mm_moved['y'], -mm_moved['z'], 'BASE')
                    mm_moved = {'x': 0.0, 'y': 0.0, 'z': 0.0}
                back = [-m for m in moved]
                if any(abs(v) > 1e-9 for v in back):
                    log.info(f'시작 자세로 — J1~6 {_fmt(back)}')
                    for j, dv in enumerate(back, start=1):
                        if abs(dv) > 1e-9:
                            cc.move_joint_rel(j, dv, carrying=True)
                    moved = [0.0] * 6
                log.info(f'posj {_fmt(cc.joints())}')
                continue
            if axis:                                                    # 직선 모드
                dmm = {'d': +mm_step, 'RIGHT': +mm_step, 'a': -mm_step, 'LEFT': -mm_step}.get(k)
                if dmm is None:
                    continue
                dmm = max(-MM_CAP, min(MM_CAP, dmm))
                if abs(mm_moved[axis] + dmm) > MM_TOTAL:
                    log.warn(f'{axis.upper()} 누적 {mm_moved[axis]:+.1f} + {dmm:+g} mm 는 한계 ±{MM_TOTAL:g} mm 를 넘는다 — 거절')
                    continue
                v = {'x': (dmm, 0.0, 0.0), 'y': (0.0, dmm, 0.0), 'z': (0.0, 0.0, dmm)}[axis]
                cc.move_rel(v[0], v[1], v[2], 'BASE')
                mm_moved[axis] += dmm
                log.info(f'{axis.upper()} {dmm:+g} mm → 누적 {mm_moved[axis]:+.1f} mm')
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
