# -*- coding: utf-8 -*-
"""설정 로더 시험 — 로봇·ROS 실행 없이 돈다.  실행: python3 -m pytest src/cobot_common/test/test_config.py"""
from pathlib import Path

import pytest

from cobot_common import config

SRC_CONFIG = Path(__file__).resolve().parent.parent / 'config'


def _write(d, cell='cell: {}\n', params='hmi: {port: 8000}\n'):
    (d / config.CELL_FILE).write_text(cell, encoding='utf-8')
    (d / config.PARAMS_FILE).write_text(params, encoding='utf-8')


def test_repo_config_loads_all_sections():
    cfg = config.load(SRC_CONFIG)
    assert set(cfg) == set(config.CELL_KEYS + config.PARAM_SECTIONS)
    assert all(isinstance(cfg[k], dict) for k in cfg)           # 빈 절도 dict
    assert {'port', 'state_rate_hz', 'disconnect_after_s', 'db_path'} <= set(cfg['hmi'])


def test_env_dir_overrides(tmp_path, monkeypatch):
    _write(tmp_path, params='hmi: {port: 9000}\n')
    monkeypatch.setenv(config.ENV_CONFIG_DIR, str(tmp_path))
    assert config.load()['hmi']['port'] == 9000
    assert config.load()['f3'] == {}                            # 없는 절은 빈 dict


def test_unknown_top_level_key_is_rejected(tmp_path):
    _write(tmp_path, params='f9: {}\n')
    with pytest.raises(config.ConfigError, match='f9'):
        config.load(tmp_path)


def test_section_in_wrong_file_is_rejected(tmp_path):
    _write(tmp_path, cell='cell: {}\nf1: {}\n')                 # 기능 절을 cell.yaml 에 넣으면 안 된다
    with pytest.raises(config.ConfigError, match='f1'):
        config.load(tmp_path)


def test_missing_file(tmp_path):
    with pytest.raises(config.ConfigError, match=config.CELL_FILE):
        config.load(tmp_path)
