# -*- coding: utf-8 -*-
"""보관함(StateStore)과 웹 응답(GET /api/state). ROS 불필요. 웹 부품(fastapi)이 없는 PC 에서는 app 시험만 건너뛴다."""
import pytest

from f4_hmi.state_store import FORCE_FRESH_S, RECENT_EVENTS, StateStore


class Clock:
    def __init__(self):
        self.t = 100.0

    def __call__(self):
        return self.t


def test_store_is_disconnected_until_first_state():
    snap = StateStore(2.0, Clock()).snapshot()
    assert snap['connected'] is False and snap['state'] is None and snap['age_s'] is None and snap['events'] == []


def test_store_connection_follows_age_of_last_state():
    clock = Clock()
    store = StateStore(2.0, clock)
    store.put_state({'step': 'PICK'})
    clock.t += 1.9
    assert store.snapshot()['connected'] is True and store.snapshot()['age_s'] == 1.9
    clock.t += 0.2                                                          # 2 s 넘게 없다 → 끊김. 마지막 값은 남겨 둔다
    snap = store.snapshot()
    assert snap['connected'] is False and snap['state'] == {'step': 'PICK'} and snap['received'] == 1


def test_store_force_is_none_when_not_wiping():
    clock = Clock()
    store = StateStore(2.0, clock)
    store.put_force(5.25)
    assert store.snapshot()['force_n'] == 5.25
    clock.t += FORCE_FRESH_S + 0.01                                         # 닦는 동안만 온다 → 끊기면 '닦는 중 아님'
    assert store.snapshot()['force_n'] is None


def test_store_keeps_recent_events_newest_first_and_copies():
    store = StateStore(2.0, Clock())
    for i in range(RECENT_EVENTS + 5):
        store.put_event({'n': i})
    events = store.snapshot()['events']
    assert len(events) == RECENT_EVENTS and events[0] == {'n': RECENT_EVENTS + 4}
    events[0]['n'] = -1                                                     # 꺼낸 사본을 고쳐도 보관함은 그대로
    assert store.snapshot()['events'][0] == {'n': RECENT_EVENTS + 4}
    store.put_gripping(1)
    assert store.snapshot()['gripping'] is True


def test_api_state_and_test_page():
    pytest.importorskip('fastapi', reason='웹 부품은 HMI 전용 상자(~/venvs/hmi)에만 있다 — 그 상자의 파이썬으로 돌리면 실행된다')
    from fastapi.testclient import TestClient
    from f4_hmi.app import create_app
    store = StateStore(2.0)
    cfg = {'flow': {'plan': [{'zone': 'RET_B', 'kind': 'BOWL', 'count': 2}], 'rack_order': {'BOWL': ['RACK_B1', 'RACK_B2']},
                    'consumables': {'sponge_max_uses': 20}}}
    client = TestClient(create_app(store, cfg))
    body = client.get('/api/state').json()
    assert body['connected'] is False and body['state'] is None and body['plan']['rack_order'] == {'BOWL': ['RACK_B1', 'RACK_B2']}
    store.put_state({'step': 'WIPE', 'kind': 'BOWL', 'done_bowl': 1})
    store.put_gripping(True)
    body = client.get('/api/state').json()
    assert body['connected'] is True and body['state']['step'] == 'WIPE' and body['gripping'] is True
    page = client.get('/')
    assert page.status_code == 200 and '/api/state' in page.text
