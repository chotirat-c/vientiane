import bpy
s = bpy.context.scene
s.render.resolution_x = 700
s.render.resolution_y = 700
s.render.resolution_percentage = 100
s.cycles.samples = 16
s.cycles.use_denoising = True
s.render.image_settings.file_format = 'PNG'
s.render.filepath = 'C:/Users/mikasaloli/Documents/Codex/2026-09-05/ho/outputs/topotutorial_end_preview.png'
bpy.ops.render.render(write_still=True)
