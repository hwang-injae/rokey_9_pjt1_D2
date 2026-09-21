# -*- coding: utf-8 -*-
"""V-10 컵 안쪽 솔 삽입·문지르기 실기 시험 (F3-03 첫 단계) — 박진용.

    soc && python3 src/f3_wipe/test/rig_v10.py --real --stage find     # ① 바닥 찾기까지만 (맨 처음 이것부터)
    soc && python3 src/f3_wipe/test/rig_v10.py --real --stage lift     # ② 띄우기까지 (문지르지 않는다)
    soc && python3 src/f3_wipe/test/rig_v10.py --real                  # ③ 전체 (기본 stage=scrub)
    soc && python3 src/f3_wipe/test/rig_v10.py --real --cycles 1 --stroke 5 --twist 10   # 값 바꿔 가며
    PREWASH_CONFIG_DIR=<임시 설정> python3 src/f3_wipe/test/rig_v10.py                 # Virtual(sodvir) — 흐름만

준비(손으로): 컵을 스펀지 홈에 넣고, **솔을 그리퍼에 쥐여 준다**(그리퍼 끝을 세척부 윗면에 닿게 — 세척부 95 mm).
🚨 E-Stop 에 손을 두고 본다. 첫 실행은 반드시 `--stage find` 로 **바닥만** 찾아 보고 숫자를 확인한다.

이 rig 가 확인하는 것 (V-10)
  · 티칭 끝점(cell.beds.SPONGE_BED_C.wash) 대비 **실제 바닥이 어디인가** — 계산상 TCP Z 128 (아래 메모)
  · 솔이 얼마나 들어가는가 · 바닥에 닿을 때 힘이 어떻게 올라오는가
  · 위아래 40 mm + 좌우 비틀기 ±18°(9/21 확정)가 컵 안에서 괜찮은가 · 속도를 얼마로 할 것인가
    (직선 이어 붙이기 — wipe.cup_strokes 를 그대로 쓴다. Move Periodic 회전은 손목을 기울여서 버렸다, 9/21 Virtual)
  · 컵이 홈 안에서 딸려 올라오거나 도는가 (옆 힘으로 본다)

🔸 끝점 계산 메모 (9/20 실기에서 나온 값으로 미리 계산한 것 — 내일 이 rig 로 확인한다)
    그릇 + 수세미(35)로 바닥 접촉 시 TCP Z 68  →  용기 안 바닥 = 68 − 35 = 33
    컵·그릇 모두 관통 구멍으로 작업대 바닥에 직접 놓인다  →  컵 안 바닥도 ≈ 33
    솔(95)로 컵 바닥 접촉 시 TCP Z = 33 + 95 = **128**.  지금 티칭값 156.54 는 **28 mm 높다**.
    그래서 f3.wipe_cup.find_max_mm 을 40 으로 두었다(끝점이 128 로 고쳐지면 25 로 줄여도 된다).

제품 코드와 같은 공용 함수(cc.*)만 쓴다 — 여기서 정한 값이 그대로 params.yaml 의 f3.wipe_cup 으로 간다.
파일 이름이 test_* 가 아니라서 pytest 는 모으지 않는다.
"""
import argparse
import csv
import math
import os
import statistics
import sys
import time

import cobot_common as cc
from cobot_common.bootstrap import dsr
from f3_wipe.wipe import cup_stroke, cup_strokes, insert_depth

STATION = 'SPONGE_BED_C'
STAGES = ('find', 'lift', 'scrub')
EXPECTED_TOOL, EXPECTED_TCP = 'Tool Weight', 'GripperDA_v1'
AIR_FORCE_MAX_N = 5.0           # 멈춰 있는데 이보다 크면 툴 무게 설정이 틀린 것 (V-03 과 같은 검사)


class Log:
    """힘 샘플 + 구간별 요약. 도는 중에는 힘만 읽는다(위치를 같이 읽으면 로봇이 선다 — 9/20)."""

    def __init__(self, p, node_log):
        self.p, self.log = p, node_log
        self.rows, self.results = [], []
        self.base = [0.0] * 6
        self.t0 = time.monotonic()

    def zero(self):
        self.base = [statistics.mean(v) for v in zip(*(cc.read_force() for _ in range(5)))]
        self.log.info(f'공중 기준값 Fz {self.base[2]:+.2f} N · 옆 {math.hypot(self.base[0], self.base[1]):.2f} N')
        return self.base

    def watch(self, phase):
        f = cc.read_force()
        press = abs(f[2] - self.base[2])
        lateral = math.hypot(f[0] - self.base[0], f[1] - self.base[1])
        self.rows.append([phase, round(time.monotonic() - self.t0, 3), f[0], f[1], f[2],
                          round(press, 3), round(lateral, 3)])
        if press > self.p['limit_n']:
            raise cc.ForceLimitError(f'{phase}: 누르는 힘 {press:.1f} N > {self.p["limit_n"]} N')
        if lateral > self.p['lateral_max_n']:
            raise cc.ForceLimitError(f'{phase}: 옆 힘 {lateral:.1f} N > {self.p["lateral_max_n"]} N '
                                     '(컵이 딸려 올라오거나 솔이 걸렸다)')
        return press, lateral

    def summarize(self, phase, since):
        vals = [(r[5], r[6]) for r in self.rows if r[0] == phase][since:]
        if not vals:
            return
        press, lat = [v[0] for v in vals], [v[1] for v in vals]
        self.results.append((phase, len(vals), statistics.mean(press), max(press), max(lat)))

    def save(self):
        os.makedirs(self.p['log_dir'], exist_ok=True)
        path = os.path.join(self.p['log_dir'], time.strftime('v10_%Y%m%d_%H%M%S.csv'))
        with open(path, 'w', newline='') as f:
            w = csv.writer(f)
            w.writerow(['phase', 't', 'fx', 'fy', 'fz', 'press_n', 'lateral_n'])
            w.writerows(self.rows)
        return path


def guards(a, log):
    """실기 안전 검사 — V-03 rig 와 같은 순서. 하나라도 걸리면 로봇을 움직이지 않는다."""
    d = dsr()
    virtual = d.get_robot_system() == d.ROBOT_SYSTEM_VIRTUAL
    if not virtual and not a.real:
        log.error('실기다 → --real 을 붙여야 실행한다 (E-Stop 담당·격리·저속 확인 뒤)')
        return None
    if virtual:
        log.warning('Virtual 이다 — 힘이 없어 바닥을 못 찾는다. 흐름만 본다')
    tool, tcp = d.get_tool(), d.get_tcp()
    if not virtual and (tool != EXPECTED_TOOL or tcp != EXPECTED_TCP):
        log.error(f'툴·TCP 가 {tool!r}·{tcp!r} — 기대 {EXPECTED_TOOL!r}·{EXPECTED_TCP!r}. '
                  '티치펜던트에서 맞추고 다시 (TCP 가 다르면 높이가 전부 어긋난다)')
        return None
    air = abs(statistics.mean(cc.read_force()[2] for _ in range(5)))
    if not virtual and air > AIR_FORCE_MAX_N:
        log.error(f'멈춰 있는데 |Fz| {air:.1f} N > {AIR_FORCE_MAX_N} N → 툴 무게 설정이 틀렸다. 실행 거부')
        return None
    scale = cc.cfg().get('run', {}).get('vel_scale', 1.0)
    if not virtual and scale > 0.3:
        log.error(f'vel_scale {scale:g} — 첫 실기는 0.3 이하로 (ros2 launch … vel_scale:=0.3)')
        return None
    return virtual


def main() -> int:
    ap = argparse.ArgumentParser(description='V-10 컵 솔 삽입·문지르기 (실기는 --real)')
    ap.add_argument('--real', action='store_true', help='실기에서 실행한다')
    ap.add_argument('--stage', choices=STAGES, default='scrub', help='어디까지 할지 (기본 scrub = 전체)')
    ap.add_argument('--cycles', type=int, default=None, help='왕복 횟수 (기본 params.yaml)')
    ap.add_argument('--stroke', type=float, default=None, help='위아래 편진폭 mm')
    ap.add_argument('--twist', type=float, default=None, help='좌우 비틀기 편진폭 deg')
    ap.add_argument('--vel', type=float, default=None, help='위아래 속도 mm/s (× vel_scale)')
    a = ap.parse_args()

    cc.init('rig_v10')                                                   # ① 맨 앞에서 한 번
    log = cc.io_node().get_logger()
    code, started, rec, can_move = 1, False, None, True      # can_move=False → 정리할 때 로봇을 움직이지 않는다
    try:
        p = dict(cc.cfg()['f3']['wipe_cup'])                             # 값의 정본은 params.yaml — 인자는 덮어쓰기만
        for key, val in (('cycles', a.cycles), ('stroke_mm', a.stroke),
                         ('twist_deg', a.twist), ('lin_vel_mm_s', a.vel)):
            if val is not None:
                p[key] = val
                log.warning(f'덮어씀: {key} = {val}  (확정되면 params.yaml 에 넣는다)')
        virtual = guards(a, log)
        if virtual is None:
            return 2
        rec = Log(p, log)
        scale = float(cc.cfg().get('run', {}).get('vel_scale', 1.0))
        log.info(f'V-10 · stage {a.stage} · vel_scale {scale:g} · 솔 세척부 {p["tool"]["clean_h_mm"]:g} mm')
        input('컵·솔 준비됐으면 엔터 → 이후 키보드에서 손을 떼고 E-Stop 에 손을 둔다 ')
        started = True

        # ── ① 접근 → 바닥 찾기 ─────────────────────────────────────────────
        up = cc.move_to(STATION, carrying=True, point='wash')
        z_top = cc.where()[2]
        rec.zero()
        gap = float(p['fast_gap_mm'])
        fast = max(0.0, up - gap)
        log.info(f'접근점 Z {z_top:.1f} · 끝점까지 {up:.1f} mm → 빠르게 {fast:.1f} mm (끝점 {gap:g} mm 위까지)')
        if fast > 0:
            cc.move_rel(0.0, 0.0, -fast, 'BASE')
        n0 = len(rec.rows)
        found, f_n = cc.contact_down(float(p['find_max_mm']), cc.cfg()['cell']['limits']['insert_limit_n'])
        z_bottom = cc.where()[2]
        inserted = insert_depth(p, found)
        rec.watch('bottom')
        rec.summarize('bottom', n0)
        log.info(f'🔸 바닥: TCP Z {z_bottom:.1f} (티칭 끝점 {z_top - up:.1f}, 차이 {z_bottom - (z_top - up):+.1f} mm) '
                 f'· 찾기 {found:.1f}/{p["find_max_mm"]:g} mm · 접촉 힘 {f_n:.1f} N · 솔이 {inserted:.1f} mm 들어감')
        if found >= float(p['find_max_mm']) - 0.5 and not virtual:
            log.error('바닥을 못 찾았다 → 끝점이 너무 높거나 컵이 없다. find_max_mm 을 늘리거나 끝점을 고친다')
            return 1
        log.info(f'   → 계산 예상은 TCP Z 128 이었다. 이 값을 cell.beds.{STATION}.wash.posx 의 z 로 올린다')
        if a.stage == 'find':
            code = 0
            return code

        # ── ② 힘 풀고 왕복의 아래쪽 끝으로 띄우기 ─────────────────────────────
        lift = float(p['lift_mm'])
        stroke = cup_stroke(p, inserted)
        if stroke <= 0:
            log.error(f'솔이 {inserted:.1f} mm 밖에 안 들어가 왕복할 자리가 없다')
            return 1
        cc.move_rel(0.0, 0.0, lift, 'BASE', vel_mm_s=float(p['lift_vel_mm_s']) * scale)
        rec.watch('lift')
        log.info(f'띄움: 바닥 + {lift:g} mm = 왕복의 아래쪽 끝 · 꼭대기는 바닥 + {lift + 2 * stroke:.1f} mm')
        if a.stage == 'lift':
            code = 0
            return code

        # ── ③ 위아래 바운스 + 좌우 비틀기 (z·c 만 바꾼 직선을 이어 붙인다) ───────
        low = cc.where()
        pts = cup_strokes(low, stroke, float(p['twist_deg']), int(p['cycles']), p['blend_radius_mm'])
        log.info(f'문지르기: 위아래 {2 * stroke:.1f} mm · 비틀기 ±{p["twist_deg"]:g}° · {p["cycles"]} 회 '
                 f'· 직선 {len(pts)} 개 (속도 {p["lin_vel_mm_s"]:g} mm/s · {p["rot_vel_deg_s"]:g} °/s × vel_scale)')
        n0 = len(rec.rows)
        t_scrub = time.monotonic()
        for pose, blend in pts:
            if time.monotonic() - t_scrub > float(p['duration_s']):
                raise cc.MotionTimeout('문지르기 시간 초과')
            cc.move_line(pose, p['lin_vel_mm_s'], p['rot_vel_deg_s'], blend)
            rec.watch('scrub')
        dsr().mwait()
        rec.summarize('scrub', n0)
        end = cc.where()
        log.info(f'끝: 아래쪽 끝 · 시작 대비 z {end[2] - low[2]:+.1f} mm · c {end[5] - low[5]:+.1f}° '
                 f'· 문지르기 {time.monotonic() - t_scrub:.1f} s → 솔을 곧게 뽑는다')
        code = 0
    except cc.ForceLimitError as e:                                      # 로봇은 정상 — 설계된 후퇴를 한다(AGENTS 규칙 2)
        log.error(f'🚨 힘 상한: {e} → 중단하고 후퇴한다')
    except KeyboardInterrupt:
        log.warning('Ctrl+C — 정리하고 끝낸다')
        code = 130
    except (cc.MoveIncomplete, cc.MotionHalted) as e:                    # 🚨 로봇이 어디 있는지 모른다
        log.error(f'중단: {type(e).__name__}: {e}')
        can_move = False
    except Exception as e:                                               # 두산 DR_Error 포함 — 상태를 믿을 수 없다
        log.error(f'중단: {type(e).__name__}: {e}')
        can_move = False
    finally:
        import rclpy
        if started:
            if not rclpy.ok():                                           # DR_Error 가 rclpy.shutdown() 을 불렀다 (TS-05)
                log.error('🚨 두산 오류로 ROS 가 꺼졌다 → 힘·순응이 켜진 채일 수 있다. 새 터미널에서 바로:\n'
                          '    soc && python3 src/cobot_common/test/release_force.py --home   (E-Stop 에 손)')
            else:
                # 🚨 9/21 08:40 실기: 6번 관절이 163° 돌아 케이블이 꼬인 채 로봇이 멈췄는데 시험 도구가
                #    자동으로 HOME 으로 가려 했다(F4 가 rig_coords 8ae86d2 에서 발견·수정). 꼬인 채 움직이면 더 꼬인다.
                #    힘·순응 해제는 모션이 아니라 언제나 한다. **움직이는 것은 로봇 위치를 알 때만.**
                steps = [('힘·순응 끄기', cc.force_off)]
                if can_move or not a.real:
                    steps += [('동작 끝 대기', lambda: dsr().mwait()),
                              ('안전 높이로', cc.safe_retreat), ('HOME', lambda: cc.move_to('HOME', False))]
                for what, step in steps:
                    try:
                        step()
                    except Exception as e:
                        log.error(f'복귀 — {what} 실패: {e!r} → 눈으로 확인, 필요하면 release_force.py --home')
                if not can_move and a.real:
                    log.error('🚨 실기에서 이동이 실패했다 — 힘만 끄고 **로봇을 자동으로 움직이지 않았다.**\n'
                              '   티치펜던트로 상태(케이블 꼬임·오류)를 확인하고 사람이 복구한 뒤 다시 돌린다')
        if rec is not None and rec.rows:
            log.info(f'힘 로그: {rec.save()}')
            log.info('구간 | 샘플 | 평균 누름 N | 최대 누름 N | 최대 옆 N')
            for phase, n, mean, mx, lat in rec.results:
                log.info(f'{phase} | {n} | {mean:.2f} | {mx:.2f} | {lat:.2f}')
        cc.shutdown()                                                    # ③ 끝낼 때
    return code


if __name__ == '__main__':
    sys.exit(main())
