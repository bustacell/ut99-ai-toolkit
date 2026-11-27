r"""Three MINIATURES thumbnails from the rendered take, type in the film's museum style (Georgia Pro).

  python mini_thumbs.py
-> output\miniatures_thumb1_museum.jpg, _thumb2_lava.jpg, _thumb3_to-scale.jpg (1280x720) + _4k.jpg (3840x2160).
Design coordinates are 1920x1080 (mini_type K=2 draws them at 4K).
"""
import os

from PIL import Image, ImageEnhance, ImageDraw, ImageFilter

import mini_type as T

from paths import FRAMES as SRC, OUT  # noqa: E402
W, H = 3840, 2160


def base(frame, lift=1.15, con=1.08, vig=0.55, zoom=1.0):
    im = Image.open(os.path.join(SRC, f'{frame:04d}.png')).convert('RGB')
    if zoom > 1:                                         # crop towards the bottom centre (drops the backdrop edge)
        w, h = im.size
        cw, ch = w / zoom, h / zoom
        im = im.crop(((w - cw) / 2, h - ch, (w + cw) / 2, h))
    im = im.resize((W, H), Image.LANCZOS)
    im = im.filter(ImageFilter.UnsharpMask(radius=2, percent=35, threshold=2))
    im = ImageEnhance.Contrast(ImageEnhance.Brightness(im).enhance(lift)).enhance(con)
    # soft vignette so the type sits on dark
    m = Image.new('L', (W // 8, H // 8), 0)
    d = ImageDraw.Draw(m)
    d.ellipse((-W // 40, -H // 30, W // 8 + W // 40, H // 8 + H // 30), fill=255)
    m = m.filter(ImageFilter.GaussianBlur(W // 60)).resize((W, H), Image.BICUBIC)
    dark = Image.new('RGB', (W, H), (0, 0, 0))
    im = Image.composite(im, Image.blend(dark, im, 1 - vig), m)
    return im.convert('RGBA')


def save(im, name):
    rgb = im.convert('RGB')
    rgb.save(os.path.join(OUT, f'miniatures_{name}_4k.jpg'), quality=93)
    rgb.resize((1280, 720), Image.LANCZOS).save(os.path.join(OUT, f'miniatures_{name}.jpg'), quality=92)
    print(name)


def label(fr, x, y, no, name, mode, scale, size=150):
    """Big museum card: number, name, hairline, mode, scale."""
    T.put(fr, f'No. {no:02d}', 'lightit', size * 0.36, T.BRASS, x, y - size * 0.62)
    w = T.put(fr, name, 'light', size, T.IVORY, x - 6, y)
    T.hair(fr, x, x + max(420, w * 0.62), y + size * 1.2, wgt=3)
    T.put(fr, mode, 'reg', size * 0.2, T.MUTED, x, y + size * 1.42, track=0.22)
    T.put(fr, f'Model scale 1 : {scale}', 'lightit', size * 0.32, T.BRASS, x, y + size * 1.72)


def main():
    T.set_k(2)
    # 1. the museum: CTF-Face's towers on their rods, the film title above
    fr = base(3830, zoom=1.16)
    T.put(fr, 'MINIATURES', 'light', 112, T.IVORY, 90, 790, track=0.12)
    T.hair(fr, 92, 92 + 420, 940, wgt=3)
    T.put(fr, 'UNREAL TOURNAMENT, BUILT SMALL', 'reg', 24, T.MUTED, 92, 968, track=0.3)
    save(fr, 'thumb1_museum')

    # 2. LavaGiant as an exhibit: the lava glows inside the model, the card names it
    fr = base(4330, lift=1.1)
    label(fr, 90, 130, 9, 'LavaGiant', 'CAPTURE THE FLAG', 270, size=140)
    save(fr, 'thumb2_lava')

    # 3. to scale: every arena in one row
    fr = base(4950, lift=1.2, vig=0.35)
    T.put(fr, 'TO SCALE', 'light', 170, T.IVORY, 1840, 120, track=0.14, align='right')
    T.hair(fr, 1840 - 520, 1840, 330, wgt=3)
    T.put(fr, 'Nine UT99 arenas, side by side', 'lightit', 54, T.BRASS, 1840, 362, align='right')
    save(fr, 'thumb3_to-scale')


if __name__ == '__main__':
    main()
