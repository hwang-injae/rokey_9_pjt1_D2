# -*- coding: utf-8 -*-
"""PC 단위 시스템 아키텍처: 같은 데이터로 SVG + draw.io(.drawio) 생성"""
import html, xml.sax.saxutils as su

W, H = 1720, 1180
C = {'f1':'#CFE2F3','f2':'#D9EAD3','f3':'#FCE5CD','f4':'#D9D2E9','ext':'#EFEFEF','pc':'#FFFFFF','db':'#FFF2CC','dev':'#F3F3F3'}
S = {'f1':'#3D85C6','f2':'#6AA84F','f3':'#E69138','f4':'#8E7CC3','ext':'#666666','pc':'#222222','db':'#BF9000','dev':'#999999'}

boxes = []   # id, x,y,w,h, lines, kind, shape('rect'|'cyl'|'dash'|'container')
edges = []   # src, dst, label, style('srv'|'topic'|'net'|'call'|'phys'), (opt) sx,sy,dx,dy anchor hints

def B(i,x,y,w,h,lines,kind='ext',shape='rect'): boxes.append((i,x,y,w,h,lines,kind,shape))
def E(s,d,label,style,pts=None,lab=None): edges.append((s,d,label,style,pts,lab))

# ---------- PC-A ----------
B('pcA',40,70,700,650,['PC-A  로봇 제어 PC  (통합 실행 시 필수)','Ubuntu 24.04 · ROS 2 Jazzy · ROS_DOMAIN_ID=60 · IP 192.168.1.__ (컨트롤러와 같은 유선망)'],'pc','container')
B('wsdsr',60,130,660,120,['ws_dsr  (강사 배포 드라이버 워크스페이스 — 수정하지 않음, 먼저 source)'],'dev','container')
B('dsrctl',80,170,350,68,['dsr_controller2  (네임스페이스 /dsr01)','ros2 launch m0609_rg2_bringup bringup.launch.py','mode:=real host:=192.168.1.100 port:=12345 model:=m0609'],'ext')
B('dsrapi',450,170,250,68,['DSR_ROBOT2 파이썬 API (DR_init)','movej / movel / set_desired_force','get_workpiece_weight / set_digital_output'],'ext')
B('wsour',60,270,660,430,['rokey_pjt01_ws  (우리 저장소 rokey_9_pjt1_D2)','docs/ + src/ · build·install·log 는 .gitignore'],'dev','container')
B('common',80,310,620,52,['cobot_common  (라이브러리, 노드 아님 · 한석형)  — 두산 API를 감싼 공용 로봇 함수 모음','move_to · grip · release · weigh · force_on/off · contact_down · periodic_search · safe_retreat'],'f1')
B('f1',80,392,196,88,['f1_node  (f1_handling)','한석형 · 파지·이송·적재 · srv:','/f1/pick /f1/place /f1/move_to','/f1/tool /f1/rack_place /f1/home','f1.yaml (좌표·폭·힘·속도)'],'f1')
B('f2',292,392,196,88,['f2_node  (f2_sense_flow)','민범진 · 무게·털기·헹굼 · srv:','/f2/weigh /f2/leftover_loop','/f2/shake /f2/dip','f2.yaml (기준 무게·임계·진폭)'],'f2')
B('f3',504,392,196,88,['f3_node  (f3_wipe)','박진용 · 접촉 닦기 · srv:','/f3/seat /f3/soap /f3/wipe','f3.yaml (목표 힘·상한·궤적)'],'f3')
B('flow',190,522,400,92,['flow_node (f2_sense_flow) · 민범진 — 유일한 호출자(상태 머신)','srv 제공: /flow/start /flow/stop /flow/resume (std_srvs/Trigger)','pub: /flow/state (2 Hz) · /flow/event (용기당 1건)','flow.yaml (슬롯 순서 · 실패 정책 · 랙 배정)'],'f2')
B('csv',610,636,90,52,['records.csv','(PC-A 로컬)'],'db','cyl')
B('msgs',80,636,230,52,['cobot_msgs  (민범진 정본 관리)','srv 12종 + msg 2종 (IRD)  — PC-A·PC-B 양쪽에서 빌드'],'f2')
B('bring',330,636,260,52,['rewash_bringup  (민범진)','rewash.launch.py / rewash_mock.launch.py'],'f2')

# ---------- switch ----------
B('sw',780,330,120,70,['스위치 / 공유기','192.168.1.0/24','(유선 권장)'],'ext')

# ---------- PC-B ----------
B('pcB',940,70,480,380,['PC-B  HMI PC  (통합 실행 시 권장 · 없으면 PC-A 1대로 통합 가능)','Ubuntu 24.04 · ROS 2 Jazzy · ROS_DOMAIN_ID=60 · IP 192.168.1.__ (PC-A와 같은 스위치)'],'pc','container')
B('wsourB',960,130,440,200,['rokey_pjt01_ws  (같은 저장소 clone — cobot_msgs + f4_hmi 만 빌드)'],'dev','container')
B('msgsB',980,170,180,50,['cobot_msgs','(FlowState·FlowEvent 해석용)'],'f2')
B('bridge',1180,170,200,140,['hmi_bridge  (f4_hmi) · 황인재','FastAPI + rclpy · 포트 8000','sub  /flow/state  /flow/event','cli  /flow/start|stop|resume','REST /api/*   WS /ws/state','SQLite 기록 (events 표)'],'f4')
B('fake',980,240,180,70,['fake_state_pub  (개발용)','/flow/state·/flow/event 를','시나리오대로 발행 — 로봇 불필요'],'f4','dash')
B('db',1300,350,100,80,['rewash.db','(SQLite)'],'db','cyl')
B('browser',960,350,320,80,['브라우저 (Chrome) — PC-B 화면 또는 LAN 태블릿','http://<PC-B IP>:8000','시작·정지·재개 / 단계·슬롯·수량 / 오류 / 이력'],'f4')

# ---------- Robot cell ----------
B('cell',940,500,480,220,['로봇 셀'],'pc','container')
B('ctrl',960,540,210,90,['M0609 컨트롤러 (제어함)','IP 192.168.1.100 · TCP 12345','Dart Platform 2.12.1','제어권: ROS ↔ 티치펜던트 동시 금지'],'ext')
B('arm',1200,540,200,50,['M0609 협동로봇 (6축 · 6 kg · 900 mm)','관절 토크 센서 → 하중·힘 측정'],'ext')
B('rg2',1200,615,200,90,['OnRobot RG2 그리퍼','파지 폭 0~110 mm · 폭 피드백','Compute Box 설정 웹 192.168.1.1','DO1/DO2 ← 잡기/놓기 · DI1/DI2 → 완료'],'ext')

# ---------- dev config / legend ----------
B('dev',1450,70,250,380,['개발 중 구성 (9/17~9/22)  — 4대 각자, 로봇 없이','','PC1 한석형: sodvir(Virtual) + f1_node','    + rig_f1 (단독 시험)','PC2 민범진: sodvir + f2_node + flow_node','    + mock_f1_f3 (가짜 F1·F3)','PC3 박진용: sodvir + f3_node + rig_f3','PC4 황인재: fake_state_pub + hmi_bridge','    + 브라우저 (ROS 드라이버 불필요)','','실기 슬롯(1대 로봇)은 docs/04 로봇 슬롯 표','Virtual 에는 힘·무게·접촉이 없음','→ 로직은 Virtual/mock, 임계값은 실기'],'dev','container')
B('legend',1450,500,250,220,['범례','','실선 = 서비스 호출 (요청→응답)','점선 = 토픽 (발행→구독)','굵은 선 = 네트워크·물리 연결','','파랑 F1 한석형 · 초록 F2 민범진','주황 F3 박진용 · 보라 F4 황인재','회색 = 두산·OnRobot·외부','','IP 빈칸(__)은 실측 후 기입'],'dev','container')

# ---------- edges ----------
# pts = 전체 폴리라인(시작점 포함), lab = 라벨 위치
E('flow','f1','srv /f1/*','srv'); E('flow','f2','srv /f2/*','srv'); E('flow','f3','srv /f3/*','srv')
E('f1','common','','call',[(178,392),(178,362)]); E('f2','common','','call',[(390,392),(390,362)]); E('f3','common','','call',[(602,392),(602,362)])
E('common','dsrapi','파이썬 함수 호출','call',[(570,310),(570,238)],(640,274))
E('dsrapi','dsrctl','dsr_msgs2 서비스','srv',[(450,204),(430,204)],(440,158))
E('flow','csv','CSV 1행/용기','call',[(590,600),(655,600),(655,636)],(625,590))
E('flow','bridge','/flow/state · /flow/event  (FlowState·FlowEvent, DDS: PC-A→PC-B)','topic',[(590,545),(760,545),(760,470),(1280,470),(1280,310)],(1020,461))
E('bridge','flow','/flow/start·stop·resume  (std_srvs/Trigger, DDS: PC-B→PC-A)','srv',[(1290,310),(1290,482),(770,482),(770,555),(590,555)],(1020,494))
E('fake','bridge','개발 시 대체','topic',[(1160,275),(1180,275)],(1170,325))
E('browser','bridge','HTTP /api/* · WS /ws/state','net',[(1110,350),(1110,330),(1230,330),(1230,310)],(1150,342))
E('bridge','db','INSERT events','call',[(1350,310),(1350,350)],(1350,332))
E('ctrl','arm','','phys',[(1170,565),(1200,565)]); E('ctrl','rg2','DO1/DO2 · DI1/DI2','phys',[(1170,600),(1185,600),(1185,660),(1200,660)],(1065,648))
E('pcA','sw','DDS + TCP','net',[(740,365),(780,365)],(760,352))
E('sw','pcB','DDS (ROS 2)','net',[(900,365),(920,365),(920,260),(940,260)],(920,248))
E('sw','ctrl','TCP 12345 (DDS 아님)','net',[(840,400),(840,585),(960,585)],(900,596))

# ---------- comm table ----------
table = [
 ('이름','타입','방향','구간'),
 ('/flow/state','cobot_msgs/msg/FlowState  (2 Hz)','flow_node → hmi_bridge','PC-A → PC-B (DDS)'),
 ('/flow/event','cobot_msgs/msg/FlowEvent  (용기당 1건)','flow_node → hmi_bridge','PC-A → PC-B (DDS)'),
 ('/flow/start  /flow/stop  /flow/resume','std_srvs/srv/Trigger','hmi_bridge → flow_node','PC-B → PC-A (DDS)'),
 ('/f1/pick /f1/place /f1/move_to /f1/tool /f1/rack_place /f1/home','cobot_msgs/srv/F1Pick · F1Place · F1MoveTo · F1Tool · F1RackPlace · std_srvs/Trigger(home)','flow_node → f1_node','PC-A 내부'),
 ('/f2/weigh /f2/leftover_loop /f2/shake /f2/dip','cobot_msgs/srv/F2Weigh · F2LeftoverLoop · F2Shake · F2Dip','flow_node → f2_node','PC-A 내부'),
 ('/f3/seat /f3/soap /f3/wipe','cobot_msgs/srv/F3Seat · F3Soap · F3Wipe','flow_node → f3_node','PC-A 내부'),
 ('/dsr01/motion/move_joint · move_line  (movej·movel)','dsr_msgs2/srv/MoveJoint · MoveLine','cobot_common(DSR_ROBOT2) → dsr_controller2','PC-A 내부'),
 ('/dsr01/force/task_compliance_ctrl · set_desired_force · release_force','dsr_msgs2/srv/TaskComplianceCtrl · SetDesiredForce · ReleaseForce','cobot_common → dsr_controller2','PC-A 내부'),
 ('/dsr01/force/get_workpiece_weight  (하중 = 잔반 판정)','dsr_msgs2/srv/GetWorkpieceWeight','cobot_common → dsr_controller2','PC-A 내부'),
 ('/dsr01/io/set_ctrl_box_digital_output · get_ctrl_box_digital_input  (RG2 제어)','dsr_msgs2/srv/SetCtrlBoxDigitalOutput · GetCtrlBoxDigitalInput','cobot_common → dsr_controller2','PC-A 내부'),
 ('/dsr01/joint_states','sensor_msgs/msg/JointState','dsr_controller2 → (모니터링·rviz)','PC-A 내부'),
 ('dsr_controller2 ↔ 컨트롤러','두산 전용 TCP 프로토콜, 포트 12345  (DDS 아님)','PC-A ↔ M0609 컨트롤러','유선 192.168.1.x'),
 ('브라우저 ↔ hmi_bridge','HTTP  GET /  ·  POST /api/start|stop|resume  ·  GET /api/history  ·  WS /ws/state (JSON)','브라우저 ↔ FastAPI','PC-B 내부 또는 LAN'),
 ('hmi_bridge → rewash.db','SQLite  events 표 (FlowEvent 필드 그대로) · state 표','FastAPI → 파일','PC-B 내부'),
]
NOTE = '※ /dsr01/* 서비스의 정확한 이름·타입은 두산 ROS 2 매뉴얼(jazzy)로 확인 후 확정. IRD 정본은 docs/interfaces/*.srv·*.msg.'

# ================= SVG =================
def center(b): return (b[1]+b[3]/2, b[2]+b[4]/2)
bx = {b[0]:b for b in boxes}
def anchor(a,b):
    """a에서 b로 향하는 변 위 점 (직교 방향 선택)"""
    ax,ay = center(a); bxc,byc = center(b)
    dx,dy = bxc-ax, byc-ay
    if abs(dx)*a[4] > abs(dy)*a[3]:   # 좌우
        return (a[1]+a[3] if dx>0 else a[1], ay)
    return (ax, a[2]+a[4] if dy>0 else a[2])

svg=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="Noto Sans CJK KR, Noto Sans CJK JP, NanumGothic, Malgun Gothic, sans-serif" font-size="12">',
 f'<rect width="{W}" height="{H}" fill="#ffffff"/>',
 '<defs><marker id="ar" markerWidth="10" markerHeight="10" refX="9" refY="5" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="#333"/></marker></defs>',
 '<text x="40" y="45" font-size="22" font-weight="bold">ReWash-Cell 시스템 아키텍처 (PC 단위) — 통합 실행 구성 2대 + 로봇 셀</text>',
 '<text x="40" y="62" font-size="11" fill="#555">SDD-REWASH-001 §2 · 2026-09-18 초안 · draw.io 로 다시 그릴 때 참고용 (같은 내용의 .drawio 파일 첨부)</text>']
for i,x,y,w,h,lines,kind,shape in boxes:
    fill=C[kind]; stroke=S[kind]
    if shape=='container':
        svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="{C["pc"] if kind=="pc" else fill}" stroke="{stroke}" stroke-width="{2 if kind=="pc" else 1.2}" {"stroke-dasharray=\"6,4\"" if kind=="dev" and i in("wsdsr","wsour","wsourB") else ""}/>')
        for k,l in enumerate(lines):
            svg.append(f'<text x="{x+10}" y="{y+18+k*15}" font-size="{13 if k==0 else 11}" font-weight="{"bold" if k==0 else "normal"}" fill="#222">{su.escape(l)}</text>')
        continue
    if shape=='cyl':
        svg.append(f'<path d="M{x},{y+8} a{w/2},8 0 0,0 {w},0 a{w/2},8 0 0,0 -{w},0 v{h-16} a{w/2},8 0 0,0 {w},0 v-{h-16}" fill="{fill}" stroke="{stroke}" stroke-width="1.2"/>')
    else:
        svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="4" fill="{fill}" stroke="{stroke}" stroke-width="1.2" {"stroke-dasharray=\"5,3\"" if shape=="dash" else ""}/>')
    n=len(lines); y0=y+h/2-(n-1)*7.5+4
    for k,l in enumerate(lines):
        svg.append(f'<text x="{x+w/2}" y="{y0+k*15}" text-anchor="middle" font-size="{12 if k==0 else 11}" font-weight="{"bold" if k==0 else "normal"}" fill="#111">{su.escape(l)}</text>')
sty={'srv':'stroke="#333" stroke-width="1.4"','topic':'stroke="#333" stroke-width="1.4" stroke-dasharray="6,4"','call':'stroke="#777" stroke-width="1.1"','net':'stroke="#1155aa" stroke-width="3"','phys':'stroke="#444" stroke-width="3"'}
def route(a,b):
    (x1,y1)=anchor(a,b); (x2,y2)=anchor(b,a)
    if x1 in (a[1],a[1]+a[3]):      # 좌우로 나감
        xm=(x1+x2)/2; return [(x1,y1),(xm,y1),(xm,y2),(x2,y2)]
    ym=(y1+y2)/2; return [(x1,y1),(x1,ym),(x2,ym),(x2,y2)]
for s,d,label,style,pts,lab in edges:
    P = pts or route(bx[s],bx[d])
    svg.append('<polyline points="'+' '.join(f'{x},{y}' for x,y in P)+f'" fill="none" {sty[style]} marker-end="url(#ar)"/>')
    if label:
        if lab: mx,my=lab
        else:
            segs=[(P[i],P[i+1]) for i in range(len(P)-1)]
            (p,q)=max(segs,key=lambda t:abs(t[0][0]-t[1][0])+abs(t[0][1]-t[1][1]))
            mx,my=(p[0]+q[0])/2,(p[1]+q[1])/2
        tw=len(label)*6.4+8
        svg.append(f'<rect x="{mx-tw/2}" y="{my-9}" width="{tw}" height="16" fill="#fff" fill-opacity="0.92"/>')
        svg.append(f'<text x="{mx}" y="{my+3}" text-anchor="middle" font-size="10.5" fill="#222">{su.escape(label)}</text>')
# table
ty=750; colw=[470,560,300,160]; tx=40
svg.append(f'<text x="{tx}" y="{ty-8}" font-size="14" font-weight="bold">노드 간 통신 정의 (토픽 · 서비스 · 네트워크)</text>')
for r,row in enumerate(table):
    yy=ty+r*24; xx=tx
    for c,cell in enumerate(row):
        svg.append(f'<rect x="{xx}" y="{yy}" width="{colw[c]}" height="24" fill="{"#DDE6F0" if r==0 else "#fff"}" stroke="#999" stroke-width="0.8"/>')
        svg.append(f'<text x="{xx+5}" y="{yy+16}" font-size="{11 if r else 12}" font-weight="{"bold" if r==0 else "normal"}">{su.escape(cell)}</text>')
        xx+=colw[c]
svg.append(f'<text x="{tx}" y="{ty+len(table)*24+18}" font-size="11" fill="#555">{su.escape(NOTE)}</text>')
svg.append('</svg>')
open('system_architecture_pc.svg','w',encoding='utf-8').write('\n'.join(svg))

# ================= draw.io =================
cells=['<mxCell id="0"/>','<mxCell id="1" parent="0"/>']
def st(kind,shape):
    base=f'fillColor={C[kind]};strokeColor={S[kind]};fontFamily=Helvetica;fontSize=11;whiteSpace=wrap;html=1;'
    if shape=='container': return base+'verticalAlign=top;align=left;spacingLeft=6;fontStyle=1;fontSize=12;rounded=1;'+('dashed=1;' if kind=='dev' else '')
    if shape=='cyl': return 'shape=cylinder3;'+base
    if shape=='dash': return base+'dashed=1;'
    return base+'rounded=1;'
for i,x,y,w,h,lines,kind,shape in boxes:
    if shape=='container':
        val=f'<b>{html.escape(lines[0])}</b>'+''.join('<br>'+html.escape(l) for l in lines[1:])
    else:
        val=f'<b>{html.escape(lines[0])}</b>'+''.join('<br>'+html.escape(l) for l in lines[1:])
    cells.append(f'<mxCell id="{i}" value="{html.escape(val,quote=True)}" style="{st(kind,shape)}" vertex="1" parent="1"><mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>')
es={'srv':'endArrow=block;strokeWidth=1.5;','topic':'endArrow=block;dashed=1;strokeWidth=1.5;','call':'endArrow=open;strokeColor=#777777;','net':'endArrow=none;strokeWidth=3;strokeColor=#1155AA;','phys':'endArrow=none;strokeWidth=3;strokeColor=#444444;'}
for k,(s,d,label,style,pts,lab) in enumerate(edges):
    wp=''.join(f'<mxPoint x="{x}" y="{y}"/>' for x,y in (pts[1:-1] if pts else []))
    geo=f'<mxGeometry relative="1" as="geometry">{"<Array as=\"points\">"+wp+"</Array>" if wp else ""}</mxGeometry>'
    cells.append(f'<mxCell id="e{k}" value="{html.escape(label,quote=True)}" style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;fontSize=10;{es[style]}" edge="1" parent="1" source="{s}" target="{d}">{geo}</mxCell>')
# table as draw.io table
ty=750; colw=[470,560,300,160]; tx=40
tid='tbl'
cells.append(f'<mxCell id="{tid}" value="" style="shape=table;startSize=0;container=1;collapsible=0;childLayout=tableLayout;fontSize=11;" vertex="1" parent="1"><mxGeometry x="{tx}" y="{ty}" width="{sum(colw)}" height="{24*len(table)}" as="geometry"/></mxCell>')
for r,row in enumerate(table):
    rid=f'{tid}r{r}'
    cells.append(f'<mxCell id="{rid}" value="" style="shape=tableRow;horizontal=0;startSize=0;swimlaneHead=0;swimlaneBody=0;top=0;left=0;bottom=0;right=0;collapsible=0;dropTarget=0;fillColor=none;points=[[0,0.5],[1,0.5]];portConstraint=eastwest;" vertex="1" parent="{tid}"><mxGeometry y="{r*24}" width="{sum(colw)}" height="24" as="geometry"/></mxCell>')
    xx=0
    for c,cell in enumerate(row):
        cells.append(f'<mxCell id="{rid}c{c}" value="{html.escape(cell,quote=True)}" style="shape=partialRectangle;html=1;whiteSpace=wrap;connectable=0;overflow=hidden;fillColor={"#DDE6F0" if r==0 else "none"};top=0;left=0;bottom=0;right=0;align=left;spacingLeft=4;fontSize=10;{"fontStyle=1;" if r==0 else ""}" vertex="1" parent="{rid}"><mxGeometry x="{xx}" width="{colw[c]}" height="24" as="geometry"/></mxCell>')
        xx+=colw[c]
cells.append(f'<mxCell id="note" value="{html.escape(NOTE,quote=True)}" style="text;html=1;fontSize=10;fontColor=#555555;" vertex="1" parent="1"><mxGeometry x="{tx}" y="{ty+24*len(table)+6}" width="1200" height="20" as="geometry"/></mxCell>')
cells.append(f'<mxCell id="title" value="{html.escape("<b>ReWash-Cell 시스템 아키텍처 (PC 단위)</b> — 통합 실행 구성 2대 + 로봇 셀",quote=True)}" style="text;html=1;fontSize=20;" vertex="1" parent="1"><mxGeometry x="40" y="20" width="900" height="30" as="geometry"/></mxCell>')
drawio=f'<mxfile host="app.diagrams.net"><diagram name="시스템 아키텍처(PC)" id="arch"><mxGraphModel dx="1400" dy="900" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="{W}" pageHeight="{H}" math="0" shadow="0"><root>{"".join(cells)}</root></mxGraphModel></diagram></mxfile>'
open('system_architecture_pc.drawio','w',encoding='utf-8').write(drawio)
print('ok')
