# -*- coding: utf-8 -*-
"""설정 로더 시험 — 로봇·ROS 실행 없이 돈다.  실행: python3 -m pytest src/cobot_common/test/test_config.py"""
from pathlib import Path

import pytest

from cobot_api import CODES, RACK_SLOTS, RET_B, RET_C, STATIONS
from cobot_common import config

SRC_CONFIG = Path(__file__).resolve().parent.parent / 'config'


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for name in (config.ENV_CONFIG_DIR, config.ENV_USE_MOCK, config.ENV_VEL_SCALE):
        monkeypatch.delenv(name, raising=False)


def _write(d, cell='cell: {}\n', params='hmi: {port: 8000}\nflow: {use_mock: [f1]}\n'):
    (d / config.CELL_FILE).write_text(cell, encoding='utf-8')
    (d / config.PARAMS_FILE).write_text(params, encoding='utf-8')


# ------------------------------------------------------------------ 저장소의 실제 설정 파일
def test_repo_config_loads_all_sections():
    cfg = config.load(SRC_CONFIG)
    assert set(cfg) == set(config.CELL_KEYS + config.PARAM_SECTIONS) | {config.RUN_KEY}
    assert all(isinstance(cfg[k], dict) for k in cfg)
    assert {'port', 'state_rate_hz', 'disconnect_after_s', 'db_path'} <= set(cfg['hmi'])
    assert cfg['run'] == {'vel_scale': 1.0}


def test_repo_cell_skeleton_uses_ird_ids():
    """cell.yaml 키 골격이 IRD §2 의 ID 와 어긋나지 않는다(오타·누락 방지)."""
    cell = config.load(SRC_CONFIG)['cell']
    assert set(cell) == {'limits', 'motion', 'force', 'presets', 'stations', 'zones', 'beds', 'rack'}
    assert set(cell['motion']) == {'vel_tcp_max_mm_s', 'acc_tcp_max_mm_s2', 'vel_joint_max_deg_s', 'acc_joint_max_deg_s2'}
    assert set(cell['force']) == {'compliance_stx', 'contact_step_mm', 'contact_vel_mm_s', 'contact_acc_mm_s2',
                                  'retreat_vel_mm_s', 'retreat_acc_mm_s2', 'force_max_n', 'search_y_period_ratio'}   # 이슈 #7 ①
    beds = {'SPONGE_BED_B', 'SPONGE_BED_C'}
    assert set(cell['stations']) == set(STATIONS) - beds          # 스펀지 홈은 beds 에 있다
    assert set(cell['beds']) == beds
    assert set(cell['zones']) == {RET_B, RET_C}
    assert set(cell['rack']['slots']) == set(RACK_SLOTS)
    assert set(cell['presets']) == {'BOWL', 'CUP', 'SPONGE', 'BRUSH'}


def test_repo_params_sections():
    cfg = config.load(SRC_CONFIG)
    assert set(cfg['flow']['policy']) <= set(CODES)               # 정책의 키는 IRD §2 실패 코드
    assert {'soap', 'wipe_bowl', 'wipe_cup'} == set(cfg['f3'])
    assert config.unfilled(cfg, config.PARAM_SECTIONS) == []      # params.yaml 은 빈 값 없이 초안 값이 있다


def test_unfilled_lists_empty_cell_values():
    empty = config.unfilled(config.load(SRC_CONFIG))
    assert 'cell.limits.safe_z_mm' in empty                       # INF-04 시점: cell 값은 한석형이 채우기 전
    assert 'cell.stations.HOME.posj' in empty
    assert not [p for p in empty if not p.startswith('cell.')]


# ------------------------------------------------------------------ 형식 검사
def test_env_dir_overrides(tmp_path, monkeypatch):
    _write(tmp_path, params='hmi: {port: 9000}\n')
    monkeypatch.setenv(config.ENV_CONFIG_DIR, str(tmp_path))
    assert config.load()['hmi']['port'] == 9000
    assert config.load()['f3'] == {}                              # 없는 절은 빈 dict


def test_unknown_top_level_key_is_rejected(tmp_path):
    _write(tmp_path, params='f9: {}\n')
    with pytest.raises(config.ConfigError, match='f9'):
        config.load(tmp_path)


def test_section_in_wrong_file_is_rejected(tmp_path):
    _write(tmp_path, cell='cell: {}\nf1: {}\n')                   # 기능 절을 cell.yaml 에 넣으면 안 된다
    with pytest.raises(config.ConfigError, match='f1'):
        config.load(tmp_path)


def test_missing_file(tmp_path):
    with pytest.raises(config.ConfigError, match=config.CELL_FILE):
        config.load(tmp_path)


# ------------------------------------------------------------------ 실행 인자(환경변수)
def test_use_mock_env_overrides_yaml(tmp_path, monkeypatch):
    _write(tmp_path)
    assert config.load(tmp_path)['flow']['use_mock'] == ['f1']    # 변수가 없으면 YAML 그대로
    monkeypatch.setenv(config.ENV_USE_MOCK, 'f1, f3')
    assert config.load(tmp_path)['flow']['use_mock'] == ['f1', 'f3']
    monkeypatch.setenv(config.ENV_USE_MOCK, '')
    assert config.load(tmp_path)['flow']['use_mock'] == []        # 빈 값 = 전부 실제


def test_use_mock_unknown_name(tmp_path, monkeypatch):
    _write(tmp_path)
    monkeypatch.setenv(config.ENV_USE_MOCK, 'f1,f4')
    with pytest.raises(config.ConfigError, match='f4'):
        config.load(tmp_path)


@pytest.mark.parametrize('text,ok', [('0.3', True), ('1', True), ('0', False), ('1.5', False), ('-0.2', False), ('빠르게', False)])
def test_vel_scale_range(tmp_path, monkeypatch, text, ok):
    _write(tmp_path)
    monkeypatch.setenv(config.ENV_VEL_SCALE, text)
    if ok:
        assert config.load(tmp_path)['run']['vel_scale'] == float(text)
    else:
        with pytest.raises(config.ConfigError, match='vel_scale'):
            config.load(tmp_path)
