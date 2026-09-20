# -*- coding: utf-8 -*-
"""hmi_bridge — 실행 입구. ROS 쪽 귀(RosLink) + 웹 쪽 입(FastAPI/uvicorn)을 한 프로그램에서 띄운다. 담당 황인재 (F4-01)

    ros2 run f4_hmi hmi_bridge      →  http://localhost:8000  (포트는 params.yaml 의 hmi.port)

웹 서버 부품(fastapi · uvicorn)은 HMI 전용 상자(venv, params.yaml 의 hmi.venv_dir)에 있다. `ros2 run` 은 시스템 파이썬으로 돌기 때문에
상자를 열지(activate) 않았으면 **상자의 site-packages 를 직접 찾아 붙인다** → 상자를 여는 것을 잊어도 그대로 뜬다.
"""
import site
import sys
from pathlib import Path

from cobot_common import config


def _ensure_web_parts(venv_dir):
    """fastapi·uvicorn 을 import 할 수 있게 한다. 못 하면 설치 방법을 알려 주고 끝낸다."""
    try:
        import fastapi, uvicorn                              # noqa: F401,E401 — 이미 보이면(상자를 열었거나 시스템에 있으면) 그대로
        return
    except ModuleNotFoundError:
        pass
    for sp in sorted(Path(str(venv_dir)).expanduser().glob('lib/python*/site-packages')):
        site.addsitedir(str(sp))
    try:
        import fastapi, uvicorn                              # noqa: F401,E401
    except ModuleNotFoundError as e:
        sys.exit(f'hmi_bridge: 웹 서버 부품이 없다({e.name}). 한 번만 설치한다 —\n'
                 f'  python3 -m venv --system-site-packages {venv_dir}\n'
                 f'  {venv_dir}/bin/pip install fastapi "uvicorn[standard]" websockets')


def main():
    cfg = config.load()
    hmi = cfg['hmi']
    _ensure_web_parts(hmi.get('venv_dir', '~/venvs/hmi'))

    import uvicorn
    from .app import create_app
    from .ros_link import RosLink
    from .state_store import StateStore

    store = StateStore(hmi['disconnect_after_s'])
    link = RosLink(store)
    link.start()
    log = link.node.get_logger()
    host, port = str(hmi.get('host', '0.0.0.0')), int(hmi['port'])
    log.info(f'HMI 서버를 연다 → http://localhost:{port}  (같은 망의 태블릿은 http://<이 PC 의 IP>:{port})')
    try:
        uvicorn.run(create_app(store, cfg), host=host, port=port, log_level='warning', lifespan='off')     # Ctrl+C 까지 여기서 돈다 (시작·종료 훅은 안 쓴다 → 끌 때 조용하다)
    except KeyboardInterrupt:                           # 런치에서 끄면 Ctrl+C 가 두 번 온다(터미널 + 런치가 전달) → 두 번째는 조용히 넘긴다
        pass
    finally:
        link.stop()


if __name__ == '__main__':
    main()
