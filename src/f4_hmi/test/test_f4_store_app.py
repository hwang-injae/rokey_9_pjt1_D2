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


# ------------------------------------------------------------------ F4-02: 구독 · 버튼 · WebSocket
def test_store_tells_listeners_what_changed():
    store = StateStore(2.0, Clock())
    heard = []
    store.subscribe(lambda kind, payload: heard.append((kind, payload)))
    store.put_state({'step': 'PICK'})
    store.put_event({'result': 'DONE'})
    store.put_force(4.236)
    store.put_gripping(True)
    store.put_gripping(True)                                                # 같은 값이 2 Hz 로 계속 와도 바뀔 때만 알린다
    store.put_gripping(False)
    kinds = [k for k, _ in heard]
    assert kinds == ['state', 'event', 'force', 'gripping', 'gripping']
    assert heard[0][1]['state'] == {'step': 'PICK'} and 'events' not in heard[0][1]     # state 몸통에는 이벤트 목록을 싣지 않는다
    assert heard[1][1] == {'event': {'result': 'DONE'}} and heard[2][1] == {'n': 4.24}
    assert [p['value'] for k, p in heard if k == 'gripping'] == [True, False]


BTN = {'X-PreWash': '1'}            # 🔒 버튼 요청의 표식 (app.BUTTON_HEADER)


def _client(command=None):
    pytest.importorskip('fastapi', reason='웹 부품은 HMI 전용 상자(~/venvs/hmi)에만 있다')
    from fastapi.testclient import TestClient
    from f4_hmi.app import create_app
    store = StateStore(2.0)
    return store, TestClient(create_app(store, {'flow': {}}, command))


def test_buttons_pass_the_flow_answer_through():
    pressed = []

    def command(name):
        pressed.append(name)
        return {'ok': name != 'abort', 'message': f'{name} 받음', 'latency_ms': 3}
    _, client = _client(command)
    for name in ('start', 'stop', 'resume', 'abort'):
        body = client.post(f'/api/{name}', headers=BTN).json()
        assert body == {'ok': name != 'abort', 'message': f'{name} 받음', 'latency_ms': 3}
    assert pressed == ['start', 'stop', 'resume', 'abort']
    assert client.post('/api/explode', headers=BTN).status_code in (404, 405)   # 없는 버튼
    assert client.get('/api/start').status_code == 405                      # 버튼은 POST 만


def test_buttons_without_flow_link_say_so():
    _, client = _client(None)
    body = client.post('/api/start', headers=BTN).json()
    assert body['ok'] is False and body['message']


def test_buttons_refuse_a_request_without_the_header():
    """🔒 F4-02b — 이 PC 브라우저로 연 다른 웹페이지가 몰래 누르는 것을 막는다(결정 E10 의 후속)."""
    pressed = []
    _, client = _client(lambda name: pressed.append(name) or {'ok': True, 'message': '', 'latency_ms': 1})
    for name in ('start', 'stop', 'resume', 'abort'):
        res = client.post(f'/api/{name}')                                   # 헤더 없이 = 다른 페이지가 보낸 단순 요청
        assert res.status_code == 403 and res.json()['ok'] is False
    assert pressed == []                                                    # flow 까지 가지 않았다
    assert client.get('/api/state').status_code == 200                      # 읽기(GET)는 그대로 — 화면이 값을 못 받으면 안 된다


def test_websocket_sends_everything_first_then_pushes_changes():
    store, client = _client()
    store.put_state({'step': 'IDLE', 'last_code': 'OK'})
    with client.websocket_connect('/ws/state') as ws:
        first = ws.receive_json()
        assert first['type'] == 'state' and first['state']['step'] == 'IDLE' and 'events' in first and 'plan' in first
        store.put_state({'step': 'PICK', 'last_code': 'OK'})                # ROS 스레드에서 들어온 셈 — 다른 스레드에서 넣는다
        msg = ws.receive_json()
        assert msg['type'] == 'state' and msg['state']['step'] == 'PICK' and 'events' not in msg
        store.put_event({'result': 'DONE', 'kind': 'BOWL'})
        assert ws.receive_json() == {'type': 'event', 'event': {'result': 'DONE', 'kind': 'BOWL'}}
        store.put_force(5.5)
        assert ws.receive_json() == {'type': 'force', 'n': 5.5}
        store.put_gripping(True)
        assert ws.receive_json() == {'type': 'gripping', 'value': True}


def test_websocket_reports_lost_connection():
    pytest.importorskip('fastapi')
    from fastapi.testclient import TestClient
    from f4_hmi import app as app_module
    from f4_hmi.app import create_app
    clock = Clock()
    store = StateStore(2.0, clock)
    store.put_state({'step': 'WIPE'})
    app_module.CONN_CHECK_S = 0.05
    try:
        with TestClient(create_app(store, {})).websocket_connect('/ws/state') as ws:
            assert ws.receive_json()['connected'] is True
            clock.t += 5.0                                                  # flow 가 5 s 동안 조용하다
            assert ws.receive_json() == {'type': 'conn', 'connected': False}
            store.put_state({'step': 'WIPE'})                               # 다시 온다
            got = [ws.receive_json(), ws.receive_json()]
            assert {'type': 'conn', 'connected': True} in got
    finally:
        app_module.CONN_CHECK_S = 0.5


def test_hub_drops_oldest_when_a_browser_is_slow():
    import asyncio
    from f4_hmi import hub as hub_module
    from f4_hmi.hub import Hub

    async def scenario():
        h = Hub()
        q = h.join()
        for i in range(hub_module.QUEUE_MAX + 10):
            h._fan_out({'n': i})
        assert q.qsize() == hub_module.QUEUE_MAX and q.get_nowait() == {'n': 10}     # 오래된 10개를 버렸다
        h.leave(q)
        assert h.clients == 0
        h.from_ros('state', {})                                             # 붙은 브라우저가 없으면 아무 일도 없다
    asyncio.run(scenario())
