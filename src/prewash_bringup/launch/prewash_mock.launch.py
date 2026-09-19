# -*- coding: utf-8 -*-
"""로봇·드라이버 없이 (PC 1대) — flow_node(기능 전부 mock) + hmi_bridge. flow·HMI 개발과 INT-4 용. SDD §10

    soc && ros2 launch prewash_bringup prewash_mock.launch.py            # 브링업(sodvir) 필요 없음
    → 브라우저 http://localhost:8000

use_mock 이 "f1,f2,f3" 전부면 flow_node 가 cobot_common.init(robot=False) 로 시작한다(SDD §5.1).
"""
from prewash_bringup.launch_common import make_description


def generate_launch_description():
    return make_description(use_mock='f1,f2,f3', vel_scale='1.0', hmi='true')
