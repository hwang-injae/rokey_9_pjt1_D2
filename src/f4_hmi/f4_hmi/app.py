# -*- coding: utf-8 -*-
"""웹 쪽 입 — 브라우저가 물으면 StateStore 의 값을 답한다. ROS 를 모른다(그래서 ROS 없이 시험할 수 있다).

F4-01 범위: GET /api/state · 시험 페이지(/). 버튼(POST /api/start …)·WebSocket(/ws/state)은 F4-02, 이력(GET /api/history)은 F4-04.
응답 모양은 docs/ref/20260920_F4-00_HMI_설계초안.md §2.
"""
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

STATIC_DIR = Path(__file__).resolve().parent / 'static'


def create_app(store, cfg: dict) -> FastAPI:
    """store: StateStore · cfg: cobot_common.config.load() 결과(plan·소모품 상한을 화면에 같이 준다)."""
    app = FastAPI(title='PreWash-Cell HMI', docs_url='/api/docs', redoc_url=None)
    flow = cfg.get('flow') or {}
    plan = {'plan': flow.get('plan') or [], 'rack_order': flow.get('rack_order') or {},
            'consumables': flow.get('consumables') or {}}

    @app.get('/api/state')
    def get_state():
        return {**store.snapshot(), 'plan': plan}

    @app.get('/')
    def index():
        return FileResponse(STATIC_DIR / 'test.html')

    app.mount('/static', StaticFiles(directory=STATIC_DIR), name='static')
    return app
