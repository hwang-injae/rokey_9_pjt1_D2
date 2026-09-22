# ROS 2 노드 구조도 (NOTE-01) — 9/22 기준. 사각형 = 노드 · 타원 = 토픽 · 점선 상자 = 파이썬 패키지(노드 아님)
#   python3 tools/gen/draw_ros2_nodes.py docs/images/ros2_node_structure.svg
#   google-chrome --headless=new --hide-scrollbars --window-size=1680,1070 --screenshot=docs/images/ros2_node_structure.png file://$PWD/docs/images/ros2_node_structure.svg
#   (노션에는 PNG 를 올린다 · 구조가 바뀌면 이 파일을 고치고 둘 다 다시 만든다)
import sys
W, H = 1680, 1070
out = []
FONT = "'Noto Sans KR','Noto Sans CJK KR','IBM Plex Sans KR',sans-serif"

def esc(t): return t.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

def text(x, y, lines, size=15, weight=400, color='#1c2430', anchor='middle', lh=None):
    lh = lh or size * 1.35
    for i, t in enumerate(lines if isinstance(lines, list) else [lines]):
        out.append(f'<text x="{x}" y="{y + i * lh:.1f}" font-size="{size}" font-weight="{weight}" fill="{color}" text-anchor="{anchor}">{esc(t)}</text>')

def box(x, y, w, h, fill, stroke, dash=None, r=10, sw=2):
    d = f' stroke-dasharray="{dash}"' if dash else ''
    out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{d}/>')

def node(x, y, w, h, title, sub, fill='#e8f1ff', stroke='#2f6fde'):
    box(x, y, w, h, fill, stroke, r=8, sw=2.5)
    text(x + w / 2, y + 30, title, 18, 700)
    text(x + w / 2, y + 54, sub, 13.5, 400, '#3d4a5c')

def pkg(x, y, w, h, title, sub):
    box(x, y, w, h, '#f6f7f9', '#8a94a6', dash='7 5', r=8, sw=1.8)
    text(x + w / 2, y + 26, title, 15.5, 700, '#2c3440')
    text(x + w / 2, y + 48, sub, 13, 400, '#56657a')

def topic(cx, cy, rx, ry, name, sub):
    out.append(f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" fill="#fff4d6" stroke="#d49a1a" stroke-width="2.5"/>')
    text(cx, cy - 4, name, 18, 700)
    text(cx, cy + 18, sub, 13, 400, '#6b4e10')

def arrow(pts, color='#2c3440', dash=None, w=2.2, label=None, lx=None, ly=None, lanchor='middle', lsize=13, lcolor=None):
    d = 'M' + ' L'.join(f'{x} {y}' for x, y in pts)
    dd = f' stroke-dasharray="{dash}"' if dash else ''
    mid = {'#2c3440': 'k', '#2f6fde': 'b', '#d49a1a': 'o', '#8a94a6': 'g', '#b3261e': 'r'}[color]
    out.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{w}"{dd} marker-end="url(#a{mid})"/>')
    if label:
        for i, t in enumerate(label if isinstance(label, list) else [label]):
            tw = len(t) * lsize * 0.62
            bx = lx - tw / 2 if lanchor == 'middle' else lx - 4
            out.append(f'<rect x="{bx:.0f}" y="{ly - lsize + i * lsize * 1.35 - 2:.0f}" width="{tw + 8:.0f}" height="{lsize * 1.35:.0f}" fill="#ffffff" opacity=".92"/>')
        text(lx, ly, label, lsize, 500, lcolor or color, anchor=lanchor)

markers = ''.join(f'<marker id="a{k}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10 z" fill="{c}"/></marker>'
                  for k, c in (('k', '#2c3440'), ('b', '#2f6fde'), ('o', '#d49a1a'), ('g', '#8a94a6'), ('r', '#b3261e')))

# ── 제목 · 범례
text(40, 44, 'PreWash-Cell · ROS 2 노드 구조 (2026-09-22 기준)', 26, 800, anchor='start')
text(40, 72, '우리가 만든 노드는 2개(flow_node · hmi_bridge). 기능 F1·F2·F3 는 노드가 아니라 flow_node 가 차례로 부르는 파이썬 함수다. ROS 통신은 flow ↔ HMI 와 드라이버뿐.', 15, 400, '#3d4a5c', anchor='start')
lg_x = 1270
box(lg_x, 22, 380, 76, '#ffffff', '#c5ccd6', r=8, sw=1.2)
box(lg_x + 14, 36, 34, 20, '#e8f1ff', '#2f6fde', r=4, sw=2); text(lg_x + 56, 51, '노드', 13, 500, anchor='start')
out.append(f'<ellipse cx="{lg_x + 128}" cy="46" rx="20" ry="11" fill="#fff4d6" stroke="#d49a1a" stroke-width="2"/>'); text(lg_x + 154, 51, '토픽', 13, 500, anchor='start')
box(lg_x + 208, 36, 34, 20, '#f6f7f9', '#8a94a6', dash='5 4', r=4, sw=1.5); text(lg_x + 250, 51, '패키지(노드 아님)', 13, 500, anchor='start')
out.append(f'<path d="M{lg_x + 14} 80 H{lg_x + 50}" stroke="#2c3440" stroke-width="2" marker-end="url(#ak)"/>'); text(lg_x + 56, 85, '서비스 호출', 13, 500, anchor='start')
out.append(f'<path d="M{lg_x + 142} 80 H{lg_x + 178}" stroke="#d49a1a" stroke-width="2" stroke-dasharray="6 4" marker-end="url(#ao)"/>'); text(lg_x + 184, 85, '토픽 발행', 13, 500, anchor='start')
out.append(f'<path d="M{lg_x + 262} 80 H{lg_x + 298}" stroke="#8a94a6" stroke-width="2" marker-end="url(#ag)"/>'); text(lg_x + 304, 85, '함수 호출', 13, 500, anchor='start')

# ── PC-A
box(30, 118, 1000, 910, '#ffffff', '#2c3440', r=14, sw=2.5)
text(52, 150, 'PC-A · 로봇 제어 PC (한석형 PC) — Ubuntu 24.04 · ROS 2 Jazzy · ROS_DOMAIN_ID 60', 17, 800, anchor='start')

# flow_node 프로세스
box(60, 172, 700, 520, '#fbfcfe', '#2f6fde', dash='10 6', r=12, sw=2)
text(80, 200, 'flow_node 프로세스 1개 — 패키지 f2_sense_flow (메인 프로그램 · 민범진)', 15.5, 700, '#2f6fde', anchor='start')
node(90, 218, 320, 96, 'flow_node_dsr', '두산 API 전용 보조 노드 (cc.init 이 만든다)', '#e8f1ff', '#2f6fde')
text(250, 300, 'cobot_common 이 두산 API 를 이 노드로 부른다', 12, 400, '#3d4a5c')
node(430, 218, 310, 96, 'flow_node (통신 노드)', '서비스 4 · 발행 2 · 상태 2 Hz 타이머', '#e8f1ff', '#2f6fde')
text(585, 300, '콜백은 값 저장·깃발 세우기만(로봇 명령 금지)', 12, 400, '#b3261e')
box(90, 336, 650, 58, '#eef7ee', '#3f8f4f', r=8, sw=2)
text(415, 360, '메인 스레드 — 공정 순서 실행 (flow.py 상태 머신)', 16, 700, '#1f5e2c')
text(415, 382, '집기 → 무게 → 털기 → 안착 → 세제 → 닦기 → 헹굼 → 적재 · 로봇 함수는 여기서만 부른다(SDD §3.2)', 12.5, 400, '#1f5e2c')
pkg(90, 416, 205, 92, 'f1_handling', 'pick · place · move_to')
text(192, 486, 'tool · rack_place (한석형 · 황인재)', 12.5, 400, '#56657a')
pkg(312, 416, 205, 92, 'f2_sense_flow.sense', 'weigh · leftover_loop')
text(414, 486, 'shake · dip (민범진)', 12.5, 400, '#56657a')
pkg(534, 416, 206, 92, 'f3_wipe', 'soap · wipe_bowl')
text(637, 486, 'wipe_cup (박진용)', 12.5, 400, '#56657a')
for cx in (192, 414, 637):
    arrow([(cx, 394), (cx, 414)], '#8a94a6', w=2)
pkg(90, 530, 650, 70, 'cobot_common (공용 로봇 함수 · 4명 분담) + cobot_api (함수 약속)', '초기화 · 이동 · 일시 정지/재개/정지 · 그리퍼 · 무게 · 힘 함수 · 설정 cell.yaml + params.yaml')
for cx in (192, 414, 637):
    arrow([(cx, 508), (cx, 528)], '#8a94a6', w=2)
text(400, 628, '기능 함수 12개는 ROS 통신이 아니라 같은 프로세스 안의 파이썬 함수 호출 — 실패는 예외가 아니라 Result.code', 13, 500, '#3d4a5c')
text(400, 650, '(개발 때는 f2_sense_flow.mock 이 같은 이름의 가짜 함수를 준다 → 로봇·남의 코드 없이 flow 시험)', 12.5, 400, '#56657a')

# 드라이버 노드
node(90, 750, 360, 100, 'dsr_controller2 (/dsr01)', '두산 드라이버 — 강사 배포 m0609_rg2_bringup', '#eef1f5', '#56657a')
text(270, 838, 'sodreal = bringup mode:=real', 12, 400, '#3d4a5c')
node(560, 750, 380, 100, 'OnRobot RG2 드라이버', 'onrobot_rg_control (OnRobotRGControllerServer)', '#eef1f5', '#56657a')
text(750, 838, '강사 배포 · 명령은 문자열 1개', 12, 400, '#3d4a5c')
out.append('<path d="M90 266 L74 266 L74 800 L88 800" fill="none" stroke="#2c3440" stroke-width="2.2" marker-end="url(#ak)"/>')
text(84, 712, 'motion/move_joint · move_line · move_pause · move_resume · move_stop', 12, 500, '#2c3440', anchor='start')
text(84, 732, 'force/task_compliance_ctrl · set_desired_force · get_workpiece_weight … (dsr_msgs2/srv)', 12, 500, '#2c3440', anchor='start')
arrow([(728, 600), (728, 748)], '#2c3440')
text(738, 722, '/onrobot/sendCommand (srv)', 12.5, 600, '#2c3440', anchor='start')
out.append('<path d="M880 748 L880 565 L744 565" fill="none" stroke="#d49a1a" stroke-width="2.2" stroke-dasharray="6 4" marker-end="url(#ao)"/>')
text(890, 640, '/onrobot_joint_states', 12.5, 600, '#8a6100', anchor='start')
text(890, 658, '(JointState — 폭·힘 환산)', 12, 400, '#8a6100', anchor='start')
topic(270, 940, 150, 44, '/dsr01/joint_states', 'sensor_msgs/JointState')
arrow([(270, 852), (270, 894)], '#d49a1a', dash='6 4')

# 하드웨어
box(560, 890, 180, 108, '#f0f0f0', '#555', r=8, sw=2)
text(650, 924, 'M0609 컨트롤러', 15, 700); text(650, 948, '192.168.1.100', 12.5, 400, '#3d4a5c'); text(650, 968, '두산 전용 TCP 12345', 12.5, 400, '#3d4a5c'); text(650, 988, '(DDS 아님)', 12, 400, '#56657a')
box(770, 890, 190, 108, '#f0f0f0', '#555', r=8, sw=2)
text(865, 924, 'RG2 Compute Box', 15, 700); text(865, 948, '192.168.1.1 (설정 웹)', 12.5, 400, '#3d4a5c'); text(865, 968, 'Modbus TCP', 12.5, 400, '#3d4a5c')
out.append('<path d="M450 850 L520 850 L520 944 L558 944" fill="none" stroke="#555" stroke-width="3"/>')
out.append('<path d="M865 852 L865 888" fill="none" stroke="#555" stroke-width="3"/>')

# ── PC-B
box(1110, 118, 540, 910, '#ffffff', '#2c3440', r=14, sw=2.5)
text(1132, 150, 'PC-B · HMI PC (황인재 PC) — 같은 스위치 · DOMAIN 60', 17, 800, anchor='start')
node(1150, 400, 460, 110, 'hmi_bridge (패키지 f4_hmi)', 'rclpy 스레드(구독·서비스 호출) + FastAPI 웹 서버 :8000', '#f1ebfa', '#7a4fc4')
text(1380, 494, '보여 주고 전달만 한다 — 흐름·복구 판단은 flow_node', 12.5, 400, '#5b3a96')
out.append('<path d="M1380 512 L1380 568" fill="none" stroke="#7a4fc4" stroke-width="2.5" marker-start="url(#ag)" marker-end="url(#ag)"/>')
text(1392, 546, 'HTTP · WS · 이 PC 안에서만', 12.5, 500, '#5b3a96', anchor='start')
box(1150, 570, 460, 150, '#fbf8ff', '#7a4fc4', dash='8 5', r=10, sw=1.8)
text(1380, 602, '웹 화면 (Next.js 정적 파일 · 브라우저)', 16, 700, '#5b3a96')
text(1380, 630, '단계 그림 · 지금 하는 일 · 팔레트 · 수량·소모품 · 이력', 13, 400, '#3d4a5c')
text(1380, 654, '시작 · 일시 정지 · 재개 · 중단 버튼', 13, 400, '#3d4a5c')
text(1380, 682, 'GET /api/state · POST /api/start | stop | resume | abort', 12.5, 500, '#3d4a5c')
text(1380, 702, 'WebSocket /ws/state (실시간)', 12.5, 500, '#3d4a5c')
pkg(1150, 750, 460, 70, 'prewash.db (SQLite) — F4-04 예정', '용기마다 FlowEvent 한 줄 · 이력 조회 GET /api/history')
pkg(1150, 850, 460, 88, '개발용: fake_state_pub (f4_hmi)', '실제 flow_node 대신 같은 토픽·서비스를 대본대로 흉내')
text(1380, 920, '→ 로봇·flow 없이 HMI 개발 (대본 5개: 정상·일시정지·격리·오류·빈 구역)', 12.5, 400, '#56657a')

# ── PC 사이 (DDS)
topic(1060, 230, 140, 46, '/flow/state', 'cobot_msgs/FlowState · 2 Hz')
topic(1060, 340, 140, 46, '/flow/event', 'cobot_msgs/FlowEvent · 용기당 1건')
out.append('<path d="M742 232 L918 232" fill="none" stroke="#d49a1a" stroke-width="2.2" stroke-dasharray="8 5" marker-end="url(#ao)"/>')
out.append('<path d="M742 296 L840 296 L840 340 L918 340" fill="none" stroke="#d49a1a" stroke-width="2.2" stroke-dasharray="8 5" marker-end="url(#ao)"/>')
text(830, 224, 'publish', 12.5, 600, '#8a6100')
out.append('<path d="M1202 230 L1300 230 L1300 398" fill="none" stroke="#d49a1a" stroke-width="2.2" stroke-dasharray="8 5" marker-end="url(#ao)"/>')
out.append('<path d="M1202 340 L1250 340 L1250 398" fill="none" stroke="#d49a1a" stroke-width="2.2" stroke-dasharray="8 5" marker-end="url(#ao)"/>')
text(1336, 262, 'subscribe', 12.5, 600, '#8a6100', anchor='start')
out.append('<path d="M1148 470 L800 470 L800 268 L744 268" fill="none" stroke="#2c3440" stroke-width="2.6" marker-end="url(#ak)"/>')
text(912, 496, '/flow/start · /flow/stop', 13.5, 700, '#2c3440')
text(912, 516, '/flow/resume · /flow/abort', 13.5, 700, '#2c3440')
text(912, 536, 'std_srvs/Trigger · HMI 버튼 4개', 12.5, 500, '#2c3440')
text(1070, 1052, 'DDS: ROS_DOMAIN_ID 60 · 평소엔 PC 마다 격리(solo) · 두 PC 가 통신할 때만 team60', 13, 500, '#3d4a5c')

svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" font-family="{FONT}">'
       f'<defs>{markers}</defs><rect width="{W}" height="{H}" fill="#ffffff"/>{"".join(out)}</svg>')
open(sys.argv[1], 'w', encoding='utf-8').write(svg)
