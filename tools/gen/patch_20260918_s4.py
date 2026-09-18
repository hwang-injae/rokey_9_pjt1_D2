# -*- coding: utf-8 -*-
"""9/18 저녁 구조 변경(DSN-02b: 스크립트형 — 노드 2개, 기능은 파이썬 함수) 반영.
구글 시트의 '현재' 내용에 아래 변경만 얹고, 할일_* 시트를 Time Line 에서 다시 채운다.
실행: python3 tools/gen/patch_20260918_s4.py 출력.xlsx
적용: 구글 시트 > 파일 > 가져오기 > 업로드 > '스프레드시트 바꾸기'  (내려받은 뒤 시트를 고쳤다면 다시 실행할 것)
한 번만 적용한다(두 번 실행해도 행이 중복되지는 않게 만들었다)."""
import sys, os, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from xlsx_patch import Book, new_timeline_row, rebuild_todo
from livesheet import SID, load, timeline
import gen_todo

ID = 'AH'
# id: (작업명, 담당, 상태, 산출물, 완료 기준, 비고)   None = 그대로 둔다
EDIT = {
 'INF-01b': ('cobot_msgs v3.0(srv 12개 삭제 · msg 2개) + cobot_api 신설 — 기능 함수 약속(ID·코드·Result·함수 서명)', None, '완료',
             'src/cobot_msgs, src/cobot_api', 'colcon build 2패키지 + pytest 통과, IRD v3.0 과 동일', '정본 관리 = PM'),
 'INF-02': ('cobot_common v0 — init(name)(DSR 전용 노드 + 통신 노드·그리퍼 폭 구독)·io_node·cfg·shutdown + move_to/move_rel/grip/release/weigh + config.py(로더)', None, None,
            'src/cobot_common/bootstrap.py, robot.py, config.py', 'Virtual에서 rig 스크립트로 move_to 연속 3회 + Ctrl+C 뒤 재실행 정상', '남들이 이걸로 개발 · 9/19 오전 V-20의 선행 · 뼈대는 ts01_repro/virtual/s4_script.py'),
 'INF-03': ('mock 모듈 mock_f1·mock_f3 — 실제와 같은 함수 이름·실패 주입 (M) + fake_state_pub (H)', None, None,
            'f2_sense_flow/mock/, fake_state_pub.py', 'cobot_api.check_api 통과·실패 주입, fake 상태 발행', '로봇 없이 flow·HMI 개발'),
 'INF-04': ('config 골격(cell.yaml + params.yaml 의 f1·f2·f3·flow·hmi 절) + prewash_bringup 런치 2종(flow_node 1개 실행 · use_mock 인자)', None, None, None, None, None),
 'V-20': ('V-20 실행 뼈대 확인 — cobot_common.init + flow_node 메인 뼈대 + 세 모듈의 빈 함수를 팀 코드로(Virtual). PM 시험 코드로는 9/18 확인(TS-01 §7)', 'M,P(S)', None,
          '검증 메모', '함수 번갈아 2바퀴, 모션 중 /flow/state 2 Hz, stop 수락, Ctrl+C 뒤 재실행 정상', 'INF-02 init PR 뒤 · 안 되면 구조 ③(DSN-02b 표)'),
 'V-21': ('V-21 (종료) 서비스 콜백 안 장시간 모션 — 구조 변경(DSN-02b)으로 해당 없음. 원인·재현은 TS-01', 'P', '완료', 'TS-01 기록', '—', '구조 변경으로 종료'),
 'TS-01': ('TS-01 두산 API 초기화 누락·서비스 콜백 안 로봇 명령 교착 — 원인·재현·구조 4종 Virtual 비교 → 구조 변경으로 종결(DSN-02b)', None, '완료',
           'docs/troubleshooting/TS-01_*.md, ts01_repro/', '기록 + 구조 비교 결과 + 문서 반영 merge', '박진용 발견 · PM 재현'),
 'DSN-04': ('2차 회의 결과 반영 — IRD v3.1·cobot_api·cobot_msgs·SDD', None, None, None, None, None),
 'CR-01': ('팀 코드리뷰 — 기능 모듈 3종·flow_node·HMI · 안전 파라미터·하드코딩·함수 약속(cobot_api) 일치 점검', None, None, None, None, None),
 'NOTE-01': ('노션 — ROS2 노드 구조(노드 2 + 패키지 구조)·인터페이스 정의서(ROS + 기능 함수) 업로드 (강사 9/22 요구)', None, None, None, None, None),
 'INT-3a': ('그릇 1개 end-to-end (실제 기능 3 + flow + HMI, mock 없음) 3회', None, None, None, None, None),
 'FLOW-01': ('flow_node 메인 뼈대(통신 노드·예외 보호·Ctrl+C) + 상태 머신·구역 계획(plan)·실패 정책·start/stop/resume (mock 모듈)', None, None,
             'flow_node.py, flow.py, config/params.yaml(flow 절)', None, None),
 'F1-01': (None, None, None, 'handling.py, config/cell.yaml', None, None),
 'F1-02': (None, None, None, 'handling.py pick()', None, None),
 'F1-05': ('place 안착 놓기 — 순응 하강·깊이/힘 판정·periodic_search·SEAT_FAIL', None, None, 'handling.py place()', None, None),
 'F1-03': (None, None, None, 'handling.py tool()', None, None),
 'F1-04': (None, None, None, 'handling.py rack_place()', None, None),
 'F2-01': (None, None, None, 'sense.py, config/params.yaml(f2 절)', None, None),
 'F2-02': (None, None, None, 'sense.py', None, None),
 'F3-02': (None, None, None, 'wipe.py, force_*.csv', None, None),
 'F3-03': (None, None, None, 'wipe.py', None, None),
}
# 새 행: id, 뒤에 붙일 기준 행 id, 서식 복제 행 id, 구분, 작업명, 담당, 상태, 칸, 산출물, 기준, 비고
NEW = [
 ('DSN-02b', 'TS-01', 'DSN-02', '설계', 'DSN-02b 실행 구조 변경 결정 — 노드 5개·서비스 → 스크립트형(노드 2개, f1·f2·f3는 flow_node가 부르는 파이썬 함수). 9/19 아침 브리핑에서 전원 확인',
  'H(전원)', '완료', [('9/18', '저녁')], 'docs/meetings/20260918_결정기록_구조_인터페이스.md, IRD v3.0, SDD v3.0, 그림, 프롬프트', '문서 merge + 9/19 브리핑에서 전원 확인', 'TS-01 · Virtual 구조 비교가 근거'),
 ('V-24', 'V-03', 'V-03', '검증', 'V-24 동작 중 소프트 정지·타임아웃 — 비동기 이동(amovej/amovel) + check_motion 폴링, 메인 스레드에서만(Virtual)',
  'P', '시작 전', [('9/19', '오전')], '검증 메모', '이동 중 stop → 1 s 안 정지, 이어서 다음 명령 정상', '안 되면 정지는 기능 함수 사이로만(현재 기본)'),
]
PEOPLE = [('할일_한석형', 'S'), ('할일_민범진', 'M'), ('할일_박진용', 'P'), ('할일_황인재', 'H')]


def main(out):
    b = Book.from_live(SID)
    tl = b.sheet('Time Line'); d = b.sheet('상세(산출물·완료기준)')

    def has(sheet, col, v):
        try: sheet.find(col, v); return True
        except KeyError: return False

    for tid, (task, owner, status, deliv, crit, note) in EDIT.items():
        r = tl.rows[tl.find(ID, tid)]
        if task: r.set('C', task)
        if owner: r.set('D', owner)
        if status: r.set('F', status)
        if has(d, 'A', tid):
            q = d.rows[d.find('A', tid)]
            for c, v in (('C', task), ('D', owner), ('E', deliv), ('F', crit), ('G', note)):
                if v is not None: q.set(c, v)
    for tid, after, like, cat, task, owner, status, slots, deliv, crit, note in NEW:
        if has(tl, ID, tid):
            d.rows[d.find('A', tid)].set('E', deliv)      # 이미 있는 행은 산출물 칸만 최신으로(파일명 변경 반영)
            continue
        n = new_timeline_row(tl, tl.rows[tl.find(ID, like)], slots, A=None, B=cat, C=task, D=owner, F=status, **{ID: tid})
        tl.insert(tl.find(ID, after) + 1, n)
        q = d.rows[d.find('A', after)].clone()
        for c, v in zip('ACDEFG', [tid, task, owner, deliv, crit, note]): q.set(c, v)
        d.insert(d.find('A', after) + 1, q)
    h = b.sheet('변경이력')
    if not has(h, 'A', '4.0'):
        k = h.first_empty(); n = h.rows[k - 1].clone()
        for c, v in zip('ABCDEF', ['4.0', '구조 변경', 'DSN-02b·V-24(신규), INF-01b·02·03·04, V-20·21, TS-01, FLOW-01, F1~F3 산출물, CR-01, NOTE-01, INT-3a, DSN-04',
                                   '실행 구조를 스크립트형으로: 노드 2개(flow_node·hmi_bridge), f1·f2·f3는 파이썬 함수. cobot_msgs v3.0(srv 삭제)·cobot_api 신설. V-21 종료, V-24(동작 중 소프트 정지) 추가. 날짜는 그대로',
                                   'TS-01: 두산 API는 서비스 콜백 안에서 교착. Virtual에서 구조 4종 비교 후 가장 안정적인 구조 채택(PM 결정, 9/19 브리핑 확인)', 'S,M,P,H']): n.set(c, v)
        h.rows[k] = n
    # 다른 시트의 문구
    m = b.sheet('마일스톤·로봇 슬롯')
    for r in m.rows:
        for c in list(r.cells):
            t = m.text(r, c)
            if 'cobot_msgs 배포' in t and 'cobot_api' not in t:
                r.set(c, t.replace('cobot_msgs 배포', 'cobot_msgs·cobot_api 배포'))
    # 할일_* 는 고친 Time Line 에서 다시 뽑는다
    tmp = os.path.join(tempfile.mkdtemp(), 'stage.xlsx'); b.save(tmp)
    rows, det = timeline(load(tmp))
    rebuild_todo(b, lambda L: gen_todo.person_entries(rows, det, L), PEOPLE)
    b.save(out); print('->', out)


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'prewash_일정표_구조변경반영.xlsx')
