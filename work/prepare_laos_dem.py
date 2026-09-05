import io
import json
import math
import os
import urllib.request

import numpy as np
from PIL import Image, ImageDraw


GEOJSON_PATH = r"C:\Users\mikasaloli\Documents\Codex\2026-09-05\ho\work\laos_adm0.geojson"
OUTPUT_PATH = r"C:\Users\mikasaloli\Documents\Codex\2026-09-05\ho\work\laos_dem_grid.json"
TILE_DIR = r"C:\Users\mikasaloli\Documents\Codex\2026-09-05\ho\work\dem_tiles"
ZOOM = 8
TARGET_WIDTH = 1200


def global_pixel(lon, lat, zoom):
    scale = 256 * (2**zoom)
    x = (lon + 180.0) / 360.0 * scale
    lat_rad = math.radians(max(-85.05112878, min(85.05112878, lat)))
    y = (1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * scale
    return x, y


def polygons(geometry):
    if geometry["type"] == "Polygon":
        return [geometry["coordinates"]]
    if geometry["type"] == "MultiPolygon":
        return geometry["coordinates"]
    raise ValueError(f"Unsupported geometry type: {geometry['type']}")


with open(GEOJSON_PATH, "r", encoding="utf-8") as handle:
    geo = json.load(handle)

features = geo["features"]
all_points = []
for feature in features:
    for polygon in polygons(feature["geometry"]):
        for ring in polygon:
            all_points.extend(ring)

min_lon = min(point[0] for point in all_points)
max_lon = max(point[0] for point in all_points)
min_lat = min(point[1] for point in all_points)
max_lat = max(point[1] for point in all_points)

px_left, px_top = global_pixel(min_lon, max_lat, ZOOM)
px_right, px_bottom = global_pixel(max_lon, min_lat, ZOOM)
tile_left = int(px_left // 256)
tile_right = int(px_right // 256)
tile_top = int(px_top // 256)
tile_bottom = int(px_bottom // 256)

os.makedirs(TILE_DIR, exist_ok=True)
stitched = Image.new("RGB", ((tile_right - tile_left + 1) * 256, (tile_bottom - tile_top + 1) * 256))

for ty in range(tile_top, tile_bottom + 1):
    for tx in range(tile_left, tile_right + 1):
        tile_path = os.path.join(TILE_DIR, f"{ZOOM}_{tx}_{ty}.png")
        if not os.path.exists(tile_path):
            url = f"https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{ZOOM}/{tx}/{ty}.png"
            request = urllib.request.Request(url, headers={"User-Agent": "Codex Laos terrain renderer"})
            with urllib.request.urlopen(request, timeout=60) as response:
                payload = response.read()
            with open(tile_path, "wb") as handle:
                handle.write(payload)
        tile = Image.open(tile_path).convert("RGB")
        stitched.paste(tile, ((tx - tile_left) * 256, (ty - tile_top) * 256))

origin_x = tile_left * 256
origin_y = tile_top * 256
crop_box = (
    int(math.floor(px_left - origin_x)),
    int(math.floor(px_top - origin_y)),
    int(math.ceil(px_right - origin_x)),
    int(math.ceil(px_bottom - origin_y)),
)

rgb = np.asarray(stitched, dtype=np.float32)
elevation = rgb[:, :, 0] * 256.0 + rgb[:, :, 1] + rgb[:, :, 2] / 256.0 - 32768.0
elevation_image = Image.fromarray(elevation, mode="F").crop(crop_box)

mask_full = Image.new("L", stitched.size, 0)
draw = ImageDraw.Draw(mask_full)
for feature in features:
    for polygon in polygons(feature["geometry"]):
        outer = []
        for lon, lat in polygon[0]:
            gx, gy = global_pixel(lon, lat, ZOOM)
            outer.append((gx - origin_x, gy - origin_y))
        draw.polygon(outer, fill=255)
        for hole in polygon[1:]:
            inner = []
            for lon, lat in hole:
                gx, gy = global_pixel(lon, lat, ZOOM)
                inner.append((gx - origin_x, gy - origin_y))
            draw.polygon(inner, fill=0)
mask_image = mask_full.crop(crop_box)

aspect = elevation_image.height / elevation_image.width
target_height = int(round(TARGET_WIDTH * aspect))
elevation_small = elevation_image.resize((TARGET_WIDTH, target_height), Image.Resampling.BICUBIC)
mask_small = mask_image.resize((TARGET_WIDTH, target_height), Image.Resampling.LANCZOS)

elev_array = np.asarray(elevation_small, dtype=np.float32)
mask_array = np.asarray(mask_small, dtype=np.uint8) >= 100
elev_array = np.where(mask_array, np.maximum(elev_array, 0.0), 0.0)

valid = elev_array[mask_array]
result = {
    "width": TARGET_WIDTH,
    "height": target_height,
    "elevation_m": np.round(elev_array, 1).tolist(),
    "mask": mask_array.astype(np.uint8).tolist(),
    "min_elevation_m": float(valid.min()),
    "max_elevation_m": float(valid.max()),
    "bbox": [min_lon, min_lat, max_lon, max_lat],
    "source": "Mapzen/Terrain Tiles Terrarium DEM; geoBoundaries LAO ADM0 mask",
}

with open(OUTPUT_PATH, "w", encoding="utf-8") as handle:
    json.dump(result, handle, separators=(",", ":"))

print(json.dumps({key: result[key] for key in ("width", "height", "min_elevation_m", "max_elevation_m", "bbox", "source")}, indent=2))
