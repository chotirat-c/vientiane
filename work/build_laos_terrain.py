import bpy
import json
import math
import os
from mathutils import Vector


DATA_PATH = r"C:\Users\mikasaloli\Documents\Codex\2026-09-05\ho\work\laos_dem_grid.json"
OUTPUT_DIR = r"C:\Users\mikasaloli\Documents\Codex\2026-09-05\ho\outputs"
BLEND_PATH = os.path.join(OUTPUT_DIR, "laos_elevation_terrain_8k.blend")
RENDER_PATH = os.path.join(OUTPUT_DIR, "laos_elevation_terrain_8k.png")


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)


def simple_material(name, color, roughness=0.5):
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = color
    bsdf.inputs["Roughness"].default_value = roughness
    return mat


def terrain_material(max_z):
    mat = bpy.data.materials.new(name="Elevation Color Ramp")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    for node in list(nodes):
        nodes.remove(node)

    output = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    geometry = nodes.new("ShaderNodeNewGeometry")
    separate = nodes.new("ShaderNodeSeparateXYZ")
    mapping = nodes.new("ShaderNodeMapRange")
    ramp = nodes.new("ShaderNodeValToRGB")

    geometry.location = (-720, 40)
    separate.location = (-540, 40)
    mapping.location = (-350, 40)
    ramp.location = (-120, 40)
    bsdf.location = (140, 40)
    output.location = (390, 40)

    mapping.inputs["From Min"].default_value = 0.0
    mapping.inputs["From Max"].default_value = max_z
    mapping.inputs["To Min"].default_value = 0.0
    mapping.inputs["To Max"].default_value = 1.0
    mapping.clamp = True

    color_ramp = ramp.color_ramp
    color_ramp.interpolation = "EASE"
    color_ramp.elements.remove(color_ramp.elements[1])
    stops = [
        (0.00, (0.68, 0.88, 0.91, 1.0)),
        (0.11, (0.18, 0.66, 0.69, 1.0)),
        (0.27, (0.22, 0.56, 0.34, 1.0)),
        (0.46, (0.73, 0.69, 0.24, 1.0)),
        (0.66, (0.88, 0.43, 0.18, 1.0)),
        (0.84, (0.57, 0.16, 0.12, 1.0)),
        (1.00, (0.96, 0.90, 0.76, 1.0)),
    ]
    first = color_ramp.elements[0]
    first.position, first.color = stops[0]
    for position, color in stops[1:]:
        element = color_ramp.elements.new(position)
        element.color = color

    bsdf.inputs["Roughness"].default_value = 0.47
    bsdf.inputs["Specular IOR Level"].default_value = 0.28
    links.new(geometry.outputs["Position"], separate.inputs["Vector"])
    links.new(separate.outputs["Z"], mapping.inputs["Value"])
    links.new(mapping.outputs["Result"], ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])
    return mat, stops


def add_text(body, location, size, material, name, extrude=0.006):
    data = bpy.data.curves.new(name=name, type="FONT")
    data.body = body
    data.align_x = "LEFT"
    data.align_y = "CENTER"
    data.size = size
    data.extrude = extrude
    data.bevel_depth = 0.0015
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    obj.location = location
    obj.data.materials.append(material)
    return obj


def aim_at(obj, target):
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat("-Z", "Y").to_euler()


with open(DATA_PATH, "r", encoding="utf-8") as handle:
    dem = json.load(handle)

width = dem["width"]
height = dem["height"]
elev = dem["elevation_m"]
mask = dem["mask"]
maximum_m = max(dem["max_elevation_m"], 1.0)

clear_scene()
os.makedirs(OUTPUT_DIR, exist_ok=True)

map_width = 8.3
map_height = map_width * height / width
max_z = 2.75
vertices = []
indices = [[-1] * width for _ in range(height)]

for row in range(height):
    y = (0.5 - row / (height - 1)) * map_height
    for col in range(width):
        if not mask[row][col]:
            continue
        x = (col / (width - 1) - 0.5) * map_width
        normalized = max(0.0, elev[row][col]) / maximum_m
        z = 0.035 + (normalized ** 0.96) * max_z
        indices[row][col] = len(vertices)
        vertices.append((x, y, z))

faces = []
for row in range(height - 1):
    for col in range(width - 1):
        a = indices[row][col]
        b = indices[row][col + 1]
        c = indices[row + 1][col + 1]
        d = indices[row + 1][col]
        if min(a, b, c, d) >= 0:
            faces.append((a, b, c, d))

mesh = bpy.data.meshes.new("Laos DEM Terrain")
mesh.from_pydata(vertices, [], faces)
mesh.update()
terrain = bpy.data.objects.new("Laos Elevation Terrain", mesh)
bpy.context.collection.objects.link(terrain)
terrain["data_source"] = dem["source"]
terrain["min_elevation_m"] = dem["min_elevation_m"]
terrain["max_elevation_m"] = dem["max_elevation_m"]

for polygon in mesh.polygons:
    polygon.use_smooth = True

terrain_mat, ramp_stops = terrain_material(max_z + 0.05)
terrain.data.materials.append(terrain_mat)

subdivision = terrain.modifiers.new("Render Micro-Smoothing", "SUBSURF")
subdivision.subdivision_type = "CATMULL_CLARK"
subdivision.levels = 0
subdivision.render_levels = 1

solidify = terrain.modifiers.new("Country Base", "SOLIDIFY")
solidify.thickness = 0.20
solidify.offset = -1.0
solidify.use_rim = True

bevel = terrain.modifiers.new("Soft Country Edge", "BEVEL")
bevel.width = 0.007
bevel.segments = 2

# Matte presentation surface.
ground_mat = simple_material("Warm White Ground", (0.72, 0.72, 0.69, 1.0), roughness=0.82)
bpy.ops.mesh.primitive_plane_add(size=30.0, location=(0.0, 0.0, -0.13))
ground = bpy.context.object
ground.name = "Presentation Ground"
ground.data.materials.append(ground_mat)

ink_mat = simple_material("Typography", (0.035, 0.045, 0.055, 1.0), roughness=0.56)
add_text("LAO PEOPLE'S DEMOCRATIC REPUBLIC", (-5.1, -5.68, 0.02), 0.34, ink_mat, "Title English", 0.008)
add_text("8K ELEVATION RELIEF · 0–2,720 METRES", (-5.08, -6.12, 0.02), 0.20, ink_mat, "Title Elevation", 0.005)

# Compact elevation legend.
legend_colors = [
    (0.68, 0.88, 0.91, 1.0),
    (0.18, 0.66, 0.69, 1.0),
    (0.22, 0.56, 0.34, 1.0),
    (0.73, 0.69, 0.24, 1.0),
    (0.88, 0.43, 0.18, 1.0),
    (0.57, 0.16, 0.12, 1.0),
    (0.96, 0.90, 0.76, 1.0),
]
legend_labels = ["0", "250", "600", "1,000", "1,500", "2,000", "2,720 m"]
start_x = -5.05
for i, (color, label) in enumerate(zip(legend_colors, legend_labels)):
    x = start_x + i * 0.83
    swatch_mat = simple_material(f"Legend {i}", color, roughness=0.5)
    bpy.ops.mesh.primitive_cube_add(location=(x + 0.25, -6.62, 0.025), scale=(0.41, 0.11, 0.025))
    swatch = bpy.context.object
    swatch.name = f"Legend Swatch {label}"
    swatch.data.materials.append(swatch_mat)
    text_obj = add_text(label, (x + 0.02, -6.90, 0.02), 0.13, ink_mat, f"Legend Label {label}", 0.003)
    text_obj.data.align_x = "CENTER"

# Lighting emphasizes slope and ridge structure.
world = bpy.context.scene.world
world.use_nodes = True
world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.58, 0.62, 0.67, 1.0)
world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.38

sun_data = bpy.data.lights.new("Terrain Sun", type="SUN")
sun_data.energy = 2.4
sun_data.angle = math.radians(18.0)
sun = bpy.data.objects.new("Terrain Sun", sun_data)
bpy.context.collection.objects.link(sun)
sun.rotation_euler = (math.radians(28), math.radians(-18), math.radians(-32))

area_data = bpy.data.lights.new("Soft Fill", type="AREA")
area_data.energy = 950
area_data.shape = "DISK"
area_data.size = 8.0
area = bpy.data.objects.new("Soft Fill", area_data)
bpy.context.collection.objects.link(area)
area.location = (-5.0, -6.0, 10.0)
aim_at(area, (0.0, 0.0, 0.4))

# Near top-down orthographic composition with enough tilt for readable relief.
camera_data = bpy.data.cameras.new("Elevation Camera")
camera_data.type = "ORTHO"
camera_data.ortho_scale = 15.8
camera = bpy.data.objects.new("Elevation Camera", camera_data)
bpy.context.collection.objects.link(camera)
camera.location = (0.0, -15.4, 18.2)
aim_at(camera, (0.0, -0.15, 0.62))
bpy.context.scene.camera = camera

scene = bpy.context.scene
scene.render.engine = "BLENDER_EEVEE"
scene.render.resolution_x = 6284
scene.render.resolution_y = 7680
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_mode = "RGBA"
scene.render.image_settings.color_depth = "8"
scene.render.filepath = RENDER_PATH
scene.render.film_transparent = False
scene.view_settings.look = "AgX - Medium High Contrast"

bpy.ops.wm.save_as_mainfile(filepath=BLEND_PATH)
bpy.ops.render.render(write_still=True)
print(
    json.dumps(
        {
            "blend": BLEND_PATH,
            "render": RENDER_PATH,
            "vertices": len(vertices),
            "faces": len(faces),
            "elevation_range_m": [dem["min_elevation_m"], dem["max_elevation_m"]],
        }
    )
)
