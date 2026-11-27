"""LVPS Vol. 3 YouTube thumbnails (adapted from vol2/tools/lvps2_thumbs.py; Vol. 2 untouched).
1280x720 JPG, < 2 MB: rendered 1080p frame + crop/grade + bold outlined text.
python3 lvps3_thumbs.py --root RENDER_ROOT --out OUTDIR [--fonts DIR] [--frame KEY=path.png ...] [--only KEY]
"""
import argparse
import glob
import os

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

ap = argparse.ArgumentParser()
ap.add_argument('--root', required=True)
ap.add_argument('--out', required=True)
ap.add_argument('--fonts', default=os.environ.get('LVPS_FONTS', '/usr/share/fonts'))
ap.add_argument('--frame', action='append', default=[])
ap.add_argument('--only', default=None)
a = ap.parse_args()
os.makedirs(a.out, exist_ok=True)
TW, TH = 1280, 720
YEL, WHT, RED = (255, 214, 0), (255, 255, 255), (230, 30, 30)

# Episode options (pitch A/C recommended, B backup) plus per-skit thumbs for Next and Cover me.
# Names are game strings; no bot names drawn on the thumbs (only the line + series badge).
SPECS = {
    'tag': dict(frame='skit1/final_v1/frames/0135.png', crop=(0, 0, 1920, 1080),
                lines=[("TAG, YOU'RE IT!", 110, YEL, 640, 8, 'ma')],
                tag="Tag, you're it!"),
    'fire': dict(frame='skit2/final_v1/frames/0135.png', crop=(200, 0, 1720, 855),
                 lines=[("I'M ON FIRE!", 140, YEL, 640, 8, 'ma')],
                 tag="I'm on fire!"),
    'next': dict(frame='skit3/final_v1/frames/0198.png', crop=(0, 0, 1920, 1080),
                 lines=[('NEXT!', 180, YEL, 40, 8, 'la')],
                 tag='Next!'),
    'cover': dict(frame='skit4/final_v1/frames/0330.png', crop=(240, 80, 1680, 890),
                  lines=[('COVER ME.', 140, YEL, 40, 8, 'la')],
                  tag='Cover me.'),
    'bow': dict(frame='skit5/final_v1/frames/0228.png', crop=(160, 40, 1760, 940),
                lines=[('BOW DOWN!', 160, YEL, 640, 8, 'ma')],
                tag='Bow down!'),
}
for o in a.frame:
    k, p = o.split('=', 1)
    SPECS[k]['frame'] = p
_fc = {}


def F(name, size):
    if name not in _fc:
        hits = glob.glob(os.path.join(a.fonts, '**', name), recursive=True)
        if not hits:
            raise SystemExit('font not found: ' + name)
        _fc[name] = hits[0]
    return ImageFont.truetype(_fc[name], size)


def outlined(im, xy, text, font, fill, anchor, stroke=14):
    sh = Image.new('RGBA', im.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).text((xy[0] + 10, xy[1] + 12), text, font=font, fill=(0, 0, 0, 200), anchor=anchor, stroke_width=stroke, stroke_fill=(0, 0, 0, 200))
    im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(8)))
    ImageDraw.Draw(im).text(xy, text, font=font, fill=fill, anchor=anchor, stroke_width=stroke, stroke_fill=(0, 0, 0))


written = []
for key, s in SPECS.items():
    if a.only and key != a.only:
        continue
    p = s['frame'] if os.path.isabs(s['frame']) else os.path.join(a.root, s['frame'])
    im = Image.open(p).convert('RGB').crop(s['crop']).resize((TW, TH), Image.LANCZOS)
    im = ImageEnhance.Contrast(ImageEnhance.Color(im).enhance(1.35)).enhance(1.15)
    im = ImageEnhance.Sharpness(im).enhance(1.4).convert('RGBA')
    vg = Image.new('L', (TW, TH), 0)
    ImageDraw.Draw(vg).ellipse((-TW * 0.25, -TH * 0.3, TW * 1.25, TH * 1.3), fill=255)
    vg = vg.filter(ImageFilter.GaussianBlur(120))
    dark = Image.new('RGBA', (TW, TH), (0, 0, 0, 170))
    im = Image.composite(im, Image.alpha_composite(im, dark), vg)
    for text, size, col, x, y, anc in s['lines']:
        outlined(im, (x, y), text, F('Anton-Regular.ttf', size), col, anc)
    d = ImageDraw.Draw(im)
    bf = F('RussoOne-Regular.ttf', 34)
    lab = 'UT99  \u00b7  LITERAL VOICE PACK'
    w = d.textlength(lab, font=bf)
    d.rectangle((0, TH - 70, w + 50, TH), fill=(200, 20, 20, 255))
    d.text((25, TH - 35), lab, font=bf, fill=WHT, anchor='lm')
    out = os.path.join(a.out, f'thumb_{key}_1280x720.jpg')
    im.convert('RGB').save(out, quality=90, optimize=True, progressive=True)
    written.append(out)
    print(out, os.path.getsize(out) // 1024, 'KB')

# overview contact, like Vol. 2's thumbs_overview.png
if written and not a.only:
    cols = min(3, len(written))
    rows = (len(written) + cols - 1) // cols
    sheet = Image.new('RGB', (TW * cols, TH * rows), (20, 20, 20))
    for i, p in enumerate(written):
        sheet.paste(Image.open(p).convert('RGB'), ((i % cols) * TW, (i // cols) * TH))
    ov = os.path.join(a.out, 'thumbs_overview.png')
    sheet.save(ov)
    print(ov)
