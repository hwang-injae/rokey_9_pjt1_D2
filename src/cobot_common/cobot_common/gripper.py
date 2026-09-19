# -*- coding: utf-8 -*-
"""그리퍼 함수(RG2) — 담당 민범진 (INF-02d, 9/19 재분담 — 결정 기록 W3). 함수 표는 docs/03_설계_SDD.md §3.1.

강사 배포 드라이버(`onrobot_rg_control`)를 통해 쓴다. 소스에서 확인한 사실(9/19):

명령 — srv `/onrobot/sendCommand` 는 **문자열 하나**만 받는다 (OnRobotRGControllerServer.genCommand):
    '600'  폭 60.0 mm (0.1 mm 단위) · 힘은 직전 값 유지
    'o'    열기(최대 폭)          · 힘은 직전 값 유지
    'c'    닫기(폭 0)             · 힘은 직전 값 유지
    'i'    힘 +2.5 N · **직전 폭으로 다시 파지**
    'd'    힘 −2.5 N · **직전 폭으로 다시 파지**
  🚨 힘을 **절대값으로 줄 수 없다.** 2.5 N 계단으로만 오르내린다. 그리고 드라이버는
     현재 힘을 알려주지 않는다 → 우리가 기억하되, 처음 한 번은 0 N 까지 내려 **기준을 맞춘다**.
  🟢 'i'/'d' 가 "같은 폭으로 힘만 바꿔 다시 파지" 라서 grip_level 에 그대로 맞는다.

완료 — 서비스 응답은 "보냈다" 일 뿐이다(`res.success = True` 를 즉시 돌려준다).
  움직이는 중인지는 `/onrobot_joint_states` 의 **effort** 로 안다(busy 면 힘 값, 아니면 0.0).

현재 폭 — 드라이버는 폭(mm)을 발행하지 않는다. `/onrobot_joint_states` 의 **관절각**을
  드라이버와 같은 식으로 환산한다(jointValueToWidth). `finger_joint` 의 mimic 비율이 1 이라
  position[finger_joint] 가 곧 관절각이다. 왕복 검증 오차 0.000 mm,
  그릇 벽 구간(0~5 mm)에서 1 mm 당 관절각 차이 0.0091 rad — 분해능 충분(9/19 확인).
"""
import threading
import time

import numpy as np

__all__ = ['grip', 'grip_level', 'release', 'grip_width']

# ── 드라이버 상수 (OnRobotRGControllerServer.py 의 RG2 분기에서 그대로) ──
_L1, _L3 = 0.108505, 0.055
_THETA1, _THETA3, _DY = 1.41371, 0.76794, -0.0144
_MAX_FORCE_N = 40.0                  # max_force 400 (0.1 N 단위)
_MAX_WIDTH_MM = 110.0                # max_width 1100 (0.1 mm 단위)
_FORCE_STEP_N = 2.5                  # 'i'/'d' 한 계단
_FINGER_JOINT = 'finger_joint'       # mimic 비율 1 → position 이 곧 관절각

_lock = threading.Lock()
_client = None                       # /onrobot/sendCommand
_joint_angle = None                  # 최신 관절각(rad)
_effort = None                       # 최신 effort — 0.0 이면 멈춘 것
_force_n = None                      # 🚨 드라이버가 안 알려줘서 우리가 기억한다


def setup_io(node):
    """init() 이 실행기를 돌리기 전에 한 번 불러 준다 (SDD §3.1). 콜백은 값 저장만."""
    global _client
    from onrobot_rg_msgs.srv import SetCommand
    from sensor_msgs.msg import JointState

    _client = node.create_client(SetCommand, '/onrobot/sendCommand')
    node.create_subscription(JointState, '/onrobot_joint_states', _on_joint_states, 10)


def _on_joint_states(msg):
    """🚨 값 저장만 한다 — 로봇 함수를 부르지 않는다 (SDD §3.2 규칙 ③)."""
    global _joint_angle, _effort
    try:
        i = list(msg.name).index(_FINGER_JOINT)
    except ValueError:
        i = 0
    with _lock:
        if i < len(msg.position):
            _joint_angle = float(msg.position[i])
        if i < len(msg.effort):
            _effort = float(msg.effort[i])


# ------------------------------------------------------------------ 공개 함수
def grip(width, force):
    """목표 폭(mm)·힘(N)으로 잡고 완료를 기다린 뒤 **실제 폭(mm)** 을 돌려준다.

    🚨 부르는 쪽은 목표 폭을 **기대보다 작게** 준다(SDD §5.2, 9/19 결정).
       같은 값을 주면 빈손으로 닫아도 그 폭에서 멈춘 것처럼 보인다 —
       그릇은 벽 파지라 기대 폭이 ≈ 2 mm 밖에 안 된다.
    """
    _set_force(float(force))
    _send(str(int(round(_clamp_width(width) * 10))))       # 0.1 mm 단위
    _wait_done()
    return grip_width()


def grip_level(kind, level):
    """파지 힘 2단계 전환 NORMAL ↔ HOLD. 같은 폭 목표로 힘만 바꿔 다시 파지 (SDD §3.1).

    털기·담금·물 털기는 시작할 때 HOLD, 끝날 때 NORMAL 로 되돌린다(IRD §4).
    드라이버의 'i'/'d' 가 직전 폭으로 다시 파지하므로 폭을 다시 명령하지 않는다.
    """
    from .bootstrap import cfg
    level = str(level).upper()
    if level not in ('NORMAL', 'HOLD'):
        raise ValueError(f"grip_level: level={level!r} — 'NORMAL' 또는 'HOLD'")
    preset = _preset(cfg(), kind)
    key = 'grip_force_n' if level == 'NORMAL' else 'hold_force_n'
    if key not in preset:
        raise KeyError(f'cell.presets.{kind}.{key} 가 없다 — 프리셋을 확인한다')
    before = grip_width()
    _set_force(float(preset[key]))
    _wait_done()
    after = grip_width()
    _log().info(f'grip_level({kind}, {level}) — 폭 {before:.1f} → {after:.1f} mm')
    return after


def release():
    """그리퍼 열기. 힘 설정은 그대로 둔다(드라이버의 'o' 가 힘을 안 바꾼다)."""
    _send('o')
    _wait_done()


def grip_width():
    """현재 그리퍼 폭(mm). `/onrobot_joint_states` 의 관절각을 드라이버와 같은 식으로 환산한다."""
    with _lock:
        th = _joint_angle
    if th is None:
        raise RuntimeError('그리퍼 관절각을 아직 못 받았다 — /onrobot_joint_states 와 브링업을 확인한다')
    return float((np.cos(th + _THETA3) * _L3 + _DY + _L1 * np.cos(_THETA1)) * 2 * 1000.0)


# ------------------------------------------------------------------ 내부
def _send(command):
    """드라이버에 문자열 명령 하나를 보낸다. 통신 노드가 다른 스레드에서 돌고 있어 동기 호출이 된다."""
    from onrobot_rg_msgs.srv import SetCommand
    if _client is None:
        raise RuntimeError('cobot_common.init(name) 을 먼저 부른다 (그리퍼 클라이언트가 없다)')
    if not _client.wait_for_service(timeout_sec=_timeout()):
        raise RuntimeError('/onrobot/sendCommand 가 안 보인다 — 브링업을 확인한다')
    req = SetCommand.Request()
    req.command = str(command)
    res = _client.call(req)
    if res is None or not res.success:
        raise RuntimeError(f'그리퍼 명령 {command!r} 실패 — {getattr(res, "message", "응답 없음")}')


def _set_force(target_n):
    """힘을 target_n 에 맞춘다. 🚨 2.5 N 계단으로만 되고, 드라이버는 현재 값을 안 알려준다.

    그래서 처음 한 번은 **0 N 까지 내려 기준을 맞춘다**(드라이버가 0 에서 더 안 내려간다).
    이후로는 우리가 기억한 값에서 차이만큼만 움직인다.
    """
    global _force_n
    target_n = max(0.0, min(_MAX_FORCE_N, float(target_n)))
    if _force_n is None:
        steps = int(_MAX_FORCE_N / _FORCE_STEP_N) + 1        # 넉넉히 내려 0 에 붙인다
        _log().info(f'그리퍼 힘 기준 맞추기 — 0 N 까지 내린다 ({steps}회)')
        for _ in range(steps):
            _send('d')
        _force_n = 0.0
    steps = int(round((target_n - _force_n) / _FORCE_STEP_N))
    for _ in range(abs(steps)):
        _send('i' if steps > 0 else 'd')
    _force_n = max(0.0, min(_MAX_FORCE_N, _force_n + steps * _FORCE_STEP_N))
    if abs(_force_n - target_n) > 0.01:
        _log().warn(f'그리퍼 힘 {target_n:.1f} N 을 정확히 못 맞춘다 (2.5 N 계단) → {_force_n:.1f} N')


def _wait_done():
    """움직임이 끝날 때까지 기다린다. effort 가 0.0 이면 멈춘 것(드라이버 busy 플래그)."""
    limit = _timeout()
    t0 = time.monotonic()
    seen_busy = False
    while time.monotonic() - t0 < limit:
        with _lock:
            e = _effort
        if e is None:
            time.sleep(0.02)
            continue
        if e > 0.0:
            seen_busy = True
        elif seen_busy or time.monotonic() - t0 > 0.3:   # 시작을 놓쳤어도 0.3 s 뒤엔 멈춘 것으로 본다
            return
        time.sleep(0.02)
    _log().warn(f'그리퍼 동작이 {limit:.1f}s 안에 안 끝났다 — 그대로 진행한다')


def _clamp_width(mm):
    w = float(mm)
    if not 0.0 <= w <= _MAX_WIDTH_MM:
        _log().warn(f'그리퍼 폭 {w:.1f} mm 는 범위(0~{_MAX_WIDTH_MM:.0f}) 밖 — 잘라서 보낸다')
    return max(0.0, min(_MAX_WIDTH_MM, w))


def _preset(conf, kind):
    presets = ((conf.get('cell') or {}).get('presets') or {})
    if kind not in presets:
        raise KeyError(f'cell.presets.{kind} 가 없다 — 티칭·프리셋을 확인한다')
    return presets[kind] or {}


def _timeout():
    from .bootstrap import cfg
    try:
        return float((cfg().get('cell') or {}).get('limits', {}).get('timeout_s') or 10.0)
    except Exception:                                    # noqa: BLE001 — 설정이 없어도 기본값으로 돈다
        return 10.0


def _log():
    from .bootstrap import io_node
    return io_node().get_logger()
