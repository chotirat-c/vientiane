# Morning Jade

Laos and Thailand relief with fresh green elevation colors, warm sunlight, and soft
blue-gray shadows. The atmosphere and Filmic color management come directly
from the original Thailand Sandy Gold scene. Each title sits in its country's
open space: southwest for Laos and beside the peninsula for Thailand.

Render from the repository root in PowerShell:

```powershell
& 'C:/Program Files/Blender Foundation/Blender 5.2/blender.exe' --background --factory-startup --disable-autoexec --python-exit-code 1 --python work/terrain_v2/build_morning_jade.py -- --country laos --stage final
```

Use `--country thailand` for Thailand and `--stage proof` for a 1,676 x 2,048
preview using a 300 m mesh. The final uses the full 150 m terrain grid
(10,216,769 vertices for Laos; 22,917,317 for Thailand), 14x vertical exaggeration,
and a 6,284 x 7,680, 16-bit RGB PNG with up to 512 adaptive Cycles samples.
Both stages save an editable Blender scene with packed fonts.

Outputs are under `outputs/<country>/morning-jade/` with the stem
`<country>_relief_morning_jade_8k` for the final and
`<country>_relief_morning_jade_preview` for the preview.

The source data is Mapzen Terrarium elevation and geoBoundaries gbOpen LAO/THA
ADM0. The color ramp represents elevation, not measured vegetation cover.
Source provenance remains in `work/terrain_v2/dem_metadata.json`,
`thailand_blue_dem_150m.json`, and `boundary_metadata.json`.

Prepare the local DEMs with `work/terrain_v2/prepare_dem.py` for Laos and
`work/thailand_terrain/prepare_thailand_blue_150m.py` for Thailand, using the
Python dependencies documented in the repository README. DEMs and downloaded
tile caches are local build inputs; packed scenes and final renders use Git LFS.
The required lighting reference scene is tracked under
`outputs/thailand/sandy-gold-terraces/`.

Validate either master with:

```powershell
& 'C:/Users/mikasaloli/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' work/thailand_terrain/inspect_sandy_gold_final.py --master outputs/laos/morning-jade/laos_relief_morning_jade_8k.png
```
