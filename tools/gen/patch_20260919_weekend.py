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
from xlsx_patch import open_gantt_cols, gantt_col,  Book, Row, new_timeline_row, rebuild_todo, set_slots
from livesheet import SID, load, timeline
import gen_todo

ID = 'AH'
VERSION = 'v9.3'
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
 'INF-02d': dict(status='진행 중', slots=S('9/19 오후', '9/20 오전'),   # 황인재가 시트에서 9/20 오후 → 오전으로 직접 옮김(9/20)
                note='R · ✅ 코드 merge(PR #17, 9/19 — 예정보다 하루 빠름, pytest 22건): 드라이버 소스 기준 구현(힘은 2.5 N 계단·처음에 0 N 으로 기준 맞춤, 폭은 관절각 → 환산, 완료는 effort 로) · 남은 것: ① 9/20 오전 V-05·V-23 실기 확인 ② setup_io 의 onrobot_rg_msgs import 가드(ws_dsr 없이 cc.init 이 죽는다) ③ 힘 기준 맞추기를 쥐지 않은 때(release)로 · 9/19 분담 변경: 한석형 → 민범진 · 박진용 제안서 참고'),
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
 'CELL-04': dict(prog='0.5', slots=S('9/19 오전', '9/19 오후', '9/20 오전'), note='R · 🚨 9/19 는 **그릇 쪽 좌표까지**, **컵 쪽 좌표는 9/20 오전에 끝낸다**(황인재 9/20) · ✅ 티칭 자세 = 그 기능이 동작을 시작하는 자세(황인재 확정 9/20 — 시험에서 맞지 않으면 좌표가 아니라 파라미터를 고친다) · V-19 를 이 세션 안에서 · 티칭 자세 = 그 기능의 시작 자세(WASTE·수조는 위에서, WEIGH 는 안전 높이 이상 권장 — SDD §5.3) · cell.motion 4개·limits 값도 같이 · 18시 교육장 마감'),
 'V-19': dict(slots=S('9/20 오전'), note='R · 좌표 작업(CELL-04)이 끝나야 할 수 있다 → 9/20 오전 좌표가 끝난 직후(황인재 9/20) · V-22 좌표 재현과 한 흐름으로'),
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
 ('FLOW-03', 'FLOW-02', 'FLOW-02', '개발', '정지·재개·중단 연결 — /flow/stop = 즉시 일시 정지(이동 도중 멈춤) · /flow/resume = 하던 동작을 이어서(실패로 멈춘 경우는 실패한 단계부터 다시) · /flow/abort 신설(툴 반납 → 용기를 격리 구역에 → HOME → 다음 용기, ROBOT_ERROR 에서는 거부) · 이벤트 DONE/ISOLATED/ERROR',
  'M', '시작 전', S('9/22 오전', '9/22 오후'), 'src/f2_sense_flow/f2_sense_flow/flow.py · flow_node.py + test_f2_policy.py',
  'mock 으로: 일시 정지 → 재개(이어서) · 실패 PAUSE → 재개(그 단계부터 다시) · abort → ISOLATED 기록·다음 용기 · ROBOT_ERROR 에서 abort 거부 · rig_v20.py probe 통과',
  '9/20 황인재 결정(IRD §6 · SDD §5.1): 사람이 확인하고 문제없으면 마저(resume), 문제라고 판단하면 접는다(abort) · motion.py 의 pause/resume 호출(V-24)이 main 에 들어온 뒤 연결 · FLOW-01 의 격리 마무리 동작(9/22 오후)과 같은 코드라 같이 한다 · 힘제어·접촉 구간은 그 동작을 마친 뒤 멈춤(9/20 오전에 만든 단계 사이 정지 그대로)'),
 ('V-25', 'F1-01', 'F1-01', '검증', 'V-25 F1-01 실기 확인 — f1.move_to · 일반 place 를 실기에서(가상 로봇에서는 진짜 그리퍼 release 를 못 돌린다)',
  'H(S)', '시작 전', S('9/21 저녁'), 'docs/test_logs/20260921_F1-01_실기_황인재.md',
  '3회 연속 OK · 용기가 홈 안에 놓임 · **놓은 뒤 올라올 때 용기를 끌지 않음** · MoveIncomplete 0회 · release 뒤 그리퍼 열림 (실패하면 접근점·place_clear_mm·presets 조정 후 재시도)',
  '황인재 9/20 21:30: "F1-01 은 가상으로만 확인했으니 일정에 실기 검증을 넣는다". R · 20~30분 · vel_scale 0.3 · 황인재가 직접 실행, 한석형 입회. 절차: ① HOME → WEIGH(BOWL) → WASTE(BOWL) → HOME 3회 ② 그릇을 쥐여 주고 place SPONGE_BED_B 3회(진짜 release) ③ 컵으로 SPONGE_BED_C 3회 ④ 좌표가 있으면 ISOLATE 각 1회. 🚨 9/21 저녁 **V-22·V-19 바로 뒤**(같은 좌표·같은 전제: limits·motion·presets + E7 코드) — 넘치면 9/22 오후 F1-03·V-08 앞. F1-03 은 V-08(실기 10회)이 곧 실기 검증이라 따로 두지 않는다'),
 ('CELL-02b', 'CELL-02', 'CELL-02', '기구', '툴·홀더 확정(수세미 툴·솔·홀더 2종 — 잡는 자리·놓는 방향) + 그릇 받침 유격 보강 — 9/21 에 확정(황인재 9/20)',
  'P(H,S)', '시작 전', S('9/21 저녁'), '확정된 툴·홀더 실물 + 사진 · 치수(세척부 높이·지름) 갱신',
  '툴을 홀더에서 10번 집고 놓아도 같은 자리 · 그릇을 손으로 5 N 밀어 안 밀림(CELL-02 의 완료 기준)',
  '9/20 한석형: 툴·홀더를 제작 중이라 툴 집기·SOAP·툴 반납 좌표를 못 찍는다 · 박진용 V-03 기록: 그릇이 스펀지 구멍 안에서 흔들린다(구멍이 그릇보다 크다) → CELL-02(9/19 완료 처리)의 완료 기준이 안 맞아 다시 연다. 🚨 9/21 저녁 **첫 순서** — 끝나면 바로 한석형이 홀더 좌표 티칭(CELL-04b) → F1-03(황인재)·F3-03(박진용)이 9/22 에 이 좌표로. 담당: 박진용(실물·파지 기준) · 황인재(제작 지원) · 한석형(홀더 위치가 집기 자세에 맞는지)'),
 ('INF-02d', 'INF-02', 'INF-02', '계약', 'cobot_common · gripper.py — 그리퍼 함수(저수준) grip · grip_level(NORMAL/HOLD) · release · grip_width(현재 폭 mm)',
  'M', '시작 전', S('9/20 오후'), 'src/cobot_common/cobot_common/gripper.py', '실기에서 명령 → 동작 → 폭(mm) 읽힘 · NORMAL↔HOLD 전환 · Virtual 에서는 가짜 그리퍼 노드로 호출 순서',
  'R · 9/19 분담 변경: 한석형(motion.py 안) → 민범진(새 파일) · V-05·V-23·V-01 결과가 곧 구현 · 박진용 제안서 참고, 박진용이 PR 리뷰 · F3 요청 grip_width() 포함 · 구독은 setup_io(node)'),
]
# 9/19 저녁 진척 취합(PM-01) — 근거: main 에 merge 된 PR #3~#18, 팀원 브랜치의 커밋 기록, 황인재 확인
PROGRESS = {
 'FLOW-02': dict(note_add='🆕 9/20 인터페이스 확정(황인재): flow_node 의 통신 노드가 **/cell/force**(Float32 10 Hz, 닦는 동안만)와 **/cell/gripping**(Bool, 바뀔 때 + 2 Hz)을 발행한다 — 9/22 오전까지(IRD §6). 파지 여부는 gripper.py 가 판정(공개 함수 gripping() 등), 힘 값은 박진용의 닦기 루프가 force.py 에 저장만'),
 'F3-02': dict(note_add='🆕 9/20: 닦기 루프에서 읽는 힘 값을 force.py 에 **저장만** 해 둔다(/cell/force 발행은 flow_node 통신 노드 — 기능 함수 안에서 발행기를 만들지 않는다) · 매 걸음 cc.force_check() 로 상한 감시'),
 'F4-03': dict(note_add='9/20 F4-00 결정: Next.js 15(Node 18) · [MOCK] 표시 없음 · 닦는 힘 그래프(/cell/force) · 파지 중/아님(/cell/gripping) · 팔레트 4칸(그릇 2·컵 2) · 버튼 이름은 **일시 정지**'),
 'V-02': dict(note_add='9/20 민범진: 측정 도구는 브랜치 beomjin/20260918-V-02-weigh-precision 의 tools/v02_weigh.py(아직 main 에 없음 — 브랜치를 지우지 않는다) → V-02 가 끝나면 결과와 함께 PR'),
 'CELL-03': dict(slots=S('9/20 오전'), note_add='9/20 오전에 한다(황인재 9/20) — 9/19 오전 칸에서 옮김'),
 'CELL-01': dict(task='반납 구역 2곳(그릇·컵)·식기세척기용 팔레트(그릇 2·컵 2 — 9/20 변경)·격리 구역 배치·핑거 패드', status='진행 중', slots=S('9/18 오후', '9/18 저녁', '9/19 오전', '9/19 오후', '9/20 오전'), note_add='좌표 측정(CELL-04)과 함께 진행 중(황인재 9/20) — 슬롯 자리 표시 포함'),
 'PKG-01': dict(status='완료', note_add='✅ 9/19 완료 — F1 골격 PR #12 · F2 PR #8 · F3 PR #4 전부 main'),
 'INF-02a': dict(note_add='후속 수정 merge: #10(콜백 예외로 통신 스레드가 끝나던 문제) · #18(robot=False 면 setup_io 훅 실패를 건너뛴다 — ws_dsr 없이도 init)'),
 'INF-02c': dict(prog='0.7'),
 'INF-02d': dict(prog='0.8', note_add='✅ 9/20 PR #26 merge: 힘 기준 맞추기를 빈손이 확실한 자리(release 뒤·grip 앞)로만, grip_level 은 기준이 없으면 거부 + 실기 시험대 rig_gripper.py(V-05·V-23·V-01 을 재고 판정, 팔은 안 움직임) → 남은 것은 실기 세션 결과 · 9/20 민범진: 힘 기준 맞추는 시점 수정은 **로봇 세션 전(오전)에** 한다(V-23 전) · 실측값 반영은 그리퍼 세션 뒤에 이어서'),
 'INF-02b': dict(prog='0.85', note_add='✅ 9/20 PR #24 merge: contact_down 을 시작 힘 대비 변화량으로(실기에서 공중 2 N 때문에 깊이 0.1 mm 에서 접촉 오판) · force_off 끝까지 시도 · force_check 추가 · PR #23 시험 파일 이름 · TS-05 문서 · 남은 것: safe_retreat 가 force_off 실패에도 후퇴하게 · 절대 힘 뒷받침 · periodic_search 힘 감시(V-04 전) · cell.force 값 PR · (이전) ✅ 9/19 17:40 PR #20 merge — force.py(순응·힘제어·접촉 하강·탐색·안전 후퇴·read_force·예외 2종) + pytest 23건 + Virtual rig · 남은 것: cell.force 값 PR(V-03 뒤)·force_off 끝까지 시도·force_on limit 감시 도우미·periodic_search 힘 감시(V-04 전) · (이전 메모) 9/19 17:16 기준(커밋 기록): 브랜치 jinyong/20260919-INF-02b-force-funcs 에 force.py·test_force.py·rig_force (15커밋), PR 은 아직 · motion.move_rel 이 main 에 들어왔으니(#15) 임시 stub 을 지우고 PR'),
 'V-03': dict(prog='0.6', note_add='9/19 오후 실기 4회차까지(커밋 기록 16:04~17:16): 힘제어 중 X·Y 이동 확인, 문지르기 방식 = 손목을 비틀며 나선으로 넓혀 벽을 찾고 벽 따라 2바퀴(8자 삭제) · 남은 것: 결과 문서(docs/test_logs)와 cell.force 값 PR'),
 'V-01': dict(prog='0.7', note_add='✅ 9/19 황인재 확인: 그릇(옆면 세로 파지 ≈ 2 mm)은 빈손과 폭으로 구분된다 · 컵은 벽이 아니라 **몸통을 통째로 파지**(폭 ≈ 컵 지름)라 빈손·그릇과 간격이 충분하다 → 3상태 구분은 사실상 확인됨 · 남은 것: 드라이버 경로(V-05)로 10회씩 기록 + 그릇 전용 허용 오차 값을 cell.yaml 에'),
 'V-05': dict(status='진행 중', prog='0.3', note_add='9/19: 드라이버 소스 분석으로 폭 읽는 경로를 구현(#17 — 관절각 → 폭 환산, 장치가 읽은 0.1 mm 폭과 같다) → 9/20 오전에 실기로 확인(닫힌 쪽 0~5 mm 반복 흔들림 포함), 확정은 그 뒤'),
 'V-20': dict(status='진행 중', prog='0.3', slots=S('9/19 오후', '9/20 오전'), note_add='9/19: cobot_common 실행 뼈대는 Virtual rig_motion 3바퀴·검사 30건으로 확인(#15) → 남은 것: flow_node + 세 모듈을 Virtual 에서 한 번에(로봇 불필요 — 로봇 교대 대기 시간에)'),
 'DSN-03': dict(prog='0.7'),
 'DSN-04': dict(status='진행 중', prog='0.7', slots=S('9/19 오후', '9/20 오전'), note_add='9/19 PM 결정분(고정 슬롯·그릇 옆면 파지·폭 판정·이슈 #7·motion/gripper 구현 방식)은 BR-SR·IRD·SDD·AGENTS·프롬프트·일정표에 반영 완료 · 남은 것: contracts.py pick docstring(황인재)·cell.yaml zones/presets 주석(한석형)·확인 대기 3건(B7 격리 마무리 순서·B11·B12)'),
}
for _tid, _e in PROGRESS.items():
    EDIT.setdefault(_tid, {}).update(_e)

# ---------------------------------------------------------------- 9/20 재계획 (황인재 지시: 좌표 작업 지연으로 쌓인 일 정리)
# 원칙: ① 한석형의 오늘 오전은 좌표 마무리(CELL-04·CELL-01·V-19)만 ② F1 사슬을 반 칸씩 뒤로 — 좌표 없이 되는 남의 일은 그대로
#       ③ 한석형 몫을 덜어 준다: V-22 → 황인재(motion.py 주인이 실기에서 확인) · V-20 → 황인재(bootstrap 주인, Virtual) · V-16 은 민범진 단독
#       ④ 동결(9/23 저녁)은 그대로 — 밀리면 SDD §9.9 범위 방어(컵 e2e·실패 주입 4종 → 2종·4개 연속 → 2개)
WHY = '9/20 재계획: 좌표 작업(CELL-04)이 9/20 오전까지 이어져'
REPLAN_0920 = {
 'CELL-04':  dict(owner='S', note_add='🚨 9/20 황인재: **팔레트 컵 칸 4 → 2**(RACK_C1·C2) — 좌표 PR 에서 cell.yaml 의 RACK_C3·C4 두 줄을 지운다. PM 이 그 PR 을 꼼꼼히 확인한 뒤 승인하고, 같은 때 contracts.py·params.yaml·시험 2개를 맞춘다 · 9/20 재계획: 9/19 민범진 참여, 9/20 오전 컵 쪽은 한석형 단독(민범진은 그리퍼 세션이 먼저)'),
 'CELL-04b': dict(slots=S('9/20 오후'), note_add=WHY + ' 오전 → 9/20 오후 첫 순서(박진용 참여 — F3-02 가 SPONGE_BED_B 를 기다린다)'),
 'V-22':     dict(owner='H(S)', slots=S('9/20 오후'), note_add=WHY + ' 한석형 → **황인재 주도**(motion.py 주인이 실기에서 YAML 좌표 재현을 확인한다, 한석형은 좌표 제공·입회) · 티칭 2차 뒤에'),
 'V-20':     dict(owner='H(M)', status='완료', slots=S('9/19 오후', '9/20 오전', '9/20 오후'),   # 9/20 오전 칸은 황인재가 시트에서 직접 추가(9/20)
             note_add='✅ 9/20 완료 — stop 위치 수정(PR #26) 뒤 rig_v20.py probe **4/4 통과**(민범진 재검증, 기록 docs/test_logs/20260920_V-20재검증_FLOW-01_민범진.md · 정지까지 5.8 s → 0.6 s) · (이전) 🟡 9/20 10:35 Virtual 실행(PR #22, 기록 docs/test_logs/20260920_V-20_황인재.md): **4개 중 3개 통과** — 세 모듈 실제 import·robot=True 로 용기 4개 × 함수 13회 ✅ · 모션 중 /flow/state 2.000 Hz ✅ · IDLE 에서 Ctrl+C 뒤 재실행 ✅ · 🔴 **stop 이 함수 사이가 아니라 용기 사이에서만 먹는다**(flow.py run_plan 에서만 stop 을 봄 — IRD §6·SDD §5.1 과 다름) → 민범진이 flow.py 수정 뒤 rig_v20.py probe 로 재검증(5분)하면 완료 · 9/20 재계획: 민범진 → 황인재 주도'),
 'V-16':     dict(owner='M', note_add='9/20 재계획: 한석형 참여 제외 — 찾은 HOLD 값만 한석형에게 전달(cell.yaml 프리셋)'),
 'F1-01':    dict(slots=S('9/20 오후'), note_add=WHY + ' 오전 → 9/20 오후(티칭 2차 뒤) · 그릇 좌표로 먼저'),
 'F1-02':    dict(slots=S('9/21 저녁'), note_add=WHY + ' 9/20 오후 → **9/21 저녁**(로봇 1시간 교대의 한석형 순서) · 코드는 9/20 오후~9/21 에 Virtual 로 미리'),
 'V-14':     dict(slots=S('9/21 저녁'), note_add=WHY + ' F1-02 와 함께 9/21 저녁'),
 'V-04':     dict(slots=S('9/22 오전'), note_add=WHY + ' 9/21 저녁 → 9/22 오전'),
 'V-15':     dict(slots=S('9/22 오전'), note_add=WHY + ' 9/21 저녁 → 9/22 오전'),
 'F1-05':    dict(slots=S('9/22 오전'), note_add=WHY + ' 9/21 저녁 → 9/22 오전(박진용 참여)'),
 'V-08':     dict(slots=S('9/22 오후'), note_add=WHY + ' 9/22 오전 → 오후'),
 'F1-03':    dict(slots=S('9/22 오후'), note_add=WHY + ' 9/22 오전 → 오후'),
 'V-06':     dict(slots=S('9/22 저녁'), note_add=WHY + ' 9/22 오후 → 저녁'),
 'F1-04':    dict(slots=S('9/22 저녁'), note_add=WHY + ' 9/22 오후 → 저녁'),
 'UT-F1':    dict(slots=S('9/22 저녁', '9/23 오전'), note_add=WHY + ' L1 의 F1 분은 9/22 저녁~9/23 오전 첫 순서(함수별 TC 는 구현 직후 바로)'),
 'INT-12b':  dict(slots=S('9/23 오전'), note_add=WHY + ' rack_place(F1-04)가 9/22 저녁이라 9/23 오전으로'),
 'INT-3a':   dict(slots=S('9/23 오후'), note_add='9/20 재계획: L2 가 9/23 오전까지라 그릇 e2e 는 9/23 오후'),
 'INT-3b':   dict(slots=S('9/23 오후', '9/23 저녁'), note_add='9/20 재계획: 🛡 범위 방어 1순위 — 밀리면 컵 e2e 는 1회로 줄이거나 도전 과제로'),
 'INT-4a':   dict(slots=S('9/23 저녁'), note_add='9/20 재계획: 9/23 오후 → 저녁 · 🛡 밀리면 4개 연속 → 2개'),
 'FIX-01':   dict(slots=S('9/23 오후', '9/23 저녁')),
 'F3-02':    dict(note_add='9/20 재계획: 셀 좌표(SPONGE_BED_B)는 9/20 오후 티칭 2차 뒤에 나온다 — 그 전에는 V-03 rig 좌표로 만든다'),
 'FLOW-01':  dict(prog='0.9', slots=S('9/19 오전', '9/19 오후', '9/20 오전', '9/22 오후'), note_add='✅ 9/20 PR #26 merge: stop 을 단계 사이마다(멈출 때 그리퍼 명령 없음) — V-20 4/4 · 남은 것: 격리 마무리 동작(9/22 오후)·재시도/격리 도중의 stop 시험 1건 · 정지 방식 결정 요청 D1~D4(docs/meetings, 민범진 → 황인재) 대기 · ✅ 9/20 민범진 확인: (a) 문서대로 단계 사이마다 정지로 고친다 — 든 채 멈출 때 파지는 NORMAL 그대로·그리퍼 명령을 새로 보내지 않는다(SDD §5.1) · 🔴 9/20 V-20 에서 발견: **stop 을 process_one() 의 단계 사이에서도 봐야 한다**(지금은 용기 사이에서만 → 정지 버튼을 눌러도 용기 1개를 끝낸 뒤에야 멈춘다, IRD §6·SDD §5.1 과 다름) — 9/21 저녁 INT-4·V-13 전에 수정, rig_v20.py probe 로 재검증 · 9/20 재계획: 남은 것(격리 마무리 동작)은 로봇이 필요 없어 비어 있는 9/22 오후로 — 9/20 오전 민범진 7건을 덜어 준다(L2 9/22 저녁 전까지면 된다) · ✅ 9/20 황인재 확정: 격리 마무리 순서 = 툴 반납 → 용기를 ISOLATE 에 놓기 → HOME · ROBOT_ERROR = 그 자리 정지 + PAUSED + 사람이 복구(SDD §7)'),
 'DSN-03':   dict(status='완료', note_add='✅ 9/20 아침 황인재: B7(격리 순서·ROBOT_ERROR)·B11(move_joint_rel)·B12(mock_f2) 승인, 티칭 자세 규칙 확정 → 급한 안건 종료. 보류 안건은 필요할 때'),
 'DSN-04':   dict(status='완료', note_add='✅ 9/20 완료: 결정분을 BR-SR·IRD(§2·§10)·SDD(§3.1·§4.3·§5.2·§5.3·§7)·AGENTS·프롬프트·일정표에 반영, contracts.py pick 설명은 PR #21 · cell.yaml 의 zones/presets 주석은 한석형의 좌표 PR(CELL-04)에서'),
}
CH = '🚨 추석(9/24~28)은 교육장이 닫힌다 — 집에서 하는 원격 작업(황인재 9/20)'
CHUSEOK = {
 'DOC-02': dict(note_add=CH + ' · 기능별 1장은 각자, 취합은 황인재'),
 'DOC-03': dict(note_add=CH + ' · 영상 원본은 9/23 저녁에 드라이브에 올려 둔다(교육장 PC 에만 두지 않는다)'),
 'DOC-04': dict(note_add=CH),
 'DOC-05': dict(note_add=CH + ' · 측정 결과(records·KPI)·사진도 9/23 저녁에 저장소·드라이브에'),
 'REH-01': dict(note_add=CH + ' · 온라인(화상)으로'),
 'INT-4d': dict(note='R · 9/23 저녁 동결 · 🚨 추석에는 교육장에 못 들어간다 → 동결할 때 **영상 원본·측정 결과·사진·로그를 전부 드라이브·저장소에 올린다**(집에서 PPT·영상 편집에 쓴다) · ✅ 로봇·기구는 추석 동안 **세팅 그대로 둔다**(황인재 확인 9/20) — 재배치·재티칭 불필요'),
 'REH-02': dict(note='R · 9/29 · ✅ 로봇·기구는 추석 동안 세팅 그대로(황인재 확인 9/20) → 재배치·재티칭 없이, 브링업 뒤 **좌표 재현 빠른 확인(V-22 방식, 10분)**만 하고 바로 리허설'),
}
REPLAN_0920.update({k: {**REPLAN_0920.get(k, {}), **v} for k, v in CHUSEOK.items()})
for _tid, _e in REPLAN_0920.items():
    EDIT.setdefault(_tid, {}).update(_e)

# ---------------------------------------------------------------- 9/20 14:50 최신화 (황인재 지시)
# "아직 끝나지 않은 일은 진행 중으로, 오늘 오후에도 이어서 하니 9/20 오후 칸에 표시" — 근거: main 의 PR #21~#29·문서, 팀원 브랜치 커밋, F4 세션 보고
AM, PM_ = '9/20 오전', '9/20 오후'
CONT = '9/20 오후에도 이어서 진행(황인재 9/20 14:50)'
LATEST_0920PM = {
 # 한석형 — 오늘 GitHub 기록 없음(cell.yaml PR 아직). 좌표 작업이 이어진다
 'CELL-04':  dict(status='진행 중', slots=S('9/19 오전', '9/19 오후', AM, PM_), note_add=CONT + ' · cell.yaml PR 은 아직 없다(limits·motion 값을 팀 전체가 기다린다)'),
 'CELL-01':  dict(status='진행 중', slots=S('9/18 오후', '9/18 저녁', '9/19 오전', '9/19 오후', AM, PM_), note_add=CONT),
 'V-19':     dict(status='진행 중', slots=S(AM, PM_), note_add=CONT + ' · 좌표가 끝난 직후에'),
 # 민범진 — 오전에 PR #26·#28·#29(코드)와 결정 요청 문서 2건. 그리퍼·무게 실기 세션 결과는 아직 올라오지 않았다
 'CELL-03':  dict(status='진행 중', slots=S(AM, PM_), note_add=CONT),
 'V-02':     dict(status='진행 중', slots=S(AM, PM_), note_add=CONT),
 'V-01':     dict(status='진행 중', slots=S(AM, PM_), note_add=CONT + ' · 시험대 rig_gripper.py 준비됨(#26·#29)'),
 'V-05':     dict(status='진행 중', prog='0.4', slots=S(AM, PM_), note_add=CONT + ' · 시험대 rig_gripper.py 준비됨(#26·#29) — 실기 결과 대기'),
 'V-23':     dict(status='진행 중', prog='0.3', slots=S(AM, PM_), note_add=CONT + ' · 🚨 시험대가 빈손으로도 통과하던 결함을 고침(#29 — 닫는 목표를 기대 폭보다 작게, 최초 파지 폭이 기대 범위 밖이면 중단)'),
 'INF-02c':  dict(status='진행 중', slots=S(AM, PM_), note_add=CONT),
 'INF-02d':  dict(status='진행 중', prog='0.85', slots=S('9/19 오후', AM, PM_), note_add='9/20 오후: PR #28(힘 기억을 명령마다 갱신·실패하면 버림) · #29(V-23 시험대) merge — 남은 것은 실기 세션 결과'),
 'FLOW-01':  dict(status='진행 중', prog='0.9', slots=S('9/19 오전', '9/19 오후', AM, PM_, '9/22 오후'), note_add='9/20 오후: PR #28 merge — 남은 resume 깃발이 다음 정지를 0초 만에 풀던 길 · 재시도 뒤 최신 실패 코드로 정책 재조회(ROBOT_ERROR 가 격리로 새던 길). 황인재 결정 대기 2건: 정지 방식(D1~D4) · PAUSE 로 멈춘 용기 처리(D1·D2) — docs/meetings/20260920_결정요청_*_민범진.md'),
 # 박진용 — PR #23·#24·TS-05. V-03 은 실기 7회차까지(브랜치의 기록), wipe_bowl 은 브랜치에서 작성 중
 'INF-02b':  dict(status='진행 중', slots=S('9/19 오후', AM, PM_), note_add=CONT),
 'V-03':     dict(status='진행 중', prog='0.8', slots=S('9/19 오후', AM, PM_), note_add='9/20: 실기 7회차까지(브랜치 jinyong/20260920-V-03-log 의 시험 기록 — 아직 PR 전) · rig 갱신 13:17 · ' + CONT),
 'V-18':     dict(status='진행 중', slots=S(AM, PM_), note_add=CONT),
 'F3-02':    dict(status='진행 중', prog='0.3', note_add='9/20: 브랜치 jinyong/20260920-F3-02-wipe-bowl 에서 작성 중(나선 → 벽 따라 2바퀴, 옆 힘 비상 정지) — 아직 PR 전'),
 # 황인재(F4 세션)
 'F4-00':    dict(status='완료', note_add='✅ 9/20 13:55 설계 확정 문서 merge(docs/ref/20260920_F4-00_HMI_설계초안.md): Next.js 15 + Node 18 · [MOCK] 표시 없음 · 힘 그래프 · 파지 중/아님 · 팔레트 4칸 — 정지 버튼 구성은 정지 방식 결정 뒤 갱신'),
 'V-24':     dict(status='진행 중', prog='0.3', slots=S(PM_), note_add='9/20 V-24a 가능성 시험(Virtual, F4 세션 — 브랜치 injae/20260920-V-24a-stop-feasibility, PR 은 황인재 확인 뒤): ✅ 동기 이동 중 move_stop 은 0.05 s 에 멈춘다(단 끊긴 movej 가 0(성공)을 돌려주고, 다음 명령을 보내면 다시 움직인다 → 정지 깃발·가드 필요) · ❌ 동기 이동 중 move_pause 는 안 먹는다 · ✅ 비동기(amovej + check_motion 폴링)에서는 pause → resume 으로 같은 동작이 이어진다 → "즉시 멈추고 재개"는 motion.py 를 비동기로 바꿔야 한다. 🚨 힘제어 중의 일시정지는 실기 확인 필요. **본작업 여부는 황인재 결정 대기**'),
}
for _tid, _e in LATEST_0920PM.items():
    EDIT.setdefault(_tid, {}).update(_e)

# ---------------------------------------------------------------- 9/20 15:30 황인재 결정: 즉시 일시 정지 → 재개로 이어서 · 중단(격리) · 웹 HMI 는 추석에도
CH_ = '9/24~28'
STOP_0920 = {
 'V-24':    dict(owner='H(M,P)', status='진행 중', prog='0.3',
                 task='V-24 즉시 일시 정지 — motion.py 를 비동기 이동(amovej/amovel) + check_motion 폴링으로 · bootstrap 에 pause/resume/stop 호출과 정지 깃발 · Virtual 시험 → 9/22 오전 실기 확인(이동 도중 멈춤 → 재개로 같은 동작을 이어서)',
                 slots=S('9/20 오후', '9/21 저녁', '9/22 오전'),
                 deliv='src/cobot_common/cobot_common/motion.py · bootstrap.py + test/rig_stop.py · docs/test_logs',
                 crit='Virtual: rig_motion 3바퀴 + rig_stop 통과(호출하는 쪽 코드 변경 없음) · 실기: 관절·직선·용기를 든 이동에서 멈춤 → 재개로 같은 동작 완료 3회',
                 note_add='✅ 9/20 황인재 결정: **선택 과제 → 한다**(목적: 문제가 생겼을 때 바로 멈췄다가, 사람이 보고 문제없으면 이어서). 범위: 자유 공간 이동만 즉시 멈춤 — 힘제어·접촉 구간(접촉 하강·닦기·안착 탐색)은 그 동작을 마친 뒤 멈춤(실기 확인 뒤 넓힐 수 있다). 되돌아갈 자리: 9/22 오전까지 실기 확인이 안 되면 지금의 단계 사이 정지로 시연(서비스 이름이 같아 HMI 는 그대로). 민범진의 연결은 FLOW-03'),
 'F4-01':   dict(slots=S('9/21 저녁'), note_add='9/20 재배치: V-24(이동 함수 비동기 전환)를 먼저 하느라 9/20 오후 → 9/21 저녁'),
 'F4-02':   dict(task='REST/WS 브리지·버튼 4종(시작 · 일시 정지 · 재개 · 중단) — 멈추면 "일시 정지됨 — 어느 단계" 를 크게 표시("E-STOP" 이라 쓰지 않는다)',
                 slots=S('9/21 저녁', '9/22 오전'), note_add='9/20 결정: /api/abort 추가(IRD §6) · 한계 문구 없음 · 9/20 재배치: 9/21 저녁~9/22 오전'),
 'V-13':    dict(slots=S('9/22 오전'), note_add='9/20 재배치: 9/21 저녁 → 9/22 오전(F4-02 뒤)'),
 'INT-4':   dict(task='INT-4 flow(mock)+HMI — 시작·일시 정지·재개·중단', slots=S('9/22 오후'), note_add='9/20 재배치: 9/21 저녁 → 9/22 오후 · 민범진의 FLOW-03 과 함께'),
 'F4-03':   dict(slots=S('9/22 오후', '9/22 저녁', CH_ + ' 오전'), note_add='🆕 9/20 황인재: **웹 HMI 는 추석에도 집에서 이어 간다**(로봇 불필요 — mock·fake_state_pub). 9/22 에는 시연·노션 gif 에 필요한 최소 화면(단계·버튼·연결 상태·힘 그래프 자리)까지, 다듬기는 추석에'),
 'NOTE-02': dict(slots=S('9/22 저녁'), note_add='9/20 재배치: 그날 저녁까지 나온 화면으로 gif(강사 9/22 요구) — 추석에 화면이 바뀌면 다시 올린다'),
 'F4-04':   dict(slots=S(CH_ + ' 오전', CH_ + ' 오후'), note_add='🆕 9/20 황인재: 추석에 집에서(mock 으로 /flow/event 를 받아 SQLite 기록·이력 API). 9/23 L3·L4 에는 없어도 된다(기록은 flow 의 records.csv 가 있다)'),
 'UT-F4':   dict(slots=S('9/23 오전', CH_ + ' 저녁'), note_add='9/20 재배치: 9/23 오전에 최소 범위(버튼 4종·상태·연결 끊김 표시) → 전체 TC-11 은 추석에 mock 으로'),
 'F4-05':   dict(slots=S('9/23 오전'), note_add='9/20 재배치: 9/23 오전만(INT-4c 측정 전에)'),
 'V-22':    dict(slots=S('9/20 오후', '9/21 저녁'), note_add='cell.yaml 의 limits·motion 값(한석형 PR)이 main 에 들어와야 한다 — 9/20 에 못 하면 9/21 저녁 첫 순서'),
 'INF-02b': dict(note_add='🆕 9/20 결정(V-24): force.py 의 접촉 하강·닦기·안착 탐색은 **즉시 멈춤을 보류하는 구간** — 그 동작을 마친 뒤 멈춘다. 표시 방법은 황인재의 motion/bootstrap API 가 나오면 맞춘다 · 9/22 오전 실기 확인에 참여(힘이 걸린 채 멈춤이 되는지는 그때 같이 본다)'),
 'FLOW-01': dict(note_add='🆕 9/20 황인재 결정 2건 → 구현은 FLOW-03(9/22): ① 일시 정지 = 즉시 멈춤 → 재개로 이어서 ② 실패로 멈춘 용기 = 사람이 확인해 마저(resume, 실패한 단계부터) 또는 접기(abort 신설 — 격리). 결정 요청 문서 2건에 답을 적었다'),
}
for _tid, _e in STOP_0920.items():
    EDIT.setdefault(_tid, {}).update(_e)

# ---------------------------------------------------------------- 9/20 15:50 그리퍼 조작 방법(민범진 결정 요청 #32) — 검증한 뒤에 정한다
GRIP_0920 = {
 'V-23': dict(note_add='🆕 9/20 황인재: 그리퍼 조작 방법 D2(털기 뒤 HOLD 유지 vs NORMAL 복귀)는 **이 검증 결과로 정한다** — HOLD → NORMAL 로 낮출 때의 폭 변화·미끄러짐을 방향별로 기록(그릇·컵 각 10회)'),
 'V-16': dict(note_add='🆕 9/20 황인재: V-23 에서 낮출 때 미끄러지면 "HOLD 유지" 후보 → HOLD 힘으로 30 s 들고 있기 3회(용기 변형·자국 없음)를 같이 확인'),
 'V-05': dict(note_add='🆕 9/20 황인재: 그리퍼 조작 방법 D1(힘 기준을 0 N 쪽 vs 40 N 쪽)은 **검증한 뒤에 정한다** — 세션에서 ① 브링업 직후 힘이 40 N 인가 ② 빈손에서 양쪽 기준 맞추기 때 핑거가 움직이는가 ③ 그릇·컵을 쥔 채 40 N 까지 올렸을 때 폭 변화·변형(3회) ④ 빈손 폭(핑거팁 두께 × 2)·용기 높이(64/45 mm 제한)를 기록. 오늘은 지금 코드 그대로 진행'),
 'INF-02d': dict(note_add='🆕 9/20: 민범진 결정 요청 #32 — D1·D2 는 검증 뒤 결정, **버그 3건(파지할 때마다 10 s 타임아웃 · 무조건 success · 안전 스위치 감지)은 바로 수정**'),
}
for _tid, _e in GRIP_0920.items():
    EDIT.setdefault(_tid, {}).update(_e)

# ---------------------------------------------------------------- 9/20 16:20 한석형 브랜치 확인(seokhyung/20260919-CELL-04-teaching)
SEOK_0920 = {
 'CELL-04': dict(prog='0.7', note_add='🔎 9/20 16:20 PM 확인 — 브랜치 seokhyung/20260919-CELL-04-teaching: **좌표 약 25개는 이미 티칭돼 있다**(그릇·컵 경로 전체: 집기 · 잔반통 앞 · 스펀지 홈 놓기(접근점+끝점) · 툴 집기/반납 · 닦는 자리 · 재파지 · 헹굼 앞 · 팔레트 그릇 2·컵 2). 다만 **cell.yaml 이 아니라 Virtual 단계 실행 스크립트(rig_f1.py v6) 안에 상수로** 들어 있어 팀이 쓸 수 없다. 늦어진 원인: ① cell.yaml 골격이 "기준점 + 오프셋·스테이션마다 자세 1개"인데, 실제 티칭은 "종류별(그릇은 위에서·컵은 옆에서) 절대 자세 + 접근점" 이라 맞지 않는다 ② 전체 경로를 Virtual 에서 한 번에 확인하는 스크립트를 6판까지 고쳤다(ChatGPT 웹이라 한 판이 오래 걸린다). 빠진 것: WEIGH · SOAP · ISOLATE · 구역의 두 번째 슬롯 · limits·motion·presets 값. 확인 필요: BOWL_RINSE_READY 의 z = −13.6 mm(로봇 받침면 아래)'),
}
for _tid, _e in SEOK_0920.items():
    EDIT.setdefault(_tid, {}).update(_e)

# ---------------------------------------------------------------- 9/20 17:00 PR #34(V-24 본작업) merge
V24_0920 = {
 'V-24':    dict(prog='0.6', slots=S('9/20 오후', '9/21 저녁', '9/22 오전'),
                 note_add='✅ 9/20 17:00 PR #34 merge(예정보다 빠름): motion.py 비동기 + 폴링 · cc.pause/resume/halt/clear_halt · MotionHalted·MoveTimeout · 새 키 cell.motion.move_timeout_s — Virtual rig_pause 10/10 · rig_motion 30/30 · rig_v20 probe 12/12 · pytest 185건. 🚨 **실기 미검증 → 9/21 저녁 첫 순서로 실기 확인**(빈손·HOME 근처 짧은 이동의 도착 위치 → 일시 정지·재개 → 그다음 V-22·접촉 동작) · 9/22 오전: 힘이 걸린 채 일시 정지(박진용과) · 남은 것: 시간 초과 갈래도 멈춘 것을 기다리기 · rig_force Virtual 회귀'),
 'V-22':    dict(note_add='🚨 9/21 저녁: V-24 실기 확인(짧은 이동의 도착 위치·일시 정지) **다음에** 한다 — 이동 함수가 비동기로 바뀌었다(#34). V-22 가 "도착하기 전에 함수가 돌아오는가"를 같이 잡아낸다'),
 'FLOW-03': dict(note_add='✅ 9/20 #34 merge → 연결 가능: /flow/stop·/flow/resume 콜백에서 cc.pause()·cc.resume()(깃발만 — 콜백에서 불러도 된다), 상태 발행에 cc.is_paused() 반영 · /flow/abort 는 cc.halt() 로 하던 이동을 끊고 → 정리 동작 전에 cc.clear_halt() · 기능 함수는 MotionHalted·MoveTimeout 을 잡지 말고 위로'),
 'INF-02b': dict(note_add='🚨 9/20 #34: 이동 함수가 비동기로 바뀌어 contact_down 의 걸음(move_rel)이 그 위에서 돈다 — 9/21 저녁 실기 확인 뒤에 접촉 동작. contact_down 의 자체 시간 상한(timeout_s)이 일시 정지 시간을 포함한다 → cc.is_paused() 인 동안은 세지 않게. test_common_force.py 8줄(가짜 두산에 amovel·check_motion, 시험 설정 move_timeout_s)은 황인재(F4 세션)가 #34 에서 같이 고쳤다 — main 을 먼저 받을 것'),
 'CELL-04': dict(note_add='🆕 9/20 #34: cell.motion 에 **move_timeout_s**(이동 1번의 상한 시간) 키가 생겼다 — 비면 이동 함수가 KeyError. Virtual 시험 값 30 s'),
}
for _tid, _e in V24_0920.items():
    EDIT.setdefault(_tid, {}).update(_e)

# ---------------------------------------------------------------- 9/20 17:30 PR #35(F2-01·F2-02) merge
F2_0920 = {
 'F2-01': dict(status='진행 중', prog='0.7', slots=S('9/20 오후', '9/21 저녁'),
               note_add='✅ 9/20 17:30 PR #35 merge — weigh(잔반 무게 = 측정값 − 빈 용기 기준값, 빈손이면 GRIP_FAIL)·leftover_loop·shake(WASTE) 구현 + 시험 44건(전체 229건). 값은 전부 임시 → 남은 것: **첫 실기 전에 rig_f2.py empty 로 빈 용기 기준값**, V-07·V-16 뒤 값 확정, 실기 단독 시험(9/21 저녁 — 황인재의 V-24 실기 확인 뒤에). 후속: _as_result 가 cc.MotionHalted 는 위로 올리게(FLOW-03 전)'),
 'F2-02': dict(status='진행 중', prog='0.6', slots=S('9/20 오후', '9/21 저녁'),
               note_add='✅ 9/20 17:30 PR #35 merge(예정 9/21 저녁보다 빠름) — dip(RINSE)·shake(RINSE), HOLD 적용·실패하면 쥔 채 먼저 올라온 뒤 힘 복귀·전후 폭으로 미끄러짐 판정. 남은 것: 실기(V-07: 빈 수조·vel_scale 0.3·작은 깊이부터)'),
 'FLOW-01': dict(note_add='🟡 9/20 #35: flow.policy 에 GRIP_FAIL: isolate 추가됨 — **황인재 결정 대기**(PM 권고 = pause: 용기를 놓친 경우 잔반통·수조에 남은 용기를 다음 용기가 찍을 수 있다). IRD §8·SDD §7 표 행 추가는 그 결정과 함께'),
}
for _tid, _e in F2_0920.items():
    EDIT.setdefault(_tid, {}).update(_e)

# ---------------------------------------------------------------- 9/20 17:40 황인재 결정: 한석형의 좌표를 황인재가 작업 파일로 만들어 넘긴다
HANDOFF_0920 = {
 'CELL-04': dict(owner='S(H)', slots=S('9/19 오전', '9/19 오후', '9/20 오전', '9/20 오후', '9/21 저녁'),
                 note_add='✅ 9/20 17:40 황인재 결정: **한석형이 정리한 좌표를 황인재가 받아 작업 파일(cell.yaml 등)로 만들어 넘겨준다**(파일 주인은 그대로 한석형) — 양식을 데이터에 맞춘다(종류별 자세 · 접근점+끝점 · 슬롯별 절대 자세, move_to 에 kind). 한석형: 빠진 자세(WEIGH·SOAP·ISOLATE·구역 두 번째 슬롯)만 추가로 찍고 BOWL_RINSE_READY z(−13.6) 확인. 팔레트 컵 2칸 코드 변경(5곳)도 같은 PR. 재료 정리: _upload/0920_좌표이전_작업브리프.md'),
 'V-22':    dict(note_add='9/20 17:40: 옮긴 cell.yaml 값으로 확인한다(황인재가 만든 파일) — 9/21 저녁, V-24 실기 확인 다음'),
 'F1-01':   dict(slots=S('9/21 저녁'), note_add='9/20 17:40: 좌표가 cell.yaml 에 들어온 뒤(황인재 작업 PR) — 9/20 오후 → 9/21 저녁. 한석형의 Virtual 경로 스크립트(rig_f1.py v6)는 그대로 PR 하지 않고, cc.move_to 로 같은 경로를 도는 짧은 rig 로 바꾼다'),
}
for _tid, _e in HANDOFF_0920.items():
    EDIT.setdefault(_tid, {}).update(_e)

# ---------------------------------------------------------------- 9/20 16:30 황인재 결정 E6: 그릇 닦기 = 고정 좌표 방식 (벽·바닥을 힘으로 찾지 않는다)
WIPE_0920 = {
 'V-03':  dict(prog='0.9', note_add='✅ 9/20 16:30 황인재 결정(E6): 검증 질문(힘제어 중 X·Y 이동)은 9/19 에 "가능"으로 답이 났다. 다만 수세미가 물러 닦는 도중에는 벽·힘을 잡을 수 없어(브랜치 커밋 56개 · 누르는 방식이 힘 → 깊이 → 띄우기 → 힘으로 한 바퀴) **닦기는 고정 좌표 방식으로 확정** — rig 다듬기는 여기서 끝. 남은 것: 시험 기록 PR(9/20 오후 회차 포함 · 판정 "가능") → 들어오면 완료'),
 'F3-02': dict(note_add='🆕 9/20 16:30 황인재 결정(E6): **고정 좌표 방식** — 시작 자세 Z 215.1 → 닦는 높이 Z 59.0(내려가는 거리 156.1 mm) · 벽 반지름 = (110 − 90) / 2 + 벽 누름 · 벽·바닥 찾기(contact_down)·목표 힘 유지(force_on) 없음 · 힘 감시는 남긴다(누르는 힘 10 N · 옆 힘 25 N → 후퇴, 힘 로그). 지금 브랜치(11:31 "나선으로 벽 찾기")는 이 방식으로 다시 맞춘다 · wipe.py 의 두산 API 직접 호출(199~211 줄)은 cobot_common 의 force.py 로 옮긴다 · 전제: 그릇이 받침에서 안 밀릴 것(SDD §5.4)'),
 'V-18':  dict(note_add='9/20 E6: 닦는 힘 기준이 "3~5 N"에서 "고정 높이로 누른 채"로 바뀜 — F3-02 첫 실기 3회 때 같이 본다(닦은 뒤 툴 자세 그대로인가)'),
}
for _tid, _e in WIPE_0920.items():
    EDIT.setdefault(_tid, {}).update(_e)

# ---------------------------------------------------------------- 9/20 16:41 PR #36 merge: 한석형 좌표 26개가 cell.yaml 에 들어왔다
PR36_0920 = {
 'CELL-04': dict(prog='0.7', note_add='✅ 9/20 16:41 PR #36 merge(황인재 F4 세션): 한석형 좌표 **26개가 cell.yaml 에 들어왔다**(값 그대로 · 기계 대조 일치 · Virtual 31번 이동 OK 51/FAIL 0 · 시험 243건). 양식 = 종류별(kind) · 용도별/슬롯(point) · 접근점+끝점, cc.move_to(station, carrying, kind, point). 🔴 **한석형에게 남은 것**: 새 자세 8개(WEIGH 그릇·컵 · SOAP 수세미·솔 · ISOLATE 그릇·컵 · 구역 슬롯 2 그릇·컵) + RACK_C2 접근점 재티칭(2.36 mm · 4.72°) + limits·motion 5개·presets 값 — 🚨 limits·motion 이 비어 있으면 실기에서 이동 함수가 KeyError 로 돌지 않는다 → **9/21 저녁 세션 전까지**'),
 'V-22':    dict(note_add='🚨 9/20 PR #36 검토에서 추가한 확인 항목: **posj 자세 5개**(RET_B·RET_C 슬롯 1 · TOOL_SPONGE/BRUSH pick · SPONGE_BED_C regrip)는 move_to 가 안전 높이와 무관하게 **그 자세까지 관절 이동**한다(물체 옆까지 바로) → HOME 출발 · 앞 스테이션 출발 두 경로를 vel_scale 0.3 으로 한 번씩. 위험하면 그 자세를 접근점+끝점(posx)으로 다시 읽는다. 그 밖에: 팔레트 그릇 칸은 접근점 없이 직접 들어감 · TOOL_SPONGE pick 의 J6 −220° · RINSE BOWL 하강 263 mm. 전제: 한석형이 limits·motion 을 채워야 시작할 수 있다'),
 'F1-01':   dict(note_add='9/20 #36: 좌표는 들어왔다 — cc.move_to(zone, False, point=슬롯) / (…, point=\'place\') 로 부른다. handling.py 설명글이 새 양식으로 바뀌었다(코드 변경 없음)'),
 'F2-01':   dict(note_add='9/20 #36: WEIGH·WASTE·RINSE 가 종류별 자리가 됐다 → sense.py 의 _goto 가 cc.move_to(station, carrying, kind) 로 kind 를 넘겨야 한다(지금은 진짜 cell.yaml 에서 ValueError). WEIGH 자세는 아직 🔴(한석형)'),
 'F3-02':   dict(note_add='9/20 #36: 닦기 시작 = cc.move_to(\'SPONGE_BED_B\', True, point=\'wash\') — 돌려주는 높이만큼 내려가면 wash 끝점(= 닦는 높이, E6 의 Z 59.0 · 지금 값 47.0 은 한석형 티칭 → 맞춰 본다). 세제 = cc.move_to(\'SOAP\', True, \'BOWL\') (아직 🔴)'),
}
for _tid, _e in PR36_0920.items():
    EDIT.setdefault(_tid, {}).update(_e)

# ---------------------------------------------------------------- 9/20 17:00 황인재 결정 E7(이동에서 안전 높이 삭제) · E8(F1 약속에 kind)
E78_0920 = {
 'INF-02':  dict(note_add='🆕 9/20 17:00 결정 E7(한석형 요청 · 황인재 승인): **move_to 의 안전 높이 경유를 삭제** — 먼저 올라가기·안전 높이에서 멈추기를 없애고 티칭한 자세(접근점)로 직접 간다(팔레트 적재 자세가 안전 높이에서 안 나온다). 구현 = F4 세션 PR(motion.py · 시험 · rig_motion · rig_coords). safe_retreat 의 후퇴 높이(cell.limits.safe_z_mm)는 그대로'),
 'V-22':    dict(note_add='🆕 9/20 E7: 안전 높이 경유가 없어진다 → move_to 는 **앞 자리에서 다음 자리로 직접** 간다. 확인 방법을 바꾼다: 자세 하나씩이 아니라 **흐름 순서대로 구간마다**(슬롯 → WEIGH → WASTE → 스펀지 홈 → 툴 홀더 → SOAP → 닦는 자리 → 홀더 → 재파지 → RINSE → 팔레트 → HOME · 그릇 한 바퀴 + 컵 한 바퀴) vel_scale 0.3. 막히는 구간은 한석형이 접근점을 추가로 찍는다. 전제: F4 의 E7 PR 이 먼저 main 에'),
 'CELL-04': dict(note_add='9/20 E7: limits.safe_z_mm 은 이제 **접촉 동작 뒤 후퇴 높이**(safe_retreat)로만 쓴다 — 이동 경로와 무관. 닦는 자리·스펀지 홈에서 툴·용기가 그릇 밖으로 나오는 높이로 정한다(예: 닦는 자리 접근점 높이)'),
 'FLOW-01': dict(note_add='🆕 9/20 E8: F1 약속에 kind 선택 인자 — f1.move_to(station, carrying, kind=None) · f1.place(station, kind=None)(contracts·mock_f1·handling 골격은 PM 이 한 커밋으로 바꿈). 민범진: flow 의 (\'WEIGH\', \'f1\', \'move_to\', (\'WEIGH\', True)) 에 self.kind 추가 · sense.py _goto 에 kind · 시험의 가짜 cc/f1 서명'),
 'FLOW-03': dict(note_add='9/20 E7·E8: 격리로 옮길 때 f1.place(\'ISOLATE\', kind). 안전 높이 경유가 없어지므로 중단(abort) 정리 동작은 **임의 자세에서 출발**한다 → 첫 이동을 HOME(관절 이동)으로 두는 안을 PM 이 권고(황인재 확인 대기)'),
 'F1-01':   dict(note_add='9/20 E8: f1.move_to · f1.place 에 kind=None 추가됨(골격 서명은 이미 main) — 구현할 때 cc.move_to(station, carrying, kind) 로 그대로 넘긴다'),
}
for _tid, _e in E78_0920.items():
    EDIT.setdefault(_tid, {}).update(_e)

# ---------------------------------------------------------------- 9/20 17:15 PR #39·#40 merge · #37 수정 요청 · V-03 기록 main · 한석형 회신
EVE_0920 = {
 'F4-01':   dict(status='완료', prog='1.0', note_add='✅ 9/20 17:10 PR #39 merge: 새 패키지 f4_hmi — 가짜 flow(fake_state_pub, 대본 5개) + hmi_bridge(GET /api/state) + 시험 페이지, 전체 시험 260건. 후속(F4-02 에 같이): cobot_msgs 시험에 importorskip · hmi.host 0.0.0.0 은 버튼이 붙기 전에 정한다'),
 'F4-02':   dict(note_add='9/20 #39 검토: 버튼(POST /api/start·abort)이 붙으면 같은 와이파이의 누구나 시작을 누를 수 있다 → hmi.host 기본값(127.0.0.1) 또는 버튼 확인 값 중 하나를 황인재가 정한다'),
 'V-03':    dict(status='완료', prog='1.0', note_add='✅ 9/20 17:00 시험 기록이 main 에(docs/test_logs/20260919_V-03_*, 15회차 · 강의자료 근거 · 두산 모션 API 에서 배운 것) — 판정 "가능". cell.force 값은 PR #40 으로 main 에. rig PR #37 은 수정 요청 1건(probe_spiral.py: 공중에서 순응·힘제어를 켜는 조합에 해제·상한이 없다 → 파일을 빼거나 감싸기)'),
 'CELL-04': dict(note_add='9/20 17:10 한석형 회신(결정기록 E9): ① 반납 구역은 **한 자리 공급 구조**(집으면 뒤 용기가 같은 자리로) → 슬롯 2 불필요(🟡 황인재 확인 대기 · 반복 정밀도 ±3 mm 확인 요청) ② WEIGH = 픽 자세 Z +100(값 받음) ③ 툴 집기·SOAP·툴 반납은 툴·홀더 확정 뒤(날짜 요청) ④ 그릇 칸의 "랙 밖 자리"를 접근점으로 추가 ⑤ 🚨 limits·motion·presets 값은 답이 없어 다시 요청 — 9/21 저녁 전'),
 'F1-04':   dict(note_add='9/20 한석형: 팔레트에서 나올 때 랙 안에서는 직선으로 되돌아 나온 뒤(컵 = 접근점까지 · 그릇 = Y 방향으로 랙 밖) HOME 은 관절 이동 — Virtual 확인 예정. 그릇 칸 접근점(랙 밖 자리) 티칭 필요'),
}
for _tid, _e in EVE_0920.items():
    EDIT.setdefault(_tid, {}).update(_e)

# ---------------------------------------------------------------- 9/20 17:25 황인재 결정 4건(E9 확인 · E10 · E11 · E12) + PR #41 merge
DEC_0920E = {
 'F4-02':   dict(status='완료', prog='1.0', note_add='✅ 9/20 17:25 PR #41 merge: 버튼 4종(start·stop·resume·abort) + WebSocket /ws/state + 가짜 flow 의 버튼 응답(--wait-start), 전체 시험 262건. ✅ 결정 E10: **웹 화면은 이 PC 의 브라우저에서만**(hmi.host 127.0.0.1 이 최종 · 태블릿용 비밀번호 F4-02b 는 하지 않는다). 후속(F4-03 과 같이): 버튼 요청에 사용자 지정 헤더 요구(다른 웹 페이지가 몰래 POST 하는 것 막기)'),
 'CELL-04': dict(note_add='✅ 9/20 17:25 황인재 확인(E9): 반납 구역은 **내리막 공급 구조** — 꺼내면 뒤 용기가 같은 자리로 내려온다 → 구역마다 집는 자리 1개(슬롯 2 폐기). cell.yaml zones.*.slots 를 1개로 · test_config 의 "슬롯 2개" 단언 · rig_coords 의 슬롯 2 항목은 F4 세션이 좌표 갱신 PR 에서. 조건: 다음 용기가 같은 자리에 오는 반복 정밀도 ±3 mm(한석형 5회 확인)'),
 'F1-02':   dict(note_add='9/20 E9: 구역마다 집는 자리 1개(내리막 공급 구조) — 같은 자리에서 count 번 집는다. 코드는 slots 목록을 도는 그대로(목록이 1개짜리). 헛잡으면 EMPTY_ZONE'),
 'FLOW-03': dict(note_add='✅ 9/20 17:25 결정 E11: 중단(/flow/abort) 정리 순서 = **HOME 먼저** → 툴 반납 → 용기를 격리(f1.place(\'ISOLATE\', kind)) → HOME → 다음 용기. ✅ E12: **GRIP_FAIL 정책 = pause**(멈추고 사람이 확인) — params.yaml flow.policy.GRIP_FAIL: isolate → pause, 주석의 🔔(IRD·SDD 에 행이 없다)는 이제 해결됨(IRD §8 · SDD §7 에 추가)'),
 'FLOW-01': dict(note_add='9/20 E12: flow.policy.GRIP_FAIL 을 pause 로(민범진 자기 절) — IRD §8 · SDD §7 반영됨'),
}
for _tid, _e in DEC_0920E.items():
    EDIT.setdefault(_tid, {}).update(_e)

# ---------------------------------------------------------------- 9/20 18:00 저녁 취합(GitHub 기준) + 9/21 부터 재배치 — 9/20 에 못 끝난 실기 작업을 9/21 저녁·9/22 로
R21 = '9/20 저녁 취합(GitHub 기준):'
REPLAN_0921 = {
 # ── 한석형 (F1·좌표) — 9/21 저녁은 남은 티칭 + V-22, F1 실기는 9/22 부터
 'CELL-04':  dict(prog='0.8', slots=S('9/19 오전', '9/19 오후', '9/20 오전', '9/20 오후', '9/21 저녁'),
                  note_add=R21 + ' 한석형이 좌표 정리 문서를 브랜치에 올림(docs/test_logs/20260920_CELL-04_티칭좌표_한석형.md · 17:07 · PR 전) — 그릇 잡기1(접근 [529, 8, 171, 157, 180, 157])·잡기2·컵 그립·WEIGH 후보·팔레트 J 값 포함, "컵 WASTE 는 다시 확인". 남은 것(9/21 저녁 첫 1시간): ISOLATE 2 · CUP_RACK2_1 · 그릇 칸 접근점 2 · 공급 구조 반복 정밀도 5회 · 🚨 limits·motion·presets 값'),
 'CELL-04b': dict(status='진행 중', prog='0.5', slots=S('9/20 오후', '9/21 저녁', '9/22 오후'),
                  note_add=R21 + ' 스펀지 홈(place·wash·regrip)은 티칭돼 main 에 있다(#36). 남은 것 = 툴 홀더(집기·반납)·SOAP — 🚨 툴·홀더를 제작 중이라 형상 확정 뒤에 찍는다(날짜 요청함). F1-03·F3-03 이 이 좌표를 기다린다'),
 'V-19':     dict(prog='0.5', slots=S('9/20 오전', '9/20 오후', '9/21 저녁'),
                  note_add=R21 + ' Virtual 에서는 전 자세 도달(#36 rig_coords OK 51·FAIL 0). 결정 E7 로 "안전 높이 경유" 조건은 없어졌다 → 실기 확인은 V-22(흐름 순서대로 구간)와 한 세션으로'),
 'V-22':     dict(slots=S('9/21 저녁'), note_add='9/21 저녁 순서: ① V-24 실기 확인(H 30분) ② 한석형 남은 티칭(1시간) ③ V-22 구간 확인(H·S) — 전제: E7 PR merge + limits·motion 값'),
 'F1-01':    dict(slots=S('9/21 저녁'), note_add=R21 + ' F1 코드는 아직 없음(브랜치 없음) — 골격만 main. 9/21 저녁은 책상에서 move_to·일반 place 부터'),
 'F1-02':    dict(slots=S('9/21 저녁', '9/22 오전'), note_add=R21 + ' 9/21 저녁 = 코드(책상), 9/22 오전 = 실기. 집는 자리 1개(E9) · 접근점 + 그립 자세'),
 'V-14':     dict(slots=S('9/22 오전'), note_add='9/20 재배치: 9/21 저녁 → 9/22 오전(9/21 저녁 로봇은 V-24·남은 티칭·V-22·그리퍼 세션으로 찬다). 내용도 바뀜(E9): 슬롯 2개가 아니라 **같은 자리에서 연속 공급** — 집은 뒤 다음 용기가 같은 자리에 오는가 포함'),
 'F1-05':    dict(slots=S('9/22 오후')), 'V-04': dict(slots=S('9/22 오후'), note_add='9/20 재배치: 9/22 오전 → 오후(F1-02 실기가 오전으로 밀림)'),
 'V-15':     dict(slots=S('9/22 오후'), note_add='9/20 재배치: 9/22 오전 → 오후'),
 'F1-03':    dict(slots=S('9/22 오후', '9/22 저녁'), note_add='9/20 재배치: 🚨 툴·홀더 확정과 좌표(CELL-04b)가 전제 — 늦어지면 9/22 저녁으로'),
 'V-08':     dict(slots=S('9/22 오후', '9/22 저녁')),
 # ── 민범진 (F2·flow) — 9/20 의 그리퍼·무게 실기 기록이 GitHub 에 없다 → 9/21 저녁 1시간
 'V-05':     dict(slots=S('9/20 오전', '9/20 오후', '9/21 저녁'), note_add=R21 + ' 실기 결과 기록이 GitHub 에 없다 → 9/21 저녁 그리퍼 세션(1시간: V-05 → V-23 → V-01 → V-16)으로'),
 'V-23':     dict(slots=S('9/20 오전', '9/20 오후', '9/21 저녁')), 'V-01': dict(slots=S('9/20 오전', '9/20 오후', '9/21 저녁')),
 'V-02':     dict(slots=S('9/20 오전', '9/20 오후', '9/21 저녁'), note_add=R21 + ' 실기 측정 기록이 아직 없다 — WEIGH 자세(픽 자세 Z +100)가 정해졌으니 9/21 저녁 그리퍼 세션에 이어서'),
 'INF-02d':  dict(slots=S('9/19 오후', '9/20 오전', '9/20 오후', '9/21 저녁')), 'INF-02c': dict(slots=S('9/20 오전', '9/20 오후', '9/21 저녁')),
 'V-16':     dict(slots=S('9/21 저녁', '9/22 오전'), note_add='9/20 재배치: 9/20 오후 → 9/21 저녁(그리퍼 세션 끝에)·9/22 오전'),
 'V-07':     dict(slots=S('9/22 오전'), note_add='9/20 재배치: 9/20 오후 → 9/22 오전. 🔴 민범진 Virtual 실측(브랜치 42dc294): 털기 한 주기가 설정 0.60 s 보다 1.6배(0.954 s) — period_s 를 정할 때 전제로'),
 'CELL-03':  dict(prog='0.7', slots=S('9/20 오전', '9/20 오후', '9/21 저녁'), note_add=R21 + ' WASTE·RINSE 자세가 티칭됐으므로 배치는 된 것으로 보인다 — 남은 것: 고정·배치 사진·잔반 대용품(≥100 g) 선정. 컵 WASTE 좌표는 한석형이 다시 확인'),
 'F2-01':    dict(prog='0.8', slots=S('9/20 오후', '9/21 저녁', '9/22 오전'), note_add=R21 + ' 코드는 main(#35). 민범진 브랜치에 Virtual 확인 추가(16:26 · 검사 13개 통과 · PR 전): weigh·shake·dip 연속 3회, 제자리 복귀 오차 0. 남은 것: _goto 에 kind(E8) · 실기(WEIGH 자세 확정 뒤, rig_f2.py empty 부터). 참고: "move_to 가 안전 높이를 왕복해 shake 1회의 37 % 가 이동" 은 E7 로 없어진다'),
 'F2-02':    dict(prog='0.75', slots=S('9/20 오후', '9/21 저녁', '9/22 오전')),
 'UT-F2':    dict(slots=S('9/22 오후'), note_add='9/20 재배치: 9/22 오전 → 오후(V-07·V-16·F2 실기가 오전)'),
 'FLOW-01':  dict(note_add=R21 + ' 남은 것: steps 의 f1.move_to·f3.soap 에 kind(E8) · policy.GRIP_FAIL = pause(E12)'),
 'FLOW-02':  dict(slots=S('9/22 오후'), note_add='9/20 재배치: 9/22 오전 → 오후(오전은 V-07·V-16·F2 실기와 FLOW-03 에 집중)'),
 'UT-FLOW':  dict(slots=S('9/22 저녁'), note_add='9/20 재배치: 9/22 오전 → 저녁(mock 시험이라 로봇 불필요 — INT-12a 교대 사이에)'),
 # ── 박진용 (F3) — V-03 완료, F3-02 는 고정 좌표 방식으로 다시
 'INF-02b':  dict(slots=S('9/19 오후', '9/20 오전', '9/20 오후', '9/22 오전'), note_add=R21 + ' 남은 후속: safe_retreat 이 force_off 예외에도 후퇴 · contact_down 시간 상한이 일시 정지 시간을 세지 않게 · 나선·원호 공용 함수(F3-02 용) — 9/22 오전까지'),
 'F3-02':    dict(prog='0.4', slots=S('9/20 오전', '9/20 오후', '9/21 저녁', '9/22 오전'), note_add=R21 + ' 브랜치는 11:31 기준(벽 찾기) 그대로 — 고정 좌표 방식(E6)으로 다시 맞추는 일이 남음. 9/21 저녁: 코드 + 실기 연속 3회(V-18 같이) · 9/22 오전 마무리. PR #37(rig)은 probe_spiral.py 수정 요청 중'),
 'V-18':     dict(slots=S('9/20 오전', '9/20 오후', '9/21 저녁'), note_add='9/20 재배치: F3-02 실기 3회 때 같이(9/21 저녁)'),
 'V-10':     dict(slots=S('9/22 오전'), note_add='9/20 재배치: 9/21 저녁 → 9/22 오전(9/21 저녁은 F3-02 실기). 🚨 솔·홀더 확정이 전제'),
 'F3-03':    dict(slots=S('9/22 오전', '9/22 오후'), note_add='9/20 재배치: 9/21 저녁·9/22 오전 → 9/22 오전·오후. 🚨 SOAP·툴 좌표(CELL-04b)가 전제 — 늦어지면 soap 은 임시 좌표로 모션만'),
 'UT-F3':    dict(slots=S('9/22 오후', '9/22 저녁')),
 # ── 황인재 (F4·PM) — F4-01·F4-02 가 하루 앞서 끝남
 'V-13':     dict(status='진행 중', prog='0.7', slots=S('9/22 오전'), note_add=R21 + ' PR #41 에서 브라우저 시작 → 민범진 mock flow 반응 확인(1 ms · 이벤트 4건), 일시 정지·재개는 가짜 flow 로 확인. 남은 것: 실제 flow 의 PAUSED·재개 반영(FLOW-03 뒤) + 캡처'),
 'INT-4':    dict(status='진행 중', prog='0.3', note_add=R21 + ' 시작은 mock flow 와 연결 확인(#41). 일시 정지(이동 도중)·중단은 FLOW-03 이 main 에 들어온 뒤'),
 'F4-03':    dict(slots=S('9/21 저녁', '9/22 오후', '9/22 저녁', '9/24~28 오전'), note_add=R21 + ' F4-01·F4-02 가 하루 앞서 끝나 9/21 저녁부터 착수 가능. 후속: 버튼 요청에 사용자 지정 헤더'),
 'ARCH-01':  dict(status='진행 중', prog='0.6', slots=S('9/20 오후', '9/21 오전'), note_add=R21 + ' docs/images/system_architecture_pc.svg·drawio 는 최신 약속(kind 인자)까지 반영돼 있다(PM 도구로 생성). 남은 것: draw.io 다듬기·노션 업로드 — MID-01 과 같이'),
 'MID-01':   dict(note_add='🚨 9/21 14:00 중간점검(조별 30분 발표 + 30분 토론). 9/21 오전은 강의(강의 중 프로젝트 준비 금지 — 강사 노션) → **9/20 밤~9/21 아침·점심에 끝내야 한다.** 아직 시작 전 — PM 에이전트가 문서에서 초안을 뽑을 수 있다'),
 'V-24':     dict(note_add=R21 + ' E7(안전 높이 경유 삭제) 구현이 F4 브랜치에 올라옴(17:47 · PR 전) — 9/21 저녁 실기 확인은 그 코드로'),
 'REH-02':   dict(note_add='강사 노션(9/29 공지) 재확인 9/20: 오전 "통합테스트 진행" → 로봇으로 통합 디버깅 가능. 🛡 9/23 에 밀린 L4 항목(실패 주입·측정)의 예비 칸으로만 쓴다 — 새 기능은 넣지 않는다'),
}
for _tid, _e in REPLAN_0921.items():
    EDIT.setdefault(_tid, {}).update(_e)

# ---------------------------------------------------------------- 9/20 20:40 황인재 지시: 한석형의 밀린 F1 과업을 나눈다 + PR #37 merge + 중간점검은 9/21 강사 확인 뒤
SH = '🔀 9/20 20:40 분담(황인재 지시 — 한석형은 좌표 지연으로 F1 이 3칸 밀려 9/22 하루에 함수 4개·검증 5개가 몰렸다):'
SHARE_0920 = {
 'F1-01':   dict(owner='H(S)', slots=S('9/21 저녁'), note_add=SH + ' **황인재(F4 세션)가 맡는다** — cc.move_to(station, carrying, kind) 를 감싼 f1.move_to + 일반 place(접근점 → 끝점 하강 → release → 되올라오기). 로봇 없이 짤 수 있다(Virtual). 한석형은 PR 검토만'),
 'F1-03':   dict(owner='H(S)', slots=S('9/22 오후', '9/22 저녁'), note_add=SH + ' **황인재(F4 세션)가 맡는다** — tool PICK/RETURN(폭 확인 · 반납은 힘 접촉). 전제: 툴·홀더 확정(CELL-02b, 9/21 저녁) → 한석형이 홀더 좌표 티칭(CELL-04b)'),
 'V-08':    dict(owner='H(S)', slots=S('9/22 오후', '9/22 저녁'), note_add=SH + ' F1-03 과 같이 황인재가'),
 'V-19':    dict(owner='H(S)', note_add=SH + ' 실기 도달 확인은 V-22(황인재 주도)와 한 세션 — 한석형은 옆에서 접근점이 필요한 구간만 추가로 찍는다'),
 'UT-F1':   dict(owner='S(H)', note_add=SH + ' TC 중 이동·일반 놓기·툴 부분은 황인재가, 집기·안착·팔레트는 한석형이'),
 'INT-12b': dict(owner='M(S)', note_add=SH + ' 주도를 민범진(통합 실행 리더)으로 — 한석형은 rack_place 만 지원'),
 'F1-05':   dict(note_add=SH + ' 담당은 그대로 한석형(박진용 참여). 🛡 범위 방어: 먼저 **단순 놓기**(접근점 → 끝점 하강 → release, F1-01 의 일반 place 와 같은 길)로 L2 를 통과시키고, 탐색(periodic_search)·SEAT_FAIL 판정은 시간이 남으면 얹는다 — 고정 좌표 + 무른 스펀지 홈이라 단순 놓기로 들어갈 가능성이 높다(V-04 에서 확인)'),
 'F1-02':   dict(note_add=SH + ' 한석형은 **집기(F1-02) → 안착(F1-05) → 팔레트(F1-04)** 세 개에 집중한다'),
 # 황인재 쪽 자리 만들기 — F4-03 은 추석에도 할 수 있다(AGENTS 규칙 9 예외)
 'F4-03':   dict(slots=S('9/24~28 오전', '9/24~28 오후'), note_add='9/20 20:40: F1-01·F1-03 을 맡으면서 9/21 저녁·9/22 오후 칸을 비운다 — 화면은 추석(집)에서. 9/22·23 노션 업로드용 gif 는 지금 시험 페이지로 충분(NOTE-02)'),
 'ENV-03':  dict(slots=S('9/22 오전'), note_add='9/20 20:40: 9/21 저녁 → 9/22 오전(9/21 저녁은 V-24 실기 확인·V-22·F1-01)'),
 'NOTE-01': dict(note_add='9/20 20:40: PM 에이전트가 초안을 만든다(노드 구조·인터페이스 — 문서에서 뽑기) → 황인재는 확인·업로드만'),
 'SAFE-01': dict(note_add='9/20 20:40: PM 에이전트가 초안을 만든다(SDD §7·§8 에서 뽑기) → 황인재·박진용은 확인만'),
 # 중간점검 — 형식 미확정
 'MID-01':  dict(note_add='❓ 9/20 20:40 황인재: 발표를 하는지 · 제출 문서가 있는지 **확정되지 않았다** → 9/21 아침 강사에게 확인한 뒤 이 행과 MID-02 를 고친다(강사 노션에는 "조별 30분 발표, 30분 토론, 8개팀 · 조별 자체점검"만 있고 양식·제출 안내는 없다)'),
 'MID-02':  dict(note_add='❓ 9/21 아침 강사 확인 뒤 수정(형식 미확정)'),
 # PR #37
 'V-03':    dict(note_add='✅ 9/20 20:35 PR #37 merge — rig_v03(바닥 나선 + 벽면 3바퀴)이 main 에. probe_spiral.py 는 PR 에서 빠짐, 나선 중 옆 힘 검사 추가'),
}
for _tid, _e in SHARE_0920.items():
    EDIT.setdefault(_tid, {}).update(_e)

# ---------------------------------------------------------------- 9/20 21:00 PR #42 merge — E7 구현(안전 높이 경유 삭제) + 도착 확인(MoveIncomplete)
PR42_0920 = {
 'INF-02':  dict(note_add='✅ 9/20 21:00 PR #42 merge(F4 세션 · 황인재가 rig_coords 를 직접 돌려 승인): move_to 가 티칭 자세로 곧장(E7) · 🆕 도착 확인 cc.MoveIncomplete — 이동이 끝났는데 목표에서 2 mm/1° 넘게 떨어져 있으면 오류(컨트롤러가 이동을 도중에 세워도 비동기 이동은 "끝남"으로만 보인다 — Virtual 에서 HOME → RACK_C1 이 122 mm 앞에서 섬). 시험 265건'),
 'V-19':    dict(task='V-19 도달 범위·특이점 — 모든 스테이션에 **티칭 경로대로(자리에서 자리로 곧장)** 도달 가능한가', note_add='9/20 #42: 작업명에서 "안전 높이 경유" 삭제(E7)'),
 'V-22':    dict(note_add='🚨 9/20 #42: ① 짧은 이동 3~4개로 **도착 확인(2 mm/1°)이 실기에서 헛경보를 내지 않는지** 먼저 ② **HOME → RACK_C1** 직선 이동을 가장 먼저·가장 천천히 — Virtual 에서 가상 컨트롤러가 수동 모드 속도 감시를 걸고 뜬 날에 122 mm 앞에서 섰다(원인 미확정). 서면 MoveIncomplete 로 멈추는 것이 맞는 동작 — 이어 내려가지 않는지 확인, 필요하면 경유 자세를 접근점으로 추가 ③ RET_B 접근 → 그립이 수평 2.78 mm 어긋남(그릇은 벽 2 mm 파지) — 그립 자세에서 z 만 올려 접근점 재티칭 ④ RET_C 는 접근 자세가 없어 관절 이동으로 그립 자세에 곧장 들어간다'),
 'V-24':    dict(note_add='9/20 #42: E7 코드가 main 에 → 9/21 저녁 실기 확인은 이 코드로(절차서·기록 양식은 F4 세션이 9/21 낮까지)'),
 'CELL-04': dict(prog='0.85', note_add='9/20 #42: WEIGH 2(픽 자세 Z +100) · 그릇 집기(접근 + 그립) 값이 cell.yaml 에 · 구역 슬롯 1개(E9). 남은 것: ISOLATE 2 · CUP_RACK2_1 · 그릇 칸 접근점 2 · RET_B 접근점 재티칭 · 컵 집기 접근 자세 · 툴·SOAP(홀더 확정 뒤) · limits·motion·presets'),
 'F1-01':   dict(note_add='9/20 #42 merge 됨 → F4 세션이 착수(황인재 확인 뒤)'),
 'FLOW-01': dict(note_add='9/20 #42: cc.MoveIncomplete 는 잡지 말고 위로(ROBOT_ERROR → PAUSED — 재시도·이어 하강 금지)'),
}
for _tid, _e in PR42_0920.items():
    EDIT.setdefault(_tid, {}).update(_e)

# ---------------------------------------------------------------- 9/20 21:50 F1-01 Virtual 완료(실기 대기) · PR #43 보류(황인재 결정 대기)
LATE_0920 = {
 'F1-01':  dict(status='진행 중', prog='0.7', note_add='9/20 21:35 F4 세션: 구현·Virtual 확인 끝(브랜치 injae/20260920-F1-01-move-place · PR 은 황인재 승인 대기) — move_to WEIGH 3/3 · place SPONGE_BED_B/C 3/3 · 안 찍은 ISOLATE 는 움직이지 않고 KeyError. 🚨 가상 그리퍼 드라이버가 힘 명령을 몰라 **진짜 release 는 못 돌렸다** → 실기 확인 V-25(9/21 저녁)'),
 'F3-02':  dict(prog='0.6', note_add='9/20 21:34 PR #43(박진용): wipe_bowl 을 9/20 실기 14회차 절차 그대로 + 공용 함수(force.py: move_spiral·move_arc·move_periodic·compliance_on·force_release) + PM 후속 전부 반영 · 시험 309건. ⏸ **보류 — 황인재 결정 대기**: 결정 E6(고정 높이 · 벽면 힘제어 없음)과 두 군데 다르다(바닥을 힘으로 찾기 · 벽면 1.5 N). 코드에는 막는 사유 없음. 실기는 아직(9/21 저녁)'),
 'F3-03':  dict(status='진행 중', prog='0.5', note_add='9/20 21:34 PR #43 에 같이: soap(count, kind) · wipe_cup = 바닥 찾기 → 띄우기 → **Move Periodic 한 명령으로 위아래 ±15 mm + 비틀기 ±45° 동시** 5회(SR-09 의 "J6 ±180°"와 다름 — 황인재 결정 대기). 코드는 9/20 밤에 미리 작성됨 — 실기·V-10 은 일정대로 9/22 오전'),
 'INF-02b': dict(prog='0.95', note_add='9/20 PR #43 에 후속 전부 포함(safe_retreat 이 force_off 실패에도 후퇴 · contact_down 시간 상한이 일시 정지 시간을 빼고 셈 · 닦기 공용 함수) — merge 되면 완료'),
 'CELL-02b': dict(note_add='9/20 PR #43 본문(박진용): "그릇 받침 유격은 이대로 두기로 했다" → 완료 기준에서 빼 달라는 요청 — 황인재 확인 대기'),
}
for _tid, _e in LATE_0920.items():
    EDIT.setdefault(_tid, {}).update(_e)

# ---------------------------------------------------------------- 9/20 22:00 황인재 결정 E13 + PR #43·#44 merge
E13 = '✅ 9/20 밤 황인재 결정 E13(박진용 요청대로 — "직접 실기로 검증하고 확인한 사실만 얘기한 것"):'
PR43_0920 = {
 'F3-02':  dict(prog='0.8', note_add=E13 + ' 닦기 = **바닥은 contact_down 으로 찾고(시작 힘 대비 2 N) 벽면은 힘제어 1.5 N 유지** — E6 의 "고정 높이·힘제어 없음"을 정정(접촉 깊이가 실행마다 12~17 mm 로 달라 티칭 높이 하나로 못 맞춘다). 벽을 찾지 않는 것(치수로 계산)·힘 상한 10 N·옆 힘 25 N 은 그대로. PR #43 merge — 실기는 9/21 저녁'),
 'F3-03':  dict(prog='0.7', note_add=E13 + ' wipe_cup = 바닥 찾기 → 띄우기 → **Move Periodic 한 명령으로 위아래 + 비틀기 동시** → 아래쪽 끝에서 종료. SR-09 의 "J6 ±180°" 는 "툴 축 회전, 각도는 V-10 에서 확정"으로 완화. PR #43 merge — 실기·V-10 은 9/22 오전'),
 'V-10':   dict(task='V-10 컵 안쪽 솔 삽입 깊이·충돌 + 닦기 값 4개 확정(위아래 진폭·비틀기 각·주기·띄우는 양)',
                crit='정지 0 · 솔이 컵 밖으로 나오지 않음 · 컵이 딸려 올라오지 않음 · 10회 정상 · stroke_mm·twist_deg·period_s·lift_mm 확정',
                note_add=E13 + ' SR-09 가 각도를 정하지 않으므로 이 네 값이 V-10 의 산출물이다'),
 'V-03':   dict(note_add='✅ 9/20 22:00 PR #43 merge — 확정 절차가 제품 코드(wipe.py)에'),
 'INF-02b': dict(status='완료', prog='1.0', note_add='✅ 9/20 PR #43 merge 로 후속 전부 반영(safe_retreat 이 force_off 실패에도 후퇴 · contact_down 이 일시 정지 시간을 빼고 셈 · 닦기 접촉 모션 공용 함수 move_spiral·move_arc·move_periodic·compliance_on·force_release·where·motion_done) — force.py 완료'),
 'CELL-02b': dict(crit='툴을 홀더에서 10번 집고 놓아도 같은 자리 · 세척부 치수(높이·지름) 확정',
                  note_add=E13 + ' ⑤ **그릇 받침 유격은 그대로 둔다**(박진용 현장 판단) → 완료 기준에서 뺐다. 툴·홀더 확정만 남는다'),
 'F1-01':  dict(note_add='✅ 9/20 22:00 PR #44 merge(코드) — 실기 확인 V-25 뒤에 완료 처리한다'),
}
for _tid, _e in PR43_0920.items():
    EDIT.setdefault(_tid, {}).update(_e)

# ---------------------------------------------------------------- 9/20 23:00 PR #45 merge(9/21 저녁 실기 준비물) + F4 선작업 2건(PR 전)
N45 = '✅ 9/20 23:00 PR #45 merge — 9/21 저녁에 그대로 쓸 도구·절차서:'
PR45_0920 = {
 'V-24':   dict(note_add=N45 + ' rig_pause.py 에 실기 모드(--real: 진짜 cell.yaml · J1 30°·옆 80 mm 의 작은 이동 · 단계마다 Enter · vel_scale>0.3 거부 · E-Stop 확인, --carrying) · 절차서 docs/test_logs/20260921_V-24_실기_일시정지_황인재.md. 🚨 --real 경로는 아직 끝까지 돈 적이 없다(값이 비어 있어 KeyError — 맞는 동작) → **1회차를 "절차가 도는지" 보는 회차로**. press_at_s 1.5 가 이동보다 늦으면 값 조정'),
 'V-22':   dict(note_add=N45 + ' rig_coords.py 에 실기 모드(--real · 구간마다 Enter · 하강 전 재확인 · **--from N 으로 막힌 구간부터 이어서** · 끝에 오차 표 = V-22 산출물) · 절차서 20260921_V-22_V-19_좌표재현_황인재.md'),
 'V-19':   dict(note_add='9/20 #45: V-22 와 같은 도구·같은 절차서로 한 세션에서 본다(rig_coords --real 의 구간별 도달 = V-19)'),
 'V-25':   dict(note_add=N45 + ' 절차서 20260921_F1-01_실기_황인재.md — PM 요청 2가지(놓은 뒤 되올라올 때 용기를 끌지 않는가 · place_clear_mm 100 이 충분한가) 포함'),
 'F1-03':  dict(status='진행 중', prog='0.6', note_add='9/20 밤 F4 세션 선작업(브랜치 injae/20260920-F1-03-tool · **PR 전** — 황인재: "실기 검증하고 승인하겠다"): tool PICK/RETURN 구현 — PICK = grip → 폭 판정, 헛잡으면 홀더에 두고 후퇴 / RETURN = contact_down 으로 바닥 찾기, **못 찾으면 release 하지 않고** TOOL_FAIL. 새 키 f1.tool_clear_mm 100 · tool_return_depth_mm 20. 가상에서는 프리셋이 비어 "안 움직이고 KeyError" 만 확인 → 9/22 V-08 뒤에 PR'),
 'F4-02':  dict(note_add='9/20 밤 F4 세션 선작업(브랜치 injae/20260920-F4-02b-button-header · **PR 전**): 버튼 POST 에 X-PreWash 헤더 요구(없으면 403) — 9/20 PM 검토에서 요청한 것. 실제 기동으로 403/200 확인. 황인재가 9/22 INT-4·V-13 때 보고 승인'),
}
for _tid, _e in PR45_0920.items():
    EDIT.setdefault(_tid, {}).update(_e)

# ---------------------------------------------------------------- 9/21 07:45 아침 점검 — 값이 하나도 안 들어왔다 → 저녁을 시간으로 끊고 넘치는 것을 9/22 오전으로
A21 = '🔎 9/21 아침 점검:'
TIERS = ('🚨 **cell.yaml 빈 값 39개를 3단계로 나눈다**(무엇이 무엇을 막는지): '
         '**① 이동 11개** = limits 의 vel_free_pct·vel_carry_pct·safe_z_mm·timeout_s + motion 5개 → V-24·V-22·V-19·V-25 와 **모든 실기 이동**의 전제. 로봇 없이 책상에서 10분이면 채운다(스크립트 값: 관절 20 deg/s·40, 직선 60 mm/s·120). '
         '**② 그리퍼 16개** = presets BOWL·CUP·SPONGE·BRUSH → 집기(F1-02)·툴(F1-03)·V-14 의 전제. 9/21 저녁 그리퍼 세션(민범진)의 **산출물**이다. '
         '**③ 닦기 3개** = limits.contact_limit_n 2.0 + 닦는 자리 z(그릇 47→68 · 컵 156.54→128) → F3-02·F3-03 의 전제. '
         '그 밖: SOAP 2·ISOLATE 2·seat 8개는 그 기능을 돌릴 때까지만 있으면 된다')
MORNING_0921 = {
 'CELL-04':  dict(note_add=A21 + ' 밤사이 값이 **하나도 안 들어왔다**(한석형 마지막 커밋 9/20 17:07 = 좌표 정리 문서). ' + TIERS),
 'CELL-04b': dict(slots=S('9/20 오후', '9/21 저녁', '9/22 오전', '9/22 오후'),
                  note_add=A21 + ' 오늘 저녁 티칭은 1시간뿐이라 **급한 순서로 자른다** — 🔴 오늘: 툴 홀더 집기·반납 2종 + SOAP 2(툴·홀더 확정 직후 · F1-03·F3-03 이 9/22 오후에 이걸 기다린다) + 그릇 집기 접근점 재티칭(수평 2.8 mm). 🟡 9/22 오전: ISOLATE 2 · CUP_RACK2_1 · 팔레트 그릇 칸 접근점 2 · 컵 집기 접근 자세'),
 'V-24':     dict(note_add=A21 + ' 전제는 위 ①(이동 11개)뿐이다 — presets 는 필요 없다'),
 'V-22':     dict(note_add=A21 + ' 전제는 ①뿐. 안 찍은 자세(SOAP·ISOLATE)는 rig 가 건너뛴다'),
 'V-25':     dict(note_add=A21 + ' 전제는 ①. place 는 release 만 쓰므로 presets 없이도 돈다'),
 'V-05':     dict(note_add=A21 + ' 🔴 이 세션의 산출물이 **presets** 다. 저녁 슬롯이 35분뿐이라 **BOWL·CUP 의 grip_width_mm·grip_force_n·width_tol_mm 6개만** 오늘 확정한다(9/22 오전 F1-02 집기·V-14 가 이것만 기다린다) — HOLD 힘(V-16)·approach_z_mm·SPONGE·BRUSH(툴은 9/22 오후 F1-03) 와 무게(V-02)는 9/22 오전'),
 # 넘치는 것을 9/22 오전으로
 'F3-02':    dict(slots=S('9/20 오전', '9/20 오후', '9/22 오전'),
                  note_add=A21 + ' 저녁 3.5 h 에 7가지는 들어가지 않는다(합쳐 약 5 h) → **닦기 실기 3회를 9/22 오전 첫 순서로** 옮긴다. 전제는 위 ③(닦기 3개) — 그 값은 오늘 저녁 티칭 때 같이 받는다. 코드는 main 에 있으니 오늘 저녁은 책상에서 준비만'),
 'V-18':     dict(slots=S('9/20 오전', '9/20 오후', '9/22 오전'), note_add=A21 + ' F3-02 실기와 함께 9/22 오전으로'),
 'V-10':     dict(slots=S('9/22 오전', '9/22 오후'), note_add=A21 + ' F3-02 실기가 9/22 오전 앞으로 와서 V-10 은 오전 뒤~오후로 걸친다'),
}
for _tid, _e in MORNING_0921.items():
    EDIT.setdefault(_tid, {}).update(_e)

# ---------------------------------------------------------------- 9/21 08:15 황인재 지시: 좌표 작업 담당을 한석형 → 황인재(F4 세션)로 위임
DEL = '🔀 9/21 08:15 위임(황인재 — 한석형 쪽 좌표 작업이 계속 길어져서):'
DELEG_0921 = {
 'CELL-04':  dict(owner='H(S)', note_add=DEL + ' **좌표 작업 담당을 황인재(F4 세션)로.** 이미 PR #36·#42 로 해 오던 것을 공식화한다 — 파일(cell.yaml) 작업은 F4 가 한석형 확인을 기다리지 않고 진행하고, 한석형은 검토·입회. 어제까지 걸어 둔 "한석형 값이 올 때까지 넣지 말라"는 제한을 푼다. 🚨 다만 **티치펜던트로 자세를 찍는 것은 위임되지 않는다** — 로봇 앞에서 사람이 해야 한다(오늘 저녁 슬롯에서 한석형이 찍거나 황인재가 직접)'),
 'CELL-04b': dict(owner='H(S,P)', note_add=DEL + ' 스펀지 홈·툴 홀더 좌표도 같이 — 찍는 것은 로봇 앞에서, 파일에 넣는 것은 F4'),
 'V-22':     dict(note_add=DEL + ' 좌표 파일의 주인이 바뀌어도 확인 절차는 그대로(H 주도·S 입회)'),
 'F1-02':    dict(note_add=DEL + ' 한석형은 이제 **F1 함수 3개(집기·안착·팔레트)에만** 집중한다 — 좌표 파일 작업은 없다'),
}
for _tid, _e in DELEG_0921.items():
    EDIT.setdefault(_tid, {}).update(_e)

# ---------------------------------------------------------------- 9/21 08:30 황인재가 08:00 경 V-22 그릇 한 바퀴를 혼자 돌렸다 — 결함 2건
R22 = '🔬 9/21 08:00 V-22 실기(황인재 · 그릇 한 바퀴 1~17번):'
REAL_0921 = {
 'V-22':     dict(status='진행 중', prog='0.5',
                  note_add=R22 + ' ✅ **좌표 정확도는 매우 좋다 — 전부 오차 0.11~0.24 mm · 관절 0.01~0.03°**(기준 2 mm). 스펀지 홈·닦는 자리 하강도 끝점에 정확히 도달. '
                  '❌ 결함 2건(아래 CELL-04 비고) · ⚠ RET_B 접근 → 그립 어긋남은 실기 **2.91 mm**(가상 2.78 과 일치) · 컵 한 바퀴(18~33)는 오늘 저녁에'),
 'V-19':     dict(prog='0.7', note_add=R22 + ' 도달 범위는 문제없다(WASTE BOWL 도 팔 길이 683 mm / 한계 900 — 안 닿는 게 아니라 특이점)'),
 'CELL-04':  dict(prog='0.9', note_add=R22 + ' 🚨 **오늘 저녁 티칭 최우선 2건(실기에서 실제로 막힌 것)**: '
                  '**① WASTE BOWL 재티칭** — 목표 6.0 mm 앞에서 컨트롤러가 세웠다(MoveIncomplete). ry = 179° 로 **손목 특이점(180°)에서 1°** 다 → 특이점에서 떨어진 자세로 다시 찍는다. 🔔 잔반 터는 자세라 방향이 바뀌면 털기(F2)에 영향 → **한석형·민범진과 같이 정한다**. '
                  '**② 팔레트 그릇 칸(RACK_B1·B2) 접근점 2개** — 접근점이 없어 꽂은 자리에서 HOME 으로 곧장 가다가 **그리퍼가 팔레트에 걸린다**(황인재 목격). 한석형 스크립트의 "y −25 → z +200 으로 빠진다"가 좌표로 안 옮겨져 있었다. 컵 칸(C1·C2)에는 접근점이 있다. '
                  '그다음 ③ 툴 홀더 집기·반납 2종 + SOAP 2 ④ 그릇 집기 접근점 재티칭(2.91 mm). 🟡 9/22 오전: ISOLATE 2 · CUP_RACK2_1 · 컵 집기 접근'),
 'CELL-04b': dict(note_add='9/21 08:30: F4 가 **값 21개를 채웠다**(브랜치 injae/20260921-CELL-04b-limits-motion · PR 은 황인재 확인 뒤) — limits 6 · motion 5 · seat 8 · 닦는 자리 z 2(E13). '
                  '🔑 safe_z_mm = **235**(SDD 예시 150 이 아니다): E7 로 뜻이 "접촉 뒤 후퇴 높이"가 됐는데 150 이면 **컵을 닦던 솔이 컵 밖으로 안 나온다**(용기 안 바닥 33 + 컵 깊이 95 = 입구 128, 솔 95 → 223 필요). 한석형의 닦기 접근점과 같은 높이다. '
                  '🟡 presets 16개는 **비워 둔다**(F4 권고 · 황인재 확인 대기): 비면 안 움직이고(안전) 임시값이면 틀린 값으로 실기가 돈다. 오늘 저녁 V-24·V-22·V-25 는 presets 를 읽지 않는다 — 필요한 곳은 F1-02 집기·F1-03 툴(9/22)뿐'),
 'F1-04':    dict(note_add=R22 + ' 🚨 팔레트에서 빠져나오는 동작이 **좌표로 없다** — 그릇 칸 접근점 2개를 찍은 뒤 rack_place 가 release → 접근점으로 되돌아 나오게 만든다(컵 칸과 같은 방식)'),
 'V-06':     dict(note_add=R22 + ' 그릇 칸 접근점이 생긴 뒤에 본다'),
 'V-07':     dict(note_add=R22 + ' 🔔 WASTE BOWL 자세가 특이점 회피로 바뀐다 → 털기 진폭·방향을 그 자세에서 다시 본다(한석형 재티칭 때 민범진 입회)'),
 'F2-01':    dict(note_add=R22 + ' 🔔 WASTE BOWL 재티칭으로 터는 자세가 바뀔 수 있다 — 저녁 티칭에 민범진 입회'),
 'V-24':     dict(note_add='9/21 08:00: 어제 넣은 도착 확인(MoveIncomplete)이 **실기에서 실제로 결함을 잡았다** — WASTE BOWL 이 6 mm 앞에서 섰는데 예전 코드였으면 성공으로 넘어갔다. 일시 정지·재개 자체의 실기 확인은 오늘 저녁 그대로'),
}
for _tid, _e in REAL_0921.items():
    EDIT.setdefault(_tid, {}).update(_e)

# ---------------------------------------------------------------- 9/21 08:45 황인재: 좌표는 티칭·파일·확인까지 전부 F4(황인재) 전담
FULL = '🔀 9/21 08:45 전담(황인재):'
FULLDEL_0921 = {
 'CELL-04':  dict(owner='H', note_add=FULL + ' **티칭까지 포함해 좌표 작업 전부를 황인재(F4 세션)가 한다.** 08:15 위임에서 "티치펜던트 티칭은 위임 안 됨"이라 했던 것도 황인재가 직접 하는 것으로 정리 — 황인재가 로봇 앞에 있다(오늘 08:00 V-22 를 혼자 돌렸다). 한석형은 **F1 함수에만** 집중하고, 기구 배치·의도를 묻는 질문에만 답한다'),
 'CELL-04b': dict(owner='H(P)', note_add=FULL + ' 티칭도 황인재. 툴 홀더 자리는 박진용의 기구 확정(CELL-02b)과 붙어 있어 P 만 남긴다'),
 'V-19':     dict(owner='H', note_add=FULL + ' 확인도 황인재 전담(한석형 입회 불필요)'),
 'V-22':     dict(owner='H', note_add=FULL + ' 확인도 황인재 전담. 🔸 티칭과 확인을 한 사람이 하므로 **티칭 직후 그 자세를 바로 rig_coords --from 으로 확인**하는 편이 빠르다(저녁 ③④를 묶는다)'),
 'F1-02':    dict(note_add=FULL + ' 한석형은 오늘 저녁 로봇 순서가 없다 → **저녁 내내 F1-02 집기 코드**(9/22 오전 실기). 그만큼 앞당길 수 있다'),
 'F1-05':    dict(note_add=FULL + ' 한석형이 저녁에 코드를 앞당길 수 있으면 9/22 오후가 수월해진다'),
 'V-14':     dict(note_add='9/21: 집기 검증은 한석형 몫 그대로(자기 함수) — 좌표 확인(V-22·V-19)만 황인재가 전담'),
}
for _tid, _e in FULLDEL_0921.items():
    EDIT.setdefault(_tid, {}).update(_e)

# ---------------------------------------------------------------- 9/21 08:50 황인재: 일정 재분담 — 민범진·황인재에 몰린 것을 한석형(좌표가 빠져 여유)·박진용(오늘 저녁이 빔)으로
RB = '🔀 9/21 08:50 재분담(황인재):'
REBAL_0921 = {
 # ① 민범진 — 그리퍼 세션에 시간을 준다(9/20 에 못 한 것으로 보인다 · 결과 기록 없음)
 'V-05':    dict(note_add=RB + ' 오늘 저녁 그리퍼 세션을 **35분 → 60분(21:00~22:00)** 으로 늘린다 — V-25(F1-01 실기)를 9/22 오후로 빼서 만든 25분. 절차는 박진용 제안서(docs/ref/20260919_제안_RG2_폭_힘_경로.md §5)라 **박진용이 옆에서 도울 수 있다**(오늘 저녁 박진용은 툴·홀더 확정 뒤 비어 있다)'),
 'V-01':    dict(note_add=RB + ' 그리퍼 세션 60분 안에서'),
 'V-25':    dict(slots=S('9/22 오후'), note_add=RB + ' 9/21 저녁 → **9/22 오후, F1-03·V-08 바로 앞**(같은 황인재 · 같은 place/release 경로라 이어서 보면 된다). 그리퍼 세션에 시간을 주려고 옮겼다 — F1-02 실기는 f1.move_to 가 아니라 cc.move_to 를 쓰므로 V-25 를 기다리지 않는다'),
 # ② INT-12b 주도를 한석형에게 되돌린다 — 어제 옮긴 이유(좌표 작업으로 과부하)가 없어졌다
 'INT-12b': dict(owner='S(M)', note_add=RB + ' **주도를 한석형에게 되돌린다.** 9/20 밤에 민범진으로 옮긴 이유(한석형이 좌표 작업으로 과부하)가 9/21 아침 좌표 전담 이관으로 없어졌고, 지금은 민범진이 가장 무겁다. INT-12b 는 F1(재파지·적재) + F2(헹굼·물 털기)라 F1 주인이 끌고 민범진이 F2 쪽을 돕는다'),
 # ③ SAFE-01 을 박진용이 주도 — 안전 파라미터 담당이고 오늘 저녁이 비어 있다
 'SAFE-01': dict(owner='P(H)', slots=S('9/21 저녁', '9/22 오전'),
                 note_add=RB + ' **박진용이 주도한다**(안전 파라미터 담당 · 오늘 저녁 툴·홀더 확정 뒤 비어 있다). PM 에이전트가 SDD §7·§8 에서 뽑은 초안을 넘기고, 박진용이 값(힘 상한·속도·후퇴 높이 235·정지 종류 DR_QSTOP)을 확인해 완성한다 → 황인재는 노션 업로드만(NOTE-01 과 묶음). 9/22 오전 황인재 부담을 던다'),
 'CR-01':   dict(note_add=RB + ' 9/22 오전 전원 — 안전 파라미터 절은 SAFE-01 을 만든 박진용이 설명'),
 # ④ 민범진 9/22 — 오전은 로봇(실기)만, 책상 작업은 오후·저녁으로 편다
 'FLOW-03': dict(slots=S('9/22 오후'), note_add=RB + ' 9/22 오전·오후 → **오후만**. 오전은 민범진이 로봇 실기(V-07·V-16·F2)에 집중하고, 정지·재개·중단 연결(mock 으로 되는 책상 작업)은 오후에 몰아서'),
 'FLOW-02': dict(slots=S('9/22 저녁'), note_add=RB + ' 9/22 오후 → **저녁**(FLOW-03 이 오후로 와서). 기록(records.csv)·소모품 카운트는 mock 으로 되는 책상 작업 — INT-12a 교대 사이에'),
}
for _tid, _e in REBAL_0921.items():
    EDIT.setdefault(_tid, {}).update(_e)

# ---------------------------------------------------------------- 9/21 08:40 실기 — 6번 관절 163° 회전으로 케이블 꼬임 · 로봇 정지
R840 = '🔬 9/21 08:40 실기(황인재):'
J6_0921 = {
 'CELL-04':  dict(note_add=R840 + ' WASTE BOWL 을 관절 자세(posj)로 바꾸니 그 자리에는 닿았지만 다음 스펀지 홈까지 **6번 관절이 약 163° 돌아 그리퍼 케이블이 꼬여 로봇이 멈췄다**(오류 상태 — 정지 명령 무응답). posx 로 되돌렸다(F4 브랜치). 🚨 **그릇 경로의 6번 관절 값이 자세마다 제각각**(0 · −16 · −179 · −220 · −117) → 자세 사이에서 손목이 크게 돈다 → **오늘 저녁 티칭은 WASTE BOWL 한 자세가 아니라 그릇 경로 전체를 6번 관절이 이어지게 다시 찍는 일**이 된다. 1 h 20 슬롯을 넘을 수 있다 → 넘치면 컵 한 바퀴 확인(④)을 9/22 오전으로'),
 'V-22':     dict(note_add=R840 + ' 🚨 rig_coords 안전 결함 발견·수정(F4 브랜치 8ae86d2): 실기에서 이동이 실패하면 도구가 **자동으로 HOME 으로 가려 했다**(케이블이 꼬인 채 자동 이동하면 더 꼬인다 — 다행히 컨트롤러가 오류 상태라 거부). → --real 이면 **어떤 이동 실패든 그 자리에서 멈추고 사람에게 넘긴다**(--from N 으로 이어서). 이 수정이 main 에 들어간 뒤에 저녁 실기를 돌린다'),
 'V-19':     dict(note_add=R840 + ' 도달 범위가 아니라 **관절 경로**(6번 관절 연속성) 문제가 드러났다 — V-19 의 판정 항목에 "자세 사이 6번 관절 회전이 과하지 않은가"를 더한다'),
 'V-07':     dict(note_add=R840 + ' WASTE BOWL 이 경로 재티칭으로 바뀐다 — 털기 방향도 같이'),
}
for _tid, _e in J6_0921.items():
    EDIT.setdefault(_tid, {}).update(_e)

# ---------------------------------------------------------------- 9/21 08:55 프리셋의 흐름을 분명히 — 민범진이 재고 → 황인재(F4)가 cell.yaml 에 넣는다
PS = '🔧 9/21 프리셋 흐름:'
PRESET_0921 = {
 'V-16':  dict(note_add=PS + ' ~~찾은 HOLD 값은 한석형이 cell.yaml 프리셋에 반영~~ → **황인재(F4)가 반영**(9/21 좌표·cell.yaml 전담 이관). 민범진은 값을 단톡방·기록으로 넘긴다'),
 'V-01':  dict(note_add=PS + ' 이 행에서 나오는 **그릇·컵의 파지 폭(grip_width_mm)·폭 허용 오차(width_tol_mm)** 와 쥐어 본 **평소 힘(grip_force_n)** 이 cell.yaml presets 의 BOWL·CUP 값이 된다 — 오늘 저녁 그리퍼 세션에서 재고, **황인재(F4)가 cell.yaml 에 넣는다**. 내일 오전 한석형의 집기(F1-02)·V-14 가 이 값을 기다린다'),
 'CELL-04b': dict(note_add=PS + ' presets 16개는 **민범진이 재고(V-01·V-16) 황인재가 넣는다** — 그때까지 비워 둔다(권고 · 황인재 확인 대기). 수세미·솔(SPONGE·BRUSH)은 툴·홀더 확정(CELL-02b) 뒤 9/22'),
}
for _tid, _e in PRESET_0921.items():
    EDIT.setdefault(_tid, {}).update(_e)

# 황인재가 시트에서 직접 바꾼 상태는 그대로 둔다(덮어쓰지 않게 여기서 마지막에 맞춘다)
USER_SET = {'CELL-01': dict(status='완료', note_add='✅ 9/20 황인재가 시트에서 완료 처리')}
for _tid, _e in USER_SET.items():
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
LECTURE['9/24 목~9/28 월'] = ('추석 — 🚨 **교육장 닫힘**(로봇·현장 작업 불가) · 집에서 각자 하는 원격 작업만(황인재 9/20)',
                            'PPT(5장 양식)·영상 편집·대본·as-built 문서·온라인 리허설 — 전부 집에서. 필요한 자료(영상 원본·측정 결과·사진)는 **9/23 저녁 동결 때 드라이브·저장소에 올려 둔다**')
LECTURE['9/19 토 · 9/20 일'] = (LECTURE['9/19 토 · 9/20 일'][0], '9/19 구조 변경 적용 → 티칭 1차(그릇 쪽) + 공용 함수 전부 main / 9/20 오전 좌표 마무리(컵 쪽)·그리퍼·무게·힘 검증 → 오후 티칭 2차·V-22·F1-01·구현 + 함수별 TC · 발표 자료')
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
GATE['G1 리그·검증']['C'] = '티칭 1차(9/20 오전 마무리)·2차(9/20 오후), 기구 완성(✅ 9/19), 공용 함수(cobot_common: motion·gripper·force·weigh) ✅ 전부 main(9/19), 실행 뼈대 확인(V-20), 설계를 정하는 검증(V-01·02·03·05·23) 결과 확보'
GATE['G2 L1']['C'] = 'UT-F2·F3·FLOW 통과 + 녹화 (함수별 TC 는 구현 직후 바로 수행) + 코드리뷰 CR-01 · 🚨 **F1(UT-F1)은 좌표 지연으로 9/22 저녁~9/23 오전 첫 순서** · UT-F4 는 9/22 저녁'
GATE['G3 L2']['C'] = 'INT-12a·13·4 는 9/22 저녁 시작, **INT-12b 는 9/23 오전**(rack_place 가 9/22 저녁) — flow_node + use_mock. 노션 업로드는 9/22'
GATE['G4 L3']['C'] = '그릇 1개 end-to-end + HMI 3회 연속이 먼저, 컵 1개는 이어서(🛡 밀리면 컵은 1회 또는 도전 과제)'
SLOT['9/20 일'] = {'B': '1시간씩 교대: 그리퍼 세션 V-05·V-23·V-01 → V-02(M) / V-03 → V-18·F3-02(P) / **좌표 마무리 CELL-04(컵 쪽)·CELL-01 → V-19(S)** · 로봇 불필요: CELL-03 배치(M)·DSN-04·F4-00(H)',
                   'C': '1시간씩 교대: **CELL-04b 티칭 2차(S·P) → V-22(H·S) → F1-01(S)** / F3-02(P) / V-07·V-16 → F2-01(M) — 18시 마감 · 로봇 불필요: V-20 Virtual(H)·gripper.py 수정(M)·F4-01·F4-02·MID-01·ARCH-01(H)',
                   'D': '🚫 교육장 마감(주말 18시) — 일정 없음'}
SLOT['9/21 월']['D'] = '1시간씩 교대: **F1-02 pick + V-14(S)** / V-10 → F3-03(P) / F2-01·F2-02(M) · 로봇 불필요: INT-4·V-13·ENV-03·F4-02(H·M)'
SLOT['9/22 화'] = {'B': '**V-04·V-15 → F1-05 안착(S, P 참여)** / F3-03 마무리(P) / UT-F2(M) · 로봇 불필요: UT-FLOW·FLOW-02(M)·CR-01(전원)·F4-03·노션 업로드(H)',
                   'C': '**F1-03·V-08(S)** / UT-F3(P) / UT-F2 잔여(M) — G2(L1) 마감(F1 제외) · 로봇 불필요: F4-03·F4-04·NOTE-02(H)',
                   'D': '**F1-04·V-06 → UT-F1(S)** / L2: INT-12a(M·S) → INT-13(P·S)'}
SLOT['9/23 수'] = {'B': 'UT-F1 잔여 → **INT-12b(S·M)** · INT-13 잔여 — G3(L2)', 'C': 'INT-3a 그릇 e2e → INT-3b 컵 e2e · FIX-01 — G4(L3)',
                   'D': 'INT-4a 연속 처리 → INT-4b 실패 주입 · INT-4c 측정 → INT-4d 영상·동결 (G5) · 🛡 범위 방어: 4개 → 2개, 실패 주입 4종 → 2종'}
GATE['G2 L1']['C'] = 'UT-F2·F3·FLOW 통과 + 녹화 (함수별 TC 는 구현 직후 바로 수행) + 코드리뷰 CR-01 · 🚨 **F1(UT-F1)은 좌표 지연으로 9/22 저녁~9/23 오전 첫 순서** · UT-F4 는 9/23 오전(최소 범위 — 버튼·상태·연결), 전체는 추석에 mock 으로'
SLOT['9/21 월']['D'] = '🚨 **첫 순서: V-24 실기 확인(H, 30분 — 짧은 이동의 도착 위치·일시 정지·재개) → V-22(H·S)** → 1시간씩 교대: F1-02 pick + V-14(S) / V-10 → F3-03(P) / F2-01·F2-02(M) · 로봇 불필요: F4-01·F4-02·ENV-03(H·M)'
SLOT['9/22 화'] = {'B': '**V-04·V-15 → F1-05 안착(S, P 참여)** / **V-24 실기 확인 — 이동 도중 일시 정지 → 재개(H·P, 1시간)** / F3-03 마무리(P) / UT-F2(M) · 로봇 불필요: FLOW-03·UT-FLOW·FLOW-02(M)·CR-01(전원)·F4-02·V-13·노션 업로드(H)',
                   'C': '**F1-03·V-08(S)** / UT-F3(P) / UT-F2 잔여(M) — G2(L1) 마감(F1 제외) · 로봇 불필요: FLOW-03·FLOW-01 격리 마무리(M)·INT-4 flow(mock)+HMI(H·M)·F4-03(H)',
                   'D': '**F1-04·V-06 → UT-F1(S)** / L2: INT-12a(M·S) → INT-13(P·S) · 로봇 불필요: F4-03·NOTE-02 gif(H)'}
# 9/20 20:40 재배치·분담 반영(v8.3)
SLOT['9/21 월']['D'] = ('🚨 **18:30~22:00 (3.5 h) — 시간으로 끊는다**(전부 넣으면 약 5 h). ①②④⑤ 의 전제 = cell.yaml 이동 값 11개(limits 4 + motion 5). '
                        '**18:30 ① 툴·홀더 확정(P 주도·H·S)** — 이동 값 11개는 **황인재(F4)가 18:30 전에 파일에 넣는다**(9/21 위임 · 없으면 뒤가 전부 KeyError) / '
                        '**18:50 ② V-24 실기**(H · rig_pause --real, 빈손 → 용기 → 용기 3회차) / '
                        '**19:20 ③ 티칭 + 그 자리에서 확인**(H 전담, 1 h 20 — 🚨 아침에 막힌 것 먼저: **그릇 경로를 6번 관절이 이어지게 다시 찍기**(08:40 케이블 꼬임 · WASTE BOWL 특이점 포함 · M 입회 — 털기 자세가 바뀐다) → **팔레트 그릇 칸 접근점 2개** → 툴 홀더 2종 + SOAP 2 → 그릇 집기 접근점. 한 자세 찍을 때마다 rig_coords --from 으로 바로 확인) / '
                        '**20:40 ④ V-22·V-19 컵 한 바퀴**(H · 그릇 한 바퀴는 아침에 봤다 — 18~33번) / '
                        
                        '**21:00 ⑤ 그리퍼 세션**(M, **60분** · P 가 옆에서 — 🔴 먼저 **BOWL·CUP 의 폭·힘·허용 오차 6개**(V-05 → V-01, 내일 오전 집기가 기다린다), 시간이 남으면 V-23·V-16. 무게(V-02)·SPONGE·BRUSH 는 9/22 오전) · 로봇 불필요: **한석형은 저녁 내내 F1-02 집기 코드**(로봇 순서 없음) · F2 kind·GRIP_FAIL(M) · **박진용은 SAFE-01 완성 + F3-02 준비** · 🛡 밀리면 ⑤ 를 9/22 오전 첫 순서로')
SLOT['9/22 화'] = {'B': '🚨 순서: **① F3-02 닦기 3회 + V-18(P, 40분 — 어제 밀린 것)** → ② 한석형 나머지 티칭(ISOLATE 2·CUP_RACK2_1·팔레트 그릇 칸 접근점 2·컵 집기 접근) → ③ **F1-02 집기 + V-14(S)** — presets 가 어제 저녁 그리퍼 세션에서 나왔어야 한다 → ④ V-07·V-16 → F2 실기 rig_f2 empty 부터(M) · 로봇 불필요: CR-01(전원)·ENV-03·NOTE-01·SAFE-01·V-13(H)·FLOW-03(M)·INF-02b 후속(P)',
                   'C': '**V-04·V-15 → F1-05 안착(S, P 참여 — 🛡 단순 놓기부터)** / **V-25 F1-01 실기 → F1-03·V-08 툴 집기·반납(H, S 검토)** / F3-03·UT-F3(P) / UT-F2(M) · 로봇 불필요: FLOW-02·FLOW-03·FLOW-01 마무리(M)·INT-4(H·M)',
                   'D': '**F1-04·V-06 → UT-F1(S·H)** / F1-03 잔여(H) / L2: INT-12a(M·S) → INT-13(P·S) · 로봇 불필요: UT-FLOW(M)·NOTE-02 gif(H)'}
SLOT['9/23 수']['B'] = 'UT-F1 잔여(S·H) → **INT-12b(S 주도·M)** · INT-13 잔여(P·S) · UT-F4·F4-05(H) — G3(L2)'
_b, _c = LECTURE['9/24 목~9/28 월']
LECTURE['9/24 목~9/28 월'] = (_b, _c + ' · 🆕 **F4 웹 HMI**(F4-03 화면 다듬기·F4-04 기록/이력·UT-F4 전체)도 집에서 mock·fake_state_pub 로 이어 간다(황인재 9/20 — ROS 인터페이스·로봇 쪽 코드는 9/23 동결 그대로)')
RULES = {       # (A 열, B 열 글자) → (새 B, 새 C)
 ('마감', '9/22(화) 오전'): ('9/22(화) 오후', 'L1 단위기능 테스트(UT-F1·F2·F3·FLOW) 통과 — 함수별 TC 는 구현 직후 바로 수행. UT-F4 는 9/22 저녁. 미통과 기능은 범위 방어표대로 축소 · 코드리뷰(CR-01) · 노션에 노드 구조·HMI 화면·안전 자료 업로드 · GitHub 최신'),
 ('마감', '9/22(화) 저녁'): ('9/23(수) 오전', 'L2 단위기능 통합 완료 (flow_node 에서 실행, 나머지 기능은 use_mock) — 9/22 저녁 시작'),
 ('로봇', '비고 R'): ('비고 R', 'R 표시 작업은 실기 로봇 필요. 🚨 추석(9/24~28)은 교육장이 닫힌다 — 로봇·현장 작업 불가, 집에서 하는 문서·PPT·영상만. 🚨 주말(9/19·20)은 교육장이 18시에 닫는다 → 하루 2슬롯(오전·오후), 저녁 칸 없음. 평일은 3슬롯(오전·오후·저녁). 배정은 전날 브리핑에서, 로봇 1대를 1시간씩 교대. 9/24~28 불가'),
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
HISTORY11 = ['v6.0', '일정', 'CELL-04, V-19, CELL-03, CELL-01', '9/20 아침 황인재 확인: 좌표 작업은 9/20 오전에 끝낸다 · V-19 는 좌표가 끝난 뒤(9/20 오전) · CELL-03 은 9/20 오전으로 · CELL-01 은 좌표 측정과 함께 진행 중 · 티칭 자세 = 기능의 시작 자세로 확정',
             '황인재 9/20', 'S,M']
HISTORY12 = ['v6.1', '재계획', 'CELL-04b, V-22, V-20, V-16, F1-01~05, V-04·06·08·14·15, UT-F1, INT-12b, INT-3a·3b·4a, DSN-03', '좌표 작업 지연에 따른 재계획(황인재 지시): ① 9/20 오전 한석형은 좌표 마무리만 ② F1 사슬을 반 칸씩 뒤로(F1-01 9/20 오후 · F1-02 9/21 저녁 · F1-05 9/22 오전 · F1-03 9/22 오후 · F1-04·UT-F1 9/22 저녁~9/23 오전 · INT-12b 9/23 오전) ③ 한석형 몫 덜기: V-22·V-20 → 황인재 주도, V-16 민범진 단독 ④ L3·L4 는 9/23 오후·저녁, 동결 그대로 — 밀리면 범위 방어 ⑤ DSN-03 완료(B7·B11·B12 승인)',
             '황인재 9/20 (좌표 지연)', 'S,M,P,H']
HISTORY13 = ['v6.2', '일정', 'DOC-02~05, REH-01, REH-02, INT-4d', '추석(9/24~28)은 교육장이 닫힌다(황인재 9/20) — 추석 칸의 일(PPT·영상 편집·대본·문서·온라인 리허설)은 집에서 각자 하는 원격 작업으로 명시. 9/23 저녁 동결 때 영상 원본·측정 결과·사진을 드라이브·저장소에 올린다. 9/29 오전은 브링업·좌표 재현부터 다시 확인',
             '황인재 9/20', 'S,M,P,H']
HISTORY14 = ['v6.3', '확인', 'INT-4d, REH-02', '추석 동안 로봇·기구는 세팅 그대로 둘 수 있다(황인재 확인) → 9/29 오전은 재배치·재티칭 없이 좌표 재현 빠른 확인 뒤 바로 리허설',
             '황인재 9/20', 'S,M,P,H']
HISTORY15 = ['v6.4', '서식·진척', 'DSN-04, 완료 행 전체', '완료한 일은 간트 칸을 회색으로(황인재 9/20 — G6 칸과 같은 서식) — 앞으로 완료 처리하면 자동으로 회색이 된다. DSN-04 완료(contracts.py 설명 PR #21)',
             '황인재 9/20', 'H']
HISTORY16 = ['v6.5', '진척·결함', 'V-20, FLOW-01', 'V-20 Virtual 실행(PR #22): 4개 중 3개 통과 — 실행 뼈대 정상. 결함 1건: flow 의 stop 이 기능 함수 사이가 아니라 용기 사이에서만 먹는다(문서와 다름) → FLOW-01 에 수정 항목 추가(9/21 저녁 INT-4 전), 고친 뒤 rig_v20.py probe 로 재검증하면 V-20 완료',
             'PR #22 · F4 세션 보고', 'M,H']
HISTORY17 = ['v6.6', '진척', 'FLOW-01, INF-02d, V-02', '민범진 회신(9/20): stop 위치는 문서대로(단계 사이마다 정지)로 고친다 — 든 채 멈출 때 파지는 NORMAL 그대로 · gripper.py 수정은 오전 로봇 세션 전에 · V-02 도구 브랜치는 유지(끝나면 PR)',
             '민범진 회신', 'M']
HISTORY18 = ['v6.7', '진척', 'INF-02b', 'PR #23(f3 시험 파일 이름 — 이제 pytest -q src 가 제외 없이 166건)·#24(contact_down 을 시작 힘 대비 변화량으로 · force_off 끝까지 · force_check 추가) merge, TS-05(두산 오류 뒤 복구) 문서 merge',
             'PR #23·#24', 'P,S']
HISTORY19 = ['v6.8', '진척', 'V-20, FLOW-01, INF-02d', 'PR #26(민범진) merge: flow 의 stop 을 단계 사이마다 · 그리퍼 힘 기준 맞추기를 빈손 자리로만 · 그리퍼 실기 시험대 → **V-20 완료(4/4)**, FLOW-01 0.9, INF-02d 0.8. 민범진의 정지 방식 결정 요청 D1~D4 접수(황인재 결정 대기)',
             'PR #26', 'M,H']
HISTORY20 = ['v6.9', '결정', 'CELL-04, CELL-01, FLOW-02, F3-02, F4-03', '황인재 9/20: ① 팔레트 컵 칸 4 → 2(RACK_C1·C2) ② HMI 토픽 확정 — /cell/force(힘 그래프) · /cell/gripping(파지 중/아님) 신설, /cell/grip_width 삭제 — 발행은 flow_node, 9/22 오전까지 ③ HMI 정지 버튼 이름 = "일시 정지"(E-STOP 이라 부르지 않는다)',
             '황인재 9/20', 'S,M,P,H']
HISTORY21 = ['v7.0', '진척', '9/20 오전 칸의 미완료 작업 전부, F4-00, V-24', '9/20 14:50 최신화(황인재 지시): 끝나지 않은 일은 진행 중 + 9/20 오후 칸에 표시. 오늘 merge: PR #21~#24·#26·#28·#29 · TS-05 · F4-00 설계 확정(완료) · V-20 완료. V-24a 정지 가능성 시험 결과 기록(본작업은 결정 대기). 한석형 cell.yaml PR 은 아직 없음',
             '황인재 9/20 · GitHub 기록', 'S,M,P,H']
HISTORY22 = ['v7.1', '결정·재배치', 'V-24, FLOW-03(신규), F4-01~05, UT-F4, V-13, INT-4, NOTE-02, V-22', '황인재 9/20 15:30: ① 일시 정지 = **즉시 멈춤 → 재개하면 하던 동작을 이어서**(V-24 를 선택 과제에서 본작업으로 — motion.py 비동기 전환, 황인재 · 연결은 민범진 FLOW-03 신규) ② 멈춘 용기는 사람이 확인해 마저(resume) 또는 접기(/flow/abort 신설 — 격리) ③ **웹 HMI 는 추석에도 집에서 이어 간다** → F4-01·02 는 9/21 저녁~9/22 오전, F4-03 다듬기·F4-04·UT-F4 전체는 추석으로. 범위: 힘제어·접촉 구간은 그 동작을 마친 뒤 멈춤. 되돌아갈 자리: 단계 사이 정지',
             '황인재 9/20 (V-24a 시험 결과)', 'H,M,P']
HISTORY23 = ['v7.2', '결정 보류', 'V-05, V-23, V-16, INF-02d', '민범진 결정 요청(그리퍼 조작 방법 D1 힘 기준 방향 · D2 HOLD 유지): 황인재 — **검증해 보고 정한다**. 오늘 그리퍼 세션은 지금 코드 그대로, 세션에서 잴 항목을 V-05·V-23·V-16 비고에 적음. gripper.py 버그 3건은 바로 수정. PR #33(V-24a 시험 도구·기록) merge',
             '황인재 9/20 15:50', 'M']
HISTORY24 = ['v7.3', '진척', 'CELL-04', '한석형 브랜치 확인: 좌표 약 25개는 티칭됨(스크립트 안 상수) → cell.yaml 로 옮기는 일이 남음. 늦어진 원인 = cell.yaml 골격과 실제 티칭 방식이 안 맞음 + 전체 경로 Virtual 스크립트 반복. CELL-04 진행 0.7',
             'PM 확인 9/20 16:20', 'S']
HISTORY25 = ['v7.4', '진척', 'V-24, V-22, FLOW-03, INF-02b, CELL-04', 'PR #34 merge — V-24 본작업(이동 함수 비동기 + 폴링 · pause/resume/halt)이 예정(9/21 저녁)보다 빨리 main 에 들어옴. 실기 미검증이라 **9/21 저녁 첫 순서 = V-24 실기 확인 → V-22 → 접촉 동작**. 새 키 cell.motion.move_timeout_s(한석형). FLOW-03 연결 가능',
             'PR #34', 'H,M,P,S']
HISTORY26 = ['v7.5', '진척', 'F2-01, F2-02', 'PR #35 merge — F2 기능 함수 4개(weigh·leftover_loop·shake·dip) 구현, 전체 시험 229건. 값은 임시라 실기 전에 빈 용기 기준값 측정부터. GRIP_FAIL 정책(isolate vs pause)은 황인재 결정 대기',
             'PR #35', 'M']
HISTORY27 = ['v7.6', '결정', 'CELL-04, V-22, F1-01', '황인재 9/20 17:40: 한석형이 정리한 좌표를 황인재가 작업 파일(cell.yaml 등)로 만들어 넘겨준다 — 양식을 데이터에 맞추고(종류별 자세·접근점·슬롯별 절대 자세), 한석형은 빠진 자세만 추가 티칭. F1-01 은 9/21 저녁으로',
             '황인재 9/20 17:40', 'S,H']
HISTORY28 = ['v7.7', '결정', 'V-03, F3-02, V-18', '황인재 9/20 16:30(결정기록 E6): 그릇 닦기를 고정 좌표 방식으로 — 벽 찾기 포기(반지름 고정) · 높이도 고정(Z 215.1 → 59.0) · 힘은 감시·기록만(상한 10 N · 옆 힘 25 N). 원인: 수세미가 로봇 순응보다 물러 닦는 도중에는 벽이 안 잡힌다(V-03). FR-08·SR-08·TR-05·SDD §5.4 수정. V-03 은 기록 PR 만 남음',
             '황인재 9/20 16:30', 'P']

HISTORY29 = ['v7.8', '진척·리스크', 'CELL-04, V-22, F1-01, F2-01, F3-02', 'PR #36 merge — 한석형 좌표 26개가 cell.yaml 에(양식: kind · point · 접근점+끝점, cc.move_to 인자 2개 추가, 팔레트 컵 2칸 5곳). 🚨 리스크: 한석형의 새 자세 8개 + limits·motion·presets 가 9/21 저녁 세션 전에 없으면 실기 이동 불가. V-22 에 posj 자세 5개의 경로 확인 추가',
             'PR #36 · PM 검토', 'S,M,P,H']

HISTORY30 = ['v7.9', '결정·인터페이스', 'INF-02, V-22, CELL-04, FLOW-01, FLOW-03, F1-01', '황인재 9/20 17:00: ① E7 이동에서 안전 높이 경유 삭제(한석형 요청 — 팔레트 적재 자세가 안 나온다) → move_to 는 티칭한 접근점으로 직접, V-22 는 흐름 순서대로 구간 확인, 구현은 F4 세션 PR ② E8 F1 약속에 kind 선택 인자(move_to · place) — contracts·mock_f1·handling 골격 반영, flow·sense 호출부는 민범진',
             '황인재 9/20 17:00', 'S,M,P,H']

HISTORY31 = ['v8.0', '진척', 'F4-01, V-03, CELL-04, F1-04, F4-02', '9/20 17:15: PR #39(F4-01 HMI 뼈대)·#40(cell.force 값) merge → F4-01·V-03 완료. #37(V-03 rig)은 수정 요청 1건. 한석형 회신(E9): 반납 구역은 한 자리 공급 구조 · WEIGH = 픽 +100 · 툴 좌표는 홀더 확정 뒤 · limits·motion·presets 재요청. E7 확인: 후퇴 높이는 남기고 안전 높이는 없앤다',
             'PR #39·#40 · 한석형 회신 · 황인재 9/20 17:10', 'S,M,P,H']

HISTORY32 = ['v8.1', '결정', 'F4-02, CELL-04, F1-02, FLOW-03, FLOW-01', '황인재 9/20 17:25: E9 확인(반납 구역 = 내리막 공급 구조 → 집는 자리 1개) · E10 웹 화면은 이 PC 에서만 · E11 중단의 첫 이동은 HOME · E12 GRIP_FAIL = pause. PR #41(F4-02 버튼·WebSocket) merge → F4-02 완료. FR-02·IRD §2·§6·§8 · SDD §5.2·§7 반영',
             '황인재 9/20 17:25 · PR #41', 'S,M,H']

HISTORY33 = ['v8.2', '진척·재배치', 'CELL-04·04b, V-19·22, F1-01~05, V-14·04·15·08, V-05·23·01·02·16·07, F2-01·02, UT-F2, F3-02·03, V-18·10, UT-F3, V-13, INT-4, F4-03, ARCH-01, MID-01', '9/20 저녁 취합(GitHub 기준) + 9/21 부터 재배치. 9/20 에 못 끝난 실기(그리퍼·무게 세션 · F3-02 고정 좌표 · 남은 티칭)를 9/21 저녁으로 → F1-02 실기·V-14·V-10 은 9/22 오전, F1-05·V-04·V-15·UT-F2 는 9/22 오후로 한 칸씩. F4-01·02 가 하루 앞서 끝나 F4-03 을 9/21 저녁부터. 강사 노션 재확인 — 일정 변동 없음(9/21 오후 중간점검 · 9/29 오전 통합테스트·14시 시연 · 9/30 11시 발표). 🚨 위험: F1 은 코드가 아직 없다 / 툴·홀더 미확정 / MID-01 미착수',
             'GitHub 9/20 17:50 · 강사 노션', 'S,M,P,H']

HISTORY34 = ['v8.3', '분담', 'F1-01, F1-03, V-08, V-19, UT-F1, INT-12b, F1-05, F4-03, ENV-03, NOTE-01, SAFE-01, MID-01·02', '황인재 9/20 20:40: 한석형의 밀린 F1 과업 분담 — F1-01(이동·일반 놓기)·F1-03(툴 집기·반납)+V-08 → 황인재(F4 세션, 한석형 검토) · V-19 실기 확인은 V-22 와 한 세션(황인재 주도) · INT-12b 주도 → 민범진 · 한석형은 집기·안착·팔레트 3개에 집중(🛡 안착은 단순 놓기부터). 황인재 자리: F4-03 은 추석으로, ENV-03 은 9/22 오전, NOTE-01·SAFE-01 초안은 PM 에이전트. 중간점검(MID-01·02)은 9/21 강사 확인 뒤 수정. PR #37 merge',
             '황인재 9/20 20:40', 'S,H,M,P']

HISTORY35 = ['v8.4', '진척', 'INF-02, V-19, V-22, V-24, CELL-04, F1-01, FLOW-01', 'PR #42 merge(9/20 21:00): E7 구현 — move_to 가 티칭 자세로 곧장 + 도착 확인 cc.MoveIncomplete(이동이 도중에 서면 오류) · WEIGH·그릇 집기(접근+그립) 값 · 구역 슬롯 1개(E9). V-22 확인 항목 추가(도착 확인 헛경보 · HOME → RACK_C1 구간 · RET_B 접근점 어긋남). SDD §3.1 · AGENTS §1 · 할일 시트 쉬운 말 3곳(V-24·V-19·F4-02) 정리',
             'PR #42 · PM 검토', 'S,M,H']

HISTORY36 = ['v8.5', '진척·신규', 'V-25(신규), F1-01, F3-02, F3-03, INF-02b, CELL-02b', '9/20 21:50: F1-01 구현·Virtual 확인 끝(F4 세션) → 황인재 지시로 **실기 확인 V-25 신설**(9/21 저녁, V-22 바로 뒤). PR #43(박진용 F3-02·F3-03)은 코드에 막는 사유가 없지만 결정 E6·SR-09 와 다른 곳이 있어 **황인재 결정 대기로 보류**',
             '황인재 9/20 21:30 · PR #43', 'H,S,P']

HISTORY37 = ['v8.6', '결정·진척', 'F3-02, F3-03, V-10, V-03, INF-02b, CELL-02b, F1-01', '황인재 결정 E13(9/20 밤): 닦기는 바닥을 contact_down 으로 찾고 벽면은 힘제어 1.5 N — E6 의 고정 높이를 정정(박진용 실기 근거) · wipe_cup 은 Move Periodic 동시 왕복 · SR-09 각도 완화 · 그릇 받침 유격은 그대로. PR #43(F3-02·F3-03)·#44(F1-01) merge. FR-08·SR-08·SR-09 · SDD §3.1·§4.3·§5.4·§8 · TC-06·07 반영',
             '황인재 9/20 22:00 · PR #43·#44', 'P,S,H']

HISTORY38 = ['v8.7', '진척', 'V-24, V-22, V-19, V-25, F1-03, F4-02', 'PR #45 merge(9/20 23:00): 9/21 저녁 실기 준비물 — rig_pause·rig_coords 실기 모드(작은 이동 · 단계마다 Enter · vel_scale 0.3 상한 · E-Stop 확인 · --from 으로 이어서) + 절차서·기록 양식 3종. F4 선작업 2건은 PR 전(F1-03 툴 집기·반납 · F4-02b 버튼 헤더) — 황인재가 실기에서 보고 승인',
             'PR #45 · F4 세션', 'H']

HISTORY39 = ['v8.8', '재배치', 'CELL-04, CELL-04b, V-24, V-22, V-25, V-05, F3-02, V-18, V-10, 로봇 슬롯', '9/21 아침 점검: 한석형 값이 밤사이 하나도 안 들어왔다 → ① cell.yaml 빈 값 39개를 3단계로 나눔(이동 11 / 그리퍼 16 = 오늘 저녁 세션 산출물 / 닦기 3) ② 저녁 3.5 h 에 7가지(약 5 h)는 안 들어가 **시간으로 끊고** 박진용 닦기 실기·V-18 을 9/22 오전 첫 순서로 ③ 오늘 저녁 티칭은 툴 홀더·SOAP·그릇 접근점만, 나머지는 9/22 오전',
             'PM 9/21 07:45', 'S,M,P,H']

HISTORY40 = ['v8.9', '위임', 'CELL-04, CELL-04b, V-22, F1-02', '황인재 9/21 08:15: 좌표 작업 담당을 한석형 → 황인재(F4 세션)로 위임 — 한석형 쪽이 계속 길어져서. cell.yaml 파일 작업은 F4 가 기다리지 않고 진행(어제의 "값이 올 때까지 넣지 말라" 제한 해제) · 티치펜던트 티칭은 위임되지 않음(로봇 앞에서 사람이) · 한석형은 F1 함수 3개에 집중',
             '황인재 9/21 08:15', 'S,H']

HISTORY41 = ['v9.0', '실기 결과', 'V-22, V-19, CELL-04, CELL-04b, F1-04, V-06, V-07, F2-01, V-24', '황인재 9/21 08:00 V-22 그릇 한 바퀴 실기: ✅ 좌표 정확도 0.11~0.24 mm(기준 2 mm) · ❌ WASTE BOWL 이 손목 특이점(ry 179°)으로 6 mm 앞에서 멈춤 → 재티칭(털기 자세 영향, 민범진 입회) · ❌ 팔레트 그릇 칸에 접근점이 없어 그리퍼가 팔레트에 걸림 → 접근점 2개. 두 건을 저녁 티칭 최우선으로. F4 가 값 21개를 채움(safe_z_mm 235 — 솔이 컵 밖으로 나오는 높이) · presets 16개는 비워 두는 안(황인재 확인 대기)',
             '황인재 실기 · F4 세션 9/21 08:30', 'S,M,H']

HISTORY42 = ['v9.1', '전담', 'CELL-04, CELL-04b, V-19, V-22, F1-02, F1-05, V-14', '황인재 9/21 08:45: 좌표는 **티칭·파일·확인까지 전부 황인재(F4 세션) 전담** — 08:15 위임에서 남겨 뒀던 티치펜던트 티칭도 포함. 한석형은 F1 함수에만 집중(오늘 저녁 로봇 순서 없음 → F1-02 코드를 앞당긴다). 저녁 ③④를 묶어 티칭 직후 그 자세를 바로 확인',
             '황인재 9/21 08:45', 'S,H']

HISTORY43 = ['v9.2', '재분담', 'V-05, V-01, V-25, INT-12b, SAFE-01, CR-01, 로봇 슬롯', '황인재 9/21 08:50 재분담 — 민범진·황인재에 몰린 것을 옮김: ① 그리퍼 세션 35 → 60분(V-25 F1-01 실기를 9/22 오후 F1-03 앞으로 빼서) · 박진용이 옆에서(절차 제안서 작성자) ② INT-12b 주도를 한석형에게 되돌림(좌표가 빠져 여유가 생겼다) ③ SAFE-01 을 박진용이 주도(안전 파라미터 담당 · 오늘 저녁이 비어 있다)',
             '황인재 9/21 08:50', 'S,M,P,H']

HISTORY44 = ['v9.3', '실기 결과', 'CELL-04, V-22, V-19, V-07, 로봇 슬롯', '황인재 9/21 08:40 실기: WASTE BOWL 을 관절 자세로 바꾸자 다음 자리로 가며 6번 관절이 163° 돌아 케이블이 꼬여 로봇 정지 → 그릇 경로 6번 관절 값이 제각각(0·−16·−179·−220·−117) → 오늘 저녁 티칭 = 그릇 경로를 6번 관절이 이어지게 다시 찍기(넘치면 컵 확인을 9/22 오전). rig_coords 가 실기 실패 뒤 자동으로 HOME 가려던 안전 결함을 F4 가 발견·수정(브랜치)',
             '황인재 실기 9/21 08:40', 'H,M']

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
        if 'status' in e and tl.text(r, 'F').strip() != '완료':   # 시트에서 이미 완료인 행은 되돌리지 않는다(황인재가 직접 완료 처리한 것 보호)
            r.set('F', e['status'])
        if 'prog' in e and tl.text(r, 'F').strip() != '완료': r.set('E', e['prog'])
        if 'slots' in e:
            try: set_slots(r, e['slots'])
            except ValueError:                           # 색 칸이 하나도 없는 행(이미 비운 행 · 보류였던 행)
                if e['slots']: _paint_like_neighbor(tl, r, e['slots'])
        if has(d, 'A', tid):
            q = d.rows[d.find('A', tid)]
            for c, k in (('C', 'task'), ('D', 'owner'), ('E', 'deliv'), ('F', 'crit'), ('G', 'note')):
                if k in e: q.set(c, e[k])
            if 'note_add' in e and e['note_add'] not in d.text(q, 'G'):     # 진척 메모는 앞에 덧붙인다(여러 번 돌려도 한 번만)
                q.set('G', e['note_add'] + ' · ' + d.text(q, 'G'))
    # 3) 완료 행은 진행 1.0 + **간트 칸을 회색으로**(황인재 9/20: G6 칸처럼 — 완료한 일은 회색). PM 이 시트에서 완료로 바꾼 행 포함
    gray = tl.rows[tl.find(ID, 'DOC-01a')].style('G')          # G6 = 회색 칸의 서식(내보낼 때마다 번호가 달라져서 매번 찾는다)
    ocols = open_gantt_cols()                                  # 닫힌 칸(주말 저녁 열 배경)은 건드리지 않는다
    for r in tl.rows:
        if tl.text(r, 'F').strip() == '완료' and tl.text(r, ID).strip():
            r.set('E', '1.0')
            styles = [r.style(c) for c in ocols if r.style(c) is not None]
            if not styles: continue
            blank = max(set(styles), key=styles.count)
            for c in ocols:
                if r.style(c) not in (None, blank, gray): r.set(c, style=gray)
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
    for hist in (HISTORY, HISTORY2, HISTORY3, HISTORY4, HISTORY5, HISTORY6, HISTORY7, HISTORY8, HISTORY9, HISTORY10, HISTORY11, HISTORY12, HISTORY13, HISTORY14, HISTORY15, HISTORY16, HISTORY17, HISTORY18, HISTORY19, HISTORY20, HISTORY21, HISTORY22, HISTORY23, HISTORY24, HISTORY25, HISTORY26, HISTORY27, HISTORY28, HISTORY29, HISTORY30, HISTORY31, HISTORY32, HISTORY33, HISTORY34, HISTORY35, HISTORY36, HISTORY37, HISTORY38, HISTORY39, HISTORY40, HISTORY41, HISTORY42, HISTORY43, HISTORY44):
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


def _paint_like_neighbor(tl, row, slots):
    """색 칸이 하나도 없는 행(보류였던 행 등)에 칸을 칠한다 — 색은 가까운 이웃 행의 작업 칸 색을 빌린다(회색 = 완료 색은 빼고)."""
    ocols = open_gantt_cols()
    styles = [row.style(c) for c in ocols if row.style(c) is not None]
    blank = max(set(styles), key=styles.count)
    gray = tl.rows[tl.find(ID, 'DOC-01a')].style('G')
    i = tl.rows.index(row)
    near = [j for d in range(1, 20) for j in (i - d, i + d) if 0 <= j < len(tl.rows)]
    donor = next((tl.rows[j].style(c) for j in near for c in ocols
                  if tl.rows[j].style(c) not in (None, blank, gray)), None)
    if donor is None:
        raise ValueError('이웃 행에도 색 칸이 없다')
    for d, p in slots:
        row.set(gantt_col(d, p), style=donor)


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
