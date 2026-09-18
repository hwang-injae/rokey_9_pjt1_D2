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
