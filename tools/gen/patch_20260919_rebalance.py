# -*- coding: utf-8 -*-
"""9/19 — 구조 변경 후속 + 부하 재배치. 구글 시트의 '현재' 내용에 변경만 얹고 모든 시트에 반영한다.
  · 새 작업: ENV-04 구조 변경 적용 · PKG-01 기능 패키지 골격 · INF-02a bootstrap(H) · INF-02c weigh(M) · CELL-04b 티칭 2차
  · cobot_common 분담: bootstrap=H · 기본 이동·그리퍼=S · weigh=M · 힘 함수·패키지 정리=P
  · 구현에 딸린 사전 검증(V)은 그 구현 칸으로, 한 사람 한 칸에 큰 작업 1 + 작은 작업 2 이내
  · 게이트: L1 9/20 저녁 → 9/22 오전, L2 → 9/22 저녁, L3 → 9/23 오전, 동결 9/23 저녁 그대로
실행: python3 tools/gen/patch_20260919_rebalance.py 출력.xlsx → 구글 시트 '스프레드시트 바꾸기'. 다시 실행해도 행이 중복되지 않는다."""
import sys, os, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from xlsx_patch import Book, Row, new_timeline_row, rebuild_todo, set_slots
from livesheet import SID, load, timeline
import gen_todo

ID = 'AH'
A, B, C = '오전', '오후', '저녁'
def S(*xs): return [tuple(x.split()) for x in xs]          # S('9/19 오전','9/19 오후')

# id: dict(task, owner, status, deliv, crit, note, slots) — 없는 키는 그대로 둔다
EDIT = {
 'INF-02': dict(task='cobot_common 기본 이동·그리퍼 함수 — move_to·move_rel·grip·grip_level·release (robot.py · V-01·V-22·V-23에서 확인한 값으로)', owner='S',
                deliv='src/cobot_common/cobot_common/robot.py', crit='Virtual에서 move_to 연속 3회 · 실기에서 grip 폭 피드백 수신',
                note='R · 9/19 분담: bootstrap=H(INF-02a) · 기본 이동·그리퍼=S · weigh=M(INF-02c) · 힘 함수·패키지 정리=P(INF-02b) · F1-01과 같은 흐름', slots=S('9/19 오후', '9/19 저녁')),
 'INF-02b': dict(task='cobot_common 힘 함수 — force_on/off·force_reached·contact_down·periodic_search·safe_retreat + 패키지 정리·리뷰(네 사람이 나눠 쓴 함수의 일관성)',
                 note='F1-02(9/19 저녁)가 contact_down 을 기다린다 · Virtual에는 힘이 없으므로 호출 순서만, 값은 V-03', slots=S('9/19 오전', '9/19 오후')),
 'INF-04': dict(crit='mock 런치 한 줄로 flow_node(전부 mock) + hmi 기동', note='config 골격 + 런치 뼈대(flow_node 실행 파일 이름만 맞추면 된다). 기동 확인은 V-20 에서', slots=S('9/19 오전')),
 'INF-03': dict(task='mock 모듈 mock_f1·mock_f3 — 실제와 같은 함수 이름·실패 주입 (fake_state_pub 은 F4-01 로 옮김)', owner='M', deliv='f2_sense_flow/mock/', crit='cobot_api.check_api 통과·실패 주입', note='로봇 없이 flow 개발', slots=S('9/19 오전')),
 'V-20': dict(owner='M,H(S,P)', note='재료: INF-02a bootstrap(H) + FLOW-01 메인 뼈대(M) + PKG-01 빈 함수 · 안 되면 구조 ③(결정 기록 표)', slots=S('9/19 오후')),
 'ENV-03': dict(note='9/21 저녁 INT-4 전까지면 된다 · 안 되면 Discovery Server', slots=S('9/20 오전')),
 'CELL-04': dict(task='공통 좌표 티칭 1차 — HOME·WEIGH·WASTE·반납 구역 기준·팔레트 기준점·수조·격리 (스펀지 홈·툴 홀더는 기구 고정 뒤 2차 = CELL-04b)', owner='S(M,P)',
                 note='R · V-19·V-22 를 이 세션 안에서 · 황인재는 불참(bootstrap 작성)', slots=S('9/19 오전')),
 'ARCH-01': dict(task='시스템 아키텍처 그림 — 구조 변경 반영본(노드 2·함수 모듈 3·드라이버 2) draw.io 다듬기·PC-B 안쪽 채우기 + 노션 산출물 10종 등록', note='MID-01 발표 자료와 같이 작업', slots=S('9/20 저녁')),
 'DSN-04': dict(slots=S('9/19 저녁', '9/20 오전')),
 'DSN-03': dict(task='2차 회의 — 반납 구역 방식(V-01 결과)·HMI 설계(F4-00)·실패 코드·정책·YAML 키 규칙 + 구조 변경 후속(모니터·기록 노드 추가 여부, /cell/force·/cell/grip_width 토픽, V-20 결과, 공용 함수 분담 확인)', crit='미확정 항목 모두 결정'),
 'DSN-02b': dict(deliv='docs/meetings/20260918_결정기록_구조_인터페이스.md, IRD v3.0, SDD v3.0, 그림, 프롬프트'),
 'MID-01': dict(note='구조 변경 근거 1장 포함(TS-01: 발견→재현→구조 5종 비교→결정)'),
 # --- 한석형
 'V-01': dict(note='R · V-05 와 한 세션 · 결과가 INF-02 grip 과 F1-02 폭 판정값이 된다', slots=S('9/19 오후')),
 'V-05': dict(task='V-05 그리퍼 드라이버 연결 확인 — /onrobot/sendCommand 응답·현재 폭 토픽 수신 (강사 배포 Modbus 드라이버 사용. DO/DI 배선 방식은 예비)', crit='명령 → 동작 → 폭 값 갱신', note='R · V-01 과 한 세션', slots=S('9/19 오후')),
 'V-19': dict(note='R · 티칭 1차(CELL-04) 세션 안에서'), 'V-22': dict(note='R · 티칭 1차(CELL-04) 세션 안에서'),
 'V-23': dict(owner='S(M)', note='R · grip_level 구현 방법을 정한다(INF-02)', slots=S('9/19 오후')),
 'V-16': dict(note='R · V-23 뒤 · F2-01 shake 직전', slots=S('9/19 저녁')),
 'F1-01': dict(note='R · INF-02(S)와 같은 흐름', slots=S('9/19 저녁')),
 'F1-02': dict(slots=S('9/20 오전')),
 'V-15': dict(note='R · 티칭 2차·기구 고정 뒤', slots=S('9/20 오후')), 'V-04': dict(note='R · 티칭 2차·기구 고정 뒤 · F1-05 직전', slots=S('9/20 오후')),
 'F1-05': dict(slots=S('9/20 오후')),
 'F1-03': dict(slots=S('9/20 저녁')), 'V-08': dict(note='R · F1-03 의 첫 단계로', slots=S('9/20 저녁')),
 'F1-04': dict(slots=S('9/21 저녁')), 'V-06': dict(note='R · F1-04 의 첫 단계로', slots=S('9/21 저녁')),
 'UT-F1': dict(task='UT-F1 — TC-01·02·05·09 (rig_f1.py 로 내 함수만 단독 실행, 같은 함수 연속 3회 이상)', note='R · 함수별 TC 는 구현 직후 바로 수행, 이 칸은 남은 TC·녹화 마무리', slots=S('9/21 저녁', '9/22 오전')),
 'INT-12b': dict(task='INT-12b F1+F2 — 재파지→헹굼→물털기→팔레트 적재 5회 (주도) · flow_node 에서 실행, use_mock=[f3]', slots=S('9/22 오후')),
 'INT-13p': dict(slots=S('9/22 저녁')),
 # --- 민범진
 'V-02': dict(note='R · 티칭 1차 뒤 첫 순서 · 도구를 INF-02c weigh 로 이식', slots=S('9/19 오후')),
 'FLOW-01': dict(note='메인 뼈대(통신 노드·깃발·예외 보호)는 오전 최우선 — V-20·런치가 기다린다', slots=S('9/19 오전', '9/19 오후', '9/19 저녁')),
 'V-07': dict(note='R · F2-01 shake 의 첫 단계로', slots=S('9/20 오전')),
 'F2-01': dict(slots=S('9/20 오전', '9/20 오후')),
 'F2-02': dict(slots=S('9/20 저녁')), 'FLOW-02': dict(slots=S('9/20 오후')),
 'UT-FLOW': dict(task='UT-FLOW — TC-10 정책 · TC-12 기록 (mock 모듈) + 기능 함수 예외 주입 시 프로그램이 죽지 않고 ROBOT_ERROR→PAUSED · Ctrl+C 종료 뒤 재실행 정상',
                 crit='정책대로, 4행, 예외 주입 후에도 flow_node 생존', slots=S('9/21 저녁')),
 'UT-F2': dict(task='UT-F2 — TC-03·04·08 (rig_f2.py 로 내 함수만 단독 실행, 같은 함수 연속 3회 이상)', note='R · 함수별 TC 는 구현 직후 바로, 이 칸은 남은 TC·녹화 마무리', slots=S('9/21 저녁')),
 'INT-12a': dict(task='INT-12a F1+F2 — 탐색 파지→무게→털기 5회 (주도) · flow_node 에서 실행, use_mock=[f3]', slots=S('9/22 오후')),
 # --- 박진용
 'CELL-02a': dict(slots=S('9/19 오전')),
 'CELL-02': dict(owner='P(H)', note='재료 9/19 오전 도착 · 황인재가 커팅·고정을 돕는다 · 끝나면 티칭 2차(CELL-04b)', slots=S('9/19 오후')),
 'V-12': dict(slots=S('9/19 오후')),
 'V-03': dict(note='R · 닦기 설계를 결정 · 불가면 범위 방어', slots=S('9/19 저녁')),
 'V-18': dict(note='R · F3-02 의 첫 단계로', slots=S('9/20 오전')),
 'F3-02': dict(slots=S('9/20 오전', '9/20 오후', '9/20 저녁')),
 'F3-03': dict(slots=S('9/21 저녁')), 'V-10': dict(note='R · F3-03 의 첫 단계로', slots=S('9/21 저녁')),
 'UT-F3': dict(task='UT-F3 — TC-06·07 (rig_f3.py 로 내 함수만 단독 실행, 같은 함수 연속 3회 이상)', note='R · 함수별 TC 는 구현 직후 바로, 이 칸은 남은 TC·녹화 마무리', slots=S('9/22 오전')),
 'INT-13': dict(task='INT-13 F1+F3 — 안착 놓기→툴→세제→닦기→반납 5회 (주도) · flow_node 에서 실행, use_mock=[f2]', slots=S('9/22 저녁')),
 'SAFE-01': dict(task='안전 파라미터 표·위험요소/안전대책·예외/오류 리스트 — SDD §7·§8 에서 뽑아 노션 등록 (값 확인은 박진용)', owner='H(P)', note='노션 업로드 묶음(NOTE-01·02 와 같이)', slots=S('9/22 오전')),
 'V-24': dict(task='V-24 (선택) 동작 중 소프트 정지·타임아웃 — 비동기 이동(amovej/amovel) + check_motion 폴링, 메인 스레드에서만(Virtual)', owner='H(P)',
              note='선택 과제: 안 되면 정지는 기능 함수 사이로만(현재 기본)', slots=S('9/20 오후')),
 # --- 황인재
 'F4-00': dict(note='DSN-03(저녁) 안건이므로 오후까지', slots=S('9/19 오후')),
 'F4-01': dict(note='fake_state_pub 포함(INF-03 에서 옮김)', slots=S('9/19 저녁')),
 'F4-02': dict(slots=S('9/20 오전', '9/20 오후')),
 'F4-03': dict(slots=S('9/20 오후', '9/20 저녁')),
 'V-13': dict(note='INT-4 와 한 세션', slots=S('9/21 저녁')),
 'F4-04': dict(slots=S('9/22 오후')), 'UT-F4': dict(slots=S('9/22 오후')),
 'F4-05': dict(slots=S('9/22 저녁', '9/23 오전')),
 # --- 통합
 'INT-3a': dict(slots=S('9/22 저녁', '9/23 오전')), 'INT-3b': dict(slots=S('9/23 오전')), 'FIX-01': dict(slots=S('9/23 오전')),
 'INT-4a': dict(slots=S('9/23 오후')), 'INT-4b': dict(slots=S('9/23 오후', '9/23 저녁')), 'INT-4c': dict(slots=S('9/23 저녁')), 'INT-4d': dict(slots=S('9/23 저녁')),
}
# 새 행: id, 뒤에 붙일 행, 서식 복제 행, 구분, 작업, 담당, 상태, 칸, 산출물, 기준, 비고
NEW = [
 ('ENV-04', 'DSN-02b', 'ENV-03', '환경', '구조 변경 적용 — git pull → build·install·log 삭제 후 cbc → 작업 브랜치에 main 병합 → 에이전트에 AGENTS·IRD v3.0·SDD §3.2 재학습 · 프롬프트 파일 교체',
  '전원', '시작 전', S('9/19 오전'), '각자 PC', 'ros2 interface list 에 cobot_msgs 가 msg 2개만 · python3 -c "import cobot_api" 성공 · 프롬프트 교체 완료', '브리핑 직후 10분 · 옛 빌드가 남으면 삭제된 서비스 타입이 계속 보인다'),
 ('INF-02a', 'INF-02', 'INF-02', '계약', 'cobot_common bootstrap.py — init(name, robot)·io_node·cfg·shutdown + config.py 로더 (Virtual 에서 돌려 본 ts01_repro/virtual/s4_script.py 를 옮겨 적는다)',
  'H', '시작 전', S('9/19 오전'), 'src/cobot_common/cobot_common/bootstrap.py, config.py, package.xml·setup.py', 'Virtual 에서 rig 스크립트로 movej 연속 3회 + 통신 노드 타이머 2 Hz + Ctrl+C 뒤 재실행 정상',
  '🚨 9/19 오전 최우선 — V-20·FLOW-01·런치·모든 rig 스크립트가 기다린다 · 9/19 분담으로 박진용에게서 넘겨받음'),
 ('INF-02c', 'INF-02a', 'INF-02', '계약', 'cobot_common weigh(n, reset=False) — V-02 측정 도구에서 이식 (reset 은 선택 동작·응답 상한 3 s·실패 시 반복 금지, TS-03)',
  'M', '시작 전', S('9/19 오후'), 'src/cobot_common/cobot_common/robot.py weigh()', '100/200 g 추에서 V-02 와 같은 값 · 연속 3회', 'R · V-02 와 한 세션 · F2-01 weigh() 가 이걸 부른다'),
 ('PKG-01', 'INF-03', 'INF-03', '계약', '기능 패키지 골격 — 각자 패키지 생성 + cobot_api 서명 그대로의 빈 함수(F1 5개·F2 4개·F3 3개, 각 함수는 Result 만 반환) + rig_f*.py 뼈대',
  'S,M,P', '시작 전', S('9/19 오전'), 'handling.py · sense.py · wipe.py · test/rig_f*.py', 'cobot_api.check_api(모듈, F?Api) == [] · colcon build 성공', 'V-20 의 재료 · cobot_common 없이도 작성 가능 · 30분'),
 ('CELL-04b', 'CELL-04', 'CELL-04', '기구', '공통 좌표 티칭 2차 — 스펀지 홈(SPONGE_BED_B/C)·툴 홀더(TOOL_SPONGE/BRUSH) (기구 CELL-02 고정 뒤) + cell.yaml 반영',
  'S(P)', '시작 전', S('9/20 오전'), 'config/cell.yaml', '두 홈·두 홀더 좌표 기록, 저속 재현 ≤ 2 mm', 'R · 9/20 첫 순서 · V-04·V-15·F1-05·F1-03·F3-02 가 기다린다'),
]
PEOPLE = [('할일_한석형', 'S'), ('할일_민범진', 'M'), ('할일_박진용', 'P'), ('할일_황인재', 'H')]
EASY = {
 'INF-02': '공용 로봇 함수 중 기본 이동·그리퍼(move_to·move_rel·grip·grip_level·release)를 만든다. 내가 검증(V-01·V-22·V-23)하면서 쓰는 바로 그 동작이다. 다른 사람들이 이걸 가져다 쓴다',
 'INF-02a': '공용 로봇 함수의 시작·끝 부분(init·shutdown)과 설정 읽기를 만든다. 가상 로봇에서 돌려 본 시험 코드를 옮겨 적는다. 이게 있어야 모두가 자기 함수를 돌려 볼 수 있다',
 'INF-02b': '공용 로봇 함수 중 힘 관련(힘제어 켜기/끄기, 닿았는지 판정, 닿을 때까지 내려가기, 흔들며 찾기, 안전 후퇴)을 만들고, 네 사람이 나눠 쓴 함수들이 서로 맞는지 정리한다',
 'INF-02c': '공용 로봇 함수 중 무게 재기(weigh)를 만든다. V-02 에서 만든 측정 도구를 옮겨 적는다. 0점 재설정은 선택 동작으로',
 'ENV-04': '바뀐 구조를 내 PC에 적용한다: 저장소 받기, 옛 빌드 폴더 지우고 다시 빌드, 내 브랜치에 main 합치기, 에이전트에게 새 문서 다시 읽히기, 프롬프트 파일 새 것으로 바꾸기',
 'PKG-01': '내 패키지 뼈대를 만든다: 약속(cobot_api)에 적힌 이름·인자 그대로 빈 함수를 만들고(결과만 돌려줌), 내 함수만 불러 보는 시험 스크립트 rig 를 만든다',
 'CELL-04': '다 같이 로봇을 손으로 움직여 위치(홈·무게 재는 곳·잔반통·반납 구역·팔레트·수조·격리)의 좌표를 읽어 cell.yaml 에 적는다. 스펀지 홈과 툴 홀더는 기구를 고정한 뒤 2차에서',
 'CELL-04b': '기구(스펀지 고정틀·툴 홀더)를 작업대에 고정한 뒤, 스펀지 홈 2곳과 툴 홀더 2곳의 좌표를 읽어 cell.yaml 에 적는다',
 'V-05': '그리퍼 드라이버가 제대로 붙었는지 확인한다: 잡기/놓기 명령이 먹는지, 현재 벌어진 폭 값이 들어오는지',
 'V-20': '새 실행 구조가 팀 코드로도 도는지 가상 로봇에서 확인한다: flow_node가 세 사람의 빈 함수를 번갈아 부르고, 그동안 상태 발행(초당 2번)과 정지 버튼이 살아 있는지, Ctrl+C로 끈 뒤 다시 켜지는지',
 'V-24': '(선택) 로봇이 움직이는 도중에도 정지 버튼이 먹게 한다: 이동 명령을 보낸 뒤 짧게 반복 확인하면서 정지 깃발·시간 초과를 본다(가상 로봇). 안 되면 빼도 된다',
 'SAFE-01': '안전 값(속도·힘 상한·타임아웃) 표와 위험요소·대책, 오류 목록을 설계 문서에서 뽑아 노션에 올린다. 값이 맞는지는 박진용이 확인',
 'CELL-02': '스펀지에 그릇·컵 모양 홈을 파고, 툴 홀더 2개와 수세미 손잡이를 만들어 작업대에 고정한다(황인재가 돕는다)',
 'UT-FLOW': 'flow 단위 테스트(TC-10 실패 규칙, TC-12 기록)를 가짜 함수로 통과시킨다. 가짜 함수가 오류를 내도 프로그램이 죽지 않고 일시정지로 가는지, Ctrl+C로 끈 뒤 다시 켜지는지도 본다',
 'INF-03': '로봇 없이 flow를 개발하려고 F1·F3와 같은 이름의 가짜 함수 모듈을 만든다(실패도 흉내 낼 수 있게)',
 'F4-01': '가짜 상태 발행기(fake_state_pub)와 FastAPI 첫 페이지를 만든다',
 'INT-12a': 'F1+F2 통합: flow_node에서 F3만 가짜로 두고, 찾아서 집기→무게→털기를 5번 연속',
 'INT-12b': 'F1+F2 통합: flow_node에서 F3만 가짜로 두고, 다시 집기→헹굼→물 털기→팔레트 적재를 5번 연속',
 'INT-13': 'F1+F3 통합: flow_node에서 F2만 가짜로 두고, 안착 놓기→툴 집기→세제→닦기→툴 반납을 5번 연속',
 'ARCH-01': '새 구조로 다시 그린 아키텍처 그림을 draw.io에서 다듬고 HMI 쪽 빈칸을 채운다. 강사가 요구한 산출물 10종을 노션에 올린다',
 'DSN-03': '2차 회의: 반납 구역 방식, HMI 설계, 실패했을 때 처리 규칙, 설정 키 이름 규칙 + 구조 변경 뒤 남은 것(모니터·기록 노드를 추가할지, 힘·그리퍼 폭 토픽, 공용 함수 분담 확인)',
}
MILESTONE = {   # A 열 글자 → {열: 새 글}
 '9/19 토 · 9/20 일': {'C': '9/19 구조 변경 적용 → 티칭 1차 + 공용 함수 분담 작성(H·S·M·P) → 사전 검증(V) → 저녁 DSN-03 2차 회의 / 9/20 티칭 2차(기구 고정 뒤) → 구현 + 함수별 TC 바로 수행'},
 '9/21 월': {'C': '중간점검 발표. 로봇·개발은 저녁만(F1-04·F3-03·UT-F2·INT-4)'},
 '9/22 화': {'C': '오전 L1 마무리(UT-F1·UT-F3) + 노션 업로드(노드 구조·HMI gif·안전·GitHub 최신), 오후 L2(INT-12a·12b), 저녁 L2(INT-13) → L3 착수'},
 '9/23 수': {'C': '오전 L3(그릇·컵) + 결함 수정 → 오후~저녁 L4 전체 통합 → 영상 → 기능 동결 v1.0-demo'},
 'G1 리그·검증': {'B': '9/20 오전', 'C': '티칭 1·2차 완료, 기구 완성, 공용 함수(cobot_common) v0, 실행 뼈대 확인(V-20), 설계를 정하는 검증(V-01·02·03·23) 결과 확보'},
 'G2 L1': {'B': '9/22 오전', 'C': 'UT-F1·F2·F3·F4·FLOW 통과 + 녹화 (함수별 TC 는 구현 직후 바로 수행)'},
 'G3 L2': {'B': '9/22 저녁', 'C': 'INT-12a·12b·13·4 통과 (flow_node + use_mock). 노션 업로드는 9/22 오전'},
 'G4 L3': {'B': '9/23 오전', 'C': '그릇 1·컵 1 end-to-end + HMI 3회 연속'},
 '9/19 토': {'B': 'CELL-04 티칭 1차(S 주도, M·P) + V-19·V-22(S) · 로봇 불필요: INF-02a bootstrap(H)·FLOW-01 뼈대·mock(M)·힘 함수·치수 도면(P)·PKG-01(S·M·P)',
             'C': 'V-02 + weigh 이식(M) → V-01·V-05·V-23 + 기본 함수(S) · 로봇 불필요: V-20 Virtual(M·H)·CELL-02 기구 제작·V-12(P·H)·F4-00(H)',
             'D': 'DSN-03 2차 회의(전원, 로봇 불필요) → V-03(P) → V-16(S·M) → F1-01(S)'},
 '9/20 일': {'B': 'CELL-04b 티칭 2차(S·P) → F1-02·V-14(S) / V-18·F3-02(P) / V-07·F2-01(M) — 1시간씩 교대', 'C': 'V-04·V-15(P·S) → F1-05(S) / F3-02(P) / F2-01(M)', 'D': 'F1-03·V-08(S) / F3-02(P) / F2-02(M) · 로봇 불필요: F4-03(H)·MID-01'},
 '9/21 월': {'D': 'F1-04·V-06 → UT-F1 착수(S) / F3-03·V-10(P) / UT-F2(M) · 로봇 불필요: UT-FLOW(M)·INT-4·V-13(H·M)·CR-01'},
 '9/22 화': {'B': 'UT-F1 마무리(S) / UT-F3(P) · 노션 업로드(H)', 'C': 'INT-12a(M·S) → INT-12b(S·M)', 'D': 'INT-13(P·S) → INT-3a 그릇 L3 착수(M 실행, 전원)'},
 '9/23 수': {'B': 'INT-3a·INT-3b L3 + FIX-01', 'C': 'INT-4a 4개 연속 → INT-4b 실패 주입', 'D': 'INT-4b 잔여 · INT-4c 측정 → INT-4d 영상·동결'},
}
RULES = {       # B 열 글자 → {열: 새 글}
 '9/20(일) 저녁': {'B': '9/22(화) 오전', 'C': 'L1 단위기능 테스트(UT-*) 전부 통과 — 함수별 TC 는 구현 직후 바로 수행. 미통과 기능은 범위 방어표대로 축소 · 노션에 노드 구조·HMI 화면·안전 자료 업로드 · GitHub 최신'},
 '9/22(화) 오전': {'B': '9/22(화) 저녁', 'C': 'L2 단위기능 통합 완료 (flow_node 에서 실행, 나머지 기능은 use_mock)'},
 'docs/01~03 v2': {'B': 'docs/01~03 v3', 'C': '요구사항(BR·SR) / 인터페이스(IRD v3.0 — 기능 함수 약속 + ROS 인터페이스) / 설계(SDD v3.0 §3.2 실행 뼈대, §9 테스트 계획, §13 일정표). 용기 그릇 2·컵 2, 팔레트 그릇 2칸·컵 4칸'},
}
NEW_RULE = ('부하', '한 사람 한 칸', '큰 작업(구현) 1개 + 작은 작업(검증·문서) 2개 이내. 구현에 딸린 사전 검증(V)은 그 구현 칸의 첫 단계로 한다. 몰리면 브리핑에서 말하고 PM 이 옮기거나 나눈다. 공용 함수(cobot_common)는 H·S·M·P 가 나눠 쓴다')


def main(out):
    gen_todo.EASY.update(EASY)
    b = Book.from_live(SID)
    tl = b.sheet('Time Line'); d = b.sheet('상세(산출물·완료기준)')

    def has(sheet, col, v):
        try: sheet.find(col, v); return True
        except KeyError: return False

    for tid, e in EDIT.items():
        r = tl.rows[tl.find(ID, tid)]
        if 'task' in e: r.set('C', e['task'])
        if 'owner' in e: r.set('D', e['owner'])
        if 'status' in e: r.set('F', e['status'])
        if 'slots' in e: set_slots(r, e['slots'])
        if has(d, 'A', tid):
            q = d.rows[d.find('A', tid)]
            for c, k in (('C', 'task'), ('D', 'owner'), ('E', 'deliv'), ('F', 'crit'), ('G', 'note')):
                if k in e: q.set(c, e[k])
    for tid, after, like, cat, task, owner, status, slots, deliv, crit, note in NEW:
        if has(tl, ID, tid):
            continue
        n = new_timeline_row(tl, tl.rows[tl.find(ID, like)], slots, A=None, B=cat, C=task, D=owner, F=status, **{ID: tid})
        tl.insert(tl.find(ID, after) + 1, n)
        q = d.rows[d.find('A', like)].clone()
        for c, v in zip('ACDEFG', [tid, task, owner, deliv, crit, note]): q.set(c, v)
        d.insert(d.find('A', after) + 1, q)
    # 마일스톤·로봇 슬롯
    m = b.sheet('마일스톤·로봇 슬롯')
    for r, key in [(r, m.text(r, 'A').strip()) for r in m.rows]:
        if key in MILESTONE:
            for c, v in MILESTONE[key].items(): r.set(c, v)
    # 규칙
    ru = b.sheet('규칙')
    orig = [(r, ru.text(r, 'B').strip()) for r in ru.rows]          # 고치기 전 글자로 한 번씩만 맞춘다
    for r, key in orig:
        if key in RULES:
            for c, v in RULES[key].items(): r.set(c, v)
    ru.rows[0].set('A', '운영 규칙 (PreWash-Cell 일정표 v4.2)')
    if not has(ru, 'A', NEW_RULE[0]):
        k = ru.first_empty(); n = ru.rows[k - 1].clone()
        for c, v in zip('ABC', NEW_RULE): n.set(c, v)
        ru.rows[k] = n
    # 변경이력
    h = b.sheet('변경이력')
    if not has(h, 'A', '4.2'):
        k = h.first_empty(); n = h.rows[k - 1].clone()
        for c, v in zip('ABCDEF', ['4.2', '재배치', 'ENV-04·PKG-01·INF-02a·INF-02c·CELL-04b(신규), INF-02·02b·03·04, V-01~24 다수, F1~F4·FLOW·UT·INT 칸, SAFE-01, CELL-02, ARCH-01, 마일스톤·로봇 슬롯·규칙',
                                   '공용 함수 분담(bootstrap=H, 기본 이동·그리퍼=S, weigh=M, 힘 함수·정리=P). 티칭을 1·2차로 분리. 구현에 딸린 V 는 그 구현 칸으로. 한 사람 한 칸 = 큰 작업 1 + 작은 작업 2 이내. SAFE-01·V-24 → H, CELL-02 에 H 보조. '
                                   '게이트: L1 9/20 저녁→9/22 오전, L2→9/22 저녁, L3→9/23 오전, 동결 9/23 저녁 그대로. 단위 시험은 rig 스크립트, L2 는 flow_node + use_mock',
                                   '구조 변경으로 작업이 늘었고 9/19 에 네 사람 모두 과부하(박진용 오전 9건). 로봇 1대 슬롯도 초과', 'S,M,P,H']): n.set(c, v)
        h.rows[k] = n
    # 고친 Time Line 을 다시 읽어 완료 목록·할일 시트를 채운다
    tmp = os.path.join(tempfile.mkdtemp(), 'stage.xlsx'); b.save(tmp)
    rows, det = timeline(load(tmp))
    done = b.sheet('완료 목록'); txt, ctr = d.rows[1].style('C'), d.rows[1].style('A')
    done.rows = done.rows[:1]
    for r in rows:
        if r['status'] != '완료' or not r['slots']: continue
        n = Row('', {})
        vals = [r['id'] or '—', r['task'], r['owner'], det.get(r['id'], {}).get('deliv', ''), ' '.join(r['slots'][0]), ' '.join(r['slots'][-1])]
        for c, v, st in zip('ABCDEF', vals, [ctr, txt, ctr, txt, ctr, ctr]): n.set(c, v, style=st)
        done.rows.append(n)
    rebuild_todo(b, lambda L: gen_todo.person_entries(rows, det, L), PEOPLE)
    b.save(out); print('->', out)
    return rows


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'prewash_일정표_0919.xlsx')
