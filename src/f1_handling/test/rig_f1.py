"""F1 단독 시험 스크립트 (SDD §3.2 · §10) — 내 함수만 직접 부른다.

    rosinfo                                                        # 🚨 먼저 RANGE=LOCALHOST(격리) 확인 — AGENTS 규칙 13
    soc && python3 src/f1_handling/test/rig_f1.py pick --zone RET_B --kind BOWL      # pick 연속 3회
    soc && python3 src/f1_handling/test/rig_f1.py place --station SPONGE_BED_B
    soc && python3 src/f1_handling/test/rig_f1.py move_to --station WEIGH --carrying
    soc && python3 src/f1_handling/test/rig_f1.py tool --tool SPONGE --action PICK -n 5
    soc && python3 src/f1_handling/test/rig_f1.py rack_place --slot RACK_B1 --kind BOWL
    soc && python3 src/f1_handling/test/rig_f1.py pick --no-robot                     # 브링업 없이 함수 반환만 확인

준비(손으로): 시험할 함수의 시작 조건을 만들어 준다 — pick 은 반납 구역에 용기, place·rack_place 는 용기를 그리퍼에 쥐여 줌,
tool PICK 은 홀더에 툴. 같은 함수를 연속 3회 이상 부른다(SDD §3.2 ⑧ — "첫 번째만 되는" 결함은 한 번으로는 안 보인다).
실기에서는 속도를 낮춘다:  PREWASH_VEL_SCALE=0.3 python3 …/rig_f1.py …   (첫 실기 20~30 %, AGENTS 규칙 1)
파일 이름이 test_* 가 아니라서 pytest 는 모으지 않는다.
"""
import argparse
import sys

import cobot_common as cc
from cobot_api import BOWL, BRUSH, CUP, PICK, RACK_SLOTS, RET_B, RET_C, RETURN, SPONGE, STATIONS, F1Api, check_api
from f1_handling import handling

BEDS = ('SPONGE_BED_B', 'SPONGE_BED_C')


def main():
    ap = argparse.ArgumentParser(description='F1 단독 시험')
    ap.add_argument('which', choices=['pick', 'place', 'move_to', 'tool', 'rack_place'])
    ap.add_argument('-n', type=int, default=3, help='연속 호출 횟수 (3 이상)')
    ap.add_argument('--zone', default=RET_B, choices=(RET_B, RET_C) + BEDS, help='pick: 반납 구역 또는 스펀지 홈(재파지)')
    ap.add_argument('--kind', default=BOWL, choices=(BOWL, CUP), help='pick · rack_place')
    ap.add_argument('--station', default='HOME', choices=STATIONS, help='place · move_to')
    ap.add_argument('--carrying', action='store_true', help='move_to: 들고 이동(저속)')
    ap.add_argument('--tool', default=SPONGE, choices=(SPONGE, BRUSH))
    ap.add_argument('--action', default=PICK, choices=(PICK, RETURN))
    ap.add_argument('--slot', default=RACK_SLOTS[0], choices=RACK_SLOTS, help='rack_place')
    ap.add_argument('--no-robot', action='store_true', help='두산 드라이버 없이 시작(init(robot=False)) — 골격·반환값 확인용')
    a = ap.parse_args()

    problems = check_api(handling, F1Api)
    if problems:
        sys.exit(f'cobot_api.F1Api 약속과 다름: {problems}')

    fn = {'pick': lambda: handling.pick(a.zone, a.kind),
          'place': lambda: handling.place(a.station),
          'move_to': lambda: handling.move_to(a.station, a.carrying),
          'tool': lambda: handling.tool(a.tool, a.action),
          'rack_place': lambda: handling.rack_place(a.slot, a.kind)}[a.which]

    cc.init('rig_f1', robot=not a.no_robot)                 # ① 맨 앞에서 한 번
    log = cc.io_node().get_logger()
    try:
        for i in range(a.n):                                # ② 연속 3회 이상
            log.info(f'{i + 1}/{a.n} {a.which} → {fn()}')
    except KeyboardInterrupt:
        log.warn('Ctrl+C — 정지 명령을 보내고 끝낸다')
    finally:
        cc.shutdown()                                       # ③ 끝낼 때 (Ctrl+C 포함)


if __name__ == '__main__':
    main()
