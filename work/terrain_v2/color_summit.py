"""Colour the topmost tier of the minimal contour sculpture; preview only."""
import bpy
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'outputs'/'laos'/'sandy-gold-terraces'
OUT.mkdir(parents=True,exist_ok=True)
s=bpy.context.scene
layers=[o for o in s.objects if 'contour_elevation_m' in o]
top=max(o['contour_elevation_m'] for o in layers)
material=bpy.data.materials.new('Highest terrace | deep azure')
material.use_nodes=True
rgb=[int('167fab'[i:i+2],16)/255 for i in (0,2,4)]
color=tuple(c/12.92 if c<=.04045 else ((c+.055)/1.055)**2.4 for c in rgb)+(1,)
material.diffuse_color=color
bsdf=material.node_tree.nodes['Principled BSDF']
bsdf.inputs['Base Color'].default_value=color
bsdf.inputs['Roughness'].default_value=.4
for obj in layers:
    if obj['contour_elevation_m']==top:
        obj.data.materials.clear()
        obj.data.materials.append(material)
        print('COLOURED_SUMMIT',obj.name,top,flush=True)

# Add the new tier colour to the existing legend.
bpy.ops.mesh.primitive_cube_add(size=1,location=(-.33,-5.42,.015))
swatch=bpy.context.object
swatch.name='Layer legend swatch | highest terrace'
swatch.dimensions=(.28,.07,.016)
swatch.data.materials.append(material)
curve=bpy.data.curves.new('Highest terrace legend','FONT')
curve.body=f'{top:,} m';curve.size=.095
curve.materials.append(bpy.data.materials['Typography | blue charcoal'])
obj=bpy.data.objects.new(curve.name,curve)
s.collection.objects.link(obj)
obj.location=(-.16,-5.45,.01);obj.visible_shadow=False
label=bpy.data.objects.get('Layer legend 400 m +')
if label: label.data.body='400–800 m';label.data.size=.082
s['Summit colour']='Deep azure on the highest 1000 m generalized contour tier.'
prefs=bpy.context.preferences.addons['cycles'].preferences
prefs.compute_device_type='HIP';prefs.refresh_devices()
for device in prefs.devices: device.use=device.type=='HIP'
s.cycles.device='GPU'
s.render.filepath=str(OUT/'laos_relief_contour_blue_summit_8k.png')
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'laos_relief_contour_blue_summit_8k.blend'),compress=True)
s.render.resolution_x=1676;s.render.resolution_y=2048
s.cycles.samples=96;s.cycles.adaptive_min_samples=16;s.cycles.adaptive_threshold=.02
s.render.image_settings.color_depth='8'
s.render.filepath=str(OUT/'laos_relief_contour_blue_summit_preview.png')
bpy.ops.render.render(write_still=True)
