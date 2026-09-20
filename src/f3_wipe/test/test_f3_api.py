import csv
import os

from cobot_api import F3Api, Result, WipeBowlResult, WipeCupResult, check_api
from f3_wipe import wipe


def test_wipe_matches_f3api():
    assert check_api(wipe, F3Api) == []


def test_return_types():
    assert isinstance(wipe.soap(1), Result)
    assert isinstance(wipe.wipe_cup(), WipeCupResult)
    # wipe_bowl 은 로봇을 움직이므로 가짜 셀로 따로 시험한다 → test_f3_wipe_bowl.py
    assert WipeBowlResult(ok=False, code='ROBOT_ERROR').code == 'ROBOT_ERROR'


def test_save_force_log(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    path = wipe._save_force_log([(0.0, 0.1, 0.2, -4.0, 4.0), (0.1, 0.1, 0.2, -4.2, 4.0)], 'logs')
    assert not os.path.isabs(path) and os.path.basename(path).startswith('force_')
    with open(path) as f:
        rows = list(csv.reader(f))
    assert tuple(rows[0]) == wipe.FORCE_LOG_HEADER and len(rows) == 3
