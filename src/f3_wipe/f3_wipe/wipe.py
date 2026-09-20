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

STATION_BOWL = 'SPONGE_BED_B'        # 그릇 홈 (cell.beds) — 닦기 자세는 point='wash'

FORCE_LOG_HEADER = ('t', 'fx', 'fy', 'fz', 'target')   # SDD §4.2 힘 로그 열


def soap(count: int) -> Result:
    """툴 든 채 세제 수조(SOAP)에 count 회 담근다(모션만, 물 없음). — F3-03.

    절차: move_to('SOAP', carrying=True) → count 회 [f3.soap.depth_mm 하강 → hold_s 유지 → 상승]
    → 안전 높이. 접촉 동작이 아니라 힘 감시는 없지만 cell.limits.timeout_s 는 지킨다(넘으면 TIMEOUT).
    """
    return Result()


def wipe_bowl() -> WipeBowlResult:
    """그릇 안쪽을 수세미로 닦는다 — F3-02. 코드 OK / FORCE_LIMIT / TIMEOUT / ROBOT_ERROR.

    V-03(9/20 실기)으로 확정한 절차. 괄호 안은 강의자료 근거.
      ① move_to('SPONGE_BED_B', point='wash') → 남은 높이만큼 내려간다
      ② contact_down 으로 바닥을 찾는다(시작 힘 대비 변화량 — 툴 무게·센서 치우침 때문)
      ③ **순응만** 켠다(힘제어는 아직) — 찾은 자리 그대로 (중급2: Force 전에 Compliance)
      ④ 바닥: **나선 한 번** — 좌우 비틀기 없음, 힘제어 없음
         (중급2 "힘 방향과 같은 방향의 모션 불가" — 나선은 툴 Z 축 모션이라 Z 힘제어와 같은 축)
         (중급1 p.69 나선은 **시간**으로 속도 지정 · 반경 대비 회전 수가 과하면 시작조차 하지 않는다)
      ⑤ 힘제어 ON(target_force_n) → 벽면: 원호를 이어 붙여 **반대 방향 turns 바퀴** + 손목 ±twist_deg
         (중급1 p.79 중첩 가능한 모션은 Move L·C·J·JX · 중급2 힘 Z + 이동 X·Y = 폴리싱)
      ⑥ 힘제어 OFF → 순응 OFF → 그 높이에서 중심 복귀 → safe_retreat
    벽 반지름 = (그릇 안지름 − 툴 지름)/2 + wall_press_mm — 수세미가 물러 벽 힘이 잡히지 않아 크기로 계산한다(9/20 결정).
    """
    p = cc.cfg()['f3']['wipe_bowl']
    limits = cc.cfg()['cell']['limits']
    t0 = time.monotonic()
    log = _Log(p, t0)
    code = ROBOT_ERROR
    try:
        up = cc.move_to(STATION_BOWL, carrying=True, point='wash')       # 홈 상공(접근점)까지
        if up > 0:
            cc.move_rel(0.0, 0.0, -up, 'BASE')                           # 티칭한 닦기 자세까지
        depth, _ = cc.contact_down(p['contact_max_depth_mm'], limits['contact_limit_n'])
        if depth >= p['contact_max_depth_mm'] - 0.5:                     # 바닥을 못 찾았다 — 용기·좌표 문제
            return _fail(log, ROBOT_ERROR, t0)
        log.start(cc.read_force(), _where())
        cc.compliance_on()                                               # ③ 순응만 (찾은 자리 그대로)
        _spiral(p, log)                                                  # ④ 바닥 나선 (힘제어 없음)
        cc.force_on('z', p['target_force_n'] + abs(log.base[2]), p['limit_n'])   # ⑤ 힘제어 (공중 기준값 보정)
        _wall_laps(p, log)
        cc.force_off()
        _to_center(p, log)                                               # ⑥ 그 높이에서 중심으로
        code = OK
    except cc.ForceLimitError:
        code = FORCE_LIMIT
    except cc.MotionTimeout:
        code = TIMEOUT
    except (RuntimeError, ValueError, KeyError):
        code = ROBOT_ERROR
    finally:
        _off_and_retreat()
    return WipeBowlResult(ok=(code == OK), code=code, force_log_path=log.save(),
                          duration_s=time.monotonic() - t0, force_mean_n=log.mean())


def _fail(log, code, t0):
    """바닥을 못 찾는 등 시작 전 실패 — 힘·순응은 켜지 않은 상태로 돌아간다."""
    return WipeBowlResult(ok=False, code=code, force_log_path=log.save(), duration_s=time.monotonic() - t0)


def _off_and_retreat():
    """어떤 실패에서도 힘·순응을 끄고 안전 높이로 (AGENTS §4). 하나가 실패해도 다음을 시도한다."""
    for step in (cc.force_off, cc.safe_retreat):
        try:
            step()
        except Exception:                                                # noqa: BLE001 — 복구는 끝까지
            cc.io_node().get_logger().error(f'wipe_bowl 정리 실패: {step.__name__} — 눈으로 확인')


class _Log:
    """닦는 동안의 기준값·중심 자세·힘 로그(SDD §4.2). 이 파일 안에서만 쓴다."""

    def __init__(self, p, t0):
        self.p, self.t0 = p, t0
        self.samples, self.presses = [], []
        self.base = [0.0] * 6
        self.center = None                                               # 바닥에 닿은 자리 = 나선의 중심

    def start(self, force, pose):
        self.base, self.center = list(force), list(pose)

    def wall_r(self):
        """벽에 닿는 툴 중심 반지름 = (그릇 안지름 − 툴 지름)/2 + 벽 누름."""
        p = self.p
        return max(0.0, (p['bowl_inner_d_mm'] - p['tool']['d_mm']) / 2 + p['wall_press_mm'])

    def watch(self, phase):
        """힘만 읽어 기록·상한 확인 — 도는 중에는 위치를 읽지 않는다(서비스 왕복이 끼면 로봇이 선다, 9/20)."""
        p = self.p
        f = cc.read_force()
        press = abs(f[2] - self.base[2])
        lateral = math.hypot(f[0] - self.base[0], f[1] - self.base[1])
        self.samples.append((round(time.monotonic() - self.t0, 3), f[0], f[1], f[2], p['target_force_n']))
        self.presses.append(press)
        if press > p['limit_n']:
            raise cc.ForceLimitError(f'{phase}: 누르는 힘 {press:.1f} N > {p["limit_n"]} N')
        if lateral > p['lateral_max_n']:
            raise cc.ForceLimitError(f'{phase}: 옆 힘 {lateral:.1f} N > {p["lateral_max_n"]} N')

    def over_time(self):
        return time.monotonic() - self.t0 > self.p['duration_s']

    def mean(self):
        return sum(self.presses) / len(self.presses) if self.presses else 0.0

    def save(self):
        return _save_force_log(self.samples, self.p['log_dir']) if self.samples else ''


def _spiral(p, log):
    """바닥 나선 한 번 — 중심에서 벽 반지름까지. 좌우 비틀기·힘제어 없음."""
    r_wall = log.wall_r()
    rev = max(1.0, round(r_wall / p['spiral_pitch_mm'], 1))
    _move_spiral(rev, r_wall, p['spiral_time_s'])
    while not _motion_done():                                            # 도는 동안 힘만 확인
        if log.over_time():
            raise cc.MotionTimeout('wipe_bowl: 나선 시간 초과')
        log.watch('spiral')
        time.sleep(p['sample_s'])
    moved = math.hypot(*[a - b for a, b in zip(_where()[:2], log.center[:2])])
    if moved < r_wall * 0.5:                                             # 명령은 받았는데 돌지 않았다(9/20 실기)
        raise RuntimeError(f'나선이 돌지 않았다(실제 {moved:.1f} mm / 목표 {r_wall:.1f}) — '
                           '회전 수·시간 조합 또는 힘제어가 켜져 있는지 확인')


def _wall_laps(p, log):
    """벽면 — 원호를 이어 붙여 반대 방향 turns 바퀴, 원호마다 손목 좌우 비틀기."""
    r = log.wall_r()
    x0, y0, z0, a, b, c = log.center
    z = _where()[2]                                                      # 지금 높이(힘제어가 정한다)
    per = max(2, int(round(360.0 / p['wall_arc_deg'])))
    n = int(p['turns'] * per)
    dth = -2 * math.pi / per                                             # 나선과 반대 방향
    th0 = math.atan2(_where()[1] - y0, _where()[0] - x0)

    def pose(th, rz):
        return [x0 + r * math.cos(th), y0 + r * math.sin(th), z, a, b, (c + rz + 180.0) % 360.0 - 180.0]

    _move_pose(pose(th0, p['twist_deg']), p['wall_approach_vel_mm_s'], 0.0)   # 벽까지 천천히 밀어 붙인다
    log.watch('wall')
    twist = 1
    for k in range(n):
        if log.over_time():
            raise cc.MotionTimeout('wipe_bowl: 벽면 시간 초과')
        th_mid, th_end = th0 + dth * (k + 0.5), th0 + dth * (k + 1)
        rz_mid = p['twist_deg'] * twist
        twist = -twist
        blend = 0.0 if k == n - 1 else p['blend_radius_mm']
        _move_arc(pose(th_mid, rz_mid), pose(th_end, p['twist_deg'] * twist), p['lin_vel_mm_s'],
                  p['rot_vel_deg_s'], blend)
        if k % max(1, int(p['force_every'])) == 0:
            log.watch('wall')


def _to_center(p, log):
    """세척 끝 — 올리지 않고 그 높이에서 중심(닿았던 자리)으로. 손목도 0 으로."""
    x0, y0, _z, a, b, c = log.center
    _move_pose([x0, y0, _where()[2], a, b, c], p['lin_vel_mm_s'], 0.0)


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


# ------------------------------------------------------------------ 🟡 임시 stub (AGENTS §2 — 남의 함수가 아직 없을 때)
# motion.py(황인재)에 요청할 것: ① 지금 자세 읽기 ② 회전을 포함한 절대 이동(+이어 붙이기) ③ 원호 이동 ④ 나선
# 넷 다 두산 함수를 그대로 감싸는 것이고, 지금은 이 파일에서 같은 이름으로 임시로 둔다(이슈로 올린 뒤 motion.py 로 옮긴다).
def _dsr():
    from cobot_common.bootstrap import dsr
    return dsr()


def _where():
    """🟡 지금 자세 [x, y, z, a, b, c] (BASE)."""
    d = _dsr()
    return [float(v) for v in d.get_current_posx(ref=d.DR_BASE)[0]]


def _motion_done():
    """🟡 비동기 동작이 끝났나 (check_motion == 0)."""
    return _dsr().check_motion() == 0


def _move_spiral(rev, rmax_mm, time_s):
    """🟡 툴 Z 축 나선 (비동기).

    🚨 속도(vel)로 부르면 드라이버가 멈춘다 — **vel·acc 0 + time** 으로만 부른다(중급1 p.69, 9/20 실기).
    """
    d = _dsr()
    d.mwait()
    ret = d.amove_spiral(rev=float(rev), rmax=float(rmax_mm), lmax=0.0, vel=[0.0, 0.0], acc=[0.0, 0.0],
                         time=float(time_s), axis=d.DR_AXIS_Z, ref=d.DR_TOOL)
    if ret != 0:
        raise RuntimeError(f'amove_spiral 실패 (반환 {ret!r})')


def _move_pose(pose, vel_mm_s, radius_mm):
    """🟡 주어진 자세로 곧게 (회전 포함, 이어 붙이기 radius)."""
    d = _dsr()
    s = cc.cfg().get('run', {}).get('vel_scale', 1.0)
    ret = d.movel([float(v) for v in pose], vel=[float(vel_mm_s) * s, 60.0 * s], acc=[600.0, 600.0],
                  radius=float(radius_mm), ref=d.DR_BASE, mod=d.DR_MV_MOD_ABS)
    if ret != 0:
        raise RuntimeError(f'movel 실패 (반환 {ret!r})')


def _move_arc(mid, end, vel_mm_s, vel_deg_s, radius_mm):
    """🟡 원호 이동 (Move C) — radius 를 주면 다음 원호로 이어 붙는다(중급1 p.79 중첩 가능)."""
    d = _dsr()
    s = cc.cfg().get('run', {}).get('vel_scale', 1.0)
    ret = d.movec([float(v) for v in mid], [float(v) for v in end],
                  vel=[float(vel_mm_s) * s, float(vel_deg_s) * s], acc=[1200.0, 1000.0],
                  radius=float(radius_mm), ref=d.DR_BASE, mod=d.DR_MV_MOD_ABS)
    if ret != 0:
        raise RuntimeError(f'movec 실패 (반환 {ret!r})')


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
