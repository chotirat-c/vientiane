"""Rebuild Laos relief from real zoom-11 Terrarium elevations.

All generated data remain inside this script's work/terrain_v2 directory.
Reference: https://github.com/tilezen/joerd/blob/master/docs/formats.md
"""
from __future__ import annotations

import concurrent.futures
import io
import json
import math
from pathlib import Path
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "deps"))
import numpy as np
from PIL import Image
from scipy.ndimage import map_coordinates, median_filter
import shapely
from shapely.geometry import shape, box
from shapely.ops import transform, unary_union
from pyproj import Transformer

ZOOM = 11
SPACING = 150.0
WEB_R = 6378137.0
WEB_HALF = math.pi * WEB_R
WORLD_PIXELS = 256 * 2**ZOOM
WEB_PIXEL = 2 * WEB_HALF / WORLD_PIXELS
TILE_DIR = ROOT / "tiles_z11"
TILE_DIR.mkdir(exist_ok=True, parents=True)
Image.MAX_IMAGE_PIXELS = None


def log(message):
    print(message, flush=True)


def fetch_tile(item):
    tx, ty = item
    path = TILE_DIR / f"{ZOOM}_{tx}_{ty}.png"
    if path.exists():
        with Image.open(path) as im:
            im.load()
            if im.size != (256, 256):
                raise RuntimeError(f"Invalid cached tile {path}")
        return item, path.stat().st_size, True
    url = f"https://elevation-tiles-prod.s3.amazonaws.com/terrarium/{ZOOM}/{tx}/{ty}.png"
    for attempt in range(5):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "Laos relief research render/2"})
            with urllib.request.urlopen(request, timeout=45) as response:
                payload = response.read()
            with Image.open(io.BytesIO(payload)) as im:
                im.load()
                if im.size != (256, 256) or im.mode not in ("RGB", "RGBA"):
                    raise RuntimeError(f"Unexpected tile format {im.size}, {im.mode}")
            temporary = path.with_suffix(".download")
            temporary.write_bytes(payload)
            temporary.replace(path)
            return item, len(payload), False
        except Exception:
            if attempt == 4:
                raise
            time.sleep(1.5 * 2**attempt)


def main():
    start = time.monotonic()
    geo = json.loads((ROOT.parent / "laos_adm0.geojson").read_text(encoding="utf-8"))
    country_ll = shapely.make_valid(unary_union([shape(f["geometry"]) for f in geo["features"]]))
    ll_to_web = Transformer.from_crs(4326, 3857, always_xy=True)
    ll_to_utm = Transformer.from_crs(4326, 32648, always_xy=True)
    utm_to_web = Transformer.from_crs(32648, 3857, always_xy=True)
    country_web = transform(ll_to_web.transform, country_ll)
    country_utm = transform(ll_to_utm.transform, country_ll)
    shapely.prepare(country_web)
    shapely.prepare(country_utm)
    coverage = country_web.buffer(1200)
    minwx, minwy, maxwx, maxwy = coverage.bounds
    tx0 = int((minwx + WEB_HALF) / WEB_PIXEL // 256)
    tx1 = int((maxwx + WEB_HALF) / WEB_PIXEL // 256)
    ty0 = int((WEB_HALF - maxwy) / WEB_PIXEL // 256)
    ty1 = int((WEB_HALF - minwy) / WEB_PIXEL // 256)
    tiles = []
    for ty in range(ty0, ty1 + 1):
        for tx in range(tx0, tx1 + 1):
            left = tx * 256 * WEB_PIXEL - WEB_HALF
            right = left + 256 * WEB_PIXEL
            top = WEB_HALF - ty * 256 * WEB_PIXEL
            bottom = top - 256 * WEB_PIXEL
            if coverage.intersects(box(left, bottom, right, top)):
                tiles.append((tx, ty))
    log(f"DOWNLOAD START: zoom {ZOOM}; {len(tiles)} selected tiles; bbox {tx0}:{tx1}, {ty0}:{ty1}; workers=12")
    total_bytes = 0
    cache_count = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
        futures = [pool.submit(fetch_tile, tile) for tile in tiles]
        for done, future in enumerate(concurrent.futures.as_completed(futures), 1):
            _, count, cached = future.result()
            total_bytes += count
            cache_count += int(cached)
            if done % 50 == 0 or done == len(tiles):
                log(f"DOWNLOAD {done}/{len(tiles)}; {total_bytes / 1e6:.1f} MB; {cache_count} cached; elapsed {time.monotonic()-start:.1f}s")

    mosaic_shape = ((ty1 - ty0 + 1) * 256, (tx1 - tx0 + 1) * 256)
    mosaic = np.lib.format.open_memmap(ROOT / "source_zoom11.npy", mode="w+", dtype="float32", shape=mosaic_shape)
    mosaic[:] = np.nan
    native_min, native_max = math.inf, -math.inf
    native_count = 0
    corrected_count = 0
    for index, (tx, ty) in enumerate(tiles):
        with Image.open(TILE_DIR / f"{ZOOM}_{tx}_{ty}.png") as im:
            rgb = np.asarray(im.convert("RGB"), dtype=np.float32)
        decoded = rgb[:, :, 0] * 256 + rgb[:, :, 1] + rgb[:, :, 2] / 256 - 32768
        # Source contains sparse resampling spikes/pits (e.g. 8679 m amid
        # 884 m neighbours). Replace only strong local outliers, not all terrain.
        local = median_filter(decoded, size=5, mode="nearest")
        bad = (np.abs(decoded-local) > 250) | (decoded < 0) | (decoded > 3100)
        decoded[bad] = local[bad]
        corrected_count += int(bad.sum())
        # Geographic tile pixels describe samples at pixel centers.
        xx = ((tx * 256 + np.arange(256) + 0.5) * WEB_PIXEL - WEB_HALF)[None, :]
        yy = (WEB_HALF - (ty * 256 + np.arange(256) + 0.5) * WEB_PIXEL)[:, None]
        native_mask = shapely.contains_xy(country_web, xx, yy)
        vals = decoded[native_mask]
        if vals.size:
            if np.any(vals <= -32000) or not np.isfinite(vals).all():
                raise RuntimeError(f"Nodata in country at tile {tx}/{ty}")
            native_min = min(native_min, float(vals.min()))
            native_max = max(native_max, float(vals.max()))
            native_count += vals.size
        row, col = (ty - ty0) * 256, (tx - tx0) * 256
        mosaic[row:row+256, col:col+256] = decoded
        if (index + 1) % 150 == 0:
            log(f"MOSAIC {index+1}/{len(tiles)}")
    mosaic.flush()
    log(f"NATIVE country samples {native_count:,}; elevation {native_min:.3f} to {native_max:.3f} m")
    if not (0 <= native_min < 200 and 2500 < native_max < 3100):
        raise RuntimeError("Implausible elevation extent for Laos; inspect source before rendering")

    minx, miny, maxx, maxy = country_utm.bounds
    # A 300-m margin leaves every boundary sample inside the raster extent.
    x0 = math.floor(minx / SPACING) * SPACING - 300
    x1 = math.ceil(maxx / SPACING) * SPACING + 300
    y0 = math.ceil(maxy / SPACING) * SPACING + 300
    y1 = math.floor(miny / SPACING) * SPACING - 300
    x_m = np.arange(x0, x1 + SPACING / 2, SPACING, dtype=np.float64)
    y_m = np.arange(y0, y1 - SPACING / 2, -SPACING, dtype=np.float64)
    dims = (y_m.size, x_m.size)
    elevation = np.zeros(dims, dtype=np.float32)
    mask = np.zeros(dims, dtype=bool)
    log(f"REPROJECT mesh EPSG:32648; shape={dims}; step={SPACING} m")

    def sample_rows(xs, ys):
        xx, yy = np.meshgrid(xs, ys)
        inside = shapely.contains_xy(country_utm, xx, yy)
        wx, wy = utm_to_web.transform(xx, yy)
        pixel_x = (wx + WEB_HALF) / WEB_PIXEL - tx0 * 256 - 0.5
        pixel_y = (WEB_HALF - wy) / WEB_PIXEL - ty0 * 256 - 0.5
        values = map_coordinates(mosaic, [pixel_y, pixel_x], order=1, mode="constant", cval=np.nan, prefilter=False)
        if not np.isfinite(values[inside]).all():
            raise RuntimeError("Missing terrain tile coverage at a country sample")
        if np.any(values[inside] <= -32000):
            raise RuntimeError("Source nodata in reprojected country terrain")
        # Outside-country values are retained where downloaded, to allow
        # interpolated border positions and physical derivatives at the edge.
        values = np.nan_to_num(values, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32)
        return values, inside

    for row in range(0, dims[0], 64):
        rows = slice(row, min(row + 64, dims[0]))
        elevation[rows], mask[rows] = sample_rows(x_m, y_m[rows])
        if row % 1024 == 0:
            log(f"MESH rows {row}/{dims[0]}")
    valid = elevation[mask]
    log(f"MESH valid vertices {valid.size:,}; {float(valid.min()):.3f} to {float(valid.max()):.3f} m; saving")
    np.savez_compressed(ROOT / "dem_mesh.npz", elevation_m=elevation, mask=mask, x_m=x_m, y_m=y_m)
    meta = {
        "source": "Mapzen Terrain Tiles (Terrarium), AWS elevation-tiles-prod",
        "source_url_template": "https://elevation-tiles-prod.s3.amazonaws.com/terrarium/{z}/{x}/{y}.png",
        "format_documentation": "https://github.com/tilezen/joerd/blob/master/docs/formats.md",
        "source_registry": "https://registry.opendata.aws/terrain-tiles/",
        "accessed": "2026-09-05",
        "zoom": ZOOM,
        "downloaded_tiles": len(tiles),
        "downloaded_bytes": total_bytes,
        "source_native_resolution_projected_webmercator_m": WEB_PIXEL,
        "source_native_resolution_ground_m_at_south_north": [WEB_PIXEL * math.cos(math.radians(country_ll.bounds[1])), WEB_PIXEL * math.cos(math.radians(country_ll.bounds[3]))],
        "source_elevation_decoding": "R*256 + G + B/256 - 32768 metres; decode before interpolation",
        "source_tile_sample_convention": "pixel centers; column increases east, row increases south",
        "source_country_sample_count": native_count,
        "source_outlier_corrections": corrected_count,
        "source_outlier_method": "Selective 5x5 median replacement only where local deviation exceeds 250 m or source is outside 0..3100 m; removes sparse obvious source spikes/pits without smoothing the general surface.",
        "source_country_min_elevation_m": native_min,
        "source_country_max_elevation_m": native_max,
        "source_mosaic_file": "source_zoom11.npy",
        "source_mosaic_shape": list(mosaic_shape),
        "source_tile_bbox_xy_inclusive": [tx0, ty0, tx1, ty1],
        "boundary": "Existing geoBoundaries gbOpen LAO ADM0, historical boundary dataset (2017 as recorded by parent workflow); display outline, not a boundary authority",
        "boundary_source": "https://www.geoboundaries.org/api/current/gbOpen/LAO/ADM0/",
        "geographic_bounds_wsen": list(country_ll.bounds),
        "projection": "EPSG:32648 (WGS 84 / UTM zone 48N)",
        "grid_spacing_m": SPACING,
        "shape_hw": list(dims),
        "valid_vertices": int(valid.size),
        "min_elevation_m": float(valid.min()),
        "max_elevation_m": float(valid.max()),
        "negative_in_country_count": int(np.sum(valid < 0)),
        "missing_in_country_count": int(np.sum(~np.isfinite(valid))),
        "x_m": "1D increasing easting in meters; corresponds to columns; samples are vertices",
        "y_m": "1D DECREASING northing in meters; corresponds to rows; row 0 is north",
        "elevation_m": "2D float32; bilinear source interpolation after decoding; no vertical exaggeration and no artificial noise",
        "mask": "2D bool; true where the grid point lies inside the country; outside-country elevations retained where source coverage exists, otherwise zero",
        "grid_extent_xmin_ymin_xmax_ymax": [float(x_m[0]), float(y_m[-1]), float(x_m[-1]), float(y_m[0])],
        "elapsed_seconds": time.monotonic()-start,
    }
    (ROOT / "dem_metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    log("MESH READY: " + str(ROOT / "dem_mesh.npz"))

    # Twice-dense real elevation texture, 16-bit PNG. It stores metres/3200,
    # not visible colors. Non-Color handling is required in Blender.
    xs = np.linspace(x_m[0], x_m[-1], (x_m.size - 1) * 2 + 1)
    ys = np.linspace(y_m[0], y_m[-1], (y_m.size - 1) * 2 + 1)
    texture = np.zeros((ys.size, xs.size), dtype=np.uint16)
    log(f"DETAIL texture shape={texture.shape}, 75 m samples")
    for row in range(0, ys.size, 48):
        rows = slice(row, min(row + 48, ys.size))
        values, _ = sample_rows(xs, ys[rows])
        texture[rows] = np.round(np.clip(values, 0, 3200) * (65535 / 3200)).astype(np.uint16)
        if row % 1920 == 0:
            log(f"DETAIL rows {row}/{ys.size}")
    Image.fromarray(texture).save(ROOT / "dem_detail_75m.png", compress_level=4)
    meta["detail_texture"] = {
        "filename": "dem_detail_75m.png",
        "shape_hw": list(texture.shape),
        "grid_spacing_m": 75.0,
        "encoding": "uint16 PNG normalized [0,65535] maps to [0,3200] metres; load as Non-Color",
        "orientation": "row0 north, col0 west; same first/last grid coordinate extent as mesh",
        "blender_uv": "u=(x-x_min)/(x_max-x_min); v=(y-y_min)/(y_max-y_min); no y inversion for ordinary Blender image textures",
    }
    meta["elapsed_seconds"] = time.monotonic()-start
    (ROOT / "dem_metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    log(f"DONE in {time.monotonic()-start:.1f}s")


if __name__ == "__main__":
    main()
