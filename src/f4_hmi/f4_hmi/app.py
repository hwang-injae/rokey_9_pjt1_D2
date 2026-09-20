# -*- coding: utf-8 -*-
"""웹 쪽 입 — 브라우저의 요청에 답하고(REST), 새 값을 밀어 준다(WebSocket). ROS 를 모른다(그래서 ROS 없이 시험할 수 있다).

    GET  /api/state                     지금 값 전부(연결·상태·그리퍼·힘·최근 이벤트·계획)
    POST /api/start|stop|resume|abort   버튼 → flow 의 같은 이름 서비스 → {ok, message, latency_ms} 를 그대로 돌려준다 (F4-02)
       🔒 버튼 요청에는 **BUTTON_HEADER 가 있어야 한다**(F4-02b). 없으면 403.
          왜: 접속을 이 PC 로 한정해도(hmi.host 127.0.0.1 · 결정 E10) **이 PC 브라우저로 연 다른 웹페이지**가
          `fetch('http://localhost:8000/api/start', {method:'POST'})` 로 **몰래 누를 수 있다**. 브라우저는 그런 '단순 요청'을
          미리 묻지 않고 그냥 보낸다(응답은 못 읽어도 로봇은 이미 움직인다). 헤더를 하나 요구하면 그 요청은 '단순 요청'이 아니게 되어
          브라우저가 먼저 서버에 물어보고(preflight), 우리는 다른 출처에 허락을 준 적이 없으므로 **브라우저가 막는다**.
          우리 화면은 헤더를 붙여 보내므로 그대로 된다. 비밀이 아니라 **다른 출처를 막는 표식**이다(값은 아무 것이나).
    WS   /ws/state                      서버 → 브라우저. 붙자마자 type=state(전부) 1번, 그 뒤로 state · event · force · gripping · conn
    GET  /                              시험 페이지                                     이력(GET /api/history)은 F4-04
응답 모양은 docs/ref/20260920_F4-00_HMI_설계초안.md §2.
"""
import asyncio
from pathlib import Path

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .hub import Hub

STATIC_DIR = Path(__file__).resolve().parent / 'static'
COMMANDS = ('start', 'stop', 'resume', 'abort')         # IRD §6 의 /flow/* 서비스 이름과 같다
BUTTON_HEADER = 'X-PreWash'                             # 🔒 버튼 요청에 이 헤더가 있어야 한다 (위 머리말 참고). 값은 보지 않는다
CONN_CHECK_S = 0.5                                      # 연결 끊김(conn)을 알아채는 간격 — 새 값이 안 와야 끊긴 것이라 기다리다 확인한다


def create_app(store, cfg: dict, command=None) -> FastAPI:
    """store: StateStore · cfg: config.load() 결과 · command(name) → {ok, message, latency_ms}: 버튼을 flow 에 전하는 함수(RosLink.call)."""
    app = FastAPI(title='PreWash-Cell HMI', docs_url='/api/docs', redoc_url=None)
    flow = cfg.get('flow') or {}
    plan = {'plan': flow.get('plan') or [], 'rack_order': flow.get('rack_order') or {},
            'consumables': flow.get('consumables') or {}}
    hub = Hub()
    store.subscribe(hub.from_ros)
    app.state.hub = hub

    def full():
        return {**store.snapshot(), 'plan': plan}

    @app.get('/api/state')
    def get_state():
        return full()

    def make_button(name):
        def press(request: Request):                    # def(동기) → 웹 서버가 작업 스레드에서 돌린다: flow 를 기다려도 다른 요청이 안 막힌다
            if request.headers.get(BUTTON_HEADER) is None:          # 🔒 다른 웹페이지가 몰래 누르지 못하게
                return JSONResponse(status_code=403, content={
                    'ok': False, 'latency_ms': 0,
                    'message': f'{BUTTON_HEADER} 헤더가 없는 요청은 받지 않는다 (이 화면에서 누른 것이 아니다)'})
            if command is None:
                return {'ok': False, 'message': 'flow 와 연결하는 부분이 없다 (시험 모드)', 'latency_ms': 0}
            return command(name)
        return press
    for name in COMMANDS:
        app.post(f'/api/{name}')(make_button(name))

    @app.websocket('/ws/state')
    async def ws_state(ws: WebSocket):
        await ws.accept()
        q = hub.join()
        try:
            first = full()
            connected = first['connected']
            await ws.send_json({'type': 'state', **first})
            while True:
                try:
                    await ws.send_json(await asyncio.wait_for(q.get(), timeout=CONN_CHECK_S))
                except asyncio.TimeoutError:
                    pass
                now = store.snapshot()['connected']
                if now != connected:                    # flow 가 끊겼다 / 다시 붙었다
                    connected = now
                    await ws.send_json({'type': 'conn', 'connected': now})
        except (WebSocketDisconnect, RuntimeError):
            pass
        finally:
            hub.leave(q)

    @app.get('/')
    def index():
        return FileResponse(STATIC_DIR / 'test.html')

    app.mount('/static', StaticFiles(directory=STATIC_DIR), name='static')
    return app
