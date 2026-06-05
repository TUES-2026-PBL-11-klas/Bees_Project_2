"""
Gridded ocean-current data with bilinear interpolation (issue #77).

The standard data source is **GRIB2** (HYCOM, NCEP RTOFS, etc.).
Parsing native GRIB2 requires ``pygrib`` (libeccodes); if it isn't
available at runtime, the loader falls back to JSON shaped like::

    {
      "lat0": 30.0, "lon0": -10.0,
      "dlat": 0.5, "dlon": 0.5,
      "nrows": 41, "ncols": 81,
      "u": [[u00, u01, ...], ...],
      "v": [[v00, v01, ...], ...]
    }

That keeps the codebase importable everywhere — production can ship
``pygrib`` in its Docker image, while CI / dev boxes stay slim.
"""

from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CurrentGrid:
    """
    Regularly-gridded U/V current field on a lat/lon grid.

    Conventions
    -----------
    * ``u`` is positive eastward (m/s).
    * ``v`` is positive northward (m/s).
    * Row 0 is at ``lat0``; row i is at ``lat0 + i*dlat``.
    * Col 0 is at ``lon0``; col j is at ``lon0 + j*dlon``.
    """
    lat0: float
    lon0: float
    dlat: float
    dlon: float
    nrows: int
    ncols: int
    u: list[list[float]]
    v: list[list[float]]

    def bbox(self) -> tuple[float, float, float, float]:
        """Return (min_lat, min_lon, max_lat, max_lon)."""
        return (
            self.lat0,
            self.lon0,
            self.lat0 + (self.nrows - 1) * self.dlat,
            self.lon0 + (self.ncols - 1) * self.dlon,
        )

    def contains(self, lat: float, lon: float) -> bool:
        mn_lat, mn_lon, mx_lat, mx_lon = self.bbox()
        return mn_lat <= lat <= mx_lat and mn_lon <= lon <= mx_lon

    def sample(self, lat: float, lon: float) -> tuple[float, float]:
        """
        Bilinear interpolation of the U/V components at *(lat, lon)*.

        Returns ``(0.0, 0.0)`` if the point is outside the grid — callers
        should call :meth:`contains` first if they need to distinguish
        "no coverage" from "zero current".
        """
        if not self.contains(lat, lon) or self.dlat == 0 or self.dlon == 0:
            return 0.0, 0.0

        fi = (lat - self.lat0) / self.dlat
        fj = (lon - self.lon0) / self.dlon

        i0 = max(0, min(self.nrows - 1, int(math.floor(fi))))
        j0 = max(0, min(self.ncols - 1, int(math.floor(fj))))
        i1 = min(self.nrows - 1, i0 + 1)
        j1 = min(self.ncols - 1, j0 + 1)

        ti = fi - i0
        tj = fj - j0

        def _bilin(field: list[list[float]]) -> float:
            v00 = field[i0][j0]
            v01 = field[i0][j1]
            v10 = field[i1][j0]
            v11 = field[i1][j1]
            return (
                v00 * (1 - ti) * (1 - tj)
                + v01 * (1 - ti) * tj
                + v10 * ti * (1 - tj)
                + v11 * ti * tj
            )

        return _bilin(self.u), _bilin(self.v)

    def to_lookup_dict(self) -> dict[tuple[float, float], tuple[float, float]]:
        """
        Materialise the grid as a ``CurrentAwareStrategy``-compatible dict
        keyed by 0.5° grid coordinates.
        """
        out: dict[tuple[float, float], tuple[float, float]] = {}
        for i in range(self.nrows):
            lat = round((self.lat0 + i * self.dlat) * 2) / 2
            for j in range(self.ncols):
                lon = round((self.lon0 + j * self.dlon) * 2) / 2
                out[(lat, lon)] = (self.u[i][j], self.v[i][j])
        return out


# ── Loaders ──────────────────────────────────────────────────────────


def load_grib2(path: str | Path) -> CurrentGrid:
    """
    Read a GRIB2 file containing ``UOGRD`` and ``VOGRD`` ocean-current
    messages and return a :class:`CurrentGrid`.

    Requires ``pygrib`` at runtime. If unavailable, raises
    ``RuntimeError`` so callers can fall back to JSON / Stokes drift.
    """
    try:
        import pygrib  # type: ignore[import-not-found]
    except Exception as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(
            "pygrib is not installed — install eccodes + pygrib in this "
            "environment to read GRIB2, or use load_json instead."
        ) from exc

    grbs = pygrib.open(str(path))
    try:
        try:
            u_msg = grbs.select(shortName="ucur")[0]
            v_msg = grbs.select(shortName="vcur")[0]
        except Exception:
            u_msg = grbs.select(shortName="UOGRD")[0]
            v_msg = grbs.select(shortName="VOGRD")[0]

        u_data, lats, lons = u_msg.data()
        v_data, _, _ = v_msg.data()

        lat0 = float(lats[0, 0])
        lon0 = float(lons[0, 0])
        dlat = float(lats[1, 0] - lats[0, 0]) if lats.shape[0] > 1 else 0.0
        dlon = float(lons[0, 1] - lons[0, 0]) if lons.shape[1] > 1 else 0.0

        return CurrentGrid(
            lat0=lat0,
            lon0=lon0,
            dlat=dlat,
            dlon=dlon,
            nrows=int(u_data.shape[0]),
            ncols=int(u_data.shape[1]),
            u=u_data.tolist(),
            v=v_data.tolist(),
        )
    finally:
        grbs.close()


def load_json(path: str | Path) -> CurrentGrid:
    """Read a serialised :class:`CurrentGrid` written as JSON."""
    p = Path(path)
    payload = json.loads(p.read_text())
    return CurrentGrid(
        lat0=float(payload["lat0"]),
        lon0=float(payload["lon0"]),
        dlat=float(payload["dlat"]),
        dlon=float(payload["dlon"]),
        nrows=int(payload["nrows"]),
        ncols=int(payload["ncols"]),
        u=[[float(x) for x in row] for row in payload["u"]],
        v=[[float(x) for x in row] for row in payload["v"]],
    )


def load_auto(path: str | Path) -> Optional[CurrentGrid]:
    """Try GRIB2 first, fall back to JSON; return None on failure."""
    p = Path(path)
    if not p.exists():
        return None
    suffix = p.suffix.lower()
    if suffix in (".grb", ".grb2", ".grib", ".grib2"):
        try:
            return load_grib2(p)
        except RuntimeError as exc:
            logger.warning("GRIB2 load failed (%s); no JSON sibling available.", exc)
            return None
    try:
        return load_json(p)
    except Exception:
        logger.exception("Failed to load current grid from %s", p)
        return None
