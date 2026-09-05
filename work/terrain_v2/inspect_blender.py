"""Read-only factory-startup audit; run with Blender --background --factory-startup."""
import bpy
import json
import struct
from pathlib import Path


def font_cmap4_has(path, text):
    data = Path(path).read_bytes()
    table_count = struct.unpack_from(">H", data, 4)[0]
    tables = {}
    for index in range(table_count):
        tag, checksum, offset, size = struct.unpack_from(">4sIII", data, 12 + 16 * index)
        tables[tag] = (offset, size)
    cmap = tables[b"cmap"][0]
    subtable_count = struct.unpack_from(">H", data, cmap + 2)[0]
    for index in range(subtable_count):
        platform, encoding, relative = struct.unpack_from(">HHI", data, cmap + 4 + 8 * index)
        start = cmap + relative
        if struct.unpack_from(">H", data, start)[0] != 4:
            continue
        count = struct.unpack_from(">H", data, start + 6)[0] // 2
        ends = struct.unpack_from(">" + "H" * count, data, start + 14)
        starts = struct.unpack_from(">" + "H" * count, data, start + 16 + 2 * count)
        delta_start = start + 16 + 4 * count
        range_start = start + 16 + 6 * count
        def has(char):
            code = ord(char)
            for segment, (low, high) in enumerate(zip(starts, ends)):
                if low <= code <= high:
                    delta = struct.unpack_from(">h", data, delta_start + 2 * segment)[0]
                    offset = struct.unpack_from(">H", data, range_start + 2 * segment)[0]
                    if offset == 0:
                        glyph = (code + delta) & 65535
                    else:
                        glyph = struct.unpack_from(">H", data, range_start + 2 * segment + offset + 2 * (code-low))[0]
                        if glyph:
                            glyph = (glyph + delta) & 65535
                    return bool(glyph)
            return False
        missing = [char for char in set(text) if not has(char)]
        if not missing:
            return {"all_sample_glyphs": True, "missing": []}
    return {"all_sample_glyphs": False, "missing": missing}


prefs = bpy.context.preferences.addons["cycles"].preferences
prefs.compute_device_type = "HIP"
prefs.refresh_devices()
sample = "ສາທາລະນະລັດ ປະຊາທິປະໄຕ ປະຊາຊົນລາວ"
result = {
    "version": bpy.app.version_string,
    "devices": [{"name": device.name, "type": device.type, "use": device.use} for device in prefs.devices],
    "settings": {name: getattr(bpy.context.scene.cycles, name, None) for name in ["samples", "adaptive_threshold", "use_adaptive_sampling", "use_denoising", "denoiser", "use_auto_tile", "tile_size", "max_bounces", "diffuse_bounces", "glossy_bounces", "transmission_bounces", "transparent_max_bounces"]},
    "fonts": {name: font_cmap4_has("C:/Windows/Fonts/" + name, sample) for name in ["LeelawUI.ttf", "LeelUIsl.ttf", "leelawad.ttf", "segoeui.ttf", "arial.ttf", "bahnschrift.ttf"]},
}
print("TERRAIN_AUDIT=" + json.dumps(result, ensure_ascii=True))
