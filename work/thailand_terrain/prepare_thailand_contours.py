"""Prepare broad stacked contour terraces for Thailand from real elevation data.

The output is deliberately generalized for the sandy-gold sculpture edition. It
uses a 600 m projected grid and an 18 km Gaussian blur before extracting broad
terraces. Raw source tiles and the exact boundary metadata stay beside this file.
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
PROJECT_ROOT = ROOT.parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "work" / "terrain_v2" / "deps"))

import contourpy
import numpy as np
from PIL import Image
from pyproj import Transformer
from scipy.ndimage import gaussian_filter, map_coordinates, median_filter
import shapely
from shapely.geometry import Polygon, box, shape
from shapely.ops import transform, unary_union

ZOOM = 9
SPACING_M = 600.0
SMOOTHING_M = 18_000.0
SIMPLIFY_M = 750.0
MIN_ISLAND_AREA_M2 = 20e6
MIN_TERRACE_AREA_M2 = 35e6
# The reference's simplified sculpture fills enclosed contour depressions so
# they do not read as stray dark dots or drilled holes in the physical layers.
MIN_HOLE_AREA_M2 = 1e30
LEVELS_M = [0, 100, 200, 400, 600, 800, 1000, 1200, 1400, 1600, 1800, 2000, 2200]
EPSG = 32647
WEB_R = 6_378_137.0
WEB_HALF = math.pi * WEB_R
WORLD_PIXELS = 256 * 2**ZOOM
WEB_PIXEL_M = 2 * WEB_HALF / WORLD_PIXELS
TILE_DIR = ROOT / f"tiles_z{ZOOM}"
TILE_DIR.mkdir(exist_ok=True, parents=True)
Image.MAX_IMAGE_PIXELS = None


def log(message: str) -> None:
    print(message, flush=True)


def fetch_tile(item: tuple[int, int]) -> tuple[tuple[int, int], int, bool]:
    tx, ty = item
    path = TILE_DIR / f"{ZOOM}_{tx}_{ty}.png"
    if path.exists():
        with Image.open(path) as image:
            image.load()
            if image.size != (256, 256):
                raise RuntimeError(f"Invalid cached tile: {path}")
        return item, path.stat().st_size, True
    url = f"https://elevation-tiles-prod.s3.amazonaws.com/terrarium/{ZOOM}/{tx}/{ty}.png"
    for attempt in range(5):
        try:
            request = urllib.request.Request(
                url, headers={"User-Agent": "Thailand sandy-gold relief render/1"}
            )
            with urllib.request.urlopen(request, timeout=45) as response:
                payload = response.read()
            with Image.open(io.BytesIO(payload)) as image:
                image.load()
                if image.size != (256, 256) or image.mode not in ("RGB", "RGBA"):
                    raise RuntimeError(f"Unexpected tile format: {image.size}, {image.mode}")
            temporary = path.with_suffix(".download")
            temporary.write_bytes(payload)
            temporary.replace(path)
            return item, len(payload), False
        except Exception:
            if attempt == 4:
                raise
            time.sleep(1.5 * 2**attempt)
    raise AssertionError("unreachable")


def ring_edges(parts: list[Polygon], lookup: dict[tuple[float, float], int]) -> np.ndarray:
    edges: list[tuple[int, int]] = []
    for part in parts:
        part = shapely.orient_polygons(part)
        for ring in [part.exterior, *part.interiors]:
            coordinates = np.asarray(ring.coords)
            ids = [lookup[tuple(value)] for value in coordinates]
            edges.extend(zip(ids[:-1], ids[1:]))
    return np.asarray(edges, dtype=np.int32)


def triangulate_region(region, center: np.ndarray, scale: float):
    triangles = shapely.get_parts(shapely.constrained_delaunay_triangles(region))
    triangle_xy = np.concatenate([shapely.get_coordinates(value)[:3] for value in triangles])
    xy, inverse = np.unique(triangle_xy, axis=0, return_inverse=True)
    top = inverse.reshape(-1, 3)
    a, b, c = xy[top[:, 0]], xy[top[:, 1]], xy[top[:, 2]]
    flip = ((b[:, 0] - a[:, 0]) * (c[:, 1] - a[:, 1]) - (b[:, 1] - a[:, 1]) * (c[:, 0] - a[:, 0])) < 0
    top[flip] = top[flip][:, ::-1]
    lookup = {tuple(value): index for index, value in enumerate(xy)}
    parts = list(shapely.get_parts(region))
    return ((xy - center) * scale).astype(np.float32), top.astype(np.int32), ring_edges(parts, lookup)


def main() -> None:
    started = time.monotonic()
    boundary_path = ROOT / "thailand_adm0.geojson"
    metadata_path = ROOT / "boundary_metadata.json"
    boundary_geojson = json.loads(boundary_path.read_text(encoding="utf-8"))
    boundary_metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    country_ll = shapely.make_valid(
        unary_union([shape(feature["geometry"]) for feature in boundary_geojson["features"]])
    )
    if not (97 < country_ll.bounds[0] < 99 and 105 < country_ll.bounds[2] < 107):
        raise RuntimeError(f"Unexpected Thailand longitude bounds: {country_ll.bounds}")
    if not (5 < country_ll.bounds[1] < 7 and 20 < country_ll.bounds[3] < 22):
        raise RuntimeError(f"Unexpected Thailand latitude bounds: {country_ll.bounds}")

    ll_to_web = Transformer.from_crs(4326, 3857, always_xy=True)
    ll_to_projected = Transformer.from_crs(4326, EPSG, always_xy=True)
    projected_to_web = Transformer.from_crs(EPSG, 3857, always_xy=True)
    country_web = transform(ll_to_web.transform, country_ll)
    country_projected = transform(ll_to_projected.transform, country_ll)
    min_web_x, min_web_y, max_web_x, max_web_y = country_web.bounds
    padding = 30_000.0
    min_web_x -= padding
    min_web_y -= padding
    max_web_x += padding
    max_web_y += padding
    tx0 = int((min_web_x + WEB_HALF) / WEB_PIXEL_M // 256)
    tx1 = int((max_web_x + WEB_HALF) / WEB_PIXEL_M // 256)
    ty0 = int((WEB_HALF - max_web_y) / WEB_PIXEL_M // 256)
    ty1 = int((WEB_HALF - min_web_y) / WEB_PIXEL_M // 256)
    tiles = [(tx, ty) for ty in range(ty0, ty1 + 1) for tx in range(tx0, tx1 + 1)]
    log(f"DOWNLOAD START: zoom {ZOOM}; {len(tiles)} tiles; bbox {tx0}:{tx1}, {ty0}:{ty1}")
    total_bytes = 0
    cached_count = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
        futures = [pool.submit(fetch_tile, tile) for tile in tiles]
        for done, future in enumerate(concurrent.futures.as_completed(futures), 1):
            _, count, cached = future.result()
            total_bytes += count
            cached_count += int(cached)
            if done % 50 == 0 or done == len(tiles):
                log(f"DOWNLOAD {done}/{len(tiles)}; {total_bytes / 1e6:.1f} MB; {cached_count} cached")

    mosaic_shape = ((ty1 - ty0 + 1) * 256, (tx1 - tx0 + 1) * 256)
    mosaic = np.lib.format.open_memmap(
        ROOT / f"source_zoom{ZOOM}.npy", mode="w+", dtype="float32", shape=mosaic_shape
    )
    native_min, native_max = math.inf, -math.inf
    corrected_count = 0
    for index, (tx, ty) in enumerate(tiles):
        with Image.open(TILE_DIR / f"{ZOOM}_{tx}_{ty}.png") as image:
            rgb = np.asarray(image.convert("RGB"), dtype=np.float32)
        decoded = rgb[:, :, 0] * 256 + rgb[:, :, 1] + rgb[:, :, 2] / 256 - 32768
        local = median_filter(decoded, size=5, mode="nearest")
        bad = (np.abs(decoded - local) > 250) | (decoded < -100) | (decoded > 3000)
        decoded[bad] = local[bad]
        corrected_count += int(bad.sum())
        native_min = min(native_min, float(decoded.min()))
        native_max = max(native_max, float(decoded.max()))
        row, column = (ty - ty0) * 256, (tx - tx0) * 256
        mosaic[row : row + 256, column : column + 256] = decoded
        if (index + 1) % 100 == 0:
            log(f"MOSAIC {index + 1}/{len(tiles)}")
    mosaic.flush()

    min_x, min_y, max_x, max_y = country_projected.bounds
    x0 = math.floor(min_x / SPACING_M) * SPACING_M - 2 * SPACING_M
    x1 = math.ceil(max_x / SPACING_M) * SPACING_M + 2 * SPACING_M
    y0 = math.ceil(max_y / SPACING_M) * SPACING_M + 2 * SPACING_M
    y1 = math.floor(min_y / SPACING_M) * SPACING_M - 2 * SPACING_M
    x_m = np.arange(x0, x1 + SPACING_M / 2, SPACING_M, dtype=np.float64)
    y_m = np.arange(y0, y1 - SPACING_M / 2, -SPACING_M, dtype=np.float64)
    elevation = np.zeros((y_m.size, x_m.size), dtype=np.float32)
    for row in range(0, y_m.size, 96):
        rows = slice(row, min(row + 96, y_m.size))
        xx, yy = np.meshgrid(x_m, y_m[rows])
        web_x, web_y = projected_to_web.transform(xx, yy)
        pixel_x = (web_x + WEB_HALF) / WEB_PIXEL_M - tx0 * 256 - 0.5
        pixel_y = (WEB_HALF - web_y) / WEB_PIXEL_M - ty0 * 256 - 0.5
        values = map_coordinates(
            mosaic, [pixel_y, pixel_x], order=1, mode="nearest", prefilter=False
        )
        elevation[rows] = values.astype(np.float32)
    valid_mask = shapely.contains_xy(country_projected, *np.meshgrid(x_m, y_m))
    raw_country_min = float(elevation[valid_mask].min())
    negative_country_count = int(np.sum(elevation[valid_mask] < 0))
    # Terrarium contains a few coastal/interpolation samples below sea level
    # inside the ADM0 polygon. Thailand's land terraces start at zero metres.
    elevation[elevation < 0] = 0
    smoothed = gaussian_filter(elevation.astype(np.float64), SMOOTHING_M / SPACING_M)
    valid = elevation[valid_mask]
    smooth_valid = smoothed[valid_mask]
    if not (0 <= float(valid.min()) < 100 and 2300 < float(valid.max()) < 2800):
        raise RuntimeError(
            f"Implausible Thailand elevation range: {float(valid.min())}..{float(valid.max())} m"
        )
    log(
        f"GRID {elevation.shape}; raw {float(valid.min()):.1f}..{float(valid.max()):.1f} m; "
        f"smoothed {float(smooth_valid.min()):.1f}..{float(smooth_valid.max()):.1f} m"
    )

    boundary = shapely.make_valid(country_projected.simplify(SIMPLIFY_M, preserve_topology=True))
    boundary_parts = [
        Polygon(part.exterior, [ring for ring in part.interiors if Polygon(ring).area > MIN_HOLE_AREA_M2])
        for part in shapely.get_parts(boundary)
        if part.geom_type == "Polygon" and part.area > MIN_ISLAND_AREA_M2
    ]
    boundary = shapely.MultiPolygon(boundary_parts)
    contour_generator = contourpy.contour_generator(
        x=x_m, y=y_m[::-1], z=smoothed[::-1], fill_type="OuterOffset"
    )
    center = np.asarray(boundary.bounds).reshape(2, 2).mean(axis=0)
    scale = 6e-6
    arrays: dict[str, np.ndarray] = {}
    summary: list[dict[str, int]] = []
    for level in LEVELS_M:
        if level == 0:
            region = boundary
        else:
            points, offsets = contour_generator.filled(level, 10_000)
            polygons = []
            for point_array, offset_array in zip(points, offsets):
                rings = [point_array[a:b] for a, b in zip(offset_array[:-1], offset_array[1:])]
                polygon = Polygon(rings[0], rings[1:])
                if polygon.area > MIN_TERRACE_AREA_M2:
                    polygons.append(polygon)
            if not polygons:
                continue
            region = shapely.intersection(shapely.union_all(polygons), boundary)
            region = region.buffer(4500, quad_segs=8).buffer(-4500, quad_segs=8)
            region = region.buffer(-1800, quad_segs=8).buffer(1800, quad_segs=8)
            region = shapely.make_valid(region.simplify(SIMPLIFY_M, preserve_topology=True))
            parts = [
                Polygon(part.exterior, [ring for ring in part.interiors if Polygon(ring).area > MIN_HOLE_AREA_M2])
                for part in shapely.get_parts(region)
                if part.geom_type == "Polygon" and part.area > MIN_TERRACE_AREA_M2
            ]
            if not parts:
                continue
            region = shapely.MultiPolygon(parts)
        xy, triangles, edges = triangulate_region(region, center, scale)
        arrays[f"xy_{level}"] = xy
        arrays[f"tri_{level}"] = triangles
        arrays[f"edge_{level}"] = edges
        parts = list(shapely.get_parts(region))
        info = {
            "level_m": level,
            "islands": len(parts),
            "holes": sum(len(part.interiors) for part in parts),
            "vertices": len(xy),
            "triangles": len(triangles),
        }
        summary.append(info)
        log(f"LAYER {info}")

    if len(summary) < 6 or summary[-1]["level_m"] < 1000:
        raise RuntimeError(f"Too few usable terraces: {summary}")
    capital = np.asarray(ll_to_projected.transform(100.5018, 13.7563))
    contour_metadata = {
        "country": "Thailand",
        "country_iso3": "THA",
        "capital": "Bangkok",
        "capital_lon_lat": [100.5018, 13.7563],
        "pin_xy": ((capital - center) * scale).tolist(),
        "projection": f"EPSG:{EPSG} (WGS 84 / UTM zone 47N)",
        "grid_spacing_m": SPACING_M,
        "smoothing_sigma_m": SMOOTHING_M,
        "simplification_m": SIMPLIFY_M,
        "minimum_island_area_m2": MIN_ISLAND_AREA_M2,
        "minimum_terrace_area_m2": MIN_TERRACE_AREA_M2,
        "minimum_hole_area_m2": MIN_HOLE_AREA_M2,
        "blender_xy_scale_per_m": scale,
        "layers": summary,
        "boundary_bounds_wsen": list(country_ll.bounds),
        "boundary_metadata": boundary_metadata,
        "boundary_sha256": "226eeef03694dc708201f142c992a819798841c0302c89e78cac8579b5058cde",
        "elevation_source": "Mapzen Terrain Tiles, Terrarium format, AWS elevation-tiles-prod",
        "elevation_url_template": "https://elevation-tiles-prod.s3.amazonaws.com/terrarium/{z}/{x}/{y}.png",
        "elevation_accessed": "2026-09-12",
        "zoom": ZOOM,
        "downloaded_tiles": len(tiles),
        "downloaded_bytes": total_bytes,
        "cached_tiles": cached_count,
        "raw_country_min_elevation_m": float(valid.min()),
        "raw_country_max_elevation_m": float(valid.max()),
        "source_country_min_before_land_floor_m": raw_country_min,
        "source_country_negative_samples_corrected": negative_country_count,
        "smoothed_country_min_elevation_m": float(smooth_valid.min()),
        "smoothed_country_max_elevation_m": float(smooth_valid.max()),
        "source_tile_min_elevation_m": native_min,
        "source_tile_max_elevation_m": native_max,
        "source_outlier_corrections": corrected_count,
        "elapsed_seconds": time.monotonic() - started,
        "artistic_note": "Generalized relief sculpture; not for survey, navigation, or authoritative borders.",
    }
    np.savez_compressed(ROOT / "contour_layers_minimal.npz", **arrays)
    (ROOT / "contour_layers_minimal.json").write_text(
        json.dumps(contour_metadata, indent=2), encoding="utf-8"
    )
    log(f"THAILAND_CONTOUR_DATA_COMPLETE in {time.monotonic() - started:.1f}s")


if __name__ == "__main__":
    main()
