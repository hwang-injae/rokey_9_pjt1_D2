"""F3 접촉 닦기 — 박진용 (IRD v3.0 §5, SDD §5.4).

flow_node(메인 프로그램)나 test/rig_f3.py 가 cobot_common.init() 뒤 **메인 스레드**에서 부르는
평범한 함수다(SDD §3.2). 이름·인자·반환은 cobot_api.F3Api 그대로이고, 실패는 예외가 아니라
Result.fail(code) 로 돌려준다. 숫자는 전부 params.yaml 의 f3 절 · cell.yaml 에서 읽는다(AGENTS 규칙 6).

시작 전제: 용기는 스펀지 홈에 안착돼 있고(F1 place) 툴을 쥔 상태(F1 tool PICK).
끝난 뒤: 툴을 쥔 채 안전 높이. 툴 반납·재파지는 flow 가 F1 을 부른다.

🔸 툴 파지 기준(9/20 확정): 수세미·솔 모두 세척부 위에 손잡이가 있고, **그리퍼 끝을 세척부 윗면에 닿게** 쥔다
   → 그리퍼 끝에서 툴 끝까지 = 세척부 높이 = params.yaml 의 f3.wipe_bowl.tool.clean_h_mm(수세미 45) · f3.wipe_cup.tool.clean_h_mm(솔 95).
   내려가는 거리·삽입 깊이·닦는 반경은 이 값과 cell.yaml 좌표로 계산한다 — 길이를 코드에 적지 않는다.

wipe_bowl 은 F3-02 로 채웠다(V-03 로 확정한 방식). soap · wipe_cup 은 F3-03 에서 채운다.
실측 근거는 docs/test_logs/20260918_CELL-02a_용기치수측정.md · docs/test_logs/20260919_V-03_힘제어중_XY이동.md.
"""
import csv
import math
import os
import time

import cobot_common as cc
from cobot_api import FORCE_LIMIT, OK, ROBOT_ERROR, TIMEOUT, Result, WipeBowlResult, WipeCupResult

FORCE_LOG_HEADER = ('t', 'fx', 'fy', 'fz', 'target')   # SDD §4.2 힘 로그 열


def soap(count: int) -> Result:
    """툴 든 채 세제 수조(SOAP)에 count 회 담근다(모션만, 물 없음). — F3-03.

    절차: move_to('SOAP', carrying=True) → count 회 [f3.soap.depth_mm 하강 → hold_s 유지 → 상승]
    → 안전 높이. 접촉 동작이 아니라 힘 감시는 없지만 cell.limits.timeout_s 는 지킨다(넘으면 TIMEOUT).
    """
    return Result()


def wipe_bowl() -> WipeBowlResult:
    """그릇 안쪽을 수세미로 힘제어 닦기 — F3-02. 코드 OK / FORCE_LIMIT / TIMEOUT / ROBOT_ERROR.

    절차(V-03 로 확정한 방식 — 그릇 크기를 정해 두지 않는다):
      ① move_to('SPONGE_BED_B', carrying=True) → 남은 높이만큼 내려간다
      ② contact_down 으로 바닥을 찾는다(시작 힘 대비 변화량으로 판정 — 툴 무게·센서 치우침 때문)
      ③ force_on('z', target_force_n, limit_n) — 닿은 채 켠다
      ④ 손목을 좌우로 비틀며(슥삭) 나선으로 반경을 넓혀 간다
      ⑤ **명령한 반경을 못 따라가면(벽에 막힘) 벽** — 힘 크기로 보지 않는다(마찰이 안쪽으로 걸려 구분 불가, V-03 9/20)
      ⑥ 그 자리에서 **반대 방향으로 turns 바퀴** — 벽을 follow_gap_mm 만큼 누른 채 돌며 벽면을 닦는다
      ⑦ force_off → safe_retreat (어떤 실패에서도 이 둘은 반드시 한다)
    걸음마다 force_check 로 누르는 힘·옆 힘을 보고 힘 로그(SDD §4.2)에 남긴다.
    """
    p = cc.cfg()['f3']['wipe_bowl']
    t0 = time.monotonic()
    log = _State(p, t0)
    code = ROBOT_ERROR
    try:
        up = cc.move_to('SPONGE_BED_B', carrying=True)          # 안전 높이를 거쳐 홈 상공까지
        if up > 0:
            cc.move_rel(0.0, 0.0, -up, 'BASE')                  # 티칭 자세까지 (자유 공간)
        depth, _ = cc.contact_down(p['contact_max_depth_mm'], cc.cfg()['cell']['limits']['contact_limit_n'])
        if depth >= p['contact_max_depth_mm'] - 0.5:            # 바닥을 못 찾았다 — 용기·좌표 문제
            cc.safe_retreat()
            return WipeBowlResult(ok=False, code=ROBOT_ERROR, duration_s=time.monotonic() - t0)
        log.start(cc.read_force())                              # 닿은 상태를 기준으로 삼는다
        cc.force_on('z', p['target_force_n'], p['limit_n'])
        wall = _spiral_find_wall(p, log)
        if wall is not None:
            _circle_wall(p, log, *wall)
        code = OK if wall is not None else TIMEOUT              # 최대 반경까지 벽이 없으면 닦을 곳을 못 찾은 것
    except cc.ForceLimitError:
        code = FORCE_LIMIT
    except cc.MotionTimeout:
        code = TIMEOUT
    except (RuntimeError, ValueError, KeyError):                # 두산 함수 실패·설정 누락 → 기능은 코드로 보고한다
        code = ROBOT_ERROR
    finally:
        _off_and_retreat()
    return WipeBowlResult(ok=(code == OK), code=code, force_log_path=log.save(),
                          duration_s=time.monotonic() - t0, force_mean_n=log.mean())


def _off_and_retreat():
    """힘·순응을 끄고 안전 높이로. 하나가 실패해도 다음을 시도한다(어떤 실패에서도 안전 높이 — AGENTS §4)."""
    for step in (cc.force_off, cc.safe_retreat):
        try:
            step()
        except Exception:                                       # noqa: BLE001 — 복구는 끝까지 시도한다
            cc.io_node().get_logger().error(f'wipe_bowl 정리 실패: {step.__name__} — 눈으로 확인')


class _State:
    """닦는 동안의 기준 자세·힘 기준값·힘 로그. (파일 안에서만 쓴다)"""

    def __init__(self, p, t0):
        self.p, self.t0 = p, t0
        self.samples = []
        self.presses = []
        self.base = [0.0] * 6
        self.pose0 = None                                       # 바닥에 닿은 자리 = 나선의 중심
        self.x = self.y = self.rz = 0.0
        self.twist, self.step_i = 1, 0
        self.gap = self.climb = 0.0

    def start(self, force):
        self.base = list(force)
        self.pose0 = where()

    def r_max(self):
        """툴 중심이 갈 수 있는 최대 반지름 = 가장 큰 그릇 반지름 − 툴 반지름 + 여유 (그릇 크기 가정이 아니다)."""
        return self.p['bowl_r_max_mm'] - self.p['tool']['d_mm'] / 2 + self.p['r_max_margin_mm']

    def step_to(self, x, y):
        """중심 기준 (x, y) 로 한 걸음 — 동시에 손목을 ±twist_deg 로 비튼다. movel 한 번(BASE 절대·이어 붙이기).

        툴 Z 회전은 ZYZ 의 C 에 더하면 된다(Rz(A)·Ry(B)·Rz(C)·Rz(q) = Rz(A)·Ry(B)·Rz(C+q)).
        Z 는 힘제어 축이라 바닥 높이를 그대로 준다. 순응 중에는 관절 이동(movej)을 하지 않는다.
        """
        p, s = self.p, cc.cfg().get('run', {}).get('vel_scale', 1.0)
        self.step_i += 1
        if self.step_i % max(1, int(p['twist_every'])) == 0:
            self.twist = -self.twist
        self.rz = p['twist_deg'] * self.twist
        x0, y0, z0, a, b, c = self.pose0
        move_pose([x0 + x, y0 + y, z0, a, b, (c + self.rz + 180.0) % 360.0 - 180.0], 'BASE',
                  vel_mm_s=p['lin_vel_mm_s'] * s, acc_mm_s2=p['lin_acc_mm_s2'],
                  vel_deg_s=p['rot_vel_deg_s'] * s, acc_deg_s2=p['rot_acc_deg_s2'],
                  radius_mm=p['blend_radius_mm'])
        self.x, self.y = x, y
        return self.check()

    def check(self):
        """힘 한 번 읽기 → 기록·상한 검사, 실제 위치로 '못 따라간 거리(gap)'와 '올라간 높이(climb)' 갱신."""
        p = self.p
        press, lateral = cc.force_check('z', baseline=self.base)
        if lateral > p['lateral_max_n']:
            raise cc.ForceLimitError(f'wipe_bowl: 옆 힘 {lateral:.1f} N > {p["lateral_max_n"]} N (벽을 세게 밀었다)')
        now = where()
        r = math.hypot(self.x, self.y)
        self.gap = r - math.hypot(now[0] - self.pose0[0], now[1] - self.pose0[1]) if r > 1e-6 else 0.0
        self.climb = now[2] - self.pose0[2]
        f = cc.read_force()
        self.samples.append((round(time.monotonic() - self.t0, 3), f[0], f[1], f[2], p['target_force_n']))
        self.presses.append(press)
        return press

    def blocked(self):
        """벽에 막혔나 — 명령한 반지름을 못 따라갔거나(gap) 툴이 벽을 타고 올라갔나(climb)."""
        return self.gap > self.p['wall_gap_mm'] or self.climb > self.p['climb_max_mm']

    def over_time(self):
        return time.monotonic() - self.t0 > self.p['duration_s']

    def mean(self):
        return sum(self.presses) / len(self.presses) if self.presses else 0.0

    def save(self):
        return _save_force_log(self.samples, self.p['log_dir']) if self.samples else ''


def _spiral_find_wall(p, st):
    """중심에서 나선(한 바퀴에 pitch_mm)으로 넓혀 가며 문지른다 → 벽이면 (반지름, 각도) · 못 찾으면 None."""
    theta = r = 0.0
    hits = 0
    while r <= st.r_max():
        if st.over_time():
            raise cc.MotionTimeout('wipe_bowl: 나선 문지르기 시간 초과')
        st.step_to(r * math.cos(theta), r * math.sin(theta))
        hits = hits + 1 if st.blocked() else 0
        if hits >= p['wall_confirm']:
            return r, theta
        dth = p['step_mm'] / max(r, p['step_mm'])                # 호 길이가 약 step_mm 가 되게
        theta += dth
        if hits == 0:                                           # 벽 같으면 더 넓히지 않고 한 번 더 본다
            r += p['pitch_mm'] * dth / (2 * math.pi)
    return None


def _circle_wall(p, st, r_hit, theta0):
    """벽에 닿은 자리에서 **나선과 반대 방향**으로 turns 바퀴 — 벽을 follow_gap_mm 만큼 누른 채 돈다.

    그릇이 중심에서 어긋나 있어도 벽을 따라가도록 걸음마다 반지름을 고친다(덜 막히면 바깥, 더 막히면 안쪽).
    """
    r, th, done = r_hit, theta0, 0.0
    while done < 2 * math.pi * p['turns']:
        if st.over_time():
            raise cc.MotionTimeout('wipe_bowl: 벽 따라 돌기 시간 초과')
        dth = p['step_mm'] / max(r, p['step_mm'])
        th, done = th - dth, done + dth                          # 반대 방향
        st.step_to(r * math.cos(th), r * math.sin(th))
        dr = (p['follow_gap_mm'] - st.gap) * p['follow_gain']
        if st.climb > p['climb_max_mm']:                         # 벽을 타고 오름 → 안쪽으로
            dr = -p['follow_step_mm']
        dr = max(-p['follow_step_mm'], min(p['follow_step_mm'], dr))
        r = max(0.0, min(st.r_max(), r + dr))


# ------------------------------------------------------------------ 🟡 임시 stub (AGENTS §2 — 남의 함수가 아직 없을 때)
def where():
    """🟡 임시 stub — 지금 자세 [x, y, z, a, b, c] (BASE). motion.py(황인재)에 요청 예정.

    벽에 막혔는지(명령을 못 따라갔는지) 보려면 **실제 위치**가 필요하다.
    """
    from cobot_common.bootstrap import dsr
    return [float(v) for v in dsr().get_current_posx(ref=dsr().DR_BASE)[0]]


def move_pose(pose, frame, *, vel_mm_s, acc_mm_s2, vel_deg_s, acc_deg_s2, radius_mm=0.0):
    """🟡 임시 stub — 주어진 자세로 곧게 이동(회전 포함, 이어 붙이기 radius). motion.py(황인재)에 요청 예정.

    motion.move_rel 에는 회전이 없고 blending 도 없다. 닦기는 **이동과 손목 회전을 한 번에** 해야 하고
    (따로 하면 비틀기가 멈췄다 도는 덜컹거림이 된다), 걸음을 이어 붙여야 부드럽다.
    """
    from cobot_common.bootstrap import dsr
    d = dsr()
    ref = {'BASE': d.DR_BASE, 'TOOL': d.DR_TOOL}[frame]
    ret = d.movel([float(v) for v in pose], vel=[float(vel_mm_s), float(vel_deg_s)],
                  acc=[float(acc_mm_s2), float(acc_deg_s2)], radius=float(radius_mm),
                  ref=ref, mod=d.DR_MV_MOD_ABS)
    if ret != 0:
        raise RuntimeError(f'movel(move_pose {frame}) 실패 (반환 {ret!r})')


def wipe_cup() -> WipeCupResult:
    """컵 안에 솔 삽입(힘 감시) → 회전 + Z 스트로크. 상한 초과 FORCE_LIMIT. — F3-03.

    절차: move_to('SPONGE_BED_C', carrying=True) → contact_down(삽입, cell.limits.insert_limit_n,
    최대 깊이 f3.wipe_cup.insert_depth_mm ≤ f3.wipe_cup.tool.clean_h_mm) — 목표 깊이 전에 힘 상한에 걸리면 safe_retreat·FORCE_LIMIT
    → cycles 회 [툴 Z 축 회전 ±rot_deg + Z 스트로크 stroke_mm] (limit_n 감시) → 컵 밖으로 곧게 상승 → safe_retreat.
    🚨 순응제어 중에는 관절 이동(movej) 불가(중급2, 오류 2.1903) → 회전은 툴 기준 직교 이동으로 하거나
    회전하는 동안 순응을 끈다. 솔은 95 mm 세척부 위에 별도의 파지용 손잡이가 있어
    세척부 전체를 삽입할 수 있다. 바닥 접촉 전 힘 상한과 실제 삽입 깊이는 V-10에서 확정한다.
    """
    return WipeCupResult()


def _save_force_log(samples, log_dir):
    """힘 샘플 [(t, fx, fy, fz, target), ...] 을 CSV 로 남기고 경로를 돌려준다(SDD §4.2).

    파일 이름 force_YYYYMMDD_HHMMSS.csv. log_dir 는 상대경로로 받는다(AGENTS 규칙 7).
    """
    os.makedirs(log_dir, exist_ok=True)
    path = os.path.join(log_dir, time.strftime('force_%Y%m%d_%H%M%S.csv'))
    with open(path, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(FORCE_LOG_HEADER)
        w.writerows(samples)
    return path
