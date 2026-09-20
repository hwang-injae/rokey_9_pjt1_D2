# f4_hmi — 시스템 모니터(웹 HMI) · 담당 황인재

설계: `docs/ref/20260920_F4-00_HMI_설계초안.md` · 인터페이스: IRD §6

| 프로그램 | 역할 | 실행 |
|---|---|---|
| `hmi_bridge` | ROS 방송(`/flow/state` 등)을 듣고 브라우저에 전달하고(REST · WebSocket), 버튼을 flow 의 서비스로 전하는 서버 | `ros2 run f4_hmi hmi_bridge` → http://localhost:8000 |
| `fake_state_pub` | **가짜 flow** — 대본대로 실제 flow 와 같은 토픽을 방송하고 버튼(`/flow/start·stop·resume·abort`)에 반응(로봇·브링업 불필요) | `ros2 run f4_hmi fake_state_pub [대본] [--speed N] [--once] [--wait-start]` |

대본(`scenarios/*.yaml`): `normal` 정상 · `isolate` 격리 · `error` 로봇 오류로 멈춤 · `paused` 일시정지→재개 · `empty_zone` 빈 구역.
🚨 `fake_state_pub` 와 실제 `flow_node` 를 **동시에 띄우지 않는다**(같은 토픽에 두 곳이 방송한다).

## 🔒 접속·버튼
- 접속은 **이 PC 의 브라우저에서만**(`params.yaml` 의 `hmi.host: 127.0.0.1` — 결정 E10). 태블릿에서 보려면 `0.0.0.0` 으로 바꾸고, 끝나면 되돌린다.
- 버튼(`POST /api/*`)은 `X-PreWash` 헤더가 있어야 받는다(F4-02b). 이 PC 브라우저로 연 **다른 웹페이지**가 몰래 시작을 누르는 것을 막는다.
  `curl` 로 눌러 볼 때도 붙인다: `curl -X POST -H 'X-PreWash: 1' localhost:8000/api/stop`

## 한 번만: 웹 서버 부품 설치 (HMI 를 돌리는 PC 에서만)
```bash
python3 -m venv --system-site-packages ~/venvs/hmi
~/venvs/hmi/bin/pip install fastapi "uvicorn[standard]" websockets
```
상자(venv)를 열지 않아도 된다 — `hmi_bridge` 가 `params.yaml` 의 `hmi.venv_dir` 에서 부품을 찾아 붙인다. 다른 팀원 PC 는 설치할 필요 없다(빌드·시험은 그대로 통과).

## 진행
- [x] F4-01 가짜 flow + 서버 뼈대 + 시험 페이지(`GET /api/state`)
- [x] F4-02 버튼(start·stop·resume·abort) · WebSocket `/ws/state` · 가짜 flow 의 버튼 응답(`--wait-start`)
- [x] F4-02b 버튼 요청에 `X-PreWash` 헤더 요구
- [ ] F4-03 화면(Next.js 15) · F4-04 이력(SQLite) · F4-05 KPI

## 시험
```bash
python3 -m pytest -q src/f4_hmi                 # 웹 부품이 없으면 app 시험 1건은 건너뛴다
~/venvs/hmi/bin/python -m pytest -q src/f4_hmi  # 전부 실행
```
