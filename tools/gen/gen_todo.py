# -*- coding: utf-8 -*-
"""담당별 할 일 시트 생성 — 구글 시트(정본)의 현재 내용(PM이 고친 것 포함)을 읽어 사람별·날짜별 체크리스트를 만든다.
실행: python3 tools/gen/gen_todo.py [출력.xlsx]   → 구글 시트에서 '파일 > 가져오기 > 업로드 > 새 시트 삽입' (기존 시트는 그대로 유지)"""
import sys, os, re, zipfile, html
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from livesheet import load, timeline

PEOPLE=[('S','한석형','팀장 · F1 파지·이송·적재 + 좌표 계산·티칭(cell.yaml) + cobot_common 기본 이동·그리퍼(motion.py)'),('M','민범진','F2 무게·털기·헹굼 + flow_node + mock · 통합 실행 리더 + cobot_common weigh(weigh.py)'),
        ('P','박진용','F3 접촉 닦기 + cobot_common 힘 함수(force.py)·패키지 정리·리뷰 + 안전 파라미터'),('H','황인재','PM · F4 웹 HMI + cobot_api·cobot_msgs·cobot_common bootstrap·런치·일정표·제출')]
DAYORD=['9/18','9/19','9/20','9/21','9/22','9/23','9/24~28','9/29','9/30']; PARTORD=['오전','오후','저녁']
WD={'9/18':'금','9/19':'토','9/20':'일','9/21':'월 · 오전 강의, 오후 중간점검 발표','9/22':'화','9/23':'수 · 저녁 기능 동결','9/24~28':'추석 · 로봇 없음','9/29':'화 · 14:00 강사 시연','9/30':'수 · 11:00 제출·발표'}

# ---- 작업을 쉬운 말로 (ID → 한 줄) ----
EASY={
'BRF':'매일 아침 09:30 브리핑: 어제 한 일·오늘 할 일·막힌 것·오늘 로봇 쓰는 순서를 5분 안에 말한다',
'PM-01':'매일 저녁 일정표의 진행·상태를 고치고, 팀원 진척과 올라온 PR을 확인한다',
'DOC-01':'문서(요구사항·인터페이스·설계)를 확정해 팀원 에이전트에 배포한다','DSN-01':'1차 회의: 아키텍처와 인터페이스를 다 같이 정한다','DSN-02':'1차 회의에서 정한 것을 문서와 메시지 패키지에 반영한다',
'ENV-01':'내 PC에 환경을 만든다: 두산 드라이버 빌드, 가상 로봇 띄우기, 저장소 받기, 우리 워크스페이스 빌드','ENV-02':'실제 로봇(192.168.1.100)에 접속되는지, 그리퍼 설정 웹이 열리는지 확인한다',
'ENV-03':'PC 두 대(로봇 PC ↔ HMI PC)가 서로의 토픽·서비스를 볼 수 있는지 확인한다',
'INF-01':'서비스·메시지 정의를 ROS 패키지(cobot_msgs)로 만들어 배포한다','INF-01b':'약속 파일을 새 구조에 맞춘다: 메시지 패키지(cobot_msgs)에서 서비스 12개를 빼고, 같은 내용의 함수 약속 패키지(cobot_api)를 만든다',
'INF-02':'공용 로봇 함수 중 기본 이동·그리퍼(move_to·move_rel·grip·grip_level·release)를 만든다. 내가 검증(V-01·V-22·V-23)하면서 쓰는 바로 그 동작이다. 다른 사람들이 이걸 가져다 쓴다',
'TS-01':'로봇 프로그램이 뜨자마자 죽거나 두 번째 호출에서 멈추는 문제(TS-01)를 기록했다. 결론은 구조 변경(DSN-02b)',
'V-24':'(선택) 로봇이 움직이는 도중에도 정지 버튼이 먹게 한다: 이동 명령을 보낸 뒤 짧게 반복 확인하면서 정지 깃발·시간 초과를 본다(가상 로봇). 안 되면 빼도 된다',
'DSN-02b':'실행 구조를 바꾼다: 노드 5개·서비스 대신, flow_node 프로그램 하나가 세 사람의 함수를 차례로 부른다. 9/19 아침 브리핑에서 다 같이 확인',
'ENV-04':'바뀐 구조를 내 PC에 적용한다: 저장소 받기, 옛 빌드 폴더 지우고 다시 빌드, 내 브랜치에 main 합치기, 에이전트에게 새 문서 다시 읽히기, 프롬프트 파일 새 것으로 바꾸기',
'PKG-01':'내 패키지 뼈대를 만든다: 약속(cobot_api)에 적힌 이름·인자 그대로 빈 함수를 만들고(결과만 돌려줌), 내 함수만 불러 보는 시험 스크립트 rig 를 만든다',
'INF-02a':'공용 로봇 함수의 시작·끝 부분(init·shutdown)과 설정 읽기를 만든다. 가상 로봇에서 돌려 본 시험 코드를 옮겨 적는다. 이게 있어야 모두가 자기 함수를 돌려 볼 수 있다',
'INF-02c':'공용 로봇 함수 중 무게 재기(weigh)를 만든다. V-02 에서 만든 측정 도구를 옮겨 적는다. 0점 재설정은 선택 동작으로',
'CELL-04b':'기구(스펀지 고정틀·툴 홀더)를 작업대에 고정한 뒤, 스펀지 홈 2곳과 툴 홀더 2곳의 좌표를 읽어 cell.yaml 에 적는다',
'INF-02b':'공용 로봇 함수 중 힘 관련(힘제어 켜기/끄기, 닿았는지 판정, 닿을 때까지 내려가기, 흔들며 찾기, 안전 후퇴)을 만들고, 네 사람이 나눠 쓴 함수들이 서로 맞는지 정리한다',
'INF-03':'로봇 없이 flow를 개발하려고 F1·F3와 같은 이름의 가짜 함수 모듈을 만든다(실패도 흉내 낼 수 있게)','INF-04':'설정 파일 2개(cell.yaml, params.yaml)의 뼈대와 한 번에 실행하는 런치 파일 2개를 만든다. 런치는 flow_node 프로그램 하나만 띄운다',
'CELL-04':'다 같이 로봇을 손으로 움직여 위치(홈·무게 재는 곳·잔반통·반납 구역·팔레트·수조·격리)의 좌표를 읽어 cell.yaml 에 적는다. 스펀지 홈과 툴 홀더는 기구를 고정한 뒤 2차에서',
'ARCH-01':'새 구조로 다시 그린 아키텍처 그림을 draw.io에서 다듬고 HMI 쪽 빈칸을 채운다. 강사가 요구한 산출물 10종을 노션에 올린다',
'DSN-03':'2차 회의: 반납 구역 방식, HMI 설계, 실패했을 때 처리 규칙, 설정 키 이름 규칙 + 구조 변경 뒤 남은 것(모니터·기록 노드를 추가할지, 힘·그리퍼 폭 토픽, 공용 함수 분담 확인)','DSN-04':'2차 회의에서 정한 것을 문서와 cobot_msgs에 반영한다',
'MID-01':'월요일 중간점검 발표 자료 10장을 만든다(주제·아키텍처·역할·진행·계획)','MID-02':'중간점검: 30분 발표 + 30분 토론. 강사 피드백을 받아 적는다','CR-01':'서로의 코드를 본다: 안전(힘 상한·후퇴·타임아웃), 숫자 하드코딩, 함수 약속(cobot_api)과 일치하는지',
'NOTE-01':'노션에 ROS 2 노드 구조와 인터페이스 정의서를 올린다(강사 9/22 요구)','NOTE-02':'노션에 HMI 화면을 gif로 올린다(강사 9/22 요구)',
'INT-3a':'그릇 1개를 처음부터 끝까지(집기→무게→닦기→헹굼→적재) 실제 함수와 HMI로 3번 연속 성공시킨다','INT-3b':'컵 1개를 처음부터 끝까지 3번 연속 성공시킨다','FIX-01':'통합에서 나온 문제를 고치고 값(힘·속도·좌표)을 다듬는다',
'INT-4a':'시작 버튼 한 번으로 그릇 2개·컵 2개를 연속 처리한다','INT-4b':'일부러 실패를 만든다(빈 구역·잔반 과다·툴 없음·팔레트 걸림·정지/재개) → 규칙대로 복구되는지 본다',
'INT-4c':'성공률·용기당 시간·잔반 검출률을 3번 측정해 표로 만든다','INT-4d':'시연 영상을 찍고, 코드에 v1.0-demo 태그를 붙인다. 이후 기능 추가 금지',
'DOC-02':'발표 PPT를 강사 5장 양식으로 만든다','DOC-03':'시연 영상을 1분 이내로 편집하고 자막을 넣는다','DOC-04':'발표 대본·시연 순서·역할·예상 질문을 정리한다','DOC-05':'문서를 실제 만든 대로 고치고 결과 수치를 넣는다. 노션도 발표 자료에 맞게 정리',
'REH-01':'온라인으로 발표 리허설을 한다','REH-02':'오전에 로봇으로 통합 리허설을 한다','DEMO-01':'14:00부터 강사 앞에서 시연하고 PPT 내용으로 토의한다','REH-03':'백업 영상을 찍고 최종 코드를 올리고 노션을 정리한다',
'SUB-01':'11시 전에 제출: 영상 mp4, PPT pdf, 소스 zip, README. 파일명 D-2_협동1_한석형_민범진_박진용_황인재','DOC-06':'최종 발표(20분 + 질의 10분)','WRAP-01':'PPT 검토·기술 공유·로봇 설정 초기화·자리 정리',
'CELL-01':'작업대에 자리를 잡는다: 그릇·컵 반납 구역, 식기세척기용 팔레트(그릇 2칸·컵 4칸), 격리 구역. 그리퍼 손가락에 미끄럼방지 패드를 붙인다',
'V-01':'그리퍼로 그릇·컵을 잡았을 때와 빈손일 때의 "벌어진 폭" 값이 확실히 다른지 잰다. 이게 돼야 "잡았는지"를 알 수 있다','V-05':'그리퍼 드라이버가 제대로 붙었는지 확인한다: 잡기/놓기 명령이 먹는지, 현재 벌어진 폭 값이 들어오는지',
'V-17':'컵을 옆면으로 잡는 방식 확인(완료: 집기·이송은 OK, 털 때는 더 세게 잡아야 함)','V-19':'로봇 팔이 모든 작업 위치에 무리 없이 닿는지 확인한다. 안 닿으면 배치를 바꾼다','V-22':'설정 파일에 적은 좌표대로 로봇을 보냈을 때 실제 위치와 2 mm 이내로 맞는지 확인한다',
'V-06':'팔레트 칸에 그릇·컵을 기울여 넣어 보고, 걸렸을 때 힘이 올라가는 게 보이는지 확인한다','V-08':'툴 홀더에서 수세미 툴·솔을 집었다 돌려놓기를 10번 해 본다',
'V-15':'스펀지 홈에 놓인 그릇·컵을 다시 잡을 때도 "폭"으로 잡았는지 알 수 있는지 확인한다','V-16':'털 때 쓰는 "강한 파지" 힘을 찾는다: 떨어지지 않으면서 용기가 찌그러지지 않는 최소 힘',
'V-23':'쥐고 있는 상태에서 힘만 올렸다 내렸다(보통↔강한 파지) 할 수 있는지, 어떤 방법으로 하는지 확인한다','V-20':'새 실행 구조가 팀 코드로도 도는지 가상 로봇에서 확인한다: flow_node가 세 사람의 빈 함수를 번갈아 부르고, 그동안 상태 발행(초당 2번)과 정지 버튼이 살아 있는지, Ctrl+C로 끈 뒤 다시 켜지는지',
'V-21':'(종료) 서비스 안에서 로봇을 움직일 때의 멈춤 문제 — 구조를 바꿔서 더 이상 해당 없음. 기록은 TS-01','V-02':'100 g·200 g 추를 들고 로봇이 재는 무게가 ±20 g 안에 들어오는지 10번 잰다','V-07':'털기 동작을 했을 때 로봇이 "충돌"로 오해해 멈추지 않는지 확인한다',
'V-03':'힘제어를 켠 채로 옆으로(원·나선) 움직일 수 있는지 로봇으로 확인한다. 닦기 방식이 이 결과로 정해진다','V-12':'자른 스펀지 홈에 그릇·컵이 1~2 mm 여유로 들어가는지 확인한다','V-04':'용기를 홈에서 2 mm 어긋나게 내려놓고, 살살 흔들며 찾는 동작(Move Periodic)으로 들어가는지 확인한다',
'V-10':'컵 안에 솔을 넣을 때 깊이와 부딪힘을 확인한다','V-18':'닦는 힘(3~5 N)이 걸려도 수세미 툴·솔이 그리퍼 안에서 밀리거나 돌지 않는지 확인한다','V-13':'브라우저에서 시작 버튼을 누르면 가짜 flow가 반응하는지 확인한다','V-14':'그릇 2개를 겹치거나 어긋나게 놓고 "찾아서 집기"를 10번 해 성공률을 잰다',
'F1-01':'cell.yaml에 좌표와 잡는 폭·힘을 넣고, 지정 위치로 이동(move_to)과 그냥 놓기(place)를 만든다','F1-02':'"찾아서 집기"(pick)를 만든다: 구역 안 여러 점을 돌며 닿을 때까지 내려가 잡고, 폭으로 성공을 판단, 못 잡으면 다음 점',
'F1-05':'"안착 놓기"를 만든다: 용기를 쥔 채 스펀지 홈에 내려놓고, 안 들어가면 살살 흔들어 찾은 뒤 놓는다','F1-03':'툴 집기/돌려놓기(tool)를 만든다','F1-04':'팔레트 적재(rack_place)를 만든다: 정해진 각도로 넣고, 걸리면 빼서 다시',
'UT-F1':'F1 단위 테스트(TC-01 찾아서 집기, 02 툴, 05 안착 놓기, 09 팔레트)를 기준대로 통과시킨다','INT-12b':'F1+F2 통합: flow_node에서 F3만 가짜로 두고, 다시 집기→헹굼→물 털기→팔레트 적재를 5번 연속','INT-13p':'F1+F3 통합에 F1 담당으로 참여(안착 놓기·툴)',
'CELL-03':'잔반통과 수조 2개를 로봇 컨트롤러 반대편에 고정하고, 잔반 대용품(구슬·쌀 등 100 g 이상)을 정한다','FLOW-01':'전체 순서를 지휘하는 메인 프로그램 flow_node를 가짜 함수로 먼저 만든다: 시작/정지/재개 받기, 상태 발행, 단계 전환, 실패 시 재시도·격리·정지, 오류가 나도 프로그램이 죽지 않게 보호',
'F2-01':'무게 재기·잔반 판정·털기를 만든다. 털기 전에 강한 파지, 끝나면 보통 파지','FLOW-02':'용기 하나 끝날 때마다 기록(CSV)과 이벤트를 남기고 소모품 횟수를 센다','F2-02':'헹굼 담금·물 털기를 만든다(강한 파지 적용)',
'UT-FLOW':'flow 단위 테스트(TC-10 실패 규칙, TC-12 기록)를 가짜 함수로 통과시킨다. 가짜 함수가 오류를 내도 프로그램이 죽지 않고 일시정지로 가는지, Ctrl+C로 끈 뒤 다시 켜지는지도 본다','UT-F2':'F2 단위 테스트(TC-03 무게, 04 잔반, 08 헹굼)를 통과시킨다','INT-12a':'F1+F2 통합: flow_node에서 F3만 가짜로 두고, 찾아서 집기→무게→털기를 5번 연속',
'SAFE-01':'안전 값(속도·힘 상한·타임아웃) 표와 위험요소·대책, 오류 목록을 설계 문서에서 뽑아 노션에 올린다. 값이 맞는지는 박진용이 확인','CELL-02a':'그릇·컵 치수를 재고 스펀지 홈을 어떻게 자를지 그림을 그린다. 툴 홀더 위치도 정한다','CELL-02':'스펀지에 그릇·컵 모양 홈을 파고, 툴 홀더 2개와 수세미 손잡이를 만들어 작업대에 고정한다(황인재가 돕는다)',
'F3-02':'그릇 닦기(wipe_bowl)를 만든다: 일정한 힘으로 누르며 나선으로 닦고 힘 기록을 남긴다. 힘이 넘거나 오래 걸리면 즉시 뒤로','F3-03':'세제 담금(soap)과 컵 닦기(wipe_cup: 솔을 넣어 돌리고 위아래)를 만든다','UT-F3':'F3 단위 테스트(TC-06 그릇 닦기, 07 컵 닦기)를 통과시킨다','INT-13':'F1+F3 통합: flow_node에서 F2만 가짜로 두고, 안착 놓기→툴 집기→세제→닦기→툴 반납을 5번 연속',
'F4-00':'HMI를 어떻게 만들지 1장으로 설계한다: 화면 구성, 서버 주소(REST/WS), 화면에 필요한 상태 값','F4-01':'가짜 상태 발행기(fake_state_pub)와 FastAPI 첫 페이지를 만든다','F4-02':'버튼 3개(시작·정지·재개)와 실시간 상태 전달(WebSocket)을 만든다. 정지 버튼은 항상 보이게',
'F4-03':'화면을 채운다: 단계·구역·팔레트 칸·수량·소모품·연결 상태·오류·이력','F4-04':'이벤트를 SQLite에 저장하고 이력 표로 보여준다','UT-F4':'HMI 단위 테스트(TC-11: 버튼 1초 안, 표시 1초 안)를 통과시킨다','INT-4':'가짜 flow에 실제 HMI를 붙여 시작·정지·재개를 확인한다','F4-05':'기록에서 성공률·사이클 타임을 뽑는 스크립트와 촬영 계획을 만든다',
}
def where(tid):
    t=tid or ''
    rules=[(r'^V-2[04]','SDD §3.2 (실행 뼈대) · §9.2'),(r'^V-','docs/03_설계_SDD.md §9.2 (통과 기준·안 되면 대안)'),(r'^UT-','SDD §9.3 (TC 표)'),(r'^INT-1|^INT-4$','SDD §9.4 (L2 통합)'),(r'^INT-3','SDD §9.5'),(r'^INT-4[a-d]','SDD §9.6~9.7'),
      (r'^F1-','SDD §5.2 · IRD §3'),(r'^F2-','SDD §5.3 · IRD §4'),(r'^FLOW','SDD §5.1 · IRD §8'),(r'^F3-','SDD §5.4 · IRD §5'),(r'^F4-','SDD §5.5·§6 · IRD §6~7'),
      (r'^INF-02','SDD §3.1 (함수 표) · §3.2 (실행 뼈대)'),(r'^INF-04','SDD §4.3 · IRD §9'),(r'^INF-01','IRD v3.0 · src/cobot_api · docs/interfaces/'),(r'^INF-03','IRD §10'),(r'^CELL','SDD §2 (워크셀)'),(r'^DSN','docs/meetings/'),(r'^TS-','docs/troubleshooting/'),
      (r'^ENV-04','docs/meetings/20260918_결정기록_구조_인터페이스.md (후속 표)'),(r'^PKG','SDD §3.2 (실행 뼈대) · src/cobot_api/cobot_api/contracts.py'),(r'^ENV','docs/setup/M0609_환경설정.md'),(r'^SAFE','SDD §8'),(r'^ARCH','SDD §1 · docs/images/*.drawio'),(r'^NOTE','SDD §12 (강사 산출물 표)'),(r'^(DOC|REH|SUB|MID|DEMO|WRAP)','일정표 "마일스톤·로봇 슬롯" 시트'),(r'^(BRF|PM)','일정표 "규칙" 시트'),(r'^CR-','CONTRIBUTING.md §4·§8'),(r'^FIX','SDD §9.9 (범위 방어)')]
    for pat,w in rules:
        if re.search(pat,t): return w
    return '내 프롬프트 (docs/prompts/)'
def role(owner,L):
    main=owner.split('(')[0]; par=owner[len(main):]
    if L in main: return '공동' if len(re.findall(r'[SMPH]',main))>1 else '담당'
    if L in par: return '참여' if '전원' not in main else '진행·취합'
    if '전원' in main: return '전원'
    return None
def key(slot): 
    d,p=slot; return (DAYORD.index(d) if d in DAYORD else 99, PARTORD.index(p) if p in PARTORD else 9)

def person_entries(rows,det,L):
    """한 사람의 할 일을 [('day',제목)] / [('item',dict)] 목록으로. gen_todo(새 파일)와 xlsx_patch(기존 시트 갱신)가 같이 쓴다."""
    mine=[(r,role(r['owner'],L)) for r in rows]; mine=[(r,ro) for r,ro in mine if ro]
    out=[]; 
    def item(r,ro,when):
        d=det.get(r['id'],{}); done=(r['status']=='완료')
        robot='R' if re.search(r'(^|\s)R(\s|$|·)',d.get('note','')) else ''
        return ('item',dict(when=when,check='☑' if done else '☐',id=r['id'],easy=EASY.get(r['id'],r['task']),task=r['task'],role=ro,robot=robot,crit=d.get('crit',''),where=where(r['id']),status=r['status'],done=done,mine=ro in('담당','공동')))
    daily=[(r,ro) for r,ro in mine if r['id'] in ('BRF','PM-01')]
    if daily:
        out.append(('day','매일'))
        for r,ro in daily: out.append(item(r,ro,'매일 아침' if r['id']=='BRF' else '매일 저녁'))
    groups={}
    for r,ro in mine:
        if r['id'] in ('BRF','PM-01'): continue
        k=key(r['slots'][0]) if r['slots'] else (98,0)
        groups.setdefault(k[0],[]).append((k[1],r,ro))
    for di in sorted(groups):
        dname=DAYORD[di] if di<len(DAYORD) else '날짜 미정 (일정표에 색 칸이 없음)'
        out.append(('day',f'{dname} ({WD.get(dname,"")})' if di<len(DAYORD) else dname))
        for pi,r,ro in sorted(groups[di],key=lambda t:(t[0],0 if t[2] in('담당','공동') else 1)):
            s0,s1=(r['slots'][0],r['slots'][-1]) if r['slots'] else (('',''),('',''))
            when=f'{s0[1]}' if s0==s1 else (f'{s0[1]} ~ {s1[1]}' if s0[0]==s1[0] else f'{s0[1]} ~ {s1[0]} {s1[1]}')
            out.append(item(r,ro,when))
    n=lambda *ro:sum(1 for r,x in mine if x in ro)
    summary=f'일정표(Time Line)의 현재 내용에서 자동으로 뽑은 목록 · 내 작업 {n("담당","공동")}개 · 참여 {n("참여")}개 · 전원 작업 {n("전원","진행·취합")}개'
    return out,summary

if __name__=='__main__':
    rows,det=timeline(load())
    # ================= xlsx =================
    def esc(v): return html.escape(str(v),quote=False)
    def col(n):
        s=''; n+=1
        while n: n,r=divmod(n-1,26); s=chr(65+r)+s
        return s
    fills=['<fill><patternFill patternType="none"/></fill>','<fill><patternFill patternType="gray125"/></fill>']
    def F(rgb): fills.append(f'<fill><patternFill patternType="solid"><fgColor rgb="{rgb}"/><bgColor indexed="64"/></patternFill></fill>'); return len(fills)-1
    f_hdr=F('FFD9D9D9'); f_day=F('FF9FC5E8'); f_done=F('FFEFEFEF'); f_robot=F('FFFFF2CC'); f_title=F('FFCFE2F3')
    AL='<alignment vertical="center" wrapText="1"/>'; AC='<alignment horizontal="center" vertical="center" wrapText="1"/>'
    xfs=['<xf numFmtId="0" fontId="0" fillId="0" borderId="0"/>',
     f'<xf numFmtId="0" fontId="1" fillId="{f_hdr}" borderId="1" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1">{AC}</xf>',      #1 hdr
     f'<xf numFmtId="0" fontId="0" fillId="0" borderId="1" applyBorder="1" applyAlignment="1">{AL}</xf>',                                        #2 txt
     f'<xf numFmtId="0" fontId="0" fillId="0" borderId="1" applyBorder="1" applyAlignment="1">{AC}</xf>',                                        #3 ctr
     f'<xf numFmtId="0" fontId="1" fillId="{f_day}" borderId="1" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1">{AL}</xf>',     #4 day
     f'<xf numFmtId="0" fontId="3" fillId="{f_done}" borderId="1" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1">{AL}</xf>',    #5 done txt
     f'<xf numFmtId="0" fontId="3" fillId="{f_done}" borderId="1" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1">{AC}</xf>',    #6 done ctr
     f'<xf numFmtId="0" fontId="1" fillId="{f_robot}" borderId="1" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1">{AC}</xf>',   #7 robot
     f'<xf numFmtId="0" fontId="2" fillId="{f_title}" borderId="0" applyFont="1" applyFill="1" applyAlignment="1">{AL}</xf>',                    #8 title
     f'<xf numFmtId="0" fontId="0" fillId="0" borderId="0" applyAlignment="1">{AL}</xf>',                                                        #9 note
     f'<xf numFmtId="0" fontId="1" fillId="0" borderId="1" applyFont="1" applyBorder="1" applyAlignment="1">{AL}</xf>']                          #10 bold txt
    styles=f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
    <fonts count="4"><font><sz val="10"/><name val="Arial"/></font><font><b/><sz val="10"/><name val="Arial"/></font><font><b/><sz val="14"/><name val="Arial"/></font><font><sz val="10"/><color rgb="FF888888"/><name val="Arial"/></font></fonts>
    <fills count="{len(fills)}">{''.join(fills)}</fills>
    <borders count="2"><border><left/><right/><top/><bottom/><diagonal/></border><border><left style="thin"><color rgb="FFBBBBBB"/></left><right style="thin"><color rgb="FFBBBBBB"/></right><top style="thin"><color rgb="FFBBBBBB"/></top><bottom style="thin"><color rgb="FFBBBBBB"/></bottom><diagonal/></border></borders>
    <cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs><cellXfs count="{len(xfs)}">{''.join(xfs)}</cellXfs>
    <cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>'''
    def cell(ref,v,s):
        if v in ('',None): return f'<c r="{ref}" s="{s}"/>'
        return f'<c r="{ref}" s="{s}" t="inlineStr"><is><t xml:space="preserve">{esc(v)}</t></is></c>'
    NC=10; WIDTHS=[17,4,10,58,44,9,7,34,34,9]
    def sheet(rws,merges):
        x=['<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">',
           '<sheetViews><sheetView workbookViewId="0"><pane ySplit="4" topLeftCell="A5" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>',
           '<cols>'+''.join(f'<col min="{i+1}" max="{i+1}" width="{w}" customWidth="1"/>' for i,w in enumerate(WIDTHS))+'</cols><sheetData>']
        for ri,r in enumerate(rws): x.append(f'<row r="{ri+1}">'+''.join(cell(f'{col(ci)}{ri+1}',v,s) for ci,(v,s) in enumerate(r))+'</row>')
        x.append('</sheetData>')
        if merges: x.append(f'<mergeCells count="{len(merges)}">'+''.join(f'<mergeCell ref="{m}"/>' for m in merges)+'</mergeCells>')
        x.append('</worksheet>'); return '\n'.join(x)
    HELP='보는 법 — 역할: 담당(내가 주인)·공동·참여(도와주기)·전원 | 로봇 R = 실제 로봇 필요(그날 로봇 순서는 "마일스톤·로봇 슬롯" 시트) | ID는 브랜치·PR 제목에 쓴다(예 seokhyung/20260919-F1-02-pick-search) | 회색 = 완료 | 모르겠으면 내 에이전트에 "일정표의 <ID> 작업을 설명하고 STEP으로 나눠 줘"'
    sheets_xml=[]; names=[]
    for L,name,desc in PEOPLE:
        mine=[]
        for r in rows:
            ro=role(r['owner'],L)
            if ro: mine.append((r,ro))
        rws=[[(f'{name} — {desc}',8)]+[('',8)]*(NC-1), [(HELP,9)]+[('',9)]*(NC-1),
             [(f'일정표(Time Line)의 현재 내용에서 자동으로 뽑은 목록 · 내 작업 {sum(1 for r,ro in mine if ro in ("담당","공동"))}개 · 참여 {sum(1 for r,ro in mine if ro=="참여")}개 · 전원 작업 {sum(1 for r,ro in mine if ro in ("전원","진행·취합"))}개',9)]+[('',9)]*(NC-1),
             [(h,1) for h in ['언제','✓','ID','할 일 (쉬운 말)','일정표의 작업명','역할','로봇','끝났다고 볼 기준','자세히 볼 곳','상태']]]
        merges=['A1:J1','A2:J2','A3:J3']
        daily=[(r,ro) for r,ro in mine if r['id'] in ('BRF','PM-01')]
        rest=[(r,ro) for r,ro in mine if r['id'] not in ('BRF','PM-01')]
        if daily:
            rws.append([('매일',4)]+[('',4)]*(NC-1)); merges.append(f'A{len(rws)}:J{len(rws)}')
            for r,ro in daily:
                d=det.get(r['id'],{}); rws.append([('매일 아침' if r['id']=='BRF' else '매일 저녁',3),('☐',3),(r['id'],3),(EASY.get(r['id'],r['task']),2),(r['task'],2),(ro,3),('',3),(d.get('crit',''),2),(where(r['id']),2),(r['status'],3)])
        groups={}
        for r,ro in rest:
            k=key(r['slots'][0]) if r['slots'] else (98,0)
            groups.setdefault(k[0],[]).append((k[1],r,ro))
        for di in sorted(groups):
            dname=DAYORD[di] if di<len(DAYORD) else '날짜 미정 (일정표에 색 칸이 없음)'
            rws.append([(f'{dname} ({WD.get(dname,"")})' if di<len(DAYORD) else dname,4)]+[('',4)]*(NC-1)); merges.append(f'A{len(rws)}:J{len(rws)}')
            for pi,r,ro in sorted(groups[di],key=lambda t:(t[0],0 if t[2] in('담당','공동') else 1)):
                d=det.get(r['id'],{}); done=(r['status']=='완료'); T,Cc=(5,6) if done else (2,3)
                s0,s1=(r['slots'][0],r['slots'][-1]) if r['slots'] else (('',''),('',''))
                when=f'{s0[1]}' if s0==s1 else (f'{s0[1]} ~ {s1[1]}' if s0[0]==s1[0] else f'{s0[1]} ~ {s1[0]} {s1[1]}')
                robot='R' if re.search(r'(^|\s)R(\s|$|·)',d.get('note','')) else ''
                rws.append([(when,Cc),('☑' if done else '☐',Cc),(r['id'],Cc),(EASY.get(r['id'],r['task']),T if (done or ro not in('담당','공동')) else 10),(r['task'],T),(ro,Cc),(robot,7 if (robot and not done) else Cc),(d.get('crit',''),T),(where(r['id']),T),(r['status'],Cc)])
        sheets_xml.append(sheet(rws,merges)); names.append(f'할일_{name}')
    wb='<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'+''.join(f'<sheet name="{esc(n)}" sheetId="{i+1}" r:id="rId{i+1}"/>' for i,n in enumerate(names))+'</sheets></workbook>'
    n=len(names)
    wbrels='<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'+''.join(f'<Relationship Id="rId{i+1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i+1}.xml"/>' for i in range(n))+f'<Relationship Id="rId{n+1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>'
    ct='<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'+''.join(f'<Override PartName="/xl/worksheets/sheet{i+1}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>' for i in range(n))+'</Types>'
    rels='<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>'
    out=sys.argv[1] if len(sys.argv)>1 else 'prewash_담당별_할일.xlsx'
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml',ct); z.writestr('_rels/.rels',rels); z.writestr('xl/workbook.xml',wb); z.writestr('xl/_rels/workbook.xml.rels',wbrels); z.writestr('xl/styles.xml',styles)
        for i,s in enumerate(sheets_xml): z.writestr(f'xl/worksheets/sheet{i+1}.xml',s)
    noeasy=sorted({r['id'] for r in rows if r['id'] and r['id'] not in EASY})
    print('->',out,'| 시트',names,'| 쉬운 말 설명이 없는 ID:',noeasy or '없음')
