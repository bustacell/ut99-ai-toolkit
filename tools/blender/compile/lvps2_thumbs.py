"""LVPS Vol. 2 YouTube thumbnails (copy of pipeline compile/lvps_thumbs.py with Vol. 2 frames/text) (1280x720 JPG, < 2 MB): rendered 1080p frame + crop/grade + bold outlined text.
python tools/blender/compile/lvps2_thumbs.py --root RENDER_ROOT --out OUTDIR [--fonts DIR] [--frame KEY=path.png ...] [--only KEY]"""
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

# key: frame, crop box in 1920x1080 (16:9), text lines [(text, size, colour, x, y, anchor)], tag
SPECS = {
    'rock': dict(frame='skit2/final_v1/frames/0300.png', crop=(0, 0, 1920, 1080),
                 lines=[('LETS ROCK!', 165, YEL, 610, 0, 'ma')],
                 tag='Lets Rock!'),
    'position': dict(frame='skit4/final_v1/frames/0120.png', crop=(240, 0, 1680, 810),
                     lines=[('HOLD THIS', 150, YEL, 1250, 20, 'ra'), ('POSITION', 150, WHT, 1250, 175, 'ra')],
                     tag='Hold this position.'),
    'perfection': dict(frame='skit5/final_v1/frames/0330.png', crop=(0, 0, 1920, 1080),
                       lines=[('WITNESS MY', 115, YEL, 30, 6, 'la'), ('PERFECTION', 115, WHT, 30, 128, 'la')],
                       tag='Witness my perfection.'),
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


for key, s in SPECS.items():
    if a.only and key != a.only:
        continue
    p = s['frame'] if os.path.isabs(s['frame']) else os.path.join(a.root, s['frame'])
    im = Image.open(p).convert('RGB').crop(s['crop']).resize((TW, TH), Image.LANCZOS)
    im = ImageEnhance.Contrast(ImageEnhance.Color(im).enhance(1.35)).enhance(1.15)
    im = ImageEnhance.Sharpness(im).enhance(1.4).convert('RGBA')
    # vignette for text contrast
    vg = Image.new('L', (TW, TH), 0)
    ImageDraw.Draw(vg).ellipse((-TW * 0.25, -TH * 0.3, TW * 1.25, TH * 1.3), fill=255)
    vg = vg.filter(ImageFilter.GaussianBlur(120))
    dark = Image.new('RGBA', (TW, TH), (0, 0, 0, 170))
    im = Image.composite(im, Image.alpha_composite(im, dark), vg)
    for text, size, col, x, y, anc in s['lines']:
        outlined(im, (x, y), text, F('Anton-Regular.ttf', size), col, anc)
    # badge: UT99 + series
    d = ImageDraw.Draw(im)
    bf = F('RussoOne-Regular.ttf', 34)
    lab = 'UT99  \u00b7  LITERAL VOICE PACK'
    w = d.textlength(lab, font=bf)
    d.rectangle((0, TH - 70, w + 50, TH), fill=(200, 20, 20, 255))
    d.text((25, TH - 35), lab, font=bf, fill=WHT, anchor='lm')
    out = os.path.join(a.out, f'thumb_{key}_1280x720.jpg')
    im.convert('RGB').save(out, quality=90, optimize=True, progressive=True)
    print(out, os.path.getsize(out) // 1024, 'KB')
