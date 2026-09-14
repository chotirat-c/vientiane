"""Create Thailand's blue-relief DEM at the Laos edition's 150 m resolution."""
from __future__ import annotations

import concurrent.futures
import functools
import io
import json
import math
from pathlib import Path
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "work" / "terrain_v2" / "deps"))

import numpy as np
from PIL import Image
from pyproj import Transformer
from scipy.ndimage import map_coordinates, median_filter
import shapely
from shapely.geometry import box, shape
from shapely.ops import transform, unary_union

ZOOM = 11
SPACING_M = 150.0
EPSG = 32647
WEB_R = 6_378_137.0
WEB_HALF = math.pi * WEB_R
WEB_PIXEL_M = 2 * WEB_HALF / (256 * 2**ZOOM)
TILE_DIR = ROOT / "tiles_z11"
TILE_DIR.mkdir(exist_ok=True, parents=True)
Image.MAX_IMAGE_PIXELS = None


def log(message: str) -> None:
    print(message, flush=True)


def fetch_tile(item: tuple[int, int]):
    tx, ty = item
    path = TILE_DIR / f"{ZOOM}_{tx}_{ty}.png"
    if path.exists():
        with Image.open(path) as image:
            image.load()
            if image.size != (256, 256):
                raise RuntimeError(f"Invalid cached tile {path}")
        return path.stat().st_size, True
    url = f"https://elevation-tiles-prod.s3.amazonaws.com/terrarium/{ZOOM}/{tx}/{ty}.png"
    for attempt in range(5):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "Thailand blue relief / 150m"})
            with urllib.request.urlopen(request, timeout=45) as response:
                payload = response.read()
            with Image.open(io.BytesIO(payload)) as image:
                image.load()
                if image.size != (256, 256) or image.mode not in ("RGB", "RGBA"):
                    raise RuntimeError(f"Unexpected terrain tile {tx}/{ty}")
            temporary = path.with_suffix(".download")
            temporary.write_bytes(payload)
            temporary.replace(path)
            return len(payload), False
        except Exception:
            if attempt == 4:
                raise
            time.sleep(1.5 * 2**attempt)


def main() -> None:
    started = time.monotonic()
    boundary_geojson = json.loads((ROOT / "thailand_adm0.geojson").read_text(encoding="utf-8"))
    country_ll = shapely.make_valid(unary_union([shape(feature["geometry"]) for feature in boundary_geojson["features"]]))
    ll_to_web = Transformer.from_crs(4326, 3857, always_xy=True)
    ll_to_utm = Transformer.from_crs(4326, EPSG, always_xy=True)
    utm_to_web = Transformer.from_crs(EPSG, 3857, always_xy=True)
    country_web = transform(ll_to_web.transform, country_ll)
    country_utm = transform(ll_to_utm.transform, country_ll)
    coverage = country_web.buffer(1200)
    min_x, min_y, max_x, max_y = coverage.bounds
    tx0 = int((min_x + WEB_HALF) / WEB_PIXEL_M // 256)
    tx1 = int((max_x + WEB_HALF) / WEB_PIXEL_M // 256)
    ty0 = int((WEB_HALF - max_y) / WEB_PIXEL_M // 256)
    ty1 = int((WEB_HALF - min_y) / WEB_PIXEL_M // 256)
    tiles = []
    for ty in range(ty0, ty1 + 1):
        for tx in range(tx0, tx1 + 1):
            left = tx * 256 * WEB_PIXEL_M - WEB_HALF
            top = WEB_HALF - ty * 256 * WEB_PIXEL_M
            if coverage.intersects(box(left, top - 256 * WEB_PIXEL_M, left + 256 * WEB_PIXEL_M, top)):
                tiles.append((tx, ty))
    log(f"DOWNLOAD START zoom={ZOOM}; selected tiles={len(tiles)}")
    total_bytes = cached = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
        futures = [pool.submit(fetch_tile, tile) for tile in tiles]
        for complete, future in enumerate(concurrent.futures.as_completed(futures), 1):
            count, from_cache = future.result()
            total_bytes += count
            cached += int(from_cache)
            if complete % 100 == 0 or complete == len(tiles):
                log(f"DOWNLOAD {complete}/{len(tiles)}; {total_bytes / 1e6:.1f} MB; cache={cached}")

    @functools.lru_cache(maxsize=256)
    def decoded_tile(tx: int, ty: int) -> np.ndarray:
        with Image.open(TILE_DIR / f"{ZOOM}_{tx}_{ty}.png") as image:
            rgb = np.asarray(image.convert("RGB"), dtype=np.float32)
        decoded = rgb[:, :, 0] * 256 + rgb[:, :, 1] + rgb[:, :, 2] / 256 - 32768
        local = median_filter(decoded, size=5, mode="nearest")
        bad = (np.abs(decoded - local) > 250) | (decoded < -150) | (decoded > 3000)
        decoded[bad] = local[bad]
        return decoded

    corrections = 0  # Tiles are selectively repaired during every sample decode.
    log("TILES READY; direct high-resolution sampling begins")

    min_x, min_y, max_x, max_y = country_utm.bounds
    x_m = np.arange(math.floor(min_x / SPACING_M) * SPACING_M - 300, math.ceil(max_x / SPACING_M) * SPACING_M + 300 + SPACING_M / 2, SPACING_M)
    y_m = np.arange(math.ceil(max_y / SPACING_M) * SPACING_M + 300, math.floor(min_y / SPACING_M) * SPACING_M - 300 - SPACING_M / 2, -SPACING_M)
    elevation = np.zeros((y_m.size, x_m.size), dtype=np.float32)
    mask = np.zeros(elevation.shape, dtype=bool)
    log(f"REPROJECT mesh EPSG:{EPSG}; shape={elevation.shape}; step=150m")

    def sample_rows(xs: np.ndarray, ys: np.ndarray):
        xx, yy = np.meshgrid(xs, ys)
        inside = shapely.contains_xy(country_utm, xx, yy)
        values = np.zeros(xx.shape, dtype=np.float32)
        web_x, web_y = utm_to_web.transform(xx[inside], yy[inside])
        source_x = (web_x + WEB_HALF) / WEB_PIXEL_M - 0.5
        source_y = (WEB_HALF - web_y) / WEB_PIXEL_M - 0.5
        tile_x = np.floor_divide(source_x.astype(np.int64), 256)
        tile_y = np.floor_divide(source_y.astype(np.int64), 256)
        local_x = source_x - tile_x * 256
        local_y = source_y - tile_y * 256
        sampled = np.empty(source_x.size, dtype=np.float32)
        for tx, ty in np.unique(np.column_stack((tile_x, tile_y)), axis=0):
            selected = (tile_x == tx) & (tile_y == ty)
            sampled[selected] = map_coordinates(
                decoded_tile(int(tx), int(ty)), [local_y[selected], local_x[selected]],
                order=1, mode="nearest", prefilter=False,
            )
        values[inside] = sampled
        return values, inside

    for row in range(0, y_m.size, 48):
        rows = slice(row, min(row + 48, y_m.size))
        values, inside = sample_rows(x_m, y_m[rows])
        elevation[rows] = values
        mask[rows] = inside
        if row % 960 == 0:
            log(f"MESH {row}/{y_m.size}")
    elevation[elevation < 0] = 0
    valid = elevation[mask]
    center = np.asarray(country_utm.bounds).reshape(2, 2).mean(axis=0)
    metadata = {
        "country": "Thailand", "country_iso3": "THA", "projection": "EPSG:32647 (WGS 84 / UTM zone 47N)",
        "grid_spacing_m": SPACING_M, "source_zoom": ZOOM, "source_web_pixel_m": WEB_PIXEL_M,
        "source": "Mapzen Terrain Tiles (Terrarium), AWS elevation-tiles-prod", "downloaded_tiles": len(tiles),
        "cached_tiles": cached, "source_outlier_corrections": corrections, "center_projected_m": center.tolist(),
        "min_elevation_m": float(valid.min()), "max_elevation_m": float(valid.max()),
        "detail": "Same 150 m terrain-grid resolution as the Laos blue edition; no Gaussian terrain smoothing.",
    }
    np.savez_compressed(ROOT / "thailand_blue_dem_150m.npz", elevation_m=elevation, mask=mask, x_m=x_m, y_m=y_m)
    (ROOT / "thailand_blue_dem_150m.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    log(f"THAILAND_150M_DEM_READY valid={valid.size:,}; range={valid.min():.1f}..{valid.max():.1f}m; elapsed={time.monotonic()-started:.1f}s")


if __name__ == "__main__":
    main()
