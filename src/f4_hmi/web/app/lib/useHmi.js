'use client';
// 값 받기 — hmi_bridge 하고만 이야기한다(로봇·ROS 를 모른다). 계약: docs/ref/20260920_F4-00_HMI_설계초안.md §2
//   ① WebSocket /ws/state — 서버가 먼저 밀어 준다. 붙자마자 전부 1번, 그 뒤 state · event · conn (force · gripping 은 안 쓴다)
//   ② 끊기면 2초 뒤 다시 걸고, 그동안은 GET /api/state 를 0.5초마다 물어본다(시험 페이지와 같은 방식)
import { useCallback, useEffect, useRef, useState } from 'react';

const POLL_MS = 500;
const RETRY_MS = 2000;
const MAX_EVENTS = 50;          // 화면에 들고 있는 최근 이벤트 수

const EMPTY = { connected: false, server: true, state: null, events: [], plan: {}, received: 0, age_s: null, ready: false };

export function useHmi() {
  const [d, setD] = useState(EMPTY);
  const [mode, setMode] = useState('연결 중');
  const ws = useRef(null);

  useEffect(() => {
    let closed = false;
    let retry = null;
    const merge = (body) => setD((prev) => ({ ...prev, ...body, server: true, ready: true }));

    function connect() {
      const sock = new WebSocket(`${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws/state`);
      ws.current = sock;
      sock.onopen = () => setMode('실시간');
      sock.onmessage = (m) => {
        const msg = JSON.parse(m.data);
        if (msg.type === 'state') {                   // 첫 번째만 events·plan 이 온다 — 그 뒤엔 빠진 몸통이라 합친다
          const { type, ...body } = msg;
          merge(body);
        } else if (msg.type === 'event') {
          setD((prev) => ({ ...prev, events: [msg.event, ...prev.events].slice(0, MAX_EVENTS) }));
        } else if (msg.type === 'conn') {                // force·gripping 은 받지 않는다 — 9/21 황인재: 보내는 쪽이 없어 화면에서 뺐다
          setD((prev) => ({ ...prev, connected: msg.connected }));
        }
      };
      sock.onclose = () => {
        ws.current = null;
        if (closed) return;
        setMode('0.5초마다 물어보기');
        retry = setTimeout(connect, RETRY_MS);
      };
    }

    async function pollOnce() {
      if (ws.current && ws.current.readyState === WebSocket.OPEN) return;
      try {
        merge(await (await fetch('/api/state', { cache: 'no-store' })).json());
      } catch {
        setD((prev) => ({ ...prev, connected: false, server: false }));
      }
    }

    connect();
    const poll = setInterval(pollOnce, POLL_MS);
    return () => { closed = true; clearTimeout(retry); clearInterval(poll); if (ws.current) ws.current.close(); };
  }, []);

  // 버튼 → POST /api/{name}. X-PreWash 헤더: 이 PC 에서 연 다른 웹페이지가 몰래 누르지 못하게(F4-02b · E10 후속) — 서버가 아직 안 봐도 해가 없다
  const press = useCallback(async (name) => {
    try {
      const r = await fetch(`/api/${name}`, { method: 'POST', headers: { 'X-PreWash': '1' } });
      return await r.json();
    } catch {
      return { ok: false, message: 'HMI 서버에 닿지 않는다', latency_ms: 0 };
    }
  }, []);

  return { d, mode, press };
}
