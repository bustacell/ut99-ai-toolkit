"""slomo 0 thumbnail (1280x720): a real in-engine frozen frame + the viewer's question (no name, no avatar).

  python slomo0_thumb2.py BG.png OUT.jpg --core X Y [--crop X0 Y0 X1 Y1] [--tag "0.25 S BEFORE IMPACT"]

BG is a 1920x1080 frame; --core is the shock core position in BG pixels (ring + pointer), --crop picks the region.
"""
import argparse, math
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

W, H = 1280, 720
GREEN = (150, 255, 120)


def font(names, size, var=None):
    for n in names:
        try:
            f = ImageFont.truetype(n, size)
            if var:
                try:
                    f.set_variation_by_name(var)
                except Exception:
                    f.set_variation_by_name(var.encode())
            return f
        except OSError:
            pass
    return ImageFont.load_default()


SEGOE = ["segoeui.ttf"]
IMPACT = ["impact.ttf"]
MONO_B = ["consolab.ttf"]
BAHN = ["bahnschrift.ttf"]


def grade(im):
    im = ImageEnhance.Color(im).enhance(1.25)
    im = ImageEnhance.Contrast(im).enhance(1.15)
    im = ImageEnhance.Brightness(im).enhance(1.05)
    return im


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("bg"); ap.add_argument("out")
    ap.add_argument("--core", type=float, nargs=2, required=True)
    ap.add_argument("--crop", type=float, nargs=4)
    ap.add_argument("--tag", default="0.25 S BEFORE IMPACT")
    ap.add_argument("--tag-angle", type=float, default=-40, help="pointer direction in degrees (screen, 0 = right)")
    a = ap.parse_args()
    src = Image.open(a.bg).convert("RGB")
    x0, y0, x1, y1 = a.crop or (0, 0, src.width, src.height)
    im = grade(src.crop((int(x0), int(y0), int(x1), int(y1))).resize((W, H), Image.LANCZOS)).convert("RGBA")
    sx, sy = W / (x1 - x0), H / (y1 - y0)
    cx, cy = (a.core[0] - x0) * sx, (a.core[1] - y0) * sy
    # darken the left for the text, vignette
    shade = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(shade)
    for x in range(W):
        d.line([(x, 0), (x, H)], fill=int(max(0, 175 * (1 - x / (W * 0.55)))))
    shade = shade.filter(ImageFilter.GaussianBlur(50))
    im = Image.composite(Image.new("RGBA", (W, H), (6, 2, 16, 255)), im, shade)
    vig = Image.new("L", (W, H), 0)
    ImageDraw.Draw(vig).ellipse((-W * 0.2, -H * 0.3, W * 1.2, H * 1.3), fill=255)
    im = Image.composite(im, Image.new("RGBA", (W, H), (0, 0, 0, 255)), vig.filter(ImageFilter.GaussianBlur(110)))
    # glowing ring around the core + pointer tag
    r = 62
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse((cx - r, cy - r, cx + r, cy + r), outline=(255, 235, 90, 255), width=12)
    glow = glow.filter(ImageFilter.GaussianBlur(10))
    im.alpha_composite(glow)
    d = ImageDraw.Draw(im)
    d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=(255, 240, 120, 255), width=6)
    ang = math.radians(a.tag_angle)
    p0 = (cx + r * math.cos(ang), cy + r * math.sin(ang))
    p1 = (p0[0] + 92 * math.cos(ang), p0[1] + 92 * math.sin(ang))
    d.line([p0, p1, (p1[0] + 40, p1[1])], fill=(255, 240, 120, 255), width=5)
    ft = font(BAHN, 34, "Bold SemiCondensed")
    tw = d.textlength(a.tag, font=ft)
    tx, ty = p1[0] + 50, p1[1] - 22
    d.rounded_rectangle((tx - 12, ty - 6, tx + tw + 12, ty + 44), 8, fill=(255, 240, 120, 255))
    d.text((tx, ty), a.tag, font=ft, fill=(20, 10, 30, 255))
    # question bubble (no name, no avatar)
    fq = font(SEGOE, 36)
    lines = ["couldn't you do this directly", "with demo recordings?"]
    pad, lh = 26, 46
    bw = int(max(d.textlength(t, font=fq) for t in lines) + 2 * pad)
    bh = int(len(lines) * lh + 2 * pad - 8)
    bx, by = 44, 40
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle((bx + 6, by + 12, bx + bw + 6, by + bh + 12), 22, fill=(0, 0, 0, 180))
    im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(14)))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((bx, by, bx + bw, by + bh), 22, fill=(255, 255, 255, 255))
    d.polygon([(bx + 44, by + bh - 2), (bx + 36, by + bh + 32), (bx + 88, by + bh - 2)], fill=(255, 255, 255, 255))
    for k, t in enumerate(lines):
        d.text((bx + pad, by + pad - 6 + k * lh), t, font=fq, fill=(15, 15, 15, 255))
    # YES.
    fy = font(IMPACT, 250)
    yx, yy = 48, by + bh + 26
    g = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(g).text((yx, yy), "YES.", font=fy, fill=(120, 255, 100, 210))
    im.alpha_composite(g.filter(ImageFilter.GaussianBlur(26)))
    ImageDraw.Draw(im).text((yx, yy), "YES.", font=fy, fill=GREEN + (255,), stroke_width=9, stroke_fill=(0, 0, 0, 255))
    # console line, bottom left under YES.
    fm = font(MONO_B, 46)
    d = ImageDraw.Draw(im)
    txt = "(> slomo 0_"
    tw = d.textlength(txt, font=fm)
    lx, ly = 56, H - 92
    d.rectangle((lx - 18, ly - 12, lx + tw + 18, ly + 62), fill=(12, 12, 12, 225))
    d.text((lx, ly), txt, font=fm, fill=(140, 255, 140, 255))
    im.convert("RGB").save(a.out, quality=93)
    print(a.out)


if __name__ == "__main__":
    main()
