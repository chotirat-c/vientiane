# Vientiane — Laos relief in Blender

Build a Laos elevation map from geographic data, then style and preview it in Blender.

![Published blue relief preview](outputs/laos_relief_white_sunlight_preview.png)

**Two parts:** [1. Gather and prepare geography](#part-1--gather-and-prepare-geography) → [2. Build and render in Blender](#part-2--build-and-render-in-blender).

**Only want a preview?** Complete **1.1**, then **2.1–2.2**. Existing scenes do not require downloading elevation data again.

**Rules for an AI following this guide:** use PowerShell from the repository root, keeping the same session between steps. Run one step at a time; check its result before continuing. Stop on errors or missing inputs and report the exact problem. Do not invent paths, inputs, URLs, script flags, fonts, or terrain. Render a preview first. An `_8k.blend` filename identifies a scene configured for a large render; it does not prove that an 8K image exists.

| Edition | Availability | Scene under `outputs/` |
| --- | --- | --- |
| Original blue relief | Git LFS | `laos_relief_rebuilt_8k.blend` |
| White background and warm sun | Git LFS; pictured above | `laos_relief_white_sunlight_8k.blend` |
| Simplified terraces and sandy-gold summit | Local working files; currently untracked | `laos_relief_contour_sandy_gold_8k.blend` |

The published preview above is the blue edition. A fresh clone currently lacks the later contour scripts and sandy-gold scenes. Step 2.5 documents that local workflow and its missing external inputs explicitly.

## Part 1 — Gather and prepare geography

### 1.1 Get the project and large files

Requirements: Windows PowerShell, Git and Git LFS. The reference workstation uses Python 3.12 and Blender 5.2.1. Scene-building scripts explicitly select Cycles HIP and require a compatible AMD GPU. Step 2.2 offers a CPU preview of an existing scene.

For a **new checkout**, run:

```powershell
git clone https://github.com/chotirat-c/vientiane.git
if ($LASTEXITCODE -ne 0) { throw 'Clone failed.' }
Set-Location .\vientiane
```

For the **existing workstation checkout**, use this instead:

```powershell
Set-Location 'C:\Users\mikasaloli\Documents\Codex\2026-09-05\ho'
```

Then, for either checkout:

```powershell
$ErrorActionPreference = 'Stop'
$ProjectRoot = (Get-Location).Path
if (!(Test-Path .\work\terrain_v2\prepare_dem.py)) { throw 'Wrong repository directory.' }
git lfs version
if ($LASTEXITCODE -ne 0) { throw 'Git LFS is required.' }
git lfs install --local
if ($LASTEXITCODE -ne 0) { throw 'Git LFS setup failed.' }
git lfs pull
if ($LASTEXITCODE -ne 0) { throw 'LFS download failed; resolve access or quota before continuing.' }
git lfs fsck
if ($LASTEXITCODE -ne 0) { throw 'LFS verification failed.' }
```

**Check:** Blender files must be downloaded assets, not small text pointers beginning `version https://git-lfs.github.com/spec/v1`. Blender files and rendered images use LFS. Downloaded tile caches and generated DEM arrays are excluded from Git.

### 1.2 Prepare ordinary Python

This Python environment prepares geographic data. Blender runs the rendering scripts with its own bundled Python.

The executable below is the existing workstation runtime. If absent, locate an actual Python 3.12 installation and change `$Python` to its verified path before continuing.

```powershell
$Python = 'C:\Users\mikasaloli\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
if (!(Test-Path $Python)) { throw 'Locate a real Python 3.12 executable and set $Python.' }
& $Python -c 'import sys; print(sys.version); assert sys.version_info[:2] == (3, 12)'
if ($LASTEXITCODE -ne 0) { throw 'Python version check failed.' }
& $Python -m pip install --target .\work\terrain_v2\deps numpy pillow scipy shapely pyproj
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
& $Python -c 'import sys; sys.path.insert(0, "work/terrain_v2/deps"); import numpy, PIL, scipy, shapely, pyproj; print("GEO_IMPORTS_OK")'
if ($LASTEXITCODE -ne 0) { throw 'Geographic imports failed.' }
```

**Check:** `GEO_IMPORTS_OK`. There is no dependency lockfile in the repository; this setup checks imports but does not guarantee identical results with future package releases.

### 1.3 Verify the boundary input

```powershell
& $Python -c 'import json; from pathlib import Path; p=Path("work/laos_adm0.geojson"); d=json.loads(p.read_text(encoding="utf-8")); assert d["type"] == "FeatureCollection" and d["features"]; print("BOUNDARY_OK", p)'
if ($LASTEXITCODE -ne 0) { throw 'Restore the missing or invalid repository boundary before continuing.' }
```

| Input | Source | Script behavior |
| --- | --- | --- |
| Country outline | Tracked `work/laos_adm0.geojson`, previously obtained from [geoBoundaries LAO ADM0](https://www.geoboundaries.org/api/current/gbOpen/LAO/ADM0/) | Reads the included file; does **not** download or update it. |
| Elevation | [Mapzen Terrain Tiles on AWS](https://registry.opendata.aws/terrain-tiles/) | Downloads intersecting zoom-11 Terrarium tiles from `https://elevation-tiles-prod.s3.amazonaws.com/terrarium/{z}/{x}/{y}.png`. |

**Check:** `BOUNDARY_OK`. Use the included boundary for this workflow. The live geoBoundaries endpoint can change; replacing the outline is a data revision, not an automatic missing-file workaround.

### 1.4 Download and prepare elevation

```powershell
& $Python .\work\terrain_v2\prepare_dem.py
if ($LASTEXITCODE -ne 0) { throw 'DEM preparation failed. Do not start Blender.' }
```

This script has **no command-line options**. It reuses valid cached tiles and:

1. Decodes Terrarium RGB to metres: `R*256 + G + B/256 - 32768`.
2. Selectively replaces extreme source artifacts using a 5 × 5 median; it does not smooth the entire surface.
3. Bilinearly resamples onto a **150 m grid in EPSG:32648**, WGS 84 / UTM zone 48N.
4. Writes the mesh data, metadata and an additional 75 m height raster.

| Output under `work/terrain_v2/` | Purpose |
| --- | --- |
| `tiles_z11/` | Downloaded tile cache |
| `source_zoom11.npy` | Decoded source mosaic |
| `dem_mesh.npz` | Blender input: `elevation_m`, `mask`, `x_m`, `y_m` |
| `dem_metadata.json` | Projection, dimensions, bounds and processing statistics |
| `dem_detail_75m.png` | Extra 16-bit height raster; **not used** by the primary Blender build |

**Check:** wait for `DONE in ...s` and exit code 0. `MESH READY` is only an intermediate message.

The historical run downloaded 832 tiles and produced a 6,366 × 5,316 grid. These are reference values, not outputs to fabricate if a rerun differs. Processing creates large arrays and needs substantial free RAM and disk space. The metadata's `accessed` date is currently hardcoded to `2026-09-05`; record the actual date separately on reruns.

### 1.5 Validate the handoff to Blender

```powershell
$CheckDem = @'
import json, sys
from pathlib import Path
sys.path.insert(0, "work/terrain_v2/deps")
import numpy as np
r = Path("work/terrain_v2")
with np.load(r / "dem_mesh.npz") as d:
    assert {"elevation_m", "mask", "x_m", "y_m"} <= set(d.files)
    z, mask, x, y = (d[k] for k in ("elevation_m", "mask", "x_m", "y_m"))
    assert mask.dtype == np.bool_ and mask.any()
    assert z.shape == mask.shape == (len(y), len(x))
    assert np.allclose(np.diff(x), 150) and np.allclose(np.diff(y), -150)
    valid = z[mask]
    assert np.isfinite(valid).all() and (valid >= 0).all()
    meta = json.loads((r / "dem_metadata.json").read_text())
    assert list(z.shape) == meta["shape_hw"]
    assert int(mask.sum()) == meta["valid_vertices"]
    print("DEM_OK", z.shape, "in-country metres:", float(valid.min()), float(valid.max()))
assert (r / "dem_detail_75m.png").is_file(), "Preparation did not finish"
'@
& $Python -c $CheckDem
if ($LASTEXITCODE -ne 0) { throw 'DEM validation failed. Stop here.' }
```

**Check:** `DEM_OK`. Row 0 is north; columns run west to east. Heights remain in metres here; Blender applies the display scale and exaggeration.

## Part 2 — Build and render in Blender

### 2.1 Locate Blender and choose a route

```powershell
$Blender = 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe'
if (!(Test-Path $Blender)) { throw 'Locate Blender 5.2 before continuing.' }
& $Blender --version
if ($LASTEXITCODE -ne 0) { throw 'Blender could not start.' }
```

The reference installation is **5.2.1**. The compositor scripts use version-specific APIs. Check compatibility before using another version; do not guess replacement nodes or properties.

| Goal | Steps |
| --- | --- |
| Preview an existing scene | 2.2; no DEM preparation needed |
| Rebuild original blue terrain from data | 1.2–1.5, then 2.3 |
| Recreate white background and warm sunlight | 2.4, starting with the original blue scene |
| Recreate local sandy-gold artwork | 1.2–1.5, then 2.5; external local inputs required |

### 2.2 Render an existing scene as a preview

This renders **1,676 × 2,048**, 64 samples, on CPU. It retains materials and lighting, writes a separate image and does **not** save changes to the scene. CPU rendering can be slow because the mesh remains large.

```powershell
$Scene = Join-Path $ProjectRoot 'outputs/laos_relief_white_sunlight_8k.blend'
if (!(Test-Path $Scene)) { throw 'Selected scene is missing.' }
if ((Get-Item $Scene).Length -lt 1MB) { throw 'Scene unexpectedly small; check Git LFS.' }
$PreviewCode = @'
import bpy
from pathlib import Path
s = bpy.context.scene
s.render.engine = "CYCLES"
s.cycles.device = "CPU"
s.cycles.samples = 64
s.cycles.adaptive_min_samples = 16
s.render.resolution_x = 1676
s.render.resolution_y = 2048
s.render.resolution_percentage = 100
s.render.image_settings.file_format = "PNG"
s.render.image_settings.color_depth = "8"
p = Path(bpy.data.filepath)
s.render.filepath = str(p.with_name(p.stem + "_review_preview.png"))
bpy.ops.render.render(write_still=True)
print("REVIEW_PREVIEW_COMPLETE", s.render.filepath, flush=True)
'@
& $Blender --background --disable-autoexec $Scene --python-exit-code 1 --python-expr $PreviewCode
if ($LASTEXITCODE -ne 0) { throw 'Preview failed.' }
```

**Check:** `REVIEW_PREVIEW_COMPLETE`, then open `outputs/laos_relief_white_sunlight_8k_review_preview.png`. Inspect silhouette, terrain, Lao glyphs, colors and shadows. A successful process exit is not visual approval.

For sandy gold, change `$Scene` to the existing `outputs/laos_relief_contour_sandy_gold_8k.blend` before running the block. Its output ends in `laos_relief_contour_sandy_gold_8k_review_preview.png`. Stop if that local scene is absent.

**Do not press F12 on an unmodified saved scene for a quick preview:** it retains its large render settings.

### 2.3 Rebuild the original blue terrain

Before any scripted build or style step, run this HIP check:

```powershell
& $Blender --background --factory-startup --disable-autoexec --python-exit-code 1 --python-expr 'import bpy; p=bpy.context.preferences.addons["cycles"].preferences; p.compute_device_type="HIP"; p.refresh_devices(); assert any(d.type == "HIP" for d in p.devices), "No HIP GPU available"; print("HIP_OK")'
if ($LASTEXITCODE -ne 0) { throw 'Build scripts require HIP. Use 2.2 for a CPU scene preview, or explicitly adapt and verify the scripts.' }
```

After completing Part 1, check the required fonts and build a proof:

```powershell
foreach ($Font in @('C:\Windows\Fonts\segoeui.ttf', 'C:\Windows\Fonts\LeelawUI.ttf')) {
    if (!(Test-Path $Font)) { throw "Required build font missing: $Font" }
}
& $Blender --background --factory-startup --disable-autoexec --python-exit-code 1 --python .\work\terrain_v2\build_terrain.py -- --stage proof --style blue
if ($LASTEXITCODE -ne 0) { throw 'Terrain proof failed.' }
```

**Check:** `work/terrain_v2/proof.png`, 1,676 × 2,048. The proof uses every second DEM sample: **300 m spacing**, with 14× vertical exaggeration. It renders an image but **does not save a Blender file**.

Supported script options are only `--stage proof|final` and `--style blue|green-paper`, after Blender's `--` separator. `green_paper.py` is an imported style helper, not a standalone builder.

**Full-render boundary:** `--stage final` uses the 150 m grid, saves `outputs/laos_relief_rebuilt_8k.blend`, then immediately renders `outputs/laos_relief_rebuilt_8k.png` at 6,284 × 7,680 with up to 1,024 samples. It overwrites those outputs. There is **no save-only flag**. Use it only when a full render and replacement of those files are explicitly requested. For preview-only styling, use the original scene supplied through LFS.

### 2.4 Recreate white background and warm sun

Run step 2.3's HIP check first. These scripts depend on exact object names and must run in this order:

`rebuilt_8k.blend` → `bright_morning.py` → `bright_morning_8k.blend` → `white_sunlight.py` → `white_sunlight_8k.blend` (all scene filenames have the `laos_relief_` prefix).

Each script saves its named scene and renders a preview, overwriting previous outputs. Preserve manual edits to those outputs before rebuilding.

```powershell
$Phetsarath = 'C:\Users\mikasaloli\AppData\Local\Microsoft\Windows\Fonts\Phetsarath-Regular.ttf'
if (!(Test-Path $Phetsarath)) { throw 'Phetsarath missing; the style script hardcodes this font path.' }
if (!(Test-Path .\outputs\laos_relief_rebuilt_8k.blend)) { throw 'Original blue scene missing; complete the LFS download.' }
& $Blender --background --disable-autoexec .\outputs\laos_relief_rebuilt_8k.blend --python-exit-code 1 --python .\work\terrain_v2\bright_morning.py
if ($LASTEXITCODE -ne 0) { throw 'Morning style failed. Stop here.' }
& $Blender --background --disable-autoexec .\outputs\laos_relief_bright_morning_8k.blend --python-exit-code 1 --python .\work\terrain_v2\white_sunlight.py
if ($LASTEXITCODE -ne 0) { throw 'White sunlight style failed.' }
```

**Check:** `MORNING_PROOF_COMPLETE`, then `WHITE_SUNLIGHT_PREVIEW_COMPLETE`. Inspect `outputs/laos_relief_white_sunlight_preview.png` at 1,676 × 2,048. The `BACKGROUND_RGB` log samples should show `[255, 255, 255]` at the sampled empty background positions.

Do not run `white_sunlight.py` directly on the original scene: it needs the `Morning daylight | backdrop only` object created by the first script. The final style disables the softbox and backdrop lamp, uses one warm Sun lamp plus faint world ambience, and composites shadows over white.

Phetsarath is loaded and packed. On another machine, change the hardcoded path in `white_sunlight.py` only after locating the real font. Changing the PowerShell variable alone does not change the script.

Both scripts save the large-resolution scene **before** lowering settings for a preview. Neither produces its named 8K PNG during this workflow.

### 2.5 Recreate the local sandy-gold terraces

**Local-only route:** contour scripts and scenes are currently untracked. A fresh clone cannot run this route without those files. The external tutorial scene supplies materials, world and marker assets; Laos geography still comes from Part 1. Its download URL is not recorded here; do not guess one.

Complete Part 1 and step 2.3's HIP check, then verify the local inputs:

```powershell
$Required = @(
    '.\work\terrain_v2\prepare_contour_layers.py',
    '.\work\terrain_v2\build_contour_edition.py',
    '.\work\terrain_v2\color_summit.py',
    '.\work\terrain_v2\sandy_gold_summit.py',
    '.\outputs\laos_relief_rebuilt_8k.blend',
    'C:\Users\mikasaloli\Downloads\TOPOtutorial_End.blend',
    'C:\Users\mikasaloli\AppData\Local\Microsoft\Windows\Fonts\Phetsarath-Regular.ttf'
)
foreach ($InputFile in $Required) {
    if (!(Test-Path $InputFile)) { throw "Missing local input: $InputFile" }
}
& $Python -m pip install --target .\work\terrain_v2\deps contourpy
if ($LASTEXITCODE -ne 0) { throw 'Contour dependency installation failed.' }
& $Python -c 'import sys; sys.path.insert(0, "work/terrain_v2/deps"); import contourpy, shapely; assert hasattr(shapely, "constrained_delaunay_triangles"), "Shapely constrained triangulation support required"; print("CONTOUR_IMPORTS_OK")'
if ($LASTEXITCODE -ne 0) { throw 'Contour dependency check failed.' }
& $Python .\work\terrain_v2\prepare_contour_layers.py --minimal
if ($LASTEXITCODE -ne 0) { throw 'Contour preparation failed.' }
```

**Check:** `work/terrain_v2/contour_layers_minimal.npz` and `.json`. The reference result has seven retained tiers at 0, 100, 200, 400, 600, 800 and 1,000 m, 14 islands and no holes. The minimal treatment applies 18 km Gaussian smoothing, removes small islands, fills holes and simplifies outlines. These are generalized sculptural terraces, not precise elevation contours.

Run all three Blender steps in order; each saves its scene and renders a 1,676 × 2,048 preview, replacing existing outputs with those names:

```powershell
& $Blender --background --disable-autoexec .\outputs\laos_relief_rebuilt_8k.blend --python-exit-code 1 --python .\work\terrain_v2\build_contour_edition.py -- --minimal
if ($LASTEXITCODE -ne 0) { throw 'Minimal contour build failed.' }
& $Blender --background --disable-autoexec .\outputs\laos_relief_contour_minimal_8k.blend --python-exit-code 1 --python .\work\terrain_v2\color_summit.py
if ($LASTEXITCODE -ne 0) { throw 'Summit material creation failed.' }
& $Blender --background --disable-autoexec .\outputs\laos_relief_contour_blue_summit_8k.blend --python-exit-code 1 --python .\work\terrain_v2\sandy_gold_summit.py
if ($LASTEXITCODE -ne 0) { throw 'Sandy-gold recoloring failed.' }
```

**Check:** `SANDY_GOLD_PREVIEW_COMPLETE`, `outputs/laos_relief_contour_sandy_gold_8k.blend` and `outputs/laos_relief_contour_sandy_gold_preview.png`. Inspect the preview before further changes.

Do not skip `color_summit.py`: it creates the material that `sandy_gold_summit.py` recolors to **#c9b383**. This edition uses 40× vertical exaggeration and the imported Sky world, a different lighting setup from the blue edition. Tutorial and font paths are hardcoded in `build_contour_edition.py`; any replacement path must point to the actual required file.

### 2.6 Report the verified result

State the route used, exact saved scene and image paths, image dimensions, whether rendering completed, and what you visually checked. If only a preview was rendered, say so. Do not claim an 8K render, GitHub upload or complete rebuild based only on filenames or old files.

For source attribution and historical processing details of the original blue edition, see [the rebuilt-edition notes](outputs/laos_relief_README.md). The recorded boundary source is OpenStreetMap/Wambacher via geoBoundaries, boundary year 2017, ODbL 1.0. Retain attribution and consult upstream licenses when redistributing. This is artwork, not a survey or authoritative border map; processed summit values are not national elevation records.
