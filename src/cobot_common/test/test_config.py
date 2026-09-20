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
    assert set(cell['motion']) == {'vel_tcp_max_mm_s', 'acc_tcp_max_mm_s2', 'vel_joint_max_deg_s', 'acc_joint_max_deg_s2',
                                   'move_timeout_s'}
    assert set(cell['force']) == {'compliance_stx', 'contact_step_mm', 'contact_vel_mm_s', 'contact_acc_mm_s2',
                                  'retreat_vel_mm_s', 'retreat_acc_mm_s2', 'force_max_n', 'search_y_period_ratio'}   # 이슈 #7 ①
    beds = {'SPONGE_BED_B', 'SPONGE_BED_C'}
    assert set(cell['stations']) == set(STATIONS) - beds          # 스펀지 홈은 beds 에 있다
    assert set(cell['beds']) == beds
    assert set(cell['zones']) == {RET_B, RET_C}
    assert set(cell['rack']['slots']) == set(RACK_SLOTS)
    assert set(cell['presets']) == {'BOWL', 'CUP', 'SPONGE', 'BRUSH'}
    # 9/20 CELL-04: 양식을 티칭 데이터에 맞췄다 — 종류별 · 용도별(point) · 슬롯별
    for name in ('WEIGH', 'WASTE', 'SOAP', 'RINSE', 'ISOLATE'):
        assert set(cell['stations'][name]) == {'BOWL', 'CUP'}, name
    for name in ('TOOL_SPONGE', 'TOOL_BRUSH'):
        assert set(cell['stations'][name]) == {'pick', 'return'}, name
    assert set(cell['beds']['SPONGE_BED_B']) == {'place', 'wash', 'seat'}
    assert set(cell['beds']['SPONGE_BED_C']) == {'place', 'regrip', 'wash', 'seat'}
    assert all(len(cell['zones'][z]['slots']) == 2 for z in (RET_B, RET_C))       # 구역마다 슬롯 2개 (flow.plan 의 count 와 같다)


def _rotation(rx, ry, rz):
    """두산 posx 의 방향(ZYZ 오일러각, deg) → 회전 행렬."""
    import math
    a, b, c = (math.radians(v) for v in (rx, ry, rz))
    ca, sa, cb, sb, cc_, sc = math.cos(a), math.sin(a), math.cos(b), math.sin(b), math.cos(c), math.sin(c)
    return [[ca * cb * cc_ - sa * sc, -ca * cb * sc - sa * cc_, ca * sb],
            [sa * cb * cc_ + ca * sc, -sa * cb * sc + ca * cc_, sa * sb],
            [-sb * cc_, sb * sc, cb]]


def _angle_between(p, q):
    import math
    r1, r2 = _rotation(*p[3:]), _rotation(*q[3:])
    trace = sum(r1[i][k] * r2[i][k] for i in range(3) for k in range(3))          # tr(R1ᵀ·R2)
    return math.degrees(math.acos(max(-1.0, min(1.0, (trace - 1.0) / 2.0))))


# ⚠ 접근점 → 끝점이 수직이 아닌 채로 옮겨 온 자세. 한석형이 다시 찍으면 여기서 지운다(9/20 CELL-04: RACK_C2 는 수평 2.4 mm · 방향 3.8°)
KNOWN_TILTED = {'cell.rack.slots.RACK_C2'}


def test_repo_approach_points_are_straight_above_end_points():
    """cc.move_to 는 접근점까지만 가고 부르는 쪽이 곧게 내려간다 → 접근점은 끝점의 **바로 위 · 같은 방향**이어야 끝점에 닿는다."""
    import math
    cell = config.load(SRC_CONFIG)['cell']
    pairs = {}

    def walk(node, path):
        if isinstance(node, dict):
            if node.get('approach_posx') and node.get('posx'):
                pairs[path] = (node['approach_posx'], node['posx'])
            for k, v in node.items():
                walk(v, f'{path}.{k}')
    walk(cell, 'cell')
    assert len(pairs) >= 6                                                         # 스펀지 홈 place·wash × 2 + 팔레트 컵 2칸
    tilted = set()
    for path, (up, end) in pairs.items():
        assert up[2] > end[2], f'{path}: 접근점이 끝점보다 낮다'
        if math.hypot(up[0] - end[0], up[1] - end[1]) > 1.0 or _angle_between(up, end) > 1.0:   # 1 mm · 1° — 손 티칭의 읽기 오차보다 크면 어긋난 것
            tilted.add(path)
    assert tilted == KNOWN_TILTED


def test_repo_params_sections():
    cfg = config.load(SRC_CONFIG)
    assert set(cfg['flow']['policy']) <= set(CODES)               # 정책의 키는 IRD §2 실패 코드
    assert {'soap', 'wipe_bowl', 'wipe_cup'} == set(cfg['f3'])
    assert config.unfilled(cfg, config.PARAM_SECTIONS) == []      # params.yaml 은 빈 값 없이 초안 값이 있다


def test_unfilled_lists_empty_cell_values():
    empty = config.unfilled(config.load(SRC_CONFIG))
    assert 'cell.limits.safe_z_mm' in empty                       # INF-04 시점: cell 값은 한석형이 채우기 전
    assert 'cell.stations.WEIGH.BOWL.posx' in empty               # 9/20 CELL-04: 한석형이 찍은 26개는 찼고, 안 찍은 자세는 비어 있다
    assert 'cell.zones.RET_B.slots[2].posj' in empty              # 슬롯 목록도 센다 (번호는 1 부터)
    assert 'cell.stations.HOME.posj' not in empty and 'cell.zones.RET_B.slots[1].posj' not in empty
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
