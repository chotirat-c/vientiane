# Vientiane — Laos elevation relief

![Current preview](outputs/laos_relief_white_sunlight_preview.png)

An editable Blender relief map of Laos. The current design uses a deep blue elevation ramp, a pure white background, one warm morning sun for the cast shadows, and Phetsarath Regular for the Lao title.

## Open the project

1. Install [Blender 5.2](https://www.blender.org/download/).
2. Open `outputs/laos_relief_white_sunlight_8k.blend`.
3. Press **F12** to render, or use the preview above for a quick look.

The file is self-contained: the Phetsarath font is packed into the `.blend` file. The 8K render is configured at 6,284 × 7,680 pixels. The preview is `outputs/laos_relief_white_sunlight_preview.png`.

## Files

- `outputs/laos_relief_white_sunlight_8k.blend` — latest editable scene.
- `outputs/laos_relief_white_sunlight_preview.png` — latest preview.
- `outputs/laos_relief_rebuilt_8k.blend` and `.png` — original blue rebuilt edition.
- `outputs/laos_relief_green_paper_8k.blend` and `.png` — green paper variation.
- `work/terrain_v2` — build scripts and metadata.

## Rebuild or edit

The source scripts are in `work/terrain_v2`. `build_terrain.py` creates the relief mesh and original blue scene. `white_sunlight.py` applies the latest lighting, pure-white background, compositor, and Phetsarath typography, then renders a preview.

Large downloaded tiles and local Python runtimes are intentionally excluded from Git. Blender files and rendered images are stored with Git LFS.

## Data and limitations

Elevation comes from [Mapzen Terrain Tiles on AWS](https://registry.opendata.aws/terrain-tiles/), processed into a projected 150-metre grid. The outline comes from [geoBoundaries gbOpen LAO ADM0](https://www.geoboundaries.org/api/current/gbOpen/LAO/ADM0/). Heights are exaggerated 14× for visual readability. This is an artistic visualization, not a survey or authoritative border map. See [`outputs/laos_relief_README.md`](outputs/laos_relief_README.md) for full provenance and processing notes.
