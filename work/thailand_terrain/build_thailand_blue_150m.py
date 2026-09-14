"""Render detailed Thailand relief and the shared Laos/Thailand Morning Jade edition."""
from __future__ import annotations

import json
import gc
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

ROOT = Path(__file__).resolve().parent
MORNING_JADE = "--morning-jade" in sys.argv
LAOS = "--laos" in sys.argv
if LAOS and not MORNING_JADE:
    raise ValueError("Laos is supported with --morning-jade")
COUNTRY = "Laos" if LAOS else "Thailand"
MORNING = "--morning" in sys.argv or MORNING_JADE
REFERENCE_SKY = "--sandy-gold-light" in sys.argv or MORNING_JADE
NATURAL = "--natural-earth" in sys.argv or MORNING
SANDY = "--sandy-gold" in sys.argv or NATURAL
FINAL = "--final" in sys.argv
STRONG_SHADOWS = "--strong-shadows" in sys.argv
OUT = ROOT.parents[1] / "outputs" / "thailand" / ("morning-sandy-light" if REFERENCE_SKY else "morning" if MORNING else "natural-earth" if NATURAL else "sandy-gold-detail" if SANDY else "blue")
if MORNING_JADE:
    OUT = ROOT.parents[1] / "outputs" / COUNTRY.lower() / "morning-jade"
OUT.mkdir(parents=True, exist_ok=True)
SCALE, EXAG, BASE, MAX_ELEVATION = 6e-6, 14.0, 0.028, 2600.0
if LAOS:
    SCALE, MAX_ELEVATION = 1e-5, 3000.0
STOPS = [(0, "eef3f3"), (150, "dfecef"), (350, "b5d2df"), (650, "78a9c5"),
         (1000, "4483ad"), (1600, "245b87"), (2200, "153e65"), (2600, "102c4a")]
if SANDY:
    STOPS = [(0, "087f8e"), (150, "22abae"), (350, "80c6bf"),
             (600, "dce6da"), (950, "eee9dd"), (1400, "e3d5b3"),
             (2000, "c9b383"), (2600, "b69860")]
if NATURAL:
    STOPS = [(0, "526b3d"), (150, "6b7f46"), (350, "879159"),
             (600, "a0a070"), (950, "b0a17b"), (1400, "a58b6a"),
             (2000, "91775f"), (2600, "b9ab93")]
if MORNING:
    STOPS = [(0, "66934f"), (150, "7da25b"), (350, "92ad67"),
             (600, "b6bd83"), (950, "c9bb90"), (1400, "ad9272"),
             (2000, "ae997e"), (2600, "c9baa2")]


def rgba(text):
    srgb = [int(text[index:index + 2], 16) / 255 for index in (0, 2, 4)]
    return tuple(value / 12.92 if value <= .04045 else ((value + .055) / 1.055) ** 2.4 for value in srgb) + (1,)


def material(name, colour, roughness=.7):
    value = bpy.data.materials.new(name)
    value.use_nodes = True
    shader = value.node_tree.nodes["Principled BSDF"]
    shader.inputs["Base Color"].default_value = rgba(colour)
    shader.inputs["Roughness"].default_value = roughness
    shader.inputs["Specular IOR Level"].default_value = .2
    return value


def ramp(nodes):
    value = nodes.new("ShaderNodeValToRGB")
    value.color_ramp.interpolation = "LINEAR"
    for index, (height, colour) in enumerate(STOPS):
        element = value.color_ramp.elements[index] if index < 2 else value.color_ramp.elements.new(height / MAX_ELEVATION)
        element.position, element.color = height / MAX_ELEVATION, rgba(colour)
    return value


def add_label(name, text, x, y, size, ink, font):
    curve = bpy.data.curves.new(name, "FONT")
    curve.body, curve.font, curve.size, curve.space_character = text, font, size, 1.05
    item = bpy.data.objects.new(name, curve)
    bpy.context.collection.objects.link(item)
    item.location = (x, y, .008)
    curve.materials.append(ink)
    item.visible_shadow = False
    return item


def aim(item, target):
    item.rotation_euler = (Vector(target) - item.location).to_track_quat("-Z", "Y").to_euler()


bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
scene = bpy.context.scene
scene.render.engine = "CYCLES"
preferences = bpy.context.preferences.addons["cycles"].preferences
preferences.compute_device_type = "HIP"
preferences.refresh_devices()
for device in preferences.devices:
    device.use = device.type == "HIP"
scene.cycles.device, scene.cycles.samples = "GPU", 128
scene.cycles.use_adaptive_sampling, scene.cycles.adaptive_threshold = True, .02
scene.cycles.adaptive_min_samples, scene.cycles.use_denoising = 16, True
scene.cycles.denoiser, scene.cycles.max_bounces = "OPENIMAGEDENOISE", 8
scene.render.resolution_x, scene.render.resolution_y, scene.render.resolution_percentage = 1676, 2048, 100
scene.render.image_settings.file_format, scene.render.image_settings.color_depth = "PNG", "8"
if FINAL:
    scene.render.resolution_x, scene.render.resolution_y = 6284, 7680
    scene.render.image_settings.color_depth = "16"
    scene.render.image_settings.color_mode = "RGB"
    scene.cycles.samples = 512
    scene.cycles.adaptive_min_samples = 32
    scene.cycles.adaptive_threshold = .005
    scene.cycles.use_auto_tile = True
    scene.cycles.tile_size = 1024
scene.view_settings.view_transform, scene.view_settings.look = "AgX", "AgX - Medium High Contrast"
scene.world.use_nodes = True
scene.world.node_tree.nodes["Background"].inputs["Color"].default_value = (.78, .85, 1, 1)
scene.world.node_tree.nodes["Background"].inputs["Strength"].default_value = .3
if SANDY:
    scene.world.node_tree.nodes["Background"].inputs["Color"].default_value = rgba("f4eee4")
    scene.world.node_tree.nodes["Background"].inputs["Strength"].default_value = .45
if STRONG_SHADOWS:
    scene.world.node_tree.nodes["Background"].inputs["Strength"].default_value = .20
if MORNING:
    scene.world.node_tree.nodes["Background"].inputs["Color"].default_value = (.72, .83, 1, 1)
    scene.world.node_tree.nodes["Background"].inputs["Strength"].default_value = .22
    scene.view_settings.exposure = .45

data_root = ROOT.parent / "terrain_v2" if LAOS else ROOT
data = np.load(data_root / ("dem_mesh.npz" if LAOS else "thailand_blue_dem_150m.npz"))
meta = json.loads((data_root / ("dem_metadata.json" if LAOS else "thailand_blue_dem_150m.json")).read_text(encoding="utf-8"))
# Laos's proof uses every second point from its 150 m grid.  Thailand follows
# that same 300 m proof sampling while retaining the 150 m source for finals.
stride = 1 if FINAL else 2
elevation, mask = data["elevation_m"][::stride, ::stride], data["mask"][::stride, ::stride]
x_m, y_m = data["x_m"][::stride], data["y_m"][::stride]
center = np.asarray([(data["x_m"][0] + data["x_m"][-1]) / 2,
                     (data["y_m"][0] + data["y_m"][-1]) / 2] if LAOS else meta["center_projected_m"])
rows, columns = np.nonzero(mask)
vertices = np.empty((len(rows), 3), np.float32)
vertices[:, 0] = (x_m[columns] - center[0]) * SCALE
vertices[:, 1] = (y_m[rows] - center[1]) * SCALE
vertices[:, 2] = BASE + elevation[rows, columns] * SCALE * EXAG
ids = np.full(mask.shape, -1, np.int32)
ids[rows, columns] = np.arange(len(rows), dtype=np.int32)
quads = mask[:-1, :-1] & mask[1:, :-1] & mask[1:, 1:] & mask[:-1, 1:]
r, c = np.nonzero(quads)
faces = np.column_stack((ids[r, c], ids[r + 1, c], ids[r + 1, c + 1], ids[r, c + 1])).astype(np.int32)
blue = material("Elevation | Thailand blue", "78a9c5", .62)
if SANDY:
    blue.name = "Elevation | turquoise pearl and sandy gold"
    blue.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = .78
if NATURAL:
    blue.name = "Elevation | muted green olive and warm earth"
nodes = blue.node_tree.nodes
geometry, separate, remap = nodes.new("ShaderNodeNewGeometry"), nodes.new("ShaderNodeSeparateXYZ"), nodes.new("ShaderNodeMapRange")
remap.inputs["From Min"].default_value = BASE
remap.inputs["From Max"].default_value = BASE + MAX_ELEVATION * SCALE * EXAG
remap.clamp = True
colour_ramp = ramp(nodes)
blue.node_tree.links.new(geometry.outputs["Position"], separate.inputs[0])
blue.node_tree.links.new(separate.outputs["Z"], remap.inputs["Value"])
blue.node_tree.links.new(remap.outputs["Result"], colour_ramp.inputs[0])
blue.node_tree.links.new(colour_ramp.outputs["Color"], nodes["Principled BSDF"].inputs["Base Color"])
mesh = bpy.data.meshes.new(COUNTRY + " | 150m-source continuous elevation surface")
mesh.vertices.add(len(vertices)); mesh.vertices.foreach_set("co", vertices.ravel())
mesh.loops.add(faces.size); mesh.loops.foreach_set("vertex_index", faces.ravel())
mesh.polygons.add(len(faces)); mesh.polygons.foreach_set("loop_start", np.arange(len(faces), dtype=np.int32) * 4)
mesh.polygons.foreach_set("loop_total", np.full(len(faces), 4, dtype=np.int32))
mesh.polygons.foreach_set("use_smooth", np.full(len(faces), True, bool)); mesh.update(calc_edges=True)
terrain = bpy.data.objects.new(mesh.name, mesh)
bpy.context.collection.objects.link(terrain); mesh.materials.append(blue)
terrain["source_grid_metres"], terrain["mesh_grid_metres"] = 150, 150 * stride
terrain["vertical_exaggeration"], terrain["projection"] = EXAG, meta["projection"]
print("TERRAIN_READY", len(mesh.vertices), "vertices; grid", 150 * stride, "m", flush=True)
# Release the construction arrays before Cycles allocates its render geometry.
data.close()
del data, elevation, mask, x_m, y_m, rows, columns, vertices, ids, quads, r, c, faces
gc.collect()

ground = material("Warm porcelain backdrop", "e2ddd4" if SANDY else "e5e7e5", .82)
if MORNING:
    ground.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = rgba("f1efe9")
bpy.ops.mesh.primitive_plane_add(size=200)
bpy.context.object.name = "Matte studio ground"; bpy.context.object.data.materials.append(ground)
ink = material("Typography | blue charcoal", "344b5a")
ink.node_tree.nodes.clear(); out, emit = ink.node_tree.nodes.new("ShaderNodeOutputMaterial"), ink.node_tree.nodes.new("ShaderNodeEmission")
emit.inputs["Color"].default_value = rgba("344b5a"); ink.node_tree.links.new(emit.outputs[0], out.inputs["Surface"])
if SANDY:
    emit.inputs["Color"].default_value = rgba("3b514f")
english, thai = bpy.data.fonts.load("C:/Windows/Fonts/segoeui.ttf"), bpy.data.fonts.load("C:/Windows/Fonts/LeelawUI.ttf")
add_label("Country title", "KINGDOM OF THAILAND", -3.9, -4.48, .255, ink, english)
add_label("Thai country title", "ราชอาณาจักรไทย", -3.9, -4.86, .225, ink, thai)
add_label("Legend caption", "ELEVATION  /  METRES", -3.9, -5.22, .11, ink, english)
legend = material("Continuous elevation legend", "ffffff", .5)
texcoord, separate, legend_ramp = legend.node_tree.nodes.new("ShaderNodeTexCoord"), legend.node_tree.nodes.new("ShaderNodeSeparateXYZ"), ramp(legend.node_tree.nodes)
legend.node_tree.links.new(texcoord.outputs["Generated"], separate.inputs[0]); legend.node_tree.links.new(separate.outputs["X"], legend_ramp.inputs[0]); legend.node_tree.links.new(legend_ramp.outputs["Color"], legend.node_tree.nodes["Principled BSDF"].inputs["Base Color"])
bpy.ops.mesh.primitive_cube_add(size=1, location=(-2.275, -5.40, .008)); bpy.context.object.dimensions = (3.25, .052, .006); bpy.context.object.data.materials.append(legend)
for height in [0, 500, 1000, 1500, 2000, 2500]:
    value = add_label(f"Legend {height}", f"{height:,}", -3.9 + 3.25 * height / MAX_ELEVATION, -5.57, .09, ink, english); value.data.align_x = "CENTER"

if SANDY:
    # The open Gulf of Thailand area gives the title its own clear column.
    title = bpy.data.objects["Country title"]
    title.data.body, title.data.size = "THAILAND", .66
    title.data.font = bpy.data.fonts.load("C:/Windows/Fonts/seguisb.ttf")
    title.location = (.55, -2.38, .008)
    add_label("Title eyebrow", "K I N G D O M   O F", .58, -1.85, .125, ink, english)
    bpy.data.objects["Thai country title"].location = (.58, -2.82, .008)
    bpy.data.objects["Thai country title"].data.size = .25
    bpy.data.objects["Legend caption"].location = (.58, -3.50, .008)
    bpy.data.objects["Legend caption"].data.size = .105
    # Flat, shadowless cartographic scale, using the same elevation colors.
    bar = next(o for o in scene.objects if o.type == "MESH" and o.data.materials and o.data.materials[0] == legend)
    bar.location = (2.18, -3.69, .008)
    bar.dimensions = (3.2, .065, .006)
    bar.visible_shadow = False
    legend_nodes = legend.node_tree.nodes
    legend_emit = legend_nodes.new("ShaderNodeEmission")
    legend.node_tree.links.new(legend_ramp.outputs["Color"], legend_emit.inputs["Color"])
    legend.node_tree.links.new(legend_emit.outputs[0], legend_nodes["Material Output"].inputs["Surface"])
    for height in [0, 500, 1000, 1500, 2000, 2500]:
        bpy.data.objects[f"Legend {height}"].location = (.58 + 3.2 * height / MAX_ELEVATION, -3.89, .008)
        bpy.data.objects[f"Legend {height}"].data.size = .105
    add_label("Relief caption", "T O P O G R A P H I C   R E L I E F", .58, -4.36, .095, ink, english)

if LAOS:
    title.data.body, title.data.size = "LAOS", .82
    title.location = (-3.5, -2.38, .008)
    eyebrow = bpy.data.objects["Title eyebrow"]
    eyebrow.data.body = "LAO PEOPLE'S DEMOCRATIC REPUBLIC"
    eyebrow.data.size = .11
    eyebrow.location = (-3.48, -1.60, .008)
    native = bpy.data.objects["Thai country title"]
    native.name = "Lao country title"
    native.data.body = "ສາທາລະນະລັດ ປະຊາທິປະໄຕ ປະຊາຊົນລາວ"
    lao_font = Path("C:/Users/mikasaloli/AppData/Local/Microsoft/Windows/Fonts/Phetsarath-Regular.ttf")
    native.data.font = bpy.data.fonts.load(str(lao_font)) if lao_font.exists() else thai
    native.data.size = .18
    native.location = (-3.48, -2.86, .008)
    bpy.data.objects["Legend caption"].location = (-3.48, -3.50, .008)
    bar.location = (-1.88, -3.69, .008)
    for height in [0, 500, 1000, 1500, 2000, 2500]:
        tick = bpy.data.objects[f"Legend {height}"]
        tick.location = (-3.48 + 3.2 * height / MAX_ELEVATION, -3.89, .008)
        tick.data.size = .10
    tick = add_label("Legend 3000", "3,000", -.28, -3.89, .10, ink, english)
    tick.data.align_x = "CENTER"
    bpy.data.objects["Relief caption"].location = (-3.48, -4.36, .008)

for name, kind, energy, size, location in [("Large northwest softbox", "AREA", 1800, 5, (-5, 4, 9)), ("Northwest raking relief light", "SUN", 2, .09, (-6, 5, 8))]:
    source = bpy.data.lights.new(name, kind); source.energy = energy
    if kind == "AREA": source.shape, source.size = "DISK", size
    else: source.angle = size
    item = bpy.data.objects.new(name, source); bpy.context.collection.objects.link(item); item.location = location; aim(item, (0, 0, 0))
    if SANDY:
        if kind == "AREA":
            source.energy, source.size = 1300, 6
        else:
            source.energy, source.angle = 1.7, .14
    if STRONG_SHADOWS:
        if kind == "AREA":
            source.energy, source.size = 650, 6
        else:
            source.energy, source.angle = 2.1, .06
            item.location = (-6, 5, 5.5)
            aim(item, (0, 0, 0))
    if MORNING:
        if kind == "AREA":
            source.energy, source.size = 700, 7
            source.color = (.85, .92, 1)
        else:
            source.energy, source.angle = 4.2, .035
            source.color = (1, .94, .84)
            item.location = (7, 5, 3.5)
            aim(item, (0, 0, 0))
if REFERENCE_SKY:
    # Reuse the actual reference atmosphere, including its large low sun disc.
    reference = ROOT.parents[1] / "outputs/thailand/sandy-gold-terraces/thailand_relief_contour_sandy_gold_8k.blend"
    with bpy.data.libraries.load(str(reference), link=False) as (available, loaded):
        loaded.worlds = ["Tutorial atmosphere | sun and sky"]
    scene.world = loaded.worlds[0]
    for item in list(scene.objects):
        if item.type == "LIGHT":
            bpy.data.objects.remove(item, do_unlink=True)
    scene.view_settings.view_transform = "Filmic"
    scene.view_settings.look = "Very High Contrast"
    scene.view_settings.exposure = 0
    ground.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (.95, .95, .95, 1)
camera = bpy.data.cameras.new("Near-overhead orthographic portrait")
camera_obj = bpy.data.objects.new(camera.name, camera); bpy.context.collection.objects.link(camera_obj); camera_obj.location = (0, -2.7, 22); aim(camera_obj, (0, -.35, 0)); camera.type, camera.ortho_scale, camera.clip_end = "ORTHO", 12.35, 300; scene.camera = camera_obj
if LAOS:
    camera.ortho_scale = 11.45
scene["Design"] = "Thailand blue elevation relief from a 150 m projected terrain grid, matching the Laos blue-source resolution."
scene["DEM provenance"], scene["Sources"] = meta["source"], "Mapzen Terrain Tiles / geoBoundaries gbOpen THA ADM0"
if LAOS:
    scene["Sources"] = "Mapzen Terrain Tiles / geoBoundaries gbOpen LAO ADM0"
scene.render.filepath = str(OUT / "thailand_relief_blue_preview.png")
if SANDY:
    scene["Design"] = "Detailed Thailand relief; turquoise lowlands, pearl ridges, sandy-gold summits on warm studio paper. Title in the open gulf area."
    if NATURAL:
        scene["Design"] = "Detailed Thailand relief in muted green, olive and earth elevation colors on warm studio paper. Title in the open gulf area."
    if MORNING:
        scene["Design"] = "Fresh green Thailand relief in warm low-angle morning sunlight, long defined shadows, neutral ivory ground, and subtle cool skylight."
    if REFERENCE_SKY:
        scene["Lighting reference"] = "Exact world atmosphere and color management from the original Thailand Sandy Gold scene."
    stem = ("thailand_relief_morning" if MORNING else "thailand_relief_natural_earth" if NATURAL else "thailand_relief_sandy_gold_detail") + ("_8k" if FINAL else "")
    if MORNING_JADE:
        scene["Edition"] = "Morning Jade"
        scene["Design"] = "Morning Jade: fresh green terrain, warm sunlight and soft blue-gray shadows from the original Sandy Gold atmosphere."
        stem = COUNTRY.lower() + "_relief_morning_jade" + ("_8k" if FINAL else "_preview")
    scene.render.filepath = str(OUT / (stem + ".png"))
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT / (stem + ".blend")), compress=True)
elif FINAL:
    scene.render.filepath = str(OUT / "thailand_relief_blue_150m_8k.png")
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT / "thailand_relief_blue_150m_8k.blend"), compress=True)
bpy.ops.render.render(write_still=True)
print(COUNTRY.upper() + "_RENDER_COMPLETE", scene.render.filepath, flush=True)
