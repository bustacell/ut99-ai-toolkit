r"""HEAD SHOT: three "nostalgic" thumbnails (1920x1080 JPG, plus 1280x720 copies).

  python hs_thumbs.py WORK OUT_PREFIX

Sources are frames of the rendered clips (CLIP, seconds), set in WORK\thumbs.json (example:
docs/examples/headshot/thumbs.json; "now" may add zoom, dx, dy to reframe). Looks: CRT scanlines, chroma split, vignette, 2000s frag-movie
type (Impact), the red in-game "Head Shot!!" message, VHS/REC furniture. No game logos.
"""
import datetime
import io
import math
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageFont

W, H = 1920, 1080
RED = (232, 24, 30)
GOLD = (255, 206, 60)


def frame(clip, t):
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", f"{t:.3f}", "-i", clip, "-frames:v", "1",
           "-vf", f"scale={W}:{H}:flags=lanczos", "-f", "image2pipe", "-vcodec", "png", "-"]
    return Image.open(io.BytesIO(subprocess.run(cmd, capture_output=True).stdout)).convert("RGB")


def font(name, size):
    return ImageFont.truetype(name, size)


def crt(img, strength=0.22, split=3):
    """scanlines + horizontal chroma split + vignette"""
    a = np.asarray(img).astype(np.float32)
    r = np.roll(a[..., 0], split, axis=1)
    b = np.roll(a[..., 2], -split, axis=1)
    a = np.stack([r, a[..., 1], b], -1)
    y = np.arange(H)[:, None, None]
    a *= 1 - strength * (0.5 + 0.5 * np.sin(y * math.pi / 2))
    yy, xx = np.mgrid[0:H, 0:W]
    d = np.hypot((xx - W / 2) / (W / 2), (yy - H / 2) / (H / 2))
    a *= np.clip(1.12 - 0.42 * d ** 2.2, 0, 1.12)[..., None]
    return Image.fromarray(a.clip(0, 255).astype(np.uint8))


def outlined(img, xy, text, f, fill, outline=(0, 0, 0), ow=8, anchor="ls", shadow=(10, 10)):
    d = ImageDraw.Draw(img)
    if shadow:
        d.text((xy[0] + shadow[0], xy[1] + shadow[1]), text, font=f, fill=(0, 0, 0), anchor=anchor, stroke_width=ow, stroke_fill=(0, 0, 0))
    d.text(xy, text, font=f, fill=fill, anchor=anchor, stroke_width=ow, stroke_fill=outline)


def glow_text(img, xy, text, f, fill, glow, radius=18, anchor="ls", ow=6):
    lay = Image.new("RGB", img.size, (0, 0, 0))
    ImageDraw.Draw(lay).text(xy, text, font=f, fill=glow, anchor=anchor, stroke_width=ow + 6, stroke_fill=glow)
    lay = lay.filter(ImageFilter.GaussianBlur(radius))
    img = ImageChops.add(img, lay)
    outlined(img, xy, text, f, fill, ow=ow, anchor=anchor, shadow=None)
    return img


def speaker(d, x, y, s, col):
    d.polygon([(x, y - s * 0.28), (x + s * 0.3, y - s * 0.28), (x + s * 0.62, y - s * 0.6), (x + s * 0.62, y + s * 0.6),
               (x + s * 0.3, y + s * 0.28), (x, y + s * 0.28)], fill=col, outline=(0, 0, 0), width=5)
    for i, r in enumerate((0.5, 0.85, 1.2)):
        bb = [x + s * 0.55 - s * r, y - s * r, x + s * 0.55 + s * r, y + s * r]
        d.arc(bb, -38, 38, fill=(0, 0, 0), width=int(s * 0.16) + 8)
        d.arc(bb, -38, 38, fill=col, width=int(s * 0.16))


def rec(d, text_left, text_right):
    f = font("consolab.ttf", 44)
    d.ellipse([60, 54, 96, 90], fill=RED, outline=(0, 0, 0), width=3)
    d.text((112, 92), text_left, font=f, fill=(255, 255, 255), anchor="ls", stroke_width=3, stroke_fill=(0, 0, 0))
    d.text((W - 60, 92), text_right, font=f, fill=(255, 255, 255), anchor="rs", stroke_width=3, stroke_fill=(0, 0, 0))


def thumb_hear(work, src, out):
    """the announcer: 'you can hear this image'"""
    img = frame(os.path.join(work, src[0]), src[1])
    img = ImageEnhance.Color(img).enhance(1.25)
    img = ImageEnhance.Contrast(img).enhance(1.12)
    img = crt(img, 0.16, 4)
    img = glow_text(img, (W // 2, 880), "HEAD SHOT!!", font("impact.ttf", 300), RED, (150, 0, 0), 26, "ms", 10)
    d = ImageDraw.Draw(img)
    f = font("impact.ttf", 96)
    speaker(d, 150, 170, 120, (255, 255, 255))
    outlined(img, (420, 205), "YOU CAN HEAR THIS IMAGE", f, (255, 255, 255), ow=7, shadow=(6, 6))
    f2 = font("consolab.ttf", 46)
    d.text((W // 2, 1010), "UT99 SNIPER RIFLE  /  NOW WITH AN ACTUAL BULLET", font=f2, fill=GOLD, anchor="ms", stroke_width=4, stroke_fill=(0, 0, 0))
    img.save(out, quality=93)


def thumb_then_now(work, src_a, src_b, out):
    """1999: hitscan / now: bullet time, split screen"""
    a = frame(os.path.join(work, src_a[0]), src_a[1])
    b = frame(os.path.join(work, src_b[0]), src_b[1])
    if len(src_b) >= 5:      # [clip, t, zoom, dx, dy]: reframe so the bullet sits in the right half
        z, dx, dy = src_b[2], src_b[3], src_b[4]
        big = b.resize((int(W * z), int(H * z)), Image.LANCZOS)
        x0 = min(max(int((big.width - W) / 2 - dx), 0), big.width - W)
        y0 = min(max(int((big.height - H) / 2 - dy), 0), big.height - H)
        b = big.crop((x0, y0, x0 + W, y0 + H))
    a = ImageEnhance.Color(a).enhance(0.55)
    a = a.resize((W // 6, H // 6), Image.BILINEAR).resize((W, H), Image.NEAREST)      # chunky 1999 pixels
    a = crt(a, 0.34, 6)
    b = ImageEnhance.Color(b).enhance(1.25)
    b = crt(ImageEnhance.Contrast(b).enhance(1.1), 0.08, 2)
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).polygon([(W * 0.56, 0), (W, 0), (W, H), (W * 0.44, H)], fill=255)
    img = Image.composite(b, a, mask)
    d = ImageDraw.Draw(img)
    d.line([(W * 0.56, 0), (W * 0.44, H)], fill=(255, 255, 255), width=10)
    fi = font("impact.ttf", 150)
    outlined(img, (70, 190), "1999", fi, (255, 255, 255))
    outlined(img, (70, 300), "HITSCAN. 0.000 s", font("impact.ttf", 76), (200, 200, 200), ow=6, shadow=(6, 6))
    outlined(img, (W - 70, 190), str(datetime.date.today().year), fi, GOLD, anchor="rs")
    outlined(img, (W - 70, 300), "BULLET TIME", font("impact.ttf", 76), GOLD, ow=6, anchor="rs", shadow=(6, 6))
    img = glow_text(img, (W // 2, 990), "HEAD SHOT!!", font("impact.ttf", 250), RED, (150, 0, 0), 24, "ms", 10)
    img.save(out, quality=93)


def thumb_macro(work, src, out, big, small):
    """bullet close-up, tape look"""
    img = frame(os.path.join(work, src[0]), src[1])
    img = ImageEnhance.Color(img).enhance(1.2)
    img = crt(ImageEnhance.Contrast(img).enhance(1.15), 0.18, 4)
    d = ImageDraw.Draw(img)
    rec(d, "REC  DEMO PLAYBACK", "SLOMO 0.02")
    img = glow_text(img, (80, 820), big, font("impact.ttf", 330), (255, 255, 255), (0, 120, 60), 30, "ls", 10)
    outlined(img, (86, 950), small, font("impact.ttf", 104), GOLD, ow=7, shadow=(6, 6))
    f2 = font("consolab.ttf", 46)
    ImageDraw.Draw(img).text((86, 1030), "UNREAL TOURNAMENT (1999)  /  ORIGINAL DEMO RECORDINGS", font=f2, fill=(255, 255, 255), stroke_width=4, stroke_fill=(0, 0, 0), anchor="ls")
    img.save(out, quality=93)


def main():
    work, prefix = sys.argv[1], sys.argv[2]
    import json
    cfg = json.load(open(os.path.join(work, "thumbs.json"), encoding="utf-8"))
    outs = [f"{prefix}_thumb1_hear-this.jpg", f"{prefix}_thumb2_1999-vs-now.jpg", f"{prefix}_thumb3_bullet.jpg"]
    thumb_hear(work, cfg["hear"], outs[0])
    thumb_then_now(work, cfg["then"], cfg["now"], outs[1])
    thumb_macro(work, cfg["macro"], outs[2], cfg["big"], cfg["small"])
    for o in outs:
        Image.open(o).resize((1280, 720), Image.LANCZOS).save(o[:-4] + "_720p.jpg", quality=92)
        print(o)


if __name__ == "__main__":
    main()
