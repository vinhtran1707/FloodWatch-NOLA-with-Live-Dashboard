from __future__ import annotations

import numpy as np

# D8 neighbor offsets (row, col) and cardinal/diagonal distances
_OFFSETS: list[tuple[int, int]] = [
    (-1, -1), (-1, 0), (-1, 1),
    ( 0, -1),          ( 0, 1),
    ( 1, -1), ( 1, 0), ( 1, 1),
]
_DIST: list[float] = [1.414, 1.0, 1.414, 1.0, 1.0, 1.414, 1.0, 1.414]


def smooth_dem(dem: np.ndarray, passes: int = 3) -> np.ndarray:
    """Box-filter to reduce flat-terrain noise before running D8."""
    dem = dem.astype(float)
    for _ in range(passes):
        pad = np.pad(dem, 1, mode="edge")
        dem = (
            pad[:-2, :-2] + pad[:-2, 1:-1] + pad[:-2, 2:]
            + pad[1:-1, :-2] + pad[1:-1, 1:-1] + pad[1:-1, 2:]
            + pad[2:, :-2] + pad[2:, 1:-1] + pad[2:, 2:]
        ) / 9.0
    return dem


def d8_flow_direction(dem: np.ndarray) -> np.ndarray:
    """
    D8 flow direction: each cell stores the index into _OFFSETS pointing
    toward the steepest downslope neighbor. -1 means local sink.
    """
    rows, cols = dem.shape
    flow = np.full((rows, cols), -1, dtype=np.int8)
    for r in range(rows):
        for c in range(cols):
            best, best_slope = -1, 0.0
            for i, (dr, dc) in enumerate(_OFFSETS):
                nr, nc = r + dr, c + dc
                if 0 <= nr < rows and 0 <= nc < cols:
                    slope = (dem[r, c] - dem[nr, nc]) / _DIST[i]
                    if slope > best_slope:
                        best_slope, best = slope, i
            flow[r, c] = best
    return flow


def flow_accumulation(dem: np.ndarray, flow_dir: np.ndarray) -> np.ndarray:
    """
    Count upstream cells draining through each cell.
    Process highest-to-lowest so each cell's tally is complete before
    it contributes downstream.
    """
    rows, cols = dem.shape
    accum = np.ones((rows, cols), dtype=np.int32)
    for idx in np.argsort(dem.ravel())[::-1]:
        r, c = divmod(int(idx), cols)
        d = int(flow_dir[r, c])
        if d >= 0:
            dr, dc = _OFFSETS[d]
            nr, nc = r + dr, c + dc
            if 0 <= nr < rows and 0 <= nc < cols:
                accum[nr, nc] += accum[r, c]
    return accum


def extract_flow_paths(
    accum: np.ndarray,
    flow_dir: np.ndarray,
    lats: list[float],
    lons: list[float],
) -> list[dict]:
    """
    Convert accumulation grid to PyDeck PathLayer records.

    Three tiers based on accumulation percentile:
      major (top 10%)    — cyan,  width 5
      secondary (10-30%) — blue,  width 3
      minor (30-55%)     — indigo, width 1

    Returns list of dicts with keys: path, color, width, tier, accumulation.
    """
    rows, cols = accum.shape
    lats_arr = np.array(lats)
    lons_arr = np.array(lons)

    p90 = float(np.percentile(accum, 90))
    p70 = float(np.percentile(accum, 70))
    p45 = float(np.percentile(accum, 45))

    paths: list[dict] = []
    for r in range(rows):
        for c in range(cols):
            a = int(accum[r, c])
            if a < p45:
                continue
            d = int(flow_dir[r, c])
            if d < 0:
                continue
            dr, dc = _OFFSETS[d]
            nr, nc = r + dr, c + dc
            if not (0 <= nr < rows and 0 <= nc < cols):
                continue

            # PyDeck PathLayer expects [lon, lat]
            seg = [
                [float(lons_arr[c]),  float(lats_arr[r])],
                [float(lons_arr[nc]), float(lats_arr[nr])],
            ]

            if a >= p90:
                color, width, tier = [6, 182, 212], 5, "major"
            elif a >= p70:
                color, width, tier = [14, 165, 233], 3, "secondary"
            else:
                color, width, tier = [30, 64, 175], 1, "minor"

            paths.append({
                "path": seg,
                "color": color,
                "width": width,
                "tier": tier,
                "accumulation": a,
            })
    return paths


def run_hydrology(elev_data: dict) -> dict:
    """
    Full pipeline: smooth → D8 direction → accumulation → paths.
    elev_data is the dict returned by get_elevation_grid().
    Returns {"dem_smooth", "flow_dir", "accum", "flow_paths"}.
    """
    dem = np.array(elev_data["dem"], dtype=float)
    lats = elev_data["lats"]
    lons = elev_data["lons"]

    dem_s = smooth_dem(dem, passes=3)
    fdir  = d8_flow_direction(dem_s)
    accum = flow_accumulation(dem_s, fdir)
    paths = extract_flow_paths(accum, fdir, lats, lons)

    return {
        "dem_smooth": dem_s,
        "flow_dir":   fdir,
        "accum":      accum,
        "flow_paths": paths,
    }
