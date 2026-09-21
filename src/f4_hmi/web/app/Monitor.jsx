'use client';
// 운영 화면 1장 — F4-00 §3. HMI 는 **보여 주고 전달만** 한다(흐름·복구 판단·로봇 동작은 하지 않는다).
import { useRef, useState } from 'react';
import { useHmi } from './lib/useHmi';
import StepIcon from './StepIcons';
import {
  FLOW, RUNNING, STEP_KO, KIND_KO, RESULT_KO, CODE_KO,
  buttons, pallet, zones, cycle, alarm, problems, clock, why,
} from './lib/derive';

const BTN_KO = { start: '시작', stop: '일시 정지', resume: '재개', abort: '중단' };
const KEY = 'prewash.lastStep';
function recall() { try { return sessionStorage.getItem(KEY) || ''; } catch { return ''; } }   // 개인 창·막힌 저장소에서도 화면은 뜬다
function remember(v) { try { sessionStorage.setItem(KEY, v); } catch { /* 없어도 된다 */ } }

export default function Monitor() {
  const { d, mode, press } = useHmi();
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
  return (
    <header className="top">
      <div className="brand">PreWash-Cell</div>
      <div className={`pill ${conn.cls}`}><span className="dot" />{conn.text}</div>
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

// 단계 표시줄 — 그림 카드 8장(+ 격리). 지금 단계 = 파랑 · 끝난 단계 = ✓ 초록 · 일시 정지 = 주황 (황인재 9/21 A안)
//   그림 속 용기는 지금 처리 중인 종류(그릇/컵)를 따라간다. 처리 중인 용기가 없으면 그릇.
function StepBar({ d, paused }) {
  const s = d.state;
  const step = s ? s.step : null;
  const kind = s && s.kind === 'CUP' ? 'CUP' : 'BOWL';
  const at = paused || step;                         // 일시 정지 중이면 멈춘 단계를 가리킨다
  const idx = FLOW.indexOf(at);
  const finished = step === 'DONE';
  return (
    <section className="stepbar">
      <div className="stepcards">
        {FLOW.map((name, i) => {
          const past = finished || (idx >= 0 && i < idx);
          const now = !finished && i === idx;
          const cls = past ? 'past' : now ? (paused ? 'now paused' : 'now') : '';
          return (
            <div key={name} className={`stepcard ${cls}`}>
              <StepIcon step={name} kind={kind} />
              <div className="stepcard-label"><span className="mark">{past ? '✓' : i + 1}</span>{STEP_KO[name]}</div>
            </div>
          );
        })}
        <div className={`stepcard iso ${step === 'ISOLATE' ? 'now isolate' : ''}`}>
          <StepIcon step="ISOLATE" kind={kind} />
          <div className="stepcard-label"><span className="mark">!</span>격리</div>
        </div>
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
