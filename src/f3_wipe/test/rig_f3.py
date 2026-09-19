"""F3 단독 시험 스크립트 (SDD §3.2 · §10) — 내 함수만 직접 부른다.

    soc && python3 src/f3_wipe/test/rig_f3.py bowl            # wipe_bowl 연속 3회
    soc && python3 src/f3_wipe/test/rig_f3.py soap --soap-count 2
    soc && python3 src/f3_wipe/test/rig_f3.py cup -n 5

준비(손으로): 스펀지 홈에 그릇·컵을 놓고, 툴(그릇=수세미 툴, 컵=솔)을 그리퍼에 쥐여 준다.
같은 함수를 연속 3회 이상 부른다(SDD §3.2 ⑧ — "첫 번째만 되는" 결함은 한 번으로는 안 보인다).
파일 이름이 test_* 가 아니라서 pytest 는 모으지 않는다.
"""
import argparse
import sys

from cobot_api import F3Api, check_api
from f3_wipe import wipe

try:
    import cobot_common as cc
except ModuleNotFoundError as e:
    if e.name != 'cobot_common':  # cobot_common 은 있는데 그 안에서 난 import 오류(DR_init 등)는 그대로 보여 준다
        raise
    cc = None  # INF-02a(bootstrap) 가 main 에 들어오기 전 — 로봇 없이 함수 호출만 확인


def main():
    ap = argparse.ArgumentParser(description='F3 단독 시험')
    ap.add_argument('which', choices=['soap', 'bowl', 'cup'])
    ap.add_argument('-n', type=int, default=3, help='연속 호출 횟수 (3 이상)')
    ap.add_argument('--soap-count', type=int, default=3, help='soap(count) 인자 — flow 호출 예시(IRD §8)와 같게')
    a = ap.parse_args()

    problems = check_api(wipe, F3Api)
    if problems:
        sys.exit(f'cobot_api.F3Api 약속과 다름: {problems}')

    fn = {'soap': lambda: wipe.soap(a.soap_count), 'bowl': wipe.wipe_bowl, 'cup': wipe.wipe_cup}[a.which]

    if cc is not None:
        cc.init('rig_f3')                                   # ① 맨 앞에서 한 번
        log = cc.io_node().get_logger()
    else:
        import rclpy.logging
        log = rclpy.logging.get_logger('rig_f3')
        log.warning('cobot_common 없음(INF-02a 전) — 로봇 없이 함수 반환만 확인')
    try:
        for i in range(a.n):                                # ② 연속 3회 이상
            log.info(f'{i + 1}/{a.n} {a.which} → {fn()}')
    finally:
        if cc is not None:
            cc.shutdown()                                   # ③ 끝낼 때 (Ctrl+C 포함)


if __name__ == '__main__':
    main()
