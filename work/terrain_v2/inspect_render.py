"""Read-only verification of the master; derived previews for visual QA."""
from pathlib import Path
from PIL import Image
import struct
import argparse
preset=argparse.ArgumentParser()
preset.add_argument('--style',choices=['blue','green-paper'],default='blue')
args=preset.parse_args()
ROOT=Path(__file__).resolve().parent
OUT=ROOT.parent.parent/'outputs'
stem='laos_relief_green_paper' if args.style=='green-paper' else 'laos_relief'
p=OUT/('laos_relief_green_paper_8k.png' if args.style=='green-paper' else 'laos_relief_rebuilt_8k.png')
with p.open('rb') as f:
    h=f.read(29)
with Image.open(p) as im:
    im.verify()
print({'size':struct.unpack('>II',h[16:24]),'bits_per_channel':h[24],
       'color_type':h[25],'bytes':p.stat().st_size,'png_verified':True})
with Image.open(p) as im:
    im.crop((1700,1600,2900,2800)).save(ROOT/(stem+'_qa_terrain.png'))
    im.crop((450,6400,2900,7390)).save(ROOT/(stem+'_qa_labels.png'))
    if args.style=='green-paper':
        im.crop((250,2800,1300,3850)).save(ROOT/'green_qa_paper.png')
    im.thumbnail((1676,2048),Image.Resampling.LANCZOS)
    im.save(OUT/(stem+'_preview.jpg'),quality=94,subsampling=0)
