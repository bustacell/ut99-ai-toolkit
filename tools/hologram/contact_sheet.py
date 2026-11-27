"""Contact sheet of the test frames: one row per map (build end, combo approach, combo freeze).

  python contact_sheet.py WORKDIR OUT.png
"""
import glob
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

work, out = sys.argv[1], sys.argv[2]
lineup = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "lineup.json")))
tw, th = 480, 270
rows = []
for e in lineup:
    imgs = sorted(glob.glob(os.path.join(work, e["key"], "test", "build", "*.png"))) + \
        sorted(glob.glob(os.path.join(work, e["key"], "test", "combo", "*.png")))
    rows.append((e["map"], imgs))
sheet = Image.new("RGB", (220 + 3 * tw, th * len(rows)), (12, 12, 14))
d = ImageDraw.Draw(sheet)
font = ImageFont.truetype(r"C:\Windows\Fonts\bahnschrift.ttf", 22)
for r, (name, imgs) in enumerate(rows):
    d.text((10, r * th + 10), name, fill=(240, 240, 240), font=font)
    for c, p in enumerate(imgs[:3]):
        sheet.paste(Image.open(p).convert("RGB").resize((tw, th)), (220 + c * tw, r * th))
sheet.save(out)
print("wrote", out)
