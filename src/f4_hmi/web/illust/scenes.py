# 단계 그림 9장 × (그릇 · 컵) — 320 × 240, 받침대 위 등각 장면
#   그릇은 벽을 세로로 잡고, 컵은 몸통을 통째로 잡는다(AGENTS.md 시나리오 ①). 툴은 그릇 = 수세미 · 컵 = 솔(E18)
import math
from iso import Scene, pedestal, container, gripper, shade, mix, BOWL, CUP, ACC

W, H = 320, 240
AX = -20                                    # 그리퍼 손가락이 벌어지는 축(도) — 화면 오른쪽 약간 앞
UX, UY = math.cos(math.radians(AX)), math.sin(math.radians(AX))

def new(pid):
    s = Scene(pid, W, H, 160, 168, k=.8)
    pedestal(s)
    return s

def dims(kind):
    return BOWL if kind == 'BOWL' else CUP

def hold(s, kind, cx, cy, z0, draw_container=True, alpha=1, between=None):
    """용기를 잡은 그리퍼 + 용기 — 그릇은 오른쪽 벽을 세로로, 컵은 몸통을 통째로"""
    d = dims(kind)
    top = z0 + d['h']
    if kind == 'BOWL':
        r = d['r1'] - 1.8
        gx, gy = cx + r * UX, cy + r * UY
        rim = container(s, kind, cx, cy, z0, alpha) if draw_container else None
        if between: between()
        gripper(s, gx, gy, top - 22, 6, finger=44, ang=AX, part='back', inner_min_z=top)
        gripper(s, gx, gy, top - 22, 6, finger=44, ang=AX, part='front')
        gripper(s, gx, gy, top - 22, 6, finger=44, ang=AX, part='top')
    else:
        zt = z0 + 30
        rr = d['r0'] + (d['r1'] - d['r0']) * .45 + 3.4
        gripper(s, cx, cy, zt, rr, finger=d['h'] - 30 + 14, ang=AX, part='back')
        rim = container(s, kind, cx, cy, z0, alpha) if draw_container else None
        if between: between()
        gripper(s, cx, cy, zt, rr, finger=d['h'] - 30 + 14, ang=AX, part='front')
        gripper(s, cx, cy, zt, rr, finger=d['h'] - 30 + 14, ang=AX, part='top')
    return rim

def right_of(s, kind, cx, cy, z0, pad=16):
    d = dims(kind)
    X, Y, rx, ry = s.ell(cx, cy, z0 + d['h'] / 2, d['r1'])
    return X + rx + pad, Y

# ── 부품 ──────────────────────────────────────────────────────────────
def tray(s):
    """반납 구역 — 내리막 경사판 + 집는 자리 판"""
    s.raw(f'<polygon points="{s.pts([(-66, -66, 8), (66, -66, 8), (66, -118, 46), (-66, -118, 46)])}" fill="{shade("rack", .93)}"/>')
    s.raw(f'<polygon points="{s.pts([(66, -66, 0), (66, -118, 0), (66, -118, 46), (66, -66, 8)])}" fill="{shade("rack", .5)}"/>')
    for t in (.25, .5, .75):                                       # 경사판 살
        y = -66 - 52 * t; z = 8 + 38 * t
        s.raw(f'<line x1="{s.P(-66, y, z)[0]:.1f}" y1="{s.P(-66, y, z)[1]:.1f}" x2="{s.P(66, y, z)[0]:.1f}" y2="{s.P(66, y, z)[1]:.1f}" stroke="{shade("rack", .7)}" stroke-width="1.2"/>')
    s.box(-66, -66, 0, 132, 132, 8, 'rack')
    s.box(-66, -66, 8, 132, 5, 6, 'rack'); s.box(-66, -66, 8, 5, 132, 6, 'rack')
    s.box(61, -66, 8, 5, 132, 6, 'rack'); s.box(-66, 61, 8, 132, 5, 6, 'rack')

def bed(s, top=38):
    """스펀지 고정틀 — 회색 틀 + 노란 스펀지 + 가운데 홈"""
    s.box(-70, -70, 0, 140, 140, top - 10, 'foam')
    s.box(-66, -66, top - 10, 132, 132, 10, 'sponge')
    X, Y, rx, ry = s.ell(0, 0, top, 42)
    g = s.lgrad([(0, shade('sponge', .30), 1), (1, shade('sponge', .62), 1)], 0, 0, 0, 1)
    s.raw(f'<ellipse cx="{X:.1f}" cy="{Y:.1f}" rx="{rx:.1f}" ry="{ry:.1f}" fill="{g}"/>')
    for i in range(22):                                             # 스펀지 구멍 무늬
        a = i * 2.39996; rr = 48 + (i * 37 % 16)
        px, py = rr * math.cos(a), rr * math.sin(a)
        if abs(px) < 62 and abs(py) < 62:
            Xp, Yp = s.P(px, py, top)
            s.raw(f'<ellipse cx="{Xp:.1f}" cy="{Yp:.1f}" rx="1.8" ry="1.1" fill="{shade("sponge", .55)}"/>')

def tool(s, kind, cx, cy, zh, clip=''):
    """툴 — 그릇이면 수세미, 컵이면 솔. zh = 머리 아래 끝. 돌려주는 값: 손잡이 위 끝 높이"""
    g = f'<g {clip}>' if clip else '<g>'
    s.raw(g)
    if kind == 'BOWL':
        s.rbox(cx, cy, zh, 17, 17, 7, 'scrub', ang=-10)
        s.rbox(cx, cy, zh + 7, 17, 17, 15, 'sponge', ang=-10)
        base = zh + 22
    else:
        s.cyl(cx, cy, zh, 13, zh + 30, 14, 'bristle', top='solid')
        X0, Y0, rx0, _ = s.ell(cx, cy, zh, 13)
        X1, Y1, rx1, _ = s.ell(cx, cy, zh + 30, 14)
        for t in [i / 9 for i in range(1, 9)]:
            s.raw(f'<line x1="{X0 - rx0 + 2 * rx0 * t:.1f}" y1="{Y0 + 3:.1f}" x2="{X1 - rx1 + 2 * rx1 * t:.1f}" y2="{Y1 + 3:.1f}" stroke="{shade("bristle", .35)}" stroke-width=".8" stroke-opacity=".7"/>')
        s.cyl(cx, cy, zh + 30, 8, zh + 38, 8, 'steel')
        base = zh + 38
    s.cyl(cx, cy, base, 5.5, base + 58, 5.5, 'handle')
    s.raw('</g>')
    return base + 58

def hold_tool(s, cx, cy, top, part='all'):
    gripper(s, cx, cy, top - 28, 9, finger=40, ang=AX, part=part)

def crumbs(s, pts, r=2.4):
    for i, (x, y) in enumerate(pts):
        rr = r * (0.7 + (i * 37 % 10) / 14)
        s.raw(f'<ellipse cx="{x:.1f}" cy="{y:.1f}" rx="{rr * 1.2:.1f}" ry="{rr:.1f}" transform="rotate({i * 47 % 180} {x:.1f} {y:.1f})" fill="{["#8a5a2b", "#a8743d", "#6e4521"][i % 3]}"/>')

def bubbles(s, pts):
    for i, (x, y, r) in enumerate(pts):
        s.raw(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="#ffffff" fill-opacity=".35" stroke="#ffffff" stroke-opacity=".9" stroke-width="1"/>'
              f'<circle cx="{x - r * .35:.1f}" cy="{y - r * .35:.1f}" r="{max(.8, r * .25):.1f}" fill="#fff"/>')

# ── 장면 ──────────────────────────────────────────────────────────────
def PICK(kind, pid):
    s = new(pid)
    tray(s)
    z0 = 14 + 26
    s.shadow(0, 0, 14, dims(kind)['r0'] + 8, op=.4)
    hold(s, kind, 0, 0, z0)
    x, y = right_of(s, kind, 0, 0, z0, 22)
    s.arrow([(x + 6, y + 34), (x + 6, y - 26)])
    return s

def WEIGH(kind, pid):
    s = new(pid)
    z0 = 34
    s.shadow(0, 0, 0, dims(kind)['r0'] + 10, op=.35)
    hold(s, kind, 0, 0, z0)
    # 무게 표시 — 추 모양
    bx, by = 262, 150
    g = s.lgrad([(0, shade('steel', .95), 1), (1, shade('steel', .55), 1)], 0, 0, 1, 1)
    s.raw(f'<circle cx="{bx}" cy="{by - 30}" r="8" fill="none" stroke="{shade("steel", .75)}" stroke-width="4"/>'
          f'<path d="M{bx - 16} {by - 22} H{bx + 16} L{bx + 24} {by + 12} Q{bx + 25} {by + 17} {bx + 20} {by + 17} H{bx - 20} Q{bx - 25} {by + 17} {bx - 24} {by + 12} Z" fill="{g}" stroke="{shade("steel", .35)}" stroke-width="1"/>'
          f'<text x="{bx}" y="{by + 6}" text-anchor="middle" font-family="IBM Plex Sans KR, system-ui, sans-serif" font-size="18" font-weight="700" fill="#1b2330">g</text>')
    x, y = right_of(s, kind, 0, 0, z0, 10)
    s.arrow([(x - 4, y - 8), (x - 4, y + 40)])
    return s

def SHAKE(kind, pid):
    s = new(pid)
    s.shadow(0, 0, 0, 60, op=.4)
    rim = s.vessel(0, 0, 0, 50, 54, 60, mat='bin', wall=4)
    X, Y, rx, ry = rim
    crumbs(s, [(X - 20, Y + 4), (X - 6, Y + 8), (X + 12, Y + 3), (X + 24, Y + 7), (X + 2, Y + 12), (X - 30, Y + 9)], 2.6)
    d = dims(kind)
    z0 = 88 if kind == 'BOWL' else 70
    px, py = s.P(0, 0, z0 + d['h'] + 60)
    s.raw(f'<g transform="rotate(-24 {px:.1f} {py:.1f})">')
    hold(s, kind, -8, 8, z0)
    s.raw('</g>')
    # 떨어지는 잔반
    ox, oy = s.P(0, 0, z0 - 6)
    crumbs(s, [(ox - 26, oy + 24), (ox - 12, oy + 38), (ox - 30, oy + 52), (ox - 4, oy + 60), (ox - 18, oy + 72)], 2.8)
    # 흔드는 표시
    lx, ly = s.P(0, 0, z0 + d['h'] / 2)
    for sg in (-1, 1):
        x0 = lx + sg * (d['r1'] * 1.25 + 26)
        s.raw(f'<path d="M{x0:.1f} {ly - 24:.1f} Q{x0 + sg * 12:.1f} {ly:.1f} {x0:.1f} {ly + 24:.1f}" fill="none" stroke="{ACC}" stroke-width="3.5" stroke-linecap="round"/>'
              f'<path d="M{x0 + sg * 10:.1f} {ly - 16:.1f} Q{x0 + sg * 19:.1f} {ly:.1f} {x0 + sg * 10:.1f} {ly + 16:.1f}" fill="none" stroke="{ACC}" stroke-opacity=".55" stroke-width="3" stroke-linecap="round"/>')
    return s

def SEAT(kind, pid):
    s = new(pid)
    bed(s)
    z0 = 38 + 24
    s.shadow(0, 0, 38, dims(kind)['r0'] + 6, op=.35)
    hold(s, kind, 0, 0, z0)
    x, y = right_of(s, kind, 0, 0, z0, 22)
    s.arrow([(x + 6, y - 30), (x + 6, y + 26)])
    return s

def holder(s):
    """세제 — 바닥에 고정한 컵 모양 홀더 + 비눗물"""
    s.cyl(0, 0, 0, 52, 5, 52, 'steel')
    s.cyl(0, 0, 5, 44, 70, 46, 'glass', top=None, alpha=.35)
    s.cyl(0, 0, 5, 42, 54, 43.5, 'water', top=None, alpha=.55, outline=False)
    X, Y, rx, ry = s.ell(0, 0, 54, 43.5)
    s.raw(f'<ellipse cx="{X:.1f}" cy="{Y:.1f}" rx="{rx:.1f}" ry="{ry:.1f}" fill="{mix("#dff0ff", "#ffffff", .4)}" fill-opacity=".85"/>')
    return X, Y, rx, ry

def SOAP(kind, pid):
    s = new(pid)
    s.shadow(0, 0, 0, 56, op=.4)
    X, Y, rx, ry = holder(s)
    zh = 22
    top = tool(s, kind, 0, 0, zh)
    s.cyl(0, 0, 5, 42, 54, 43.5, 'water', top=None, alpha=.45, outline=False)          # 물속 부분을 물빛으로 덮는다
    Xg, Yg, rxg, ryg = s.ell(0, 0, 70, 46)
    s.raw(f'<ellipse cx="{Xg:.1f}" cy="{Yg:.1f}" rx="{rxg:.1f}" ry="{ryg:.1f}" fill="none" stroke="{shade("glass", .95)}" stroke-width="1.5" stroke-opacity=".8"/>')
    s.raw(f'<path d="M{Xg - rxg * .7:.1f} {Yg + ryg * .8:.1f} L{Xg - rxg * .72:.1f} {Y + 40:.1f}" stroke="#fff" stroke-opacity=".5" stroke-width="3" stroke-linecap="round"/>')
    bubbles(s, [(X - 30, Y - 2, 5), (X - 18, Y + 6, 4), (X + 22, Y + 5, 5.5), (X + 34, Y - 3, 3.5), (X - 36, Y + 8, 3), (X + 10, Y + 10, 3.5),
                (X + 58, Y - 34, 4), (X + 70, Y - 58, 3), (X - 62, Y - 44, 3.5), (X + 48, Y - 70, 2.5)])
    hold_tool(s, 0, 0, top)
    return s

def WIPE(kind, pid):
    s = new(pid)
    bed(s)
    z0 = 38 - 14
    rim = container(s, kind, 0, 0, z0)
    clip = s.clip_open(rim)
    if kind == 'BOWL':
        tx, ty, zh = -14, -10, z0 + 6
    else:
        tx, ty, zh = 0, 0, z0 + 22
    top = tool(s, kind, tx, ty, zh, clip=clip)
    hold_tool(s, tx, ty, top)
    X, Y, rx, ry = rim
    if kind == 'BOWL':                                           # 안쪽을 도는 화살표
        a0, a1 = math.radians(200), math.radians(520)
        pts = [(X + rx * .78 * math.cos(t), Y + 4 + ry * .7 * math.sin(t)) for t in [a0 + (a1 - a0) * i / 30 for i in range(31)]]
        s.arrow(pts[4:], w=3.5, head=7)
    else:                                                        # 위아래로 문지르는 화살표
        x = X + rx + 22
        s.arrow([(x, Y + 10), (x, Y - 30)], w=3.5, head=7)
        s.arrow([(x + 12, Y - 30), (x + 12, Y + 10)], w=3.5, head=7)
    return s

def RINSE(kind, pid):
    s = new(pid)
    x0, x1, y0, y1, zt, zw = -76, 76, -58, 58, 64, 46
    s.shadow(0, 0, 0, 80, op=.35)
    s.raw(f'<polygon points="{s.pts([(x0, y0, 0), (x1, y0, 0), (x1, y0, zt), (x0, y0, zt)])}" fill="{shade("glass", .45)}" fill-opacity=".55"/>')
    s.raw(f'<polygon points="{s.pts([(x0, y0, 0), (x0, y1, 0), (x0, y1, zt), (x0, y0, zt)])}" fill="{shade("glass", .6)}" fill-opacity=".55"/>')
    s.raw(f'<polygon points="{s.pts([(x0, y0, 0), (x1, y0, 0), (x1, y1, 0), (x0, y1, 0)])}" fill="{shade("glass", .35)}" fill-opacity=".6"/>')
    s.raw(f'<polygon points="{s.pts([(x0, y0, zw), (x1, y0, zw), (x1, y1, zw), (x0, y1, zw)])}" fill="{shade("water", .85)}" fill-opacity=".55"/>')
    d = dims(kind)
    z0 = zw - (28 if kind == 'BOWL' else 44)
    rw = d['r0'] + (d['r1'] - d['r0']) * ((zw - z0) / d['h'])
    Xw, Yw, rxw, ryw = s.ell(0, 0, zw, rw)
    def waterline():
        s.raw(f'<polygon points="{s.pts([(x0, y0, zw), (x1, y0, zw), (x1, y1, zw), (x0, y1, zw)])}" fill="{shade("water", .8)}" fill-opacity=".5"/>')
        for m, op in ((1.2, .85), (1.48, .5), (1.8, .28)):
            s.raw(f'<ellipse cx="{Xw:.1f}" cy="{Yw:.1f}" rx="{rxw * m:.1f}" ry="{ryw * m:.1f}" fill="none" stroke="#ffffff" stroke-opacity="{op}" stroke-width="1.6"/>')
        cid = s.uid('wl')
        s.defs.append(f'<clipPath id="{cid}"><rect x="-2000" y="-2000" width="4000" height="{2000 + Yw:.1f}"/><ellipse cx="{Xw:.1f}" cy="{Yw:.1f}" rx="{rxw:.1f}" ry="{ryw:.1f}"/></clipPath>')
        s.raw(f'<g clip-path="url(#{cid})">'); container(s, kind, 0, 0, z0); s.raw('</g>')
        s.raw(f'<ellipse cx="{Xw:.1f}" cy="{Yw:.1f}" rx="{rxw:.1f}" ry="{ryw:.1f}" fill="none" stroke="#ffffff" stroke-opacity=".9" stroke-width="1.4"/>')
    hold(s, kind, 0, 0, z0, between=waterline)
    # 물 앞면 — 잠긴 부분을 물빛으로
    s.raw(f'<polygon points="{s.pts([(x0, y1, 0), (x1, y1, 0), (x1, y1, zw), (x0, y1, zw)])}" fill="{shade("water", .7)}" fill-opacity=".5"/>')
    s.raw(f'<polygon points="{s.pts([(x1, y0, 0), (x1, y1, 0), (x1, y1, zw), (x1, y0, zw)])}" fill="{shade("water", .5)}" fill-opacity=".55"/>')
    # 유리 앞면 · 테두리
    s.raw(f'<polygon points="{s.pts([(x0, y1, zw), (x1, y1, zw), (x1, y1, zt), (x0, y1, zt)])}" fill="{shade("glass", .9)}" fill-opacity=".12"/>')
    s.raw(f'<polygon points="{s.pts([(x1, y0, zw), (x1, y1, zw), (x1, y1, zt), (x1, y0, zt)])}" fill="{shade("glass", .7)}" fill-opacity=".12"/>')
    s.raw(f'<polyline points="{s.pts([(x0, y1, zt), (x1, y1, zt), (x1, y0, zt), (x0, y0, zt), (x0, y1, zt)])}" fill="none" stroke="{shade("glass", 1)}" stroke-width="1.5" stroke-opacity=".85"/>')
    for a, b in (((x0, y1, 0), (x0, y1, zt)), ((x1, y1, 0), (x1, y1, zt)), ((x1, y0, 0), (x1, y0, zt)), ((x0, y1, 0), (x1, y1, 0)), ((x1, y1, 0), (x1, y0, 0))):
        (ax, ay), (bx, by) = s.P(*a), s.P(*b)
        s.raw(f'<line x1="{ax:.1f}" y1="{ay:.1f}" x2="{bx:.1f}" y2="{by:.1f}" stroke="{shade("glass", 1)}" stroke-width="1.2" stroke-opacity=".7"/>')
    return s

def rack_base(s):
    s.box(-86, -74, 0, 172, 148, 6, 'rack')
    for i in range(1, 8):
        x = -86 + 172 * i / 8
        (ax, ay), (bx, by) = s.P(x, -74, 6), s.P(x, 74, 6)
        s.raw(f'<line x1="{ax:.1f}" y1="{ay:.1f}" x2="{bx:.1f}" y2="{by:.1f}" stroke="{shade("rack", .72)}" stroke-width="1"/>')
    for i in range(1, 7):
        y = -74 + 148 * i / 7
        (ax, ay), (bx, by) = s.P(-86, y, 6), s.P(86, y, 6)
        s.raw(f'<line x1="{ax:.1f}" y1="{ay:.1f}" x2="{bx:.1f}" y2="{by:.1f}" stroke="{shade("rack", .72)}" stroke-width="1"/>')

def RACK(kind, pid):
    s = new(pid)
    s.shadow(0, 0, 0, 92, op=.35)
    rack_base(s)
    if kind == 'BOWL':
        tines = lambda x: [s.cyl(x, y, 6, 2.2, 42, 2.2, 'rack') for y in (-64, -46, -28, -10, 10, 28, 46, 64)]
        tines(-26)
        zb = 6 + 16
        s.shadow(0, 0, 6, 30, op=.4, squash=.6)
        s.standing_bowl(0, 0, zb)
        tines(26)
        top = zb + 2 * 57
        gripper(s, 20 + 2, 0, top - 22, 6, finger=44, ang=0)
        X, Y = s.P(0, 57, zb + 57)
        s.arrow([(X - 26, Y - 40), (X - 26, Y + 14)])
    else:
        for a in (45, 135, 225, 315):
            px, py = 48 * math.cos(math.radians(a)), 48 * math.sin(math.radians(a))
            if px + py < 0:
                s.cyl(px, py, 6, 3, 40, 3, 'rack')
        X, Y, rx, ry = s.ell(0, 0, 6, 40)
        s.raw(f'<ellipse cx="{X:.1f}" cy="{Y:.1f}" rx="{rx:.1f}" ry="{ry:.1f}" fill="none" stroke="{ACC}" stroke-width="2" stroke-dasharray="5 5"/>')
        z0 = 6 + 26
        s.shadow(0, 0, 6, 36, op=.35)
        hold(s, kind, 0, 0, z0)
        for a in (45, 135, 225, 315):
            px, py = 48 * math.cos(math.radians(a)), 48 * math.sin(math.radians(a))
            if px + py >= 0:
                s.cyl(px, py, 6, 3, 40, 3, 'rack')
        x, y = right_of(s, kind, 0, 0, z0, 20)
        s.arrow([(x + 4, y - 30), (x + 4, y + 26)])
    return s

def ISOLATE(kind, pid):
    s = new(pid)
    x0, x1, y0, y1, h = -78, 78, -66, 66, 46
    s.shadow(0, 0, 0, 86, op=.4)
    s.raw(f'<polygon points="{s.pts([(x0, y0, 0), (x1, y0, 0), (x1, y0, h), (x0, y0, h)])}" fill="{shade("amber", .55)}"/>')
    s.raw(f'<polygon points="{s.pts([(x0, y0, 0), (x0, y1, 0), (x0, y1, h), (x0, y0, h)])}" fill="{shade("amber", .68)}"/>')
    s.raw(f'<polygon points="{s.pts([(x0, y0, 0), (x1, y0, 0), (x1, y1, 0), (x0, y1, 0)])}" fill="{shade("amber", .4)}"/>')
    d = dims(kind)
    s.shadow(0, 0, 1, d['r0'] + 6, op=.45)
    container(s, kind, 0, 0, 2)
    # 앞 벽 + 경고 띠
    for face, lv in (([(x0, y1, 0), (x1, y1, 0), (x1, y1, h), (x0, y1, h)], .78), ([(x1, y0, 0), (x1, y1, 0), (x1, y1, h), (x1, y0, h)], .55)):
        cid = s.uid('hz')
        s.defs.append(f'<clipPath id="{cid}"><polygon points="{s.pts(face)}"/></clipPath>')
        s.raw(f'<polygon points="{s.pts(face)}" fill="{shade("amber", lv)}"/>')
        (ax, ay), (bx, by) = s.P(*face[0]), s.P(*face[1])
        band = [(face[0][0], face[0][1], 14), (face[1][0], face[1][1], 14), (face[1][0], face[1][1], 30), (face[0][0], face[0][1], 30)]
        stripes = ''.join(f'<path d="M{ax + i * 14:.1f} {ay - 60:.1f} l-30 90 h7 l30 -90 z" fill="#161616"/>' for i in range(-4, 24))
        cid2 = s.uid('hb')
        s.defs.append(f'<clipPath id="{cid2}"><polygon points="{s.pts(band)}"/></clipPath>')
        s.raw(f'<g clip-path="url(#{cid2})"><polygon points="{s.pts(band)}" fill="{mix("#f8cb52", "#ffffff", .1)}"/>{stripes}</g>')
    s.raw(f'<polyline points="{s.pts([(x0, y1, h), (x1, y1, h), (x1, y0, h)])}" fill="none" stroke="{shade("amber", 1)}" stroke-width="2"/>')
    # 경고 표지
    bx, by = 262, 62
    s.raw(f'<path d="M{bx} {by - 26} L{bx + 26} {by + 18} H{bx - 26} Z" fill="#f8cb52" stroke="#161616" stroke-width="3" stroke-linejoin="round"/>'
          f'<path d="M{bx} {by - 8} V{by + 4}" stroke="#161616" stroke-width="4" stroke-linecap="round"/><circle cx="{bx}" cy="{by + 11}" r="2.4" fill="#161616"/>')
    # 놓고 올라가는 그리퍼
    gripper(s, 0, 0, 104, 26 if kind == 'BOWL' else 48, finger=40, ang=AX)
    X, Y = s.P(0, 0, 104)
    s.arrow([(X + 70, Y + 20), (X + 70, Y - 20)], w=3.5, head=7)
    return s

STEPS = ['PICK', 'WEIGH', 'SHAKE', 'SEAT', 'SOAP', 'WIPE', 'RINSE', 'RACK', 'ISOLATE']
KO = {'PICK': '집기', 'WEIGH': '무게', 'SHAKE': '털기', 'SEAT': '안착', 'SOAP': '세제', 'WIPE': '닦기', 'RINSE': '헹굼', 'RACK': '적재', 'ISOLATE': '격리'}
FN = {k: globals()[k] for k in STEPS}

def step_svg(step, kind, pid=None, cls=''):
    pid = pid or f'{step.lower()}-{kind.lower()}'
    return FN[step](kind, pid).svg(f'{KO[step]} — {"그릇" if kind == "BOWL" else "컵"}', cls)
