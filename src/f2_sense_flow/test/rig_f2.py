"""F2 단독 시험 스크립트 (SDD §3.2 · §10) — 내 함수만 직접 부른다.

    soc && python3 src/f2_sense_flow/test/rig_f2.py empty --kind BOWL     # 빈 용기 기준값 측정
    soc && python3 src/f2_sense_flow/test/rig_f2.py weigh                 # weigh 연속 3회
    soc && python3 src/f2_sense_flow/test/rig_f2.py loop --max-rounds 2
    soc && python3 src/f2_sense_flow/test/rig_f2.py shake --mode WASTE -n 5
    soc && python3 src/f2_sense_flow/test/rig_f2.py dip --kind CUP
    python3 src/f2_sense_flow/test/rig_f2.py weigh --no-robot             # 브링업 없이 반환만 확인

준비(손으로): 용기를 그리퍼에 쥐여 준다. weigh 시험은 100 g·200 g 추(TC-03).
같은 함수를 연속 3회 이상 부른다(SDD §3.2 ⑧ — "첫 번째만 되는" 결함은 한 번으로는 안 보인다).

🚨 로봇을 움직이기 전에 `rosinfo` 로 RANGE=LOCALHOST 인지 확인한다 (AGENTS §3 규칙 13).
   격리가 안 되어 있으면 내 movej 가 남의 Virtual·실기에도 간다.

파일 이름이 test_* 가 아니라서 pytest 는 모으지 않는다.
"""
import argparse
import sys

import cobot_common as cc
from cobot_api import F2Api, check_api

from f2_sense_flow import sense


def main():
    ap = argparse.ArgumentParser(description='F2 단독 시험')
    ap.add_argument('which', choices=['empty', 'weigh', 'loop', 'shake', 'dip'],
                    help="empty = 빈 용기 기준값 측정(params.yaml f2.empty_weight_g 에 넣을 값)")
    ap.add_argument('-n', type=int, default=3, help='연속 호출 횟수 (3 이상)')
    ap.add_argument('--kind', default='BOWL', choices=['BOWL', 'CUP'], help='용기 종류 (IRD §2)')
    ap.add_argument('--mode', default='WASTE', choices=['WASTE', 'RINSE'], help='shake 모드')
    ap.add_argument('--station', default='RINSE', choices=['RINSE'], help='dip 수조')
    ap.add_argument('--count', type=int, default=1, help='shake·dip 의 횟수 인자')
    ap.add_argument('--max-rounds', type=int, default=2, help='leftover_loop 의 최대 반복')
    ap.add_argument('--no-robot', action='store_true',
                    help='두산 드라이버 없이 (브링업 없이 함수 반환만 확인)')
    a = ap.parse_args()

    if a.which == 'empty':
        return _measure_empty(a)

    problems = check_api(sense, F2Api)               # 약속과 어긋나면 로봇을 켜기 전에 멈춘다
    if problems:
        sys.exit(f'cobot_api.F2Api 약속과 다름: {problems}')

    fn = {
        'weigh': lambda: sense.weigh(a.kind),
        'loop': lambda: sense.leftover_loop(a.kind, a.max_rounds),
        'shake': lambda: sense.shake(a.mode, a.count, a.kind),
        'dip': lambda: sense.dip(a.station, a.count, a.kind),
    }[a.which]

    cc.init('rig_f2', robot=not a.no_robot)          # ① 맨 앞에서 한 번
    log = cc.io_node().get_logger()
    if a.no_robot:
        log.warn('--no-robot — 두산 드라이버 없이 함수 반환만 확인한다')
    try:
        for i in range(a.n):                         # ② 연속 3회 이상
            log.info(f'{i + 1}/{a.n} {a.which} → {fn()}')
    finally:
        cc.shutdown()                                # ③ 끝낼 때 (Ctrl+C 포함)


def _measure_empty(a):
    """빈 용기 기준값 측정 — params.yaml 의 f2.empty_weight_g 에 넣을 값을 구한다.

    🚨 저울로 잰 진짜 무게를 넣으면 안 된다. 로봇 하중에는 정체불명 옵셋이 있어서
       (V-02: +42~45 g), 잔반 판정 `측정값 − 기준값` 이 상쇄되려면 **같은 경로·같은 자세**로
       잰 값이어야 한다. 저울 값을 넣으면 빈 용기가 잔반 43 g 으로 보인다.

    🚨 자세가 달라지면 옵셋도 달라질 수 있다(V-02 §3 미확인 항목).
       티칭이 끝나면 WEIGH 자세에서 다시 재는 것이 정확하다.
       브링업을 다시 했으면(다른 세션) 값이 달라질 수 있으니 시연 날 아침에 다시 잰다.
    """
    cc.init('rig_f2', robot=not a.no_robot)
    log = cc.io_node().get_logger()
    try:
        samples = cc.cfg()['f2']['weigh_samples']
        log.info(f'빈 {a.kind} 을(를) 그리퍼에 물린 상태에서 {a.n}회 잰다 (회당 {samples} 표본)')
        got = []
        for i in range(a.n):
            g = cc.weigh(samples)                    # 내 cobot_common/weigh.py
            got.append(g)
            log.info(f'  {i + 1}/{a.n}  {g:.1f} g')
        got.sort()
        mid = got[len(got) // 2] if len(got) % 2 else (got[len(got) // 2 - 1] + got[len(got) // 2]) / 2
        log.info(f'중앙값 {mid:.1f} g  (폭 {max(got) - min(got):.1f} g)')
        log.info(f'→ params.yaml 의 f2.empty_weight_g.{a.kind} 에 {round(mid)} 을(를) 넣으세요')
        if max(got) - min(got) > 20:
            log.warn('회차 간 폭이 20 g 을 넘는다 — 로봇을 완전히 멈추고 다시 재는 것이 좋다')
    finally:
        cc.shutdown()


if __name__ == '__main__':
    main()
