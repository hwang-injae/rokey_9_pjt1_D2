# -*- coding: utf-8 -*-
"""9/18 TS-01(두산 API 초기화·실행기 교착) 반영 — 구글 시트의 '현재' 내용에 아래 변경만 얹는다.
실행: python3 tools/gen/patch_20260918_ts01.py 출력.xlsx
적용: 구글 시트 > 파일 > 가져오기 > 업로드 > '스프레드시트 바꾸기'  (내려받은 뒤 시트를 고쳤다면 다시 실행할 것)"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from xlsx_patch import Book
from livesheet import SID

T = dict(
 INF02_task='cobot_common v0 — init(node)·spin(node)(두산 API 초기화·실행기, TS-01) + move_to/move_rel/grip/release/weigh + config.py(로더)',
 INF02_crit='Virtual에서 서비스 콜백 안 movej 연속 3회 응답 + move_to·grip 동작',
 INF02_note='남들이 이걸로 개발 · init/spin PR이 9/19 오전 V-20과 세 노드 뼈대의 선행',
 V20_task='V-20 여러 노드의 두산 API 동시 사용 — f1·f2·f3 세 노드가 SDD §3.2 뼈대(cobot_common.init·spin)로 같은 드라이버에 번갈아 명령(Virtual, 실제 드라이버)',
 V20_crit='세 노드에서 번갈아 movej, 노드당 연속 3회 성공', V20_note='INF-02 init/spin PR 뒤 · 안 되면 로봇 명령을 한 노드로 모음', V20_owner='S,M,P',
 V21_task='V-21 flow_node 실행 구조 — 작업 스레드 + 동기 호출로 기다리는 동안 /flow/state 2 Hz·stop 수락(mock). 기능 노드 쪽 교착은 TS-01로 원인·해법 확정(9/18 박진용)',
 V21_crit='flow가 응답을 연속 3회 받고 /flow/state 2 Hz 유지, 모션 중 stop 수락', V21_note='mock · SDD §5.1 · 안 되면 액션 전환',
 TS_task='TS-01 두산 API 초기화 누락·서비스 콜백 안 로봇 명령 교착 — 원인 분석·재현·해법 확정, 문서 반영(SDD §3.2 노드 뼈대 규약)',
 TS_deliv='docs/troubleshooting/TS-01_*.md, 재현 스크립트', TS_crit='트러블슈팅 기록 + SDD·AGENTS·프롬프트 반영 merge, 팀 공지', TS_note='박진용 발견 · PM 재현. 1차 수정안은 두 번째 호출부터 멈춤 → DSR 전용 노드 분리',
)
EASY = dict(
 INF02='공용 로봇 함수 묶음(cobot_common)을 만든다. 맨 먼저 노드 시작 함수 init·spin(이게 없으면 로봇 노드가 죽거나 멈춘다, TS-01), 그다음 이동·그리퍼 잡기/놓기·무게 재기 + 설정 파일 읽는 함수. 다른 사람들이 이걸 가져다 쓴다',
 V20='f1·f2·f3 세 프로그램을 정해진 뼈대(SDD §3.2)로 만들어, 가상 로봇에 번갈아 명령을 보낸다. 프로그램마다 같은 서비스를 3번 연속 불러 본다(한 번만 부르면 결함이 안 보인다)',
 V21='flow_node가 다른 노드를 부르고 기다리는 동안에도 상태 발행(초당 2번)과 정지 버튼이 살아 있는지 가짜 노드로 확인한다. 순서 실행은 별도 스레드에서 한다(SDD §5.1)',
 TS='로봇 노드가 뜨자마자 죽거나 두 번째 호출에서 멈추는 문제(TS-01)를 기록하고, 해결 방법(노드 뼈대 규약)을 문서·프롬프트에 반영해 팀에 알린다',
)

def main(out):
    b = Book.from_live(SID)
    # ---------- Time Line ----------
    tl = b.sheet('Time Line'); ID = 'AH'
    r = tl.rows[tl.find(ID, 'INF-02')]; r.set('C', T['INF02_task'])
    i20 = tl.find(ID, 'V-20'); r = tl.rows[i20]; r.set('C', T['V20_task']); r.set('D', T['V20_owner'])
    fill, blank = r.style('I'), r.style('J')                     # 9/18 저녁(I) → 9/19 오전(J)
    if fill != blank: r.set('I', style=blank); r.set('J', style=fill)
    r = tl.rows[tl.find(ID, 'V-21')]; r.set('C', T['V21_task'])
    doc = tl.rows[tl.find(ID, 'DSN-02')]                          # 서식 복제용(문서·계약 색)
    docfill = next(doc.style(c) for c in 'GHI' if doc.style(c) != doc.style('M'))
    n = tl.rows[i20].clone()
    for c in list(n.cells):
        if c not in 'ABCDEF' and c != ID: n.set(c, style=doc.style('M'))
    n.set('B', '기록'); n.set('C', T['TS_task']); n.set('D', 'P,H'); n.set('F', '진행 중'); n.set('I', style=docfill); n.set(ID, 'TS-01')
    tl.insert(i20 + 1, n)
    # ---------- 상세 ----------
    d = b.sheet('상세(산출물·완료기준)')
    r = d.rows[d.find('A', 'INF-02')]; r.set('C', T['INF02_task']); r.set('F', T['INF02_crit']); r.set('G', T['INF02_note'])
    j = d.find('A', 'V-20'); r = d.rows[j]; r.set('C', T['V20_task']); r.set('D', T['V20_owner']); r.set('F', T['V20_crit']); r.set('G', T['V20_note'])
    r = d.rows[d.find('A', 'V-21')]; r.set('C', T['V21_task']); r.set('F', T['V21_crit']); r.set('G', T['V21_note'])
    n = d.rows[j].clone(); n.set('A', 'TS-01'); n.set('C', T['TS_task']); n.set('D', 'P,H'); n.set('E', T['TS_deliv']); n.set('F', T['TS_crit']); n.set('G', T['TS_note'])
    d.insert(j + 1, n)
    # ---------- 변경이력 ----------
    h = b.sheet('변경이력'); k = h.first_empty(); n = h.rows[k - 1].clone()
    for c, v in zip('ABCDEF', ['3.1', '변경', 'TS-01(신규), INF-02, V-20, V-21', 'TS-01 기록 행 추가 · INF-02에 init/spin 포함 · V-20을 9/19 오전으로(담당 S,M,P, 노드당 연속 3회) · V-21은 flow 실행 구조로 범위 정리',
                           '9/18 박진용 결함 보고 → PM 재현: 문서대로 구현하면 통합 실행 불가', 'S,M,P,H']): n.set(c, v)
    h.rows[k] = n
    # ---------- 할일_* (있을 때만) ----------
    def todo(name, L):
        if name not in b.paths: return
        s = b.sheet(name)
        def row_of(tid):
            try: return s.find('C', tid)
            except KeyError: return None
        def tmpl():                                             # 담당·로봇 없음·미완료 행의 서식
            for r in s.rows:
                if s.text(r, 'F') in ('담당', '공동') and not s.text(r, 'G') and s.text(r, 'J') != '완료' and s.text(r, 'C'): return r
        def set_row(r, when, tid, easy, task, role, crit, where, status):
            for c, v in zip('ABCDEFGHIJ', [when, '☐', tid, easy, task, role, '', crit, where, status]): r.set(c, v)
        i = row_of('INF-02')
        if i is not None: r = s.rows[i]; r.set('D', EASY['INF02']); r.set('E', T['INF02_task']); r.set('H', T['INF02_crit'])
        i = row_of('V-21')
        if i is not None: r = s.rows[i]; r.set('D', EASY['V21']); r.set('E', T['V21_task']); r.set('H', T['V21_crit'])
        # V-20: 9/19 오전 맨 위로
        h19 = s.find('A', '9/19', prefix=True); i = row_of('V-20')
        if L in 'SMP':
            r = s.rows.pop(i) if i is not None else tmpl().clone()
            h19 = s.find('A', '9/19', prefix=True)
            set_row(r, '오전', 'V-20', EASY['V20'], T['V20_task'], '공동', T['V20_crit'], 'docs/03_설계_SDD.md §3.2 · §9.2', '시작 전')
            s.rows.insert(h19 + 1, r)
            if i is None and s.is_empty(s.rows[-1]): s.rows.pop()
        if L in 'PH' and row_of('TS-01') is None:
            h19 = s.find('A', '9/19', prefix=True); r = tmpl().clone()
            set_row(r, '저녁', 'TS-01', EASY['TS'], T['TS_task'], '공동', T['TS_crit'], 'docs/troubleshooting/', '진행 중')
            s.insert(h19, r)
    for name, L in [('할일_한석형', 'S'), ('할일_민범진', 'M'), ('할일_박진용', 'P'), ('할일_황인재', 'H')]: todo(name, L)
    b.save(out); print('->', out)

if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'prewash_일정표_TS01반영.xlsx')
