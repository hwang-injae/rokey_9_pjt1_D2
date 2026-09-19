# -*- coding: utf-8 -*-
"""설정 로더 — config/cell.yaml(공용) + config/params.yaml(기능별 절)을 읽어 하나의 dict 로 합친다. (SDD §4.3, IRD §9)

    from cobot_common import config
    cfg = config.load()
    cfg['cell']['limits']['safe_z_mm']      # 공용 값 (주인 한석형)
    cfg['f3']['wipe_bowl']                  # 기능별 절 (자기 절만 수정)

설정 폴더를 찾는 순서
  1) 환경변수 PREWASH_CONFIG_DIR (시험·현장에서 다른 설정 묶음으로 바꿔 끼울 때)
  2) 설치된 패키지의 share/cobot_common/config  (cbc 는 --symlink-install 이라 YAML 을 고치면 재빌드 없이 반영된다)
  3) 빌드 전이면 소스 트리의 src/cobot_common/config (이 파일 기준 상대경로)
"""
import os
from pathlib import Path

import yaml

CELL_FILE = 'cell.yaml'
PARAMS_FILE = 'params.yaml'
CELL_KEYS = ('cell',)                               # cell.yaml 의 최상위 키
PARAM_SECTIONS = ('f1', 'f2', 'f3', 'flow', 'hmi')  # params.yaml 의 절 (IRD §9)
ENV_CONFIG_DIR = 'PREWASH_CONFIG_DIR'


class ConfigError(RuntimeError):
    """설정 파일이 없거나 형식이 약속(SDD §4.3)과 다를 때."""


def config_dir() -> Path:
    """설정 폴더 경로를 돌려준다."""
    env = os.environ.get(ENV_CONFIG_DIR)
    if env:
        return Path(env)
    try:
        from ament_index_python.packages import get_package_share_directory
        return Path(get_package_share_directory('cobot_common')) / 'config'
    except Exception:       # 빌드 전(패키지 미설치) → 소스 트리
        return Path(__file__).resolve().parent.parent / 'config'


def _read(path: Path, allowed) -> dict:
    if not path.is_file():
        raise ConfigError(f'설정 파일이 없다: {path}')
    with open(path, encoding='utf-8') as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ConfigError(f'{path.name}: 최상위는 "키: 값" 형식이어야 한다')
    unknown = [k for k in data if k not in allowed]
    if unknown:
        raise ConfigError(f'{path.name}: 약속에 없는 최상위 키 {unknown} (허용: {list(allowed)})')
    return data


def load(directory=None) -> dict:
    """두 파일을 읽어 하나의 설정으로 합친다. 비어 있는 절은 빈 dict 로 채워 KeyError 를 막는다."""
    d = Path(directory) if directory else config_dir()
    merged = {}
    merged.update(_read(d / CELL_FILE, CELL_KEYS))
    merged.update(_read(d / PARAMS_FILE, PARAM_SECTIONS))
    for key in CELL_KEYS + PARAM_SECTIONS:
        if merged.get(key) is None:
            merged[key] = {}
    return merged
