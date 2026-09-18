cmake_minimum_required(VERSION 3.8)
project(cobot_msgs)

# 메시지·서비스 정의만 담는 패키지다. 노드 코드는 각 기능 패키지에 둔다.
find_package(ament_cmake REQUIRED)
find_package(rosidl_default_generators REQUIRED)
find_package(builtin_interfaces REQUIRED)   # FlowState/FlowEvent 의 stamp

# IRD v2.0 §3~7 · 정본은 docs/interfaces/ (파일 내용은 그대로 복사한 것)
rosidl_generate_interfaces(${PROJECT_NAME}
  # --- msg 2 (flow → HMI) ---
  "msg/FlowState.msg"
  "msg/FlowEvent.msg"
  # --- srv 5 : F1 파지·이송·적재 (한석형) ---
  "srv/F1Pick.srv"
  "srv/F1Place.srv"
  "srv/F1MoveTo.srv"
  "srv/F1Tool.srv"
  "srv/F1RackPlace.srv"
  # --- srv 4 : F2 무게·털기·헹굼 (민범진) ---
  "srv/F2Weigh.srv"
  "srv/F2LeftoverLoop.srv"
  "srv/F2Shake.srv"
  "srv/F2Dip.srv"
  # --- srv 3 : F3 접촉 닦기 (박진용) ---
  "srv/F3Seat.srv"
  "srv/F3Soap.srv"
  "srv/F3Wipe.srv"
  DEPENDENCIES builtin_interfaces
)

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  ament_lint_auto_find_test_dependencies()
endif()

ament_export_dependencies(rosidl_default_runtime)
ament_package()
