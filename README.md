# Laos relief map in Blender

Create a Laos relief map from real boundary and elevation data, then build and render it in Blender.

![White sunlight preview](outputs/laos/white-sunlight/laos_relief_white_sunlight_preview.png)

1. [Geo boundary and elevation](#part-1--geo-boundary-and-elevation)
2. [Blender build and render](#part-2--blender-build-and-render)

## Output organization

Rendered assets are grouped first by region, then by visual version:

```text
outputs/
└── laos/
    ├── blue/
    ├── green-paper/
    ├── white-sunlight/
    └── sandy-gold-terraces/
```

Shared geographic inputs and build scripts remain under `work/` because all four versions use them.

For a quick review of an existing scene, do **1.1**, **2.1** and **2.2** only. Run all commands in the same Windows PowerShell session from the repository root. Stop when a check fails.

## Part 1 — Geo boundary and elevation

### 1.1 Set up the project

Requirements: Git, Git LFS and Python 3.12. The reference setup uses Blender 5.2.1.

For a new checkout:

```powershell
git clone https://github.com/chotirat-c/vientiane.git
if ($LASTEXITCODE -ne 0) { throw 'Clone failed.' }
Set-Location .\vientiane
```

For the existing workstation:

```powershell
Set-Location 'C:\Users\mikasaloli\Documents\Codex\2026-09-05\ho'
```

Download the large Blender and image files:

```powershell
$ErrorActionPreference = 'Stop'
$ProjectRoot = (Get-Location).Path
if (!(Test-Path .\work\terrain_v2\prepare_dem.py)) { throw 'Wrong repository directory.' }

git lfs version
if ($LASTEXITCODE -ne 0) { throw 'Git LFS is required.' }
git lfs install --local
if ($LASTEXITCODE -ne 0) { throw 'Git LFS setup failed.' }
git lfs pull
if ($LASTEXITCODE -ne 0) { throw 'Git LFS download failed.' }
git lfs fsck
if ($LASTEXITCODE -ne 0) { throw 'Git LFS verification failed.' }
```

Set up the Python dependencies used for geographic processing:

```powershell
$Python = 'C:\Users\mikasaloli\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
if (!(Test-Path $Python)) { throw 'Set $Python to a real Python 3.12 executable.' }
& $Python -c 'import sys; assert sys.version_info[:2] == (3, 12); print(sys.version)'
if ($LASTEXITCODE -ne 0) { throw 'Python 3.12 is required.' }

& $Python -m pip install --target .\work\terrain_v2\deps numpy pillow scipy shapely pyproj
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
& $Python -c 'import sys; sys.path.insert(0, "work/terrain_v2/deps"); import numpy, PIL, scipy, shapely, pyproj; print("GEO_IMPORTS_OK")'
if ($LASTEXITCODE -ne 0) { throw 'Geographic imports failed.' }
```

Continue only after `GEO_IMPORTS_OK`.

### 1.2 Check the Laos boundary

The included `work/laos_adm0.geojson` is the country outline. The preparation script reads this local file; it does not download or update the boundary.

```powershell
& $Python -c 'import json; from pathlib import Path; p=Path("work/laos_adm0.geojson"); d=json.loads(p.read_text(encoding="utf-8")); assert d["type"] == "FeatureCollection" and d["features"]; print("BOUNDARY_OK", p)'
if ($LASTEXITCODE -ne 0) { throw 'The boundary is missing or invalid.' }
```

Continue only after `BOUNDARY_OK`. Replacing this file is a geographic data revision.

### 1.3 Prepare the elevation model

```powershell
& $Python .\work\terrain_v2\prepare_dem.py
if ($LASTEXITCODE -ne 0) { throw 'DEM preparation failed. Do not start the Blender build.' }
```

The script has no command-line options. It downloads or reuses zoom-11 Terrarium tiles, decodes elevations to metres, repairs only extreme local artifacts, and resamples the data to a 150 m grid in EPSG:32648.

| Output under `work/terrain_v2/` | Purpose |
| --- | --- |
| `tiles_z11/` | Download cache |
| `source_zoom11.npy` | Decoded elevation mosaic |
| `dem_mesh.npz` | Elevation, country mask and projected coordinates for Blender |
| `dem_metadata.json` | Projection, bounds and processing statistics |
| `dem_detail_75m.png` | Optional finer raster; not used by the main build |

Wait for `DONE in ...s`; `MESH READY` is only an intermediate message.

### 1.4 Validate the Blender input

```powershell
$CheckDem = @'
import json, sys
from pathlib import Path
sys.path.insert(0, "work/terrain_v2/deps")
import numpy as np
r = Path("work/terrain_v2")
with np.load(r / "dem_mesh.npz") as d:
    z, mask, x, y = (d[k] for k in ("elevation_m", "mask", "x_m", "y_m"))
    assert mask.dtype == np.bool_ and mask.any()
    assert z.shape == mask.shape == (len(y), len(x))
    assert np.isfinite(z[mask]).all() and (z[mask] >= 0).all()
    assert np.allclose(np.diff(x), 150) and np.allclose(np.diff(y), -150)
    meta = json.loads((r / "dem_metadata.json").read_text())
    assert list(z.shape) == meta["shape_hw"] and int(mask.sum()) == meta["valid_vertices"]
    print("DEM_OK", z.shape, float(z[mask].min()), float(z[mask].max()))
assert (r / "dem_detail_75m.png").is_file()
'@
& $Python -c $CheckDem
if ($LASTEXITCODE -ne 0) { throw 'DEM validation failed.' }
```

Continue only after `DEM_OK`. Row 0 is north, columns run west to east, and heights remain in metres until Blender applies the display scale.

### Sources and limitations

- Boundary: [geoBoundaries gbOpen LAO ADM0](https://www.geoboundaries.org/api/current/gbOpen/LAO/ADM0/), from an OpenStreetMap/Wambacher source, boundary year 2017, ODbL 1.0.
- Elevation: [Mapzen Terrain Tiles on AWS](https://registry.opendata.aws/terrain-tiles/), Terrarium format, downloaded 5 September 2026.
- The recorded run used 832 tiles, corrected 817 extreme samples with a selective 5 × 5 median, and produced a 6,366 × 5,316 grid with in-country values of about 11.6–2,814.7 m. Treat these as comparison values, not required outputs.
- This is an artistic visualization, not a survey, navigation product or authoritative border statement. Retain attribution and check upstream licenses before redistribution.

### Adapting Part 1 to another country

The current scripts are Laos-specific; there is no working `--country` option. For a new country:

1. Request ADM0 metadata from `https://www.geoboundaries.org/api/current/gbOpen/{ISO3}/ADM0/`, then download the URL in `gjDownloadURL`.
2. Save the metadata, resolved download URL, checksum, source license and acquisition date in a separate country directory.
3. Inspect coordinate order, bounds, islands, holes and geometry validity.
4. Choose an appropriate metre-based CRS; do not reuse Laos's UTM zone automatically or build geometry directly from longitude/latitude degrees.
5. Adapt tile coverage, grid spacing, nodata rules and elevation checks. Laos's 0–3,100 m artifact limits are invalid for many countries.
6. Use separate cache, intermediate and output names so the Laos files cannot be overwritten.

## Part 2 — Blender build and render

### 2.1 Locate Blender

```powershell
$Blender = 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe'
if (!(Test-Path $Blender)) { throw 'Set $Blender to the Blender 5.2 executable.' }
& $Blender --version
if ($LASTEXITCODE -ne 0) { throw 'Blender could not start.' }
```

The compositor scripts use Blender 5.2 APIs. Verify compatibility before using another version.

### 2.2 Preview an existing scene

This makes a separate 1,676 × 2,048 CPU preview without saving changes to the scene.

```powershell
$Scene = Join-Path $ProjectRoot 'outputs/laos/white-sunlight/laos_relief_white_sunlight_8k.blend'
if (!(Test-Path $Scene)) { throw 'Selected scene is missing.' }
if ((Get-Item $Scene).Length -lt 1MB) { throw 'Scene is unexpectedly small; check Git LFS.' }

$PreviewCode = @'
import bpy
from pathlib import Path
s = bpy.context.scene
s.render.engine = "CYCLES"
s.cycles.device = "CPU"
s.cycles.samples = 64
s.cycles.adaptive_min_samples = 16
s.render.resolution_x, s.render.resolution_y = 1676, 2048
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

After `REVIEW_PREVIEW_COMPLETE`, inspect the silhouette, relief, labels, colors and shadows in the new `_review_preview.png`. Change `$Scene` to preview another `.blend`. Do not press F12 on an unchanged `_8k.blend` for a quick review; it retains its large render settings.

### 2.3 Build and approve a proof

The builder selects Cycles HIP and needs a compatible AMD GPU:

```powershell
& $Blender --background --factory-startup --disable-autoexec --python-exit-code 1 --python-expr 'import bpy; p=bpy.context.preferences.addons["cycles"].preferences; p.compute_device_type="HIP"; p.refresh_devices(); assert any(d.type == "HIP" for d in p.devices), "No HIP GPU available"; print("HIP_OK")'
if ($LASTEXITCODE -ne 0) { throw 'No HIP GPU. Use step 2.2 or explicitly adapt and test the builder.' }
```

Check the required fonts, then build the blue proof:

```powershell
foreach ($Font in @('C:\Windows\Fonts\segoeui.ttf', 'C:\Windows\Fonts\LeelawUI.ttf')) {
    if (!(Test-Path $Font)) { throw "Required font missing: $Font" }
}
& $Blender --background --factory-startup --disable-autoexec --python-exit-code 1 --python .\work\terrain_v2\build_terrain.py -- --stage proof --style blue
if ($LASTEXITCODE -ne 0) { throw 'Proof render failed.' }
```

Inspect `outputs/laos/blue/proof.png` at 1,676 × 2,048. For the green-paper edition, use `--style green-paper` and inspect `outputs/laos/green-paper/proof.png`. A proof does not save a `.blend` file.

### 2.4 Render and verify the final

Only continue after approving the proof. This command overwrites the fixed blue output names, saves the scene, and immediately renders a 6,284 × 7,680 image. There is no save-only option.

```powershell
& $Blender --background --factory-startup --disable-autoexec --python-exit-code 1 --python .\work\terrain_v2\build_terrain.py -- --stage final --style blue
if ($LASTEXITCODE -ne 0) { throw 'Final build or render failed.' }

& $Python .\work\terrain_v2\inspect_render.py --style blue
if ($LASTEXITCODE -ne 0) { throw 'Final image verification failed.' }
```

For green paper, change both commands to `--style green-paper`. The QA script checks the PNG and creates separate viewing copies in the selected version folder without changing the master.

Confirm the actual files, dimensions and bit depth, then visually inspect the full composition and 1:1 crops. Report clearly whether you produced a preview or a completed final render. An `_8k.blend` filename alone is not proof of an 8K render.

| Blue deliverable | Description |
| --- | --- |
| `outputs/laos/blue/laos_relief_rebuilt_8k.png` | 6,284 × 7,680, 16-bit RGB PNG |
| `outputs/laos/blue/laos_relief_rebuilt_8k.blend` | Editable Blender 5.2 scene with packed fonts |

The final terrain uses a 150 m projected grid, about 10.2 million vertices, upward normals, 14× vertical exaggeration and no invented surface noise. Cycles HIP uses adaptive sampling up to 1,024 samples and OpenImageDenoise. The color ramp represents elevation, not provinces or vegetation.

### Optional style variants

- White sunlight: run `bright_morning.py` on `outputs/laos/blue/laos_relief_rebuilt_8k.blend`, then run `white_sunlight.py` on the generated `outputs/laos/white-sunlight/laos_relief_bright_morning_8k.blend`. Both scripts save scenes and render previews in `outputs/laos/white-sunlight/`. They require the Phetsarath font at the hardcoded local path.
- Sandy-gold terraces: the contour scripts, generated scenes and tutorial `.blend` are local and currently untracked. A fresh clone cannot reproduce this route without those inputs; do not guess missing paths or download URLs.
- Another country: update the height range, palette, legend, camera, labels, fonts, QA crops and filenames together. Build a simple geographic proof before developing the final art direction.
