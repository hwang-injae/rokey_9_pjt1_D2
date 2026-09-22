"""흔들기(털기) 값을 **키보드로 바꿔 가며 눈으로 정하는 도구** — 민범진 · 9/22

═══════════════════════════════════════════════════════════════════════════════════════
🔰 이게 무슨 프로그램인가
═══════════════════════════════════════════════════════════════════════════════════════
  "얼마나 크게, 얼마나 세게 털어야 하나" 는 계산으로 못 정한다. 눈으로 보고 정해야 한다.
  이 프로그램은 리모컨이다 — **키를 누르면 숫자만 바뀌고, 스페이스를 눌러야 로봇이 실제로 한 번 턴다.**
  마음에 드는 값이 나오면 w 키를 눌러 찍힌 한 줄을 params.yaml 에 옮겨 적으면 끝이다.

  🚨 여기서 바꾼 값은 **이번 실행 동안만** 살아 있다. 저장되지 않는다.
     w 로 찍어서 params.yaml 에 직접 옮겨 적어야 다음에도 그 값으로 돈다.

  두 가지 털기를 각각 맞출 수 있다
    --mode WASTE   잔반(음식물) 털기 — 잔반통 위에서 그릇을 기울여 쏟아 낸다
    --mode RINSE   물 털기         — 수조 위에서 손목을 까딱까딱

───────────────────────────────────────────────────────────────────────────────────────
🔰 하는 순서
───────────────────────────────────────────────────────────────────────────────────────
  ① 터미널 1 에서 로봇을 켠다            sod && sodreal
  ② 터미널 2 에서 코드를 빌드한다        cbc
  ③ 🚨 용기를 **미리 손으로 쥐여 준다**   python3 src/f2_sense_flow/test/rig_f2.py release
                                            (그리퍼가 벌어진다 → 손으로 그릇을 사이에 대 준다)
                                          python3 src/f2_sense_flow/test/rig_f2.py grip --kind BOWL
     이 프로그램은 그리퍼를 열고 닫지 않는다. 쥔 상태로 시작해야 한다.
  ④ 이 프로그램을 띄운다 (처음에는 꼭 30 % 속도로)
       PREWASH_VEL_SCALE=0.3 python3 src/f2_sense_flow/test/rig_shake_tune.py --mode RINSE --kind BOWL
  ⑤ 스페이스를 한 번 눌러 본다 → 로봇이 스스로 그 자리로 가서 지금 값으로 한 번 턴다
  ⑥ 키로 값을 바꾸고 다시 스페이스. 마음에 들 때까지 반복한다
  ⑦ v 를 눌러 100 % 속도로 바꿔 한 번 더 본다 (30 % 에서 괜찮아도 빠르면 다를 수 있다)
  ⑧ w 를 눌러 찍힌 줄을 params.yaml 에 옮겨 적는다 → q 로 끝낸다

───────────────────────────────────────────────────────────────────────────────────────
🔰 키
───────────────────────────────────────────────────────────────────────────────────────
    space 또는 s   지금 값으로 **실제로 한 번 턴다** (이 키만 로봇을 움직인다)

    A / a          크게 / 작게 흔든다        (관절이면 5°씩 · 직선이면 5 mm씩)
    p / P          세게 / 약하게 턴다        (한 번 왕복하는 시간을 0.05 초씩 · **p 를 누를수록 빨라져서 세진다**)
    N / n          횟수 늘리기 / 줄이기
    T / t          기울이기 각도 +10° / −10°  (잔반 털기에서 그릇 입이 아래를 보게 · 관절 왕복일 때만)
    C / c          가속도 +100 / −100         (직선 왕복일 때만 · 짧은 왕복에서는 이 값이 '툭 치는 느낌' 을 만든다)
    v              속도 30 % ↔ 100 % 전환
    w              지금 값을 **params.yaml 에 붙일 한 줄**로 찍어 준다
    h              키 설명 다시 보기
    q              끝낸다 (로봇은 움직이지 않고 그 자리에 선다)

───────────────────────────────────────────────────────────────────────────────────────
🔰 안전
───────────────────────────────────────────────────────────────────────────────────────
  · 값이 너무 크면 **로봇이 움직이기 전에 거절한다** (params.yaml 의 f2.limits 가 상한이다)
  · 털다가 용기가 미끄러지면 스스로 멈추고 GRIP_FAIL 을 돌려준다
  · 위험하면 Ctrl+C — 그 자리에 선다. 손은 비상정지 버튼 근처에 둔다
  · 시작할 때 컨트롤러의 툴·TCP 이름을 확인한다(다르면 시작 거부 · TS-07) ·
    낮은 자세면 곧게 위로 올라온 뒤 HOME 으로 간다(TS-08)

파일 이름이 test_ 로 시작하지 않아서 자동 시험(pytest)이 이 파일을 모으지 않는다.
"""
import argparse
import sys
import termios
import tty

import cobot_common as cc
from f2_sense_flow import sense
from f2_sense_flow.preflight import go_home_safely, require_controller


def _key():
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        return sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def _show(log, mode, p, count):
    run = cc.cfg().get('run', {})
    vs = float(run.get('vel_scale', 1.0))
    if p.get('axis') is not None:
        body = f"axis {p['axis']} · amp {p.get('amp_mm')} mm · period {p.get('period_s')} s · acc {p.get('acc_mm_s2') or '기본'} mm/s²"
    else:
        body = f"J{p.get('joint')} · amp {p.get('amp_deg')}° · period {p.get('period_s')} s · tilt {p.get('tilt_deg') or 0}°"
    log.info(f'[{mode}] {body} · 횟수 {count} · 속도 {vs * 100:.0f} %')


def _yaml(mode, p, kind=''):
    keys = [k for k in ('axis', 'joint', 'amp_mm', 'amp_deg', 'cycles', 'period_s', 'acc_mm_s2', 'tilt_deg') if p.get(k) is not None]
    head = f'      {kind}:' if kind else f'    {mode}:'
    return f"{head} {{" + ', '.join(f'{k}: {p[k]}' for k in keys) + '}'


def main():
    ap = argparse.ArgumentParser(description='흔들기 튜닝 시험대')
    ap.add_argument('--mode', default='RINSE', choices=['RINSE', 'WASTE'])
    ap.add_argument('--kind', default='BOWL', choices=['BOWL', 'CUP'])
    ap.add_argument('--count', type=int, default=3, help='처음 횟수')
    a = ap.parse_args()
    if not sys.stdin.isatty():
        sys.exit('터미널에서 직접 실행한다 (키 입력이 필요하다)')

    cc.init('rig_shake_tune')
    log = cc.io_node().get_logger()
    require_controller(cc.io_node(), cc.cfg(), log)          # TS-07
    cfg = cc.cfg()
    p = sense.shake_params(cfg['f2'], a.mode, a.kind)         # 메모리 설정(종류별 묶음이면 그 종류) — 바꾸면 sense.shake 가 그대로 읽는다
    linear = p.get('axis') is not None
    count = a.count
    cfg.setdefault('run', {}).setdefault('vel_scale', 1.0)
    try:
        log.info('E15 — 먼저 HOME 으로 간다 (낮으면 곧게 올라온 뒤에 · 9/22 충돌)')
        go_home_safely(a.kind, log)
        log.info('준비됐다 — 키로 값을 바꾸고 **스페이스**를 누르면 한 번 턴다. h 키 설명 · q 끝내기')
        _show(log, a.mode, p, count)
        while True:
            k = _key()
            if k == 'q':
                log.info('끝낸다 — 로봇은 그 자리에 선다. 마지막 값(params.yaml 에 옮겨 적을 줄):\n'
                         + _yaml(a.mode, p, a.kind)); return
            if k == 'h':
                log.info('\n' + __doc__.split('🔰 키')[1].split('🔰 안전')[0].strip('─\n ')); continue
            if k in ('a', 'A'):
                key, step = ('amp_mm', 5.0) if linear else ('amp_deg', 5.0)
                p[key] = max(0.0, float(p.get(key) or 0.0) + (step if k == 'A' else -step))
            elif k in ('p', 'P'):
                p['period_s'] = round(max(0.05, float(p.get('period_s') or 0.5) + (0.05 if k == 'P' else -0.05)), 2)
            elif k in ('c', 'C') and linear:
                p['acc_mm_s2'] = max(0.0, float(p.get('acc_mm_s2') or 0.0) + (100.0 if k == 'C' else -100.0)) or None
            elif k in ('t', 'T') and not linear:
                p['tilt_deg'] = float(p.get('tilt_deg') or 0.0) + (10.0 if k == 'T' else -10.0)
            elif k in ('n', 'N'):
                count = max(1, count + (1 if k == 'N' else -1))
            elif k == 'v':
                run = cfg['run']
                run['vel_scale'] = 1.0 if float(run.get('vel_scale', 1.0)) < 1.0 else 0.3
            elif k == 'w':
                log.info('👉 이 줄을 params.yaml 의 f2.shake 밑에 그대로 옮겨 적는다:\n'
                         + _yaml(a.mode, p, a.kind)); continue
            elif k in (' ', 's'):
                _show(log, a.mode, p, count)
                r = sense.shake(a.mode, count, a.kind)         # 🚨 진짜 함수 — 자리로 가서(_goto) 흔들고 되돌아온다
                log.info(f'→ {r}' + ('' if r.ok else '   🚨 실패 — 값을 줄이거나 멈춘다'))
                continue
            else:
                continue
            _show(log, a.mode, p, count)
    except KeyboardInterrupt:
        log.warn('Ctrl+C — 로봇은 그 자리에 선다')
    finally:
        cc.shutdown()


if __name__ == '__main__':
    main()
