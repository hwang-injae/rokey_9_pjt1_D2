# -*- coding: utf-8 -*-
"""9/19 오후 — 재계획: ① 주말(9/19·9/20)은 교육장이 18시에 닫는다 → **주말 저녁 칸을 전부 비운다** ② 한석형은 9/19 에 티칭까지만
③ 분담 변경(PM 결정, DSN-03 에서 확인): 그리퍼 검증 V-01·V-05·V-23 + gripper.py = 민범진 · 이동 함수 motion.py(move_to·move_rel·관절 상대 이동)·
   cell.force 키 골격·F1 패키지 골격 = 황인재(F4 세션) · 한석형 = 티칭·cell.yaml 값·실기 검증·F1 기능 함수
④ 게이트: G1 9/20 오후 · L1 9/22 오후 · L2 9/23 오전 · L3 9/23 오후 · 동결 9/23 저녁(그대로)
구글 시트의 '현재' 내용에 변경만 얹는다(PM 이 시트에서 고친 상태·행 순서는 그대로). 다시 실행해도 같은 결과가 나온다.
실행: python3 tools/gen/patch_20260919_weekend.py ../_upload/출력.xlsx → tools/gen/sheet_push.sh ../_upload/출력.xlsx
이 파일이 9/19 오후 이후의 최신 패치다. patch_20260919_audit.py·rebalance.py 는 다시 실행하지 않는다(여기서 옮긴 칸이 되돌아간다)."""
import sys, os, re, tempfile, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from xlsx_patch import Book, Row, new_timeline_row, rebuild_todo, set_slots
from livesheet import SID, load, timeline
import gen_todo

ID = 'AH'
VERSION = 'v5.9'
OUT = 'prewash_일정표_0919s.xlsx'
def S(*xs): return [tuple(x.split()) for x in xs]          # S('9/20 오전','9/20 오후')

# id: dict(task, owner, status, deliv, crit, note, slots) — 없는 키는 그대로 둔다
EDIT = {
 # --- 전원 구역
 'PM-01': dict(slots=S('9/18 저녁', '9/19 오후', '9/20 오후', '9/21 저녁', '9/22 저녁', '9/23 저녁'), note='주말은 교육장 마감(18시) 전에'),
 'PKG-01': dict(owner='H,M,P', note='V-20 의 재료 · ✅ F3(박진용) PR #4 · ✅ F2(민범진) PR #8 · F1 골격은 황인재 F4 세션이 대신 작성(패키지 주인은 한석형 그대로 — 9/19 PM 결정, 한석형은 티칭에 집중) · pytest 파일 이름은 test_f1_api.py'),
 'INF-02': dict(status='완료', task='cobot_common 2/4 · motion.py — 이동 함수(저수준) move_to · move_rel(dx,dy,dz,frame,*,vel_mm_s,acc_mm_s2) · move_joint_rel(관절 상대 이동, 털기용) · 속도 = cell.limits × run.vel_scale',
                owner='H', deliv='src/cobot_common/cobot_common/motion.py + cell.yaml 의 cell.force 키 골격(값 없음)·test_config 수정',
                crit='Virtual(격리)에서 move_to·move_rel·move_joint_rel 연속 3회 · 시험용 설정으로 pytest',
                note='✅ 9/19 PR #15 merge(예정보다 반나절 빠름) — Virtual rig 3바퀴 30건·pytest 23건 · 🚨 move_to 는 안전 높이 아래로 내려가지 않고 "남은 높이"를 돌려준다(하강은 부르는 쪽이 move_rel/contact_down) · 새 키 cell.motion 4개(100 % 기준 속도) — 값은 한석형, 비어 있으면 이동 함수가 KeyError · ✅ move_joint_rel 시간 지정 경로의 속도 상한 추가(PR #16) · 남은 것(안건): 사용자 좌표계·RACK_*·회전 포함 상대 이동 · 9/19 분담 변경: 한석형 → 황인재(F4 세션) · Virtual 만으로 완성(로봇 불필요) · 이슈 #7 ② move_rel 속도 선택 인자 · DSN-03 B11 관절 이동 함수 · 박진용 force.py 의 임시 stub _move_rel 을 대체 · 좌표는 cell.yaml(한석형)에서 읽기만',
                slots=S('9/19 오후')),
 'INF-02d': dict(status='진행 중', slots=S('9/19 오후', '9/20 오후'), note='R · ✅ 코드 merge(PR #17, 9/19 — 예정보다 하루 빠름, pytest 22건): 드라이버 소스 기준 구현(힘은 2.5 N 계단·처음에 0 N 으로 기준 맞춤, 폭은 관절각 → 환산, 완료는 effort 로) · 남은 것: ① 9/20 오전 V-05·V-23 실기 확인 ② setup_io 의 onrobot_rg_msgs import 가드(ws_dsr 없이 cc.init 이 죽는다) ③ 힘 기준 맞추기를 쥐지 않은 때(release)로 · 9/19 분담 변경: 한석형 → 민범진 · 박진용 제안서 참고'),
 'INF-02b': dict(slots=S('9/19 오후', '9/20 오전'), note='force.py 구현·시험은 브랜치에 있음 — V-03(9/20 오전) 전이라도 PR 을 올린다(값은 후속 PR) · F1-02(9/20 오후)가 contact_down 을 기다린다 · 이슈 #7: cell.force 키 골격은 황인재(INF-02), 값은 박진용이 그 절만 PR · move_rel 이 들어오면 임시 stub 삭제'),
 'INF-02c': dict(status='진행 중', slots=S('9/20 오전'), note='R · ✅ 코드 merge(PR #13, 9/19 — 중앙값·음수 실패값 거르기·reset 선택 동작, pytest 10건) → 남은 것은 9/20 오전 실기 확인(V-02 와 한 세션)과 빈 용기 기준값 측정(rig_f2.py empty) · f2.weigh(F2-01)가 이걸 불러 판정한다'),
 'DSN-03': dict(task='2차 회의 안건 — **회의 없이 PM 이 결정**(9/19): 반납 구역 = 고정 슬롯 · 그릇 = 옆면(벽) 세로 파지 · 그리퍼 폭 경로 · 이슈 #7 수락 · 9/19 선결정 확정. 나머지는 보류', status='진행 중', slots=S('9/19 오후'),
               crit='급한 안건 결정 + 팀 공지', note='시간 부족으로 회의를 열지 못함 → PM 결정 후 공지, 이의는 9/20 브리핑 · 결정 표 docs/meetings/20260919_결정기록_DSN-03.md · 확인 중: 실패 정책 마무리 순서(B7)·move_joint_rel(B11)·mock_f2(B12) · 보류: YAML 키·/cell 토픽·HMI 설계·정지 방식·rig 속도·C1~C5'),
 'DSN-04': dict(slots=S('9/20 오전')),
 'ARCH-01': dict(slots=S('9/20 오후')),
 'MID-01': dict(slots=S('9/20 오후', '9/21 오전'), note='구조 변경 근거 1장 포함(TS-01: 발견→재현→구조 5종 비교→결정) · 각자 자기 기능 1장을 9/20 오후까지 · 주말 저녁 없음'),
 'V-20': dict(note='재료: cobot_common(main) + flow_node(PR #8·#9) + f3_wipe(PR #4) + F1 골격(황인재 세션 대신 작성) · 격리 상태 Virtual · 안 되면 구조 ③(결정 기록 표)'),
 'INT-12a': dict(slots=S('9/22 저녁'), note='R · 9/22 저녁 첫 순서'),
 'INT-12b': dict(slots=S('9/22 저녁'), note='R · INT-12a 다음'),
 'INT-13': dict(slots=S('9/22 저녁', '9/23 오전'), note='R · INT-12b 다음 — 9/23 오전 첫 순서까지'),
 'INT-3a': dict(slots=S('9/23 오전'), note='R · L2(G3, 9/23 오전) 통과 뒤 바로'),
 'INT-3b': dict(slots=S('9/23 오전', '9/23 오후')),
 'FIX-01': dict(slots=S('9/23 오후')),
 'INT-4a': dict(slots=S('9/23 오후'), note='R · 🛡 범위 방어(SDD §9.9): L3 가 9/23 오후 첫 1시간 안에 안 끝나면 4개 연속 → 2개(그릇 1·컵 1)'),
 'INT-4b': dict(slots=S('9/23 저녁'), note='R · 🛡 범위 방어: 실패 주입 4종 → 2종(빈 구역·정지/재개)'),
 # --- F1 (한석형: 티칭·실기·기능 함수)
 'CELL-04': dict(prog='0.5', slots=S('9/19 오전', '9/19 오후', '9/20 오전'), note='R · 🚨 9/19 는 **그릇 쪽 좌표까지**, **컵 쪽 좌표는 9/20 오전**(황인재 확인 9/19 17:50 — 좌표 작업이 예상보다 오래 걸림) · V-19 를 이 세션 안에서 · 티칭 자세 = 그 기능의 시작 자세(WASTE·수조는 위에서, WEIGH 는 안전 높이 이상 권장 — SDD §5.3) · cell.motion 4개·limits 값도 같이 · 18시 교육장 마감'),
 'V-19': dict(slots=S('9/19 오후', '9/20 오전'), note='R · 티칭과 함께 — 9/19 그릇 쪽, 9/20 오전 컵 쪽(CELL-04 와 같이 나뉨)'),
 'V-01': dict(owner='M', slots=S('9/20 오전'), crit='상태마다 10회 — 세 범위가 겹치지 않고, 그릇(≈ 2 mm) ↔ 빈손 간격이 흔들림(최대 − 최소)의 2배 이상', note='R · V-05·V-23 과 한 그리퍼 세션(9/20 오전 첫 순서) · 9/19 분담 변경: 한석형 → 민범진 · 🚨 9/19 PM 결정: **그릇은 옆면(벽)을 세로로 파지**(외경 114 mm > RG2 최대 폭 110 mm) — ✅ 9/19 검증: 파지 폭 ≈ 2 mm 이고 빈손과 구분된다(황인재) → **그릇도 폭으로 가른다(무게로 가르지 않음)** · 남은 것: 컵·빈손 포함 10회 기록, 허용 오차를 cell.yaml 에, 드라이버 경로(V-05)에서도 같은 값이 읽히는지 · 그릇 전용 허용 오차를 정하고, grip 의 닫는 목표 폭은 기대 폭보다 작게(같으면 빈손도 성공으로 읽힌다) · 미달이면 핑거 패드를 두껍게 · 결과가 gripper.py grip 과 F1-02 폭 판정값이 된다'),
 'V-05': dict(owner='M', slots=S('9/20 오전'), note='R · 절차는 박진용 제안서 docs/ref/20260919_제안_RG2_폭_힘_경로.md §5(30분): A 드라이버(관절각→폭 환산, 힘 2.5 N 계단) 먼저 → 안 되면 B Compute Box XML-RPC 를 읽기부터 · 9/19 분담 변경: 한석형 → 민범진'),
 'V-23': dict(owner='M', slots=S('9/20 오전'), note='R · V-05 와 한 세션 · grip_level 구현 방법을 정한다(gripper.py) · 9/19 분담 변경: 한석형 → 민범진'),
 'F1-01': dict(slots=S('9/20 오전', '9/20 오후'), note='R · 🚨 9/20 오전에 컵 쪽 티칭(CELL-04)이 더해져 오후로 넘어갈 수 있다 — 그릇 좌표만으로 먼저 짠다 · ✅ motion.py 는 9/19 에 main 에 들어왔다(#15) → 바로 착수 가능 · 먼저 cell.yaml 의 cell.motion 4개·limits 값을 채워야 cc.move_to 가 움직인다 · cc.move_to 는 상공까지만 가고 남은 높이를 돌려준다 · 티칭 2차 세션 뒤에'),
 'F1-02': dict(task='pick 고정 슬롯 파지 — 구역의 지정 슬롯을 순서대로: 슬롯 상공 → 힘 상한 감시 하강 → 파지 → 폭 판정 · 빈 슬롯이면 다음 슬롯 · 다 비면 EMPTY_ZONE (그릇은 옆면(벽) 세로 파지)', slots=S('9/20 오후'),
               crit='고정 슬롯(그릇 2·컵 2)에서 10회 ≥9 · 빈 슬롯은 다음 슬롯으로', note='R · 9/19 PM 결정: 구역 + 탐색 파지 → **고정 슬롯**(겹친·어긋난 용기 대응 제외) · pick 서명·EMPTY_ZONE·YAML 키는 그대로(offsets_mm = 슬롯 위치) · contact_down(박진용)을 부른다'),
 'V-14': dict(task='V-14 고정 슬롯 파지 성공률 — 그릇 슬롯 2·컵 슬롯 2, 빈 슬롯 포함 (이전: 겹친 용기 탐색 파지)', slots=S('9/20 오후'), crit='≥9/10, 낙하 0, 빈 슬롯은 다음 슬롯으로', note='R · F1-02 의 TC 로 한 흐름'),
 'V-15': dict(slots=S('9/21 저녁')), 'V-04': dict(slots=S('9/21 저녁')), 'F1-05': dict(slots=S('9/21 저녁')),
 'F1-03': dict(slots=S('9/22 오전')), 'V-08': dict(slots=S('9/22 오전')),
 'F1-04': dict(slots=S('9/22 오후')), 'V-06': dict(slots=S('9/22 오후')),
 'UT-F1': dict(slots=S('9/22 오후'), note='R · 함수별 TC 는 구현 직후 바로 수행, 이 칸은 남은 TC·녹화 마무리 · 🛡 F1 은 시연 필수 경로 — 밀리면 DSN-03 C5(F1 함수 초안을 다른 세션이 Virtual 에서 작성, 한석형은 실기 튜닝)'),
 'V-16': dict(slots=S('9/20 오후'), note='R · F2-01 shake 의 첫 단계로(V-07 과 한 세션) · gripper.py grip_level 이 있어야 한다 · 찾은 HOLD 값은 한석형이 cell.yaml 프리셋에 반영'),
 # --- F2·flow (민범진)
 'V-02': dict(slots=S('9/20 오전'), note='R · INF-02c weigh 이식과 한 세션 · 9/19 오후는 티칭이 로봇을 쓴다'),
 'FLOW-01': dict(slots=S('9/19 오전', '9/19 오후', '9/20 오전'), note='✅ PR #8·#9 merge: 메인 뼈대·상태 머신·실패 정책·예외 보호 · 🔧 남은 것: 격리 마무리 동작(툴 반납 → ISOLATE 에 놓기 → HOME) — 순서는 DSN-03 B7, 로봇 교대 대기 시간에'),
 'V-07': dict(slots=S('9/20 오후')),
 'F2-01': dict(slots=S('9/20 오후', '9/21 저녁')),
 'F2-02': dict(slots=S('9/21 저녁')),
 'FLOW-02': dict(slots=S('9/22 오전')),
 'UT-F2': dict(slots=S('9/22 오전')),
 # --- F3 (박진용)
 'V-03': dict(slots=S('9/19 오후', '9/20 오전'), note='R · 닦기 설계를 결정 · 불가면 범위 방어 · 9/19 오후 착수(PM 시트 기준 진행 중) → 주말 저녁이 없어 남은 것은 9/20 오전 로봇 교대의 박진용 첫 순서'),
 'V-10': dict(slots=S('9/21 저녁')),
 'F3-03': dict(slots=S('9/21 저녁', '9/22 오전'), note='R · 시연 필수 경로 — 함수가 둘이라 2칸(9/21 저녁 V-10·뼈대, 9/22 오전 실기 마무리) · 🛡 밀리면 컵 닦기는 도전 과제, 그릇만 MVP(SDD §9.9)'),
 'UT-F3': dict(slots=S('9/22 오후')),
 # --- F4 (황인재)
 'F4-00': dict(slots=S('9/20 오전'), note='9/19 오후는 F1 골격·motion.py 가 먼저 · DSN-03 B5 는 9/20 브리핑에서 확인'),
 'F4-01': dict(slots=S('9/20 오후')),
 'F4-02': dict(slots=S('9/20 오후', '9/21 저녁')),
 'F4-03': dict(slots=S('9/22 오전', '9/22 오후'), note='DSN-03 결과 반영 · 이동 함수(INF-02)를 맡으면서 한 칸씩 뒤로'),
 'NOTE-02': dict(slots=S('9/22 오후'), note='F4-03 화면이 나온 뒤 gif — 강사 요구일(9/22) 안에'),
 'UT-F4': dict(slots=S('9/22 저녁')),
 'V-24': dict(status='보류', note='선택 과제 — 9/19 재계획에서 뺌(황인재가 motion.py 를 맡음). Virtual 에서는 모션 중 Ctrl+C 정지 확인됨(PR #3). 시간이 남으면 9/22 이후', slots=[]),
}
# 새 행: id, 뒤에 붙일 행, 서식 복제 행, 구분, 작업, 담당, 상태, 칸, 산출물, 기준, 비고
NEW = [
 ('INF-02d', 'INF-02', 'INF-02', '계약', 'cobot_common · gripper.py — 그리퍼 함수(저수준) grip · grip_level(NORMAL/HOLD) · release · grip_width(현재 폭 mm)',
  'M', '시작 전', S('9/20 오후'), 'src/cobot_common/cobot_common/gripper.py', '실기에서 명령 → 동작 → 폭(mm) 읽힘 · NORMAL↔HOLD 전환 · Virtual 에서는 가짜 그리퍼 노드로 호출 순서',
  'R · 9/19 분담 변경: 한석형(motion.py 안) → 민범진(새 파일) · V-05·V-23·V-01 결과가 곧 구현 · 박진용 제안서 참고, 박진용이 PR 리뷰 · F3 요청 grip_width() 포함 · 구독은 setup_io(node)'),
]
# 9/19 저녁 진척 취합(PM-01) — 근거: main 에 merge 된 PR #3~#18, 팀원 브랜치의 커밋 기록, 황인재 확인
PROGRESS = {
 'PKG-01': dict(status='완료', note_add='✅ 9/19 완료 — F1 골격 PR #12 · F2 PR #8 · F3 PR #4 전부 main'),
 'INF-02a': dict(note_add='후속 수정 merge: #10(콜백 예외로 통신 스레드가 끝나던 문제) · #18(robot=False 면 setup_io 훅 실패를 건너뛴다 — ws_dsr 없이도 init)'),
 'INF-02c': dict(prog='0.7'),
 'INF-02d': dict(prog='0.6'),
 'INF-02b': dict(prog='0.8', note_add='✅ 9/19 17:40 PR #20 merge — force.py(순응·힘제어·접촉 하강·탐색·안전 후퇴·read_force·예외 2종) + pytest 23건 + Virtual rig · 남은 것: cell.force 값 PR(V-03 뒤)·force_off 끝까지 시도·force_on limit 감시 도우미·periodic_search 힘 감시(V-04 전) · (이전 메모) 9/19 17:16 기준(커밋 기록): 브랜치 jinyong/20260919-INF-02b-force-funcs 에 force.py·test_force.py·rig_force (15커밋), PR 은 아직 · motion.move_rel 이 main 에 들어왔으니(#15) 임시 stub 을 지우고 PR'),
 'V-03': dict(prog='0.6', note_add='9/19 오후 실기 4회차까지(커밋 기록 16:04~17:16): 힘제어 중 X·Y 이동 확인, 문지르기 방식 = 손목을 비틀며 나선으로 넓혀 벽을 찾고 벽 따라 2바퀴(8자 삭제) · 남은 것: 결과 문서(docs/test_logs)와 cell.force 값 PR'),
 'V-01': dict(prog='0.7', note_add='✅ 9/19 황인재 확인: 그릇(옆면 세로 파지 ≈ 2 mm)은 빈손과 폭으로 구분된다 · 컵은 벽이 아니라 **몸통을 통째로 파지**(폭 ≈ 컵 지름)라 빈손·그릇과 간격이 충분하다 → 3상태 구분은 사실상 확인됨 · 남은 것: 드라이버 경로(V-05)로 10회씩 기록 + 그릇 전용 허용 오차 값을 cell.yaml 에'),
 'V-05': dict(status='진행 중', prog='0.3', note_add='9/19: 드라이버 소스 분석으로 폭 읽는 경로를 구현(#17 — 관절각 → 폭 환산, 장치가 읽은 0.1 mm 폭과 같다) → 9/20 오전에 실기로 확인(닫힌 쪽 0~5 mm 반복 흔들림 포함), 확정은 그 뒤'),
 'V-20': dict(status='진행 중', prog='0.3', slots=S('9/19 오후', '9/20 오전'), note_add='9/19: cobot_common 실행 뼈대는 Virtual rig_motion 3바퀴·검사 30건으로 확인(#15) → 남은 것: flow_node + 세 모듈을 Virtual 에서 한 번에(로봇 불필요 — 로봇 교대 대기 시간에)'),
 'DSN-03': dict(prog='0.7'),
 'DSN-04': dict(status='진행 중', prog='0.7', slots=S('9/19 오후', '9/20 오전'), note_add='9/19 PM 결정분(고정 슬롯·그릇 옆면 파지·폭 판정·이슈 #7·motion/gripper 구현 방식)은 BR-SR·IRD·SDD·AGENTS·프롬프트·일정표에 반영 완료 · 남은 것: contracts.py pick docstring(황인재)·cell.yaml zones/presets 주석(한석형)·확인 대기 3건(B7 격리 마무리 순서·B11·B12)'),
}
for _tid, _e in PROGRESS.items():
    EDIT.setdefault(_tid, {}).update(_e)

# 팀(구역) 이동: id → (새 팀, 이 ID 행 바로 뒤에 둔다) — 이미 그 구역에 있으면 PM 이 정한 행 순서를 건드리지 않는다
MOVE = {'V-01': ('F2·flow', 'V-02'), 'V-05': ('F2·flow', 'V-01'), 'V-23': ('F2·flow', 'V-05')}
EASY = {
 'INF-02': '공용 로봇 함수 중 이동(지정 위치로 이동 move_to, 상대 이동 move_rel, 관절 상대 이동)을 motion.py 에 만든다. 가상 로봇만으로 완성한다. 접촉 하강이 쓰도록 속도 선택 인자를 넣고, cell.yaml 에 힘 관련 키 골격도 추가한다',
 'INF-02d': '공용 로봇 함수 중 그리퍼(잡기 grip, 힘 2단계 grip_level, 놓기 release, 현재 폭 읽기 grip_width)를 새 파일 gripper.py 에 만든다. 그리퍼 검증(V-05·V-23·V-01)에서 확인한 방법 그대로',
 'V-01': '그리퍼로 그릇·컵을 잡았을 때와 빈손일 때의 "벌어진 폭" 값이 확실히 다른지 10번씩 잰다. 그릇은 옆면(벽)을 세로로 잡아 폭이 약 2 mm 로 나온다 → 빈손(완전히 닫힘)과 겹치지 않는지가 핵심',
 'V-05': '그리퍼 드라이버가 제대로 붙었는지, 현재 폭을 어디서 읽을지 정한다(박진용 제안서의 30분 절차): 드라이버의 관절각을 폭으로 바꿔 자로 잰 값과 비교 → 안 맞으면 Compute Box 를 읽기부터',
 'PKG-01': '내 패키지 뼈대를 만든다: 약속(cobot_api)에 적힌 이름·인자 그대로 빈 함수를 만들고, 내 함수만 불러 보는 시험 스크립트 rig 를 만든다. F1 골격은 황인재 세션이 대신 만들어 준다(주인은 한석형)',
 'DSN-03': '2차 회의 안건을 회의 없이 PM 이 결정했다(시간 부족): 반납 구역은 고정 슬롯, 그릇은 옆면을 세로로 잡기, 그리퍼 폭은 드라이버 방식 먼저, 박진용의 힘 함수 요청 수락. 이의는 9/20 아침 브리핑에서',
 'F1-02': '"슬롯에서 집기"(pick)를 만든다: 반납 구역의 정해진 자리(슬롯)를 순서대로 가서, 닿을 때까지 내려가 잡고, 폭으로 성공을 판정한다. 빈 자리면 다음 자리로, 다 비었으면 "구역 비었음". 그릇은 옆면(벽)을 세로로 잡는다',
 'V-14': '정해진 자리(슬롯)에 놓인 그릇 2개·컵 2개를 10번 집어 9번 이상 성공하는지 본다. 빈 자리가 있으면 다음 자리로 넘어가는지도',
 'V-24': '(보류) 로봇이 움직이는 도중에도 정지 버튼이 먹게 하는 선택 과제 — 이번 재계획에서 뺐다',
}
TITLES = {'할일_한석형': '한석형 — 팀장 · F1 파지·이송·적재 + 좌표 계산·티칭(cell.yaml 값) + 실기 검증',
          '할일_민범진': '민범진 — F2 무게·털기·헹굼 + flow_node + mock · 통합 실행 리더 + cobot_common weigh.py · gripper.py + 그리퍼 검증',
          '할일_박진용': '박진용 — F3 접촉 닦기 + cobot_common 힘 함수(force.py)·패키지 정리·리뷰 + 안전 파라미터',
          '할일_황인재': '황인재 — PM · F4 웹 HMI + cobot_api·cobot_msgs·cobot_common bootstrap·config·motion.py·런치·일정표·제출'}
LECTURE = {'9/19 토 · 9/20 일': ('휴일(로봇 사용 가능 — 🚨 교육장 18시 마감, **저녁 칸 없음**)',
                                 '9/19 구조 변경 적용 → 티칭 1차(한석형) + 공용 함수·기능 골격 → 17:15 DSN-03 2차 회의 / 9/20 오전 그리퍼·무게·힘 검증 + 티칭 2차 → 오후 구현 + 함수별 TC · 발표 자료')}
GATE = {
 'G1 리그·검증': {'B': '9/20 오후', 'C': '티칭 1·2차 완료, 기구 완성(✅ 9/19), 공용 함수(cobot_common: motion·gripper·force·weigh) v0, 실행 뼈대 확인(V-20), 설계를 정하는 검증(V-01·02·03·05·23) 결과 확보'},
 'G2 L1': {'B': '9/22 오후', 'C': 'UT-F1·F2·F3·FLOW 통과 + 녹화 (함수별 TC 는 구현 직후 바로 수행) + 코드리뷰 CR-01 · UT-F4 는 9/22 저녁'},
 'G3 L2': {'B': '9/23 오전', 'C': 'INT-12a·12b·13·4 통과 (flow_node + use_mock) — 9/22 저녁 시작, 9/23 오전 첫 순서까지. 노션 업로드는 9/22'},
 'G4 L3': {'B': '9/23 오후', 'C': '그릇 1·컵 1 end-to-end + HMI 3회 연속'},
 'G5 L4·동결': {'C': '4개 연속·실패 주입·측정·영상, v1.0-demo 태그 · 🛡 밀리면 SDD §9.9 범위 방어(4개 → 2개, 실패 주입 4종 → 2종)'},
}
SLOT = {        # 로봇 슬롯 표 (A 열 → {열: 글})
 '9/19 토': {'C': 'CELL-04 티칭 1차 계속 + V-19(S·M) — 18시 교육장 마감까지 · 로봇 불필요: F1 골격·motion.py 착수(H)·V-20 Virtual(M·H)·force.py PR(P)·V-12(P) → 17:15 DSN-03 2차 회의(전원)',
             'D': '🚫 교육장 마감(주말 18시) — 일정 없음'},
 '9/20 일': {'B': '1시간씩 교대: 그리퍼 세션 V-05·V-23·V-01(M) → V-02 + weigh 이식(M) / V-03 → V-18·F3-02(P) / CELL-04b 티칭 2차 + V-22 → F1-01(S·P) · 로봇 불필요: motion.py PR·DSN-04·F4-00(H)',
             'C': 'F1-02·V-14(S) / F3-02(P) / V-07·V-16 → F2-01(M) — 1시간씩 교대, 18시 마감 · 로봇 불필요: gripper.py(M)·F4-01·F4-02·MID-01·ARCH-01(H)',
             'D': '🚫 교육장 마감(주말 18시) — 일정 없음'},
 '9/21 월': {'D': '1시간씩 교대(순서는 DSN-03 C1): V-04·V-15 → F1-05(S, P 참여) / V-10 → F3-03(P) / F2-01·F2-02(M) · 로봇 불필요: INT-4·V-13·ENV-03·F4-02(H·M)'},
 '9/22 화': {'B': 'F1-03·V-08(S) / F3-03 마무리(P) / UT-F2(M) · 로봇 불필요: UT-FLOW·FLOW-02(M)·CR-01(전원)·F4-03·노션 업로드(H)',
             'C': 'F1-04·V-06 → UT-F1(S) / UT-F3(P) — G2(L1) 마감 · 로봇 불필요: F4-03·F4-04·NOTE-02(H)',
             'D': 'L2: INT-12a(M·S) → INT-12b(S·M) → INT-13(P·S)'},
 '9/23 수': {'B': 'INT-13 잔여 — G3(L2) → INT-3a·INT-3b L3(M 실행, 전원)', 'C': 'INT-3b·FIX-01 — G4(L3) → INT-4a 연속 처리',
             'D': 'INT-4b 실패 주입 · INT-4c 측정 → INT-4d 영상·동결 (G5)'},
}
RULES = {       # (A 열, B 열 글자) → (새 B, 새 C)
 ('마감', '9/22(화) 오전'): ('9/22(화) 오후', 'L1 단위기능 테스트(UT-F1·F2·F3·FLOW) 통과 — 함수별 TC 는 구현 직후 바로 수행. UT-F4 는 9/22 저녁. 미통과 기능은 범위 방어표대로 축소 · 코드리뷰(CR-01) · 노션에 노드 구조·HMI 화면·안전 자료 업로드 · GitHub 최신'),
 ('마감', '9/22(화) 저녁'): ('9/23(수) 오전', 'L2 단위기능 통합 완료 (flow_node 에서 실행, 나머지 기능은 use_mock) — 9/22 저녁 시작'),
 ('로봇', '비고 R'): ('비고 R', 'R 표시 작업은 실기 로봇 필요. 🚨 주말(9/19·20)은 교육장이 18시에 닫는다 → 하루 2슬롯(오전·오후), 저녁 칸 없음. 평일은 3슬롯(오전·오후·저녁). 배정은 전날 브리핑에서, 로봇 1대를 1시간씩 교대. 9/24~28 불가'),
}
NEW_RULES = [
 ('공용 파일', 'cobot_common · config', 'cobot_common 은 사람별 파일: bootstrap.py·config.py·__init__.py·motion.py = H / gripper.py·weigh.py = M / force.py = P (부르는 쪽은 그대로 cc.함수()). config/cell.yaml 은 한석형 혼자(단 cell.force 절의 값은 박진용이 그 절만 PR), params.yaml 은 자기 절만'),
]
HISTORY2 = ['v5.1', '결정', 'DSN-03, F1-02, V-14, V-01', 'DSN-03 회의를 열지 못해 PM 이 결정: 반납 구역 = 고정 슬롯(겹친·어긋난 용기 대응 제외, pick 서명·EMPTY_ZONE·YAML 키는 그대로) · 그릇 = 옆면(벽) 세로 파지(폭 차이가 작으면 무게로 확인) · 그리퍼 폭 경로·이슈 #7 수락 · 9/19 선결정 확정. 나머지 안건은 보류',
            '시간 부족(교육장 18시 마감) — PM 결정 9/19 16시', 'S,M,P,H']
HISTORY3 = ['v5.2', '결정', 'V-01', '그릇의 파지 성공도 파지 폭으로 가른다 — 옆면 세로 파지 폭 ≈ 2 mm 확인(황인재), 무게(WEIGH)로 가르는 대안은 뺐다. V-01 완료 기준을 "세 값 간격 ≥ 6 mm" → "세 범위가 겹치지 않고 그릇 ↔ 빈손 간격이 흔들림의 2배 이상"으로. grip 의 닫는 목표 폭은 기대 폭보다 작게',
            'PM 결정 9/19 (실측 확인)', 'S,M']
HISTORY4 = ['v5.3', '진척', 'V-01', '그릇 옆면 세로 파지 폭 ≈ 2 mm 가 빈손과 구분되는 것을 검증(황인재 9/19). V-01 의 남은 것은 컵·빈손 포함 10회 기록과 허용 오차 값, 드라이버 경로(V-05) 확인',
            '실기 확인 9/19', 'M,S']
HISTORY5 = ['v5.4', '진척', 'INF-02, F1-01', 'INF-02 motion.py 완료(PR #15, 9/19 — 예정보다 반나절 빠름): move_to 는 상공까지만 + 남은 높이 반환, 새 키 cell.motion 4개(값은 한석형). PR #14(rig_f2 안내) merge. F1-01 은 cell.motion·limits 값이 들어오면 바로 착수 가능',
            'PR #14·#15 merge', 'H,S,M,P']
HISTORY6 = ['v5.5', '진척', 'INF-02d, INF-02', 'INF-02d gripper.py 코드 merge(PR #17, 예정보다 하루 빠름) — 실기 확인(V-05·V-23)과 수정 2건(import 가드·힘 기준 맞추는 시점)이 남음. INF-02 move_joint_rel 속도 상한(PR #16) merge',
            'PR #16·#17 merge', 'M,H']
HISTORY7 = ['v5.6', '진척', 'PKG-01, V-20, V-03, V-05, V-01, DSN-04, INF-02b·c·d', '9/19 저녁 진척 취합(GitHub 기록 기준): PKG-01 완료(#4·#8·#12) · INF-02 완료(#15·#16) · INF-02c 0.7(#13·#14) · INF-02d 0.6(#17) · INF-02a 후속 #10·#18 · V-03 실기 4회차(문지르기 방식 확정) · V-05 경로 구현 · V-20 일부 확인 · DSN-04 결정분 문서 반영',
            'PM-01 9/19 저녁', 'S,M,P,H']
HISTORY8 = ['v5.7', '진척', 'INF-02b', 'INF-02b force.py merge(PR #20) — 공용 로봇 함수 파일 5개(bootstrap·motion·gripper·weigh·force)가 모두 main 에 들어왔다. F1-02 pick 이 기다리던 contact_down 사용 가능. 남은 것은 cell.force·cell.motion·limits 값과 실기 확인',
            'PR #20 merge', 'P,S,M']
HISTORY9 = ['v5.8', '진척', 'V-01', 'V-01: 그릇은 빈손과 폭으로 구분됨(검증), 컵은 벽이 아니라 몸통을 통째로 파지해 폭이 충분 — 3상태 구분은 사실상 확인. 남은 것은 드라이버 경로 기록과 허용 오차 값',
            '황인재 확인 9/19', 'M,S']
HISTORY10 = ['v5.9', '일정', 'CELL-04, V-19, F1-01', '티칭 1차(CELL-04)는 9/19 에 그릇 쪽 좌표까지, 컵 쪽은 9/20 오전으로(좌표 작업이 예상보다 오래 걸림). V-19 도 같이 나뉨. F1-01 은 9/20 오후까지 걸칠 수 있음 — 그릇 좌표로 먼저. 9/20 오전 한석형 4건(CELL-04 컵·CELL-04b·V-22·F1-01)',
             '황인재 확인 9/19 17:50', 'S']
HISTORY = ['v5.0', '재계획', '주말 저녁 칸 전체, V-01·05·23, INF-02·02d(신규)·02b·02c, PKG-01, DSN-03·04, F1-01~05, F2-01·02, F3-03, F4-00~03, UT-*, INT-*, 게이트·로봇 슬롯·규칙',
           '① 주말(9/19·20)은 교육장 18시 마감 → 주말 저녁 칸을 전부 비움(DSN-03 은 9/19 17:15 교육장) ② 한석형은 9/19 티칭까지만 ③ 분담 변경: 그리퍼 검증 V-01·05·23 + gripper.py(신규 INF-02d) = 민범진, '
           '이동 함수 motion.py(INF-02)·cell.force 골격·F1 패키지 골격 = 황인재, 한석형 = 티칭·cell.yaml 값·실기·F1 기능 함수 ④ 게이트: G1 9/20 오후 · L1 9/22 오후 · L2 9/23 오전 · L3 9/23 오후 · 동결 9/23 저녁 그대로(밀리면 범위 방어) ⑤ V-24 보류',
           '교육장 주말 운영 시간(18시 마감) · 한석형 티칭 지연 · 이슈 #7·B11·grip_width 요청을 한석형 부담 없이 수락하기 위함 (PM 결정, DSN-03 에서 확인)', 'S,M,P,H']


def main(out):
    gen_todo.EASY.update(EASY)
    b = Book.from_live(SID)
    tl = b.sheet('Time Line'); d = b.sheet('상세(산출물·완료기준)')

    def has(sheet, col, v):
        try: sheet.find(col, v); return True
        except KeyError: return False

    # 1) 새 행
    for tid, after, like, cat, task, owner, status, slots, deliv, crit, note in NEW:
        if has(tl, ID, tid): continue
        n = new_timeline_row(tl, tl.rows[tl.find(ID, like)], slots, A=None, B=cat, C=task, D=owner, E='0.0', F=status, **{ID: tid})
        tl.insert(tl.find(ID, after) + 1, n)
        q = d.rows[d.find('A', like)].clone()
        for c, v in zip('ACDEFG', [tid, task, owner, deliv, crit, note]): q.set(c, v)
        d.insert(d.find('A', after) + 1, q)
    # 2) 셀 고치기
    for tid, e in EDIT.items():
        r = tl.rows[tl.find(ID, tid)]
        if 'task' in e: r.set('C', e['task'])
        if 'owner' in e: r.set('D', e['owner'])
        if 'status' in e: r.set('F', e['status'])
        if 'prog' in e: r.set('E', e['prog'])
        if 'slots' in e:
            try: set_slots(r, e['slots'])
            except ValueError:                           # 색 칸이 하나도 없는 행(이미 비운 행)
                if e['slots']: raise
        if has(d, 'A', tid):
            q = d.rows[d.find('A', tid)]
            for c, k in (('C', 'task'), ('D', 'owner'), ('E', 'deliv'), ('F', 'crit'), ('G', 'note')):
                if k in e: q.set(c, e[k])
            if 'note_add' in e and e['note_add'] not in d.text(q, 'G'):     # 진척 메모는 앞에 덧붙인다(여러 번 돌려도 한 번만)
                q.set('G', e['note_add'] + ' · ' + d.text(q, 'G'))
    # 3) 완료 행은 진행 1.0 (PM 이 시트에서 완료로 바꾼 행 포함)
    for r in tl.rows:
        if tl.text(r, 'F').strip() == '완료' and tl.text(r, ID).strip(): r.set('E', '1.0')
    # 4) 팀(구역) 이동
    def team_of(i):
        while i >= 0 and not tl.text(tl.rows[i], 'A').strip(): i -= 1
        return tl.text(tl.rows[i], 'A').strip() if i >= 0 else ''
    for tid, (team, after) in MOVE.items():
        src = tl.find(ID, tid); dst = tl.find(ID, after)
        if team_of(src) != team and src != dst + 1:
            if tl.text(tl.rows[src], 'A').strip():           # 구역 첫 행이면 이름표를 다음 행에 넘긴다
                tl.rows[src + 1].cells['A'] = list(tl.rows[src].cells['A'])
            tl.move(src, dst + 1)
            up = tl.rows[tl.find(ID, after)]
            a_style = up.style('A') if not tl.text(up, 'A').strip() else tl.rows[tl.find(ID, after) + 2].style('A')
            tl.rows[tl.find(ID, tid)].set('A', None, style=a_style)
            qs = d.find('A', tid); qd = d.find('A', after)
            if qs != qd + 1: d.move(qs, qd + 1)
        d.rows[d.find('A', tid)].set('B', team)
    # 5) 마일스톤·로봇 슬롯
    m = b.sheet('마일스톤·로봇 슬롯')
    k_mile = m.find('A', '마일스톤'); k_slot = m.find('A', '로봇 슬롯', prefix=True)
    for i, r in enumerate(m.rows):
        key = m.text(r, 'A').strip()
        if i < k_mile and key in LECTURE:
            r.set('B', LECTURE[key][0]); r.set('C', LECTURE[key][1])
        elif k_mile < i < k_slot and key in GATE:
            for c, v in GATE[key].items(): r.set(c, v)
        elif i > k_slot and key in SLOT:
            for c, v in SLOT[key].items(): r.set(c, v)
    # 6) 규칙
    ru = b.sheet('규칙')
    for r in ru.rows:
        key = (ru.text(r, 'A').strip(), ru.text(r, 'B').strip())
        if key in RULES: r.set('B', RULES[key][0]); r.set('C', RULES[key][1])
    ru.rows[0].set('A', f'운영 규칙 (PreWash-Cell 일정표 {VERSION})')
    for rule in NEW_RULES:
        if has(ru, 'A', rule[0]):
            r_ = ru.rows[ru.find('A', rule[0])]; r_.set('B', rule[1]); r_.set('C', rule[2])
        else:
            k = ru.first_empty(); n = ru.rows[k - 1].clone()
            for c, v in zip('ABC', rule): n.set(c, v)
            ru.rows[k] = n
    # 7) 변경이력
    h = b.sheet('변경이력')
    for hist in (HISTORY, HISTORY2, HISTORY3, HISTORY4, HISTORY5, HISTORY6, HISTORY7, HISTORY8, HISTORY9, HISTORY10):
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
    """사람별·칸별 부하(주도 + (참여)) — 브리핑·PM-01 제외, 5건 이상 ⚠. 주말 저녁에 남은 작업이 있으면 🚫 로 알린다."""
    load_ = collections.defaultdict(list); bad = []
    for r in rows:
        if r['status'] in ('완료', '보류') or r['id'] in ('BRF', 'PM-01'): continue
        lead = re.sub(r'\(.*?\)', '', r['owner']); part = ''.join(re.findall(r'\((.*?)\)', r['owner']))
        L = set('SMPH') if '전원' in lead else set(c for c in lead if c in 'SMPH')
        P = (set('SMPH') if '전원' in part else set(c for c in part if c in 'SMPH')) - L
        for dday, p in r['slots']:
            if '~' in dday or int(dday.split('/')[1]) > 23: continue
            if dday in ('9/19', '9/20') and p == '저녁': bad.append(r['id'])
            for w in L: load_[(dday, p, w)].append(r['id'])
            for w in P: load_[(dday, p, w)].append('(' + r['id'] + ')')
    order = {'오전': 0, '오후': 1, '저녁': 2}
    for w in 'SMPH':
        print('==', w)
        for k in sorted([k for k in load_ if k[2] == w and k[0] != '9/18'], key=lambda k: (int(k[0].split('/')[1]), order[k[1]])):
            print(f"  {k[0]} {k[1]} [{len(load_[k])}]{' ⚠' if len(load_[k]) >= 5 else ''} {' '.join(load_[k])}")
    print('🚫 주말 저녁에 남은 작업:', bad or '없음')


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else OUT)
