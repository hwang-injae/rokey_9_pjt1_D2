#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V-03 — 힘제어를 켠 채 X·Y 로 움직일 수 있는가 (솔로 그릇 안쪽 바닥을 누르며 문지르기). 실기 전용 · Virtual 은 흐름만.

실행 (저장소 루트, 격리 상태 solo — AGENTS 규칙 13)
    Virtual 흐름 확인 :  sod && sodvir  →  soc && python3 src/cobot_common/test/rig_v03.py
    Virtual + 가짜 벽 :  soc && python3 src/cobot_common/test/rig_v03.py --fake-wall   (나선 → 벽 → 2바퀴 흐름·시간)
                         그릇 크기를 바꿔 보려면  --fake-wall --fake-bowl-d 200   (안지름 mm)
    실기             :  sod && sodreal →  soc && python3 src/cobot_common/test/rig_v03.py --real
준비(로봇 정지 상태): 그릇 중심을 HOME 바로 아래에 테이프로 고정 · 솔을 그리퍼에 쥐여 둔다('o' → 넣고 → 'c')
        · rig_v03.yaml 의 approach_down_mm = (솔 끝 → 그릇 안쪽 바닥) − 30 mm
🚨 엔터를 누른 뒤에는 키보드에서 손을 떼고 한 손은 E-Stop, 눈은 로봇. 속도는 vel_scale 0.3(바꾸려면 PREWASH_VEL_SCALE).

흐름: HOME → 빠른 접근(approach_down_mm) → contact_down(바닥 찾기, 못 찾으면 힘제어 없이 중단)
      → 닿은 채 제자리 누르기 → 누른 채 손목을 ±scrub_deg 로 비틀며 중심에서 나선으로 넓혀 가기
      → 반지름 방향 힘이 (가운데에서 배운 마찰 + wall_margin_n) 을 넘으면 벽 → 그 자리에서 바로 벽에 붙어 2바퀴 → 후퇴 → HOME
걸음은 blend_radius_mm 로 이어 붙여 멈추지 않고 움직인다.
솔은 낮은 원통이라 손목(6축) 비틀림 각도는 닦기에 상관없다 — 따로 되돌리지 않고 HOME(관절 이동)이 0 으로 돌려 놓는다.
힘은 닿은 채 켠다(force.py 는 절대값 ABS: 목표 = 실제 누르는 힘). 9/19 1차에 3 mm 위(공중)에서 상대 모드로 켰더니
3 s 안에 바닥까지 못 내려가 공중에서 8자를 그렸다 → 방식 변경.
누르는 힘 = 공중에서 잰 기준값 대비 Fz 변화. 어느 순간이든 limit_n 을 넘으면 즉시 힘 해제 → 후퇴.
🚨 두산 API 의 DR_Error 는 생기는 순간 rclpy.shutdown() 을 부른다 → 이 프로세스로는 힘·순응을 못 끈다.
   그때는 화면 안내대로 release_force.py(--home) 를 새로 실행한다.
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
        self.fake_wall_r = None                                          # Virtual 가짜 벽 반지름 mm (--fake-wall)
        self.climb = 0.0                                                 # 바닥에서 올라간 높이 mm (check 가 갱신)
        self.gap = 0.0                                                   # 반지름 방향으로 못 따라간 거리 mm (check 가 갱신)
        self.z_now = 0.0                                                 # 지금 실제 Z — 다음 걸음의 Z 명령으로 그대로 쓴다
        self.compliance_on = False                                       # depth 방식에서 직접 켠 순응

    def z(self):
        return self.d.get_current_posx(ref=self.d.DR_BASE)[0][2]

    def move_z(self, dz, vel, acc):
        s = cc.cfg()['run']['vel_scale']
        ret = self.d.movel([0.0, 0.0, float(dz), 0.0, 0.0, 0.0], vel=vel * s, acc=acc,
                           ref=self.d.DR_BASE, mod=self.d.DR_MV_MOD_REL)
        if ret != 0:
            raise RuntimeError(f'movel(Z {dz:+.1f} mm) 실패')

    def zero(self):
        """공중에서 Fz·Fx·Fy 기준값을 잡는다(툴 무게·옵셋 제거)."""
        fs = [cc.read_force() for _ in range(5)]
        self.baseline = statistics.mean(f[2] for f in fs)
        self.fx0 = statistics.mean(f[0] for f in fs)
        self.fy0 = statistics.mean(f[1] for f in fs)

    # ------------------------------------------------------------ 나선 문지르기 · 벽 찾기 · 벽 따라 돌기
    def scrub_to(self, x, y, phase='spiral'):
        """중심 기준 (x, y) 로 한 걸음 가면서 **동시에** 손목을 ±scrub_deg 로 비튼다 — movel 한 번(BASE 절대 좌표).

        목표 = [중심 X + x, 중심 Y + y, 바닥 Z, A, B, C + 비틀기]. 툴 Z 축 회전은 ZYZ 의 C 에 더하면 된다
        (Rz(A)·Ry(B)·Rz(C)·Rz(q) = Rz(A)·Ry(B)·Rz(C + q)).
        🚨 Z 는 **힘제어가 정한다** — 명령에는 '지금 실제 Z'를 넣는다. 처음 닿은 높이를 계속 명령하면
        힘제어(더 눌러 내려가려 함)와 위치 명령(그 높이로 끌어올림)이 싸워 작업대를 쿵쿵 친다(9/20 실기).
        🔸 blend_radius_mm(> 0) 이면 목표 앞 그 거리에서 다음 걸음으로 **이어서** 간다(멈췄다 가는 뚝뚝 끊김 없앰).
        🔸 손목은 twist_every 걸음마다 한 번만 방향을 바꾼다 — 걸음마다 바꾸면 이어 붙이기가 비틀기를 지워 버리고(Virtual 실측),
           매 걸음 회전을 세웠다 돌리느라 덜컹거린다(9/20 실기 소음).
        순응 중 관절 이동(movej) 금지라 직교 이동만. 한 걸음마다 힘을 읽어 기록하고 (누르는 힘, 옆 힘, 반지름 방향 힘) 을 돌려준다.
        """
        p, d, s = self.p, self.d, cc.cfg()['run']['vel_scale']
        vel = [p['scrub_lin_vel_mm_s'] * s, p['scrub_rot_vel_deg_s'] * s]
        acc = [p['scrub_lin_acc_mm_s2'], p['scrub_rot_acc_deg_s2']]
        self.step_i += 1
        if self.step_i % max(1, int(p['twist_every'])) == 0:
            self.twist = -self.twist
        rz = p['scrub_deg'] * self.twist
        x0, y0, _z0, a, b, c = self.p0
        target = [x0 + x, y0 + y, self.z_now, a, b, (c + rz + 180.0) % 360.0 - 180.0]
        if d.movel(target, vel=vel, acc=acc, radius=p['blend_radius_mm'], ref=d.DR_BASE, mod=d.DR_MV_MOD_ABS) != 0:
            raise RuntimeError('movel(한 걸음 + 손목 비틀기) 실패')
        self.x, self.y = x, y
        self.rz = rz
        return self.check(phase)

    def set_frame(self):
        """지금 자세(바닥에 닿은 중심)를 나선·원의 기준으로 기억한다 — 손목 0° 기준."""
        self.p0 = [float(v) for v in self.d.get_current_posx(ref=self.d.DR_BASE)[0]]
        self.z_now = self.p0[2]

    def check(self, phase):
        """힘 한 번 읽기 → 기록 · 누르는 힘/옆 힘 상한 검사 → (press, lateral, radial).

        radial = 옆 힘을 지금 위치의 반지름 방향(중심 → 솔)으로 투영한 크기. 문지름 마찰은 주로 진행 방향(둘레)이라
        반지름 성분이 작고, 벽은 솔을 반지름 방향으로 되민다 → 벽 판정은 radial 로 한다(9/19 3회차: 옆 힘 전체로는 못 찾음).
        """
        import math
        p = self.p
        f = cc.read_force()
        r = math.hypot(self.x, self.y)
        if self.fake_wall_r is not None:                                 # Virtual 가짜 벽(중심이 어긋난 그릇): 넘어간 만큼 되민다
            wx, wy = self.x - p['fake_bowl_offset_mm'][0], self.y - p['fake_bowl_offset_mm'][1]
            wr = math.hypot(wx, wy)
            if wr > self.fake_wall_r:
                push = p['fake_wall_k_n_per_mm'] * (wr - self.fake_wall_r)
                f = [f[0] - push * wx / wr, f[1] - push * wy / wr] + list(f[2:])
        press = abs(f[2] - self.baseline)
        lx, ly = f[0] - self.fx0, f[1] - self.fy0
        lateral = math.hypot(lx, ly)
        radial = abs(lx * self.x / r + ly * self.y / r) if r > 1e-6 else 0.0
        now = self.d.get_current_posx(ref=self.d.DR_BASE)[0]             # 실제 위치 — 명령을 못 따라간 만큼이 벽에 막힌 양이다
        ax, ay = float(now[0]) - self.p0[0], float(now[1]) - self.p0[1]
        if self.fake_wall_r is not None:                                 # Virtual 은 순응이 없어 늘 명령대로 간다 → 막히는 것도 흉내
            wx, wy = self.x - p['fake_bowl_offset_mm'][0], self.y - p['fake_bowl_offset_mm'][1]
            wr = math.hypot(wx, wy)
            if wr > self.fake_wall_r:
                k = (self.fake_wall_r + (wr - self.fake_wall_r) * 0.2) / wr     # 벽 너머는 20 %만 들어간다
                ax, ay = p['fake_bowl_offset_mm'][0] + wx * k, p['fake_bowl_offset_mm'][1] + wy * k
        self.gap = r - math.hypot(ax, ay) if r > 1e-6 else 0.0           # 반지름 방향으로 못 따라간 거리 mm (벽에 막힘)
        self.z_now = float(now[2])                                       # 다음 걸음은 이 높이를 명령한다(Z 는 힘제어 몫)
        self.climb = self.z_now - self.p0[2]                             # 바닥에서 올라간 높이 — 툴이 벽을 타고 오르면 커진다
        # 실제 손목 비틀림: B≈180°(툴이 아래를 봄)에서는 툴 Z 회전이 A − C 로 나타난다 → −Δ(A − C)
        arz = -((float(now[3]) - float(now[5])) - (self.p0[3] - self.p0[5]) + 180.0) % 360.0 + 180.0
        arz = (arz + 180.0) % 360.0 - 180.0
        self.rows.append([phase, round(time.monotonic() - self.t0, 3), f[0], f[1], f[2], round(press, 3), p['wipe_target_n'],
                          round(self.x, 2), round(self.y, 2), round(radial, 3), round(ax, 2), round(ay, 2),
                          round(arz, 1), round(self.rz, 1), round(self.climb, 2), round(self.gap, 2)])
        if press > p['limit_n']:
            raise cc.ForceLimitError(f'{phase}: 누르는 힘 {press:.1f} N > {p["limit_n"]} N')
        if lateral > p['lateral_max_n']:
            raise cc.ForceLimitError(f'{phase}: 옆 힘 {lateral:.1f} N > {p["lateral_max_n"]} N (벽을 세게 밀었다)')
        return press, lateral, radial

    def wall_r(self):
        """그릇 벽에 닿는 툴 중심 반지름 = (그릇 안지름 − 툴 지름) / 2 + 눌러 주는 양 (9/20: 수세미가 물러서 힘으로 못 찾음)."""
        p = self.p
        return max(0.0, (p['bowl_inner_d_mm'] - p['brush_d_mm']) / 2 + p['wall_press_mm'])

    def r_max(self):
        """솔 중심이 갈 수 있는 최대 반지름 = 받을 수 있는 가장 큰 그릇 반지름 − 솔 반지름 + 여유. 그릇 크기를 가정하지 않는다."""
        p = self.p
        return p['bowl_r_max_mm'] - p['brush_d_mm'] / 2 + p['r_max_margin_mm']

    def spiral_find_wall(self):
        """중심에서 나선으로 넓혀 가며 문지르다 **정해진 반지름**에 닿으면 그 자리를 벽으로 본다 → (반지름, 각도).

        🔸 9/20 결정: 수세미는 스펀지처럼 물러서 벽에 눌려도 잘 막히지 않는다(힘·못 따라간 거리로는 벽을 못 찾음)
           → **그릇 안지름을 넣어** 벽 반지름 = (bowl_inner_d_mm − brush_d_mm) / 2 + wall_press_mm 로 계산한다.
        그래도 그보다 **먼저 막히면**(gap·올라감) 거기서 멈춘다 — 그릇이 작거나 잘못 놓였을 때의 안전장치.
        """
        import math
        p = self.p
        self.x = self.y = self.rz = 0.0
        self.twist, self.step_i = 1, 0
        self.set_frame()
        r_wall = min(self.wall_r(), self.r_max())
        self.log.info(f'  벽 반지름 {r_wall:.1f} mm = (그릇 안지름 {p["bowl_inner_d_mm"]:g} − 툴 {p["brush_d_mm"]:g}) / 2 '
                      f'+ 눌러 주기 {p["wall_press_mm"]:g} mm')
        theta, r, hits, presses = 0.0, 0.0, 0, []
        start = time.monotonic()
        while True:
            if time.monotonic() - start > p['scrub_timeout_s']:
                raise cc.MotionTimeout('나선 문지르기 시간 초과')
            press, lat, rad = self.scrub_to(r * math.cos(theta), r * math.sin(theta))
            presses.append(press)
            climbed = self.climb > p['climb_max_mm']
            blocked = self.gap > p['wall_gap_mm']
            hits = hits + 1 if (blocked or climbed) else 0
            early = hits >= p['wall_confirm']                            # 계산한 반지름 전에 막혔다(안전장치)
            if early or r >= r_wall:
                why = (f'솔이 {self.climb:.1f} mm 올라감' if climbed and early else
                       f'명령을 {self.gap:.1f} mm 못 따라감' if early else '정해진 반지름 도달')
                self.log.info(f'  벽: 반지름 {r:.1f} mm · 각 {math.degrees(theta):.0f}° · {why} · '
                              f'반지름 방향 힘 {rad:.1f} N · 옆 힘 {lat:.1f} N · 나선 {time.monotonic() - start:.1f} s')
                self.result('spiral', p['wipe_target_n'], presses)
                return r, theta
            dth = p['scrub_step_mm'] / max(r, p['scrub_step_mm'])       # 호 길이가 약 scrub_step_mm 가 되게
            theta += dth
            r = min(r + p['spiral_pitch_mm'] * dth / (2 * math.pi), r_wall)

    def circle_wall(self, r_hit, theta0):
        """벽에 닿은 자리에서 바로 circle_turns 바퀴 — 반지름은 **고정**(벽을 만난 반지름 − circle_margin_mm).

        🔸 나선과 **반대 방향**으로 돈다(circle_reverse) — 같은 방향이면 나선 마지막 바퀴와 구분이 안 된다(9/19 5회차).
        🔸 걸음마다 반지름을 고치는 '벽 따라가기'는 9/20 결정으로 삭제했다. 그릇은 홈 가운데에 놓는 것이 전제이고,
           한쪽을 세게 밀면 옆 힘 상한(lateral_max_n)에서 멈춘다.
        """
        import math
        p = self.p
        r = max(0.0, r_hit - p['circle_margin_mm'])
        sign = -1.0 if p['circle_reverse'] else 1.0
        th, done = theta0, 0.0
        presses, lats, gaps = [], [], []
        self.d.mwait()                                                   # 나선 끝 — 벽에 닿은 채 잠깐 멈춤(구분되게)
        self.sample('wall_pause', p['wipe_target_n'], seconds=p['circle_pause_s'])
        self.log.info(f'  벽 따라 {p["circle_turns"]}바퀴 시작 — {"반대 방향" if p["circle_reverse"] else "같은 방향"} '
                      f'· 반지름 고정 {r:.1f} mm')
        start = time.monotonic()
        while done < 2 * math.pi * p['circle_turns']:
            if time.monotonic() - start > p['scrub_timeout_s']:
                raise cc.MotionTimeout('벽 따라 돌기 시간 초과')
            dth = p['scrub_step_mm'] / max(r, p['scrub_step_mm'])
            th, done = th + sign * dth, done + dth
            press, lat, rad = self.scrub_to(r * math.cos(th), r * math.sin(th), 'wall')
            presses.append(press)
            lats.append(lat)
            gaps.append(self.gap)
        self.log.info(f'  벽 따라 {p["circle_turns"]}바퀴: 반지름 {r:.1f} mm · 벽 누름 평균 {statistics.mean(gaps):.1f} '
                      f'(최소 {min(gaps):.1f} · 최대 {max(gaps):.1f}) mm · 옆 힘 평균 {statistics.mean(lats):.1f} · '
                      f'최대 {max(lats):.1f} N · {time.monotonic() - start:.1f} s')
        self.result('circle', p['wipe_target_n'], presses)

    def sample(self, phase, target, seconds=None, until_motion=False):
        """seconds 동안 또는 비동기 동작이 끝날 때까지 힘을 기록. limit_n 넘으면 ForceLimitError."""
        p = self.p
        start = time.monotonic()
        vals = []
        while True:
            f = cc.read_force()
            press = abs(f[2] - self.baseline)
            now = time.monotonic()
            self.rows.append([phase, round(now - self.t0, 3), f[0], f[1], f[2], round(press, 3), target,
                              '', '', '', '', '', '', '', '', ''])
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
        """누르기 시작. press_mode 로 두 방식 중 하나 (9/20: 수세미는 물러서 힘제어로는 깊게 눌린다).

        'force' : 힘제어 — 목표 힘이 날 때까지 로봇이 알아서 내려간다. 무른 툴은 몇 mm 씩 깊게 들어간다.
        'depth' : 순응만 켜고 **정해진 깊이(press_depth_mm)만** 내려간다. 눌리는 깊이를 직접 정하는 방식
                  (SDD §9.9 의 대안). 걸리는 힘 ≈ Z 순응 강성 × 깊이 (500 N/m = 0.5 N/mm → 3 mm ≈ 1.5 N).
        """
        p = self.p
        if p['press_mode'] == 'force':
            cc.force_on('z', target, p['limit_n'])
            return
        if p['press_mode'] != 'depth':
            raise ValueError(f"press_mode={p['press_mode']!r} — 'force'·'depth' 중 하나")
        d = self.d
        d.mwait()                                                        # 비동기 이동 중 순응 ON 은 오류 2.1903
        stx = cc.cfg()['cell']['force']['compliance_stx']
        if d.task_compliance_ctrl(stx) != 0:
            raise RuntimeError('task_compliance_ctrl 실패')
        self.compliance_on = True
        if p['press_depth_mm'] > 0:
            self.move_z(-p['press_depth_mm'], p['press_vel_mm_s'], p['press_acc_mm_s2'])
        self.log.info(f'  순응만 켜고 누르기: 더 내려감 {p["press_depth_mm"]:g} mm (Z 순응 {stx[2]:g} N/m → 약 '
                      f'{stx[2] / 1000 * p["press_depth_mm"]:.1f} N). 0 이면 바닥 찾은 자리 그대로')

    def press_off(self):
        """누르기 끝 — force 방식은 cc.force_off(), depth 방식은 직접 켠 순응을 직접 끈다."""
        cc.force_off()                                                   # 힘제어를 켠 적 있으면 끈다(아니면 아무 일도 안 함)
        if self.compliance_on:
            self.d.release_compliance_ctrl()
            self.compliance_on = False

    def save(self):
        os.makedirs(self.p['log_dir'], exist_ok=True)
        path = os.path.join(self.p['log_dir'], time.strftime('v03_%Y%m%d_%H%M%S.csv'))
        with open(path, 'w', newline='') as f:
            w = csv.writer(f)
            w.writerow(['phase', 't', 'fx', 'fy', 'fz', 'press_n', 'target', 'x_mm', 'y_mm', 'radial_n',
                        'actual_x_mm', 'actual_y_mm', 'actual_rz_deg', 'cmd_rz_deg', 'climb_mm', 'gap_mm'])
            w.writerows(self.rows)
        return path


def main() -> int:
    ap = argparse.ArgumentParser(description='V-03 힘제어 중 X·Y 이동 (실기는 --real)')
    ap.add_argument('--real', action='store_true', help='실기에서 실행한다 (🚨 E-Stop 담당·격리·저속 확인 뒤)')
    ap.add_argument('--fake-wall', action='store_true',
                    help='Virtual 전용: 그릇 안지름·솔 지름으로 가짜 벽 힘을 넣는다 (실기에서는 거부)')
    ap.add_argument('--fake-bowl-d', type=float, default=None,
                    help='Virtual 가짜 그릇 안지름 mm (기본 rig_v03.yaml)')
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
        if args.fake_wall and not virtual:
            log.error('--fake-wall 은 Virtual 전용이다 (실기에는 진짜 벽이 있다) → 실행 거부')
            return 2
        approach = p['virtual_approach_down_mm'] if virtual else p['approach_down_mm']
        if approach is None:
            log.error('rig_v03.yaml 의 approach_down_mm 이 비어 있다 → (솔 끝 → 그릇 바닥 실측) − 30 mm 를 넣는다')
            return 2
        tool, tcp = d.get_tool(), d.get_tcp()
        if not virtual and (tool != p['expected_tool'] or tcp != p['expected_tcp']):
            # 브링업을 새로 켜면 툴·TCP 가 비어 있다(9/19). 자동 모드에서는 설정이 거부돼 수동 모드로 바꿔 설정하고 되돌린다
            log.warning(f'툴·TCP 가 {tool!r}·{tcp!r} → {p["expected_tool"]!r}·{p["expected_tcp"]!r} 로 설정한다 (로봇 안 움직임)')
            d.set_robot_mode(d.ROBOT_MODE_MANUAL)
            d.set_tool(str(p['expected_tool']))
            d.set_tcp(str(p['expected_tcp']))
            d.set_robot_mode(d.ROBOT_MODE_AUTONOMOUS)
            tool, tcp = d.get_tool(), d.get_tcp()
        log.info(f"{'Virtual(흐름만 — 힘 판정은 의미 없음)' if virtual else '실기'} · vel_scale {cc.cfg()['run']['vel_scale']:g} "
                 f'· 툴 {tool!r} · TCP {tcp!r} · 접근 {approach:.0f} mm')
        if not virtual and (tool != p['expected_tool'] or tcp != p['expected_tcp']):
            log.error(f"툴·TCP 설정이 다르다(기대 {p['expected_tool']!r} · {p['expected_tcp']!r}) → 실행 거부. 설정:\n"
                      f"    ros2 service call /dsr01/dsr_controller2/tool/set_current_tool dsr_msgs2/srv/SetCurrentTool "
                      f"\"{{name: '{p['expected_tool']}'}}\"\n"
                      f"    ros2 service call /dsr01/dsr_controller2/tcp/set_current_tcp dsr_msgs2/srv/SetCurrentTcp "
                      f"\"{{name: '{p['expected_tcp']}'}}\"")
            return 2
        air = abs(statistics.mean(cc.read_force()[2] for _ in range(5)))
        if not virtual and air > p['air_force_max_n']:
            log.error(f"로봇이 멈춰 있는데 |Fz| {air:.1f} N > {p['air_force_max_n']} N → 툴 무게 설정이 틀렸다(무게가 외력으로 잡힘). 실행 거부")
            return 2
        input('준비되면 엔터 → 이후 키보드에서 손을 떼고 E-Stop 에 손을 둔다 ')

        run = Run(d, p, log)
        if args.fake_wall:
            if args.fake_bowl_d is not None:                             # Virtual 전용 — 실기는 위에서 이미 거부
                p['fake_bowl_inner_d_mm'] = args.fake_bowl_d
            run.fake_wall_r = max(0.0, (p['fake_bowl_inner_d_mm'] - p['brush_d_mm']) / 2)
            log.info(f"가짜 벽: 그릇 안지름 {p['fake_bowl_inner_d_mm']:g} − 솔 지름 {p['brush_d_mm']:g} → "
                     f"솔 중심 반지름 {run.fake_wall_r:.1f} mm 에서 벽 · 나선 최대 {run.r_max():.1f} mm")
        d.movej(p['home_posj'], vel=p['home_vel_deg_s'] * cc.cfg()['run']['vel_scale'], acc=p['home_acc_deg_s2'])
        z_home = run.z()
        cc.cfg()['cell']['limits']['safe_z_mm'] = z_home                 # 시험 전용: 안전 높이 = HOME
        log.info(f'HOME Z {z_home:.1f} → 빠른 접근 {approach:.0f} mm')
        run.move_z(-approach, p['approach_vel_mm_s'], p['approach_acc_mm_s2'])

        run.zero()                                                       # 공중 기준값 (닿기 전)
        log.info(f'공중 Fz 기준값 {run.baseline:.2f} N')
        if not virtual and abs(run.baseline) > p['air_force_max_n']:
            log.error(f'접근 뒤 공중 |Fz| {abs(run.baseline):.1f} N 가 크다 → 툴 무게·접촉 확인. 힘제어 없이 중단')
            return 1
        depth, f = cc.contact_down(p['contact_max_depth_mm'], p['contact_limit_n'])
        contacted = depth < p['contact_max_depth_mm'] - 0.5
        log.info(f'contact_down: 깊이 {depth:.1f} mm · |Fz| {f:.1f} N · {"바닥 찾음" if contacted else "못 찾음"} · 바닥 Z {run.z():.1f}')
        if not contacted and not virtual:
            log.error('바닥을 못 찾았다 → 힘제어를 켜지 않고 중단 (approach_down_mm·그릇 위치 확인)')
            return 1

        log.info('① 닿은 채 제자리 누르기')
        for target in p['press_targets_n']:
            run.press_on(target)
            run.sample(f'press_{target:g}N', target, seconds=p['press_hold_s'])
            run.press_off()

        log.info('② 손목을 비틀며 나선으로 넓혀 가다 벽을 찾고 → 벽 따라 돌기')
        run.press_on(p['wipe_target_n'])
        run.sample('wipe_settle', p['wipe_target_n'], seconds=p['settle_s'] * 2)
        wall = run.spiral_find_wall()
        if wall is not None:
            run.circle_wall(*wall)
        run.press_off()
        code = 0 if wall is not None else 1
    except KeyboardInterrupt:
        log.warning('Ctrl+C — 정지 명령을 보내고 끝낸다')
        code = 130
    except Exception as e:                                               # 두산 DR_Error 포함 — 무엇이든 멈추고 정리
        log.error(f'중단: {type(e).__name__}: {e}')
        code = 1
    finally:
        import rclpy
        if code != 130 and run is not None:                              # 로봇을 움직이기 시작한 경우에만 복귀 (거부·Ctrl+C 는 제외)
            if not rclpy.ok():                                           # DR_Error 가 rclpy.shutdown() 을 불렀다 → 이 프로세스로는 못 끈다
                log.error('🚨 두산 오류로 ROS 가 꺼졌다 → 힘·순응이 켜진 채일 수 있다. 새 터미널에서 바로:\n'
                          '    soc && python3 src/cobot_common/test/release_force.py --home   (E-Stop 에 손)')
            else:
                for what, step in (('힘·순응 끄기', run.press_off), ('동작 끝 대기', lambda: dsr().mwait()),
                                   ('안전 높이로', cc.safe_retreat),
                                   ('HOME', lambda: dsr().movej(p['home_posj'],
                                                                vel=p['home_vel_deg_s'] * cc.cfg()['run']['vel_scale'],
                                                                acc=p['home_acc_deg_s2']))):
                    try:                                                 # 하나가 실패해도 다음을 시도
                        step()
                    except Exception as e:
                        log.error(f'복귀 — {what} 실패: {e!r} → 눈으로 확인, 필요하면 release_force.py --home')
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
