"""PreWash-Cell 공용 로봇 함수 모음. 문서: docs/03_설계_SDD.md §3.1(함수 표) · §3.2(실행 뼈대 규약)

    import cobot_common as cc
    cc.init('rig_f1')  →  cc.move_to('HOME', False) · cc.cfg()['f1'] · cc.io_node()  →  cc.shutdown()

사람별 파일 — 자기 파일만 고친다 (AGENTS.md §2)
    bootstrap.py · config.py · __init__.py   황인재   init · io_node · cfg · shutdown · config.load
    motion.py                                황인재   move_to · move_rel · move_joint_rel
    gripper.py                               민범진   grip · grip_level · release · grip_width
    weigh.py                                 민범진   weigh
    force.py                                 박진용   force_on/off · force_reached · contact_down · periodic_search · safe_retreat ·
                                                      where · motion_done · move_spiral · move_arc (닦기 접촉 모션)

함수를 추가할 때 이 파일은 고치지 않는다. 자기 파일의 `__all__` 에 이름을 넣으면 `cc.함수()` 로 보인다.
이 파일은 두산 API 를 import 하지 않는다(import 만으로는 드라이버·ws_dsr 이 필요 없다).
"""
from . import config                                          # noqa: F401
from .bootstrap import cfg, init, io_node, shutdown           # noqa: F401
from .force import *                                          # noqa: F401,F403
from .gripper import *                                        # noqa: F401,F403
from .motion import *                                         # noqa: F401,F403
from .weigh import *                                          # noqa: F401,F403
