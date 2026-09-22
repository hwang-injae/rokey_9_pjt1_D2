"""F3 접촉 닦기 — 박진용 (IRD v3.0 §5, SDD §5.4).

flow_node(메인 프로그램)나 test/rig_f3.py 가 cobot_common.init() 뒤 **메인 스레드**에서 부르는
평범한 함수다(SDD §3.2). 이름·인자·반환은 cobot_api.F3Api 그대로이고, 실패는 예외가 아니라
Result.fail(code) 로 돌려준다. 숫자는 전부 params.yaml 의 f3 절 · cell.yaml 에서 읽는다(AGENTS 규칙 6).

시작 전제: 용기는 스펀지 홈에 안착돼 있고(F1 place) 툴을 쥔 상태(F1 tool PICK).
🔧 9/22 3차(박진용): `soap()`이 쥔 폭으로 수세미/컵솔을 스스로 가려서 **작업 위치까지 좌표로 직접 데려간다**
   (movej로 HOME을 들르지 않는다) — 수세미면 HOME(367.48, 8.09, 215.11), 컵솔이면 그 z+40·y+140(컵 위).
   `wipe_bowl()`·`wipe_cup()`은 더 이상 스스로 위치를 찾지 않는다 — 호출되면 **그 자리에서 바로 하강**하고,
   끝나면 호출 시점 높이로 곧게 상승만 하고 끝난다(호출자가 이미 올바른 자리에 데려다 놨다는 전제).
끝난 뒤: 툴을 쥔 채 그 자리. 툴 반납·재파지는 flow 가 F1 을 부른다.

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
    """툴 든 채 세제를 묻힌다(모션만, 물 없음). — F3-03. 코드 OK / TIMEOUT / ROBOT_ERROR.

    kind 인자는 안 쓴다(호환용으로만 남김) — 🔧 9/22 3차: **쥔 폭으로** 수세미/컵솔을 스스로 가린다
    (`f3.soap.tool_split_width_mm`). 그릇·컵 둘 다 **동작이 같다**(비틀고 왕복) — SOAP 자리로 옮기지 않고
    툴 픽업 직후 그 자리에서: ① 좌우 비틀기(6번 관절 ±twist_deg) twist_cycles 회 → ② Z 왕복(±updown_mm)
    updown_cycles 회 → ③ 작업 위치까지 **좌표로 직접**(z 먼저, 그다음 x·y) — movej·HOME 경유 없음:
       수세미 → HOME(cell.yaml stations.HOME 실측 x·y·z) · 컵솔 → 그 z+over_cup_up_mm·y+over_cup_dy_mm(컵 위).
    `wipe_bowl()`·`wipe_cup()`은 이 위치를 전제로 **호출되자마자 바로 하강**한다(스스로 자리 안 찾음).
    `count` 인자는 안 쓴다(횟수는 config 의 twist_cycles·updown_cycles 가 정한다).
    """
    return _soap_twist_updown()


def _soap_is_cup():
    """지금 쥔 폭으로 컵솔인지 판정한다(박진용 9/22 3차) — 수세미는 막히면 ≈25.6mm, 컵솔 목표는 5mm 근처라
    둘 사이 문턱값(`tool_split_width_mm`, 15.0)보다 좁으면 컵솔."""
    split = float(cc.cfg()['f3']['soap']['tool_split_width_mm'])
    return cc.grip_width() < split


def _soap_target(is_cup):
    """작업 위치 (x, y, z) — 수세미는 HOME 그대로, 컵솔은 HOME + z(over_cup_up_mm) + y(over_cup_dy_mm)(컵 위)."""
    home = cc.cfg()['cell']['stations'][START]
    x, y, z = float(home['posx_x_mm']), float(home['posx_y_mm']), float(home['posx_z_mm'])
    if is_cup:
        wc = cc.cfg()['f3']['wipe_cup']
        z += float(wc['over_cup_up_mm'])
        y += float(wc['over_cup_dy_mm'])
    return x, y, z


def _soap_move_to(target_xyz):
    """지금 자리에서 목표 (x, y, z) 로 — **z 먼저**(제자리 곧게 상승) → **그다음 x·y**(수평 이동).
    빠른 하강과 같은 속도(f3.wipe_bowl.fast_vel_mm_s·fast_acc_mm_s2, 박진용 9/22 3차) — 이미 도착했으면 안 움직인다."""
    wb = cc.cfg()['f3']['wipe_bowl']
    vel, acc = float(wb['fast_vel_mm_s']) * _scale(), float(wb['fast_acc_mm_s2']) * _scale()
    tx, ty, tz = target_xyz
    dz = tz - cc.where()[2]
    if dz > 0:
        cc.move_rel(0.0, 0.0, dz, 'BASE', vel_mm_s=vel, acc_mm_s2=acc)
    now = cc.where()
    dx, dy = tx - now[0], ty - now[1]
    if abs(dx) > 1e-6 or abs(dy) > 1e-6:
        cc.move_rel(dx, dy, 0.0, 'BASE', vel_mm_s=vel, acc_mm_s2=acc)


def _soap_twist_updown() -> Result:
    """툴 픽업 직후 그 자리에서 좌우 비틀기 → Z 왕복(톡톡) → 작업 위치(박진용 9/22 3차). soap() 의 실제 구현 — 그릇·컵 공용.

    🔧 9/22 1차 실기: 전체 시간 상한으로 `cell.limits.timeout_s`(10s, 접촉 동작 전용)를 잘못 빌려 써서
       TIMEOUT — 자기 전용 `f3.soap.duration_s`(60s)로 교체.
    🔧 2차: `move_joint_rel`·`move_rel`은 vel_scale 로 강제로 깎여(30°/s·120mm/s 상한) config 를 올려도 안 빨라졌다
       → 결정 E17("세척 동작 속도는 vel_scale 예외")과 같은 방식으로 **`move_periodic(scale=False)`**로 교체(9/22).
       🔸 컵과 달리 **1·4번 관절 감시는 넣지 않는다**(박진용 9/22 — 컵에만 둔다).
    🔧 3차: movej로 HOME 관절 이동하며 6번 관절을 풀어주던 걸 없앴다 — **좌표로 직접** 작업 위치까지 간다
       (그 자리에서 상승만 → 수평 이동만). 비틀기가 왕복이라 한 번 호출로는 거의 원위치로 돌아오지만,
       여러 번 반복되면 6번 관절이 조금씩 남아 쌓일 수 있다 — 실기로 지켜봐야 한다(박진용도 인지).
    """
    p = cc.cfg()['f3']['soap']
    duration = float(p['duration_s'])
    ramp = float(p['ramp_s'])
    t0 = time.monotonic()
    code, moved = ROBOT_ERROR, True
    is_cup = _soap_is_cup()
    target = _soap_target(is_cup)
    try:
        _halt_check('세제 동작 시작')
        twist = float(p['twist_deg'])
        twist_period = float(p['twist_period_s'])
        peak = 2.0 * math.pi * twist / twist_period                       # 로봇 한계 넘으면 컨트롤러가 거절(알람 1212) — 미리 본다
        limit = float(p['rot_vel_limit_deg_s'])
        if peak > limit:
            raise ValueError(f'soap: 비틀기 최고 {peak:.0f}°/s > 로봇 한계 {limit:g}°/s — twist_period_s 를 '
                             f'{2 * math.pi * twist / limit:.2f} s 이상으로')
        if time.monotonic() - t0 > duration:
            raise cc.MotionTimeout(f'soap: {duration:g} s 안에 비틀기를 시작 못 했다')
        cc.move_periodic([0.0, 0.0, 0.0, 0.0, 0.0, twist], [0.0, 0.0, 0.0, 0.0, 0.0, twist_period],
                          repeat=int(p['twist_cycles']), ref='TOOL', atime=ramp, scale=False)
        while not cc.motion_done():
            _halt_check('비틀기 도는 중')
            if time.monotonic() - t0 > duration:
                cc.stop_now()
                raise cc.MotionTimeout(f'soap: {duration:g} s 안에 비틀기를 못 끝냈다')
            time.sleep(0.05)

        updown = float(p['updown_mm'])
        up_period = float(p['updown_period_s'])
        if time.monotonic() - t0 > duration:
            raise cc.MotionTimeout(f'soap: {duration:g} s 안에 왕복을 시작 못 했다')
        cc.move_periodic([0.0, 0.0, updown, 0.0, 0.0, 0.0], [0.0, 0.0, up_period, 0.0, 0.0, 0.0],
                          repeat=int(p['updown_cycles']), ref='TOOL', atime=ramp, scale=False)
        while not cc.motion_done():
            _halt_check('왕복 도는 중')
            if time.monotonic() - t0 > duration:
                cc.stop_now()
                raise cc.MotionTimeout(f'soap: {duration:g} s 안에 왕복을 못 끝냈다')
            time.sleep(0.05)
        _halt_check('작업 위치로 이동')
        if time.monotonic() - t0 > duration:
            raise cc.MotionTimeout(f'soap: {duration:g} s 안에 작업 위치로 이동을 못 끝냈다')
        _soap_move_to(target)
        code = OK
    except (cc.MotionHalted, cc.MoveIncomplete):                          # 로봇 위치를 모른다 → 올리지 않는다
        moved = False
        raise
    except (cc.MotionTimeout, cc.MoveTimeout):
        code = TIMEOUT
    except (RuntimeError, ValueError, KeyError):
        code = ROBOT_ERROR
    finally:
        try:
            cc.force_off()
        except Exception:                                                # noqa: BLE001 — 복구는 끝까지
            _warn('정리 실패: force_off — 눈으로 확인')
        if not moved:
            _warn('🚨 로봇이 어디 있는지 모른다 → 힘만 끄고 **움직이지 않았다**. '
                  '티치펜던트로 상태를 확인하고 사람이 복구한다')
        elif code != OK:                                                  # 성공(이미 정확히 목표 위치)이면 더 안 움직인다 — 실패했을 때만 후퇴
            try:
                _soap_move_to(target)
            except Exception as e:                                       # noqa: BLE001 — 복구는 끝까지
                _warn(f'정리 실패: 목표 위치로 후퇴 — {e!r} · 눈으로 확인')
    return Result(ok=(code == OK), code=code)


def wipe_bowl() -> WipeBowlResult:
    """그릇 안쪽을 수세미로 닦는다 — F3-02. 코드 OK / FORCE_LIMIT / TIMEOUT / ROBOT_ERROR.

    🔸 두산 명령(동기 movel · amove_spiral · movec · release_*)은 **cc 함수로만** 부른다(AGENTS 규칙 4).
       값은 params.yaml f3.wipe_bowl.
    🔧 9/22: 나선이 조용히 시작 안 하던 문제는 **시작 위치·순서와 무관했다** — 진짜 원인은 (1) 나선 진입 직전
       순응을 껐다 켜던 토글(`contact_down(keep_compliance=True)`로 제거) (2) 시작 감지 대기시간이 짧음
       (`_START_WAIT_S` 2.0→5.0) (3) 그래도 실패하면 재시도(`move_spiral` 최대 3회) 였다 — force.py 참고.
       "9/20 rig_v03 순서 그대로 복제해야 한다"는 옛 가설(9/21)은 틀렸다 — 폐기.
    순서:
      하강(movel) → 공중 기준 5 회(|Fz| > 3 N 이면 중단) → 바닥 찾기(cc.contact_down 3 mm 걸음 · 3 N)
      → ① 순응 ON(찾은 자리 · 밀렸으면 되돌림) → ② 나선(힘제어 없이 · 시작 기다림 · 도는 동안 힘·위치)
      → ③ 힘제어 ON(1.5 N + 공중 기준) → 벽면(+18° 로 붙기 · 원호 12 개 시계 · ±18°) → 힘제어 OFF
      → 중심 복귀 → 힘·순응 OFF → 곧게 올라와 HOME(관절). 실패해도 힘 끄고 올라와 HOME —
      단 MotionHalted·MoveIncomplete(로봇 위치를 모른다, 결정 E11)면 힘만 끄고 움직이지 않는다.
    전체 시간 상한 duration_s(120 s)는 남긴다(황인재 결정 9/22 — "시간 초과 → 한 번 더 → 격리" 규칙용, 정상 닦기 19 s).
    """
    p = cc.cfg()['f3']['wipe_bowl']
    t0 = time.monotonic()
    log = _Log(p, t0)
    code, started, moved, bowl_check_z = ROBOT_ERROR, False, True, None
    try:
        _halt_check('그릇 닦기 시작')
        bowl_check_z = cc.where()[2]                                      # 호출된 자리(soap이 이미 데려다 놓음) — 안 움직이고 기록만
        started = True
        _bowl_move_z(-float(p['fast_down_mm']), p['fast_vel_mm_s'], p['fast_acc_mm_s2'])
        _bowl_zero(log)
        if abs(log.base[2]) > float(p['air_force_max_n']):
            raise RuntimeError(f'빠른 하강 뒤 공중 |Fz| {abs(log.base[2]):.1f} N > {p["air_force_max_n"]:g} N — 툴 무게·접촉 확인')
        depth, f = cc.contact_down(float(p['find_max_mm']), float(p['find_limit_n']),
                                   timeout_s=float(p['contact_timeout_s']), keep_compliance=True)
        z_contact = cc.where()[2]
        _info(f'wipe_bowl 바닥: 빠르게 {p["fast_down_mm"]:g} mm + 찾기 {depth:.1f} mm · 접촉 힘 {f:.1f} N '
              f'· 바닥 Z {z_contact:.1f} · 공중 기준 Fz {log.base[2]:.2f} N')
        if depth >= float(p['find_max_mm']) - 0.5:
            raise RuntimeError(f'{p["find_max_mm"]:g} mm 를 내려가도 바닥을 못 찾았다 — 그릇·좌표 확인')
        _bowl_settle_at_contact(p, z_contact)                            # ① 순응은 이미 켜진 채(끊지 않는다) — 밀렸으면만 보정
        _halt_check('바닥 나선')
        r_wall = _bowl_spiral(p, log)                                    # ② 나선
        _bowl_force_on(p, log, float(p['target_force_n']))               # ③ 힘제어 → 벽면
        _halt_check('벽면 회전')
        _bowl_wall(p, log, r_wall)
        cc.force_release()                                               # mwait → release_force (순응 유지)
        log.target = 0.0
        _bowl_to_center(p, log)
        cc.force_off()                                                   # 힘 → 순응 순서로 끈다
        code = OK
    except (cc.MotionHalted, cc.MoveIncomplete) as e:                    # 로봇 위치를 모른다(결정 E11) → 힘만 끄고 움직이지 않는다
        _warn(f'wipe_bowl 중단: {type(e).__name__}: {e}')
        moved = False
        raise
    except cc.ForceLimitError as e:
        _warn(f'wipe_bowl 중단: {e}')
        code = FORCE_LIMIT
    except (cc.MotionTimeout, cc.MoveTimeout) as e:
        _warn(f'wipe_bowl 중단: {e}')
        code = TIMEOUT
    except (RuntimeError, ValueError, KeyError) as e:
        _warn(f'wipe_bowl 중단: {type(e).__name__}: {e}')
        code = ROBOT_ERROR
    finally:
        _bowl_finish(p, started, moved, bowl_check_z)                    # 끄기 → (위치 알 때만) 기다림 → 곧게 호출 시점 높이로
    return WipeBowlResult(ok=(code == OK), code=code, force_log_path=log.save(),
                          duration_s=time.monotonic() - t0, force_mean_n=log.mean())


def _bowl_move_z(dz, vel, acc):
    """빠른 하강·올라오기 — 컵 `_fast_z`와 같은 방식(vel·acc 둘 다 vel_scale 적용, 박진용 9/22)."""
    cc.move_rel(0.0, 0.0, float(dz), 'BASE', vel_mm_s=float(vel) * _scale(), acc_mm_s2=float(acc) * _scale())


def _bowl_zero(log):
    fs = [cc.read_force() for _ in range(5)]
    log.start([sum(v) / len(fs) for v in zip(*fs)])


def _bowl_settle_at_contact(p, z_contact):
    """순응은 `contact_down(keep_compliance=True)`이 이미 켜 둔 채로 넘어온다(박진용 9/22) —
    여기서 다시 껐다 켜지 않는다(그 토글이 나선이 시작 안 하는 것과 관련 있어 보였다).
    밀렸으면(0.05mm 넘게) 찾은 높이로만 되돌린다."""
    dz = z_contact - cc.where()[2]
    if abs(dz) > 0.05:
        _bowl_move_z(dz, p['press_vel_mm_s'], p['press_acc_mm_s2'])
    _info(f'wipe_bowl 순응 유지 · Z {z_contact:.1f} → {cc.where()[2]:.1f} mm')


def _bowl_spiral(p, log):
    """바닥 닦기 — move_spiral(두산 amove_spiral) 한 번. 좌우 비틀기 없음.

    🔧 9/22 박진용: 접수는 되는데 조용히 실행 큐에 안 들어갈 때가 있었다(알람 없음·check_motion 계속 0) —
       `cc.move_spiral`에 최대 3회 재시도를 넣었다(force.py). 나선 함수 자체는 그대로 쓴다.
    """
    p0 = cc.where()
    log.center = list(p0)
    r_wall = log.wall_r()
    rev = max(1.0, round(r_wall / p['spiral_pitch_mm'], 1))
    cc.move_spiral(rev, r_wall, float(p['spiral_time_s']))               # mwait → amove_spiral(속도 0 · 시간, 최대 3회 재시도)
    rmax_seen = _bowl_sample_spiral(p, log, p0)
    _info(f'wipe_bowl 나선: 최대 반지름 {rmax_seen:.1f} mm (목표 {r_wall:.1f})')
    if rmax_seen < r_wall * 0.5:
        raise RuntimeError(f'나선이 돌지 않았다(최대 {rmax_seen:.1f} mm)')
    return r_wall


def _bowl_sample_spiral(p, log, p0):
    rmax = 0.0
    t0 = time.monotonic()
    while True:
        log.watch('spiral')
        now = cc.where()
        rmax = max(rmax, math.hypot(now[0] - p0[0], now[1] - p0[1]))
        if cc.motion_done():
            return rmax
        if time.monotonic() - t0 > float(p['spiral_time_s']) + 5.0:
            raise cc.MotionTimeout('나선이 끝나지 않는다')
        if log.over_time():                                              # 전체 duration_s(120 s) 상한 — 황인재 결정 9/22
            raise cc.MotionTimeout(f'wipe_bowl: 전체 {p["duration_s"]} s 초과(나선)')
        time.sleep(p['sample_s'])


def _bowl_force_on(p, log, target):
    cc.wait_done()
    cc.force_on('z', target + abs(log.base[2]), p['limit_n'])
    log.target = target


def _bowl_wall(p, log, r_wall):
    x0, y0, z_now, a, b, c = log.center
    lin_v, rot_v = float(p['lin_vel_mm_s']), float(p['rot_vel_deg_s'])
    lin_a, rot_a = float(p['lin_acc_mm_s2']), float(p['rot_acc_deg_s2'])
    now = cc.where()
    dx, dy = now[0] - x0, now[1] - y0
    th0 = math.atan2(dy, dx) if math.hypot(dx, dy) > 1e-6 else 0.0
    per = max(2, int(round(360.0 / p['wall_arc_deg'])))
    n = int(p['turns'] * per)
    dth = -2 * math.pi / per
    chord = 2 * r_wall * abs(math.sin(dth / 2))
    radius = min(float(p['blend_radius_mm']), chord * 0.45)
    tw = float(p['twist_deg'])

    def pose(th, rz):
        return [x0 + r_wall * math.cos(th), y0 + r_wall * math.sin(th), z_now,
                a, b, (c + rz + 180.0) % 360.0 - 180.0]

    twist = 1
    cc.wait_done()
    cc.move_pose(pose(th0, tw), float(p['wall_approach_vel_mm_s']), rot_v, lin_a, rot_a)   # 벽으로 천천히 (+twist)
    log.watch('wall')
    for k in range(n):
        if log.over_time():                                              # 전체 duration_s(120 s) 상한 — 황인재 결정 9/22
            raise cc.MotionTimeout(f'wipe_bowl: 전체 {p["duration_s"]} s 초과(벽면)')
        th_mid, th_end = th0 + dth * (k + 0.5), th0 + dth * (k + 1)
        rz_mid = tw * twist
        twist = -twist
        cc.move_arc(pose(th_mid, rz_mid), pose(th_end, tw * twist), lin_v, rot_v,
                    0.0 if k == n - 1 else radius, lin_a, rot_a)
        if k % max(1, int(p['force_every'])) == 0:
            log.watch('wall')
    cc.wait_done()


def _bowl_to_center(p, log):
    x0, y0, z_now, a, b, c = log.center
    cc.wait_done()
    cc.move_pose([x0, y0, z_now, a, b, c], float(p['lin_vel_mm_s']), float(p['rot_vel_deg_s']),
                 float(p['lin_acc_mm_s2']), float(p['rot_acc_deg_s2']))


def _bowl_finish(p, started, moved, bowl_check_z):
    """힘·순응 끄기는 언제나 → moved 면 동작 끝 대기 → 곧게 호출 시점 높이로 상승. 그걸로 끝(움직여서 자리 안 찾는다).

    🚨 moved=False(MotionHalted·MoveIncomplete — 로봇 위치를 모른다)면 힘만 끄고 움직이지 않는다
       (soap 과 같은 규칙 — AGENTS §4, 9/21 6번 관절 케이블 꼬임 사고)."""
    if not started:
        try:
            cc.force_off()
        except Exception:                                                # noqa: BLE001
            _warn('정리 실패: force_off — 눈으로 확인')
        return
    try:
        cc.force_off()
    except Exception as e:                                               # noqa: BLE001 — 복구는 끝까지
        _warn(f'정리 실패: 힘·순응 끄기 — {e!r} · 눈으로 확인')
    if not moved:
        _warn('🚨 로봇이 어디 있는지 모른다 → 힘만 끄고 **움직이지 않았다**. '
              '티치펜던트로 상태를 확인하고 사람이 복구한다')
        return

    def rise():
        dz = bowl_check_z - cc.where()[2]
        if dz > 0:
            _bowl_move_z(dz, p['fast_vel_mm_s'], p['fast_acc_mm_s2'])

    for what, fn in (('동작 끝 대기', cc.wait_done), ('곧게 올라오기', rise)):
        try:
            fn()
        except Exception as e:                                           # noqa: BLE001 — 복구는 끝까지
            _warn(f'정리 실패: {what} — {e!r} · 눈으로 확인')


def cup_hops(p):
    """HOME → 컵 위 상대 이동 [(dx, dy, dz), ...] (BASE). 올라가서 옆으로 — 컵 위 높이(HOME + over_cup_up_mm)에서 멈춘다.

    🔧 9/22 박진용 2차: 예전엔 올라갔다가 다시 내려와 HOME 높이로 돌아온 뒤 fast_down_mm 로 다시 내려갔다
       — 위로 40 갔다가 도로 40 내려오는 왕복이 그대로 보였다("위아래로 깔짝"). 이제 **내려오지 않고 그 높이가
       바로 컵 세척 시작점**이다 — fast_down_mm 을 그만큼(over_cup_up_mm) 늘려서 같은 깊이까지 내려간다."""
    up, dy = float(p['over_cup_up_mm']), float(p['over_cup_dy_mm'])
    return [(0.0, 0.0, up), (0.0, dy, 0.0)]


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

    9/21 확정 시나리오, 🔧 9/22 3차(박진용) — **스스로 컵 위를 찾아가지 않는다**: soap()이 이미 컵 위
    (HOME + z(over_cup_up_mm) + y(over_cup_dy_mm))에 데려다 놨다는 전제로, 호출되자마자 바로 하강부터 시작한다.
    괄호 안은 강의자료 근거.
      ① 호출된 그 자리에서 **fast_down_mm 만큼 빠르게** 내려간다(9/21 실측 90 mm − 10 + over_cup_up_mm 40). 바닥 위치는 미리 정하지 않는다
      ② **바닥을 찾는다** — cc.contact_down(순응 ON, 조금씩 하강, f3.wipe_cup.find_limit_n 5 N — 15 N 이면 컵이 눌렸다)
         (중급2 "힘 방향과 같은 방향의 모션 불가" — Z 힘제어로는 내려갈 수 없다. 순응 + 걸음 하강이 매뉴얼 방식)
      ③ 바닥을 찾으면 **힘을 풀고**(contact_down 이 해제한다) — 세척의 **가장 낮은 곳 = 바닥 + 3 mm**
      ④⑤ **Move Periodic 한 명령**(TOOL 기준): 위아래 z ±15 mm(2·3·5번 조인트) + 그리퍼 축 rz **좌우 ±90°(6번 조인트)** 를
         같은 주기 3.0 s 로 — 그릇 벽면 비틀기처럼 왔다 갔다 (중급1 p.71 "왕복 이동/회전")
         🚨 도는 동안 1·4번 조인트 감시, 1° 넘으면 즉시 정지하고 **자동으로 움직이지 않는다**(힘만 끔 → 사람이 확인)
         🚨 회전 최고 속도가 로봇 한계 225 °/s 를 넘으면 움직이기 전에 멈춘다
         🚨 회전 칸은 **rz** — rx 는 실기에서 4번 조인트를 돌렸다. Virtual 은 rx ↔ rz 를 뒤바꿔 움직여 믿지 않는다(9/21)
      ⑥ cycles(5) 번 뒤 가장 낮은 곳(바닥 + 3)으로 내려서 끝낸다 — 6번 조인트도 제자리
      ⑦ 솔을 컵에서 곧게 뽑아 **호출된 자리 높이로만** 상승 — 그걸로 끝(HOME 이동·수평 복귀 없음)

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
    code, depth, moved, cup_check_z = ROBOT_ERROR, 0.0, True, None
    try:
        _halt_check('컵 닦기 시작')
        cup_check_z = cc.where()[2]                                      # 호출된 자리(soap이 이미 데려다 놓음) — 안 움직이고 기록만
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
    except JointGuardStop as e:                                          # 1·4번 조인트가 움직였다 — 곧게 뽑아 호출된 높이로(박진용 9/22)
        code = ROBOT_ERROR                                               #   수세미·솔 둘 다 무르다 → 컵도 그릇처럼 자동 복귀해도 된다
        _warn(f'{e} → 호출된 높이로 복귀했다. 티치펜던트로 자세 확인')
    except cc.ForceLimitError:
        code = FORCE_LIMIT
    except (cc.MotionTimeout, cc.MoveTimeout):
        code = TIMEOUT
    except (RuntimeError, ValueError, KeyError):
        code = ROBOT_ERROR
    finally:
        _cup_finish(p, moved, cup_check_z)                                # 힘 끄고, 위치를 알 때만 곧게 호출된 높이로만
    return WipeCupResult(ok=(code == OK), code=code, force_log_path=log.save(),
                         duration_s=time.monotonic() - t0, insert_depth_mm=depth)


def _cup_finish(p, moved, cup_check_z):
    """힘 끄기는 언제나 → moved 면 동작 끝 대기 → 곧게 호출 시점 높이로 상승. 그걸로 끝(움직여서 자리 안 찾는다, 박진용 9/22 3차)."""
    try:
        cc.force_off()
    except Exception as e:                                               # noqa: BLE001 — 복구는 끝까지
        _warn(f'정리 실패: 힘 끄기 — {e!r} · 눈으로 확인')
    if not moved:
        _warn('🚨 로봇이 어디 있는지 모른다 → 힘만 끄고 **움직이지 않았다**. '
              '티치펜던트로 상태를 확인하고 사람이 복구한다')
        return

    def rise():
        if cup_check_z is None:
            return
        dz = cup_check_z - cc.where()[2]
        if dz > 0:
            _fast_z(p, dz)

    for what, fn in (('동작 끝 대기', cc.wait_done), ('곧게 올라오기', rise)):
        try:
            fn()
        except Exception as e:                                           # noqa: BLE001 — 복구는 끝까지
            _warn(f'정리 실패: {what} — {e!r} · 눈으로 확인')


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
