# 구글 시트(정본)를 내려받아 Time Line 행 + 간트 색 칸(=일정) + 상세 시트를 읽는다
import urllib.request, io, re, zipfile, xml.etree.ElementTree as ET
SID='1ikTAYTa8bgZofF_3RgP5jDoOipSZBPB1'
NS={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
def colnum(c):
    n=0
    for ch in c: n=n*26+ord(ch)-64
    return n
def load(path=None):
    d=open(path,'rb').read() if path else urllib.request.urlopen(f'https://docs.google.com/spreadsheets/d/{SID}/export?format=xlsx',timeout=40).read()
    z=zipfile.ZipFile(io.BytesIO(d))
    ss=[''.join(t.text or '' for t in si.iter('{%s}t'%NS['m'])) for si in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('m:si',NS)]
    st=ET.fromstring(z.read('xl/styles.xml'))
    fills=[]
    for f in st.find('m:fills',NS):
        pf=f.find('m:patternFill',NS); fg=pf.find('m:fgColor',NS) if pf is not None else None
        fills.append((fg.get('rgb') or ('theme'+fg.get('theme') if fg.get('theme') else None)) if fg is not None else None)
    xfs=[int(x.get('fillId') or 0) for x in st.find('m:cellXfs',NS)]
    wb=ET.fromstring(z.read('xl/workbook.xml')); rels=ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
    rmap={r.get('Id'):r.get('Target') for r in rels}
    sheets={}
    for sh in wb.find('m:sheets',NS):
        rid=sh.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')
        path='xl/'+rmap[rid].replace('/xl/','').lstrip('/')
        rows=[]
        for row in ET.fromstring(z.read(path)).iter('{%s}row'%NS['m']):
            d={}
            for c in row.findall('m:c',NS):
                v=c.find('m:v',NS); t=c.get('t'); col=re.sub(r'\d','',c.get('r'))
                if t=='s' and v is not None: val=ss[int(v.text)]
                elif t=='inlineStr': val=''.join(x.text or '' for x in c.iter('{%s}t'%NS['m']))
                else: val=v.text if v is not None else ''
                fill=fills[xfs[int(c.get('s'))]] if c.get('s') and int(c.get('s'))<len(xfs) else None
                d[col]=(val,fill)
            rows.append(d)
        sheets[sh.get('name')]=rows
    return sheets
def timeline(sheets):
    tl=sheets['Time Line']
    h=next(i for i,r in enumerate(tl) if r.get('A',('',0))[0].strip()=='팀')
    hdr,sub=tl[h],tl[h+1]
    idcol=[k for k,v in hdr.items() if 'ID' in (v[0] or '')][-1]
    gcols=sorted([k for k in set(hdr)|set(sub) if colnum('F')<colnum(k)<colnum(idcol)],key=colnum)
    day=''; lab={}
    for k in gcols:
        if hdr.get(k,('',0))[0]: day=hdr[k][0].split('(')[0].strip()
        lab[k]=(day,(sub.get(k,('',0))[0] or '')[:2])
    out=[]; team=''
    WHITE={None,'FFFFFFFF','theme0'}
    # 열 배경: 작업 행의 80% 이상이 같은 색이면 그 열의 그 색은 작업 칸이 아니라 배경이다
    # (황인재가 닫힌 칸 — 주말 저녁 — 을 열 전체 연분홍으로 칠해 둔 것, 9/19)
    body=[r for r in tl[h+2:] if (r.get(idcol,('',None))[0] or '').strip() or (r.get('C',('',None))[0] or '').strip()]
    bg={}
    for k in gcols:
        cnt={}
        for r in body:
            f=r.get(k,('',None))[1]
            if f not in WHITE: cnt[f]=cnt.get(f,0)+1
        top=max(cnt,key=cnt.get) if cnt else None
        if top and cnt[top]>=0.8*len(body): bg[k]=top
    for r in tl[h+2:]:
        g=lambda c:(r.get(c,('',None))[0] or '').strip()
        team=g('A') or team
        if not g(idcol) and not g('C'): continue
        slots=[lab[k] for k in gcols if r.get(k,('',None))[1] not in WHITE and r.get(k,('',None))[1]!=bg.get(k)]
        out.append(dict(team=team,cat=g('B'),task=g('C'),owner=g('D'),prog=g('E'),status=g('F'),id=g(idcol),slots=slots))
    det={}
    for r in sheets.get('상세(산출물·완료기준)',[]):
        g=lambda c:(r.get(c,('',None))[0] or '').strip()
        if g('A'): det[g('A')]=dict(deliv=g('E'),crit=g('F'),note=g('G'))
    return out,det
if __name__=='__main__':
    rows,det=timeline(load())
    print(len(rows),'rows')
    for r in rows: print(f"{r['id']:9}|{r['owner']:10}|{r['status'][:4]:5}|{(r['slots'][0][0]+r['slots'][0][1] if r['slots'] else '-'):9}~{(r['slots'][-1][0]+r['slots'][-1][1] if r['slots'] else ''):9}|{r['task'][:48]}")
