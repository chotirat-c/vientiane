# Laos relief — green paper edition

The green-paper edition retains the rebuilt, elevation-based Laos terrain and native 6,284 × 7,680 output. Blue renders remain unchanged.

- `laos_relief_green_paper_8k.png`: 16-bit RGB master.
- `laos_relief_green_paper_8k.blend`: editable Blender scene, with packed fonts and procedural paper material.
- `laos_relief_green_paper_preview.jpg`: smaller viewing copy, not the 8K master.

## Visual changes

Meadow and olive greens transition through golden slopes, warm terracotta highlands and pale summits. Color remains tied to elevation, not province or land cover. The legend uses the same color mapping as the terrain.

A separate warm-white cotton-paper sheet sits on a neutral tabletop. Its visible edge, fine procedural grain and subtle surface relief create a paper presentation. The map base is slightly raised, with longer, soft-edged northwest shadows. Terrain exaggeration remains 14×; no new landscape features were invented. Typography is forest-grey and treated as printed ink without letter cast shadows.

## Technical details and sources

The 150-metre projected grid, 10.2-million-vertex terrain, underlying elevation data and source-artifact corrections are unchanged from the blue rebuilt edition. See `laos_relief_README.md` for full data provenance and limitations. Rendering uses Cycles HIP, up to 1,024 adaptive samples, 0.005 noise threshold and OpenImageDenoise.

Elevation: [Mapzen Terrain Tiles](https://registry.opendata.aws/terrain-tiles/). Outline: [geoBoundaries gbOpen LAO ADM0](https://www.geoboundaries.org/api/current/gbOpen/LAO/ADM0/), with underlying OpenStreetMap/Wambacher attribution as recorded in the original notes. This is an artistic relief map, not a survey or authoritative border reference.
