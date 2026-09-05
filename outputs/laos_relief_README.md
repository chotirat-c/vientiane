# Laos elevation relief — rebuilt edition

Deliverables:

- `laos_relief_rebuilt_8k.png`: 6,284 × 7,680 pixels, 16-bit RGB PNG.
- `laos_relief_rebuilt_8k.blend`: editable Blender 5.2 scene with geometry, materials, lighting, camera and packed fonts.

The earlier renders are preserved under their original filenames.

## Design and rendering

Continuous white-to-blue colors encode elevation, not administrative regions. Elevation stops in metres: 0, 150, 350, 650, 1,000, 1,600, 2,200 and 3,000. The legend uses those same colors and numerical mapping. Lighting also changes apparent brightness.

The terrain has 10,216,769 vertices and 10,194,815 surface quads on a 150-metre projected grid, plus a separate vertical outline edge. Upward-facing surface normals, no subdivision, no Solidify modifier, and no invented noise. Heights are exaggerated 14× for legibility; horizontal coordinates use WGS 84 / UTM zone 48N (EPSG:32648). The view is near-overhead and orthographic.

Cycles HIP rendering: up to 1,024 samples, adaptive noise threshold 0.005, minimum 64 samples, OpenImageDenoise, 1,024-pixel render tiles. This is a native 8K-long-edge render, not an upscaled small image. 8K output resolution does not imply 8K independent measurements across the country.

## Data and limitations

Elevation: [Mapzen Terrain Tiles on AWS](https://registry.opendata.aws/terrain-tiles/), downloaded 5 September 2026. 832 zoom-11 Terrarium tiles; tile sample spacing is approximately 71–74 metres on the ground over Laos. These are sampling intervals, not a claim of survey accuracy or uniform effective source resolution. Elevations were decoded to metres before bilinear reprojection. [Terrarium format documentation](https://github.com/tilezen/joerd/blob/master/docs/formats.md).

Sparse obvious source artifacts included an 8,679-metre spike surrounded by terrain near 884 metres. A selective 5×5 median replacement corrected 817 samples across downloaded tiles where deviation from the local median exceeded 250 metres or values lay outside 0–3,100 metres. The general surface was not median-smoothed. The final in-country grid has no missing or negative samples and spans approximately 11.6–2,814.7 metres. These extrema describe this processed grid, not authoritative national elevation records.

Outline: [geoBoundaries gbOpen LAO ADM0](https://www.geoboundaries.org/api/current/gbOpen/LAO/ADM0/), using the previously downloaded boundary. Its recorded underlying source is OpenStreetMap/Wambacher, ODbL 1.0, boundary year 2017. The silhouette is a visualization boundary, not an authoritative statement about borders. Please retain source attribution when distributing the map and consult upstream data licenses for your intended use.

Intermediate DEM data, metadata and reproducible scripts remain in `work/terrain_v2` beside the output directory. A separately prepared 75-metre raster is retained there for future refinement; it is not applied as an extra texture in this delivered render.
