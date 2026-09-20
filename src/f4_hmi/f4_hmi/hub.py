# -*- coding: utf-8 -*-
"""WebSocket 전화 교환기 — ROS 스레드에서 들어온 값을 열려 있는 모든 브라우저에 밀어 준다.

    ROS 스레드: store.put_*() → Hub.from_ros(type, payload) → loop.call_soon_threadsafe(…)      (스레드를 건너가는 유일한 자리)
    웹 루프   : 브라우저마다 큐 1개 → /ws/state 핸들러가 큐에서 꺼내 보낸다
브라우저가 느려 큐가 차면 **그 브라우저의 오래된 것부터 버린다**(힘 값 10 Hz 가 밀려도 최신 상태가 중요하다). ROS 쪽은 절대 기다리지 않는다.
"""
import asyncio

QUEUE_MAX = 200


class Hub:
    def __init__(self):
        self.loop = None                    # 웹 서버의 이벤트 루프 — 첫 브라우저가 붙을 때 잡는다
        self._queues = set()

    # ------------------------------------------------------------------ 웹 루프에서
    def join(self) -> asyncio.Queue:
        self.loop = asyncio.get_running_loop()
        q = asyncio.Queue(maxsize=QUEUE_MAX)
        self._queues.add(q)
        return q

    def leave(self, q):
        self._queues.discard(q)

    @property
    def clients(self) -> int:
        return len(self._queues)

    def _fan_out(self, message):
        for q in list(self._queues):
            if q.full():
                q.get_nowait()              # 오래된 것 하나를 버린다
            q.put_nowait(message)

    # ------------------------------------------------------------------ ROS 스레드에서
    def from_ros(self, kind, payload):
        if self.loop is None or not self._queues:
            return                          # 붙어 있는 브라우저가 없다
        try:
            self.loop.call_soon_threadsafe(self._fan_out, {'type': kind, **payload})
        except RuntimeError:                # 서버가 꺼지는 중(루프가 닫혔다)
            pass
