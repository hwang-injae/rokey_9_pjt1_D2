# -*- coding: utf-8 -*-
"""9/19 — 구조 변경(스크립트형)으로 '할 일' 자체가 달라진 부분을 일정표에 반영.
새 작업 2행(ENV-04 구조 변경 적용 · PKG-01 기능 패키지 골격), 시험·통합 방법 문구, V-24 이동, 회의 안건.
실행: python3 tools/gen/patch_20260919_tasks.py 출력.xlsx  → 구글 시트 '스프레드시트 바꾸기'. 다시 실행해도 행이 중복되지 않는다."""
import sys, os, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from xlsx_patch import Book, new_timeline_row, rebuild_todo, set_slots
from livesheet import SID, load, timeline
import gen_todo

ID = 'AH'
# id: (작업명, 담당, 상태, 산출물, 완료 기준, 비고, 칸)   None = 그대로
EDIT = {
 'INF-02': (None, None, None, None, 'Virtual에서 rig 스크립트로 move_to 연속 3회 + Ctrl+C 뒤 재실행 정상 (init PR 먼저, 나머지 함수는 이어서)',
            '🚨 9/19 오전 최우선 — PKG-01·V-20·FLOW-01·INF-04 가 전부 이 PR 을 기다린다 · 뼈대는 ts01_repro/virtual/s4_script.py · 그리퍼 폭 수신은 실기 V-01 과 함께 확인', None),
 'V-24': ('V-24 (선택) 동작 중 소프트 정지·타임아웃 — 비동기 이동(amovej/amovel) + check_motion 폴링, 메인 스레드에서만(Virtual)', None, None, None, None,
          '선택 과제: 안 되면 정지는 기능 함수 사이로만(현재 기본) · 박진용 9/19 오전 과부하로 9/20 오전으로 이동', [('9/20', '오전')]),
 'INF-04': (None, None, None, None, 'mock 런치 한 줄로 flow_node(전부 mock) + hmi 기동', '런치는 flow_node 1개 실행(use_mock 인자) → FLOW-01 메인 뼈대가 먼저 있어야 한다', None),
 'UT-F1': ('UT-F1 — TC-01·02·05·09 (rig_f1.py 로 내 함수만 단독 실행, 같은 함수 연속 3회 이상)', None, None, None, None, None, None),
 'UT-F2': ('UT-F2 — TC-03·04·08 (rig_f2.py 로 내 함수만 단독 실행, 같은 함수 연속 3회 이상)', None, None, None, None, None, None),
 'UT-F3': ('UT-F3 — TC-06·07 (rig_f3.py 로 내 함수만 단독 실행, 같은 함수 연속 3회 이상)', None, None, None, None, None, None),
 'UT-FLOW': ('UT-FLOW — TC-10 정책 · TC-12 기록 (mock 모듈) + 기능 함수 예외 주입 시 프로그램이 죽지 않고 ROBOT_ERROR→PAUSED · Ctrl+C 종료 뒤 재실행 정상', None, None, None,
             '정책대로, 4행, 예외 주입 후에도 flow_node 생존', None, None),
 'INT-12a': ('INT-12a F1+F2 — 탐색 파지→무게→털기 5회 (주도) · flow_node 에서 실행, use_mock=[f3]', None, None, None, None, None, None),
 'INT-12b': ('INT-12b F1+F2 — 재파지→헹굼→물털기→팔레트 적재 5회 (주도) · flow_node 에서 실행, use_mock=[f3]', None, None, None, None, None, None),
 'INT-13': ('INT-13 F1+F3 — 안착 놓기→툴→세제→닦기→반납 5회 (주도) · flow_node 에서 실행, use_mock=[f2]', None, None, None, None, None, None),
 'DSN-03': ('2차 회의 — 반납 구역 방식(V-01·V-15 결과)·HMI 설계(F4-00)·실패 코드·정책·YAML 키 규칙 + 구조 변경 후속(모니터·기록 노드 추가 여부, /cell/force·/cell/grip_width 토픽, V-20 결과)', None, None, None,
            '미확정 항목 모두 결정', None, None),
 'ARCH-01': ('시스템 아키텍처 그림 — 구조 변경 반영본(노드 2·함수 모듈 3·드라이버 2) draw.io 다듬기·PC-B 안쪽 채우기 + 노션 산출물 10종 등록', None, None, None, None, None, None),
 'MID-01': (None, None, None, None, None, '구조 변경 근거 1장 포함(TS-01: 발견→재현→구조 5종 비교→결정)', None),
 'DSN-02b': (None, None, None, 'docs/meetings/20260918_결정기록_구조_인터페이스.md, IRD v3.0, SDD v3.0, 그림, 프롬프트', None, None, None),
}
NEW = [
 ('ENV-04', 'DSN-02b', 'ENV-03', '환경', '구조 변경 적용 — git pull → build·install·log 삭제 후 cbc → 작업 브랜치에 main 병합 → 에이전트에 AGENTS·IRD v3.0·SDD §3.2 재학습 · 프롬프트 파일 교체',
  '전원', '시작 전', [('9/19', '오전')], '각자 PC', 'ros2 interface list 에 cobot_msgs 가 msg 2개만 · python3 -c "import cobot_api" 성공 · 프롬프트 교체 완료', '브리핑 직후 10분 · 옛 빌드가 남으면 삭제된 서비스 타입이 계속 보인다'),
 ('PKG-01', 'INF-03', 'INF-03', '계약', '기능 패키지 골격 — 각자 패키지 생성 + cobot_api 서명 그대로의 빈 함수(F1 5개·F2 4개·F3 3개, 각 함수는 move_to 1회 뒤 Result 반환) + rig_f*.py 뼈대',
  'S,M,P', '시작 전', [('9/19', '오전')], 'handling.py · sense.py · wipe.py · test/rig_f*.py', 'cobot_api.check_api(모듈, F?Api) == [] · colcon build 성공', 'V-20 의 재료 · INF-02 init PR 과 병행 가능(빈 함수는 cobot_common 없이도 작성 가능)'),
]
PEOPLE = [('할일_한석형', 'S'), ('할일_민범진', 'M'), ('할일_박진용', 'P'), ('할일_황인재', 'H')]
EASY = {
 'ENV-04': '바뀐 구조를 내 PC에 적용한다: 저장소 받기, 옛 빌드 폴더 지우고 다시 빌드, 내 브랜치에 main 합치기, 에이전트에게 새 문서 다시 읽히기, 프롬프트 파일 새 것으로 바꾸기',
 'PKG-01': '내 패키지 뼈대를 만든다: 약속(cobot_api)에 적힌 이름·인자 그대로 빈 함수를 만들고(안에서는 한 번 이동하고 결과만 돌려줌), 내 함수만 불러 보는 시험 스크립트 rig를 만든다',
 'V-24': '(선택) 로봇이 움직이는 도중에도 정지 버튼이 먹게 한다: 이동 명령을 보낸 뒤 짧게 반복 확인하면서 정지 깃발·시간 초과를 본다(가상 로봇). 안 되면 빼도 된다',
 'UT-FLOW': 'flow 단위 테스트(TC-10 실패 규칙, TC-12 기록)를 가짜 함수로 통과시킨다. 가짜 함수가 오류를 내도 프로그램이 죽지 않고 일시정지로 가는지, Ctrl+C로 끈 뒤 다시 켜지는지도 본다',
 'INT-12a': 'F1+F2 통합: flow_node에서 F3만 가짜로 두고, 찾아서 집기→무게→털기를 5번 연속',
 'INT-12b': 'F1+F2 통합: flow_node에서 F3만 가짜로 두고, 다시 집기→헹굼→물 털기→팔레트 적재를 5번 연속',
 'INT-13': 'F1+F3 통합: flow_node에서 F2만 가짜로 두고, 안착 놓기→툴 집기→세제→닦기→툴 반납을 5번 연속',
 'ARCH-01': '새 구조로 다시 그린 아키텍처 그림을 draw.io에서 다듬고 HMI 쪽 빈칸을 채운다. 강사가 요구한 산출물 10종을 노션에 올린다',
 'DSN-03': '2차 회의: 반납 구역 방식, HMI 설계, 실패했을 때 처리 규칙, 설정 키 이름 규칙 + 구조 변경 뒤 남은 것(모니터·기록 노드를 추가할지, 힘·그리퍼 폭 토픽)',
}


def main(out):
    gen_todo.EASY.update(EASY)
    b = Book.from_live(SID)
    tl = b.sheet('Time Line'); d = b.sheet('상세(산출물·완료기준)')

    def has(sheet, col, v):
        try: sheet.find(col, v); return True
        except KeyError: return False

    for tid, (task, owner, status, deliv, crit, note, slots) in EDIT.items():
        r = tl.rows[tl.find(ID, tid)]
        if task: r.set('C', task)
        if owner: r.set('D', owner)
        if status: r.set('F', status)
        if slots: set_slots(r, slots)
        if has(d, 'A', tid):
            q = d.rows[d.find('A', tid)]
            for c, v in (('C', task), ('D', owner), ('E', deliv), ('F', crit), ('G', note)):
                if v is not None: q.set(c, v)
    for tid, after, like, cat, task, owner, status, slots, deliv, crit, note in NEW:
        if has(tl, ID, tid):
            continue
        n = new_timeline_row(tl, tl.rows[tl.find(ID, like)], slots, A=None, B=cat, C=task, D=owner, F=status, **{ID: tid})
        tl.insert(tl.find(ID, after) + 1, n)
        q = d.rows[d.find('A', after)].clone()
        for c, v in zip('ACDEFG', [tid, task, owner, deliv, crit, note]): q.set(c, v)
        d.insert(d.find('A', after) + 1, q)
    h = b.sheet('변경이력')
    if not has(h, 'A', '4.1'):
        k = h.first_empty(); n = h.rows[k - 1].clone()
        for c, v in zip('ABCDEF', ['4.1', '구조 변경 후속', 'ENV-04·PKG-01(신규), INF-02·INF-04, V-24, UT-F1~F3·UT-FLOW, INT-12a·12b·13, DSN-03, ARCH-01, MID-01',
                                   '새 작업 2행(구조 변경 적용 · 기능 패키지 골격). 단위 시험은 rig 스크립트, L2 통합은 flow_node + use_mock 으로. UT-FLOW 에 예외 주입·Ctrl+C. V-24 는 선택 과제로 9/20 오전. DSN-03 안건에 모니터·기록 노드',
                                   '구조가 바뀌면서 시험·통합 방법과 선행 관계가 달라짐. 박진용 9/19 오전 과부하', 'S,M,P,H']): n.set(c, v)
        h.rows[k] = n
    tmp = os.path.join(tempfile.mkdtemp(), 'stage.xlsx'); b.save(tmp)
    rows, det = timeline(load(tmp))
    rebuild_todo(b, lambda L: gen_todo.person_entries(rows, det, L), PEOPLE)
    b.save(out); print('->', out)


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'prewash_일정표_0919.xlsx')
