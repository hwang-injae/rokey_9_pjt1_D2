# -*- coding: utf-8 -*-
"""구글 시트(정본)에서 내려받은 xlsx를 '그 자리에서' 고치는 도구.
PM이 시트에서 직접 고친 내용(행 추가·날짜 이동·상태)을 그대로 둔 채 몇 개 셀·행만 바꾼다.
서식은 기존 행의 스타일 번호를 복제해서 쓴다. 수식·조건부 서식이 없는 시트 전제."""
import re, io, zipfile, html, urllib.request, copy

def colnum(c):
    n=0
    for ch in c: n=n*26+ord(ch)-64
    return n

class Row:
    def __init__(s,attrs,cells): s.attrs=attrs; s.cells=cells      # cells: {col: [attr_str, inner_xml]}
    def style(s,col):
        m=re.search(r'\bs="(\d+)"',s.cells.get(col,['',''])[0]); return m.group(1) if m else None
    def set(s,col,text=None,style=None):
        st=style if style is not None else s.style(col)
        a=(f' s="{st}"' if st is not None else '')
        if text in (None,''): s.cells[col]=[a,None]
        else: s.cells[col]=[a+' t="inlineStr"',f'<is><t xml:space="preserve">{html.escape(str(text),quote=False)}</t></is>']
    def clone(s): return Row(s.attrs,copy.deepcopy(s.cells))

class Sheet:
    def __init__(s,xml,ss):
        s.ss=ss
        m=re.search(r'<sheetData>(.*)</sheetData>',xml,re.S); s.head,s.tail=xml[:m.start()],xml[m.end():]
        s.rows=[]
        for ra,body in re.findall(r'<row ([^>]*?)(?:/>|>(.*?)</row>)',m.group(1),re.S):
            cells={}
            for c in re.finditer(r'<c r="([A-Z]+)\d+"([^>]*?)(?:/>|>(.*?)</c>)',body,re.S): cells[c.group(1)]=[c.group(2).rstrip(),c.group(3)]
            s.rows.append(Row(re.sub(r'\br="\d+"\s*','',ra).strip(),cells))
        # 병합 셀은 행 객체로 기억해 두었다가 저장할 때 번호를 다시 매긴다
        s.merges=[]
        for ref in re.findall(r'<mergeCell ref="([^"]+)"/>',s.tail):
            a,b=ref.split(':'); ca,ra_=re.match(r'([A-Z]+)(\d+)',a).groups(); cb,rb=re.match(r'([A-Z]+)(\d+)',b).groups()
            s.merges.append((ca,s.rows[int(ra_)-1],cb,s.rows[int(rb)-1]))
    def text(s,row,col):
        a,inner=row.cells.get(col,['',None])
        if not inner: return ''
        if 't="s"' in a: return s.ss[int(re.search(r'<v>(\d+)</v>',inner).group(1))]
        if 'inlineStr' in a: return html.unescape(''.join(re.findall(r'<t[^>]*>(.*?)</t>',inner,re.S)))
        v=re.search(r'<v>(.*?)</v>',inner,re.S); return v.group(1) if v else ''
    def find(s,col,value,start=0,prefix=False):
        for i in range(start,len(s.rows)):
            t=s.text(s.rows[i],col).strip()
            if (t.startswith(value) if prefix else t==value): return i
        raise KeyError((col,value))
    def is_empty(s,row): return all(not inner for a,inner in row.cells.values())
    def insert(s,index,row):
        s.rows.insert(index,row)
        if s.is_empty(s.rows[-1]): s.rows.pop()          # 전체 행 수 유지
    def move(s,src,dst):
        r=s.rows.pop(src); s.rows.insert(dst if dst<src else dst-1,r)
    def first_empty(s,col='A',start=1):
        for i in range(start,len(s.rows)):
            if s.is_empty(s.rows[i]): return i
        s.rows.append(Row('',{})); return len(s.rows)-1
    def xml(s):
        idx={id(r):i+1 for i,r in enumerate(s.rows)}; out=[]
        for i,r in enumerate(s.rows):
            cs=[]
            for col in sorted(r.cells,key=colnum):
                a,inner=r.cells[col]; ref=f'{col}{i+1}'
                cs.append(f'<c r="{ref}"{(" "+a.strip()) if a.strip() else ""}/>' if not inner else f'<c r="{ref}"{(" "+a.strip()) if a.strip() else ""}>{inner}</c>')
            out.append(f'<row r="{i+1}"{(" "+r.attrs) if r.attrs else ""}>'+''.join(cs)+'</row>')
        tail=s.tail
        if s.merges:
            mc=''.join(f'<mergeCell ref="{ca}{idx[id(ra)]}:{cb}{idx[id(rb)]}"/>' for ca,ra,cb,rb in s.merges)
            tail=re.sub(r'<mergeCells[^>]*>.*?</mergeCells>',f'<mergeCells count="{len(s.merges)}">{mc}</mergeCells>',tail,flags=re.S)
        return s.head+'<sheetData>'+''.join(out)+'</sheetData>'+tail

class Book:
    def __init__(s,data):
        s.z=zipfile.ZipFile(io.BytesIO(data)); s.files={n:s.z.read(n) for n in s.z.namelist()}
        s.ss=[html.unescape(''.join(re.findall(r'<t[^>]*>(.*?)</t>',x,re.S))) for x in re.findall(r'<si>(.*?)</si>',s.files['xl/sharedStrings.xml'].decode(),re.S)]
        wb=s.files['xl/workbook.xml'].decode(); rels=s.files['xl/_rels/workbook.xml.rels'].decode()
        rmap={}
        for m in re.finditer(r'<Relationship [^>]*>',rels):
            i=re.search(r'Id="([^"]+)"',m.group(0)).group(1); t=re.search(r'Target="([^"]+)"',m.group(0)).group(1); rmap[i]='xl/'+t.replace('/xl/','').lstrip('/')
        s.paths={html.unescape(n):rmap[r] for n,r in re.findall(r'<sheet [^>]*?name="([^"]+)"[^>]*?r:id="([^"]+)"',wb)}
        s.sheets={}
    @classmethod
    def from_live(cls,sid): return cls(urllib.request.urlopen(f'https://docs.google.com/spreadsheets/d/{sid}/export?format=xlsx',timeout=40).read())
    def sheet(s,name):
        if name not in s.sheets: s.sheets[name]=Sheet(s.files[s.paths[name]].decode(),s.ss)
        return s.sheets[name]
    def save(s,out):
        for n,sh in s.sheets.items(): s.files[s.paths[n]]=sh.xml().encode()
        with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
            for n in s.z.namelist(): z.writestr(n,s.files[n])


# ---------------------------------------------------------------- 공용 도우미
GANTT = dict(zip(['9/18', '9/19', '9/20', '9/21', '9/22', '9/23', '9/24~28', '9/29', '9/30'],
                 [('G', 'H', 'I'), ('J', 'K', 'L'), ('M', 'N', 'O'), ('P', 'Q', 'R'), ('S', 'T', 'U'),
                  ('V', 'W', 'X'), ('Y', 'Z', 'AA'), ('AB', 'AC', 'AD'), ('AE', 'AF', 'AG')]))
PART = {'오전': 0, '오후': 1, '저녁': 2}
# 닫힌 칸 — 주말(9/19·20) 저녁은 교육장이 18시에 닫아 일정이 없다. 황인재가 시트에서 그 열 전체를 연분홍으로 칠해 두었다(9/19).
# 그 칠은 작업 칸이 아니라 배경이다: 색을 고를 때 보지 않고, 지우지 않고, 작업을 넣지도 않는다.
CLOSED = [('9/19', '저녁'), ('9/20', '저녁')]


def gantt_col(day, part):
    return GANTT[day][PART[part]]


def open_gantt_cols():
    """작업 칸으로 쓰는 간트 열(닫힌 칸 제외)."""
    closed = {gantt_col(d, p) for d, p in CLOSED}
    return [c for cs in GANTT.values() for c in cs if c not in closed]


def _check_open(slots):
    bad = [x for x in slots if tuple(x) in CLOSED]
    if bad:
        raise ValueError(f'닫힌 칸에는 작업을 넣지 않는다(교육장 주말 18시 마감): {bad}')


def new_timeline_row(sheet, like_row, slots, **cells):
    """like_row 의 서식을 복제해 새 Time Line 행을 만든다. slots=[('9/19','오전'), …] 칸에만 색을 칠한다."""
    _check_open(slots)
    gcols = open_gantt_cols()
    fill = next((like_row.style(c) for c in gcols if like_row.style(c) != like_row.style('AG')), None)
    blank = like_row.style('AG') if like_row.style('AG') != fill else '3'
    # AG(9/30 저녁)가 색칸인 행은 드물다. 빈칸 서식은 색이 없는 칸에서 가져온다
    styles = [like_row.style(c) for c in gcols if like_row.style(c) is not None]
    blank = max(set(styles), key=styles.count)
    fill = next((s for s in styles if s != blank), fill)
    n = like_row.clone()
    for c in gcols:
        n.set(c, style=blank)
    for d, p in slots:
        n.set(gantt_col(d, p), style=fill)
    for c, v in cells.items():
        n.set(c, v)
    return n


def rebuild_todo(book, entries_fn, people):
    """할일_* 시트를 Time Line 의 현재 내용으로 다시 채운다(시트가 있을 때만). 서식은 그 시트의 기존 행에서 복제."""
    for name, L in people:
        if name not in book.paths:
            continue
        s = book.sheet(name)
        h = s.find('A', '언제')
        body = [r for r in s.rows[h + 1:] if not s.is_empty(r)]
        tx = lambda r, c: s.text(r, c).strip()
        t_day = next(r for r in body if not tx(r, 'C') and not tx(r, 'B') and tx(r, 'A'))
        items = [r for r in body if tx(r, 'B') in ('☐', '☑')]
        pick = lambda cond: next((r for r in items if cond(r)), None)
        t_mine = pick(lambda r: tx(r, 'F') in ('담당', '공동') and tx(r, 'J') != '완료' and not tx(r, 'G')) or items[0]
        t_other = pick(lambda r: tx(r, 'F') not in ('담당', '공동') and tx(r, 'J') != '완료' and not tx(r, 'G')) or t_mine
        t_done = pick(lambda r: tx(r, 'J') == '완료') or t_other
        t_robot = pick(lambda r: tx(r, 'G') == 'R' and tx(r, 'J') != '완료')
        robot_style = t_robot.style('G') if t_robot else t_mine.style('G')
        entries, summary = entries_fn(L)
        # 기존 내용 행과 그 병합을 지운다
        dead = set(id(r) for r in s.rows[h + 1:])
        s.merges = [m for m in s.merges if id(m[1]) not in dead]
        n_old = len(s.rows)
        s.rows = s.rows[:h + 1]
        for kind, e in entries:
            if kind == 'day':
                r = t_day.clone()
                for c in 'ABCDEFGHIJ':
                    r.set(c, e if c == 'A' else None)
                s.rows.append(r); s.merges.append(('A', r, 'J', r))
            else:
                r = (t_done if e['done'] else t_mine if e['mine'] else t_other).clone()
                vals = [e['when'], e['check'], e['id'], e['easy'], e['task'], e['role'], e['robot'], e['crit'], e['where'], e['status']]
                for c, v in zip('ABCDEFGHIJ', vals):
                    r.set(c, v)
                if e['robot'] and not e['done']:
                    r.set('G', 'R', style=robot_style)
                elif not e['done']:
                    r.set('G', e['robot'], style=(t_mine if e['mine'] else t_other).style('F'))
                s.rows.append(r)
        while len(s.rows) < n_old:
            s.rows.append(Row('', {}))
        s.rows[2].set('A', summary)


def set_slots(row, slots):
    """기존 Time Line 행의 간트 색 칸을 slots=[('9/20','오전'), …] 로 다시 칠한다(색은 그 행이 쓰던 색)."""
    _check_open(slots)
    gcols = open_gantt_cols()
    styles = [row.style(c) for c in gcols if row.style(c) is not None]
    blank = max(set(styles), key=styles.count)
    fill = next((s for s in styles if s != blank), None)
    if fill is None:
        raise ValueError('이 행에는 색 칸이 없어 색을 알 수 없다')
    for c in gcols:
        row.set(c, style=blank)
    for d, p in slots:
        row.set(gantt_col(d, p), style=fill)
