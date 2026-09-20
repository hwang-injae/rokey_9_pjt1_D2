"""F3 접촉 닦기 — 박진용 (IRD v3.0 §5, SDD §5.4).

flow_node(메인 프로그램)나 test/rig_f3.py 가 cobot_common.init() 뒤 **메인 스레드**에서 부르는
평범한 함수다(SDD §3.2). 이름·인자·반환은 cobot_api.F3Api 그대로이고, 실패는 예외가 아니라
Result.fail(code) 로 돌려준다. 숫자는 전부 params.yaml 의 f3 절 · cell.yaml 에서 읽는다(AGENTS 규칙 6).

시작 전제: 용기는 스펀지 홈에 안착돼 있고(F1 place) 툴을 쥔 상태(F1 tool PICK).
끝난 뒤: 툴을 쥔 채 안전 높이. 툴 반납·재파지는 flow 가 F1 을 부른다.

🔸 툴 파지 기준(9/20 확정): 수세미·솔 모두 세척부 위에 손잡이가 있고, **그리퍼 끝을 세척부 윗면에 닿게** 쥔다
   → 그리퍼 끝에서 툴 끝까지 = 세척부 높이 = params.yaml 의 f3.wipe_bowl.tool.clean_h_mm(수세미 35) · f3.wipe_cup.tool.clean_h_mm(솔 95).
   내려가는 거리·삽입 깊이·닦는 반경은 이 값과 cell.yaml 좌표로 계산한다 — 길이를 코드에 적지 않는다.

wipe_bowl = F3-02 **고정 좌표 방식**(9/20 결정 E6 · SDD §5.4) · soap · wipe_cup = F3-03.
🔸 그릇만 고정 좌표다 — 컵은 깊고 솔이 단단해 **삽입만 힘으로 찾는다**(contact_down), 문지르기는 위치 제어다.
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
STATION_CUP = 'SPONGE_BED_C'         # 컵 홈

_R_MIN_MM = 2.0                      # 나선 방향을 재기 시작하는 반지름 — 중심 근처에서는 각도가 튄다

FORCE_LOG_HEADER = ('t', 'fx', 'fy', 'fz', 'target')   # SDD §4.2 힘 로그 열


def soap(count: int, kind: str = None) -> Result:
    """툴 든 채 세제 수조(SOAP)에 count 회 담근다(모션만, 물 없음). — F3-03. 코드 OK / TIMEOUT / ROBOT_ERROR.

    kind(BOWL/CUP): SOAP 은 종류별 자리다 — BOWL = 수세미를 쥔 자세 · CUP = 솔을 쥔 자세 (9/20 약속 추가, flow 가 넘겨 준다).
    절차: cc.move_to('SOAP', True, kind) → count 회 [f3.soap.depth_mm 하강 → hold_s 유지 → 상승] → safe_retreat.
    수조 안은 비어 있어(물·세제 없음) **접촉 동작이 아니다** — 순응·힘제어를 켜지 않고 힘 감시도 없다(AGENTS 규칙 3).
    대신 cell.limits.timeout_s 는 지키고(넘으면 TIMEOUT), 담금과 담금 사이에서 강제정지를 본다.
    담그는 깊이는 수조 깊이보다 작아야 한다 — 값은 V-07 에서(물 없이 모션만).
    """
    p = cc.cfg()['f3']['soap']
    timeout = cc.cfg()['cell']['limits']['timeout_s']
    if count < 0:
        return Result(ok=False, code=ROBOT_ERROR)
    t0 = time.monotonic()
    code = ROBOT_ERROR
    try:
        _halt_check('세제 수조 이동')
        up = cc.move_to('SOAP', carrying=True, kind=kind)
        if up > 0:
            cc.move_rel(0.0, 0.0, -up, 'BASE')                           # 티칭한 담금 시작 자세까지
        depth = float(p['depth_mm'])
        vel = float(p['vel_mm_s']) * _scale()
        for i in range(int(count)):
            _halt_check(f'{i + 1}번째 담금')
            if time.monotonic() - t0 > timeout:
                raise cc.MotionTimeout(f'soap: {timeout} s 안에 {count} 회를 못 끝냈다({i} 회 함)')
            cc.move_rel(0.0, 0.0, -depth, 'BASE', vel_mm_s=vel)
            time.sleep(float(p['hold_s']))
            cc.move_rel(0.0, 0.0, +depth, 'BASE', vel_mm_s=vel)          # 넣은 만큼 그대로 뺀다
        code = OK
    except cc.MotionHalted:
        raise
    except (cc.MotionTimeout, cc.MoveTimeout):
        code = TIMEOUT
    except (RuntimeError, ValueError, KeyError):
        code = ROBOT_ERROR
    finally:
        _off_and_retreat()
    return Result(ok=(code == OK), code=code)


def wipe_bowl() -> WipeBowlResult:
    """그릇 안쪽을 수세미로 닦는다 — F3-02. 코드 OK / FORCE_LIMIT / TIMEOUT / ROBOT_ERROR.

    **9/20 실기(V-03)로 확정한 절차 그대로**다(rig_v03.py · docs/test_logs/20260919_V-03_*). 괄호 안은 강의자료 근거.
      ① cc.move_to('SPONGE_BED_B', point='wash') → 빠르게 내려간 뒤 **바닥을 힘으로 찾는다**(cc.contact_down)
      ② **순응 ON** — 바닥을 찾은 그 자리에서. 더 누르지 않는다 (중급2: 목표 TCP 근처에서 켜는 것을 권장)
      ③ 바닥: **나선 한 번** — 중심에서 벽 반지름까지, 좌우 비틀기 없음, **힘제어는 켜지 않는다**
         (중급2 "힘 방향과 같은 방향의 모션 불가" — 나선은 툴 Z 축 모션이라 Z 힘제어와 같은 축이다.
          9/20 실기: 켜 두면 반환은 0 인데 나선이 시작조차 하지 않았다)
         (중급1 p.69 나선은 **시간**으로 속도 지정 · 반경 대비 회전 수가 과하면 시작조차 하지 않는다)
      ④ **힘제어 ON** — Z 로 target_force_n 유지. 공중 기준값(센서 치우침·툴 무게)을 더해서 명령한다
      ⑤ 벽면: 원호를 이어 붙여 **반대 방향 turns 바퀴** + 손목(6번 축) ±twist_deg 좌우 비틀기
         (이동이 X·Y 라 Z 힘제어와 함께 쓸 수 있다 — 중급2 폴리싱 예시)
         (중급1 p.79 중첩 가능한 모션은 Move L·C·J·JX — radius 를 줘야 멈추지 않고 이어진다)
      ⑥ **힘제어만 OFF**(순응은 유지) → ⑦ 올리지 않고 그 높이에서 중심 복귀 → 순응 OFF → safe_retreat

    🚨 **벽은 찾지 않는다**(결정 E6): 벽 반지름 = (bowl_inner_d_mm − tool.d_mm)/2 + wall_press_mm 로 계산한다.
       수세미가 로봇 순응보다 훨씬 물러 "못 따라간 거리"가 생기지 않고, 바닥 마찰(5~14 N)이 벽 신호(1~2 N)를 덮는다(V-03).
    🔸 **바닥은 찾는다**(박진용 9/21 — 9/20 실기에서 확인한 방식). 접촉 깊이가 실행마다 12~17 mm 로 달라서
       티칭한 높이 하나로는 맞출 수 없다. 🚨 결정 E6 ① 은 "고정 높이"였으므로 PM 에게 알려야 한다.
    🔸 **순응·힘제어는 접촉 구간에서만** 켠다(AGENTS 규칙 3): 바닥을 찾은 뒤 순응, 벽면에서만 힘제어.
       어떤 실패에서도 힘 → 순응 순서로 끄고 안전 높이로 올라온다.
    감시는 한다(NFR-01): 공중 기준값 대비 누르는 힘 > limit_n 또는 옆 힘 > lateral_max_n 이면 즉시 후퇴 FORCE_LIMIT ·
    duration_s 를 넘으면 TIMEOUT · 힘 로그 CSV 저장. 구간과 구간 사이에서 강제정지(cc.is_halted)를 본다.
    """
    p = cc.cfg()['f3']['wipe_bowl']
    t0 = time.monotonic()
    log = _Log(p, t0)
    code = ROBOT_ERROR
    try:
        _descend(p, log)                                                 # ① 빠른 접근 → 바닥 찾기
        cc.compliance_on()                                               # ② 순응 ON (찾은 자리 그대로)
        _spiral(p, log)                                                  # ③ 바닥 나선 (힘제어 없이)
        log.target = float(p['target_force_n'])
        cc.force_on('z', log.target + abs(log.base[2]), p['limit_n'])    # ④ 힘제어 ON (공중 기준값 보정)
        _wall_laps(p, log)                                               # ⑤ 벽면 turns 바퀴
        cc.force_release()                                               # ⑥ 힘제어만 OFF (순응은 유지)
        log.target = 0.0
        _to_center(p, log)                                               # ⑦ 그 높이에서 중심으로
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
        self.sweep = 0.0                                                 # 나선이 실제로 돈 각도(rad, BASE 기준 부호 있음)
        self.target = 0.0                                                # 지금 구간의 목표 누르는 힘 (힘 로그의 target 열)

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
        self.samples.append((round(time.monotonic() - self.t0, 3), f[0], f[1], f[2], self.target))
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
    """닦는 자리 위 → 빠르게 내려간 뒤 **바닥을 힘으로 찾는다**(9/20 실기에서 확인한 방식, 박진용 9/21 확정).

    빠른 하강은 티칭한 끝점(cell.beds.SPONGE_BED_B.wash.posx 의 z = 9/20 실기로 잰 바닥) **find_gap_mm 위**까지.
       나머지는 힘으로 찾는다 — 접촉 깊이가 실행마다 12~17 mm 로 달라 끝점 하나로는 맞출 수 없다.
    바닥 찾기는 cc.contact_down — 순응을 켜고 cell.force.contact_step_mm 씩 내려가며
    **시작 힘 대비** cell.limits.contact_limit_n 만큼 힘이 커지면 멈춘다(공중 치우침 1.4~2.4 N 때문에 절대값으로 보면 안 된다).
    찾은 자리에서 더 누르지 않는다. contact_down 이 끝나며 순응을 꺼 주므로 닦기는 위치 제어로 이어진다.
    """
    _halt_check('닦는 자리 이동')
    up = cc.move_to(STATION_BOWL, carrying=True, point='wash')           # 접근점까지 · up = 티칭 끝점까지 남은 높이
    log.start(cc.read_force())                                           # 공중 기준값은 **내려가기 전에** 잰다
    fast = max(0.0, up - float(p['find_gap_mm']))                        # ① 빠르게 (바닥 find_gap_mm 위까지)
    if fast > 0:
        cc.move_rel(0.0, 0.0, -fast, 'BASE')
    depth, f = cc.contact_down(float(p['find_max_mm']),                   # ② 나머지는 힘으로
                               cc.cfg()['cell']['limits']['contact_limit_n'])
    log.center = cc.where()
    _info(f'wipe_bowl 바닥: 빠르게 {fast:.0f} mm + 찾기 {depth:.1f} mm (최대 {p["find_max_mm"]:g}) '
          f'· 접촉 힘 {f:.1f} N · 실제 Z {log.center[2]:.1f} mm · 공중 기준 Fz {log.base[2]:.1f} N')
    if depth >= float(p['find_max_mm']) - 0.5:                           # 끝까지 내려가도 바닥이 없다
        raise RuntimeError(f'wipe_bowl: {p["find_max_mm"]:g} mm 를 내려가도 바닥을 못 찾았다 — 그릇·좌표 확인')


def _spiral(p, log):
    """바닥 나선 한 번 — 중심에서 벽 반지름까지. 좌우 비틀기 없음.

    🔸 도는 동안 **방향도 잰다**(log.sweep, BASE 기준 부호 있는 총 회전각). 벽면을 그 반대로 돌기 위해서다.
       나선은 TOOL 기준이고 원호는 BASE 기준인데, 닦는 자세는 툴 Z 가 아래를 향한다(b=180)
       → **툴에서 반시계로 돌면 베이스에서는 시계로 보인다.** 부호를 미리 정해 두면 두 동작이 같은 방향이 된다(9/21 실측).
       두산 API 에는 방향 인자가 없고(rev > 0 만 허용) 강의자료에도 방향 설명이 없어서, 추측하지 않고 잰다.
    """
    _halt_check('바닥 나선')
    r_wall = log.wall_r()
    rev = max(1.0, round(r_wall / p['spiral_pitch_mm'], 1))
    every = max(1, int(p['force_every']))
    cc.move_spiral(rev, r_wall, p['spiral_time_s'])                      # 비동기 — 도는 동안 힘만 본다
    k, last_th = 0, None
    while not cc.motion_done():
        if log.over_time():
            raise cc.MotionTimeout('wipe_bowl: 나선 시간 초과')
        log.watch('spiral')
        k += 1
        if k % every == 0:                                               # 위치는 가끔만 — 매번 읽으면 로봇이 선다(9/20)
            now = cc.where()
            if _radius(now, log.center) > _R_MIN_MM:                     # 중심 근처에서는 각도가 튄다
                th = math.atan2(now[1] - log.center[1], now[0] - log.center[0])
                if last_th is not None:
                    log.sweep += _wrap(th - last_th)                     # 한 조각이 180° 미만이라 그대로 더하면 풀린다
                last_th = th
        time.sleep(p['sample_s'])
    moved = _radius(cc.where(), log.center)
    _info(f'wipe_bowl 나선 끝: 반지름 {moved:.1f} mm (목표 {r_wall:.1f}) · '
          f'돈 각도 {math.degrees(log.sweep):+.0f}° (목표 {rev * 360:.0f}°) → 벽면은 반대로 돈다')
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
    if log.sweep == 0.0:                                                 # 못 쟀다 — 도는 것부터 확인해야 한다
        _warn('wipe_bowl: 나선이 돈 방향을 재지 못했다 — 벽면을 시계 방향으로 돈다(같은 방향일 수 있다)')
    dth = -math.copysign(2 * math.pi / per, log.sweep or 1.0)            # 🔸 **잰 나선 방향의 반대**
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


def _wrap(rad):
    """각도 차이를 −π~π 로. 조각마다 180° 미만이면 이것을 더해 가는 것만으로 총 회전각이 풀린다."""
    return math.atan2(math.sin(rad), math.cos(rad))


def _scale():
    """실행 인자 vel_scale — 속도를 직접 주는 이동에는 부르는 쪽이 곱한다(cobot_common 약속)."""
    return float(cc.cfg().get('run', {}).get('vel_scale', 1.0))


def wipe_cup() -> WipeCupResult:
    """컵 안을 솔로 닦는다 — F3-03. 코드 OK / FORCE_LIMIT / TIMEOUT / ROBOT_ERROR.

    9/21 확정 시나리오. 괄호 안은 강의자료 근거.
      ① 컵 위 → **바닥 fast_gap_mm 위까지 빠르게** 내려간다
      ② **바닥을 찾는다** — cc.contact_down(순응 ON, 조금씩 하강, insert_limit_n)
         (중급2 "힘 방향과 같은 방향의 모션 불가" — Z 힘제어로는 내려갈 수 없다. 순응 + 걸음 하강이 매뉴얼 방식)
      ③ 바닥을 찾으면 **힘을 풀고**(contact_down 이 해제한다) 살짝 띄운다 — 왕복의 가운데 자리로
      ④⑤ **위아래 왕복 + 좌우 비틀기를 한 명령으로 동시에** — Move Periodic
         (중급1 p.71 "일정한 진폭과 주기로 왕복 **이동/회전** 모션" · p.74 실습 15° 회전 왕복 ·
          p.75 축마다 주기를 달리할 수 있다 / 🚨 진폭을 준 축은 주기도 줘야 한다 — 오류 2.1218)
      ⑥ cycles 회가 끝나면 가운데로 돌아온다 → **아래쪽 끝으로 내려서 끝낸다**(사용자 시나리오 6)
      ⑦ safe_retreat — 솔을 컵에서 곧게 뽑는다. HOME 복귀는 flow 가 부른다

    🚨 그릇(고정 좌표, 결정 E6)과 달리 컵은 **바닥을 힘으로 찾는다** — 컵이 깊고(95 mm) 솔이 단단해
       높이가 어긋나면 바로 세게 박히고, 그릇과 달리 물러서 완충해 줄 것이 없다.
    🔸 솔 세척부 길이 = 컵 내부 높이(둘 다 95 mm, CELL-02a) → 바닥에 닿으면 세척부가 통째로 들어가고
       그리퍼 끝은 컵 입구와 나란하다. 그래서 **삽입 깊이는 솔 길이 기준으로 센다**(내려온 거리가 아니다).
    🚨 왕복은 **순응·힘제어를 끈 상태**로 한다(시나리오 3 "힘 풀기") — 명령한 진폭이 실제 진폭이어야 한다.
       안전은 힘 감시가 맡는다: 누르는 힘 limit_n · 옆 힘 lateral_max_n · duration_s · 힘 로그.
    진폭·비틀기 각·주기는 V-10(실기)에서 확정한다.
    """
    p = cc.cfg()['f3']['wipe_cup']
    limits = cc.cfg()['cell']['limits']
    t0 = time.monotonic()
    log = _Log(p, t0)
    code, depth = ROBOT_ERROR, 0.0
    try:
        _halt_check('컵 닦는 자리 이동')
        up = cc.move_to(STATION_CUP, carrying=True, point='wash')
        log.start(cc.read_force())                                       # 공중 기준값은 내려가기 전에
        z_top = cc.where()[2]
        gap = float(p['fast_gap_mm'])
        if up - gap > 0:
            cc.move_rel(0.0, 0.0, -(up - gap), 'BASE')                   # ① 바닥 gap 위까지 빠르게
        found, _f = cc.contact_down(float(p['find_max_mm']), limits['insert_limit_n'])   # ② 바닥 찾기
        log.center = cc.where()
        # 🔸 삽입 깊이 = **솔이 컵 안에 들어간 길이**다 — 접근점에서 내려온 거리가 아니다(컵 위 빈 공간이 섞인다).
        #    솔 세척부 길이 = 컵 내부 높이 이므로(CELL-02a), 바닥에 닿으면 세척부가 통째로 들어간 것이고
        #    gap 을 다 내려가기 전에 막혔으면 그만큼 덜 들어간 것이다.
        depth = max(0.0, float(p['tool']['clean_h_mm']) - (gap - found))
        _info(f'wipe_cup 바닥: 솔이 {depth:.1f} mm 들어갔다 (찾기 구간 {found:.1f} / {gap:g} mm) '
              f'· 실제 Z {log.center[2]:.1f} mm (접근점에서 {z_top - log.center[2]:.1f} mm 하강)')
        if found >= float(p['find_max_mm']) - 0.5:                       # 끝까지 내려가도 바닥이 없다
            raise RuntimeError(f'wipe_cup: {p["find_max_mm"]:g} mm 를 내려가도 바닥을 못 찾았다 — 컵·좌표 확인')
        if depth < float(p['insert_min_mm']):                            # 바닥에 닿기 전에 막혔다
            raise cc.ForceLimitError(f'wipe_cup: 솔이 {depth:.1f} mm 밖에 못 들어갔다 '
                                     f'(최소 {p["insert_min_mm"]:g} mm) — 컵이 제자리인지·솔에 걸리는 것이 없는지 확인')
        _scrub_cup(p, log, depth)                                        # ③④⑤⑥
        code = OK
    except cc.MotionHalted:
        raise
    except cc.ForceLimitError:
        code = FORCE_LIMIT
    except (cc.MotionTimeout, cc.MoveTimeout):
        code = TIMEOUT
    except (RuntimeError, ValueError, KeyError):
        code = ROBOT_ERROR
    finally:
        _off_and_retreat()                                               # ⑦ 힘 끄고 컵 밖으로 곧게
    return WipeCupResult(ok=(code == OK), code=code, force_log_path=log.save(),
                         duration_s=time.monotonic() - t0, insert_depth_mm=depth)


def _scrub_cup(p, log, depth):
    """③ 살짝 띄우고 → ④⑤ 위아래 왕복 + 좌우 비틀기를 **한 명령으로 동시에**(Move Periodic) → ⑥ 아래에서 끝낸다.

    진폭은 편진폭이라 왕복 한 번에 위아래로 2 × stroke 를 움직인다(중급1 p.71 그림).
    가운데를 바닥 + lift + stroke 에 두면 **가장 낮은 자리가 바닥 + lift** 가 된다 — 바닥을 찧지 않는다.
    """
    lift = float(p['lift_mm'])
    # 왕복의 꼭대기에서도 솔이 keep_in_mm 만큼은 컵 안에 남아야 한다. 꼭대기 = 바닥에서 lift + 2 × stroke.
    room = max(0.0, depth - lift - float(p['keep_in_mm']))               # depth = 지금 컵 안에 들어가 있는 솔 길이
    stroke = min(float(p['stroke_mm']), room / 2.0)
    if stroke <= 0:
        raise RuntimeError(f'wipe_cup: 깊이 {depth:.1f} mm 로는 왕복할 자리가 없다 — 좌표·설정 확인')
    _halt_check('왕복 문지르기')
    cc.move_rel(0.0, 0.0, lift + stroke, 'BASE',                         # ③ 왕복의 가운데로
                vel_mm_s=float(p['lift_vel_mm_s']) * _scale())
    log.watch('cup-lift')
    period = float(p['period_s'])
    cc.move_periodic([0.0, 0.0, stroke, 0.0, 0.0, float(p['twist_deg'])],    # ④⑤ z 왕복 + rz 비틀기 동시
                     [0.0, 0.0, period, 0.0, 0.0, period * float(p['twist_period_ratio'])],
                     repeat=int(p['cycles']), ref='TOOL')
    _info(f'wipe_cup 문지르기: 위아래 ±{stroke:.0f} mm · 비틀기 ±{p["twist_deg"]:g}° · '
          f'주기 {period:g} s · {p["cycles"]} 회 (Move Periodic 한 명령)')
    while not cc.motion_done():                                          # 도는 동안 힘만 본다
        if log.over_time():
            raise cc.MotionTimeout('wipe_cup: 문지르기 시간 초과')
        log.watch('cup-scrub')
        time.sleep(p['sample_s'])
    cc.move_rel(0.0, 0.0, -stroke, 'BASE',                               # ⑥ 위 말고 **아래**에서 끝낸다
                vel_mm_s=float(p['lift_vel_mm_s']) * _scale())
    log.watch('cup-end')


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
