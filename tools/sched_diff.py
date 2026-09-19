#!/usr/bin/env python3
"""구글 시트 일정표(정본)가 지난번 확인 뒤로 어떻게 바뀌었는지 보여 준다. 로그인 불필요(링크 공유), 읽기 전용.
사용:  tools/sched_diff.py            → 지난 스냅숏과 지금 시트를 비교해 바뀐 것만 출력하고, 지금 것을 새 스냅숏으로 저장
      tools/sched_diff.py --keep     → 비교만 하고 스냅숏은 그대로 둔다
      tools/sched_diff.py 파일.xlsx   → 그 파일(예: 패치로 만든 xlsx)과 지금 시트를 비교 (스냅숏은 건드리지 않음)
스냅숏 위치: 환경변수 PREWASH_SCHED_SNAPSHOT, 없으면 ~/.cache/prewash/sched_snapshot.xlsx"""
import os, sys, urllib.request
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / 'gen'))
from livesheet import SID, load, timeline

SNAP = Path(os.environ.get('PREWASH_SCHED_SNAPSHOT') or Path.home() / '.cache' / 'prewash' / 'sched_snapshot.xlsx')
URL = f'https://docs.google.com/spreadsheets/d/{SID}/export?format=xlsx'
PART = {'오전': 'a', '오후': 'p', '저녁': 'e'}


def slots(r):
    return ','.join(d.replace('9/', '') + PART.get(p, p) for d, p in r['slots']) or '-'


def cells(sheet):
    rows = [{c: v[0] for c, v in r.items() if v[0]} for r in sheet]
    return [r for r in rows if r]


def main():
    args = [a for a in sys.argv[1:] if a != '--keep']
    keep = '--keep' in sys.argv[1:] or bool(args)
    base = Path(args[0]) if args else SNAP
    data = urllib.request.urlopen(URL, timeout=40).read()
    tmp = SNAP.with_suffix('.new.xlsx'); tmp.parent.mkdir(parents=True, exist_ok=True); tmp.write_bytes(data)
    new = load(str(tmp))
    if not base.is_file():
        tmp.replace(SNAP); print(f'첫 실행 — 지금 시트를 스냅숏으로 저장했다: {SNAP}'); return
    old = load(str(base))
    (o_rows, _), (n_rows, _) = timeline(old), timeline(new)
    O = {r['id'] or r['task']: r for r in o_rows}; N = {r['id'] or r['task']: r for r in n_rows}
    out = []
    for k, r in N.items():
        if k not in O:
            out.append(f"  + 새 행 {k} [{r['team']}] {r['owner']} {r['status']} {slots(r)} | {r['task'][:70]}"); continue
        o = O[k]
        ch = [f"{name}: {a} → {b}" for name, a, b in (('담당', o['owner'], r['owner']), ('상태', o['status'], r['status']), ('진행', o['prog'], r['prog']),
                                                       ('칸', slots(o), slots(r)), ('구역', o['team'], r['team']), ('구분', o['cat'], r['cat'])) if a != b]
        if o['task'] != r['task']: ch.append(f"작업명: {o['task'][:50]}… → {r['task'][:50]}…")
        if ch: out.append(f"  ~ {k}: " + ' · '.join(ch))
    out += [f"  - 사라진 행 {k} | {O[k]['task'][:70]}" for k in O if k not in N]
    if [r['id'] for r in o_rows if (r['id'] or r['task']) in N] != [r['id'] for r in n_rows if (r['id'] or r['task']) in O]:
        out.append('  ~ 행 순서가 바뀌었다')
    print('== Time Line ==' + ('' if out else ' 변화 없음')); print('\n'.join(out)) if out else None
    for name in new:
        if name == 'Time Line': continue
        a, b = cells(old.get(name, [])), cells(new[name])
        if a == b: continue
        print(f'== {name} == (행 {len(a)} → {len(b)})')
        n = 0
        for i in range(max(len(a), len(b))):
            x, y = (a[i] if i < len(a) else {}), (b[i] if i < len(b) else {})
            for c in sorted(set(x) | set(y)):
                if x.get(c) != y.get(c) and n < 25:
                    n += 1; print(f"  {i + 1}행 {c}: {str(x.get(c, ''))[:45]!r} → {str(y.get(c, ''))[:45]!r}")
        if n >= 25: print('  … (더 있음)')
    for name in old:
        if name not in new: print(f'== {name} == 시트가 없어졌다')
    if keep: tmp.unlink()
    else: tmp.replace(SNAP); print(f'(스냅숏 갱신: {SNAP})')


if __name__ == '__main__':
    main()
