"""Turn Thailand contour data into the sandy-gold terrace Blender edition."""
from __future__ import annotations

import json
from pathlib import Path
import sys

import bpy
from mathutils import Vector
import numpy as np

ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parents[1]
OUT = PROJECT_ROOT / "outputs" / "thailand" / "sandy-gold-terraces"
OUT.mkdir(parents=True, exist_ok=True)

metadata = json.loads((ROOT / "contour_layers_minimal.json").read_text(encoding="utf-8"))
data = np.load(ROOT / "contour_layers_minimal.npz")
scene = bpy.context.scene


def remove_object(obj) -> None:
    data_block = obj.data
    bpy.data.objects.remove(obj, do_unlink=True)
    if data_block and data_block.users == 0:
        if isinstance(data_block, bpy.types.Mesh):
            bpy.data.meshes.remove(data_block)
        elif isinstance(data_block, bpy.types.Curve):
            bpy.data.curves.remove(data_block)


for obj in list(scene.objects):
    if "contour_elevation_m" in obj:
        remove_object(obj)
for collection in list(bpy.data.collections):
    if collection.name.startswith("LAOS |"):
        bpy.data.collections.remove(collection)

materials = {
    "base": bpy.data.materials["Deep lagoon coloured base"],
    "cyan": bpy.data.materials["Turquoise contour foundation"],
    "resin": bpy.data.materials["Turquoise resin | decorative lowland layer"],
    "pearl": bpy.data.materials["Tutorial pearl contour layers"],
    "gold": bpy.data.materials["Highest terrace | muted sandy gold"],
}
collection = bpy.data.collections.new("THAILAND | stacked contour sculpture")
scene.collection.children.link(collection)
top_level = metadata["layers"][-1]["level_m"]
previous_level = 0
for info in metadata["layers"]:
    level = info["level_m"]
    xy = data[f"xy_{level}"]
    triangles = data[f"tri_{level}"]
    edges = data[f"edge_{level}"]
    count = len(xy)
    upper = 0.095 + level * 0.0004
    lower = 0.006 if level == 0 else 0.095 + previous_level * 0.0004 - 0.001
    previous_level = level
    vertices = np.empty((count * 2, 3), np.float32)
    vertices[:count, :2] = xy
    vertices[count:, :2] = xy
    vertices[:count, 2] = upper
    vertices[count:, 2] = lower
    walls = np.column_stack(
        [edges[:, 0], edges[:, 0] + count, edges[:, 1] + count, edges[:, 1]]
    )
    faces = (
        [tuple(value) for value in triangles]
        + [tuple(value[::-1] + count) for value in triangles]
        + [tuple(value) for value in walls]
    )
    mesh = bpy.data.meshes.new(f"Thailand contour slab {level:04d} m")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(mesh.name, mesh)
    collection.objects.link(obj)
    material = (
        materials["base"]
        if level == 0
        else materials["cyan"]
        if level == 100
        else materials["resin"]
        if level == 200
        else materials["gold"]
        if level == top_level
        else materials["pearl"]
    )
    mesh.materials.append(material)
    bevel = obj.modifiers.new("Soft cut edge", "BEVEL")
    bevel.width = 0.004
    bevel.segments = 3
    bevel.limit_method = "ANGLE"
    obj["contour_elevation_m"] = level
    obj["style"] = "Generalized Thailand DEM, 18 km smoothing; 40x vertical scale"
    print("BUILT_THAILAND_LAYER", level, len(vertices), flush=True)

pin = bpy.data.objects.get("Vientiane | tutorial red location pin")
if pin is None:
    raise RuntimeError("Reference pin is missing from the source scene")
pin.name = "Bangkok | red location pin"
pin.location = (*metadata["pin_xy"], 0.2)
pin["Location"] = "Bangkok, approximately 13.7563 N, 100.5018 E"
point = np.asarray(metadata["pin_xy"])
surface = 0.095
for info in metadata["layers"]:
    level = info["level_m"]
    triangle_coordinates = data[f"xy_{level}"][data[f"tri_{level}"]]
    signs = []
    for index in range(3):
        a = triangle_coordinates[:, index]
        b = triangle_coordinates[:, (index + 1) % 3]
        signs.append(
            (b[:, 0] - a[:, 0]) * (point[1] - a[:, 1])
            - (b[:, 1] - a[:, 1]) * (point[0] - a[:, 0])
        )
    if np.any(np.all(np.stack(signs) >= -1e-9, axis=0)):
        surface = 0.095 + level * 0.0004
bpy.context.view_layer.update()
pin_box = [pin.matrix_world @ Vector(value) for value in pin.bound_box]
pin.location.z += surface + 0.018 - min(value.z for value in pin_box)
print("BANGKOK_PIN_SURFACE", surface, flush=True)

english_title = bpy.data.objects["Country title"]
english_title.data.body = "KINGDOM OF THAILAND"
english_title.data.size = 0.255
thai_title = bpy.data.objects["Lao country title"]
thai_title.name = "Thai country title"
thai_title.data.name = "Thai country title"
thai_title.data.body = "ราชอาณาจักรไทย"
thai_title.data.font = bpy.data.fonts.load("C:/Windows/Fonts/LeelawUI.ttf")
thai_title.data.size = 0.225
bpy.data.objects["Contour style note"].data.body = (
    "GENERALIZED RELIEF / TURQUOISE RESIN BASE / PIN: BANGKOK"
)
bpy.data.objects["Highest terrace legend"].data.body = f"{top_level:,} m"
middle_levels = [item["level_m"] for item in metadata["layers"] if 400 <= item["level_m"] < top_level]
bpy.data.objects["Layer legend 400 m +"].data.body = f"400–{max(middle_levels):,} m"
for obj in scene.objects:
    if obj.type == "FONT":
        obj.visible_shadow = False

camera = scene.camera
camera.location = (0, -7, 22)
camera.rotation_euler = (
    Vector((0, -0.25, 0.1)) - camera.location
).to_track_quat("-Z", "Y").to_euler()
camera.data.ortho_scale = 12.35
scene.render.resolution_x = 1676
scene.render.resolution_y = 2048
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_depth = "8"
scene.render.film_transparent = False

scene["Design"] = (
    "Thailand stacked contour sculpture. Pearl terraces, turquoise decorative "
    "foundation, sandy-gold summit tier, and red Bangkok pin."
)
scene["Terrain generalization"] = json.dumps(
    {key: value for key, value in metadata.items() if key not in ["layers", "pin_xy", "boundary_metadata"]}
)
scene["Resin note"] = (
    "Turquoise foundation is a decorative material treatment, not a depiction "
    "of water or flooding."
)
scene["Boundary note"] = (
    "Artistic visualization using geoBoundaries gbOpen THA ADM0; not an "
    "authoritative border statement."
)

preferences = bpy.context.preferences.addons["cycles"].preferences
preferences.compute_device_type = "HIP"
preferences.refresh_devices()
for device in preferences.devices:
    device.use = device.type == "HIP"
scene.cycles.device = "GPU"
scene.cycles.samples = 96
scene.cycles.adaptive_min_samples = 16
scene.cycles.adaptive_threshold = 0.02
preview_path = OUT / "thailand_relief_contour_sandy_gold_preview.png"
blend_path = OUT / "thailand_relief_contour_sandy_gold_8k.blend"
scene.render.filepath = str(preview_path)
bpy.ops.file.pack_all()
bpy.ops.render.render(write_still=True)
# Leave the editable deliverable configured for the project's final portrait
# dimensions; the checked PNG above remains the deliberately quicker proof.
scene.render.resolution_x = 6284
scene.render.resolution_y = 7680
scene.render.image_settings.color_depth = "16"
scene.cycles.samples = 512
scene.cycles.adaptive_min_samples = 32
scene.cycles.adaptive_threshold = 0.01
scene.render.filepath = str(OUT / "thailand_relief_contour_sandy_gold_8k.png")
bpy.ops.wm.save_as_mainfile(filepath=str(blend_path), compress=True)
print("THAILAND_SANDY_GOLD_PREVIEW_COMPLETE", preview_path, flush=True)
