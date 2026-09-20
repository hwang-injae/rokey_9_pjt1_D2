# -*- coding: utf-8 -*-
""""마지막으로 들은 값" 보관함 — ROS 스레드가 넣고(put_*), 웹 스레드가 꺼낸다(snapshot). ROS·웹 부품을 쓰지 않는다.

    ROS 콜백 → put_state() · put_event() · put_force() · put_gripping()      (값 저장만 — 콜백에서 다른 일은 하지 않는다)
    GET /api/state → snapshot()                                                (그 순간의 사본 — 락 안에서 복사한다)
연결 판정: /flow/state 가 hmi.disconnect_after_s 넘게 안 오면 connected = False (IRD §6 "2 s 이상 안 오면 연결 끊김").
"""
import threading
import time
from collections import deque

RECENT_EVENTS = 50              # SQLite(F4-04) 전까지 메모리에 들고 있는 최근 이벤트 수
FORCE_FRESH_S = 0.5             # /cell/force 는 닦는 동안만 온다 → 이 시간 넘게 없으면 '지금은 닦지 않는다'(None)


class StateStore:
    def __init__(self, disconnect_after_s, clock=time.monotonic):
        self._limit = float(disconnect_after_s)
        self._clock = clock
        self._lock = threading.Lock()
        self._state, self._state_at = None, None
        self._gripping = None
        self._force, self._force_at = None, None
        self._events = deque(maxlen=RECENT_EVENTS)
        self._count = 0                                     # 받은 /flow/state 수 (시험·진단용)

    # ------------------------------------------------------------------ ROS 스레드
    def put_state(self, fields: dict):
        with self._lock:
            self._state, self._state_at = dict(fields), self._clock()
            self._count += 1

    def put_event(self, fields: dict):
        with self._lock:
            self._events.appendleft(dict(fields))           # 최근 것이 앞

    def put_force(self, newton: float):
        with self._lock:
            self._force, self._force_at = float(newton), self._clock()

    def put_gripping(self, value: bool):
        with self._lock:
            self._gripping = bool(value)

    # ------------------------------------------------------------------ 웹 스레드
    def snapshot(self) -> dict:
        with self._lock:
            now = self._clock()
            age = None if self._state_at is None else now - self._state_at
            fresh = self._force_at is not None and now - self._force_at <= FORCE_FRESH_S
            return {
                'connected': age is not None and age <= self._limit,
                'age_s': None if age is None else round(age, 2),
                'received': self._count,
                'state': None if self._state is None else dict(self._state),
                'gripping': self._gripping,
                'force_n': round(self._force, 2) if fresh else None,
                'events': [dict(e) for e in self._events],
            }
