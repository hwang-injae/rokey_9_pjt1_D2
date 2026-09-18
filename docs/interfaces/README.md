# docs/interfaces — 메시지 정본

| 파일 | 쓰는 곳 |
|---|---|
| `FlowState.msg` | `/flow/state` (flow_node → hmi_bridge, 2 Hz) |
| `FlowEvent.msg` | `/flow/event` (용기 1개 완료·격리·오류마다 1건) |

`src/cobot_msgs/msg/`에 **그대로 복사**해 빌드한다(PM 관리). 기능 함수의 약속(인자·반환·코드)은 메시지가 아니라 [`src/cobot_api/cobot_api/contracts.py`](../../src/cobot_api/cobot_api/contracts.py)가 정본이다. 설명은 [../02_인터페이스_IRD.md](../02_인터페이스_IRD.md).

v2.1까지 있던 서비스 정의 12개(`F1Pick.srv` …)는 9/18 구조 변경(스크립트형)으로 삭제했다. 같은 이름·인자·반환 필드가 `cobot_api`의 함수 서명으로 옮겨졌다.
