#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""F2-01·F2-02 Virtual 확인 — sense.py 의 **이동 부분**을 가상 로봇으로 실제로 돌린다. 🚨 Virtual 전용.

왜 이걸 따로 만드나
    Virtual 에는 **힘·무게·접촉이 없고**(AGENTS §5) **그리퍼 드라이버도 없다**(V-20 기록).
    그래서 sense.py 를 그대로 돌리면 cc.weigh · cc.grip_level · cc.grip_width 에서 멈춘다.
    → Virtual 에 **있는 것(이동)은 진짜로**, **없는 것(무게·그리퍼)만 가짜로** 바꿔 끼운다.
       바꿔 끼운 것은 실행할 때마다 로그에 찍는다 — 이 시험을 "다 됐다" 로 오해하면 안 된다.

실행 (저장소 루트에서, 격리 상태 solo — AGENTS 규칙 13)
    rosinfo                                                       # 🚨 RANGE=LOCALHOST 확인
    터미널 1:  sod && sodvir                                       (이미 떠 있으면 그대로 쓴다)
    터미널 2:  soc && python3 src/f2_sense_flow/test/rig_f2_virtual.py all
               soc && python3 src/f2_sense_flow/test/rig_f2_virtual.py shake -n 3

무엇을 확인하나 (실기 전에 잡을 수 있는 것)
    ① 세 함수가 **두산 오류 없이** 끝난다 — 연속 n 회 (SDD §3.2 ⑧: "첫 번째만 되는" 결함)
    ② cc.move_to 가 **남은 높이**를 돌려주고 _goto 가 그만큼 더 내려간다
       (WEIGH 는 안전 높이 위라 up=0, WASTE·RINSE 는 아래라 up=50 이 나오게 좌표를 갈라 뒀다)
    ③ 🔑 털기 한 주기가 **설정한 period_s 에 맞게** 걸리는가 (time_s 를 period/4·period/2 로 나눈 것)
    ④ force_off() 뒤에 관절 이동이 되는가 (순응 중 movej 거부 = 2.1903 을 안 밟는지)
    ⑤ 담금이 내려간 만큼 **정확히 되올라오는가** (Z 가 제자리)

🚨 여기서 확인 **안 되는 것** — 전부 실기(V-01·02·05·07·16·23)로 간다
    무게 값 · 잔반 임계 · 파지 폭/힘 · 미끄러짐 판정 · 충돌 감지 오작동 · 안전 스위치

설정: 좌표는 같은 폴더의 config_virtual/cell.yaml(가상 좌표), f2 값은 **팀 params.yaml 그대로**.
      (값을 두 곳에 두면 한쪽만 고치는 사고가 난다 — 실행할 때 임시 폴더에 합쳐서 쓴다)
종료 코드 0(통과) / 1(실패) / 2(실행 거부) / 130(Ctrl+C).
"""
import argparse
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent.parent                       # src/f2_sense_flow/test → 저장소 루트
TEAM_PARAMS = REPO / 'src' / 'cobot_common' / 'config' / 'params.yaml'

# 🚨 cc.init 이 설정을 읽기 **전에** 임시 폴더를 만들어 가리킨다.
_TMP = Path(tempfile.mkdtemp(prefix='rig_f2_virtual_'))
shutil.copy(HERE / 'config_virtual' / 'cell.yaml', _TMP / 'cell.yaml')
shutil.copy(TEAM_PARAMS, _TMP / 'params.yaml')         # f2 값의 정본은 팀 파일 하나뿐
os.environ['PREWASH_CONFIG_DIR'] = str(_TMP)

import cobot_common as cc                              # noqa: E402
from cobot_common.bootstrap import dsr                 # noqa: E402  rig 라 내부 함수를 쓴다

from f2_sense_flow import sense                        # noqa: E402

_FAKE_WIDTH_MM = 2.0          # 가짜 그리퍼가 늘 돌려주는 폭 — 미끄러짐 판정은 실기에서만 뜻이 있다
_FAKE_RAW_G = 180.0           # 가짜 하중 — 빈 용기 기준값과 같게 두어 "잔반 0 g" 이 되게


def _stub_what_virtual_lacks(log):
    """🚨 Virtual 에 없는 것만 가짜로 바꾼다. 이동은 **진짜 가상 로봇**이 한다."""
    calls = {'weigh': 0, 'grip_level': 0, 'grip_width': 0}

    def fake_weigh(n, reset=False):
        calls['weigh'] += 1
        return _FAKE_RAW_G

    def fake_grip_level(kind, level):
        calls['grip_level'] += 1
        return _FAKE_WIDTH_MM

    def fake_grip_width():
        calls['grip_width'] += 1
        return _FAKE_WIDTH_MM

    cc.weigh = fake_weigh
    cc.grip_level = fake_grip_level
    cc.grip_width = fake_grip_width
    log.warn('🚨 Virtual 에 없는 것을 가짜로 바꿔 끼웠다 — cc.weigh · cc.grip_level · cc.grip_width')
    log.warn('   이 시험은 **이동만** 본다. 무게·파지·미끄러짐은 실기(V-01·02·05·07·16·23)에서 본다')
    return calls


def _z():
    d = dsr()
    return float(d.get_current_posx(ref=d.DR_BASE)[0][2])


def _j(i):
    return float(dsr().get_current_posj()[i - 1])


def main() -> int:
    ap = argparse.ArgumentParser(description='F2-01·F2-02 Virtual 확인 (이동만)')
    ap.add_argument('which', choices=['weigh', 'shake', 'dip', 'all'])
    ap.add_argument('-n', type=int, default=3, help='연속 호출 횟수 (SDD §3.2 ⑧ — 3 이상)')
    ap.add_argument('--kind', default='BOWL', choices=['BOWL', 'CUP'])
    ap.add_argument('--real', action='store_true', help='🚨 Virtual 이 아니어도 실행 (쓰지 마라)')
    a = ap.parse_args()

    cc.init('rig_f2_virtual')
    log = cc.io_node().get_logger()
    fails = []

    def check(what, ok, detail=''):
        log.info(f'{"OK  " if ok else "FAIL"} {what} {detail}')
        if not ok:
            fails.append(what)

    try:
        d = dsr()
        if d.get_robot_system() != d.ROBOT_SYSTEM_VIRTUAL and not a.real:
            log.error('🚨 Virtual 이 아니다 → 실행하지 않는다. 이 좌표는 가상 로봇용이다')
            return 2

        calls = _stub_what_virtual_lacks(log)
        conf = cc.cfg()['f2']
        safe_z = cc.cfg()['cell']['limits']['safe_z_mm']
        log.info(f'설정 — safe_z {safe_z} mm · shake.WASTE {conf["shake"]["WASTE"]} · dip {conf["dip"]}')

        cc.move_to('HOME', False)                       # 늘 같은 자리에서 시작한다

        # ── weigh : 이동 + (가짜) 측정 ──────────────────────────────
        if a.which in ('weigh', 'all'):
            log.info(f'── weigh × {a.n} ──')
            for i in range(1, a.n + 1):
                t0 = time.monotonic()
                r = sense.weigh(a.kind)
                check(f'weigh {i}/{a.n}', r.ok,
                      f'잔반 {r.weight_g:.1f} g · Z {_z():.1f} mm · {time.monotonic() - t0:.2f} s')
            # WEIGH 는 안전 높이 **위**라 남은 높이가 0 이어야 한다
            check('WEIGH 는 안전 높이 위 → 더 내려가지 않는다', _z() >= safe_z - 1.0,
                  f'Z {_z():.1f} ≥ safe_z {safe_z}')

        # ── shake : 관절 왕복 (제일 중요) ────────────────────────────
        if a.which in ('shake', 'all'):
            log.info(f'── shake(WASTE) × {a.n} ──')
            p = conf['shake']['WASTE']
            joint, period = int(p['joint']), float(p['period_s'])
            cycles = int(p['cycles'])
            # 🚨 먼저 WASTE **티칭 자세까지** 보내 놓고 잰다. 안 그러면 shake 안의 _goto 가 일으킨
            #    관절 변화까지 "흔들고 제자리로 안 왔다" 로 잡힌다(시험대 쪽 문제였다).
            #    cc.move_to 만 부르면 **상공까지만** 가서 남은 50 mm 하강이 J5 를 또 바꾼다
            #    → sense._goto 를 그대로 써야 같은 자세가 된다.
            sense._goto('WASTE', True)
            for i in range(1, a.n + 1):
                j0 = _j(joint)
                t0 = time.monotonic()
                r = sense.shake('WASTE', cycles, a.kind)
                took = time.monotonic() - t0
                back = abs(_j(joint) - j0)
                check(f'shake {i}/{a.n}', r.ok, f'{took:.2f} s · J{joint} 복귀오차 {back:.2f}°')
                # 🔑 한 주기가 period_s 에 맞나 (이동 외 시간이 섞이므로 하한만 본다)
                check(f'shake {i} 주기 — {cycles}회 × {period:.2f} s 이상 걸린다',
                      took >= cycles * period * 0.5,
                      f'실제 {took:.2f} s vs 설정 {cycles * period:.2f} s '
                      f'(짧으면 time_s 를 안 나눴거나 컨트롤러가 무시한 것)')
                check(f'shake {i} — 가운데로 돌아왔다', back < 1.0, f'{back:.2f}°')
            # WASTE 는 안전 높이 **아래** → _goto 가 더 내려갔어야 한다
            check('WASTE 는 안전 높이 아래 → 남은 높이만큼 내려갔다', _z() < safe_z - 1.0,
                  f'Z {_z():.1f} < safe_z {safe_z}')

        # ── dip : Z 하강·상승 ───────────────────────────────────────
        if a.which in ('dip', 'all'):
            log.info(f'── dip(RINSE) × {a.n} ──')
            depth = float(conf['dip']['RINSE']['depth_mm'])
            # 🚨 shake 와 같은 이유로 먼저 RINSE **티칭 자세까지** 보내 놓는다 (cc.move_to 는 상공까지만)
            sense._goto('RINSE', True)
            for i in range(1, a.n + 1):
                z_before = _z()
                t0 = time.monotonic()
                r = sense.dip('RINSE', 1, a.kind)
                took = time.monotonic() - t0
                z_after = _z()
                check(f'dip {i}/{a.n}', r.ok, f'{took:.2f} s · Z {z_after:.1f} mm')
                check(f'dip {i} — 내려간 만큼 되올라왔다', abs(z_after - z_before) < 1.0,
                      f'Z {z_before:.1f} → {z_after:.1f} (담금 깊이 {depth:.0f} mm)')

        cc.move_to('HOME', False)
        log.info(f'가짜로 부른 횟수 — weigh {calls["weigh"]} · grip_level {calls["grip_level"]} '
                 f'· grip_width {calls["grip_width"]}')
        log.info(f'결과: {"통과" if not fails else "실패 — " + ", ".join(fails)}')
        log.warn('🚨 이 통과는 **이동만** 확인한 것이다. 무게·파지·미끄러짐은 실기에서 다시 본다')
        return 0 if not fails else 1

    except KeyboardInterrupt:
        log.warning('Ctrl+C — 정지 명령을 보내고 끝낸다')
        return 130
    finally:
        cc.shutdown()
        shutil.rmtree(_TMP, ignore_errors=True)


if __name__ == '__main__':
    sys.exit(main())
