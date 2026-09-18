#!/usr/bin/env python3
"""구글 시트 일정표(정본)를 내려받아 터미널에 보여 준다. 로그인 불필요(링크 공유).
사용:  tools/sched.py                → Time Line 전체 (ID·팀·작업·담당·진행·상태·간트)
      tools/sched.py S               → 담당에 S(한석형)가 포함된 행만 (M 민범진 · P 박진용 · H 황인재 · 전원)
      tools/sched.py F1-02           → 그 ID 행 + 상세 시트의 산출물·완료 기준
      tools/sched.py --sheet 규칙     → 다른 시트 출력 (마일스톤·로봇 슬롯 / 완료 목록 / 규칙 / 변경이력)
"""
import sys, io, re, zipfile, urllib.request, xml.etree.ElementTree as ET
SHEET_ID='1zV0yb2k89li7SNBvDWSXT2jT3KTbuDVF'
URL=f'https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=xlsx'
NS={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
def load():
    data=urllib.request.urlopen(URL,timeout=30).read()
    z=zipfile.ZipFile(io.BytesIO(data))
    ss=[''.join(t.text or '' for t in si.iter('{%s}t'%NS['m'])) for si in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('m:si',NS)] if 'xl/sharedStrings.xml' in z.namelist() else []
    wb=ET.fromstring(z.read('xl/workbook.xml')); rels=ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
    rmap={r.get('Id'):r.get('Target') for r in rels}
    sheets={}
    for sh in wb.find('m:sheets',NS):
        rid=sh.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')
        path='xl/'+rmap[rid].replace('/xl/','').lstrip('/')
        rows=[]
        for row in ET.fromstring(z.read(path)).iter('{%s}row'%NS['m']):
            cells={}
            for c in row.findall('m:c',NS):
                v=c.find('m:v',NS); t=c.get('t'); ref=re.sub(r'\d','',c.get('r'))
                if t=='s' and v is not None: val=ss[int(v.text)]
                elif t=='inlineStr': val=''.join(x.text or '' for x in c.iter('{%s}t'%NS['m']))
                elif v is not None: val=v.text
                else: val=''
                cells[ref]=val
            rows.append(cells)
        sheets[sh.get('name')]=rows
    return sheets
def col(n):
    s=''; n+=1
    while n: n,r=divmod(n-1,26); s=chr(65+r)+s
    return s
def main():
    a=sys.argv[1:]
    sheets=load()
    if a and a[0]=='--sheet':
        name=' '.join(a[1:]); rows=sheets.get(name) or next((v for k,v in sheets.items() if name in k),None)
        if not rows: print('시트 없음:',list(sheets)); return
        for r in rows:
            vals=[r.get(col(i),'') for i in range(8)]
            if any(vals): print(' | '.join(v for v in vals if v))
        return
    tl=sheets['Time Line']; hdr=tl[0]; sub=tl[1] if len(tl)>1 else {}
    # 간트 열 = G 이후 ~ ID 열 앞
    keys=sorted(hdr.keys(),key=lambda k:(len(k),k)); idcol=[k for k in keys if 'ID' in (hdr.get(k) or '')][-1]
    gcols=[k for k in keys if k not in ('A','B','C','D','E','F',idcol) and (len(k)==1 and k>'F' or len(k)==2) and (keys.index(k)<keys.index(idcol))]
    day=''; labels=[]
    for k in gcols:
        if hdr.get(k): day=hdr[k].split('(')[0]
        labels.append(f"{day}{sub.get(k,'')[:1]}")
    flt=a[0] if a else None; team=''
    for r in tl[2:]:
        team=r.get('A') or team
        tid=r.get(idcol,''); own=r.get('D','')
        if flt and not (flt==tid or (flt in own) or (flt=='전원' and '전원' in own)): continue
        gantt=''.join('■' if r.get(k,'')=='' and False else '' for k in gcols)  # 색은 xlsx export에 값이 없어 표시 불가
        print(f"[{tid:8}] {team:6} {r.get('B',''):5} {r.get('C','')[:70]:<70} {own:8} 진행 {r.get('E','')} {r.get('F','')}")
    if flt and re.match(r'^[A-Z][A-Z0-9]*-',flt):
        for r in sheets.get('상세(산출물·완료기준)',[]):
            if r.get('A')==flt: print('\n  산출물:',r.get('E',''),'\n  완료 기준:',r.get('F',''),'\n  비고:',r.get('G',''))
    print('\n(간트 색·로봇 슬롯은 시트에서 직접 보기:',f'https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit',')')
main()
