# -*- coding: utf-8 -*-
"""시스템 아키텍처(PC 단위) — 노드=사각형, 토픽=타원, 점선 상자=파이썬 패키지(노드 아님), 화살표 라벨=서비스·메시지 타입·함수.  SVG + draw.io 동시 생성.
실행: python3 tools/gen/gen_arch.py  → docs/images/system_architecture_pc.svg / .drawio
웹(PC-B) 안쪽은 F4-00 설계 전이라 비워 둔다. 팀이 회의하며 draw.io 로 다시 그리는 밑그림이다."""
import os, html, xml.sax.saxutils as su
ROOT=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT=os.path.join(ROOT,'docs','images')
W,H=1760,1040
COL={'f1':('#CFE2F3','#3D85C6'),'f2':('#D9EAD3','#6AA84F'),'f3':('#FCE5CD','#E69138'),'f4':('#D9D2E9','#8E7CC3'),
     'ext':('#EFEFEF','#666666'),'topic':('#FFF2CC','#BF9000'),'pc':('#FFFFFF','#222222'),'lib':('#F7F7F7','#777777'),'todo':('#FFFFFF','#8E7CC3')}
shapes=[]; edges=[]
def N(i,x,y,w,h,lines,kind,shape='node'): shapes.append((i,x,y,w,h,lines,kind,shape))   # shape: node|topic|container|lib|todo|data
def E(s,d,pts,label=None,lab=None,style='srv'): edges.append((s,d,pts,label,lab,style))

# ---------- 컨테이너 ----------
N('pcA',40,84,1060,880,['PC-A  로봇 제어 PC   ·  Ubuntu 24.04 · ROS 2 Jazzy · ROS_DOMAIN_ID=60 · 유선 192.168.1.x'],'pc','container')
N('pcB',1440,84,290,420,['PC-B  HMI PC  · DOMAIN 60'],'pc','container')
N('cell',1160,560,570,404,['로봇 셀'],'pc','container')
# ---------- 노드(사각형) ----------
N('flow',395,124,330,70,['flow_node   (메인 프로그램 · 프로세스 1개)','f2_sense_flow · 민범진 · 유일한 호출자 · 상태 머신','메인 스레드 = 순서 실행  /  통신 노드 스레드 = /flow/* · 상태 2 Hz'],'f2')
N('f1',70,360,280,84,['f1_handling.handling   (함수 모듈 · 노드 아님)','한석형','탐색 파지 · 안착 놓기 · 이송 · 툴 · 팔레트 적재'],'f1','lib')
N('f2',420,360,280,84,['f2_sense_flow.sense   (함수 모듈 · 노드 아님)','민범진','무게 · 잔반 폐루프 · 털기 · 헹굼'],'f2','lib')
N('f3',770,360,280,84,['f3_wipe.wipe   (함수 모듈 · 노드 아님)','박진용','세제 담금 · 그릇 닦기 · 컵 닦기'],'f3','lib')
N('dsr',400,690,320,78,['dsr_controller2  (/dsr01)','두산 드라이버 · ws_dsr (수정 안 함)','m0609_rg2_bringup bringup.launch.py'],'ext')
N('grip',770,800,290,70,['OnRobotRGControllerServer','그리퍼 드라이버 · ws_dsr (강사 배포)','명령 srv · 현재 폭 topic'],'ext')
N('rviz',110,830,190,48,['rviz2 · 모니터링 (선택)'],'ext')
N('hmi',1465,150,240,96,['hmi_bridge','f4_hmi · 황인재','설계 중 (F4-00) → DSN-03에서 확정'],'f4')
N('ctrl',1190,620,240,80,['M0609 컨트롤러','192.168.1.100 · TCP 12345','Dart Platform 2.12.1'],'ext')
N('arm',1470,620,230,60,['M0609 협동로봇','6축 · 6 kg · 관절 토크 센서'],'ext')
N('rg2',1470,740,230,84,['OnRobot RG2 그리퍼','폭 피드백 0~110 mm','설정 웹 192.168.1.1'],'ext')
# ---------- 라이브러리·데이터·빈칸 ----------
N('common',70,502,980,84,['cobot_common  (라이브러리 — 노드 아님 · 박진용)      +      cobot_api  (기능 함수 약속: ID · 코드 · Result · 함수 서명 — PM)',
   'bootstrap.py: init(name) → DSR 전용 노드(flow_node_dsr) + 통신 노드(백그라운드 실행기) · shutdown()   🚨 두산 함수는 메인 스레드에서만 (TS-01 · SDD §3.2)',
   'robot.py: move_to · move_rel · grip · grip_level · release · weigh · force_on/off · force_reached · contact_down · periodic_search · safe_retreat',
   'config.py → config/cell.yaml (공용 좌표·속도·프리셋 · 한석형) + config/params.yaml (f1 · f2 · f3 · flow · hmi 절 — 자기 절만 수정)'],'lib','lib')
N('csv',130,128,180,56,['records.csv','용기당 1행 (PC-A 로컬)'],'ext','data')
N('web',1465,280,240,200,['웹 서버 · 브라우저 · DB','','(비워 둠)','황인재가 설계한 뒤','회의에서 함께 채운다'],'todo','todo')
# ---------- 토픽(타원) ----------
N('t_state',1140,105,250,60,['/flow/state'],'topic','topic')
N('t_event',1140,195,250,60,['/flow/event'],'topic','topic')
N('t_joint',90,700,230,58,['/dsr01/joint_states'],'topic','topic')
# ---------- 범례 ----------
N('legend',1140,300,280,232,['범례','','□ 사각형 = 노드','◯ 타원 = 토픽','→ 실선 화살표 = 서비스 호출(요청 방향)','     라벨 = 서비스 이름 : 타입','⇢ 점선 화살표 = 토픽 publish / subscribe','     라벨 = 메시지 타입','┄ 점선 상자 = 파이썬 패키지·함수(노드 아님)','→ 회색 가는 화살표 = 파이썬 함수 호출','━ 굵은 선 = 네트워크·물리 연결','색: 파랑 F1 · 초록 F2 · 주황 F3 · 보라 F4 · 회색 외부'],'lib','lib')

# ---------- 엣지 ----------
E('flow','f1',[(480,194),(480,222),(210,222),(210,360)],
  ['파이썬 함수 호출 (같은 프로세스 · 메인 스레드)','pick(zone_id, kind) → PickResult','place(station) → PlaceResult','move_to(station, carrying) → Result','tool(tool, action) → ToolResult','rack_place(rack_slot, kind) → Result'],(210,291),'call')
E('flow','f2',[(560,194),(560,360)],
  ['파이썬 함수 호출','weigh(kind) → WeighResult','leftover_loop(kind, max_rounds) → LeftoverResult','shake(mode, count, kind) → Result','dip(station, count, kind) → Result'],(560,291),'call')
E('flow','f3',[(640,194),(640,222),(910,222),(910,360)],
  ['파이썬 함수 호출','soap(count) → Result','wipe_bowl() → WipeBowlResult','wipe_cup() → WipeCupResult','(반환 타입은 cobot_api)'],(910,291),'call')
E('f1','common',[(210,444),(210,502)],None,None,'call')
E('f2','common',[(560,444),(560,502)],['파이썬 함수 호출 (import)'],(560,477),'call')
E('f3','common',[(910,444),(910,502)],None,None,'call')
E('common','dsr',[(560,586),(560,690)],
  ['서비스 호출 (DSR_ROBOT2 API 내부)  flow_node_dsr → dsr_controller2','/dsr01/dsr_controller2/motion/move_joint · move_line','/dsr01/dsr_controller2/force/task_compliance_ctrl','· set_desired_force · get_workpiece_weight  (dsr_msgs2/srv/…)'],(560,640))
E('common','grip',[(960,586),(960,800)],['/onrobot/sendCommand (srv)','OnRobotRGInput (topic · 현재 폭)'],(960,700))
E('grip','rg2',[(1060,835),(1440,835),(1440,805),(1470,805)],['Modbus TCP · RG2 Compute Box 192.168.1.1'],(1260,852),'net')
E('flow','csv',[(395,156),(310,156)],['CSV 기록'],(370,144),'call')
E('flow','t_state',[(725,135),(1140,135)],['publish · cobot_msgs/msg/FlowState · 2 Hz'],(930,122),'topic')
E('flow','t_event',[(725,178),(1112,178),(1112,225),(1140,225)],['publish · cobot_msgs/msg/FlowEvent · 용기당 1건'],(915,165),'topic')
E('t_state','hmi',[(1390,135),(1428,135),(1428,180),(1465,180)],['subscribe'],(1428,120),'topic')
E('t_event','hmi',[(1390,225),(1465,225)],['subscribe'],(1428,240),'topic')
E('hmi','flow',[(1690,150),(1690,70),(560,70),(560,124)],['서비스 호출  hmi_bridge → flow_node      /flow/start · /flow/stop · /flow/resume : std_srvs/srv/Trigger'],(1180,58))
E('dsr','t_joint',[(400,729),(320,729)],['publish · sensor_msgs/msg/JointState'],(300,682),'topic')
E('t_joint','rviz',[(205,758),(205,830)],['subscribe'],(245,796),'topic')
E('dsr','ctrl',[(720,729),(1130,729),(1130,660),(1190,660)],['두산 전용 TCP 12345 (DDS 아님) · 유선 192.168.1.x'],(925,746),'net')
E('ctrl','arm',[(1430,650),(1470,650)],None,None,'net')
E('ctrl','rg2',[(1430,685),(1450,685),(1450,782),(1470,782)],['DO1/DO2 · DI1/DI2'],(1330,730),'net')
E('hmi','web',[(1585,246),(1585,280)],None,None,'call')

TITLE='PreWash-Cell 시스템 아키텍처 (PC 단위) — 노드 □ · 토픽 ◯ · 패키지(함수) ┄ · 화살표 라벨 = 서비스/메시지 타입/함수'
SUB='9/18 구조 변경(DSN-02b): 노드 2개 · f1·f2·f3는 flow_node가 부르는 파이썬 함수 · 로봇 명령은 메인 스레드 하나'
NOTE='개발 중에는 mock 모듈(f2_sense_flow.mock — 같은 함수 이름, 민범진)이 f1·f3 함수를, fake_state_pub(황인재)이 /flow/state · /flow/event 를 대신한다 → 로봇·남의 코드 없이 개발.   각자 단독 시험은 rig_f*.py.   PC-A ↔ PC-B 는 같은 스위치의 DDS.'

# ================= SVG =================
FONT='Noto Sans CJK KR, NanumGothic, Malgun Gothic, Apple SD Gothic Neo, sans-serif'
o=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="{FONT}" font-size="12">',
   f'<rect width="{W}" height="{H}" fill="#ffffff"/>',
   '<defs><marker id="ar" markerWidth="10" markerHeight="10" refX="9" refY="5" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="#333"/></marker>'
   '<marker id="arb" markerWidth="10" markerHeight="10" refX="9" refY="5" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="#1155aa"/></marker></defs>',
   f'<text x="40" y="34" font-size="21" font-weight="bold">{su.escape(TITLE)}</text>',
   f'<text x="40" y="54" font-size="11" fill="#555">{su.escape(SUB)}</text>']
for i,x,y,w,h,lines,kind,shape in shapes:
    fill,stroke=COL[kind]
    if shape=='container':
        o.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="none" stroke="{stroke}" stroke-width="2"/>')
        o.append(f'<text x="{x+12}" y="{y+20}" font-size="13" font-weight="bold">{su.escape(lines[0])}</text>'); continue
    if shape=='topic':
        o.append(f'<ellipse cx="{x+w/2}" cy="{y+h/2}" rx="{w/2}" ry="{h/2}" fill="{fill}" stroke="{stroke}" stroke-width="1.6"/>')
    elif shape in('lib','todo'):
        o.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="4" fill="{fill}" stroke="{stroke}" stroke-width="1.4" stroke-dasharray="6,4"/>')
    elif shape=='data':
        o.append(f'<path d="M{x},{y+8} a{w/2},8 0 0,0 {w},0 a{w/2},8 0 0,0 -{w},0 v{h-16} a{w/2},8 0 0,0 {w},0 v-{h-16}" fill="{fill}" stroke="{stroke}" stroke-width="1.2"/>')
    else:
        o.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}" stroke="{stroke}" stroke-width="1.8"/>')
    n=len(lines); left = (i=='legend')
    y0=y+h/2-(n-1)*7.5+4 if not left else y+20
    for k,l in enumerate(lines):
        bold = (k==0)
        if left: o.append(f'<text x="{x+12}" y="{y0+k*17}" font-size="{13 if bold else 11}" font-weight="{"bold" if bold else "normal"}">{su.escape(l)}</text>')
        else:    o.append(f'<text x="{x+w/2}" y="{y0+k*15}" text-anchor="middle" font-size="{13 if bold else 10.5}" font-weight="{"bold" if bold else "normal"}" fill="#111">{su.escape(l)}</text>')
STY={'srv':'stroke="#333" stroke-width="1.6" marker-end="url(#ar)"','topic':'stroke="#333" stroke-width="1.5" stroke-dasharray="7,4" marker-end="url(#ar)"',
     'call':'stroke="#888" stroke-width="1.2" marker-end="url(#ar)"','net':'stroke="#1155aa" stroke-width="3" marker-end="url(#arb)"'}
for s,d,pts,label,lab,style in edges:
    o.append('<polyline points="'+' '.join(f'{x},{y}' for x,y in pts)+f'" fill="none" {STY[style]}/>')
for s,d,pts,label,lab,style in edges:          # 라벨은 선 위에 나중에 그린다
    if not label: continue
    cx,cy=lab; n=len(label); wmax=max(len(l) for l in label)*6.1+14; hh=n*13+6
    o.append(f'<rect x="{cx-wmax/2}" y="{cy-hh/2}" width="{wmax}" height="{hh}" fill="#ffffff" fill-opacity="0.93" stroke="#cccccc" stroke-width="0.6"/>')
    for k,l in enumerate(label):
        o.append(f'<text x="{cx}" y="{cy-hh/2+13+k*13}" text-anchor="middle" font-size="10" font-weight="{"bold" if (k==0 and n>1) else "normal"}" fill="#222">{su.escape(l)}</text>')
o.append(f'<text x="40" y="{H-42}" font-size="11" fill="#555">{su.escape(NOTE)}</text>')
o.append('</svg>')
open(os.path.join(OUT,'system_architecture_pc.svg'),'w',encoding='utf-8').write('\n'.join(o))

# ================= draw.io =================
cells=['<mxCell id="0"/>','<mxCell id="1" parent="0"/>']
def val(lines,left=False): return html.escape('<b>'+html.escape(lines[0])+'</b>'+''.join('<br>'+html.escape(l) for l in lines[1:]),quote=True)
for i,x,y,w,h,lines,kind,shape in shapes:
    fill,stroke=COL[kind]
    base=f'whiteSpace=wrap;html=1;fontSize=11;fillColor={fill};strokeColor={stroke};'
    st={'node':base+'rounded=0;strokeWidth=2;','topic':'ellipse;'+base+'strokeWidth=2;','lib':base+'dashed=1;rounded=1;'+('align=left;spacingLeft=8;verticalAlign=top;' if i=='legend' else ''),
        'todo':base+'dashed=1;rounded=1;','data':'shape=cylinder3;'+base,'container':'rounded=1;whiteSpace=wrap;html=1;fillColor=none;strokeColor=#222222;strokeWidth=2;verticalAlign=top;align=left;spacingLeft=8;fontStyle=1;fontSize=12;'}[shape]
    cells.append(f'<mxCell id="{i}" value="{val(lines)}" style="{st}" vertex="1" parent="1"><mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>')
EST={'srv':'endArrow=block;strokeWidth=2;','topic':'endArrow=block;dashed=1;strokeWidth=2;','call':'endArrow=open;strokeColor=#888888;','net':'endArrow=block;strokeWidth=3;strokeColor=#1155AA;'}
for k,(s,d,pts,label,lab,style) in enumerate(edges):
    wp=''.join(f'<mxPoint x="{x}" y="{y}"/>' for x,y in pts[1:-1])
    lv=html.escape('<br>'.join(html.escape(l) for l in (label or [])),quote=True)
    arr=('<Array as="points">'+wp+'</Array>') if wp else ''
    geo='<mxGeometry relative="1" as="geometry">'+arr+'</mxGeometry>'
    cells.append(f'<mxCell id="e{k}" value="{lv}" style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;fontSize=10;labelBackgroundColor=#ffffff;{EST[style]}" edge="1" parent="1" source="{s}" target="{d}">{geo}</mxCell>')
cells.append(f'<mxCell id="title" value="{html.escape("<b>"+html.escape(TITLE)+"</b><br>"+html.escape(SUB),quote=True)}" style="text;html=1;fontSize=14;align=left;" vertex="1" parent="1"><mxGeometry x="40" y="10" width="1500" height="50" as="geometry"/></mxCell>')
cells.append(f'<mxCell id="note" value="{html.escape(html.escape(NOTE),quote=True)}" style="text;html=1;fontSize=10;fontColor=#555555;align=left;" vertex="1" parent="1"><mxGeometry x="40" y="{H-60}" width="1600" height="30" as="geometry"/></mxCell>')
open(os.path.join(OUT,'system_architecture_pc.drawio'),'w',encoding='utf-8').write(
 f'<mxfile host="app.diagrams.net"><diagram name="시스템 아키텍처(PC)" id="arch"><mxGraphModel dx="1400" dy="900" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="{W}" pageHeight="{H}" math="0" shadow="0"><root>{"".join(cells)}</root></mxGraphModel></diagram></mxfile>')
print('ok ->',OUT)
