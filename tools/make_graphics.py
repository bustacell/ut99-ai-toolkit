"""Frag-movie graphics for UT99 Demo Director (transparent 1920x1080 PNG overlays).

  python -I make_graphics.py lowerthird OUT.png --title "MEGA KILL" --sub "2on2 Crates 2022" [--chip "4 KILLS"]
  python -I make_graphics.py title OUT.png --name YOURNICK --top "UNREAL TOURNAMENT" --bottom "COMBOGIB  BEST OF"
  python -I make_graphics.py outro OUT.png --name YOURNICK --bottom "THANKS FOR WATCHING"

Style: dark angled glass panel, shock-purple accent, Bahnschrift with wide tracking, soft glow.
"""
import argparse
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1920, 1080
FONT = r"C:\Windows\Fonts\bahnschrift.ttf"
ACCENT = (150, 95, 255)       # shock purple
ACCENT2 = (225, 140, 255)     # light purple
TEXT = (255, 255, 255)
SUB = (205, 198, 255)


def font(size, style):
    f = ImageFont.truetype(FONT, size)
    f.set_variation_by_name(style)
    return f


def text_width(f, s, tracking):
    if not s:
        return 0
    return sum(f.getlength(c) for c in s) + tracking * (len(s) - 1)


def draw_tracked(d, xy, s, f, fill, tracking):
    x, y = xy
    for c in s:
        d.text((x, y), c, font=f, fill=fill)
        x += f.getlength(c) + tracking


def glow_text(base, xy, s, f, tracking, color, glow, radius=14):
    """Text with a soft colored glow behind it."""
    g = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw_tracked(ImageDraw.Draw(g), xy, s, f, glow + (255,), tracking)
    g = g.filter(ImageFilter.GaussianBlur(radius))
    base.alpha_composite(g)
    base.alpha_composite(g)  # stronger glow
    draw_tracked(ImageDraw.Draw(base), xy, s, f, color + (255,), tracking)


def gradient_panel(w, h, skew, alpha_left=185, alpha_right=0):
    """Angled dark panel fading to transparent on the right."""
    panel = Image.new("RGBA", (w + skew, h), (0, 0, 0, 0))
    grad = Image.new("L", (w + skew, 1))
    for x in range(w + skew):
        t = x / (w + skew)
        a = alpha_left if t < 0.55 else int(alpha_left + (alpha_right - alpha_left) * ((t - 0.55) / 0.45) ** 1.3)
        grad.putpixel((x, 0), max(0, a))
    grad = grad.resize((w + skew, h))
    mask = Image.new("L", (w + skew, h), 0)
    ImageDraw.Draw(mask).polygon([(skew, 0), (w + skew, 0), (w, h), (0, h)], fill=255)
    alpha = Image.composite(grad, Image.new("L", grad.size, 0), mask)
    fill = Image.new("RGBA", panel.size, (12, 8, 28, 255))
    fill.putalpha(alpha)
    return fill


def accent_bar(h, skew, width=12):
    bar = Image.new("RGBA", (width + skew, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(bar)
    for y in range(h):
        t = y / max(1, h - 1)
        c = tuple(int(ACCENT2[i] + (ACCENT[i] - ACCENT2[i]) * t) for i in range(3))
        off = int(skew * (1 - t))
        d.line([(off, y), (off + width, y)], fill=c + (255,))
    return bar


def lowerthird(out, title, sub, chip):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ft = font(92, "Bold Condensed")
    fs = font(30, "SemiLight SemiCondensed")
    fc = font(30, "Bold SemiCondensed")
    t_track, s_track = 3, 7
    tw = text_width(ft, title, t_track)
    sw = text_width(fs, sub.upper(), s_track)
    cw = (text_width(fc, chip, 3) + 36) if chip else 0
    pw = int(max(tw + (cw + 30 if chip else 0), sw) + 190)
    ph = 168
    x0, y0, skew = 70, 742, 34
    img.alpha_composite(gradient_panel(pw, ph, skew), (x0, y0))
    img.alpha_composite(accent_bar(ph, skew), (x0 - 6, y0))
    tx = x0 + 52
    glow_text(img, (tx, y0 + 10), title, ft, t_track, TEXT, ACCENT, radius=16)
    d = ImageDraw.Draw(img)
    # thin divider + subtitle
    d.line([(tx + 2, y0 + 118), (tx + 2 + 46, y0 + 118)], fill=ACCENT2 + (255,), width=3)
    draw_tracked(d, (tx + 62, y0 + 102), sub.upper(), fs, SUB + (255,), s_track)
    if chip:
        cx = tx + int(tw) + 30
        cy = y0 + 38
        chh = 46
        d.rounded_rectangle([cx, cy, cx + cw, cy + chh], radius=6, fill=ACCENT + (235,))
        draw_tracked(d, (cx + 18, cy + 6), chip, fc, (255, 255, 255, 255), 3)
    img.save(out)


def centered(img, y, s, f, tracking, color, glow=None, radius=18):
    x = (W - text_width(f, s, tracking)) / 2
    if glow:
        glow_text(img, (x, y), s, f, tracking, color, glow, radius)
    else:
        draw_tracked(ImageDraw.Draw(img), (x, y), s, f, color + (255,), tracking)
    return x


def vignette(img, strength=200):
    v = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(v)
    for i in range(60):
        a = int(strength * (i / 60) ** 2)
        d.rectangle([i * 8, i * 4.5, W - i * 8, H - i * 4.5], outline=255 - a)
    v = v.filter(ImageFilter.GaussianBlur(60))
    dark = Image.new("RGBA", (W, H), (5, 3, 15, 0))
    dark.putalpha(Image.eval(v, lambda p: 255 - p))
    img.alpha_composite(dark)


def titlecard(out, name, top, bottom):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    vignette(img, 230)
    # center band
    band = Image.new("RGBA", (W, 330), (10, 6, 24, 150))
    img.alpha_composite(band, (0, 375))
    d = ImageDraw.Draw(img)
    d.line([(0, 375), (W, 375)], fill=ACCENT + (180,), width=2)
    d.line([(0, 704), (W, 704)], fill=ACCENT + (180,), width=2)
    centered(img, 400, top, font(34, "SemiLight SemiCondensed"), 14, SUB)
    centered(img, 440, name, font(190, "Bold Condensed"), 18, TEXT, glow=ACCENT, radius=26)
    fb = font(36, "SemiBold SemiCondensed")
    x = centered(img, 645, bottom, fb, 12, ACCENT2)
    bw = text_width(fb, bottom, 12)
    d = ImageDraw.Draw(img)
    d.line([(x - 130, 668), (x - 30, 668)], fill=ACCENT2 + (255,), width=3)
    d.line([(x + bw + 30, 668), (x + bw + 130, 668)], fill=ACCENT2 + (255,), width=3)
    img.save(out)


def outrocard(out, name, bottom):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    vignette(img, 240)
    centered(img, 430, name, font(150, "Bold Condensed"), 16, TEXT, glow=ACCENT, radius=24)
    centered(img, 610, bottom, font(34, "SemiLight SemiCondensed"), 14, SUB)
    img.save(out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("kind", choices=["lowerthird", "title", "outro"])
    ap.add_argument("out")
    ap.add_argument("--title", default="")
    ap.add_argument("--sub", default="")
    ap.add_argument("--chip", default="")
    ap.add_argument("--name", default="PLAYER")
    ap.add_argument("--top", default="UNREAL TOURNAMENT")
    ap.add_argument("--bottom", default="COMBOGIB  BEST OF")
    a = ap.parse_args()
    if a.kind == "lowerthird":
        lowerthird(a.out, a.title, a.sub, a.chip)
    elif a.kind == "title":
        titlecard(a.out, a.name, a.top, a.bottom)
    else:
        outrocard(a.out, a.name, a.bottom)
