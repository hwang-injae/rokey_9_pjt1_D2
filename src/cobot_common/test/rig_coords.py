#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CELL-04 · V-22 · V-19 — **진짜 cell.yaml 의 좌표**를 cc.move_to 로 흐름 순서대로 돌아본다.

확인하는 것
    ① 찍은 자세마다: 이름(+ kind · point)으로 불러서 **그 자세에 도착하는가**(닿는가 · 도중에 멈추지 않는가) — V-19 도달 범위
    ② 접근점이 있는 자세: move_to 가 돌려준 높이만큼 곧게 내려가면 **끝점**에 닿는가 → 다시 올라온다 — V-22 재현 오차
    ③ 아직 안 찍은 자세(🔴): 로봇을 **움직이지 않고** KeyError 를 내는가
도는 순서는 공정 흐름 그대로 — 그릇 한 바퀴 → 컵 한 바퀴(9/20 E7 로 안전 높이 경유가 없어져 **구간마다** 보는 것이 중요하다).

실행 — 두 가지 모드 (rosinfo 로 RANGE=LOCALHOST 확인 · AGENTS 규칙 13)
  ① Virtual 시험 (기본)                sod && sodvir  →  soc && python3 src/cobot_common/test/rig_coords.py
       cell.yaml 의 limits·motion 이 비어 있어도 돌게 **rig_coords.yaml 의 시험 값으로 채운 사본**을 임시 폴더에 만들어 쓴다
       (진짜 파일은 건드리지 않는다. 좌표는 진짜 값 그대로). 🚨 Virtual 이 아니면 거부한다.
  ② 실기 확인 (V-22·V-19 · 9/21 저녁)  sod && sodreal →  PREWASH_VEL_SCALE=0.3 python3 src/cobot_common/test/rig_coords.py --real
       진짜 cell.yaml 을 **그대로** 쓴다(한석형이 limits·motion·presets 를 채운 뒤). **구간마다 Enter** 로 확인하며 넘어간다.
       막히는 구간이 나오면 q 로 멈추고 그 자리에서 한석형이 접근점을 추가로 찍는다 → `--from N` 으로 그 구간부터 다시.
       🚨 E-Stop 을 손에 잡고, 로봇 반경 안에 사람이 없는지 확인한 뒤에 시작한다.
  · 실기 절차를 미리 익히려면 Virtual 에서 `--step`(채운 값 + 구간마다 Enter)으로 예행연습한다.

끝에 **오차 표**를 찍는다(V-22 산출물). 종료 코드 0(통과) / 1(실패) / 2(실행 거부).
"""
import argparse
import math
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
REAL_CONFIG = HERE.parent / 'config'

# (이름, 들고 있나, kind, point) — 한석형 스크립트의 작업 순서
ROUTE = [
    ('HOME', False, None, None),
    ('RET_B', False, None, 1), ('WEIGH', True, 'BOWL', None), ('WASTE', True, 'BOWL', None), ('SPONGE_BED_B', True, None, 'place'),
    ('TOOL_SPONGE', False, None, 'pick'), ('HOME', True, None, None), ('SPONGE_BED_B', True, None, 'wash'),
    ('HOME', True, None, None), ('TOOL_SPONGE', True, None, 'return'), ('SPONGE_BED_B', False, None, 'place'),
    ('RINSE', True, 'BOWL', None), ('HOME', True, None, None), ('RACK_B1', True, None, None),
    ('HOME', False, None, None), ('RACK_B2', True, None, None), ('HOME', False, None, None),
    ('RET_C', False, None, 1), ('WEIGH', True, 'CUP', None), ('WASTE', True, 'CUP', None), ('SPONGE_BED_C', True, None, 'place'),
    ('TOOL_BRUSH', False, None, 'pick'), ('HOME', True, None, None), ('SPONGE_BED_C', True, None, 'wash'),
    ('HOME', True, None, None), ('TOOL_BRUSH', True, None, 'return'), ('SPONGE_BED_C', False, None, 'regrip'),
    ('RINSE', True, 'CUP', None), ('HOME', True, None, None), ('RACK_C1', True, None, None),
    ('HOME', False, None, None), ('RACK_C2', True, None, None), ('HOME', False, None, None),
]
# 아직 안 찍은 자세 — 움직이지 않고 KeyError 여야 한다
UNTAUGHT = [('SOAP', 'BOWL', None), ('SOAP', 'CUP', None),
            ('ISOLATE', 'BOWL', None), ('ISOLATE', 'CUP', None)]


def _filled_copy(fill):
    """진짜 설정 폴더의 사본을 만들고, cell.yaml 의 비어 있는 limits·motion 만 fill 로 채운다 → 사본 폴더 경로."""
    tmp = Path(tempfile.mkdtemp(prefix='rig_coords_'))
    shutil.copy(REAL_CONFIG / 'params.yaml', tmp / 'params.yaml')
    with open(REAL_CONFIG / 'cell.yaml', encoding='utf-8') as f:
        doc = yaml.safe_load(f)
    for section, values in fill.items():
        target = doc['cell'].setdefault(section, {})
        for key, value in values.items():
            if target.get(key) is None:
                target[key] = value
    with open(tmp / 'cell.yaml', 'w', encoding='utf-8') as f:
        yaml.safe_dump(doc, f, allow_unicode=True)
    return tmp


def _rotation(rx, ry, rz):
    """두산 posx 의 방향(ZYZ 오일러각, deg) → 회전 행렬."""
    a, b, c = (math.radians(v) for v in (rx, ry, rz))
    ca, sa, cb, sb, cc_, sc = math.cos(a), math.sin(a), math.cos(b), math.sin(b), math.cos(c), math.sin(c)
    return [[ca * cb * cc_ - sa * sc, -ca * cb * sc - sa * cc_, ca * sb],
            [sa * cb * cc_ + ca * sc, -sa * cb * sc + ca * cc_, sa * sb],
            [-sb * cc_, sb * sc, cb]]


def _rot_diff_deg(p, q):
    r1, r2 = _rotation(*p[3:]), _rotation(*q[3:])
    trace = sum(r1[i][k] * r2[i][k] for i in range(3) for k in range(3))
    return math.degrees(math.acos(max(-1.0, min(1.0, (trace - 1.0) / 2.0))))


def main() -> int:
    ap = argparse.ArgumentParser(description='CELL-04·V-22·V-19 좌표 순회 (기본 Virtual · --real 로 실기)')
    ap.add_argument('--real', action='store_true', help='실기: 진짜 cell.yaml 을 그대로 쓰고 구간마다 Enter 로 확인한다')
    ap.add_argument('--step', action='store_true', help='구간마다 Enter (실기는 기본으로 켜진다)')
    ap.add_argument('--from', dest='start', type=int, default=1, help='몇 번째 이동부터 돌까 (1 부터 · 막힌 구간을 고친 뒤 이어서)')
    opt = ap.parse_args([v for v in sys.argv[1:] if not v.startswith('--ros-args')])
    opt.step = opt.step or opt.real

    with open(HERE / 'rig_coords.yaml', encoding='utf-8') as f:
        p = yaml.safe_load(f)
    tmp = None if opt.real else _filled_copy(p['fill'])        # 실기는 진짜 설정 그대로 — 시험 값으로 실기를 움직이지 않는다
    if tmp is not None:
        os.environ['PREWASH_CONFIG_DIR'] = str(tmp)

    import cobot_common as cc
    from cobot_common.bootstrap import dsr      # cobot_common 자체 시험이라 내부 함수를 쓴다
    from cobot_common.motion import _named_pose

    cc.init('rig_coords')
    log = cc.io_node().get_logger()
    tol, fails, rows = p['tol'], [], []
    try:
        d = dsr()
        virtual = d.get_robot_system() == d.ROBOT_SYSTEM_VIRTUAL
        if not opt.real and not virtual:
            log.error('Virtual 이 아니다 → 실행하지 않는다 (실기는 --real, 값이 채워진 cell.yaml 로)')
            return 2
        if opt.real:
            scale = cc.cfg()['run']['vel_scale']
            log.info(f"실기 절차{' (Virtual 에서 돈다)' if virtual else ''} · vel_scale {scale:g} · 구간마다 Enter")
            if not virtual and scale > 0.3:
                log.error(f'첫 실기는 vel_scale ≤ 0.3 이다 (지금 {scale:g}) → PREWASH_VEL_SCALE=0.3 으로 다시')
                return 2
            if not virtual and input('    🚨 E-Stop 을 손에 · 로봇 반경 안에 사람 없음 · 격리(rosinfo) 확인했으면 Enter > ').strip().lower() == 'q':
                return 2

        def posx():
            return [float(v) for v in d.get_current_posx(ref=d.DR_BASE)[0]]

        def posj():
            return [float(v) for v in d.get_current_posj()]

        def off(now, want):
            """(위치 오차 mm, 방향 오차 deg)"""
            return math.dist(now[:3], want[:3]), _rot_diff_deg(now, want)

        def _exits():
            """이 칸에서 꽂고 놓은 뒤 빠져나오는 상대 이동 목록(BASE). 접근점이 있는 칸은 수직 복귀라 비어 있다."""
            slots = ((cc.cfg().get('cell') or {}).get('rack') or {}).get('slots') or {}
            return (slots.get(station) or {}).get('exit_rel_mm') or []

        def record(label, ok, detail):
            rows.append((label, ok, detail))
            log.info(f"{'OK  ' if ok else 'FAIL'} {label:<34} {detail}")
            if not ok:
                fails.append(label)

        log.info(f'──── ① ② 찍은 자세 {len(ROUTE)}번 이동 — 자세에서 자세로 곧장(9/20 E7) ────')
        for n, (station, carrying, kind, point) in enumerate(ROUTE, start=1):
            label = station + (f' {kind}' if kind else '') + (f' point={point}' if point is not None else '')
            if n < opt.start:
                continue
            _, spec = _named_pose(station, kind, point)
            if opt.step:
                log.info(f'[{n}/{len(ROUTE)}] 다음 이동: {label} · {"들고" if carrying else "빈손"}')
                if input('    Enter = 이동 / q = 그만(여기 번호를 --from 에 적어 이어서) > ').strip().lower() == 'q':
                    raise KeyboardInterrupt
            try:
                up = cc.move_to(station, carrying, kind, point)
            except cc.MoveIncomplete as e:                              # 컨트롤러가 이동을 도중에 세웠다 — move_to 가 알려 준다(9/20)
                if station in p['known_path_stop']:
                    log.warn(f'⚠  {label}: {e}')
                    log.warn('⚠    └ 이미 아는 경로 문제(rig_coords.yaml known_path_stop) — 실패로 세지 않고 HOME 으로 돌아가 계속한다')
                else:
                    record(label, False, f'move_to 오류: MoveIncomplete: {e}')
                cc.move_to('HOME', carrying)
                continue
            except Exception as e:                                      # noqa: BLE001 — 어느 자세에서 막혔는지 표에 남긴다
                record(label, False, f'move_to 오류: {type(e).__name__}: {e}')
                continue
            time.sleep(p['settle_s'])
            if 'posj' in spec:
                worst = max(abs(a - b) for a, b in zip(posj(), spec['posj']))
                record(label, up == 0.0 and worst <= tol['joint_deg'], f'관절 자세 · 가장 큰 오차 {worst:.2f}°')
                continue
            end = spec.get('posx') or spec['approach_posx']
            stop = list(spec.get('approach_posx') or end)
            dpos, drot = off(posx(), stop)
            ok = dpos <= tol['pos_mm'] and drot <= tol['rot_deg'] and abs(up - (stop[2] - end[2])) < 1e-6
            record(label, ok, f"{'접근점' if 'approach_posx' in spec else '티칭 자세'} z {stop[2]:g} · 오차 {dpos:.2f} mm {drot:.2f}° · 남은 높이 {up:.1f} mm")
            if up > 0.0:                                                # ② 곧게 내려가면 끝점인가 → 다시 올라온다
                if opt.step and input(f'    끝점까지 {up:.1f} mm 내려간다 — Enter = 하강 / s = 건너뛰기 > ').strip().lower() == 's':
                    continue
                cc.move_rel(0.0, 0.0, -up, 'BASE')
                time.sleep(p['settle_s'])
                dpos, drot = off(posx(), end)
                hit = dpos <= tol['pos_mm'] and drot <= tol['rot_deg']
                if not hit and station in p['known_tilted']:             # 이미 아는 어긋남 — 재서 보여 주기만 한다
                    log.warn(f"⚠    └ {station}: 곧게 내려간 자리가 찍은 끝점과 {dpos:.2f} mm · {drot:.2f}° 어긋난다 (접근점을 끝점 위로 다시 찍는다)")
                else:
                    record(f'  └ {up:.1f} mm 하강 → 끝점', hit, f'끝점 z {end[2]:g} · 오차 {dpos:.2f} mm {drot:.2f}°')
                cc.move_rel(0.0, 0.0, up, 'BASE')

            for k, step_mm in enumerate(_exits(), start=1):              # ④ 팔레트 칸에서 빠져나오기 (cell.yaml 의 exit_rel_mm)
                dx, dy, dz = (float(v) for v in step_mm)
                if opt.step and input(f'    빠져나오기 {k}: Δ({dx:g}, {dy:g}, {dz:g}) mm — Enter = 이동 / s = 건너뛰기 > ').strip().lower() == 's':
                    break
                cc.move_rel(dx, dy, dz, 'BASE')
                log.info(f'  ↳ 빠져나오기 {k}: Δ({dx:g}, {dy:g}, {dz:g}) mm — 여기서 팔레트에 안 걸리는지 본다')

        log.info('──── ③ 아직 안 찍은 자세 — 움직이지 않고 KeyError ────')
        for station, kind, point in UNTAUGHT:
            before = posj()
            try:
                cc.move_to(station, False, kind, point)
                refused = False
            except KeyError:
                refused = True
            still = max(abs(a - b) for a, b in zip(posj(), before)) < 0.01
            record(f'{station} {kind or ""} {point or ""}'.strip() + ' (안 찍음)', refused and still, 'KeyError · 안 움직임' if refused and still else '움직였거나 오류가 안 났다')

        log.info('──── 오차 표 (V-22 산출물 — 기록 문서에 붙인다) ────')
        for label, ok, detail in rows:
            log.info(f"  {'OK  ' if ok else 'FAIL'} | {label:<34} | {detail}")
        n_ok = sum(1 for _, ok, _ in rows if ok)
        log.info(f"결과: {'통과' if not fails else '실패'} — OK {n_ok} · FAIL {len(fails)}" + (f' → {fails}' if fails else ''))
        return 0 if not fails else 1
    except KeyboardInterrupt:
        log.warn('사람이 멈췄다(q 또는 Ctrl+C)')
        return 130
    finally:
        cc.shutdown()
        if tmp is not None:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    sys.exit(main())
