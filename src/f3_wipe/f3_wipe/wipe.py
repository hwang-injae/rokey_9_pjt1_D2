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
   (cc.move_spiral · cc.move_arc · cc.move_periodic · cc.where · cc.joints · cc.motion_done · cc.stop_now).
실측 근거는 docs/test_logs/20260918_CELL-02a_용기치수측정.md · docs/test_logs/20260919_V-03_힘제어중_XY이동.md.
"""
import csv
import math
import os
import time

import cobot_common as cc
from cobot_api import FORCE_LIMIT, OK, ROBOT_ERROR, TIMEOUT, Result, WipeBowlResult, WipeCupResult

class JointGuardStop(RuntimeError):
    """컵 세척 중 1·4번 조인트가 움직여 즉시 정지했다 — 손목이 이미 꺾였을 수 있어 **자동으로 움직이지 않는다**(PR #56 리뷰)."""


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
    trip = _Trip([], p)                                                  # 그릇은 HOME 바로 아래 — 옆으로 갈 것이 없다
    code, moved = ROBOT_ERROR, True                                      # moved=False → 정리할 때 로봇을 움직이지 않는다
    try:
        _halt_check('그릇 닦기 시작')
        _bowl_home(p)                                                    # HOME — rig_v03 속도 (공용 이동 함수 안 씀)
        trip.started, trip.spot_z = True, cc.where()[2]                  #   곧게 올라올 높이 = HOME 높이
        _descend(p, log)                                                 # ① 빠른 하강 → 바닥 찾기
        cc.compliance_on()                                               # ② 순응 ON (찾은 자리 그대로)
        _hold_contact_z(p, log)                                          #    순응을 켜며 밀린 만큼 찾은 높이로 되돌린다(rig_v03 그대로)
        log.center = cc.where()                                          #    나선·벽면의 중심 = 순응 켠 뒤 자리 (rig_v03 set_frame)
        _spiral(p, log)                                                  # ③ 바닥 나선 (힘제어 없이)
        log.target = float(p['target_force_n'])
        cc.force_on('z', log.target + abs(log.base[2]), p['limit_n'])    # ④ 힘제어 ON (공중 기준값 보정)
        _wall_laps(p, log)                                               # ⑤ 벽면 turns 바퀴
        cc.force_release()                                               # ⑥ 힘제어만 OFF (순응은 유지)
        log.target = 0.0
        _to_center(p, log)                                               # ⑦ 그 높이에서 중심으로
        code = OK
    except (cc.MotionHalted, cc.MoveIncomplete):                         # 코드로 바꾸지 않고 올린다 (결정 E11)
        raise                                                            # 🔸 그래도 rig_v03 처럼 **올라와 HOME** 으로 간다(박진용 9/21)
    except cc.ForceLimitError:
        code = FORCE_LIMIT
    except (cc.MotionTimeout, cc.MoveTimeout):
        code = TIMEOUT
    except (RuntimeError, ValueError, KeyError):
        code = ROBOT_ERROR
    finally:
        if moved and trip.spot_z is not None:                            # 곧게 올라오기 = rig_v03 safe_retreat 속도 (힘 끄고 먼저 올린다)
            try:
                cc.force_off()
                rise = trip.spot_z - cc.where()[2]
                if rise > 0:
                    _bowl_rise(rise)
                _bowl_home(p)                                            # HOME — rig_v03 속도
                trip.started = False                                     #   trip.back 은 힘만 끈다(이미 HOME)
            except Exception:                                            # noqa: BLE001 — 복구는 끝까지, 나머지는 trip.back 이
                _warn('정리 실패: 곧게 올라오기·HOME — 눈으로 확인')
        trip.back(moved)                                                 # 힘을 끄고, (실패로 남았으면) 남은 만큼 올려 HOME
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


def _fast_z(p, dz):
    """빠른 하강 · 곧게 올라오기 — Move L 상대(BASE z). 속도·가속도는 f3.wipe_*.fast_vel_mm_s · fast_acc_mm_s2 (× vel_scale).
    그릇과 컵이 **같은 값**이어야 한다(박진용 9/21) — test_fast_z_same_for_bowl_and_cup 이 본다."""
    cc.move_rel(0.0, 0.0, float(dz), 'BASE',
                vel_mm_s=float(p['fast_vel_mm_s']) * _scale(), acc_mm_s2=float(p['fast_acc_mm_s2']) * _scale())


class _Trip:
    """초기자세 HOME ↔ 닦는 자리 오가기. go() 로 가고, back() 으로 **간 만큼만** 거꾸로 돌아온다.

    back: 힘·순응 끄기(언제나) → 닦는 자리에 닿았으면 그 높이까지 **곧게** 올린다(툴을 용기에서 뽑는다)
          → 간 이동을 거꾸로 → HOME(관절). 🚨 move=False(로봇 위치를 모름, 결정 E11)면 힘만 끄고 움직이지 않는다.
    """

    def __init__(self, hops, p):
        self.hops, self.done, self.spot_z, self.started = list(hops), [], None, False
        self.p = p

    def go(self):
        self.started = True
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
        if not self.started:                                             # 움직이기 전에 멈췄다 — 돌아갈 것이 없다
            return
        try:
            if self.spot_z is not None:
                rise = self.spot_z - cc.where()[2]
                if rise > 0:
                    _fast_z(self.p, rise)                                # 용기에서 곧게 뽑는다 — 빠른 하강과 같은 속도
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
    """HOME → 빠르게 fast_down_mm → 공중 기준값 → **바닥을 힘으로 찾는다**. 🔸 9/20 실기 rig_v03 과 같은 명령·같은 값(박진용 9/21).

    rig_v03: move_z(−approach_down_mm, 200 × vel_scale, 가속 200 그대로) → zero()(공중 힘 5 번) → |Fz| > 3 N 이면 중단
             → contact_down(30 mm, 2 N, 시간 상한 40 s) → 바닥을 못 찾으면 순응을 켜지 않고 중단.
    바닥 위치는 미리 정하지 않는다 — 나머지는 힘으로 찾는다(접촉 깊이가 실행마다 달랐다, 9/20).
    """
    fast = float(p['fast_down_mm'])                                      # ① 빠르게 (정한 길이만큼)
    if fast > 0:
        cc.move_rel(0.0, 0.0, -fast, 'BASE', vel_mm_s=float(p['fast_vel_mm_s']) * _scale(),
                    acc_mm_s2=float(p['fast_acc_mm_s2']))                # 가속도는 vel_scale 을 안 곱한다(rig_v03)
    log.start(_air_force())                                              # 공중 기준값 — 멈춘 자리에서 5 번 (rig_v03 zero)
    if abs(log.base[2]) > float(p['air_force_max_n']):
        raise RuntimeError(f'wipe_bowl: 빠른 하강 뒤 공중 |Fz| {abs(log.base[2]):.1f} N > {p["air_force_max_n"]:g} N '
                           '— 툴 무게·접촉 확인')
    depth, f = _find_bottom(p, log)                                      # ② 나머지는 힘으로 (내려가는 도중에 계속 본다)
    log.center = cc.where()
    _info(f'wipe_bowl 바닥: 빠르게 {fast:.0f} mm + 찾기 {depth:.1f} mm (최대 {p["find_max_mm"]:g}) '
          f'· 접촉 힘 {f:.1f} N · 실제 Z {log.center[2]:.1f} mm · 공중 기준 Fz {log.base[2]:.1f} N')
    if depth >= float(p['find_max_mm']) - 0.5:                           # 끝까지 내려가도 바닥이 없다
        raise RuntimeError(f'wipe_bowl: {p["find_max_mm"]:g} mm 를 내려가도 바닥을 못 찾았다 — 그릇·좌표 확인')


def _bowl_home(p):
    """HOME(cell.stations.HOME 관절값)으로 Move J — rig_v03 과 같은 속도 home_vel_deg_s × vel_scale · 가속 home_acc_deg_s2 그대로."""
    cc.move_joints(cc.cfg()['cell']['stations'][START]['posj'], float(p['home_vel_deg_s']), float(p['home_acc_deg_s2']))


def _find_bottom(p, log):
    """그릇 바닥 찾기 — 순응 ON 으로 find_max_mm 까지 **한 번에 천천히** 내려가며 힘을 **계속** 읽다가,
    공중 기준 대비 find_limit_n(3 N)을 넘는 **그 순간** 즉시 정지(cc.stop_now) → 순응 OFF → (내려간 거리, 힘).

    🔸 컵 세척 감시와 같은 방식(비동기로 움직이며 보다가 멈춘다 — 박진용 9/21).
       예전 cc.contact_down 은 3 mm 걸음 **끝에서만** 힘을 봐서, 수세미가 한 걸음 사이에 6~7 N 까지 눌린 뒤에야 멈췄다
       → 그렇게 눌린 채로는 나선이 시작하지 않았다(9/21 실기 4 회). 컵은 그대로 cc.contact_down 을 쓴다.
    끝까지 가도 못 찾으면 depth ≈ find_max_mm 로 돌려준다(부르는 쪽이 판정). 누르는 힘이 limit_n 을 넘으면 ForceLimitError.
    """
    f_lim, f_max = float(p['find_limit_n']), float(p['limit_n'])
    timeout = float(p['contact_timeout_s'])
    z0 = cc.where()[2]
    cc.compliance_on()
    f = 0.0
    try:
        cc.start_line_rel(0.0, 0.0, -float(p['find_max_mm']), float(p['find_vel_mm_s']), float(p['find_acc_mm_s2']))
        t0 = time.monotonic()
        while True:
            f = abs(cc.read_force()[2] - log.base[2])
            if f >= f_lim:
                cc.stop_now()                                            # 🔸 넘는 순간 그 자리에서
                break
            if f > f_max:
                cc.stop_now()
                raise cc.ForceLimitError(f'wipe_bowl 바닥 찾기: 누르는 힘 {f:.1f} N > {f_max:g} N')
            if cc.motion_done():                                         # 끝까지 갔다 = 못 찾음
                break
            if time.monotonic() - t0 > timeout:
                cc.stop_now()
                raise cc.MotionTimeout(f'wipe_bowl 바닥 찾기: {timeout:g} s 안에 못 찾았다')
    finally:
        cc.force_off()                                                   # 순응 OFF (contact_down 과 같게 끝낸다)
    return z0 - cc.where()[2], f


def _bowl_rise(dz):
    """그릇에서 곧게 올라오기 — rig_v03 의 safe_retreat 와 같은 속도(cell.force.retreat_vel_mm_s × vel_scale · retreat_acc_mm_s2 그대로)."""
    fc = cc.cfg()['cell']['force']
    cc.move_rel(0.0, 0.0, float(dz), 'BASE', vel_mm_s=float(fc['retreat_vel_mm_s']) * _scale(),
                acc_mm_s2=float(fc['retreat_acc_mm_s2']))


def _air_force(n=5):
    """공중 힘 n 번 평균 [fx, fy, fz, ...] — 빠른 하강 **직후** 바닥 찾기 전에 부른다(9/20 rig_v03 zero() 그대로).

    🚨 9/21 실기: 빠른 하강이 끝나자마자 바닥 찾기를 시작하면 로봇이 서며 흔들리는 중에 기준값을 읽는다
       (공중 기준 −1.0 · 0.7 · 0.1 N 으로 매번 달랐다) → 기준이 틀어져 수세미를 **6~7 N** 까지 누른 뒤에야 바닥으로 봤고,
       그렇게 눌린 채로는 **나선이 시작하지 않았다**(3 회). rig_v03 은 여기서 5 번 읽어 안정시킨 뒤 찾아서 2.7 N · 나선 OK.
    """
    fs = [cc.read_force() for _ in range(int(n))]
    return [sum(v) / len(fs) for v in zip(*fs)]


def _hold_contact_z(p, log):
    """순응을 켜면 로봇이 조금 밀릴 수 있다 → 바닥을 찾은 높이(log.center z)로 명령 위치를 다시 맞춘다(9/20 rig_v03 compliance_on_here 그대로)."""
    dz = log.center[2] - cc.where()[2]
    if abs(dz) > 0.05:
        cc.move_rel(0.0, 0.0, dz, 'BASE', vel_mm_s=float(p['press_vel_mm_s']) * _scale(),
                    acc_mm_s2=float(p['press_acc_mm_s2']))
    _info(f'wipe_bowl 순응 ON · Z {log.center[2]:.1f} (보정 {dz:+.2f} mm)')


def _spiral(p, log):
    """바닥 나선 한 번 — 중심에서 벽 반지름까지, 좌우 비틀기 없음, 힘제어 없음. 🔸 rig_v03 wipe_bottom·sample_spiral 그대로.

    나선 시작(cc.move_spiral 이 시작을 기다린다) → 도는 동안 **매번** 힘과 위치를 읽어 상한을 보고 최대 반지름을 잰다
    → 끝(check_motion 0) · spiral_time_s + 5 s 넘으면 시간 초과 → 최대 반지름이 목표의 절반 미만이면 "돌지 않았다".
    """
    _halt_check('바닥 나선')
    r_wall = log.wall_r()
    rev = max(1.0, round(r_wall / p['spiral_pitch_mm'], 1))
    cx, cy = log.center[0], log.center[1]
    cc.move_spiral(rev, r_wall, p['spiral_time_s'])                      # 비동기 — 시작할 때까지 기다린다
    t0, r_seen = time.monotonic(), 0.0
    while True:
        log.watch('spiral')
        now = cc.where()
        r_seen = max(r_seen, math.hypot(now[0] - cx, now[1] - cy))
        if cc.motion_done():
            break
        if time.monotonic() - t0 > float(p['spiral_time_s']) + 5.0:
            raise cc.MotionTimeout('wipe_bowl: 나선이 끝나지 않는다')
        time.sleep(p['sample_s'])
    _info(f'wipe_bowl 나선 끝: 최대 반지름 {r_seen:.1f} mm (목표 {r_wall:.1f}) · {rev:g} 바퀴 · {p["spiral_time_s"]:g} s')
    if r_seen < r_wall * 0.5:                                            # 명령은 받았는데 돌지 않았다
        raise RuntimeError(f'나선이 돌지 않았다(최대 {r_seen:.1f} mm / 목표 {r_wall:.1f} mm)')


def _wall_laps(p, log):
    """벽면 — 🔸 rig_v03 wipe_wall 그대로: 벽까지 비틀기(+twist)를 넣은 자세로 천천히 붙고 →
    원호(Move C)를 이어 붙여 **베이스에서 시계 방향**(rig_v03 dth < 0) turns 바퀴, 원호마다 손목 ±twist_deg 번갈아 → 다 돌고 기다린다."""
    _halt_check('벽면 회전')
    r = log.wall_r()
    x0, y0, z0, a, b, c = log.center
    now = cc.where()
    dx, dy = now[0] - x0, now[1] - y0
    th0 = math.atan2(dy, dx) if math.hypot(dx, dy) > 1e-6 else 0.0
    per = max(2, int(round(360.0 / p['wall_arc_deg'])))
    n = int(p['turns'] * per)
    dth = -2 * math.pi / per                                             # rig_v03: 나선과 반대 방향으로 본 값 그대로
    chord = 2 * r * abs(math.sin(dth / 2))
    blend = min(float(p['blend_radius_mm']), chord * 0.45)
    lin_acc, rot_acc = float(p['lin_acc_mm_s2']), float(p['rot_acc_deg_s2'])
    tw = float(p['twist_deg'])

    def pose(th, rz):
        return [x0 + r * math.cos(th), y0 + r * math.sin(th), z0, a, b, (c + rz + 180.0) % 360.0 - 180.0]

    cc.wait_done()
    cc.move_pose(pose(th0, tw), p['wall_approach_vel_mm_s'], p['rot_vel_deg_s'], lin_acc, rot_acc)   # 벽으로 천천히
    log.watch('wall')
    twist = 1
    for k in range(n):                                                   # (rig_v03 처럼 전체 시간 상한은 보지 않는다)
        th_mid, th_end = th0 + dth * (k + 0.5), th0 + dth * (k + 1)
        rz_mid = tw * twist
        twist = -twist
        cc.move_arc(pose(th_mid, rz_mid), pose(th_end, tw * twist), p['lin_vel_mm_s'], p['rot_vel_deg_s'],
                    0.0 if k == n - 1 else blend, lin_acc, rot_acc)      # 마지막만 이어 붙이지 않는다
        if k % max(1, int(p['force_every'])) == 0:
            log.watch('wall')
    cc.wait_done()


def _to_center(p, log):
    """세척 끝 — 🔸 rig_v03 back_to_center 그대로: 올리지 않고 그 높이에서 중심 자세(손목 0)로 Move L."""
    _halt_check('중심 복귀')
    cc.wait_done()
    cc.move_pose(log.center, p['lin_vel_mm_s'], p['rot_vel_deg_s'], p['lin_acc_mm_s2'], p['rot_acc_deg_s2'])


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
      ③ 바닥을 찾으면 **힘을 풀고**(contact_down 이 해제한다) — 세척의 **가장 낮은 곳 = 바닥 + 3 mm**
      ④⑤ **Move Periodic 한 명령**(TOOL 기준): 위아래 z ±15 mm(2·3·5번 조인트) + 그리퍼 축 rz **좌우 ±90°(6번 조인트)** 를
         같은 주기 3.0 s 로 — 그릇 벽면 비틀기처럼 왔다 갔다 (중급1 p.71 "왕복 이동/회전")
         🚨 도는 동안 1·4번 조인트 감시, 1° 넘으면 즉시 정지하고 **자동으로 움직이지 않는다**(힘만 끔 → 사람이 확인)
         🚨 회전 최고 속도가 로봇 한계 225 °/s 를 넘으면 움직이기 전에 멈춘다
         🚨 회전 칸은 **rz** — rx 는 실기에서 4번 조인트를 돌렸다. Virtual 은 rx ↔ rz 를 뒤바꿔 움직여 믿지 않는다(9/21)
      ⑥ cycles(5) 번 뒤 가장 낮은 곳(바닥 + 3)으로 내려서 끝낸다 — 6번 조인트도 제자리
      ⑦ 솔을 컵에서 곧게 뽑아 컵 위 높이로 → z +40 → y −140 → z −40 → HOME (⓪ 의 반대)

    🚨 그릇(고정 좌표, 결정 E6)과 달리 컵은 **바닥을 힘으로 찾는다** — 컵이 깊고(95 mm) 솔이 단단해
       높이가 어긋나면 바로 세게 박히고, 그릇과 달리 물러서 완충해 줄 것이 없다.
    🔸 솔 세척부 길이 = 컵 내부 높이(둘 다 95 mm, CELL-02a) → 바닥에 닿으면 세척부가 통째로 들어가고
       그리퍼 끝은 컵 입구와 나란하다 → 왕복 진폭은 솔 길이 기준으로 줄인다. 돌려주는 insert_depth_mm 은
       **컵 위에서 바닥까지 내려간 거리**(빠른 하강 + 찾기)다 — 잰 값이다.
    🚨 왕복은 **순응·힘제어를 끈 상태**로 한다(시나리오 3 "힘 풀기") — 명령한 진폭이 실제 진폭이어야 한다.
       안전은 힘 감시가 맡는다: 누르는 힘 limit_n · 옆 힘 lateral_max_n · duration_s · 힘 로그.
    9/21 박진용 실기 확정: 위아래 3 cm(stroke 15 × 2) · 6번 조인트 좌우 ±90° · 주기 3.0 s · 5 회 · 가장 낮은 곳 바닥 + 3 mm.
    """
    p = cc.cfg()['f3']['wipe_cup']
    t0 = time.monotonic()
    log = _Log(p, t0)
    trip = _Trip(cup_hops(p), p)
    code, depth, moved = ROBOT_ERROR, 0.0, True
    try:
        _halt_check('컵 닦기 시작')
        check_spin_speed(p)                                              # 로봇 한계를 넘는 설정이면 움직이기 전에 멈춘다
        trip.go()                                                        # ⓪ HOME → 컵 위
        log.start(cc.read_force())                                       # 공중 기준값은 내려가기 전에
        fast = float(p['fast_down_mm'])
        _fast_z(p, -fast)                                                # ① 정한 길이만큼 빠르게
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
    except JointGuardStop as e:                                          # 🚨 손목이 꺾였을 수 있다 → 힘만 끄고 그대로 둔다
        moved = False                                                    #   곧게 뽑으면 꺾인 솔이 컵을 끌고 올라온다(PR #56 리뷰)
        code = ROBOT_ERROR
        _warn(f'{e} → 티치펜던트로 자세를 확인하고 사람이 컵에서 빼낸다')
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
    """6번 조인트가 시작 각 ± spin_deg/2 를 돌아도 한계(±j6_limit − margin) 안인가. 아니면 ValueError — 돌지 않는다."""
    half, lim = float(p['spin_deg']) / 2.0, float(p['j6_limit_deg']) - float(p['j6_margin_deg'])
    if abs(j6) + half > lim:
        raise ValueError(f'wipe_cup: 6번 조인트 {j6:.1f}° 에서 ±{half:g}° 를 돌면 한계(±{lim:g}°)를 넘는다 — 돌지 않는다')


def check_spin_speed(p):
    """세척 회전 최고 속도 2π × (spin_deg/2) / period_s 가 로봇 한계(rot_vel_limit_deg_s)를 넘으면 ValueError — **내려가기 전에** 본다.
    넘으면 컨트롤러가 Periodic 을 거절한다(9/21 알람 1212: 251 > 225 °/s)."""
    peak = 2.0 * math.pi * float(p['spin_deg']) / 2.0 / float(p['period_s'])
    lim = float(p['rot_vel_limit_deg_s'])
    if peak > lim:
        raise ValueError(f'wipe_cup: 세척 회전 최고 {peak:.0f} °/s > 로봇 한계 {lim:g} °/s — period_s 를 '
                         f'{2 * math.pi * float(p["spin_deg"]) / 2 / lim:.2f} s 이상으로')
    return peak


def cup_periodic(p, stroke):
    """세척 한 명령의 (진폭, 주기) — [x, y, z, rx, ry, rz], **TOOL 기준**. 위아래(툴 z) ±stroke · 툴 z 축 회전(rz) ±spin/2 · 같은 주기.

    🔸 툴 z = 그리퍼 축이라 **rz = 6번 조인트**(두산 정의). 9/21 근거:
       · 실기 TOOL rx → 4번 조인트(두산 정의대로 — rx 는 옆으로 누운 축) · 실기 TCP 는 회전값이 없다(티칭 좌표 a−c 가 플랜지와 같다)
       · 🚨 Virtual 은 rx ↔ rz 를 뒤바꿔 움직였다(rx → 6번, rz → 4번) — Periodic 회전은 Virtual 결과를 믿지 않는다
    """
    t = float(p['period_s'])
    return ([0.0, 0.0, float(stroke), 0.0, 0.0, float(p['spin_deg']) / 2.0],
            [0.0, 0.0, t, 0.0, 0.0, t])


def _scrub_cup(p, log):
    """③ **가장 낮은 곳 = 바닥 + lift_mm(3)** — Periodic 은 시작 자리를 가운데로 위아래 똑같이 움직이므로 바닥 + 3 + stroke 에서 시작
    → ④⑤ Move Periodic 한 명령(TOOL z ±stroke + TOOL rz ±spin/2) × cycles → ⑥ 가장 낮은 곳(바닥 + 3)으로 내려서 끝낸다.

    🚨 도는 동안 1·4번 조인트를 계속 읽어 joint_guard_deg 를 넘으면 **즉시 정지**하고 멈춘다 — 6번 조인트만 돌아야 한다.
    세척 주기는 vel_scale 예외(결정 E17).
    """
    stroke = cup_stroke(p)
    if stroke <= 0:
        raise RuntimeError('wipe_cup: 솔 길이로는 왕복할 자리가 없다 — f3.wipe_cup 설정 확인')
    _halt_check('세척')
    cc.move_rel(0.0, 0.0, float(p['lift_mm']) + stroke, 'BASE',          # ③ 가장 낮은 곳 = 바닥 + lift_mm(3) 이 되게 가운데로
                vel_mm_s=float(p['lift_vel_mm_s']) * _scale())
    log.watch('cup-lift')
    q0 = cc.joints()
    spin_room(q0[5], p)
    amp, period = cup_periodic(p, stroke)
    guard = float(p['joint_guard_deg'])
    cc.move_periodic(amp, period, repeat=int(p['cycles']), ref='TOOL', atime=float(p['ramp_s']), scale=False)
    _info(f'wipe_cup 세척: 위아래 {2 * stroke:.0f} mm · 6번 조인트 {p["spin_deg"]:g}° 폭 · 주기 {p["period_s"]:g} s '
          f'· {p["cycles"]} 회 (Move Periodic · TOOL rz · 6번 조인트 {q0[5]:.1f}° 에서 시작)')
    while not cc.motion_done():                                          # ④⑤ 도는 동안 조인트·힘 감시
        q = cc.joints()
        bad = [(k + 1, q[k] - q0[k]) for k in (0, 3) if abs(q[k] - q0[k]) > guard]
        if bad:
            cc.stop_now()
            raise JointGuardStop('wipe_cup: ' + ' · '.join(f'{k}번 조인트 {d:+.1f}°' for k, d in bad)
                                 + ' 가 움직였다 — 6번 조인트만 돌아야 한다. 즉시 정지 · 자동으로 움직이지 않는다')
        if log.over_time():
            cc.stop_now()
            raise cc.MotionTimeout('wipe_cup: 세척 시간 초과')
        log.watch('cup-scrub')
        time.sleep(float(p['sample_s']))
    end = cc.joints()[5]
    if abs(end - q0[5]) > 5.0:
        _warn(f'wipe_cup: 끝난 뒤 6번 조인트 {end:.1f}° — 시작 {q0[5]:.1f}° 로 돌아오지 않았다')
    cc.move_rel(0.0, 0.0, -stroke, 'BASE',                               # ⑥ 가장 낮은 곳(바닥 + 3)에서 끝낸다
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
