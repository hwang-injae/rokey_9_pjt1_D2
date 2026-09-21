"""하중 센서 원값 탐침 — 🚨 읽기만 한다, 로봇·그리퍼를 움직이지 않는다 (민범진 · V-02 사전 확인).

    soc && python3 src/cobot_common/test/rig_weigh_probe.py            # 5회
    soc && python3 src/cobot_common/test/rig_weigh_probe.py -n 10

왜: 9/21 첫 실기에서 그릇을 쥔 채 `get_workpiece_weight()` 가 "0.1, 0.0, 0.0" 으로 읽혔다.
    weigh.py 는 소수 첫째 자리까지만 찍어서 **단위(kg 인지 g 인지)** 를 알 수 없었다.
    여기서는 소수 4자리 원값과 시각을 그대로 보여 준다. 판정하지 않는다.
"""
import argparse
import statistics
import time

import cobot_common as cc
from cobot_common.bootstrap import dsr


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('-n', type=int, default=5)
    ap.add_argument('--gap', type=float, default=0.5, help='읽기 사이 대기(s)')
    a = ap.parse_args()
    cc.init('rig_weigh_probe')
    log = cc.io_node().get_logger()
    vals = []
    try:
        d = dsr()
        log.info(f'원값 {a.n}회 — 로봇은 움직이지 않는다')
        for i in range(a.n):
            t0 = time.monotonic()
            v = d.get_workpiece_weight()
            log.info(f'  {i + 1:2d}  {v!r:>12}   ({time.monotonic() - t0:.2f} s)')
            if isinstance(v, (int, float)) and v >= 0:
                vals.append(float(v))
            time.sleep(a.gap)
        if vals:
            med = statistics.median(vals)
            log.info(f'중앙값 {med:.4f} · 최소 {min(vals):.4f} · 최대 {max(vals):.4f} · 폭 {max(vals) - min(vals):.4f}')
            log.info(f'→ kg 이라면 {med * 1000:.1f} g / g 이라면 {med:.1f} g')
    finally:
        cc.shutdown()


if __name__ == '__main__':
    main()
