"""F3 접촉 닦기 — 박진용 (IRD v3.0 §5, SDD §5.4).

flow_node(메인 프로그램)나 test/rig_f3.py 가 cobot_common.init() 뒤 **메인 스레드**에서 부르는
평범한 함수다(SDD §3.2). 이름·인자·반환은 cobot_api.F3Api 그대로이고, 실패는 예외가 아니라
Result.fail(code) 로 돌려준다. 숫자는 전부 params.yaml 의 f3 절 · cell.yaml 에서 읽는다(AGENTS 규칙 6).

시작 전제: 용기는 스펀지 홈에 안착돼 있고(F1 place) 툴을 쥔 상태(F1 tool PICK).
🔸 닦기(wipe_bowl·wipe_cup)는 **언제나 초기자세 HOME(관절 0·0·90·0·90·0)에서 시작해 HOME 으로 끝난다**(박진용 9/21).
   그릇은 HOME 바로 아래라 그 자리에서 내려가고, 컵은 HOME 에서 z +40 → y +140 → z −40 으로 컵 위에 간다.
   돌아올 때는 곧게 올린 뒤 그 반대로 — 초기자세 높이에서 옆으로 바로 가면 솔이 컵에 걸린다.
끝난 뒤: 툴을 쥔 채 HOME. 툴 반납·재파지는 flow 가 F1 을 부른다.

🔸 툴 파지 기준(9/20 확정): 수세미·솔 모두 세척부 위에 손잡이가 있고, **그리퍼 끝을 세척부 윗면에 닿게** 쥔다
   → 그리퍼 끝에서 툴 끝까지 = 세척부 높이 = params.yaml 의 f3.wipe_bowl.tool.clean_h_mm(수세미 35) · f3.wipe_cup.tool.clean_h_mm(솔 95).
   빠른 하강 길이(fast_down_mm, 9/21 실측)·닦는 반경은 params.yaml 에서 읽는다 — 길이를 코드에 적지 않는다. 바닥은 힘으로 찾는다.

wipe_bowl = F3-02 **고정 좌표 방식**(9/20 결정 E6 · SDD §5.4) · soap · wipe_cup = F3-03.
🔸 그릇만 고정 좌표다 — 컵은 깊고 솔이 단단해 **삽입만 힘으로 찾는다**(contact_down), 문지르기는 위치 제어다.
🔸 두산 함수를 직접 부르지 않는다(AGENTS §3 규칙 4) — 나선·원호를 포함한 접촉 모션은 cobot_common 의 force.py 에 있다
   (cc.move_spiral · cc.move_arc · cc.move_line · cc.where · cc.motion_done).
실측 근거는 docs/test_logs/20260918_CELL-02a_용기치수측정.md · docs/test_logs/20260919_V-03_힘제어중_XY이동.md.
"""
import csv
import math
import os
import time

import cobot_common as cc
from cobot_api import FORCE_LIMIT, OK, ROBOT_ERROR, TIMEOUT, Result, WipeBowlResult, WipeCupResult

START = 'HOME'                       # 닦기의 시작·끝 = 초기자세 (cell.stations.HOME, 관절 0·0·90·0·90·0)

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
    code, moved = ROBOT_ERROR, True
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
    except (cc.MotionHalted, cc.MoveIncomplete):                         # 로봇 위치를 모른다 → 올린다
        moved = False
        raise
    except (cc.MotionTimeout, cc.MoveTimeout):
        code = TIMEOUT
    except (RuntimeError, ValueError, KeyError):
        code = ROBOT_ERROR
    finally:
        _off_and_retreat(moved)
    return Result(ok=(code == OK), code=code)


def wipe_bowl() -> WipeBowlResult:
    """그릇 안쪽을 수세미로 닦는다 — F3-02. 코드 OK / FORCE_LIMIT / TIMEOUT / ROBOT_ERROR.

    **9/20 실기(V-03)로 확정한 절차 그대로**다(rig_v03.py · docs/test_logs/20260919_V-03_*). 괄호 안은 강의자료 근거.
      ① 초기자세 HOME(그릇 바로 위) → fast_down_mm 빠르게 내려간 뒤 **바닥을 힘으로 찾는다**(cc.contact_down)
      ② **순응 ON** — 바닥을 찾은 그 자리에서. 더 누르지 않는다 (중급2: 목표 TCP 근처에서 켜는 것을 권장)
      ③ 바닥: **나선 한 번** — 중심에서 벽 반지름까지, 좌우 비틀기 없음, **힘제어는 켜지 않는다**
         (중급2 "힘 방향과 같은 방향의 모션 불가" — 나선은 툴 Z 축 모션이라 Z 힘제어와 같은 축이다.
          9/20 실기: 켜 두면 반환은 0 인데 나선이 시작조차 하지 않았다)
         (중급1 p.69 나선은 **시간**으로 속도 지정 · 반경 대비 회전 수가 과하면 시작조차 하지 않는다)
      ④ **힘제어 ON** — Z 로 target_force_n 유지. 공중 기준값(센서 치우침·툴 무게)을 더해서 명령한다
      ⑤ 벽면: 원호를 이어 붙여 **반대 방향 turns 바퀴** + 손목(6번 축) ±twist_deg 좌우 비틀기
         (이동이 X·Y 라 Z 힘제어와 함께 쓸 수 있다 — 중급2 폴리싱 예시)
         (중급1 p.79 중첩 가능한 모션은 Move L·C·J·JX — radius 를 줘야 멈추지 않고 이어진다)
      ⑥ **힘제어만 OFF**(순응은 유지) → ⑦ 올리지 않고 그 높이에서 중심 복귀 → 순응 OFF → 곧게 올려 HOME

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
    trip = _Trip([])                                                     # 그릇은 HOME 바로 아래 — 옆으로 갈 것이 없다
    code, moved = ROBOT_ERROR, True                                      # moved=False → 정리할 때 로봇을 움직이지 않는다
    try:
        _halt_check('그릇 닦기 시작')
        trip.go()                                                        # HOME
        _descend(p, log)                                                 # ① 빠른 하강 → 바닥 찾기
        cc.compliance_on()                                               # ② 순응 ON (찾은 자리 그대로)
        _spiral(p, log)                                                  # ③ 바닥 나선 (힘제어 없이)
        log.target = float(p['target_force_n'])
        cc.force_on('z', log.target + abs(log.base[2]), p['limit_n'])    # ④ 힘제어 ON (공중 기준값 보정)
        _wall_laps(p, log)                                               # ⑤ 벽면 turns 바퀴
        cc.force_release()                                               # ⑥ 힘제어만 OFF (순응은 유지)
        log.target = 0.0
        _to_center(p, log)                                               # ⑦ 그 높이에서 중심으로
        code = OK
    except (cc.MotionHalted, cc.MoveIncomplete):                         # 로봇 위치를 모른다 → 코드로 바꾸지 않고 올린다
        moved = False                                                    # (결정 E11 · MoveIncomplete 약속 — motion.py)
        raise
    except cc.ForceLimitError:
        code = FORCE_LIMIT
    except (cc.MotionTimeout, cc.MoveTimeout):
        code = TIMEOUT
    except (RuntimeError, ValueError, KeyError):
        code = ROBOT_ERROR
    finally:
        trip.back(moved)                                                 # 힘을 끄고, 위치를 알 때만 곧게 올려 HOME
    return WipeBowlResult(ok=(code == OK), code=code, force_log_path=log.save(),
                          duration_s=time.monotonic() - t0, force_mean_n=log.mean())


def _off_and_retreat(move=True):
    """힘·순응을 끄고(움직이지 않는다) → move 면 안전 높이까지 올린다 (AGENTS §4). 하나가 실패해도 다음을 시도한다.

    🚨 move=False 는 **로봇이 어디 있는지 모를 때**다(MoveIncomplete · 강제정지).
       9/21 08:40 실기에서 6번 관절이 163° 돌아 케이블이 꼬인 채 로봇이 섰는데, 그 상태에서 도구가
       자동으로 HOME 으로 가려 했다(F4 가 rig_coords 에서 발견). 꼬인 채 움직이면 더 꼬이거나 부딪힌다.
       힘·순응 해제는 모션이 아니라서 어느 경우에도 한다.
    """
    steps = [cc.force_off] + ([cc.safe_retreat] if move else [])
    for step in steps:
        try:
            step()
        except Exception:                                                # noqa: BLE001 — 복구는 끝까지
            _warn(f'정리 실패: {step.__name__} — 눈으로 확인')
    if not move:
        _warn('🚨 로봇이 어디 있는지 모른다 → 힘만 끄고 **움직이지 않았다**. '
              '티치펜던트로 상태를 확인하고 사람이 복구한다')


def cup_hops(p):
    """HOME → 컵 위 상대 이동 [(dx, dy, dz), ...] (BASE). 올라가서 옆으로 가서 내려온다 — 솔이 컵에 걸리지 않게."""
    up, dy = float(p['over_cup_up_mm']), float(p['over_cup_dy_mm'])
    return [(0.0, 0.0, up), (0.0, dy, 0.0), (0.0, 0.0, -up)]


class _Trip:
    """초기자세 HOME ↔ 닦는 자리 오가기. go() 로 가고, back() 으로 **간 만큼만** 거꾸로 돌아온다.

    back: 힘·순응 끄기(언제나) → 닦는 자리에 닿았으면 그 높이까지 **곧게** 올린다(툴을 용기에서 뽑는다)
          → 간 이동을 거꾸로 → HOME(관절). 🚨 move=False(로봇 위치를 모름, 결정 E11)면 힘만 끄고 움직이지 않는다.
    """

    def __init__(self, hops):
        self.hops, self.done, self.spot_z = list(hops), [], None

    def go(self):
        cc.move_to(START, carrying=True)
        for hop in self.hops:
            cc.move_rel(*hop, 'BASE')
            self.done.append(hop)
        self.spot_z = cc.where()[2]                                      # 닦는 자리 위 높이 — 돌아올 때 여기까지 곧게 올린다

    def back(self, move=True):
        try:
            cc.force_off()
        except Exception:                                                # noqa: BLE001 — 복구는 끝까지
            _warn('정리 실패: force_off — 눈으로 확인')
        if not move:
            _warn('🚨 로봇이 어디 있는지 모른다 → 힘만 끄고 **움직이지 않았다**. '
                  '티치펜던트로 상태를 확인하고 사람이 복구한다')
            return
        try:
            if self.spot_z is not None:
                rise = self.spot_z - cc.where()[2]
                if rise > 0:
                    cc.move_rel(0.0, 0.0, rise, 'BASE')                  # 용기에서 곧게 뽑는다
            for dx, dy, dz in reversed(self.done):
                cc.move_rel(-dx, -dy, -dz, 'BASE')
            cc.move_to(START, carrying=True)
        except Exception:                                                # noqa: BLE001
            _warn('정리 실패: HOME 복귀 — 눈으로 확인')


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

    빠른 하강은 초기자세 HOME 에서 **fast_down_mm 만큼**(9/21 실측 145 mm − 10). 바닥 위치는 미리 정하지 않는다 —
       나머지는 힘으로 찾는다(접촉 깊이가 실행마다 12~17 mm 로 달랐다, 9/20).
    바닥 찾기는 cc.contact_down — 순응을 켜고 cell.force.contact_step_mm 씩 내려가며
    **시작 힘 대비** cell.limits.contact_limit_n 만큼 힘이 커지면 멈춘다(공중 치우침 1.4~2.4 N 때문에 절대값으로 보면 안 된다).
    찾은 자리에서 더 누르지 않는다. contact_down 이 끝나며 순응을 꺼 주므로 닦기는 위치 제어로 이어진다.
    """
    log.start(cc.read_force())                                           # 공중 기준값은 **내려가기 전에** 잰다
    fast = float(p['fast_down_mm'])                                      # ① 빠르게 (정한 길이만큼)
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
    r_seen = _radius(cc.where(), log.center)                             # (바깥 함수의 moved 와 헷갈리지 않게 다른 이름)
    _info(f'wipe_bowl 나선 끝: 반지름 {r_seen:.1f} mm (목표 {r_wall:.1f}) · '
          f'돈 각도 {math.degrees(log.sweep):+.0f}° (목표 {rev * 360:.0f}°) → 벽면은 반대로 돈다')
    if r_seen < r_wall * 0.5:                                            # 명령은 받았는데 돌지 않았다(9/20 실기 증상)
        raise RuntimeError(f'나선이 돌지 않았다(실제 {r_seen:.1f} mm / 목표 {r_wall:.1f} mm) — '
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
      ⓪ 초기자세 HOME → z +over_cup_up_mm → y +over_cup_dy_mm → z −over_cup_up_mm (컵 위, 솔이 컵에 걸리지 않게)
      ① 거기서 **fast_down_mm 만큼 빠르게** 내려간다(9/21 실측 90 mm − 10). 바닥 위치는 미리 정하지 않는다
      ② **바닥을 찾는다** — cc.contact_down(순응 ON, 조금씩 하강, f3.wipe_cup.find_limit_n 5 N — 15 N 이면 컵이 눌렸다)
         (중급2 "힘 방향과 같은 방향의 모션 불가" — Z 힘제어로는 내려갈 수 없다. 순응 + 걸음 하강이 매뉴얼 방식)
      ③ 바닥을 찾으면 **힘을 풀고**(contact_down 이 해제한다) 세척의 가운데(바닥 + lift + stroke)로 띄운다
      ④⑤ **Move Periodic 한 명령**으로 위아래 ±20 mm 와 6번 축 ±180° 를 같은 주기로 — 오르내릴 때마다 6번 축 360°
         (중급1 p.71 "왕복 이동/회전" · 🚨 회전은 rx 칸 = 6번 축, rz 칸은 4번 축이라 손목이 기운다 — 9/21 Virtual)
         🚨 Move Periodic 의 회전 진폭은 쓰지 않는다 — 9/21 Virtual 에서 툴 축이 아니라 4번 축이 돌아 손목이 기울었다
      ⑥ cycles(3) 번 뒤 가운데로 돌아오면(6번 축도 제자리) **아래쪽 끝으로 내려서** 끝낸다
      ⑦ 솔을 컵에서 곧게 뽑아 컵 위 높이로 → z +40 → y −140 → z −40 → HOME (⓪ 의 반대)

    🚨 그릇(고정 좌표, 결정 E6)과 달리 컵은 **바닥을 힘으로 찾는다** — 컵이 깊고(95 mm) 솔이 단단해
       높이가 어긋나면 바로 세게 박히고, 그릇과 달리 물러서 완충해 줄 것이 없다.
    🔸 솔 세척부 길이 = 컵 내부 높이(둘 다 95 mm, CELL-02a) → 바닥에 닿으면 세척부가 통째로 들어가고
       그리퍼 끝은 컵 입구와 나란하다 → 왕복 진폭은 솔 길이 기준으로 줄인다. 돌려주는 insert_depth_mm 은
       **컵 위에서 바닥까지 내려간 거리**(빠른 하강 + 찾기)다 — 잰 값이다.
    🚨 왕복은 **순응·힘제어를 끈 상태**로 한다(시나리오 3 "힘 풀기") — 명령한 진폭이 실제 진폭이어야 한다.
       안전은 힘 감시가 맡는다: 누르는 힘 limit_n · 옆 힘 lateral_max_n · duration_s · 힘 로그.
    위아래 40 mm(stroke 20 × 2) · 360° 회전 3 회는 9/21 박진용 확정(비틀기 ±18° 에서 바꿈). 속도는 V-10(실기)에서 본다.
    """
    p = cc.cfg()['f3']['wipe_cup']
    t0 = time.monotonic()
    log = _Log(p, t0)
    trip = _Trip(cup_hops(p))
    code, depth, moved = ROBOT_ERROR, 0.0, True
    try:
        _halt_check('컵 닦기 시작')
        trip.go()                                                        # ⓪ HOME → 컵 위
        log.start(cc.read_force())                                       # 공중 기준값은 내려가기 전에
        fast = float(p['fast_down_mm'])
        cc.move_rel(0.0, 0.0, -fast, 'BASE')                             # ① 정한 길이만큼 빠르게
        found, _f = cc.contact_down(float(p['find_max_mm']), float(p['find_limit_n']))   # ② 바닥 찾기 (컵 전용 힘)
        log.center = cc.where()
        depth = fast + found                                             # 컵 위에서 바닥까지 내려간 거리 (잰 값)
        _info(f'wipe_cup 바닥: 빠르게 {fast:.0f} mm + 찾기 {found:.1f} mm (최대 {p["find_max_mm"]:g}) '
              f'= {depth:.1f} mm · 실제 Z {log.center[2]:.1f} mm')
        if found >= float(p['find_max_mm']) - 0.5:                       # 끝까지 내려가도 바닥이 없다
            raise RuntimeError(f'wipe_cup: {p["find_max_mm"]:g} mm 를 내려가도 바닥을 못 찾았다 — 컵·좌표 확인')
        _scrub_cup(p, log)                                               # ③④⑤⑥
        code = OK
    except (cc.MotionHalted, cc.MoveIncomplete):                         # 로봇 위치를 모른다 → 올린다
        moved = False
        raise
    except cc.ForceLimitError:
        code = FORCE_LIMIT
    except (cc.MotionTimeout, cc.MoveTimeout):
        code = TIMEOUT
    except (RuntimeError, ValueError, KeyError):
        code = ROBOT_ERROR
    finally:
        trip.back(moved)                                                 # ⑦ 힘 끄고, 위치를 알 때만 곧게 뽑아 ⓪ 의 반대로 HOME
    return WipeCupResult(ok=(code == OK), code=code, force_log_path=log.save(),
                         duration_s=time.monotonic() - t0, insert_depth_mm=depth)


def cup_stroke(p):
    """위아래 편진폭(mm). 꼭대기(바닥 + lift + 2 × stroke)에서도 솔이 keep_in_mm 은 컵 안에 남게 줄인다.

    바닥에서는 솔 세척부가 통째로 컵 안에 있다(솔 95 = 컵 깊이 95, CELL-02a) → 들어간 길이 = clean_h_mm.
    """
    room = max(0.0, float(p['tool']['clean_h_mm']) - float(p['lift_mm']) - float(p['keep_in_mm']))
    return min(float(p['stroke_mm']), room / 2.0)


def spin_room(j6, p):
    """6번 축이 시작 각 ± spin_deg/2 를 돌아도 한계(±j6_limit − margin) 안인가. 아니면 ValueError — 돌지 않는다."""
    half, lim = float(p['spin_deg']) / 2.0, float(p['j6_limit_deg']) - float(p['j6_margin_deg'])
    if abs(j6) + half > lim:
        raise ValueError(f'wipe_cup: 6번 축 {j6:.1f}° 에서 ±{half:g}° 를 돌면 한계(±{lim:g}°)를 넘는다 — 돌지 않는다')


def cup_periodic(p, stroke):
    """세척 한 명령의 (진폭, 주기) — [x, y, z, rx, ry, rz]. 위아래 ±stroke · 6번 축 ±spin/2 를 같은 주기로.

    🚨 회전은 **rx 칸** — 이 드라이버에서 rx 칸이 6번 축, rz 칸은 4번 축이다(9/21 Virtual, force.move_periodic 주석).
    """
    t = float(p['period_s'])
    return ([0.0, 0.0, float(stroke), float(p['spin_deg']) / 2.0, 0.0, 0.0],
            [0.0, 0.0, t, t, 0.0, 0.0])


def _scrub_cup(p, log):
    """③ 세척의 가운데(바닥 + lift + stroke)로 띄우고 → ④⑤ Move Periodic 한 명령(위아래 + 6번 축 360°) × cycles
    → ⑥ 아래쪽 끝(바닥 + lift)으로 내려서 끝낸다. 6번 축은 한 주기가 끝나면 제자리로 돌아온다.

    툴 기준 +z 는 아래라, 가운데에서 **내려가며 한 방향 · 올라가며 반대로** 돈다(사인 곡선 — 끊김 없음).
    도는 동안은 힘만 본다(위치를 읽지 않는다). 세척 속도(period_s)는 vel_scale 예외(결정 E17).
    """
    stroke = cup_stroke(p)
    if stroke <= 0:
        raise RuntimeError('wipe_cup: 솔 길이로는 왕복할 자리가 없다 — f3.wipe_cup 설정 확인')
    _halt_check('세척')
    cc.move_rel(0.0, 0.0, float(p['lift_mm']) + stroke, 'BASE',          # ③ 세척의 가운데로
                vel_mm_s=float(p['lift_vel_mm_s']) * _scale())
    log.watch('cup-lift')
    j6 = cc.joints()[5]
    spin_room(j6, p)
    amp, period = cup_periodic(p, stroke)
    cc.move_periodic(amp, period, repeat=int(p['cycles']), ref='TOOL', scale=False)
    _info(f'wipe_cup 세척: 위아래 {2 * stroke:.0f} mm · 6번 축 {p["spin_deg"]:g}° 씩 오르내리며 · 주기 {p["period_s"]:g} s '
          f'· {p["cycles"]} 회 (Move Periodic 한 명령 · 6번 축 {j6:.1f}° 에서 시작)')
    while not cc.motion_done():                                          # ④⑤ 도는 동안 힘만 본다
        if log.over_time():
            raise cc.MotionTimeout('wipe_cup: 세척 시간 초과')
        log.watch('cup-scrub')
        time.sleep(float(p['sample_s']))
    end = cc.joints()[5]
    if abs(end - j6) > 5.0:
        _warn(f'wipe_cup: 끝난 뒤 6번 축 {end:.1f}° — 시작 {j6:.1f}° 로 돌아오지 않았다. 케이블 확인')
    cc.move_rel(0.0, 0.0, -stroke, 'BASE',                               # ⑥ 아래쪽 끝에서 끝낸다
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
