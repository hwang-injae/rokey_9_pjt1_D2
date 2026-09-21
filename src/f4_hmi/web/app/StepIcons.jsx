// 단계 그림 — 선 그림(SVG)을 코드로 그린다(이미지 파일 없음 · 황인재 9/21 A안).
//   용기는 종류에 따라 그릇(넓고 얕다) / 컵(좁고 깊다), 툴은 그릇 = 수세미 / 컵 = 솔(결정 E18 — 세제는 툴 홀더의 비눗물).
//   선 색은 카드의 글자색(currentColor)을 따라가고, 채움 색은 globals.css 의 .si-* — 밝은/어두운 화면을 따라간다.
//   그림 칸은 120 × 90.

// 집게 — 가운데 x, 손바닥 높이 t, 벌린 반폭 w
const grip = (x, t, w) => `M${x} 0 V${t} M${x - w} ${t} H${x + w} M${x - w} ${t} V${t + 26} M${x + w} ${t} V${t + 26}`;
// 용기 — 윗면 가운데 (x, y)
const bowl = (x, y) => `M${x - 16} ${y} H${x + 16} L${x + 11} ${y + 18} Q${x} ${y + 23} ${x - 11} ${y + 18} Z`;
const cup = (x, y) => `M${x - 11} ${y - 4} H${x + 11} L${x + 8} ${y + 24} H${x - 8} Z`;
const ware = (kind, x, y) => (kind === 'CUP' ? cup(x, y) : bowl(x, y));
const gw = (kind) => (kind === 'CUP' ? 13 : 18);                  // 집게 반폭 — 컵은 몸통을, 그릇은 벽을 잡는다

// 화살표 — 선 + 머리(마커를 안 쓴다: 여러 그림이 한 화면에 있어도 id 가 안 겹친다)
const up = (x, y1, y2) => `M${x} ${y1} V${y2} M${x - 6} ${y2 + 6} L${x} ${y2} L${x + 6} ${y2 + 6}`;
const down = (x, y1, y2) => `M${x} ${y1} V${y2} M${x - 6} ${y2 - 6} L${x} ${y2} L${x + 6} ${y2 - 6}`;

// 툴 머리 — 그릇이면 수세미 덩어리, 컵이면 솔(털)
function ToolHead({ kind, x, y }) {
  if (kind === 'CUP') {
    return (
      <>
        <rect x={x - 5} y={y} width="10" height="7" rx="2" className="si-tool" />
        <path d={[-8, -4, 0, 4, 8].map((dx) => `M${x + dx} ${y + 8} V${y + 22}`).join(' ')} className="si-bristle" />
      </>
    );
  }
  return <rect x={x - 11} y={y} width="22" height="15" rx="3" className="si-tool" />;
}

const DRAW = {
  PICK: (k) => (
    <>
      <path d={grip(60, 12, gw(k))} />
      <path d={ware(k, 60, 26)} className="si-ware" />
      <path d="M14 70 L106 64" />
      <path d={up(102, 48, 20)} />
    </>
  ),
  WEIGH: (k) => (
    <>
      <path d={grip(48, 12, gw(k))} />
      <path d={ware(k, 48, 26)} className="si-ware" />
      <path d={down(48, 58, 74)} />
      <rect x="82" y="18" width="30" height="26" rx="4" />
      <text x="97" y="36" className="si-text">g</text>
    </>
  ),
  SHAKE: (k) => (
    <>
      <g transform="rotate(-22 60 28)">
        <path d={grip(60, 12, gw(k))} />
        <path d={ware(k, 60, 26)} className="si-ware" />
      </g>
      <path d="M22 16 Q14 28 22 40 M98 16 Q106 28 98 40" />
      <circle cx="56" cy="56" r="2" className="si-dot" /><circle cx="64" cy="60" r="2" className="si-dot" /><circle cx="58" cy="64" r="2" className="si-dot" />
      <path d="M36 68 H84 L80 88 H40 Z" />
    </>
  ),
  SEAT: (k) => (
    <>
      <path d={grip(56, 8, gw(k))} />
      <path d={ware(k, 56, 22)} className="si-ware" />
      <rect x="14" y="62" width="88" height="18" rx="3" />
      <path d="M24 62 Q30 57 36 62 Q42 57 48 62 Q54 57 60 62 Q66 57 72 62 Q78 57 84 62 Q90 57 96 62" />
      <path d={down(108, 16, 46)} />
    </>
  ),
  SOAP: (k) => (
    <>
      <path d="M50 0 H70 M50 0 V8 M70 0 V8 M60 4 V30" />
      <ToolHead kind={k} x={60} y={30} />
      <path d="M40 44 H80 L75 88 H45 Z" />
      <circle cx="52" cy="66" r="3" /><circle cx="66" cy="74" r="4" /><circle cx="58" cy="80" r="2.5" />
      <circle cx="90" cy="32" r="3" /><circle cx="96" cy="22" r="2" />
    </>
  ),
  WIPE: (k) => (k === 'CUP' ? (
    <>
      <path d="M60 0 V28" />
      <ToolHead kind={k} x={60} y={28} />
      <path d="M36 16 V78 Q36 86 44 86 H76 Q84 86 84 78 V16" className="si-inside" />
      <path d={`${up(100, 58, 22)} ${down(100, 30, 66)}`} />
      <path d="M44 72 A16 5 0 1 0 76 72" />
    </>
  ) : (
    <>
      <path d="M60 0 V40" />
      <ToolHead kind={k} x={60} y={40} />
      <path d="M18 30 Q18 82 60 82 Q102 82 102 30" className="si-inside" />
      <path d="M34 62 A26 8 0 1 0 86 62 M80 58 L86 62 L79 66" />
    </>
  )),
  RINSE: (k) => (
    <>
      <path d={grip(60, 10, gw(k))} />
      <path d={ware(k, 60, 24)} className="si-ware" />
      <path d="M14 58 H106 V88 H14 Z" className="si-water" />
      <path d="M14 38 V88 H106 V38" />
      <path d="M14 50 Q24 44 34 50 T54 50 T74 50 T94 50 T106 48" className="si-wave" />
    </>
  ),
  RACK: (k) => (k === 'CUP' ? (
    <>
      <path d={grip(56, 8, gw(k))} />
      <path d={cup(56, 24)} className="si-ware" />
      <path d="M12 88 H104 M28 88 V64 M84 88 V64" />
      <ellipse cx="56" cy="66" rx="18" ry="5" />
      <path d={down(106, 14, 42)} />
    </>
  ) : (
    <>
      <path d="M56 0 V8 M44 8 H68 M44 8 V26 M68 8 V26" />
      <ellipse cx="56" cy="44" rx="9" ry="22" className="si-ware" />
      <path d="M12 88 H104 M24 88 V52 M40 88 V52 M72 88 V52 M88 88 V52" />
      <path d={down(106, 14, 42)} />
    </>
  )),
  ISOLATE: (k) => (
    <>
      <path d="M18 38 H102 V88 H18 Z" />
      <path d={ware(k, 60, 54)} className="si-ware" />
      <circle cx="98" cy="22" r="12" className="si-alert" />
      <path d="M98 15 V24 M98 29 V29.5" className="si-alert" />
    </>
  ),
};

export default function StepIcon({ step, kind }) {
  const draw = DRAW[step];
  if (!draw) return null;
  return (
    <svg viewBox="0 0 120 92" className="si" aria-hidden="true">
      {draw(kind === 'CUP' ? 'CUP' : 'BOWL')}
    </svg>
  );
}
