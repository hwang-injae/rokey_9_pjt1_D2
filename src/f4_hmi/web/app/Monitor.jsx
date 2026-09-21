'use client';
// 운영 화면 1장 — F4-00 §3. HMI 는 **보여 주고 전달만** 한다(흐름·복구 판단·로봇 동작은 하지 않는다).
import { useRef, useState } from 'react';
import { useHmi } from './lib/useHmi';
import {
  FLOW, RUNNING, STEP_KO, KIND_KO, RESULT_KO, CODE_KO,
  buttons, pallet, zones, cycle, alarm, problems, clock, why,
} from './lib/derive';

const BTN_KO = { start: '시작', stop: '일시 정지', resume: '재개', abort: '중단' };
const KEY = 'prewash.lastStep';
function recall() { try { return sessionStorage.getItem(KEY) || ''; } catch { return ''; } }   // 개인 창·막힌 저장소에서도 화면은 뜬다
function remember(v) { try { sessionStorage.setItem(KEY, v); } catch { /* 없어도 된다 */ } }

export default function Monitor() {
  const { d, mode, force, press } = useHmi();
  const [reply, setReply] = useState(null);
  // 일시 정지됐을 때 "어느 단계에서" 를 보여 주려고 기억한다 — flow 가 보내는 값(FlowState)에는 그 칸이 없다.
  // 같은 탭에서 새로고침해도 잊지 않게 탭 저장소(sessionStorage)에도 둔다. 멈춘 **뒤에** 새 탭으로 열면 모른다.
  const lastRunning = useRef(null);
  const s = d.state;
  if (lastRunning.current === null) lastRunning.current = recall();
  if (s && RUNNING.includes(s.step) && lastRunning.current !== s.step) { lastRunning.current = s.step; remember(s.step); }
  if (s && (s.step === 'IDLE' || s.step === 'DONE') && lastRunning.current) { lastRunning.current = ''; remember(''); }

  const can = buttons(d);
  async function onPress(name) {
    if (name === 'abort' && !window.confirm('이 용기를 격리 구역으로 보내고 다음 용기로 넘어갑니다.\n중단할까요?')) return;
    setReply({ pending: true, text: `${BTN_KO[name]} 보내는 중…` });
    const r = await press(name);
    setReply({ ok: r.ok, text: `${r.ok ? '✔' : '✖'} ${BTN_KO[name]}: ${r.message}${r.latency_ms != null ? ` (${r.latency_ms} ms)` : ''}` });
  }

  return (
    <div className="page">
      <TopBar d={d} can={can} onPress={onPress} />
      <Alarm d={d} step={lastRunning.current || null} />
      <Controls can={can} onPress={onPress} reply={reply} />
      <StepBar d={d} paused={s && s.step === 'PAUSED' ? lastRunning.current || null : null} />
      <div className="grid">
        <Zones d={d} />
        <Pallet d={d} />
        <Counts d={d} />
      </div>
      <ForceGraph d={d} force={force} />
      <History d={d} />
      <footer className="dim small">
        받는 방식: {mode} · 받은 상태 메시지 {d.received}건 · 점검용 <a href="/test">시험 페이지</a>
      </footer>
    </div>
  );
}

function TopBar({ d, can, onPress }) {
  const conn = !d.server ? { cls: 'bad', text: 'HMI 서버에 닿지 않는다' }
    : d.connected ? { cls: 'ok', text: 'flow 연결됨' }
    : d.state ? { cls: 'bad', text: 'flow 연결 끊김 — 마지막 값을 보여 주는 중' }
    : { cls: 'bad', text: 'flow 의 방송을 아직 못 받았다' };
  const grip = d.gripping == null ? { cls: 'dim', text: '파지 —' }
    : d.gripping ? { cls: 'on', text: '✊ 파지 중' } : { cls: 'off', text: '✋ 파지 안 함' };
  return (
    <header className="top">
      <div className="brand">PreWash-Cell</div>
      <div className={`pill ${conn.cls}`}><span className="dot" />{conn.text}</div>
      <div className={`pill grip ${grip.cls}`}>{grip.text}</div>
      <div className="spacer" />
      <div className="stopbox">
        <button className="btn stop" disabled={!can.stop} onClick={() => onPress('stop')}>일시 정지</button>
        <div className="dim tiny">즉시 멈춘다 · 재개하면 이어서 · 급하면 로봇 E-Stop</div>
      </div>
    </header>
  );
}

function Alarm({ d, step }) {
  const a = alarm(d);
  if (!a) return null;
  const label = CODE_KO[a.code] || a.code;
  if (a.level === 'error') {
    return (
      <section className="alarm error">
        <div className="alarm-title">🚨 운영자 복구 필요 — {label}</div>
        {a.message && <div className="alarm-msg">{a.message}</div>}
        <ol className="alarm-steps">
          <li>로봇과 주변을 확인한다(용기·툴이 걸려 있지 않은지)</li>
          <li>필요하면 <code>release_force.py</code> 로 힘제어를 푼다</li>
          <li><b>재개</b> 를 누른다 — 1초 안에 대답이 없으면 flow_node 를 다시 띄운다</li>
        </ol>
      </section>
    );
  }
  if (a.level === 'pause') {
    return (
      <section className="alarm pause">
        <div className="alarm-title">일시 정지됨{step ? ` — ${STEP_KO[step]} 단계` : ''}</div>
        <div className="alarm-msg">
          {a.message || '운영자 요청'} · 확인한 뒤 <b>재개</b>(하던 동작을 이어서) 또는 <b>중단</b>(이 용기를 격리)
          {a.code && a.code !== 'OK' ? ` · 원인: ${label}` : ''}
        </div>
      </section>
    );
  }
  return (
    <section className="alarm warn">
      <div className="alarm-title">⚠ {label}</div>
      {a.message && <div className="alarm-msg">{a.message}</div>}
    </section>
  );
}

function Controls({ can, onPress, reply }) {
  return (
    <section className="controls">
      <button className="btn go" disabled={!can.start} onClick={() => onPress('start')}>시작</button>
      <button className="btn go" disabled={!can.resume} onClick={() => onPress('resume')}>재개</button>
      <button className="btn warn" disabled={!can.abort} onClick={() => onPress('abort')}>중단</button>
      <div className={`reply ${reply ? (reply.pending ? 'dim' : reply.ok ? 'ok' : 'bad') : 'dim'}`}>
        {reply ? reply.text : '버튼을 누르면 flow 의 대답이 여기에 나온다'}
      </div>
    </section>
  );
}

function StepBar({ d, paused }) {
  const s = d.state;
  const step = s ? s.step : null;
  const at = paused || step;                         // 일시 정지 중이면 멈춘 단계를 가리킨다
  const idx = FLOW.indexOf(at);
  const finished = step === 'DONE';
  return (
    <section className="stepbar">
      <div className="steps">
        {FLOW.map((name, i) => {
          const cls = finished || (idx >= 0 && i < idx) ? 'past'
            : i === idx ? (paused ? 'now paused' : 'now') : '';
          return (
            <div key={name} className={`step ${cls}`}>
              <span className="mark">{cls.startsWith('past') ? '✓' : i + 1}</span>
              <span>{STEP_KO[name]}</span>
            </div>
          );
        })}
        {step === 'ISOLATE' && <div className="step now isolate"><span className="mark">!</span><span>격리 중</span></div>}
      </div>
      <div className="current">
        <div className="big-state">{step ? STEP_KO[step] || step : '-'}</div>
        <div className="dim">{s && s.kind ? `${KIND_KO[s.kind] || s.kind} · ${s.zone_id || '-'}` : '처리 중인 용기 없음'}</div>
      </div>
    </section>
  );
}

function Zones({ d }) {
  const zs = zones(d);
  return (
    <section className="card">
      <h2>반납 구역</h2>
      {!zs.length && <div className="dim">계획이 아직 없다</div>}
      {zs.map((z) => (
        <div key={z.zone} className="zone">
          <div className="zone-name">{KIND_KO[z.kind]} <span className="dim small">{z.zone}</span></div>
          <div className="cups">
            {Array.from({ length: z.count }, (_, i) => <span key={i} className={`cup ${i < z.left ? 'full' : ''}`} />)}
          </div>
          <div className={`zone-status ${z.status === '처리 중' ? 'ok' : z.status === '비었음' ? 'warn' : 'dim'}`}>
            {z.status} · 남음 {z.left}
          </div>
        </div>
      ))}
    </section>
  );
}

// 팔레트 — 실제 배치를 위에서 본 모양(황인재 9/21 그림). 넣는 순서 그릇 1 → 그릇 2 → 컵 1 → 컵 2 = params.yaml flow.rack_order
//   ┌──────────────────────┬────────┬────────┐
//   │            (컵 1)     │ (그릇 2)│ (그릇 1)│   그릇은 세로로 세워 꽂는다(긴 타원)
//   │ (컵 2)                │        │        │
//   └──────────────────────┴────────┴────────┘
const RACK_VIEW = { w: 718, h: 420, walls: [361, 541] };
const RACK_SHAPES = {
  'BOWL-1': { cx: 631, cy: 210, rx: 74, ry: 190 },
  'BOWL-2': { cx: 451, cy: 210, rx: 74, ry: 190 },
  'CUP-1': { cx: 263, cy: 113, r: 82 },
  'CUP-2': { cx: 98, cy: 321, r: 82 },
};

function Pallet({ d }) {
  const cells = pallet(d);
  const filled = cells.filter((c) => c.filled).length;
  const full = cells.length > 0 && filled >= cells.length;       // 이번 회차가 칸을 다 채웠다 → 사람이 팔레트를 바꾼다
  const t = d.totals || {};
  return (
    <section className="card">
      <h2>팔레트 <span className="dim tiny">넣는 순서 — 그릇 1 → 그릇 2 → 컵 1 → 컵 2</span></h2>
      <div className="rack-head">
        <b className={full ? 'ok' : ''}>이번 팔레트 {filled} / {cells.length}칸</b>
        {full && <span className="rack-full">✔ 가득 참 — 식기세척기로 옮기고 새 팔레트를 놓는다</span>}
      </div>
      <svg viewBox={`0 0 ${RACK_VIEW.w} ${RACK_VIEW.h}`} className="rack" role="img" aria-label="팔레트 배치 상태">
        <rect x="2" y="2" width={RACK_VIEW.w - 4} height={RACK_VIEW.h - 4} className="rack-frame" />
        {RACK_VIEW.walls.map((x) => <line key={x} x1={x} y1="2" x2={x} y2={RACK_VIEW.h - 2} className="rack-frame" />)}
        {cells.map((c) => {
          const sh = RACK_SHAPES[`${c.kind}-${c.n}`];
          if (!sh) return null;
          const state = c.filled ? 'filled' : c.loading ? 'loading' : '';
          return (
            <g key={c.slot} className={`rack-slot ${state}`}>
              <title>{c.slot}</title>
              {sh.r ? <circle cx={sh.cx} cy={sh.cy} r={sh.r} /> : <ellipse cx={sh.cx} cy={sh.cy} rx={sh.rx} ry={sh.ry} />}
              <text x={sh.cx} y={sh.cy - 4} className="rack-label">{KIND_KO[c.kind]} {c.n}</text>
              <text x={sh.cx} y={sh.cy + 30} className="rack-status">{c.filled ? '적재됨' : c.loading ? '적재 중' : '비어 있음'}</text>
            </g>
          );
        })}
      </svg>
      <div className="rack-totals">
        <div><span className="dim">처리한 팔레트</span><b>{t.pallets ?? 0}장</b></div>
        <div><span className="dim">누적</span><b>그릇 {t.bowls ?? 0} · 컵 {t.cups ?? 0} · 격리 {t.isolated ?? 0}</b></div>
      </div>
      <div className="dim tiny">누적은 HMI 를 켠 뒤부터 · 끝난 회차 {t.runs ?? 0}번 · 팔레트는 칸을 다 채우고 끝난 회차만 센다</div>
    </section>
  );
}

// warn = 소모품처럼 한도에 가까워지면 주황으로 알릴 막대(수량 진행률은 다 차도 경고가 아니다)
function Bar({ value, max, warn = false }) {
  const pct = max ? Math.min(100, (value / max) * 100) : 0;
  return <div className="bar"><i style={{ width: `${pct}%` }} className={warn && pct >= 90 ? 'hot' : ''} /></div>;
}

function Counts({ d }) {
  const s = d.state || {};
  const c = (d.plan && d.plan.consumables) || {};
  const cy = cycle(d);
  return (
    <section className="card">
      <h2>수량</h2>
      <div className="count-row"><span>그릇</span><b>{s.done_bowl ?? '-'} / {s.target_bowl ?? '-'}</b></div>
      <Bar value={s.done_bowl || 0} max={s.target_bowl} />
      <div className="count-row"><span>컵</span><b>{s.done_cup ?? '-'} / {s.target_cup ?? '-'}</b></div>
      <Bar value={s.done_cup || 0} max={s.target_cup} />
      <div className="count-row"><span>격리</span><b className={s.isolated ? 'warn' : ''}>{s.isolated ?? '-'}</b></div>
      <h2 className="gap">소모품</h2>
      <div className="count-row"><span>수세미</span><b>{s.sponge_uses ?? '-'}{c.sponge_max_uses ? ` / ${c.sponge_max_uses}` : ''}</b></div>
      <Bar value={s.sponge_uses || 0} max={c.sponge_max_uses} warn />
      <div className="count-row"><span>세제 담금</span><b>{s.soap_dips ?? '-'}{c.soap_max_dips ? ` / ${c.soap_max_dips}` : ''}</b></div>
      <Bar value={s.soap_dips || 0} max={c.soap_max_dips} warn />
      <div className="count-row"><span>헹굼 담금</span><b>{s.rinse_dips ?? '-'}</b></div>
      <h2 className="gap">사이클 타임</h2>
      <div className="count-row">
        <span>최근 · 평균</span>
        <b>{cy ? `${cy.last.toFixed(1)} s · ${cy.mean.toFixed(1)} s` : '-'}</b>
      </div>
    </section>
  );
}

// 닦는 힘 — /cell/force(닦는 동안만 10 Hz). 목표선(그릇만 — 컵은 힘제어 없이 돌린다)·상한선은 params.yaml f3 에서
// (브리지가 plan.force 로 넘긴다 — 숫자를 화면 코드에 쓰지 않는다). 가로축은 **마지막 값 기준 최근 10초**라 닦기를 멈추면 그래프도 멈춘다.
const G = { w: 1000, h: 170, win: 10, left: 44, right: 12, top: 10, bottom: 24 };

function ForceGraph({ d, force }) {
  const s = d.state || {};
  const kind = s.kind || 'BOWL';
  const ref = ((d.plan && d.plan.force) || {})[kind] || {};
  const wiping = d.force_n != null;                 // 브리지가 0.5초 넘게 힘을 못 받으면 비운다 → '닦는 중 아님'
  const last = force.length ? force[force.length - 1] : null;
  const pts = last ? force.filter((p) => last.t - p.t <= G.win) : [];
  const top = Math.max(ref.limit_n || 10, ...pts.map((p) => p.n)) * 1.15;
  const x = (t) => G.left + (1 - (last.t - t) / G.win) * (G.w - G.left - G.right);
  const y = (n) => G.h - G.bottom - (n / top) * (G.h - G.top - G.bottom);
  const ticks = [0, 5, 10, 15].filter((v) => v <= top);
  return (
    <section className="card">
      <h2>닦는 힘 <span className="dim tiny">{KIND_KO[kind]} 닦기 · 최근 {G.win}초</span></h2>
      <div className="force-head">
        <b className={wiping ? 'force-now' : 'force-now dim'}>{wiping ? `${d.force_n.toFixed(1)} N` : '닦는 중 아님'}</b>
        <span className="dim">
          {ref.target_n != null ? `목표 ${ref.target_n} N` : '힘 목표 없음(솔을 돌리고 오르내린다)'} · 상한 {ref.limit_n ?? '-'} N — 넘으면 즉시 물러난다
        </span>
      </div>
      <svg viewBox={`0 0 ${G.w} ${G.h}`} className={wiping ? 'force' : 'force idle'} role="img" aria-label="닦는 힘 그래프">
        {ticks.map((v) => (
          <g key={v}>
            <line x1={G.left} x2={G.w - G.right} y1={y(v)} y2={y(v)} className="force-grid" />
            <text x={G.left - 8} y={y(v) + 5} className="force-axis">{v}</text>
          </g>
        ))}
        {ref.limit_n != null && (
          <g className="force-limit">
            <line x1={G.left} x2={G.w - G.right} y1={y(ref.limit_n)} y2={y(ref.limit_n)} />
            <text x={G.w - G.right - 4} y={y(ref.limit_n) - 6}>상한 {ref.limit_n} N</text>
          </g>
        )}
        {ref.target_n != null && (
          <g className="force-target">
            <line x1={G.left} x2={G.w - G.right} y1={y(ref.target_n)} y2={y(ref.target_n)} />
            <text x={G.w - G.right - 4} y={y(ref.target_n) - 6}>목표 {ref.target_n} N</text>
          </g>
        )}
        {pts.length > 1 && <polyline className="force-line" points={pts.map((p) => `${x(p.t).toFixed(1)},${y(p.n).toFixed(1)}`).join(' ')} />}
        {!pts.length && <text x={G.w / 2} y={G.h / 2} className="force-empty">아직 닦은 기록이 없다</text>}
      </svg>
    </section>
  );
}

// 이력 — 끝난 용기 1개 = /flow/event 1건. 최근 것부터 20건.
//   지금은 브리지가 메모리에 들고 있는 최근 50건(HMI 를 켠 뒤부터) — 껐다 켜도 남게 하는 저장은 F4-04(SQLite).
//   [전체 / 문제만] — 문제만 = 완료가 아닌 것(격리 · 오류 · 건너뜀).
const HISTORY_ROWS = 20;

function History({ d }) {
  const [onlyProblems, setOnlyProblems] = useState(false);
  const all = d.events || [];
  const rows = (onlyProblems ? problems({ events: all, state: d.state }) : all).slice(0, HISTORY_ROWS);
  const nProblems = all.filter((e) => e.result && e.result !== 'DONE').length;
  return (
    <section className="card">
      <div className="history-head">
        <h2>이력 <span className="dim tiny">끝난 용기마다 한 줄 · 최근 것부터</span></h2>
        <div className="tabs">
          <button className={onlyProblems ? '' : 'on'} onClick={() => setOnlyProblems(false)}>전체 {all.length}</button>
          <button className={onlyProblems ? 'on' : ''} onClick={() => setOnlyProblems(true)}>문제만 {nProblems}</button>
        </div>
      </div>
      {!rows.length ? (
        <div className="dim">{onlyProblems ? '문제 있던 용기가 없다' : '아직 끝난 용기가 없다'}</div>
      ) : (
        <div className="scroll-x"><table className="list history">
          <thead>
            <tr><th>시각</th><th>종류</th><th>구역 → 칸</th><th>무게 전 → 후</th><th>결과</th><th>원인</th><th>소요</th><th>시도</th></tr>
          </thead>
          <tbody>
            {rows.map((e, i) => (
              <tr key={`${e.stamp}-${i}`} className={e.result === 'ERROR' ? 'bad' : e.result === 'DONE' ? '' : 'warn'}>
                <td>{clock(e.stamp)}</td>
                <td>{KIND_KO[e.kind] || e.kind || '-'}</td>
                <td>{e.zone_id || '-'} → {e.rack_slot ? e.rack_slot.replace('RACK_', '') : e.result === 'ISOLATED' ? '격리' : '-'}</td>
                <td className="num">{e.weight_before_g || e.weight_after_g ? `${Math.round(e.weight_before_g)} → ${Math.round(e.weight_after_g)} g` : '-'}</td>
                <td>{RESULT_KO[e.result] || e.result}</td>
                <td>{e.result === 'DONE' ? '-' : why(e)}</td>
                <td className="num">{e.duration_s ? `${e.duration_s.toFixed(1)} s` : '-'}</td>
                <td className="num">{e.attempts || '-'}</td>
              </tr>
            ))}
          </tbody>
        </table></div>
      )}
      <div className="dim tiny gap-top">HMI 를 켠 뒤 받은 것만 보인다 — 껐다 켜도 남게 하는 저장은 다음 작업(F4-04)</div>
    </section>
  );
}
