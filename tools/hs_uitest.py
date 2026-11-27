"""UI stills: python hs_uitest.py PLAN WORK OUT.jpg t1 t2 ...  (film seconds; drawn over mid grey, 4K -> half size)"""
import json, sys
from PIL import Image
import hs_assemble as A
plan = json.load(open(sys.argv[1], encoding="utf-8")); work = sys.argv[2]
segs, end = A.build_timeline(plan, work)
ui = A.UI(plan, segs, 3840, 2160)
tiles = []
for t in [float(x) for x in sys.argv[4:]]:
    bg = Image.new("RGBA", (3840, 2160), (70, 84, 78, 255))
    bg.alpha_composite(ui.frame(A.fr(t)))
    tiles.append(bg.convert("RGB").resize((960, 540), Image.LANCZOS))
cols = 2; rows = (len(tiles) + 1) // 2
sheet = Image.new("RGB", (960 * cols, 540 * rows))
for i, im in enumerate(tiles): sheet.paste(im, ((i % cols) * 960, (i // cols) * 540))
sheet.save(sys.argv[3], quality=90); print(sheet.size)
