"""Unit tests for CurrentGrid."""

import json
from pathlib import Path

import pytest

from src.core.services.current_grid import (
    CurrentGrid,
    load_auto,
    load_json,
)


def _simple_grid() -> CurrentGrid:
    # 3x3 grid covering lat 40-42, lon 10-12, with linear u/v fields:
    #   u(lat,lon) = (lon - 10)        → 0, 1, 2 along columns
    #   v(lat,lon) = (lat - 40)        → 0, 1, 2 along rows
    u = [[0.0, 1.0, 2.0],
         [0.0, 1.0, 2.0],
         [0.0, 1.0, 2.0]]
    v = [[0.0, 0.0, 0.0],
         [1.0, 1.0, 1.0],
         [2.0, 2.0, 2.0]]
    return CurrentGrid(
        lat0=40.0, lon0=10.0, dlat=1.0, dlon=1.0,
        nrows=3, ncols=3, u=u, v=v,
    )


def test_bbox_matches_construction():
    g = _simple_grid()
    assert g.bbox() == (40.0, 10.0, 42.0, 12.0)


def test_contains():
    g = _simple_grid()
    assert g.contains(41, 11) is True
    assert g.contains(40, 10) is True
    assert g.contains(42, 12) is True
    assert g.contains(39, 11) is False
    assert g.contains(41, 13) is False


def test_sample_grid_corners_exact():
    g = _simple_grid()
    u, v = g.sample(40, 10)
    assert (u, v) == (0.0, 0.0)
    u, v = g.sample(42, 12)
    assert (u, v) == (2.0, 2.0)


def test_sample_bilinear_midpoint():
    g = _simple_grid()
    u, v = g.sample(41, 11)
    # Linear field → exact answer
    assert pytest.approx(u) == 1.0
    assert pytest.approx(v) == 1.0


def test_sample_bilinear_offset():
    g = _simple_grid()
    u, v = g.sample(40.5, 11.5)
    assert pytest.approx(u) == 1.5
    assert pytest.approx(v) == 0.5


def test_sample_outside_returns_zero():
    g = _simple_grid()
    assert g.sample(0, 0) == (0.0, 0.0)


def test_to_lookup_dict_keys_use_05_grid():
    g = _simple_grid()
    lookup = g.to_lookup_dict()
    # 3x3 grid → 9 entries
    assert len(lookup) == 9
    assert (40.0, 10.0) in lookup
    assert lookup[(40.0, 10.0)] == (0.0, 0.0)
    assert lookup[(42.0, 12.0)] == (2.0, 2.0)


def test_load_json_roundtrip(tmp_path: Path):
    payload = {
        "lat0": 40, "lon0": 10, "dlat": 1, "dlon": 1,
        "nrows": 3, "ncols": 3,
        "u": [[0, 1, 2], [0, 1, 2], [0, 1, 2]],
        "v": [[0, 0, 0], [1, 1, 1], [2, 2, 2]],
    }
    p = tmp_path / "grid.json"
    p.write_text(json.dumps(payload))
    g = load_json(p)
    assert g.sample(41, 11) == (1.0, 1.0)


def test_load_auto_missing_file_returns_none(tmp_path: Path):
    assert load_auto(tmp_path / "nope.json") is None
