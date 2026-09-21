# -*- coding: utf-8 -*-
"""F3 실기 시험용 설정 묶음을 만든다 — 박진용 (V-10 · F3-02 재검증).

    python3 src/f3_wipe/test/make_cfg_f3.py            → logs/cfg_f3/ 에 cell.yaml · params.yaml 을 쓴다
    export PREWASH_CONFIG_DIR=$PWD/logs/cfg_f3          → 이 터미널의 rig 가 그 설정을 읽는다

왜: cell.yaml 의 limits·motion 이 main 에서 비어 있어 공용 이동 함수(move_to·move_rel)가 로봇을 움직이지 않는다.
    cell.yaml 을 고치지 않고, 좌표·힘 설정은 **지금 저장소 값 그대로** 두고 비어 있는 칸만 아래 값으로 채운다.
    (이미 값이 있는 칸은 건드리지 않는다 — 누가 cell.yaml 을 채우면 그 값이 이긴다.)

채우는 값
  속도 — 한석형 9/20 실기 티칭 rig(seokhyung/20260919-CELL-04-teaching · rig_f1.py)의 관절 20 °/s·가속 40,
         직선 60 mm/s·가속 120 을 **vel_scale 0.3 일 때 실제 속도**가 되게 100 % 기준을 적는다.
         컵 문지르기(move_line)는 이 값도 vel_scale 도 쓰지 않는다 — params.yaml f3.wipe_cup 의 실제 속도 그대로.
  힘·시간 — 바닥 판정 contact_limit_n 2 N(V-03 9/20 실기) · insert_limit_n 5 N · timeout_s 20 s(박진용 9/21).
  safe_z_mm · vel_free_pct 는 닦기(wipe_bowl·wipe_cup)가 쓰지 않아 비워 둔다.
"""
import os
import sys

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, '..', '..', 'cobot_common', 'config')
OUT = os.path.join('logs', 'cfg_f3')                 # 실행 위치(저장소 루트) 기준 — logs/ 는 git 이 무시한다

SCALE = 0.3                                          # rig 의 첫 실기 상한 — 이 값에서 아래 속도가 실제 속도가 된다
FILL = {
    'limits': {
        'vel_carry_pct': 100,
        'contact_limit_n': 2.0,
        'insert_limit_n': 5.0,
        'timeout_s': 20.0,
    },
    'motion': {
        'vel_tcp_max_mm_s': 60.0 / SCALE,                # 200 → 60 mm/s
        'acc_tcp_max_mm_s2': 120.0 / SCALE,              # 400 → 120 mm/s²
        'vel_joint_max_deg_s': 20.0 / SCALE,             # 66.7 → 20 °/s
        'acc_joint_max_deg_s2': 40.0 / SCALE,            # 133.3 → 40 °/s²
        'move_timeout_s': 60.0,
    },
}


def main():
    with open(os.path.join(SRC, 'cell.yaml'), encoding='utf-8') as f:
        cell = yaml.safe_load(f)
    filled = []
    for sec, kv in FILL.items():
        node = cell['cell'].setdefault(sec, {})
        for k, v in kv.items():
            if node.get(k) is None:
                node[k] = round(v, 1)
                filled.append(f'cell.{sec}.{k} = {node[k]:g}')
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, 'cell.yaml'), 'w', encoding='utf-8') as f:
        yaml.safe_dump(cell, f, allow_unicode=True, sort_keys=False)
    with open(os.path.join(SRC, 'params.yaml'), encoding='utf-8') as fi, \
            open(os.path.join(OUT, 'params.yaml'), 'w', encoding='utf-8') as fo:
        fo.write(fi.read())
    print('채운 칸:\n  ' + '\n  '.join(filled or ['(없음 — cell.yaml 이 이미 채워져 있다)']))
    print(f'\n다음 줄을 실행한다:\n  export PREWASH_CONFIG_DIR={os.path.abspath(OUT)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
