#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CELL-04 단독 시험 — **진짜 cell.yaml 의 좌표**를 cc.move_to 로 전부 돌아본다. 🚨 Virtual 전용.

확인하는 것
    ① 한석형이 찍은 자세마다: 이름(+ kind · point)으로 불러서 **그 자세에 도착하는가**(가상 로봇이 닿는가 · 도중에 멈추지 않는가)
    ② 접근점이 있는 자세: move_to 가 돌려준 높이만큼 곧게 내려가면 **끝점**에 닿는가 → 다시 올라온다
    ③ 아직 안 찍은 자세(🔴): 로봇을 **움직이지 않고** KeyError 를 내는가
도는 순서는 한석형 스크립트(rig_f1.py v6)의 작업 순서 그대로 — 그릇 한 바퀴 → 컵 한 바퀴.

실행 (저장소 루트 · rosinfo 로 RANGE=LOCALHOST · sodvir 가 떠 있어야 한다 — 이미 떠 있으면 그대로 쓴다)
    soc && python3 src/cobot_common/test/rig_coords.py
cell.yaml 의 limits·motion 은 아직 비어 있어서(한석형 몫) **rig_coords.yaml 의 Virtual 시험 값으로 채운 사본**을 임시 폴더에 만들어 쓴다.
    진짜 파일은 건드리지 않는다. 좌표는 진짜 값 그대로다.
종료 코드 0(통과) / 1(실패) / 2(실행 거부).
"""
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
    ('RET_B', False, None, 1), ('WASTE', True, 'BOWL', None), ('SPONGE_BED_B', True, None, 'place'),
    ('TOOL_SPONGE', False, None, 'pick'), ('HOME', True, None, None), ('SPONGE_BED_B', True, None, 'wash'),
    ('HOME', True, None, None), ('TOOL_SPONGE', True, None, 'return'), ('SPONGE_BED_B', False, None, 'place'),
    ('RINSE', True, 'BOWL', None), ('HOME', True, None, None), ('RACK_B1', True, None, None),
    ('HOME', False, None, None), ('RACK_B2', True, None, None), ('HOME', False, None, None),
    ('RET_C', False, None, 1), ('WASTE', True, 'CUP', None), ('SPONGE_BED_C', True, None, 'place'),
    ('TOOL_BRUSH', False, None, 'pick'), ('HOME', True, None, None), ('SPONGE_BED_C', True, None, 'wash'),
    ('HOME', True, None, None), ('TOOL_BRUSH', True, None, 'return'), ('SPONGE_BED_C', False, None, 'regrip'),
    ('RINSE', True, 'CUP', None), ('HOME', True, None, None), ('RACK_C1', True, None, None),
    ('HOME', False, None, None), ('RACK_C2', True, None, None), ('HOME', False, None, None),
]
# 아직 안 찍은 자세 — 움직이지 않고 KeyError 여야 한다
UNTAUGHT = [('WEIGH', 'BOWL', None), ('WEIGH', 'CUP', None), ('SOAP', 'BOWL', None), ('SOAP', 'CUP', None),
            ('ISOLATE', 'BOWL', None), ('ISOLATE', 'CUP', None), ('RET_B', None, 2), ('RET_C', None, 2)]


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
    with open(HERE / 'rig_coords.yaml', encoding='utf-8') as f:
        p = yaml.safe_load(f)
    tmp = _filled_copy(p['fill'])
    os.environ['PREWASH_CONFIG_DIR'] = str(tmp)

    import cobot_common as cc
    from cobot_common.bootstrap import dsr      # cobot_common 자체 시험이라 내부 함수를 쓴다
    from cobot_common.motion import _named_pose

    cc.init('rig_coords')
    log = cc.io_node().get_logger()
    tol, fails, rows = p['tol'], [], []
    try:
        d = dsr()
        if d.get_robot_system() != d.ROBOT_SYSTEM_VIRTUAL:
            log.error('Virtual 이 아니다 → 실행하지 않는다')
            return 2
        safe_z = float(cc.cfg()['cell']['limits']['safe_z_mm'])

        def posx():
            return [float(v) for v in d.get_current_posx(ref=d.DR_BASE)[0]]

        def posj():
            return [float(v) for v in d.get_current_posj()]

        def off(now, want):
            """(위치 오차 mm, 방향 오차 deg)"""
            return math.dist(now[:3], want[:3]), _rot_diff_deg(now, want)

        def record(label, ok, detail):
            rows.append((label, ok, detail))
            log.info(f"{'OK  ' if ok else 'FAIL'} {label:<34} {detail}")
            if not ok:
                fails.append(label)

        log.info(f'──── ① ② 찍은 자세 {len(ROUTE)}번 이동 (안전 높이 {safe_z:g} mm — Virtual 시험 값) ────')
        for station, carrying, kind, point in ROUTE:
            label = station + (f' {kind}' if kind else '') + (f' point={point}' if point is not None else '')
            _, spec = _named_pose(station, kind, point)
            try:
                up = cc.move_to(station, carrying, kind, point)
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
            stop[2] = max(stop[2], safe_z)
            dpos, drot = off(posx(), stop)
            ok = dpos <= tol['pos_mm'] and drot <= tol['rot_deg'] and abs(up - (stop[2] - end[2])) < 1e-6
            record(label, ok, f"{'접근점' if 'approach_posx' in spec else '상공'} z {stop[2]:g} · 오차 {dpos:.2f} mm {drot:.2f}° · 남은 높이 {up:.1f} mm")
            if up > 0.0:                                                # ② 곧게 내려가면 끝점인가 → 다시 올라온다
                cc.move_rel(0.0, 0.0, -up, 'BASE')
                time.sleep(p['settle_s'])
                dpos, drot = off(posx(), end)
                hit = dpos <= tol['pos_mm'] and drot <= tol['rot_deg']
                if not hit and station in p['known_tilted']:             # 이미 아는 어긋남 — 재서 보여 주기만 한다
                    log.warn(f"⚠    └ {station}: 곧게 내려간 자리가 찍은 끝점과 {dpos:.2f} mm · {drot:.2f}° 어긋난다 (접근점을 끝점 위로 다시 찍는다)")
                else:
                    record(f'  └ {up:.1f} mm 하강 → 끝점', hit, f'끝점 z {end[2]:g} · 오차 {dpos:.2f} mm {drot:.2f}°')
                cc.move_rel(0.0, 0.0, up, 'BASE')

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

        n_ok = sum(1 for _, ok, _ in rows if ok)
        log.info(f"결과: {'통과' if not fails else '실패'} — OK {n_ok} · FAIL {len(fails)}" + (f' → {fails}' if fails else ''))
        return 0 if not fails else 1
    except KeyboardInterrupt:
        return 130
    finally:
        cc.shutdown()
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    sys.exit(main())
