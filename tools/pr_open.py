#!/usr/bin/env python3
"""열린 PR을 로그인 없이 본다(공개 저장소의 GitHub API, 읽기 전용).
사용:  tools/pr_open.py          → 열린 PR 목록 (번호 · head SHA · 작성자 · draft/hold · 제목)
      tools/pr_open.py 12       → PR #12 의 본문 · 변경 파일 · 리뷰 · 최근 코멘트
검토는 tools/pr_check.sh <번호> 와 git diff origin/main...pr-<번호> 로 한다. 이 도구는 아무것도 바꾸지 않는다."""
import sys, json, urllib.request, urllib.error

REPO = 'hwang-injae/rokey_9_pjt1_D2'
API = f'https://api.github.com/repos/{REPO}'


def get(path):
    req = urllib.request.Request(API + path, headers={'Accept': 'application/vnd.github+json', 'User-Agent': 'prewash-pr-open'})
    try:
        return json.load(urllib.request.urlopen(req, timeout=20))
    except urllib.error.HTTPError as e:                      # 403 = 시간당 60회 제한(로그인 없는 호출)
        sys.exit(f'GitHub API {e.code}: {e.read().decode()[:200]}')


def hold(p):
    return '[hold]' in p['title'].lower() or any(l['name'] == 'hold' for l in p.get('labels', []))


def main():
    if len(sys.argv) > 1:
        n = sys.argv[1]
        p = get(f'/pulls/{n}')
        print(f"#{p['number']} {p['state']}{' draft' if p['draft'] else ''}{' HOLD' if hold(p) else ''} · {p['user']['login']} · {p['head']['ref']} @ {p['head']['sha'][:7]} → {p['base']['ref']}")
        print(f"제목: {p['title']}\n변경: 파일 {p['changed_files']} · +{p['additions']} -{p['deletions']} · 커밋 {p['commits']} · mergeable={p.get('mergeable')}")
        print('--- 본문\n' + (p['body'] or '(없음)'))
        print('--- 변경 파일')
        for f in get(f'/pulls/{n}/files?per_page=100'):
            print(f"  {f['status'][:1].upper()} +{f['additions']:<4} -{f['deletions']:<4} {f['filename']}")
        print('--- 리뷰')
        for r in get(f'/pulls/{n}/reviews'):
            print(f"  {r['user']['login']} {r['state']} {r['submitted_at']} @ {r['commit_id'][:7]} | {(r['body'] or '')[:100]}")
        print('--- 최근 코멘트 3개')
        for c in get(f'/issues/{n}/comments?per_page=100')[-3:]:
            print(f"  {c['user']['login']} {c['created_at']} | {c['body'][:160].replace(chr(10), ' ')}")
        return
    prs = get('/pulls?state=open&per_page=50')
    if not prs:
        print('열린 PR 없음')
    for p in prs:
        flags = ('draft ' if p['draft'] else '') + ('HOLD ' if hold(p) else '')
        print(f"#{p['number']} {p['head']['sha'][:7]} {p['user']['login']:<16} {flags}{p['updated_at'][5:16]} | {p['title']}")


if __name__ == '__main__':
    main()
