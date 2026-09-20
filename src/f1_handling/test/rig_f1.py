"""F1 단독 시험 스크립트 (SDD §3.2 · §10) — 내 함수만 직접 부른다.

    rosinfo                                                        # 🚨 먼저 RANGE=LOCALHOST(격리) 확인 — AGENTS 규칙 13
    soc && python3 src/f1_handling/test/rig_f1.py pick --zone RET_B --kind BOWL      # pick 연속 3회
    soc && python3 src/f1_handling/test/rig_f1.py place --station SPONGE_BED_B
    soc && python3 src/f1_handling/test/rig_f1.py move_to --station WEIGH --carrying
    soc && python3 src/f1_handling/test/rig_f1.py tool --tool SPONGE --action PICK -n 5
    soc && python3 src/f1_handling/test/rig_f1.py rack_place --slot RACK_B1 --kind BOWL
    soc && python3 src/f1_handling/test/rig_f1.py pick --no-robot                     # 브링업 없이 함수 반환만 확인(🚧 골격 함수만)
  Virtual 에서 (cell.yaml 의 limits·motion 이 아직 비어 있는 동안):
    soc && python3 src/f1_handling/test/rig_f1.py move_to --station WEIGH --carrying --kind CUP --fill-virtual
    soc && python3 src/f1_handling/test/rig_f1.py place --station SPONGE_BED_B --fill-virtual --no-gripper
      --fill-virtual : 비어 있는 limits·motion 만 Virtual 시험 값(cobot_common/test/rig_coords.yaml)으로 채운 임시 사본으로 돈다. 🚨 Virtual 이 아니면 거부한다
      --no-gripper   : cc.release() 를 로그만 남기는 가짜로 바꾼다(그리퍼 드라이버가 없는 환경에서 이동·순서만 볼 때)

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
    ap.add_argument('--fill-virtual', action='store_true', help='비어 있는 limits·motion 을 Virtual 시험 값으로 채운 임시 설정으로 돈다(Virtual 전용)')
    ap.add_argument('--no-gripper', action='store_true', help='cc.release() 를 가짜로 — 그리퍼 드라이버 없이 이동·순서만 확인')
    a = ap.parse_args()
    if a.fill_virtual:
        _use_filled_config()

    problems = check_api(handling, F1Api)
    if problems:
        sys.exit(f'cobot_api.F1Api 약속과 다름: {problems}')

    fn = {'pick': lambda: handling.pick(a.zone, a.kind),
          'place': lambda: handling.place(a.station, a.kind),              # kind 는 종류별 자리(ISOLATE …)에서만 쓰인다
          'move_to': lambda: handling.move_to(a.station, a.carrying, a.kind),
          'tool': lambda: handling.tool(a.tool, a.action),
          'rack_place': lambda: handling.rack_place(a.slot, a.kind)}[a.which]

    cc.init('rig_f1', robot=not a.no_robot)                 # ① 맨 앞에서 한 번
    log = cc.io_node().get_logger()
    try:
        if a.fill_virtual:
            from cobot_common.bootstrap import dsr          # rig 의 안전 확인용 — 기능 코드에서는 쓰지 않는다
            if dsr().get_robot_system() != dsr().ROBOT_SYSTEM_VIRTUAL:
                log.error('--fill-virtual 은 Virtual 전용이다(시험 값으로 실기를 움직이지 않는다) → 실행하지 않는다')
                return
        if a.no_gripper:
            def fake_release():
                from cobot_common.bootstrap import dsr
                z = float(dsr().get_current_posx(ref=dsr().DR_BASE)[0][2]) if not a.no_robot else float('nan')
                log.info(f'  (가짜) release — 그리퍼 명령은 보내지 않았다 · 이 순간 TCP 높이 z = {z:.1f} mm')
            cc.release = fake_release                       # handling.cc 는 같은 모듈이라 같이 바뀐다
        if not a.no_robot and a.which in ('place', 'move_to'):
            log.info('시작 자세 HOME 으로 — 공정은 HOME 에서 시작한다(켠 직후의 곧게 편 자세는 특이점이라 직선 이동이 안 먹는다)')
            cc.move_to('HOME', False)
        for i in range(a.n):                                # ② 연속 3회 이상
            log.info(f'{i + 1}/{a.n} {a.which} → {fn()}')
    except KeyboardInterrupt:
        log.warn('Ctrl+C — 정지 명령을 보내고 끝낸다')
    finally:
        cc.shutdown()                                       # ③ 끝낼 때 (Ctrl+C 포함)


def _use_filled_config():
    """진짜 설정의 사본을 만들고 비어 있는 limits·motion 만 Virtual 시험 값으로 채운다(cobot_common/test/rig_coords.py 의 방식 그대로)."""
    import os
    from pathlib import Path

    import yaml
    common_test = Path(__file__).resolve().parents[2] / 'cobot_common' / 'test'
    sys.path.insert(0, str(common_test))
    import rig_coords
    with open(common_test / 'rig_coords.yaml', encoding='utf-8') as f:
        os.environ['PREWASH_CONFIG_DIR'] = str(rig_coords._filled_copy(yaml.safe_load(f)['fill']))


if __name__ == '__main__':
    main()
