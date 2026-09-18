# src/
우리 ROS 2 패키지 8개가 여기에 들어간다: cobot_api(기능 함수 약속) · cobot_msgs(메시지) · cobot_common · f1_handling · f2_sense_flow · f3_wipe · f4_hmi · prewash_bringup (구조는 docs/03_설계_SDD.md §3)

노드는 `flow_node`(f2_sense_flow, 메인 프로그램)와 `hmi_bridge`(f4_hmi) 둘뿐이다. f1_handling · f3_wipe 와 f2_sense_flow 의 `sense.py` 는 flow_node 가 부르는 **파이썬 함수 모듈**이다(SDD §3.2).
