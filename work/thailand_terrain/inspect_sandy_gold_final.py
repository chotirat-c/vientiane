"""Verify the full-resolution master and export small visual QA views."""
import json
import argparse
import struct
from pathlib import Path

from PIL import Image

parser = argparse.ArgumentParser()
parser.add_argument("--master", type=Path)
args = parser.parse_args()
out = Path(__file__).resolve().parents[2] / "outputs/thailand/sandy-gold-detail"
master = args.master.resolve() if args.master else out / "thailand_relief_sandy_gold_detail_8k.png"
out = master.parent
with master.open("rb") as stream:
    header = stream.read(29)
assert header[:8] == b"\x89PNG\r\n\x1a\n"
assert struct.unpack(">II", header[16:24]) == (6284, 7680)
assert header[24:26] == bytes((16, 2)), "Expected 16-bit RGB PNG"
with Image.open(master) as picture:
    picture.verify()
with Image.open(master) as picture:
    picture.load()
    is_laos = master.name.startswith("laos_")
    terrain_box = (1400, 1400, 2600, 2600) if is_laos else (1750, 1000, 2950, 2200)
    labels_box = (650, 4550, 3100, 6540) if is_laos else (3390, 4740, 5570, 6080)
    picture.crop(terrain_box).save(out / "final_qa_terrain.png")
    picture.crop(labels_box).save(out / "final_qa_typography.png")
    picture.thumbnail((1676, 2048), Image.Resampling.LANCZOS)
    picture.save(out / (master.stem + "_preview.jpg"), quality=95)
print(json.dumps({"file": str(master), "dimensions": [6284, 7680],
                  "bits_per_channel": 16, "bytes": master.stat().st_size,
                  "png_verified": True}))
