#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V-03 — 힘제어를 켠 채 X·Y 로 움직일 수 있는가 (솔로 그릇 안쪽 바닥을 누르며 문지르기). 실기 전용 · Virtual 은 흐름만.

실행 (저장소 루트, 격리 상태 solo — AGENTS 규칙 13)
    Virtual 흐름 확인 :  sod && sodvir  →  soc && python3 src/cobot_common/test/rig_v03.py
    실기             :  sod && sodreal →  soc && python3 src/cobot_common/test/rig_v03.py --real
준비(로봇 정지 상태): 그릇 중심을 HOME 바로 아래에 테이프로 고정 · 솔을 그리퍼에 쥐여 둔다('o' → 넣고 → 'c')
        · rig_v03.yaml 의 approach_down_mm = (솔 끝 → 그릇 안쪽 바닥) − 30 mm
🚨 엔터를 누른 뒤에는 키보드에서 손을 떼고 한 손은 E-Stop, 눈은 로봇. 속도는 vel_scale 0.3(바꾸려면 PREWASH_VEL_SCALE).

흐름: HOME → 빠른 접근(approach_down_mm) → contact_down(바닥 찾기, 못 찾으면 힘제어 없이 중단)
      → backoff 로 살짝 들고 → 제자리 누르기 3·4·5 N → 누른 채 문지르기(move_periodic 8자 → move_spiral) → 후퇴 → HOME
힘은 상대 모드라, 이미 눌린 채 켜면 목표만큼 더 누른다 → 매번 backoff 로 공중에서 켜고 3 mm 만 내려가 닿게 한다.
누르는 힘 = 공중에서 잰 기준값 대비 Fz 변화. 어느 순간이든 limit_n 을 넘으면 즉시 힘 해제 → 후퇴.
설정은 같은 폴더의 rig_v03_config/(시험 전용 cell.yaml) · rig_v03.yaml. 힘 로그는 log_dir 에 CSV.
종료 코드 0(통과) / 1(실패·중단) / 2(실행 거부) / 130(Ctrl+C).
"""
import argparse
import csv
import os
import statistics
import sys
import time
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
os.environ['PREWASH_CONFIG_DIR'] = str(HERE / 'rig_v03_config')      # cc.init 이 설정을 읽기 전에
os.environ.setdefault('PREWASH_VEL_SCALE', '0.3')                     # 첫 실기 저속 (AGENTS 규칙 1)

import cobot_common as cc                                               # noqa: E402
from cobot_common.bootstrap import dsr                                  # noqa: E402  cobot_common 자체 시험이라 내부 함수를 쓴다


class Run:
    """한 번의 V-03 실행: 힘 기록·구간 통계·CSV."""

    def __init__(self, d, p, log):
        self.d, self.p, self.log = d, p, log
        self.rows = []
        self.results = []
        self.baseline = 0.0
        self.t0 = time.monotonic()

    def z(self):
        return self.d.get_current_posx(ref=self.d.DR_BASE)[0][2]

    def move_z(self, dz, vel, acc):
        s = cc.cfg()['run']['vel_scale']
        ret = self.d.movel([0.0, 0.0, float(dz), 0.0, 0.0, 0.0], vel=vel * s, acc=acc,
                           ref=self.d.DR_BASE, mod=self.d.DR_MV_MOD_REL)
        if ret != 0:
            raise RuntimeError(f'movel(Z {dz:+.1f} mm) 실패')

    def zero(self):
        """공중에서 Fz 기준값을 잡는다(툴 무게·옵셋 제거)."""
        self.baseline = statistics.mean(cc.read_force()[2] for _ in range(5))

    def sample(self, phase, target, seconds=None, until_motion=False):
        """seconds 동안 또는 비동기 동작이 끝날 때까지 힘을 기록. limit_n 넘으면 ForceLimitError."""
        p = self.p
        start = time.monotonic()
        vals = []
        while True:
            f = cc.read_force()
            press = abs(f[2] - self.baseline)
            now = time.monotonic()
            self.rows.append([phase, round(now - self.t0, 3), f[0], f[1], f[2], round(press, 3), target])
            if now - start >= p['settle_s']:
                vals.append(press)
            if press > p['limit_n']:
                raise cc.ForceLimitError(f'{phase}: 누르는 힘 {press:.1f} N > limit {p["limit_n"]} N')
            if until_motion:
                if self.d.check_motion() == 0:
                    break
            elif now - start >= seconds:
                break
            if now - start > cc.cfg()['cell']['limits']['timeout_s']:
                raise cc.MotionTimeout(f'{phase}: 시간 초과')
            time.sleep(p['sample_s'])
        self.result(phase, target, vals)

    def result(self, phase, target, vals):
        p = self.p
        if not vals:
            self.results.append((phase, target, None, None, None, 0, False))
            return
        mean, mx = statistics.mean(vals), max(vals)
        sd = statistics.pstdev(vals)
        ok = abs(mean - target) <= p['tol_n'] and mx <= p['limit_n']
        self.results.append((phase, target, mean, sd, mx, len(vals), ok))
        self.log.info(f'  {phase}: 목표 {target:.1f} N · 평균 {mean:.2f} · 흔들림 {sd:.2f} · 최대 {mx:.2f} N · {"OK" if ok else "FAIL"}')

    def press_on(self, target):
        """backoff 로 든 공중에서 힘제어를 켠다 → 3 mm 내려가 닿는다."""
        self.zero()
        cc.force_on('z', target, self.p['limit_n'])

    def lift(self):
        cc.force_off()
        self.move_z(self.p['backoff_mm'], self.p['approach_vel_mm_s'], self.p['approach_acc_mm_s2'])

    def save(self):
        os.makedirs(self.p['log_dir'], exist_ok=True)
        path = os.path.join(self.p['log_dir'], time.strftime('v03_%Y%m%d_%H%M%S.csv'))
        with open(path, 'w', newline='') as f:
            w = csv.writer(f)
            w.writerow(['phase', 't', 'fx', 'fy', 'fz', 'press_n', 'target'])
            w.writerows(self.rows)
        return path


def main() -> int:
    ap = argparse.ArgumentParser(description='V-03 힘제어 중 X·Y 이동 (실기는 --real)')
    ap.add_argument('--real', action='store_true', help='실기에서 실행한다 (🚨 E-Stop 담당·격리·저속 확인 뒤)')
    args = ap.parse_args()
    with open(HERE / 'rig_v03.yaml', encoding='utf-8') as f:
        p = yaml.safe_load(f)

    cc.init('rig_v03')                                                   # ① 맨 앞에서 한 번
    log = cc.io_node().get_logger()
    code = 1
    run = None
    try:
        d = dsr()
        virtual = d.get_robot_system() == d.ROBOT_SYSTEM_VIRTUAL
        if not virtual and not args.real:
            log.error('실기다 → --real 을 붙여야 실행한다 (E-Stop 담당·격리·저속 확인 뒤)')
            return 2
        approach = p['virtual_approach_down_mm'] if virtual else p['approach_down_mm']
        if approach is None:
            log.error('rig_v03.yaml 의 approach_down_mm 이 비어 있다 → (솔 끝 → 그릇 바닥 실측) − 30 mm 를 넣는다')
            return 2
        log.info(f"{'Virtual(흐름만 — 힘 판정은 의미 없음)' if virtual else '실기'} · vel_scale {cc.cfg()['run']['vel_scale']:g} "
                 f'· 툴 {d.get_tool()!r} · TCP {d.get_tcp()!r} · 접근 {approach:.0f} mm')
        input('준비되면 엔터 → 이후 키보드에서 손을 떼고 E-Stop 에 손을 둔다 ')

        run = Run(d, p, log)
        d.movej(p['home_posj'], vel=p['home_vel_deg_s'] * cc.cfg()['run']['vel_scale'], acc=p['home_acc_deg_s2'])
        z_home = run.z()
        cc.cfg()['cell']['limits']['safe_z_mm'] = z_home                 # 시험 전용: 안전 높이 = HOME
        log.info(f'HOME Z {z_home:.1f} → 빠른 접근 {approach:.0f} mm')
        run.move_z(-approach, p['approach_vel_mm_s'], p['approach_acc_mm_s2'])

        run.zero()
        depth, f = cc.contact_down(p['contact_max_depth_mm'], p['contact_limit_n'])
        contacted = depth < p['contact_max_depth_mm'] - 0.5
        log.info(f'contact_down: 깊이 {depth:.1f} mm · |Fz| {f:.1f} N · {"바닥 찾음" if contacted else "못 찾음"} · 바닥 Z {run.z():.1f}')
        if not contacted and not virtual:
            log.error('바닥을 못 찾았다 → 힘제어를 켜지 않고 중단 (approach_down_mm·그릇 위치 확인)')
            return 1
        run.move_z(p['backoff_mm'], p['approach_vel_mm_s'], p['approach_acc_mm_s2'])

        log.info('① 제자리 누르기')
        for target in p['press_targets_n']:
            run.press_on(target)
            run.sample(f'press_{target:g}N', target, seconds=p['press_hold_s'])
            run.lift()

        log.info('② 누른 채 문지르기')
        run.press_on(p['wipe_target_n'])
        run.sample('wipe_settle', p['wipe_target_n'], seconds=p['settle_s'] * 2)
        amp, per = p['circle_amp_mm'], p['circle_period_s']
        d.amove_periodic(amp=[amp, amp, 0.0, 0.0, 0.0, 0.0], period=[per, per * 2, 0.0, 0.0, 0.0, 0.0],
                         repeat=p['circle_repeat'], ref=d.DR_TOOL)
        run.sample('wipe_periodic', p['wipe_target_n'], until_motion=True)
        d.amove_spiral(rev=p['spiral_rev'], rmax=p['spiral_rmax_mm'], lmax=0.0, time=p['spiral_time_s'],
                       axis=d.DR_AXIS_Z, ref=d.DR_TOOL)
        run.sample('wipe_spiral', p['wipe_target_n'], until_motion=True)
        cc.force_off()
        code = 0 if all(r[6] for r in run.results) or virtual else 1
    except (cc.ForceLimitError, cc.MotionTimeout, RuntimeError, ValueError, KeyError) as e:
        log.error(f'중단: {type(e).__name__}: {e}')
        code = 1
    except KeyboardInterrupt:
        log.warning('Ctrl+C — 정지 명령을 보내고 끝낸다')
        code = 130
    finally:
        try:
            if code != 130 and run is not None:                          # 로봇을 움직이기 시작한 경우에만 복귀 (거부·Ctrl+C 는 제외)
                cc.force_off()
                d = dsr()
                d.mwait()                                                # 비동기 동작이 남아 있으면 끝난 뒤
                cc.safe_retreat()
                d.movej(p['home_posj'], vel=p['home_vel_deg_s'] * cc.cfg()['run']['vel_scale'], acc=p['home_acc_deg_s2'])
        except Exception as e:                                           # 정리 중 오류는 기록만
            log.error(f'복귀 중 오류: {e!r} — 로봇 상태를 눈으로 확인한다')
        if run is not None and run.rows:
            path = run.save()
            log.info(f'힘 로그: {path}')
            log.info('구간 | 목표 N | 평균 | 흔들림 | 최대 | 샘플 | 판정')
            for phase, target, mean, sd, mx, n, ok in run.results:
                vals = '—' if mean is None else f'{mean:.2f} | {sd:.2f} | {mx:.2f}'
                log.info(f'{phase} | {target:g} | {vals} | {n} | {"OK" if ok else "FAIL"}')
            wipe = [r for r in run.results if r[0].startswith('wipe_') and r[0] != 'wipe_settle']
            verdict = '가능' if wipe and all(r[6] for r in wipe) else '불가 또는 미확인'
            log.info(f'V-03 판정: 힘제어 중 X·Y 이동 {verdict} (문지르는 동안 평균이 목표 ±{p["tol_n"]} N · 최대 ≤ {p["limit_n"]} N)')
        cc.shutdown()                                                    # ③ 끝낼 때 (Ctrl+C 포함)
    return code


if __name__ == '__main__':
    sys.exit(main())
