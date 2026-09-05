"""Edit the supplied blue relief scene and render a lighting proof."""
import bpy
from pathlib import Path
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[2]
scene = bpy.context.scene
ground = bpy.data.objects['Matte studio ground'].data.materials[0]
ground.name = 'Clean white morning backdrop'
ground.diffuse_color = (1, 1, 1, 1)
bsdf = ground.node_tree.nodes['Principled BSDF']
bsdf.inputs['Base Color'].default_value = (1, 1, 1, 1)
bsdf.inputs['Roughness'].default_value = .9
bsdf.inputs['Specular IOR Level'].default_value = .12

world = scene.world.node_tree.nodes['Background']
world.inputs['Color'].default_value = (1, 1, 1, 1)
world.inputs['Strength'].default_value = .12

sun = bpy.data.objects['Northwest raking relief light']
sun.location = (-6, 5, 6)
sun.rotation_euler = (Vector((0, 0, 0))-sun.location).to_track_quat('-Z','Y').to_euler()
sun.data.energy = 4.2
sun.data.color = (1, 1, 1)
sun.data.angle = .045
fill = bpy.data.objects['Large northwest softbox']
fill.data.energy = 500
fill.data.color = (1, 1, 1)
scene.view_settings.exposure = .35
# A linked daylight source lifts the white ground without washing out the blue.
receivers = bpy.data.collections.new('Morning backdrop light receivers')
receivers.objects.link(bpy.data.objects['Matte studio ground'])
ground_sun = bpy.data.objects.new('Morning daylight | backdrop only', sun.data.copy())
scene.collection.objects.link(ground_sun)
ground_sun.location = sun.location
ground_sun.rotation_euler = sun.rotation_euler
ground_sun.data.energy = 7.0
ground_sun.light_linking.receiver_collection = receivers
scene['Lighting revision'] = 'Bright neutral-white morning ground; stronger lower northwest sun, reduced ambient fill, pronounced directional shadows. Original blue elevation material preserved.'

prefs = bpy.context.preferences.addons['cycles'].preferences
prefs.compute_device_type = 'HIP'
prefs.refresh_devices()
for device in prefs.devices:
    device.use = device.type == 'HIP'
scene.cycles.device = 'GPU'
scene.render.filepath = str(ROOT/'outputs/laos_relief_bright_morning_8k.png')
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'outputs/laos_relief_bright_morning_8k.blend'), compress=True)

scene.render.resolution_x = 1676
scene.render.resolution_y = 2048
scene.render.resolution_percentage = 100
scene.cycles.samples = 128
scene.cycles.adaptive_min_samples = 16
scene.cycles.adaptive_threshold = .015
scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.color_depth = '8'
scene.render.filepath = str(ROOT/'outputs/laos_relief_bright_morning_preview.png')
bpy.ops.render.render(write_still=True)
print('MORNING_PROOF_COMPLETE', flush=True)
