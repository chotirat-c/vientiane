import bpy
from pathlib import Path

OUT = Path(__file__).resolve().parents[1]/'outputs'/'laos'/'sandy-gold-terraces'
OUT.mkdir(parents=True, exist_ok=True)
s = bpy.context.scene
s.render.resolution_x = 700
s.render.resolution_y = 700
s.render.resolution_percentage = 100
s.cycles.samples = 16
s.cycles.use_denoising = True
s.render.image_settings.file_format = 'PNG'
s.render.filepath = str(OUT/'topotutorial_end_preview.png')
bpy.ops.render.render(write_still=True)
