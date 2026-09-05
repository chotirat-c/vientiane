import bpy
import json
import math
import os
from mathutils import Vector


GEOJSON_PATH = r"C:\Users\mikasaloli\Documents\Codex\2026-09-05\ho\work\laos_adm1.geojson"
OUTPUT_DIR = r"C:\Users\mikasaloli\Documents\Codex\2026-09-05\ho\outputs"
BLEND_PATH = os.path.join(OUTPUT_DIR, "laos_adm1_colored_map.blend")
RENDER_PATH = os.path.join(OUTPUT_DIR, "laos_adm1_colored_map.png")

PALETTE = [
    (0.08, 0.55, 0.67, 1.0),
    (0.98, 0.55, 0.20, 1.0),
    (0.95, 0.78, 0.22, 1.0),
    (0.30, 0.70, 0.47, 1.0),
    (0.75, 0.32, 0.40, 1.0),
    (0.43, 0.42, 0.78, 1.0),
    (0.92, 0.42, 0.55, 1.0),
    (0.20, 0.64, 0.60, 1.0),
    (0.95, 0.66, 0.18, 1.0),
]


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for datablocks in (
        bpy.data.curves,
        bpy.data.meshes,
        bpy.data.materials,
        bpy.data.cameras,
        bpy.data.lights,
    ):
        for block in list(datablocks):
            if block.users == 0:
                datablocks.remove(block)


def material(name, color, roughness=0.48, metallic=0.0):
    mat = bpy.data.materials.new(name=name)
    mat.diffuse_color = color
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = color
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    return mat


def polygon_curve(name, points, height, mat):
    curve = bpy.data.curves.new(name=name, type="CURVE")
    curve.dimensions = "2D"
    curve.resolution_u = 1
    curve.fill_mode = "BOTH"
    curve.extrude = height
    curve.bevel_depth = 0.012
    curve.bevel_resolution = 2
    spline = curve.splines.new("POLY")
    spline.points.add(len(points) - 1)
    for p, (x, y) in zip(spline.points, points):
        p.co = (x, y, 0.0, 1.0)
    spline.use_cyclic_u = True
    obj = bpy.data.objects.new(name, curve)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(mat)
    return obj


def border_curve(name, points, z, mat):
    curve = bpy.data.curves.new(name=name, type="CURVE")
    curve.dimensions = "3D"
    curve.resolution_u = 1
    curve.bevel_depth = 0.022
    curve.bevel_resolution = 2
    spline = curve.splines.new("POLY")
    spline.points.add(len(points) - 1)
    for p, (x, y) in zip(spline.points, points):
        p.co = (x, y, z, 1.0)
    spline.use_cyclic_u = True
    obj = bpy.data.objects.new(name, curve)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(mat)
    return obj


def add_text(body, location, size, mat, name, extrude=0.008):
    curve = bpy.data.curves.new(name=name, type="FONT")
    curve.body = body
    curve.align_x = "CENTER"
    curve.align_y = "CENTER"
    curve.size = size
    curve.extrude = extrude
    curve.bevel_depth = 0.002
    obj = bpy.data.objects.new(name, curve)
    bpy.context.collection.objects.link(obj)
    obj.location = location
    obj.data.materials.append(mat)
    return obj


def aim_at(obj, target):
    direction = Vector(target) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


os.makedirs(OUTPUT_DIR, exist_ok=True)
with open(GEOJSON_PATH, "r", encoding="utf-8") as handle:
    geo = json.load(handle)

all_coords = []
for feature in geo["features"]:
    all_coords.extend(feature["geometry"]["coordinates"][0])

min_lon = min(p[0] for p in all_coords)
max_lon = max(p[0] for p in all_coords)
min_lat = min(p[1] for p in all_coords)
max_lat = max(p[1] for p in all_coords)
center_lon = (min_lon + max_lon) / 2.0
center_lat = (min_lat + max_lat) / 2.0
lon_adjust = math.cos(math.radians(center_lat))
span_x = (max_lon - min_lon) * lon_adjust
span_y = max_lat - min_lat
scale = 12.0 / max(span_x, span_y)


def project(coord):
    return (
        (coord[0] - center_lon) * lon_adjust * scale,
        (coord[1] - center_lat) * scale,
    )


clear_scene()

province_collection = bpy.data.collections.new("LAOS_ADM1_PROVINCES")
bpy.context.scene.collection.children.link(province_collection)
label_collection = bpy.data.collections.new("PROVINCE_LABELS")
bpy.context.scene.collection.children.link(label_collection)

border_mat = material("Borders", (0.025, 0.037, 0.055, 1.0), roughness=0.4)
label_mat = material("Label Ink", (0.018, 0.025, 0.038, 1.0), roughness=0.5)
title_mat = material("Title", (0.91, 0.96, 0.98, 1.0), roughness=0.42)
ground_mat = material("Ground", (0.018, 0.028, 0.045, 1.0), roughness=0.78)

province_materials = []
for i, color in enumerate(PALETTE):
    province_materials.append(material(f"Province Color {i + 1:02d}", color, roughness=0.38))

for index, feature in enumerate(sorted(geo["features"], key=lambda f: f["properties"]["shapeName"])):
    name = feature["properties"]["shapeName"]
    iso = feature["properties"].get("shapeISO", "")
    raw_ring = feature["geometry"]["coordinates"][0]
    if raw_ring[0] == raw_ring[-1]:
        raw_ring = raw_ring[:-1]
    ring = [project(point) for point in raw_ring]
    height = 0.12 + 0.026 * (index % 5)
    obj = polygon_curve(f"ADM1_{name}", ring, height, province_materials[index % len(province_materials)])
    obj["province_name"] = name
    obj["province_iso"] = iso
    obj["admin_level"] = "ADM1"
    for collection in list(obj.users_collection):
        collection.objects.unlink(obj)
    province_collection.objects.link(obj)
    border = border_curve(f"Border_{name}", ring, height * 2.0 + 0.018, border_mat)
    for collection in list(border.users_collection):
        collection.objects.unlink(border)
    province_collection.objects.link(border)

    cx = sum(p[0] for p in ring) / len(ring)
    cy = sum(p[1] for p in ring) / len(ring)
    short_name = name.replace("Vientiane Capital", "Vientiane\nCapital").replace("Luang Prabang", "Luang\nPrabang").replace("Luang Namtha", "Luang\nNamtha")
    label_size = 0.16 if len(name) > 13 else 0.19
    label = add_text(short_name, (cx, cy, height * 2.0 + 0.055), label_size, label_mat, f"Label_{name}")
    for collection in list(label.users_collection):
        collection.objects.unlink(label)
    label_collection.objects.link(label)

# Presentation ground.
bpy.ops.mesh.primitive_plane_add(size=26.0, location=(0.0, 0.0, -0.10))
ground = bpy.context.object
ground.name = "Presentation Ground"
ground.data.materials.append(ground_mat)

# Title and subtitle above the northern edge.
add_text("LAOS", (-4.4, 6.15, 0.08), 0.72, title_mat, "Title_LAOS", extrude=0.012)
add_text("18 PROVINCES · ADM1", (-4.38, 5.58, 0.08), 0.25, title_mat, "Subtitle_ADM1", extrude=0.006)

# Camera with a slight tilt to reveal the province elevation.
camera_data = bpy.data.cameras.new("Map Camera")
camera = bpy.data.objects.new("Map Camera", camera_data)
bpy.context.collection.objects.link(camera)
camera.location = (0.0, -10.8, 15.8)
camera_data.type = "ORTHO"
camera_data.ortho_scale = 16.1
camera_data.lens = 52
aim_at(camera, (0.0, 0.25, 0.0))
bpy.context.scene.camera = camera

# Broad studio lighting.
key_data = bpy.data.lights.new("Key Area", type="AREA")
key_data.energy = 1250
key_data.shape = "DISK"
key_data.size = 8.0
key = bpy.data.objects.new("Key Area", key_data)
bpy.context.collection.objects.link(key)
key.location = (-5.0, -4.0, 11.0)
aim_at(key, (0.0, 0.0, 0.0))

fill_data = bpy.data.lights.new("Fill Area", type="AREA")
fill_data.energy = 800
fill_data.size = 7.0
fill = bpy.data.objects.new("Fill Area", fill_data)
bpy.context.collection.objects.link(fill)
fill.location = (6.0, 3.0, 9.0)
aim_at(fill, (0.0, 0.5, 0.0))

world = bpy.context.scene.world
world.use_nodes = True
world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.012, 0.020, 0.036, 1.0)
world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.32

scene = bpy.context.scene
scene.render.engine = "BLENDER_EEVEE_NEXT"
scene.render.resolution_x = 1100
scene.render.resolution_y = 1350
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
scene.render.film_transparent = False
scene.render.filepath = RENDER_PATH
scene.render.image_settings.color_mode = "RGBA"
scene.render.image_settings.color_depth = "8"
scene.view_settings.look = "AgX - Medium High Contrast"

# Soft contact shadows and clean edges.
scene.render.use_file_extension = True
bpy.ops.wm.save_as_mainfile(filepath=BLEND_PATH)
bpy.ops.render.render(write_still=True)
print(json.dumps({"blend": BLEND_PATH, "render": RENDER_PATH, "province_count": len(geo["features"])}))
