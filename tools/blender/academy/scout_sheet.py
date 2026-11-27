"""Contact sheet from scout renders: python scout_sheet.py OUTDIR"""
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from assetpaths import find_font  # noqa: E402

d = sys.argv[1]
info = json.load(open(os.path.join(d, 'spots.json')))
cols = 5
w, h = 480, 270
rows = (len(info) + cols - 1) // cols
sheet = Image.new('RGB', (cols * w, rows * h), 'black')
_font_file = find_font('arialbd.ttf', 'DejaVuSans-Bold.ttf')
font = ImageFont.truetype(_font_file, 15) if _font_file else ImageFont.load_default()
for n, i in enumerate(info):
    p = os.path.join(d, f"{i['name']}.png")
    if not os.path.exists(p):
        continue
    im = Image.open(p).convert('RGB')
    dr = ImageDraw.Draw(im)
    txt = f"{i['name']}  open {i['free_avg']:.0f}m min {i['free_min']:.1f} ceil {i['ceiling']:.0f}"
    dr.rectangle((0, 0, w, 20), fill=(0, 0, 0))
    dr.text((4, 2), txt, font=font, fill=(255, 230, 0))
    sheet.paste(im, ((n % cols) * w, (n // cols) * h))
sheet.save(os.path.join(d, 'sheet.jpg'), quality=85)
print(os.path.join(d, 'sheet.jpg'))
