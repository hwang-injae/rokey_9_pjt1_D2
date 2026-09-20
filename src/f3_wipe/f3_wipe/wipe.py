"""F3 접촉 닦기 — 박진용 (IRD v3.0 §5, SDD §5.4).

flow_node(메인 프로그램)나 test/rig_f3.py 가 cobot_common.init() 뒤 **메인 스레드**에서 부르는
평범한 함수다(SDD §3.2). 이름·인자·반환은 cobot_api.F3Api 그대로이고, 실패는 예외가 아니라
Result.fail(code) 로 돌려준다. 숫자는 전부 params.yaml 의 f3 절 · cell.yaml 에서 읽는다(AGENTS 규칙 6).

시작 전제: 용기는 스펀지 홈에 안착돼 있고(F1 place) 툴을 쥔 상태(F1 tool PICK).
끝난 뒤: 툴을 쥔 채 안전 높이. 툴 반납·재파지는 flow 가 F1 을 부른다.

🔸 툴 파지 기준(9/20 확정): 수세미·솔 모두 세척부 위에 손잡이가 있고, **그리퍼 끝을 세척부 윗면에 닿게** 쥔다
   → 그리퍼 끝에서 툴 끝까지 = 세척부 높이 = params.yaml 의 f3.wipe_bowl.tool.clean_h_mm(수세미 45) · f3.wipe_cup.tool.clean_h_mm(솔 95).
   내려가는 거리·삽입 깊이·닦는 반경은 이 값과 cell.yaml 좌표로 계산한다 — 길이를 코드에 적지 않는다.

wipe_bowl 은 F3-02 로 채웠다 — **고정 좌표 방식**(9/20 결정 E6 · SDD §5.4). soap · wipe_cup 은 F3-03 에서 채운다.
🔸 두산 함수를 직접 부르지 않는다(AGENTS §3 규칙 4) — 나선·원호를 포함한 접촉 모션은 cobot_common 의 force.py 에 있다
   (cc.move_spiral · cc.move_arc · cc.where · cc.motion_done).
실측 근거는 docs/test_logs/20260918_CELL-02a_용기치수측정.md · docs/test_logs/20260919_V-03_힘제어중_XY이동.md.
"""
import csv
import math
import os
import time

import cobot_common as cc
from cobot_api import FORCE_LIMIT, OK, ROBOT_ERROR, TIMEOUT, Result, WipeBowlResult, WipeCupResult

STATION_BOWL = 'SPONGE_BED_B'        # 그릇 홈 (cell.beds) — 닦기 자세는 point='wash'

# SDD §4.2 힘 로그 열 (정본이라 그대로 둔다). 🔸 target 은 0 — 고정 좌표 방식이라 유지할 목표 힘이 없다(결정 E6)
FORCE_LOG_HEADER = ('t', 'fx', 'fy', 'fz', 'target')


def soap(count: int, kind: str = None) -> Result:
    """툴 든 채 세제 수조(SOAP)에 count 회 담근다(모션만, 물 없음). — F3-03.

    kind(BOWL/CUP): SOAP 은 종류별 자리다 — BOWL = 수세미를 쥔 자세 · CUP = 솔을 쥔 자세 (9/20 약속 추가, flow 가 넘겨 준다).
    절차: cc.move_to('SOAP', True, kind) → count 회 [f3.soap.depth_mm 하강 → hold_s 유지 → 상승]
    → 안전 높이. 접촉 동작이 아니라 힘 감시는 없지만 cell.limits.timeout_s 는 지킨다(넘으면 TIMEOUT).
    """
    return Result()


def wipe_bowl() -> WipeBowlResult:
    """그릇 안쪽을 수세미로 닦는다 — F3-02. 코드 OK / FORCE_LIMIT / TIMEOUT / ROBOT_ERROR.

    **고정 좌표 방식**(결정 E6 · SDD §5.4). 괄호 안은 강의자료 근거.
      ① cc.move_to('SPONGE_BED_B', point='wash') → 티칭한 닦는 높이까지 내려간다
         — 앞은 빠르게, 마지막 slow_mm 구간만 천천히 걸음마다 누르는 힘을 보면서
      ② 바닥: **나선 한 번** — 중심에서 벽 반지름까지, 좌우 비틀기 없음
         (중급1 p.69 나선은 **시간**으로 속도 지정 · 반경 대비 회전 수가 과하면 시작조차 하지 않는다)
      ③ 벽면: 원호를 이어 붙여 **반대 방향 turns 바퀴** + 손목(6번 축) ±twist_deg 좌우 비틀기
         (중급1 p.79 중첩 가능한 모션은 Move L·C·J·JX — radius 를 줘야 멈추지 않고 이어진다)
      ④ 올리지 않고 그 높이에서 중심 복귀 → safe_retreat

    🚨 **찾지 않는다**: 벽 찾기 · 바닥 찾기(contact_down) · 목표 힘 유지(force_on) 를 쓰지 않는다.
       수세미가 로봇 순응보다 훨씬 물러 "못 따라간 거리"가 생기지 않고, 바닥 마찰(5~14 N)이 벽 신호(1~2 N)를 덮는다(V-03).
       벽 반지름 = (bowl_inner_d_mm − tool.d_mm)/2 + wall_press_mm.
    🚨 **순응도 켜지 않는다**: 순응을 켠 채 내리면 명령한 Z 와 실제 Z 가 다르다(Z 200 N/m 면 3 N 에 15 mm 덜 내려간다)
       → 고정 높이가 뜻을 잃는다. 대신 수세미(스펀지)가 완충 노릇을 하고, 안전은 아래 힘 감시가 맡는다.
       닦는 높이에 닿으면 **실제 Z 를 로그로 남긴다**(명령한 높이와 같은지 확인용).
    감시는 한다(NFR-01): 공중 기준값 대비 누르는 힘 > limit_n 또는 옆 힘 > lateral_max_n 이면 즉시 후퇴 FORCE_LIMIT ·
    duration_s 를 넘으면 TIMEOUT · 힘 로그 CSV 저장. 구간과 구간 사이에서 강제정지(cc.is_halted)를 본다.
    """
    p = cc.cfg()['f3']['wipe_bowl']
    t0 = time.monotonic()
    log = _Log(p, t0)
    code = ROBOT_ERROR
    try:
        _descend(p, log)                                                 # ① 닦는 높이까지
        _spiral(p, log)                                                  # ② 바닥 나선
        _wall_laps(p, log)                                               # ③ 벽면 turns 바퀴
        _to_center(p, log)                                               # ④ 그 높이에서 중심으로
        code = OK
    except cc.MotionHalted:                                              # 강제정지는 코드로 바꾸지 않는다 — flow 의 중단 흐름으로 (결정 E11)
        raise
    except cc.ForceLimitError:
        code = FORCE_LIMIT
    except (cc.MotionTimeout, cc.MoveTimeout):
        code = TIMEOUT
    except (RuntimeError, ValueError, KeyError):
        code = ROBOT_ERROR
    finally:
        _off_and_retreat()                                               # 끝나든 실패하든 힘을 끄고 안전 높이로
    return WipeBowlResult(ok=(code == OK), code=code, force_log_path=log.save(),
                          duration_s=time.monotonic() - t0, force_mean_n=log.mean())


def _off_and_retreat():
    """어떤 실패에서도 힘·순응을 끄고 안전 높이로 (AGENTS §4). 하나가 실패해도 다음을 시도한다."""
    for step in (cc.force_off, cc.safe_retreat):
        try:
            step()
        except Exception:                                                # noqa: BLE001 — 복구는 끝까지
            _warn(f'wipe_bowl 정리 실패: {step.__name__} — 눈으로 확인')


def _info(msg):
    cc.io_node().get_logger().info(msg)


def _warn(msg):
    cc.io_node().get_logger().error(msg)


def _halt_check(where):
    """구간과 구간 사이에서만 강제정지를 본다 — 나선·원호는 도는 중에 끊을 수 없다(move_periodic 과 같은 취급)."""
    if cc.is_halted():
        raise cc.MotionHalted(f'wipe_bowl: {where} 앞에서 강제정지')


class _Log:
    """닦는 동안의 공중 기준값·중심 자세·힘 로그(SDD §4.2). 이 파일 안에서만 쓴다."""

    def __init__(self, p, t0):
        self.p, self.t0 = p, t0
        self.samples, self.presses = [], []
        self.base = [0.0] * 6                                            # 공중 기준값 — 툴 무게·센서 치우침(V-03: 1.4~2.4 N)
        self.center = None                                               # 닦는 높이에 닿은 자리 = 나선의 중심

    def start(self, force):
        self.base = list(force)

    def wall_r(self):
        """벽에 닿는 툴 중심 반지름 = (그릇 안지름 − 툴 지름)/2 + 벽 누름. 힘으로 찾지 않는다(결정 E6)."""
        p = self.p
        return max(0.0, (p['bowl_inner_d_mm'] - p['tool']['d_mm']) / 2 + p['wall_press_mm'])

    def watch(self, phase):
        """힘만 읽어 기록·상한 확인 — 도는 중에는 위치를 읽지 않는다(서비스 왕복이 끼면 로봇이 선다, 9/20)."""
        p = self.p
        f = cc.read_force()
        press = abs(f[2] - self.base[2])
        lateral = math.hypot(f[0] - self.base[0], f[1] - self.base[1])
        self.samples.append((round(time.monotonic() - self.t0, 3), f[0], f[1], f[2], 0.0))
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


def _descend(p, log):
    """닦는 자리 위 → 티칭한 닦는 높이. 앞은 빠르게, 마지막 slow_mm 만 걸음마다 힘을 보면서 천천히."""
    _halt_check('닦는 자리 이동')
    up = cc.move_to(STATION_BOWL, carrying=True, point='wash')           # 접근점까지 · up = 끝점(닦는 높이)까지 남은 높이
    log.start(cc.read_force())                                           # 공중 기준값은 **내려가기 전에** 잰다
    slow = min(float(p['slow_mm']), up)
    if up - slow > 0:
        cc.move_rel(0.0, 0.0, -(up - slow), 'BASE')                      # 앞 구간은 보통 속도
    vel = float(p['slow_vel_mm_s']) * _scale()
    left = slow
    while left > 1e-6:                                                   # 느린 구간 — 걸음마다 누르는 힘 상한
        dz = min(float(p['slow_step_mm']), left)
        cc.move_rel(0.0, 0.0, -dz, 'BASE', vel_mm_s=vel)
        left -= dz
        log.watch('down')
    log.center = cc.where()
    _info(f'wipe_bowl 닦는 높이: 실제 Z {log.center[2]:.1f} mm (순응 끔 — 명령한 높이와 같아야 한다), '
          f'공중 기준 Fz {log.base[2]:.1f} N')


def _spiral(p, log):
    """바닥 나선 한 번 — 중심에서 벽 반지름까지. 좌우 비틀기 없음."""
    _halt_check('바닥 나선')
    r_wall = log.wall_r()
    rev = max(1.0, round(r_wall / p['spiral_pitch_mm'], 1))
    cc.move_spiral(rev, r_wall, p['spiral_time_s'])                      # 비동기 — 도는 동안 힘만 본다
    while not cc.motion_done():
        if log.over_time():
            raise cc.MotionTimeout('wipe_bowl: 나선 시간 초과')
        log.watch('spiral')
        time.sleep(p['sample_s'])
    moved = _radius(cc.where(), log.center)
    if moved < r_wall * 0.5:                                             # 명령은 받았는데 돌지 않았다(9/20 실기 증상)
        raise RuntimeError(f'나선이 돌지 않았다(실제 {moved:.1f} mm / 목표 {r_wall:.1f} mm) — '
                           '회전 수·시간 조합을 확인(중급1 p.69)')


def _wall_laps(p, log):
    """벽면 — 원호(Move C)를 이어 붙여 반대 방향 turns 바퀴, 원호마다 손목 좌우 비틀기."""
    _halt_check('벽면 회전')
    r = log.wall_r()
    x0, y0, _z0, a, b, c = log.center
    now = cc.where()
    z = now[2]                                                           # 닦는 높이 그대로 (힘제어를 쓰지 않으므로 변하지 않는다)
    gap = r - _radius(now, log.center)
    if gap > 0.1:                                                        # 나선이 벽까지 다 못 갔으면 남은 만큼만 천천히 붙인다
        th = math.atan2(now[1] - y0, now[0] - x0)
        cc.move_rel(gap * math.cos(th), gap * math.sin(th), 0.0, 'BASE',
                    vel_mm_s=float(p['wall_approach_vel_mm_s']) * _scale())
        log.watch('wall')
    per = max(2, int(round(360.0 / p['wall_arc_deg'])))
    n = int(p['turns'] * per)
    dth = -2 * math.pi / per                                             # 나선과 반대 방향
    th0 = math.atan2(cc.where()[1] - y0, cc.where()[0] - x0)
    chord = 2 * r * abs(math.sin(dth / 2))
    blend = min(float(p['blend_radius_mm']), chord * 0.45)               # 이어 붙이는 거리가 호의 절반을 넘으면 안 된다

    def pose(th, rz):
        return [x0 + r * math.cos(th), y0 + r * math.sin(th), z, a, b, (c + rz + 180.0) % 360.0 - 180.0]

    twist = 1
    for k in range(n):
        if log.over_time():
            raise cc.MotionTimeout('wipe_bowl: 벽면 시간 초과')
        th_mid, th_end = th0 + dth * (k + 0.5), th0 + dth * (k + 1)
        rz_mid = p['twist_deg'] * twist
        twist = -twist
        rz_end = 0.0 if k == n - 1 else p['twist_deg'] * twist           # 마지막 원호는 손목을 제자리로 돌려놓고 끝낸다
        cc.move_arc(pose(th_mid, rz_mid), pose(th_end, rz_end),
                    p['lin_vel_mm_s'], p['rot_vel_deg_s'],
                    0.0 if k == n - 1 else blend)                        # 마지막만 이어 붙이지 않는다(그 자리에 선다)
        if k % max(1, int(p['force_every'])) == 0:
            log.watch('wall')


def _to_center(p, log):
    """세척 끝 — 올리지 않고 그 높이에서 중심(내려온 자리)으로. 손목은 마지막 원호에서 이미 제자리다."""
    _halt_check('중심 복귀')
    now = cc.where()
    cc.move_rel(log.center[0] - now[0], log.center[1] - now[1], 0.0, 'BASE',
                vel_mm_s=float(p['lin_vel_mm_s']) * _scale())


def _radius(pose, center):
    return math.hypot(pose[0] - center[0], pose[1] - center[1])


def _scale():
    """실행 인자 vel_scale — 속도를 직접 주는 이동에는 부르는 쪽이 곱한다(cobot_common 약속)."""
    return float(cc.cfg().get('run', {}).get('vel_scale', 1.0))


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
