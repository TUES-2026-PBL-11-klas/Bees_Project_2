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


def test_load_auto_dispatches_grib_extension(tmp_path: Path, monkeypatch):
    """A .grib2 path goes through load_grib2, not load_json."""
    from src.core.services import current_grid as cg

    grib_path = tmp_path / "currents.grib2"
    grib_path.write_bytes(b"fake-grib-bytes")

    sentinel = _simple_grid()

    def _fake_loader(path):
        assert Path(path) == grib_path
        return sentinel

    monkeypatch.setattr(cg, "load_grib2", _fake_loader)
    assert load_auto(grib_path) is sentinel


def test_load_auto_returns_none_when_grib_unavailable(tmp_path: Path, monkeypatch):
    """When pygrib isn't installed, .grib paths log + return None instead of crashing."""
    from src.core.services import current_grid as cg

    grib_path = tmp_path / "currents.grib"
    grib_path.write_bytes(b"fake")

    def _fail(path):
        raise RuntimeError("pygrib not installed")

    monkeypatch.setattr(cg, "load_grib2", _fail)
    assert load_auto(grib_path) is None


def test_load_grib2_raises_without_pygrib(tmp_path: Path, monkeypatch):
    """The loader gives a clear RuntimeError when pygrib import fails."""
    import builtins

    from src.core.services import current_grid as cg

    real_import = builtins.__import__

    def _no_pygrib(name, *args, **kwargs):
        if name == "pygrib":
            raise ImportError("not installed")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _no_pygrib)
    with pytest.raises(RuntimeError, match="pygrib is not installed"):
        cg.load_grib2(tmp_path / "anything.grib2")


def test_sample_zero_step_grid_returns_zero():
    """A degenerate grid (dlat or dlon == 0) must not divide by zero."""
    g = CurrentGrid(
        lat0=0.0, lon0=0.0, dlat=0.0, dlon=1.0,
        nrows=1, ncols=2, u=[[1.0, 1.0]], v=[[0.0, 0.0]],
    )
    assert g.sample(0.0, 0.5) == (0.0, 0.0)
