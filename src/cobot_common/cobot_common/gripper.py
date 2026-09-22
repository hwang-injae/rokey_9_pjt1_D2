# -*- coding: utf-8 -*-
"""그리퍼 함수(RG2) — 담당 민범진 (INF-02d, 9/19 재분담 — 결정 기록 W3). 함수 표는 docs/03_설계_SDD.md §3.1.

강사 배포 드라이버(`onrobot_rg_control`)를 통해 쓴다. 소스에서 확인한 사실(9/19):

명령 — srv `/onrobot/sendCommand` 는 **문자열 하나**만 받는다 (OnRobotRGControllerServer.genCommand):
    '600'  폭 60.0 mm (0.1 mm 단위) · 힘은 직전 값 유지
    'o'    열기(최대 폭)          · 힘은 직전 값 유지
    'c'    닫기(폭 0)             · 힘은 직전 값 유지
    'i'    힘 +2.5 N · **직전 폭으로 다시 파지**
    'd'    힘 −2.5 N · **직전 폭으로 다시 파지**
  🚨 힘을 **절대값으로 줄 수 없다.** 2.5 N 계단으로만 오르내린다.
  🟢 'i'/'d' 가 "같은 폭으로 힘만 바꿔 다시 파지" 라서 grip_level 에 그대로 맞는다.

현재 힘 — 🟢 **읽을 수 있다**(9/21 실기 확인). `/onrobot_joint_states` 의 **effort** 가
  드라이버의 현재 목표 힘(N)이다(getStatus: `effort = rgfr/10`, 상태 비트가 켜져 있을 때).
  🚨 **움직이거나 닫혀 있을 때만** 읽힌다 — 활짝 열린 채 정지하면 0 이 온다(= 모름).
  🚨 드라이버가 힘을 **프로세스 종료 뒤에도 기억**한다(3회 연속 실행: 40 → 35 → 30 → 25 N)
     → "브링업 직후 40 N" 은 첫 실행에서만 참이다. 세지 않고 **매번 읽어서** 맞춘다.

완료 — 서비스 응답은 "보냈다" 일 뿐이다(`res.success = True` 를 무조건 돌려준다 — 실패를 알 수 없다).
  🚨 끝났는지는 **폭이 멈추는 것**으로 본다. effort 로 보면 파지에 성공했을 때 "잡았다" 비트 때문에
     0 이 되지 않아 **잡을 때마다 상한까지 기다린다**(9/21 실기에서 확인).

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
_OPEN_WIDTH_MM = 100.0               # 🆕 9/23 이 폭보다 넓으면 '열려 있다(빈손)' — grip_level 이 힘 전환·탐색을 거부한다(RG2 최대 110)
_MAX_WIDTH_MM = 110.0                # max_width 1100 (0.1 mm 단위)
_FORCE_STEP_N = 2.5                  # 'i'/'d' 한 계단
_FINGER_JOINT = 'finger_joint'       # mimic 비율 1 → position 이 곧 관절각
_POLL_S = 0.02                       # 폭을 들여다보는 간격 (드라이버 발행 50 Hz)
_SETTLE_SPAN_MM = 0.05               # 이 폭 안에서 머물면 "멈췄다"
_SETTLE_HOLD_S = 0.2                 # 그 상태가 이만큼 이어져야 한다

_lock = threading.Lock()
_client = None                       # /onrobot/sendCommand
_joint_angle = None                  # 최신 관절각(rad)
_effort = None                       # 최신 effort — 0.0 이면 멈춘 것
# 🚨 마지막으로 **읽은** 힘(N). 셈으로 만들지 않는다 — 콜백이 effort 에서 갱신한다.
#    드라이버가 목표 힘을 프로세스 종료 뒤에도 기억해서(9/21 실기: 3회 연속 40 → 35 → 30 → 25 N)
#    "브링업 직후 40 N" 같은 가정은 첫 실행에서만 맞는다. 그래서 세지 않고 읽는다.
#    🚨 힘은 **움직이거나 닫혀 있을 때만** 읽힌다 — 활짝 열린 채 정지하면 0 이 온다(= 모름).
#       그래서 마지막으로 읽은 값을 들고 있는다. 어떤 움직임이든 일어나면 콜백이 갱신한다.
_force_n = None


def setup_io(node):
    """init() 이 실행기를 돌리기 전에 한 번 불러 준다 (SDD §3.1). 콜백은 값 저장만."""
    global _client
    from onrobot_rg_msgs.srv import SetCommand
    from sensor_msgs.msg import JointState

    _client = node.create_client(SetCommand, '/onrobot/sendCommand')
    node.create_subscription(JointState, '/onrobot_joint_states', _on_joint_states, 10)


def _on_joint_states(msg):
    """🚨 값 저장만 한다 — 로봇 함수를 부르지 않는다 (SDD §3.2 규칙 ③)."""
    global _joint_angle, _effort, _force_n
    try:
        i = list(msg.name).index(_FINGER_JOINT)
    except ValueError:
        i = 0
    with _lock:
        if i < len(msg.position):
            _joint_angle = float(msg.position[i])
        if i < len(msg.effort):
            _effort = float(msg.effort[i])
            # 🚨 값 저장만 한다. effort > 0 이면 그게 드라이버의 **현재 목표 힘(N)** 이다
            #    (드라이버 getStatus: effort = rgfr/10, 상태 비트가 켜져 있을 때만).
            if _effort > 0.0:
                _force_n = float(_effort)


# ------------------------------------------------------------------ 공개 함수
def grip(width, force):
    """목표 폭(mm)·힘(N)으로 잡고 완료를 기다린 뒤 **실제 폭(mm)** 을 돌려준다.

    🚨 부르는 쪽은 목표 폭을 **기대보다 작게** 준다(SDD §5.2, 9/19 결정).
       같은 값을 주면 빈손으로 닫아도 그 폭에서 멈춘 것처럼 보인다 —
       그릇은 벽 파지라 기대 폭이 ≈ 2 mm 밖에 안 된다.
    """
    _set_force(float(force))                               # 잡기 **전에** 맞춘다 (아직 빈손)
    before = _width_or_none()
    _send(str(int(round(_clamp_width(width) * 10))))       # 0.1 mm 단위
    after = _wait_done()
    _warn_if_stuck(before, after, f'폭 {float(width):.1f} mm 로 잡기')
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
    w_now = _width_or_none()
    if w_now is not None and w_now > _OPEN_WIDTH_MM:
        # 🚨 9/23 08:4x 실기: 명령이 섞여 그리퍼가 **열린 채**(110.6) 담금이 시작됐고, 아래 탐색 'i' 가 빈손을 꽉 닫아 버렸다
        #    → 쥐고 있지 않으면 힘 전환도 탐색도 하지 않는다(부르는 쪽이 GRIP_FAIL 로 처리)
        raise RuntimeError(f'grip_level: 그리퍼가 열려 있다(폭 {w_now:.1f} mm > {_OPEN_WIDTH_MM:g}) — 쥐고 있을 때만 힘을 바꾼다')
    with _lock:
        known = _force_n is not None
    if not known:
        # 🚨 여기는 **이미 쥐고 있는** 자리다. 힘을 모르는 채 계단을 보내면 어디로 갈지 모른다.
        #    🔄 9/23 08:3x(PM · E36 실기): 새 프로세스가 쥔 용기로 시작하면 드라이버가 effort 를 안 보내 여기서 멈추는 일이
        #    실기에서 났다(상태 비트가 꺼져 있으면 effort 0). 놓지 않고 읽는 방법 = **한 계단 올려(+2.5 N) 같은 폭으로 다시 잡기**
        #    ('i' 는 직전 폭으로 재파지 → 움직이는 동안 effort 가 온다). 그 다음 _set_force 가 읽은 값에서 목표까지 맞춘다.
        _log().warn('grip_level: 그리퍼 힘을 아직 못 읽었다 — 쥔 채로 한 계단(+2.5 N) 다시 잡아 읽는다')
        _send('i')
        _wait_done()
        with _lock:
            known = _force_n is not None
        if not known:
            raise RuntimeError(
                'grip_level: 그리퍼 힘을 다시 잡아도 못 읽었다 — 모르는 채로 힘을 바꾸면 용기를 놓칠 수 있다. '
                '드라이버(/onrobot_joint_states effort)를 확인하고, 이 프로그램에서 cc.release() 나 cc.grip() 을 먼저 부른다')
    before = grip_width()
    _set_force(float(preset[key]))                       # 'i'/'d' 안에서 _wait_done 까지 한다
    after = grip_width()
    _log().info(f'grip_level({kind}, {level}) — 폭 {before:.1f} → {after:.1f} mm')
    return after


def release():
    """그리퍼 열기. 힘 설정은 그대로 둔다(드라이버의 'o' 가 힘을 안 바꾼다).

    🚨 힘은 **움직이거나 닫혀 있을 때만** 읽힌다. 이미 활짝 열려 있으면 'o' 가 아무 움직임도
       안 만들어 못 읽는다 → 아직 한 번도 못 읽었으면 **빈손으로 한 번 닫았다 연다**.
       여기가 손이 빈 게 확실한 유일한 자리다 — 그래서 그리퍼를 쓰는 프로그램은
       아무것도 쥐지 않은 상태의 release() 로 시작한다(그 약속은 그대로다).
    """
    before = _width_or_none()
    _send('o')
    after = _wait_done()
    _warn_if_stuck(before, after, '열기')
    with _lock:
        known = _force_n is not None
    if not known:
        _log().info('그리퍼 힘을 아직 못 읽었다 — 빈손으로 한 번 닫았다 열어서 읽는다')
        _send('c')
        _wait_done()
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
    """목표 힘에 맞춘다 — 🚨 **세지 않고 읽어서** 맞춘다.

    드라이버는 힘을 절대값으로 못 받고 2.5 N 계단('i'/'d')으로만 오르내린다. 그런데 현재 힘은
    effort 로 **읽을 수 있으므로**(머리말) 마지막으로 읽은 값에서 계단 수를 구하면 된다.
    예전처럼 0 N 까지 내려 기준을 잡던 방식(_anchor_force)은 없앴다 —
      · 0 N 은 데이터시트 유효 범위(3~40 N) 밖이고
      · 쥔 채로 하면 힘이 0 을 지나는 동안 용기를 놓치며
      · 매번 17회 통신이 들었는데, 무엇보다 **드라이버가 힘을 기억해서 셈이 어긋났다**(9/21).

    🚨 한 번도 못 읽었으면(_force_n is None) 맞출 수 없다 — 부르는 쪽이 먼저 움직여 준다(release).
    """
    target_n = max(0.0, min(_MAX_FORCE_N, float(target_n)))
    with _lock:
        now = _force_n
    if now is None:
        raise RuntimeError(
            '그리퍼 힘을 아직 한 번도 못 읽었다 — 힘은 움직이거나 닫혀 있을 때만 읽힌다. '
            'cc.release() 를 먼저 불러 한 번 움직인 뒤에 쓴다')
    steps = int(round((target_n - now) / _FORCE_STEP_N))
    if steps == 0:
        return now
    cmd = 'i' if steps > 0 else 'd'
    for _ in range(abs(steps)):
        _send(cmd)
    _wait_done()                                         # 'i'/'d' 는 직전 폭으로 **다시 파지**한다
    with _lock:
        got = _force_n
    if got is None or abs(got - target_n) > 0.01:
        _log().warn(f'그리퍼 힘 {target_n:.1f} N 을 정확히 못 맞춘다 (2.5 N 계단) → 읽은 값 '
                    + (f'{got:.1f} N' if got is not None else '없음'))
    return got


def _width_or_none():
    try:
        return grip_width()
    except RuntimeError:
        return None


def _warn_if_stuck(before, after, what):
    """🚨 폭을 명령했는데 **전혀 안 움직이면** 안전 스위치를 의심한다.

    RG2 매뉴얼 §6.2.3 — 안전 스위치(S1·S2)가 걸리면 그리퍼가 움직이지 않고
    **전원을 다시 넣어야만** 풀린다. 시연 중에 걸리면 그 자리에서 복구가 안 된다.
    드라이버에 `/onrobot/restartPower` 가 있지만 호출부의 인자가 어긋나 보여(소스 확인)
    자동으로 부르지 않는다 — 사람이 컴퓨트박스 전원을 다시 넣는 쪽이 확실하다.
    """
    if before is None or after is None or abs(after - before) >= _SETTLE_SPAN_MM:
        return
    _log().warn(f'그리퍼가 "{what}" 에 **전혀 움직이지 않았다** (폭 {before:.2f} mm 그대로). '
                f'이미 그 자리였을 수도 있지만, 안전 스위치(S1·S2)가 걸렸을 수 있다 — '
                f'걸렸으면 컴퓨트박스 전원을 다시 넣어야 풀린다 (RG2 매뉴얼 §6.2.3)')


def _wait_done():
    """움직임이 끝날 때까지 기다린다 — **폭이 멈추는 것**으로 본다. 멈춘 폭(mm)을 돌려준다.

    🚨 예전에는 effort 가 0 이 되는 것으로 봤다. 그런데 드라이버의 `busy` 는 상태 레지스터를
       **통째로** 읽은 값이라(비트 묶음), **파지에 성공하면 "잡았다" 비트 때문에 0 이 되지 않는다**
       → 잡을 때마다 상한까지 기다렸다. 9/21 실기에서 확인했고, 폭 기준으로 바꾸니 0.20~0.34 s 다.
    🚨 폭은 0.1 mm 단위로 계속 오므로 "더 안 변하면 끝" 이 더 정확하다.
    """
    limit = _timeout()
    t0 = time.monotonic()
    window = []                                          # [(시각, 폭)] — 최근 _SETTLE_HOLD_S 구간만 남긴다
    while time.monotonic() - t0 < limit:
        now = time.monotonic()
        try:
            w = grip_width()
        except RuntimeError:                             # 아직 관절각이 안 왔다
            time.sleep(_POLL_S)
            continue
        window.append((now, w))
        window[:] = [(t, x) for t, x in window if now - t <= _SETTLE_HOLD_S]
        spread = max(x for _, x in window) - min(x for _, x in window)
        if now - t0 >= _SETTLE_HOLD_S and spread <= _SETTLE_SPAN_MM:
            return w
        time.sleep(_POLL_S)
    _log().warn(f'그리퍼 동작이 {limit:.1f}s 안에 안 끝났다 — 그대로 진행한다')
    try:
        return grip_width()
    except RuntimeError:
        return None


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
