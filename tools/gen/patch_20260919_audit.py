# -*- coding: utf-8 -*-
"""9/19 — 일정표 점검(역할 겹침·부하·로봇 슬롯·선후·옛 표현). 구글 시트의 '현재' 내용에 변경만 얹고 모든 시트에 반영한다.
  · 주인 하나로: 공동 표기(A,B) → 주도(참여). V-04·V-15 = S(P) · V-16 = M(S) · ENV-03 = H(M) · INT-4b = M(P) · V-20 = M(H) · V-23 = S · V-24 = H · CELL-04 = S(M)
  · 팀(구역) = 주도자의 기능: V-23·V-04 → F1 · V-16 → F2·flow · V-24 → F4 · SAFE-01·V-21 → 전원 · INT-13p(INT-13 과 중복) 삭제
  · cobot_common 은 사람별 파일(motion.py=S · force.py=P · weigh.py=M · bootstrap·config·__init__=H), cell.yaml 은 한석형 혼자(INF-04 는 키 골격만)
  · 부하·로봇: INF-04 → 9/19 오후 · INF-03 → 9/19 저녁 · V-22 → 9/20 오전(티칭 2차 안, move_to 뒤) · V-16 → 9/20 오전 · F4-01 → 9/20 오전
               F3-02 2칸 + F3-03 2칸(9/20 저녁·9/21 저녁) · V-10 → 9/20 저녁 · F4-03 → 9/20 저녁·9/21 저녁 · ENV-03 → 9/21 저녁(INT-4 와 한 세션)
               UT-F1·UT-FLOW·CR-01 → 9/22 오전 (9/21 저녁은 구현·로봇 교대에 집중)
  · 고침: 마일스톤 위쪽 표(강사 일정) 9/21~23 행이 로봇 슬롯 글로 덮였던 것 복구 · G2 조건에서 UT-F4 분리 · 완료 행 진행 1.0 · 중복 ID(DOC-01) · ID 없는 행
실행: python3 tools/gen/patch_20260919_audit.py 출력.xlsx → 구글 시트 '스프레드시트 바꾸기'. 다시 실행해도 같은 결과가 나온다."""
import sys, os, re, tempfile, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from xlsx_patch import Book, Row, rebuild_todo, set_slots
from livesheet import SID, load, timeline
import gen_todo

ID = 'AH'
def S(*xs): return [tuple(x.split()) for x in xs]          # S('9/19 오전','9/19 오후')

# id: dict(task, owner, deliv, crit, note, slots) — 없는 키는 그대로 둔다
EDIT = {
 # --- cobot_common: 사람별 파일 · 이름이 같은 공용 함수/기능 함수 구분
 'INF-02': dict(task='cobot_common 2/4 · motion.py — 기본 이동·그리퍼 함수(저수준) move_to·move_rel·grip·grip_level·release (값은 V-01·V-23 결과로)',
                deliv='src/cobot_common/cobot_common/motion.py',
                note='R · 사람별 파일이라 PR 이 부딪히지 않는다: motion.py=S · force.py=P · weigh.py=M · bootstrap·config·__init__=H · f1.move_to(F1-01)는 이 함수를 감싼 기능 함수 · 9/18 브랜치(seokhyung/…INF-02-cobot-common-v0)의 robot.py 뼈대는 motion.py 로 옮긴다'),
 'INF-02a': dict(task='cobot_common 1/4 · bootstrap.py(선행) — init(name, robot)·io_node·cfg·shutdown + config.py 로더 + __init__.py(함수 재수출)·함수 이름만 있는 뼈대 motion.py·force.py·weigh.py + Ctrl+C 처리 (Virtual 에서 돌려 본 ts01_repro/virtual/s4_script.py 를 옮겨 적는다)',
                 deliv='src/cobot_common/cobot_common/bootstrap.py, config.py, __init__.py, 뼈대 motion.py·force.py·weigh.py(SDD §3.1 함수 이름·인자 + NotImplementedError), package.xml·setup.py',
                 crit='격리 상태(solo)의 Virtual 에서 rig 스크립트로 movej 연속 3회 + 통신 노드 타이머 2 Hz + 멈춰 있을 때 Ctrl+C → 깨끗이 종료·재실행 정상 (움직이는 중 Ctrl+C 는 최선 시도 — V-24)',
                 note='✅ PR #3 merge(9/19) — git pull → cbc 후 S·P·M 은 자기 파일(motion·force·weigh)만 채운다 · 두산 함수는 함수 안에서 from .bootstrap import dsr → dsr().movej(...) (맨 위 DSR_ROBOT2 import 금지) · 구독은 자기 파일의 setup_io(node) · Ctrl+C 는 init() 이 단독 · Virtual 에서 모션 중 Ctrl+C 정지 확인(실기는 V-24)'),
 'INF-02b': dict(task='cobot_common 3/4 · force.py — 힘 함수 force_on/off·force_reached·contact_down·periodic_search·safe_retreat + 패키지 정리·리뷰(네 사람이 나눠 쓴 함수의 일관성)',
                 deliv='src/cobot_common/cobot_common/force.py', note='F1-02(9/20 오전)가 contact_down 을 기다린다 · Virtual에는 힘이 없으므로 호출 순서만, 값은 V-03 · 자기 파일(force.py)만 고친다 · 이동이 필요한 곳(safe_retreat 등)은 motion.py 가 나오기 전까지 임시 stub'),
 'INF-02c': dict(task='cobot_common 4/4 · weigh.py — weigh(n, reset=False) 저수준 측정 · V-02 측정 도구에서 이식 (reset 은 선택 동작·응답 상한 3 s·실패 시 반복 금지, TS-03)',
                 deliv='src/cobot_common/cobot_common/weigh.py', note='R · V-02 와 한 세션 · f2.weigh(F2-01)가 이걸 불러 판정한다'),
 'PKG-01': dict(note='V-20 의 재료 · cobot_common 없이도 작성 가능 · 30분 · ✅ F3(박진용) PR #4 merge(9/19) · F1(한석형)·F2(민범진) 남음'),
 'CELL-02a': dict(note='로봇 불필요 · ✅ 용기·툴 실측 기록 docs/test_logs/20260918_CELL-02a_용기치수측정.md (PR #4) — 그릇 외경 114 mm > RG2 최대 폭 110 mm(테두리 파지) · 수세미 중심 이동 한계 10 mm → DSN-03 안건 · 남은 것: 홈 커팅 도면·툴 홀더 위치'),
 'INF-04': dict(task='config 골격 — params.yaml(f1·f2·f3·flow·hmi 절) + cell.yaml 키 골격만(값·파일 주인은 한석형) + prewash_bringup 런치 2종(flow_node 1개 실행 · use_mock 인자)',
                note='오전은 INF-02a 하나만 → 오후로 · cell.yaml 에 티칭 값이 이미 있으면 건드리지 않는다 · 기동 확인은 V-20 에서', slots=S('9/19 오후')),
 'INF-03': dict(note='로봇 없이 flow 개발 · 오전은 FLOW-01 메인 뼈대 먼저, mock 은 저녁', slots=S('9/19 저녁')),
 'F1-01': dict(task='f1.move_to(station, carrying) + 일반 place — cobot_common.move_to 를 감싼 기능 함수(Result 반환). 좌표·프리셋 값은 CELL-04 에서 적은 cell.yaml 을 읽기만 한다',
               deliv='handling.py', note='R · INF-02(S)와 같은 흐름'),
 'F2-01': dict(task='f2.weigh(kind) · leftover_loop · shake(WASTE) — cobot_common.weigh 를 불러 잔반 판정까지 · 시작 시 강한 파지(HOLD)·끝나면 NORMAL·전후 폭 비교'),
 # --- 주인 하나로 (주도(참여))
 'V-20': dict(owner='M(H)', crit='격리 상태(solo)에서 함수 번갈아 2바퀴, 모션 중 /flow/state 2 Hz, stop 수락(함수 사이), 멈춰 있을 때 Ctrl+C 뒤 재실행 정상', note='재료: INF-02a bootstrap(H) + FLOW-01 메인 뼈대(M) + PKG-01 빈 함수(S·P 는 PKG-01 제출로 참여 끝) · 안 되면 구조 ③(결정 기록 표)'),
 'ENV-03': dict(owner='H(M)', note='INT-4·V-13 과 한 세션(PC-A mock flow ↔ PC-B HMI) · 안 되면 Discovery Server → 그래도 안 되면 PC 1대(결정 A)', slots=S('9/21 저녁')),
 'CELL-04': dict(owner='S(M)', note='R · V-19 를 이 세션 안에서 · 박진용(힘 함수·도면)·황인재(bootstrap)는 불참 · V-22 는 move_to 가 생긴 뒤 티칭 2차에서'),
 'CELL-04b': dict(note='R · 9/20 첫 순서 · V-22(좌표 재현 오차)를 이 세션 안에서 · V-04·V-15·F1-05·F1-03·F3-02 가 기다린다'),
 'V-22': dict(note='R · 티칭 2차(CELL-04b) 세션 안에서 — YAML 좌표를 ROS 로 보내려면 INF-02 move_to 가 먼저 있어야 한다', slots=S('9/20 오전')),
 'V-23': dict(owner='S', note='R · grip_level 구현 방법을 정한다(INF-02) · 결과는 DSN-03 에서 공유(F2-01 shake 가 쓴다)'),
 'V-16': dict(owner='M(S)', note='R · F2-01 shake 의 첫 단계로(V-07 과 한 세션) · 찾은 HOLD 값은 한석형이 cell.yaml 프리셋에 반영', slots=S('9/20 오전')),
 'V-15': dict(owner='S(P)', note='R · 티칭 2차·기구 고정 뒤 · F1-05 의 첫 단계로'),
 'V-04': dict(owner='S(P)', note='R · 티칭 2차·기구 고정 뒤 · F1-05 의 첫 단계로 · periodic_search(INF-02b)는 박진용이 제공·참여'),
 'V-05': dict(task='V-05 그리퍼 드라이버 연결 확인 — /onrobot/sendCommand 응답 + 현재 폭을 읽을 경로 확정 (강사 배포 드라이버는 OnRobotRGInput 토픽을 발행하지 않는다 → /onrobot_joint_states 관절각을 폭으로 환산 등. DO/DI 배선 방식은 예비)',
              crit='명령 → 동작 → 폭 값(mm)이 코드에서 읽힘', note='R · V-01 과 한 세션 · 🚨 9/19 확인: 드라이버가 내는 것은 JointState 뿐 → 폭 경로를 여기서 정해 INF-02 grip 에 반영, 결과는 DSN-03 에서 공유(IRD·SDD 수정)'),
 'V-24': dict(owner='H', task='V-24 (선택) 동작 중 소프트 정지·타임아웃 — 비동기 이동(amovej/amovel) + check_motion 폴링 + motion/move_stop 서비스(DSR_ROBOT2 에 stop 함수 없음). shutdown() 의 정지 명령이 모션 중에 먹는지도 확인. 메인 스레드에서만(Virtual)',
              note='선택 과제(시간 남을 때만): 안 되면 정지는 기능 함수 사이로만, 움직이는 중 Ctrl+C 는 "브링업 재시작 필요" 로그(현재 기본) · 급한 정지는 E-Stop'),
 'INT-4b': dict(owner='M(P)'),
 'ENV-04': dict(task='구조 변경 적용 — git pull → build·install·log 삭제 후 cbc → 작업 브랜치에 main 병합 → 에이전트에 AGENTS·IRD v3.0·SDD §3.2 재학습 · 프롬프트 파일 교체 · 🚨 .bashrc 에 격리 한 줄(ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST) + solo/team60 별칭',
                crit='ros2 interface list 에 cobot_msgs 가 msg 2개만 · python3 -c "import cobot_api" 성공 · 프롬프트 교체 완료 · rosinfo 가 ROS_DOMAIN_ID=60 · RANGE=LOCALHOST',
                note='옛 빌드가 남으면 삭제된 서비스 타입이 계속 보인다 · 격리는 안전 규칙(AGENTS §3 규칙 13): 같은 망에서 서로 보이면 내 movej 가 남의 Virtual·실기에도 간다(도메인 번호는 60 그대로) · 환경설정 문서 §9'),
 # --- 부하·로봇 슬롯
 'UT-F1': dict(note='R · 함수별 TC 는 구현 직후 바로 수행, 이 칸은 남은 TC·녹화 마무리 · 9/21 저녁은 F1-04 에 집중', slots=S('9/22 오전')),
 'UT-FLOW': dict(note='로봇 불필요 · 9/21 저녁은 UT-F2(로봇)에 집중', slots=S('9/22 오전')),
 'CR-01': dict(note='L2 통합(9/22 오후) 전에 · PR 리뷰에서 이미 본 것은 생략 · 30분', slots=S('9/22 오전')),
 'F3-02': dict(slots=S('9/20 오전', '9/20 오후')),
 'F3-03': dict(note='R · 시연 필수 경로 — 함수가 둘이라 2칸(9/20 저녁 뼈대·V-10, 9/21 저녁 실기 마무리)', slots=S('9/20 저녁', '9/21 저녁')),
 'V-10': dict(slots=S('9/20 저녁')),
 'F4-01': dict(note='fake_state_pub 포함(INF-03 에서 옮김) · 9/19 저녁은 DSN-03 회의·반영 → 9/20 오전, F4-02 와 같은 흐름', slots=S('9/20 오전')),
 'F4-03': dict(note='DSN-03 결과 반영 · 산출물은 DSN-03 에서 화면 방식(Next.js)이 확정되면 바꾼다', slots=S('9/20 저녁', '9/21 저녁')),
 'INT-12a': dict(note='R · 9/22 오후 첫 순서'), 'INT-12b': dict(note='R · 9/22 오후 INT-12a 다음'), 'INT-13': dict(note='R · 9/22 저녁 첫 순서'),
 'INT-3a': dict(note='R · INT-13 통과(G3) 뒤에 착수 — 밀리면 9/23 오전으로'),
 # --- 옛 값·빈 칸
 'V-02': dict(task='V-02 하중 측정 정밀도 — 100/200 g 추 10회'),
 'TS-01': dict(task='TS-01 두산 API 초기화 누락·서비스 콜백 안 로봇 명령 교착 — 원인·재현·구조 5종 Virtual 비교 → 구조 변경으로 종결(DSN-02b)'),
 'DSN-03': dict(task='2차 회의 — 반납 구역 방식(V-01 결과)·HMI 설계(F4-00)·실패 코드·정책·YAML 키 규칙 + 구조 변경 후속(모니터·기록 노드 추가 여부, /cell/force·/cell/grip_width 토픽, V-20 결과, '
                     '공용 함수 분담·사람별 파일 확인) + 9/21 저녁 로봇 순서(S·P·M) + 격리 규칙(LOCALHOST)·Ctrl+C 주인(결정 기록 S1~S4) 확인 + 그릇 파지 방식(외경 114 mm > RG2 110 mm, CELL-02a 실측)·정지 방식 DR_QSTOP 확인',
                deliv='docs/meetings/20260919_결정기록_DSN-03.md'),
 'DOC-05': dict(deliv='docs v3.x, 노션'),
 'BRF': dict(deliv='노션 진행률 · 당일 로봇 순서'),
 'DOC-06': dict(deliv='발표', crit='20분 안에 발표 + QnA 대응'),
 'WRAP-01': dict(deliv='정리 체크', crit='로봇 설정 초기화 · 자리 원상 복구'),
}
# 상태 갱신: id → (상태, 진행)
STATUS = {'INF-02a': ('완료', '1.0'),      # PR #3 merge (9/19 12:22)
          'PKG-01': ('진행 중', '0.33'),    # F3 골격 PR #4 merge (9/19 12:39) · F1·F2 남음
          'CELL-02a': ('진행 중', '0.5')}   # 용기·툴 실측 기록 merge(PR #4) · 홈 도면·홀더 위치 남음
# 팀(구역) 이동: id → (새 팀, 이 ID 행 바로 뒤에 둔다)
MOVE = {'INF-02': ('전원', 'INF-02a'), 'INF-02b': ('전원', 'INF-02'),      # cobot_common 네 행은 한곳에: 02a(선행) → 02 → 02b → 02c
        'V-23': ('F1', 'V-05'), 'V-04': ('F1', 'V-15'), 'V-16': ('F2·flow', 'V-07'), 'V-24': ('F4', 'F4-03'), 'SAFE-01': ('전원', 'NOTE-01'), 'V-21': ('전원', 'TS-01')}
DELETE = ['INT-13p']                                    # INT-13 P(S) 와 같은 일
EASY = {
 'INF-02': '공용 로봇 함수 중 기본 이동·그리퍼(move_to·move_rel·grip·grip_level·release)를 내 파일 motion.py 에 만든다. 내가 검증(V-01·V-23)하면서 쓰는 바로 그 동작이다. 다른 사람들이 이걸 가져다 쓴다',
 'INF-02a': '공용 로봇 함수의 시작·끝 부분(init·shutdown)과 설정 읽기를 만든다. 가상 로봇에서 돌려 본 시험 코드를 옮겨 적는다. 세 사람이 채울 빈 파일(motion·force·weigh)도 같이 올린다. 이게 있어야 모두가 자기 함수를 돌려 볼 수 있다',
 'INF-02b': '공용 로봇 함수 중 힘 관련(힘제어 켜기/끄기, 닿았는지 판정, 닿을 때까지 내려가기, 흔들며 찾기, 안전 후퇴)을 내 파일 force.py 에 만들고, 네 사람이 나눠 쓴 함수들이 서로 맞는지 정리한다',
 'INF-02c': '공용 로봇 함수 중 무게 재기(weigh)를 내 파일 weigh.py 에 만든다. V-02 에서 만든 측정 도구를 옮겨 적는다. 0점 재설정은 선택 동작으로',
 'INF-04': '설정 파일의 뼈대(params.yaml 의 다섯 절, cell.yaml 은 키 이름만 — 값은 한석형)와 한 번에 실행하는 런치 파일 2개를 만든다. 런치는 flow_node 하나만 띄운다',
 'F1-01': '지정 위치로 이동(f1.move_to)과 그냥 놓기(place)를 만든다. 공용 함수 move_to 를 감싸 결과(Result)를 돌려주는 함수다. 좌표는 cell.yaml 에서 읽기만 한다',
 'F2-01': '무게 재기·잔반 판정·털기를 만든다. 무게는 공용 함수 weigh 를 불러서 잰다. 털기 전에 강한 파지, 끝나면 보통 파지',
 'CELL-04': '한석형·민범진이 로봇을 손으로 움직여 위치(홈·무게 재는 곳·잔반통·반납 구역·팔레트·수조·격리)의 좌표를 읽어 cell.yaml 에 적는다. 스펀지 홈과 툴 홀더는 기구를 고정한 뒤 2차에서',
 'V-22': '설정 파일에 적은 좌표대로 로봇을 보냈을 때 실제 티칭 위치와 얼마나 차이 나는지 잰다(2 mm 이내). 이동 함수(move_to)가 생긴 뒤 티칭 2차 때 같이 한다',
}
TITLES = {'할일_한석형': '한석형 — 팀장 · F1 파지·이송·적재 + 좌표 계산·티칭(cell.yaml) + cobot_common 기본 이동·그리퍼(motion.py)',
          '할일_민범진': '민범진 — F2 무게·털기·헹굼 + flow_node + mock · 통합 실행 리더 + cobot_common weigh(weigh.py)',
          '할일_박진용': '박진용 — F3 접촉 닦기 + cobot_common 힘 함수(force.py)·패키지 정리·리뷰 + 안전 파라미터',
          '할일_황인재': '황인재 — PM · F4 웹 HMI + cobot_api·cobot_msgs·cobot_common bootstrap·런치·일정표·제출'}
LECTURE = {     # 마일스톤 시트 위쪽 표(강사 일정) — 지난 패치가 로봇 슬롯 글로 덮어쓴 행을 되돌린다
 '9/21 월': ('6차시 오전 DRL srv·launch, 오후 프로젝트 중간점검(조별 30분 발표 + 30분 토론)', '중간점검 발표. 로봇·개발은 저녁만(F1-04 → F3-03 → UT-F2 1시간씩 교대 · INT-4·ENV-03)'),
 '9/22 화': ('7차시 모듈 구현 프로그래밍', '오전 L1 마무리(UT-F1·UT-F3·UT-FLOW) + 코드리뷰 + 노션 업로드(노드 구조·HMI gif·안전·GitHub 최신), 오후 L2(INT-12a·12b), 저녁 L2(INT-13) → L3 착수'),
 '9/23 수': ('8차시 모듈 통합·PROTO 통합 동작 테스트', '오전 L3(그릇·컵) + 결함 수정 → 오후~저녁 L4 전체 통합 → 영상 → 기능 동결 v1.0-demo'),
}
GATE = {'G2 L1': {'C': 'UT-F1·F2·F3·FLOW 통과 + 녹화 (함수별 TC 는 구현 직후 바로 수행) + 코드리뷰 CR-01 · UT-F4 는 F4-04 뒤 9/22 오후'}}
SLOT = {        # 로봇 슬롯 표
 '9/19 토': {'B': 'CELL-04 티칭 1차(S 주도, M) + V-19(S) · 로봇 불필요: INF-02a bootstrap(H)·FLOW-01 뼈대(M)·힘 함수·치수 도면(P)·PKG-01(S·M·P)',
             'C': 'V-02 + weigh 이식(M) → V-01·V-05·V-23 + 기본 함수(S) · 로봇 불필요: V-20 Virtual(M·H)·INF-04(H)·CELL-02 기구 제작·V-12(P·H)·F4-00(H)',
             'D': 'DSN-03 2차 회의(전원, 로봇 불필요) → V-03(P) → F1-01(S) · 로봇 불필요: INF-03 mock(M)'},
 '9/20 일': {'B': 'CELL-04b 티칭 2차 + V-22(S·P) → F1-02·V-14(S) / V-18·F3-02(P) / V-07·V-16·F2-01(M, V-16 은 S 참여) — 1시간씩 교대',
             'C': 'V-04·V-15 → F1-05(S, P 참여) / F3-02(P) / F2-01(M)', 'D': 'F1-03·V-08(S) / F3-03·V-10(P) / F2-02(M) · 로봇 불필요: F4-03(H)·MID-01'},
 '9/21 월': {'D': '1시간씩 교대(순서는 DSN-03 에서 확정): F1-04·V-06(S) → F3-03(P) → UT-F2(M) · 로봇 불필요: INT-4·V-13·ENV-03(H·M)·F4-03(H)'},
 '9/22 화': {'B': 'UT-F1 마무리(S) / UT-F3(P) · 로봇 불필요: UT-FLOW(M)·CR-01(전원)·노션 업로드(H)', 'D': 'INT-13(P·S) → 통과하면 INT-3a 그릇 L3 착수(M 실행, 전원)'},
}
RULES = {       # B 열 글자 → C 열 새 글
 '9/22(화) 오전': 'L1 단위기능 테스트(UT-F1·F2·F3·FLOW) 통과 — 함수별 TC 는 구현 직후 바로 수행. UT-F4 는 9/22 오후. 미통과 기능은 범위 방어표대로 축소 · 코드리뷰(CR-01) · 노션에 노드 구조·HMI 화면·안전 자료 업로드 · GitHub 최신',
 '이 파일(구글 드라이브)': '일정표 정본은 구글 공유 드라이브의 이 xlsx. 테스트 기준(TC·INT·V)은 저장소 docs/03_설계_SDD.md §9. 완료 행은 Time Line 에 남기고 완료 목록 시트에 복사된다(패치가 자동으로 채운다)',
}
RULES_A = {     # A 열 글자 → C 열 새 글
 '개발 흐름': '단위기능 완성 → 단위기능 테스트(TC 있는 작업) → main pull → 통합 테스트 → main PR → Actions 자동 검사(main 충돌·산출물). 문서만 바뀐 PR 은 자동 승인·merge, 코드·설정·도구·인터페이스 정본이 포함된 PR 은 PM 에이전트가 전부 읽고 승인·merge 또는 거절(황인재 위임, 보류는 제목 [hold]). 로봇 움직이는 테스트는 녹화 권장 YYYYMMDD_TCxx_기능_담당_시도N.mp4',
}
NEW_RULES = [
 ('담당 표기', 'A(B) · A,B', 'A(B) = A 가 주도하고 B 는 참여. A,B = 같은 이름의 작업을 각자 자기 몫만 따로 한다(예 PKG-01). 한 가지 일을 둘이 같이 할 때는 반드시 주도(참여)로 적어 주인을 한 명으로 한다. 팀(구역)은 주도자의 기능을 따른다. 단 공용 패키지(cobot_common·config·런치·mock) 작업은 주도자와 상관없이 전원 구역의 "계약"에 모은다'),
 ('🚨 격리', '기본 LOCALHOST · team60 은 통합 때만', 'Virtual·rig·mock 시험과 혼자 하는 실기 시험은 격리 상태(solo = ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST, 도메인은 60 그대로)에서만. team60(서로 보이게 풀기)은 PC-A↔PC-B 통합(ENV-03·INT-4·L3·L4·리허설·시연) 때만 켜고 끝나면 solo. 로봇을 움직이기 전에 rosinfo 로 확인 (AGENTS §3 규칙 13)'),
 ('공용 파일', 'cobot_common · config', 'cobot_common 은 사람별 파일: bootstrap.py·config.py·__init__.py = H / motion.py = S / force.py = P / weigh.py = M (부르는 쪽은 그대로 cc.함수()). config/cell.yaml 은 한석형 혼자, params.yaml 은 자기 절만'),
]
HISTORY = ['4.3', '점검', 'V-04·15·16·20·22·23·24, ENV-03, CELL-04, INT-4b, INT-13p(삭제), INF-02·02a·02b·02c·03·04, F1-01, F2-01, F3-02·03, V-10, F4-01·03, UT-F1·FLOW, CR-01, 마일스톤·로봇 슬롯·규칙·완료 목록·할일',
           '주인을 한 명으로(공동 표기 → 주도(참여)), 팀 구역 = 주도자 기능, INT-13p 삭제. cobot_common 사람별 파일(motion·force·weigh), cell.yaml 은 한석형 혼자. '
           '부하·로봇: INF-04→9/19 오후, INF-03→저녁, V-22→9/20 오전(티칭 2차 안), V-16→9/20 오전, F4-01→9/20 오전, F3-03 2칸(9/20 저녁~), ENV-03→9/21 저녁, UT-F1·UT-FLOW·CR-01→9/22 오전. '
           'G2 조건에서 UT-F4 분리. 강사 일정 표 9/21~23 복구, 완료 행 진행 1.0, DOC-01a/b·DSN-01b',
           '9/19 PM 점검: 같은 일에 주인이 둘·같은 파일을 세 사람이 수정·선행 작업보다 앞선 검증(V-22)·한 칸 5~7건·9/21 저녁 로봇 3명', 'S,M,P,H']


HISTORY2 = ['4.4', '점검', 'INF-02·02a·02b·02c', 'cobot_common 네 행을 전원 구역 "계약"에 선행 순서로 모음(02a bootstrap → 02 motion → 02b force → 02c weigh). INF-02b 가 F3 구역에 떨어져 있어 전원 구역에서는 a·c 만 보였다. 제목에 1/4~4/4 와 파일 이름. 공용 패키지 작업은 전원 구역에 둔다는 규칙 추가',
            '팀원 보고: cobot_common 일정이 흩어져 있고 순서가 선행 관계와 반대', 'S,M,P,H']

HISTORY3 = ['4.5', '안전·기준', 'ENV-04, INF-02a, V-05, V-20, V-24, DSN-03, 규칙', '🚨 기본 격리: 도메인은 60 그대로, .bashrc 에 ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST 한 줄. PC 여러 대 통합 때만 그 터미널에서 team60 → 끝나면 solo. ENV-04 에 .bashrc 격리 설정 추가. '
            'Ctrl+C 는 cobot_common.init() 이 단독 처리, flow_node·rig 는 try/finally 만. INF-02a·V-20 기준을 "멈춰 있을 때 Ctrl+C"로, 움직이는 중 정지(move_stop)는 V-24 로. INF-02a 의 세 파일은 함수 이름만 있는 뼈대. V-05: 그리퍼 드라이버가 OnRobotRGInput 을 발행하지 않으므로 현재 폭을 읽을 경로를 V-05 에서 확정',
            'F4 점검 보고(9/19): 모든 PC 가 도메인 60·서비스 이름 /dsr01 공통 → 시험 명령이 남의 Virtual·실기에 전달될 수 있음(로봇에 물린 PC 도 와이파이로는 이어져 있다). DSR_ROBOT2 에 정지 함수 없음, rclpy 기본 SIGINT 가 컨텍스트를 먼저 닫음', 'S,M,P,H']

HISTORY4 = ['4.6', '안전·단순화', 'ENV-04, 규칙 🚨 격리, DSN-03', '격리 방식을 단순하게: 개인 도메인 번호(61~64)는 나누지 않는다. 도메인은 전원 60 그대로, .bashrc 에 ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST 한 줄 + solo/team60 별칭. PC 여러 대 통합 때만 team60',
            'PM 결정(9/19): 로봇에 랜선으로 붙는 PC 는 1대뿐이지만 그 PC 도 와이파이로는 다른 PC 와 이어져 있어 DDS 로는 명령이 들어온다 → 격리는 유지하되 번호 관리의 번거로움은 없앤다', 'S,M,P,H']

HISTORY5 = ['4.7', 'PR 흐름', '규칙(개발 흐름)', 'PR 승인 방식 변경: 문서만 바뀐 PR 은 지금처럼 자동 승인·merge, 코드·설정·도구·인터페이스 정본이 포함된 PR 은 PM 에이전트가 바뀐 것을 전부 읽고 황인재 확인 뒤 merge',
            '9/19 확인: 기계 검사(main 충돌·산출물)만 통과하면 19초 만에 자동 merge 되어 로봇을 움직이는 코드가 아무도 읽지 않은 채 main 에 들어갈 수 있었다', 'S,M,P,H']

HISTORY6 = ['4.8', '진행·PR', 'INF-02a, 규칙(개발 흐름)', 'INF-02a 완료(PR #3 merge, 9/19 12:22): cobot_common 실행 뼈대 + 사람별 뼈대 파일 → S·P·M 이 자기 파일을 채울 수 있다. PR 검토는 PM 에이전트가 직접 승인·merge 또는 거절(황인재 위임)',
            'PR #3 검토·merge · 황인재 지시(개인 브랜치 → main PR 은 PM 에이전트가 검토 후 승인/거절)', 'S,M,P,H']

HISTORY7 = ['4.9', '진행', 'PKG-01, CELL-02a, DSN-03', 'PKG-01 F3 골격(PR #4) merge → 진행 중 1/3 · CELL-02a 실측 기록 merge → 진행 중. DSN-03 안건에 그릇 파지 방식(외경 114 mm > RG2 최대 폭 110 mm)·정지 방식 DR_QSTOP 추가',
            'PR #4 검토·merge (박진용)', 'S,P,H']


def main(out):
    gen_todo.EASY.update(EASY)
    b = Book.from_live(SID)
    tl = b.sheet('Time Line'); d = b.sheet('상세(산출물·완료기준)')

    def has(sheet, col, v):
        try: sheet.find(col, v); return True
        except KeyError: return False

    def drop(sheet, i):                                   # 행 삭제(전체 행 수 유지)
        r = sheet.rows.pop(i); sheet.merges = [m for m in sheet.merges if m[1] is not r and m[3] is not r]; sheet.rows.append(Row('', {}))

    # 0) ID 정리: DOC-01 두 행 → a/b, ID 없는 재회의 행 → DSN-01b
    docs = [i for i, r in enumerate(tl.rows) if tl.text(r, ID).strip() == 'DOC-01']
    if len(docs) == 2:
        tl.rows[docs[0]].set(ID, 'DOC-01a'); tl.rows[docs[1]].set(ID, 'DOC-01b')
        q = d.rows[d.find('A', 'DOC-01')]; q.set('A', 'DOC-01b')
        q2 = q.clone(); q2.set('A', 'DOC-01a'); q2.set('C', tl.text(tl.rows[docs[0]], 'C')); q2.set('E', 'docs/01~03 v1'); d.insert(d.find('A', 'DOC-01b'), q2)
    for i, r in enumerate(tl.rows):
        if tl.text(r, 'C').strip() == '1차 회의 후 재회의' and not tl.text(r, ID).strip():
            r.set(ID, 'DSN-01b')
            if not has(d, 'A', 'DSN-01b'):
                q = d.rows[d.find('A', 'DSN-02')].clone()
                for c, v in zip('ACDEFG', ['DSN-01b', '1차 회의 후 재회의', '전원', '결정 기록에 통합', '합의', '']): q.set(c, v)
                d.insert(d.find('A', 'DSN-02') + 1, q)
    # 1) 셀 고치기
    for tid, e in EDIT.items():
        r = tl.rows[tl.find(ID, tid)]
        if 'task' in e: r.set('C', e['task'])
        if 'owner' in e: r.set('D', e['owner'])
        if 'slots' in e: set_slots(r, e['slots'])
        if has(d, 'A', tid):
            q = d.rows[d.find('A', tid)]
            for c, k in (('C', 'task'), ('D', 'owner'), ('E', 'deliv'), ('F', 'crit'), ('G', 'note')):
                if k in e: q.set(c, e[k])
    for tid, (st, pg) in STATUS.items():
        r = tl.rows[tl.find(ID, tid)]; r.set('F', st); r.set('E', pg)
    # 2) 완료 행은 진행 1.0
    for r in tl.rows:
        if tl.text(r, 'F').strip() == '완료' and tl.text(r, ID).strip(): r.set('E', '1.0')
    # 3) 팀(구역) 이동 — A 열 서식은 옮겨 간 자리의 윗행 것을 쓴다
    for tid, (team, after) in MOVE.items():
        src = tl.find(ID, tid); dst = tl.find(ID, after)
        if src != dst + 1:
            if tl.text(tl.rows[src], 'A').strip():             # 구역 첫 행이면 구역 이름표를 다음 행에 넘긴다
                tl.rows[src + 1].cells['A'] = list(tl.rows[src].cells['A'])
            tl.move(src, dst + 1)
        r = tl.rows[tl.find(ID, tid)]; up = tl.rows[tl.find(ID, after)]
        a_style = up.style('A') if not tl.text(up, 'A').strip() else tl.rows[tl.find(ID, after) + 2].style('A')   # 구역 첫 행(글자 있는 칸)의 서식은 쓰지 않는다
        r.set('A', None, style=a_style)
        qs = d.find('A', tid); qd = d.find('A', after)
        if qs != qd + 1: d.move(qs, qd + 1)
        d.rows[d.find('A', tid)].set('B', team)
    # 4) 중복 행 삭제
    for tid in DELETE:
        if has(tl, ID, tid): drop(tl, tl.find(ID, tid))
        if has(d, 'A', tid): drop(d, d.find('A', tid))
    # 5) 마일스톤·로봇 슬롯
    m = b.sheet('마일스톤·로봇 슬롯')
    k_mile = m.find('A', '마일스톤'); k_slot = m.find('A', '로봇 슬롯', prefix=True)
    for i, r in enumerate(m.rows):
        key = m.text(r, 'A').strip()
        if i < k_mile and key in LECTURE:
            r.set('B', LECTURE[key][0]); r.set('C', LECTURE[key][1]); r.cells.pop('D', None)
        elif k_mile < i < k_slot and key in GATE:
            for c, v in GATE[key].items(): r.set(c, v)
        elif i > k_slot:
            if key in SLOT:
                for c, v in SLOT[key].items(): r.set(c, v)
            if key == '9/18 금': r.set('D', m.text(r, 'D').replace(' · V-20은 Virtual(S·M)', ''))
    # 6) 규칙
    ru = b.sheet('규칙')
    for r in ru.rows:
        key = ru.text(r, 'B').strip()
        if key in RULES and ru.text(r, 'A').strip() in ('마감', '정본'): r.set('C', RULES[key])
    for r in ru.rows:
        if ru.text(r, 'A').strip() in RULES_A: r.set('C', RULES_A[ru.text(r, 'A').strip()])
    ru.rows[0].set('A', '운영 규칙 (PreWash-Cell 일정표 v4.9)')
    if has(ru, 'A', '🚨 도메인'):                          # v4.5 의 규칙 이름(개인 도메인 번호 방식) → v4.6 에서 '🚨 격리'(LOCALHOST 한 줄)로
        ru.rows[ru.find('A', '🚨 도메인')].set('A', '🚨 격리')
    for rule in NEW_RULES:
        if has(ru, 'A', rule[0]):
            r_ = ru.rows[ru.find('A', rule[0])]; r_.set('B', rule[1]); r_.set('C', rule[2])
        else:
            k = ru.first_empty(); n = ru.rows[k - 1].clone()
            for c, v in zip('ABC', rule): n.set(c, v)
            ru.rows[k] = n
    # 7) 변경이력
    h = b.sheet('변경이력')
    for hist in (HISTORY, HISTORY2, HISTORY3, HISTORY4, HISTORY5, HISTORY6, HISTORY7):
        if not has(h, 'A', hist[0]):
            k = h.first_empty(); n = h.rows[k - 1].clone()
            for c, v in zip('ABCDEF', hist): n.set(c, v)
            h.rows[k] = n
    # 8) 고친 Time Line 을 다시 읽어 완료 목록·할일 시트를 채운다
    tmp = os.path.join(tempfile.mkdtemp(), 'stage.xlsx'); b.save(tmp)
    rows, det = timeline(load(tmp))
    done = b.sheet('완료 목록'); txt, ctr = d.rows[1].style('C'), d.rows[1].style('A'); n_old = len(done.rows)
    done.rows = done.rows[:1]
    for r in rows:
        if r['status'] != '완료' or not r['slots']: continue
        n = Row('', {})
        vals = [r['id'] or '—', r['task'], r['owner'], det.get(r['id'], {}).get('deliv', ''), ' '.join(r['slots'][0]), ' '.join(r['slots'][-1])]
        for c, v, st in zip('ABCDEF', vals, [ctr, txt, ctr, txt, ctr, ctr]): n.set(c, v, style=st)
        done.rows.append(n)
    while len(done.rows) < n_old: done.rows.append(Row('', {}))
    people = [('할일_한석형', 'S'), ('할일_민범진', 'M'), ('할일_박진용', 'P'), ('할일_황인재', 'H')]
    rebuild_todo(b, lambda L: gen_todo.person_entries(rows, det, L), people)
    for name, _ in people:
        if name in b.paths: b.sheet(name).rows[0].set('A', TITLES[name])
    b.save(out); print('->', out)
    report(rows)
    return rows


def report(rows):
    """사람별·칸별 부하(주도 + (참여)). 브리핑·PM-01 은 뺀다. 5건 이상이면 ⚠."""
    load_ = collections.defaultdict(list)
    for r in rows:
        if r['status'] == '완료' or r['id'] in ('BRF', 'PM-01'): continue
        lead = re.sub(r'\(.*?\)', '', r['owner']); part = ''.join(re.findall(r'\((.*?)\)', r['owner']))
        L = set('SMPH') if '전원' in lead else set(c for c in lead if c in 'SMPH')
        P = (set('SMPH') if '전원' in part else set(c for c in part if c in 'SMPH')) - L
        for dday, p in r['slots']:
            if '~' in dday or int(dday.split('/')[1]) > 23: continue
            for w in L: load_[(dday, p, w)].append(r['id'])
            for w in P: load_[(dday, p, w)].append('(' + r['id'] + ')')
    order = {'오전': 0, '오후': 1, '저녁': 2}
    for w in 'SMPH':
        print('==', w)
        for k in sorted([k for k in load_ if k[2] == w], key=lambda k: (int(k[0].split('/')[1]), order[k[1]])):
            print(f"  {k[0]} {k[1]} [{len(load_[k])}]{' ⚠' if len(load_[k]) >= 5 else ''} {' '.join(load_[k])}")


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'prewash_일정표_0919h.xlsx')
