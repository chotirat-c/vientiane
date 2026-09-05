"""Pure white backdrop and warm morning sun; preview only."""
import bpy
from pathlib import Path

root = Path(__file__).resolve().parents[2]
s = bpy.context.scene
sun = bpy.data.objects['Northwest raking relief light']
sun.data.color = (1.0, .80, .57)
sun.data.energy = 5.0
sun.data.angle = .0093
sun.name = 'Pale yellow morning sun | upper left'
fill = bpy.data.objects['Large northwest softbox']
fill.data.color = (1, .98, .93)
fill.hide_render = True
s.world.node_tree.nodes['Background'].inputs['Color'].default_value=(.78,.87,1,1)
s.world.node_tree.nodes['Background'].inputs['Strength'].default_value=.30

# A separate linked light exposes the backdrop to display white. Excluding the
# ground from diffuse rays prevents this photographic backdrop light from
# washing out the blue terrain. Relief still blocks it to form cast shadows.
ground = bpy.data.objects['Matte studio ground']
ground.visible_diffuse = True
ground.visible_glossy = True
ground.is_shadow_catcher = True
backlight = bpy.data.objects['Morning daylight | backdrop only']
backlight.data.energy = 256
backlight.data.color = (1, 1, 1)
backlight.data.angle = .055
backlight.hide_render = True
# Composite the shaded relief and real shadow catcher over display-white after
# AgX. This keeps white exact without overexposing text antialiasing or terrain.
s.render.film_transparent = True
s.render.dither_intensity = 0
tree = bpy.data.node_groups.new('White background | AgX relief and true cast shadows', 'CompositorNodeTree')
s.compositing_node_group = tree
tree.interface.new_socket(name='Image', in_out='OUTPUT', socket_type='NodeSocketColor')
layers = tree.nodes.new('CompositorNodeRLayers')
straight = tree.nodes.new('CompositorNodePremulKey')
straight.inputs['Type'].default_value = 'To Straight'
display = tree.nodes.new('CompositorNodeConvertToDisplay')
display.display_settings.display_device = 'sRGB'
display.view_settings.view_transform = 'AgX'
display.view_settings.look = 'AgX - Medium High Contrast'
exposure = tree.nodes.new('CompositorNodeExposure')
exposure.inputs['Exposure'].default_value=.55
premul = tree.nodes.new('CompositorNodePremulKey')
premul.inputs['Type'].default_value = 'To Premultiplied'
over = tree.nodes.new('CompositorNodeAlphaOver')
over.inputs['Factor'].default_value = 1
over.inputs['Background'].default_value = (1,1,1,1)
linear = tree.nodes.new('CompositorNodeConvertColorSpace')
linear.from_color_space = 'sRGB'
linear.to_color_space = 'Linear Rec.709'
output = tree.nodes.new('NodeGroupOutput')
for a,b in [(layers.outputs['Image'],straight.inputs[0]),(straight.outputs[0],exposure.inputs['Image']),(exposure.outputs[0],display.inputs['Image']),(display.outputs[0],premul.inputs[0]),(premul.outputs[0],over.inputs['Foreground']),(over.outputs[0],linear.inputs[0]),(linear.outputs[0],output.inputs['Image'])]:
    tree.links.new(a,b)
for index,node in enumerate([layers,straight,exposure,display,premul,over,linear,output]):
    node.location=(index*220,0)
s.view_settings.view_transform='Standard'
s.view_settings.look='None'
s.view_settings.exposure=0
s['Lighting revision'] = 'Single warm morning sun with physical 0.53 degree angular diameter. No studio or backdrop lights; faint sky ambience. AgX shaded relief composited over pure white, with real cast shadows. Embedded Phetsarath Regular. Preview only rendered.'
prefs = bpy.context.preferences.addons['cycles'].preferences
prefs.compute_device_type = 'HIP'
prefs.refresh_devices()
for device in prefs.devices:
    device.use = device.type == 'HIP'
s.cycles.device = 'GPU'
lao = bpy.data.objects['Lao country title']
bpy.context.view_layer.update()
old_width = lao.dimensions.x
lao.data.font = bpy.data.fonts.load('C:/Users/mikasaloli/AppData/Local/Microsoft/Windows/Fonts/Phetsarath-Regular.ttf')
bpy.context.view_layer.update()
lao.data.size *= old_width / lao.dimensions.x
lao.visible_shadow = False
lao['Font revision'] = 'Phetsarath Regular, embedded; original line width preserved.'
bpy.ops.file.pack_all()
s.render.filepath = str(root/'outputs/laos_relief_white_sunlight_8k.png')
bpy.ops.wm.save_as_mainfile(filepath=str(root/'outputs/laos_relief_white_sunlight_8k.blend'), compress=True)
s.render.resolution_x = 1676
s.render.resolution_y = 2048
s.render.resolution_percentage = 100
s.cycles.samples = 128
s.cycles.adaptive_min_samples = 16
s.cycles.adaptive_threshold = .015
s.render.image_settings.file_format = 'PNG'
s.render.image_settings.color_depth = '8'
s.render.filepath = str(root/'outputs/laos_relief_white_sunlight_preview.png')
bpy.ops.render.render(write_still=True)
im = bpy.data.images.load(s.render.filepath, check_existing=False)
im.colorspace_settings.name = 'Non-Color'
w,h = im.size
for x,y in [(25,25),(25,h-25),(w-25,h-25),(w-25,25),(w//2,h-25)]:
    i = (y*w+x)*4
    print('BACKGROUND_RGB',x,y,[round(v*255) for v in im.pixels[i:i+3]],flush=True)
print('WHITE_SUNLIGHT_PREVIEW_COMPLETE',flush=True)
