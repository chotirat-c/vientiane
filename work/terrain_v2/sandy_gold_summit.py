"""Recolour the minimal sculpture's summit material; preview only."""
import bpy
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'outputs'/'laos'/'sandy-gold-terraces'
OUT.mkdir(parents=True,exist_ok=True)
scene=bpy.context.scene
material=bpy.data.materials['Highest terrace | deep azure']
material.name='Highest terrace | muted sandy gold'
rgb=[int('c9b383'[i:i+2],16)/255 for i in (0,2,4)]
color=tuple(v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4 for v in rgb)+(1,)
material.diffuse_color=color
material.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value=color
scene['Summit colour']='Muted sandy gold (#c9b383) on the highest generalized contour tier and matching legend swatch.'
prefs=bpy.context.preferences.addons['cycles'].preferences
prefs.compute_device_type='HIP'
prefs.refresh_devices()
for device in prefs.devices:
    device.use=device.type=='HIP'
scene.cycles.device='GPU'
scene.render.filepath=str(OUT/'laos_relief_contour_sandy_gold_8k.png')
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'laos_relief_contour_sandy_gold_8k.blend'),compress=True)
scene.render.resolution_x=1676
scene.render.resolution_y=2048
scene.cycles.samples=96
scene.cycles.adaptive_min_samples=16
scene.cycles.adaptive_threshold=.02
scene.render.image_settings.color_depth='8'
scene.render.filepath=str(OUT/'laos_relief_contour_sandy_gold_preview.png')
bpy.ops.render.render(write_still=True)
print('SANDY_GOLD_PREVIEW_COMPLETE',flush=True)
