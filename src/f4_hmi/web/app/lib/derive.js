// 받은 값 → 화면에 그릴 값. 전부 순수 함수(화면·통신과 무관).
// 팔레트 칸·반납 구역은 메시지에 없어서 계획(plan)과 수량으로 **파생**한다 — F4-00 §4.

export const FLOW = ['PICK', 'WEIGH', 'SHAKE', 'SEAT', 'SOAP', 'WIPE', 'RINSE', 'RACK'];   // 용기 1개의 순서(IRD §8)
export const RUNNING = [...FLOW, 'ISOLATE'];

export const STEP_KO = {
  IDLE: '대기', PICK: '집기', WEIGH: '무게', SHAKE: '털기', SEAT: '안착', SOAP: '세제',
  WIPE: '닦기', RINSE: '헹굼', RACK: '적재', ISOLATE: '격리', DONE: '완료', ERROR: '오류', PAUSED: '일시 정지',
};
export const KIND_KO = { BOWL: '그릇', CUP: '컵' };
export const RESULT_KO = { DONE: '완료', ISOLATED: '격리', ERROR: '오류', SKIPPED: '건너뜀' };
export const CODE_KO = {                             // cobot_api CODES (IRD §2)
  OK: '정상', GRIP_FAIL: '집기 실패', EMPTY_ZONE: '빈 구역', LEFTOVER: '잔반 있음', LEFTOVER_REMAIN: '잔반이 남음',
  SEAT_FAIL: '안착 실패', TOOL_FAIL: '툴 집기 실패', FORCE_LIMIT: '힘 상한 초과', TIMEOUT: '시간 초과',
  RACK_JAM: '적재 걸림', RACK_FULL: '팔레트 가득 참', ROBOT_ERROR: '로봇 오류', STOPPED: '멈춤',
  TOOL_LOST: '툴 놓침',                              // 🆕 E37(9/23) — 닦는 중 수세미·솔이 그리퍼에서 빠짐
};

// 멈춤(PAUSED)의 원인 갈래 — flow 가 보내는 last_code 와 message 로 가른다(F4 9/25 · 시연 예외 6개에 맞춤).
//   'cable' 만 message 로 본다: 케이블 이상은 코드가 아니라 flow 가 last_code=ROBOT_ERROR 에 케이블 안내 문구를 얹어 보낸다(flow.handle_cable_tight).
export function pauseKind(s) {
  if (!s || s.step !== 'PAUSED') return null;
  if ((s.message || '').includes('케이블')) return 'cable';
  switch (s.last_code) {
    case 'ROBOT_ERROR': return 'robot_error';
    case 'TOOL_LOST': return 'tool_lost';
    case 'TOOL_FAIL': return 'tool_fail';         // 🆕 E52(9/25) — 홀더에서 못 집음 → 멈춤(격리 X) · 홀더 확인 → 톡
    case 'LEFTOVER_REMAIN': return 'leftover';
    case 'GRIP_FAIL': return 'grip';
    case 'RACK_FULL': return 'rack_full';
    default: return 'operator';                      // 일시 정지 버튼 · 빈 구역 뒤 HOME 실패 등
  }
}

// 멈춤 원인별 운영자 안내 — 무엇이 일어났고, 무엇을 하면 되는지(재개하면 flow 가 어디부터 이어 가는지). 문구는 SDD §7 과 같다.
export const GUIDE_KO = {
  operator: { title: '일시 정지됨', what: '운영자 요청으로 그 자리에서 멈췄습니다.',
    steps: ['재개 — 하던 동작을 이어서 합니다', '중단 — 이 용기를 격리 구역으로 보내고 다음 용기로 갑니다'] },
  cable: { title: '케이블 이상 — 확인 필요', what: '무게를 재는 동안 값이 크게 떨렸습니다(그리퍼 케이블이 당겨지거나 걸린 것으로 봅니다). 그 자리에서 멈췄습니다.',
    steps: ['케이블이 팽팽하거나 걸려 있지 않은지 확인하고 정리합니다', '로봇 손목을 가볍게 톡 칩니다(또는 재개) — 떨림을 다시 재고 정상이면 이어 갑니다', '계속 이상이면 중단 — 이 용기를 격리합니다'] },
  tool_lost: { title: '툴 놓침 — 홀더에 다시 꽂기', what: '닦는 도중 수세미·솔이 그리퍼에서 빠졌습니다. 로봇은 즉시 멈췄습니다.',
    steps: ['툴을 집어 홀더에 원래 방향으로 꽂습니다', '로봇 손목을 가볍게 톡 칩니다(또는 재개) — 툴을 다시 집고 닦기부터 이어 갑니다', '다시 집지 못하면 이 용기는 격리됩니다'] },
  tool_fail: { title: '툴 집기 실패 — 홀더 확인', what: '홀더에서 수세미·솔을 집지 못했습니다(파지 폭이 기준과 다름). 툴은 홀더에 있고 로봇은 물러나 멈췄습니다. 용기는 스펀지 홈에 그대로입니다.',
    steps: ['홀더에 툴이 원래 방향으로 제대로 꽂혀 있는지 확인하고 고쳐 꽂습니다', '로봇 손목을 가볍게 톡 칩니다(또는 재개) — 툴 집기부터 다시 합니다', '또는 중단 — 이 용기를 격리 구역으로 보냅니다'] },   // 🆕 E52
  leftover: { title: '잔반이 남음 — 용기를 든 채 멈춤', what: '두 번 털어도 잔반이 50 g 넘게 남았습니다. 용기를 든 채 무게 자세에서 멈췄습니다. (E52 9/25 이후 flow 는 멈추지 않고 곧장 격리 구역으로 보냅니다 — 이 안내는 옛 flow 용)',
    steps: ['잔반을 손으로 덜어냅니다(로봇은 멈춰 있습니다)', '재개 — 무게를 다시 재고 이어 갑니다', '또는 중단 — 이 용기를 격리 구역으로 보냅니다'] },
  grip: { title: '집기 실패 · 미끄러짐', what: '용기를 놓쳤거나 파지 폭이 변했습니다.',
    steps: ['용기가 어디 있는지 확인합니다', '재개 — 멈춘 단계부터 다시 합니다', '또는 중단 — 이 용기를 격리합니다'] },
  rack_full: { title: '팔레트 가득 참', what: '넣을 칸이 없습니다.',
    steps: ['팔레트를 식기세척기로 옮기고 새 팔레트를 놓습니다', '재개 — 적재부터 다시 합니다'] },
  robot_error: { title: '로봇 오류 — 사람이 확인·처리', what: '로봇 오류로 그 자리에서 멈췄습니다. 로봇은 스스로 움직이지도, 격리 구역으로 가지도 않습니다 — 아래 문구(message)가 지금 몇 번째 신호를 기다리는지 알려 줍니다.',
    steps: ['로봇과 주변을 확인합니다(팔·케이블이 걸려 있지 않은지) — 보호정지는 톡/재개 뒤 자동 복구를 시도하고, 안 되면 펜던트에서 해제',
            '쥔 것이 있으면: 톡 1번(또는 재개) → 그리퍼만 열립니다 → 툴은 홀더에 원래 방향으로 꽂고, 용기는 받아 치웁니다(스펀지 홈에 용기가 있으면 그것도)',
            '받아 치운 뒤 한 발 물러나 화면의 재개 버튼 → 곧게 위로 → HOME → 이 용기는 오류로 기록 · 다음 용기 (둘째 신호는 톡을 받지 않습니다 — 누르면 팔이 바로 움직입니다 · 빈손이면 첫 신호에 바로 이 단계)',
            '톡이 안 잡히면 재개 버튼 · 그리퍼가 안 열리면 rig_release.py 또는 펜던트'] },   // 🔄 E52(9/25) 2단 신호 · 9/27 신호 2 = 재개 버튼만(황인재)
};

const doneOf = (s, kind) => (kind === 'BOWL' ? s.done_bowl : s.done_cup) || 0;

// 버튼을 누를 수 있는가 — 시험 페이지(F4-02)와 같은 규칙(IRD §6)
export function buttons(d) {
  const s = d.state;
  const step = s ? s.step : null;
  const c = !!d.connected;
  return {
    start: c && step === 'IDLE',
    stop: c && RUNNING.includes(step),
    resume: c && step === 'PAUSED',
    abort: c && step === 'PAUSED' && pauseKind(s) !== 'robot_error',   // 로봇 오류면 사람이 복구한다 — 중단(격리)으로 덮지 않는다. 케이블 이상은 코드가 ROBOT_ERROR 여도 중단 가능(flow.handle_cable_tight)
  };
}

// 이번 회차의 이벤트 — 이벤트 목록에는 지난 회차 것도 섞여 있다(가짜 flow 는 대본을 반복한다).
// 끝난 용기 1개 = DONE 또는 ISOLATED 이벤트 1건이므로, 최근 것부터 (done_bowl + done_cup + isolated) 건까지가 이번 회차다.
export function currentRun(d) {
  const s = d.state || {};
  let need = (s.done_bowl || 0) + (s.done_cup || 0) + (s.isolated || 0);
  const out = [];
  for (const e of d.events || []) {
    if (need <= 0) break;
    out.push(e);
    if (e.result === 'DONE' || e.result === 'ISOLATED') need -= 1;
  }
  return out;
}

// 팔레트 칸 — rack_order 앞에서부터 done 개가 찼다(F4-00 §4). 지금 적재 중인 칸은 표시한다.
export function pallet(d) {
  const order = (d.plan && d.plan.rack_order) || {};
  const s = d.state || {};
  const out = [];
  for (const kind of ['BOWL', 'CUP']) {
    const done = doneOf(s, kind);
    (order[kind] || []).forEach((slot, i) => out.push({
      slot, kind, n: i + 1,                           // n = 그 종류에서 몇 번째로 넣는 칸(그릇 1·2 · 컵 1·2)
      filled: i < done,
      loading: i === done && s.step === 'RACK' && s.kind === kind,
    }));
  }
  return out;
}

// 반납 구역 — 계획 수에서 끝난 수(완료 + 격리)를 뺀 것이 남은 용기. E9: 구역마다 집는 자리는 1개(내리막 공급)
export function zones(d) {
  const plan = (d.plan && d.plan.plan) || [];
  const s = d.state || {};
  const run = currentRun(d);
  const running = RUNNING.includes(s.step) || s.step === 'PAUSED';
  const perKind = (k) => plan.filter((q) => q.kind === k).length;
  return plan.map((p) => {
    // 목표 수량은 flow 가 보내는 값(target_*)이 기준 — 설정 파일의 계획과 다를 수 있다(가짜 대본 · 계획을 바꾼 실행).
    // 한 종류에 구역이 하나면 그 값을 그대로 쓴다.
    const target = kind => (kind === 'BOWL' ? s.target_bowl : s.target_cup);
    const count = s && target(p.kind) != null && perKind(p.kind) === 1 ? target(p.kind) : p.count;
    const isolated = run.filter((e) => e.result === 'ISOLATED' && e.zone_id === p.zone).length;
    const finished = Math.min(count, doneOf(s, p.kind) + isolated);
    // 빈 구역(EMPTY_ZONE) — flow 는 그 구역을 건너뛰고(SKIPPED 이벤트) 바로 다음 구역으로 간다. 상태는 1초 남짓만 스친다
    // → 이벤트로도 본다. 건너뛴 구역에는 더 집을 용기가 없다(남음 0).
    const empty = (s.last_code === 'EMPTY_ZONE' && s.zone_id === p.zone)
      || run.some((e) => e.result === 'SKIPPED' && e.zone_id === p.zone);
    const active = running && s.zone_id === p.zone && !empty;
    return {
      zone: p.zone, kind: p.kind, count,
      left: empty ? 0 : count - finished,
      status: active ? '처리 중' : empty ? '비었음' : count === 0 ? '계획 없음' : finished >= count ? '완료' : '대기',
    };
  });
}

// 사이클 타임 — 이번 회차에 끝난 용기의 소요 시간. recent = 최근 8개(오래된 것 → 최근 것, 작은 막대 그림용)
export function cycle(d) {
  const ds = currentRun(d).filter((e) => e.result === 'DONE' || e.result === 'ISOLATED').map((e) => e.duration_s || 0);
  if (!ds.length) return null;
  return { last: ds[0], mean: ds.reduce((a, b) => a + b, 0) / ds.length, n: ds.length, recent: ds.slice(0, 8).reverse() };
}

// 몇 번째 용기인가 — 끝난 용기(완료 + 격리) 수와 계획 수
export function progress(d) {
  const s = d.state || {};
  return {
    finished: (s.done_bowl || 0) + (s.done_cup || 0) + (s.isolated || 0),
    total: (s.target_bowl || 0) + (s.target_cup || 0),
  };
}

// 다음 할 일 — "지금 하는 일" 칸의 한 줄. 적재 뒤에는 다음 용기(남았으면) 또는 끝
export function nextStep(step, p) {
  if (step === 'IDLE') return '시작 누르기';
  if (step === 'DONE') return '팔레트 확인';
  if (step === 'PAUSED') return '재개 또는 중단';
  if (step === 'ERROR') return '운영자 복구';
  if (step === 'WEIGH') return '털기 또는 안착';               // 잔반(50 g 이상)이 있을 때만 턴다
  const i = FLOW.indexOf(step);
  if (i >= 0 && i < FLOW.length - 1) return STEP_KO[FLOW[i + 1]];
  return p.finished + 1 < p.total ? '다음 용기 집기' : '마지막 — 완료';
}

// 소모품 — 교체까지 남은 횟수. 한도의 15 % 이하로 남으면 warn(곧 교체), 0 이면 bad(교체 필요)
function remain(used, max) {
  if (used == null) return null;
  if (!max) return { used, max: null, left: null, level: 'ok' };
  const left = Math.max(0, max - used);
  const level = left === 0 ? 'bad' : left <= Math.max(1, Math.round(max * 0.15)) ? 'warn' : 'ok';
  return { used, max, left, level };
}
export function consumables(d) {
  const s = d.state || {};
  const c = (d.plan && d.plan.consumables) || {};
  return { sponge: remain(s.sponge_uses, c.sponge_max_uses), soap: remain(s.soap_dips, c.soap_max_dips), rinse: s.rinse_dips };
}

// 알람 — 멈춤(PAUSED)이면 원인 갈래(pauseKind)로 붉은색(로봇 오류)/주황(그 밖) · 운전 중이면 마지막 코드가 정상이 아닐 때 노란 경고
export function alarm(d) {
  const s = d.state;
  if (!s) return null;
  const kind = pauseKind(s);
  if (kind) return { level: kind === 'robot_error' ? 'error' : 'pause', kind, guide: GUIDE_KO[kind], code: s.last_code, message: s.message };
  if (s.last_code && s.last_code !== 'OK') return { level: 'warn', kind: null, guide: null, code: s.last_code, message: s.message };   // 재개해 진행 중 — 최근 원인만
  return null;
}

// 최근 문제 — 완료가 아닌 이벤트(격리·오류·건너뜀) 최근 5건
export function problems(d) {
  return (d.events || []).filter((e) => e.result && e.result !== 'DONE').slice(0, 5);
}

// 이벤트의 원인 — 운영자가 중단(/flow/abort)하면 flow 는 ISOLATED 에 **그때의 last_code** 를 붙인다.
// 일시 정지 → 중단이면 그 값이 OK 라서 "격리 · 정상" 으로 보인다 → "운영자 중단" 으로 풀어 쓴다(flow.py abort_container)
export function why(e) {
  if (e.result === 'ISOLATED' && (!e.code || e.code === 'OK' || e.code === 'STOPPED')) return '운영자 중단';
  return CODE_KO[e.code] || e.code || '-';
}

export function clock(stamp) {
  if (!stamp) return '-';
  const t = new Date(stamp * 1000);
  return [t.getHours(), t.getMinutes(), t.getSeconds()].map((v) => String(v).padStart(2, '0')).join(':');
}
