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
    abort: c && step === 'PAUSED' && s.last_code !== 'ROBOT_ERROR',   // 로봇 오류면 사람이 복구한다 — 중단(격리)으로 덮지 않는다
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
      slot, kind,
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

// 사이클 타임 — 이번 회차에 끝난 용기의 소요 시간
export function cycle(d) {
  const ds = currentRun(d).filter((e) => e.result === 'DONE' || e.result === 'ISOLATED').map((e) => e.duration_s || 0);
  if (!ds.length) return null;
  return { last: ds[0], mean: ds.reduce((a, b) => a + b, 0) / ds.length, n: ds.length };
}

// 알람 — 로봇 오류(붉은색) > 일시 정지 > 경고(주황)
export function alarm(d) {
  const s = d.state;
  if (!s) return null;
  if (s.last_code === 'ROBOT_ERROR') return { level: 'error', code: s.last_code, message: s.message };
  if (s.step === 'PAUSED') return { level: 'pause', code: s.last_code, message: s.message };
  if (s.last_code && s.last_code !== 'OK') return { level: 'warn', code: s.last_code, message: s.message };
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
