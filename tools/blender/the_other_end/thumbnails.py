"""Make three 16:9 thumbnail treatments from the rendered teaser plates."""
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFont

from paths import WORK, assetpaths


WIDTH, HEIGHT = 1920, 1080
X = np.arange(WIDTH)[None, :]
Y = np.arange(HEIGHT)[:, None]
GOLD = (240, 180, 96)
MINT = (159, 220, 188)
ICE = (157, 214, 242)
BONE = (243, 241, 223)


def font(size, condensed=True):
    fonts = Path(assetpaths.FONTS)
    preferred = fonts / ('ArialNovaCond-Bold.ttf' if condensed else 'ArialNova-Bold.ttf')
    return ImageFont.truetype(str(preferred if preferred.exists() else fonts / 'arialbd.ttf'), size)


def blend(image, color, opacity):
    values = np.broadcast_to(np.clip(opacity * 255, 0, 255), (HEIGHT, WIDTH))
    return Image.composite(Image.new('RGB', image.size, color), image, Image.fromarray(values.astype(np.uint8)))


def grade(image, tint, amount, brightness):
    image = ImageEnhance.Contrast(image).enhance(1.15)
    image = ImageEnhance.Color(image).enhance(1.08)
    image = ImageEnhance.Brightness(image).enhance(brightness)
    return Image.blend(image, Image.new('RGB', image.size, tint), amount)


def plate(frame, center, anchor, zoom=1, scene=None):
    directory = WORK / 'montage' / scene if scene else WORK
    with Image.open(directory / 'frames' / f'{frame:04}.png') as source:
        image = source.convert('RGB').resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)
    x = center[0] - anchor[0] / zoom
    y = center[1] - anchor[1] / zoom
    return image.transform((WIDTH, HEIGHT), Image.Transform.AFFINE,
                           (1 / zoom, 0, x, 0, 1 / zoom, y),
                           Image.Resampling.BICUBIC, fillcolor=(9, 16, 17))


def tracking(draw, text, position, face, spacing, fill, centered=False):
    advance = [draw.textlength(letter, font=face) + spacing for letter in text]
    x, y = position
    if centered:
        x -= (sum(advance) - spacing) / 2
    for letter, width in zip(text, advance):
        draw.text((round(x), y), letter, font=face, fill=fill, anchor='lt')
        x += width


def large(draw, text, position, size, fill=BONE, centered=False):
    draw.text((position[0] + 4, position[1] + 8), text, font=font(size), fill=(10, 14, 16),
              anchor='mt' if centered else 'lt', stroke_width=4)
    draw.text(position, text, font=font(size), fill=fill, anchor='mt' if centered else 'lt')


def brand(draw, x, y, color):
    draw.rectangle((x, y, x+58, y+3), fill=color)
    tracking(draw, 'UNREAL TOURNAMENT ’99', (x, y+22), font(36), 4, BONE)


def faceoff():
    brock = grade(plate(70, (936, 378), (500, 356), 1.62), (103, 51, 25), .05, 1.20)
    xan = grade(plate(143, (957, 205), (1475, 315), 1.90), (22, 73, 59), .09, 1.23)
    seam = 1090 - .24 * Y
    mask = np.clip((seam - X) / 99 + .5, 0, 1)
    image = Image.composite(brock, xan, Image.fromarray((mask * 255).astype(np.uint8)))
    image = blend(image, (10, 12, 13), .90 * np.clip((Y - 560) / 470, 0, 1))
    image = blend(image, (10, 12, 13), .54 * np.clip((245 - Y) / 245, 0, 1))
    draw = ImageDraw.Draw(image)
    brand(draw, 94, 71, GOLD)
    draw.line((281, 826, 1639, 826), fill=(143, 114, 72), width=2)
    large(draw, 'BROCK', (672, 854), 147, centered=True)
    large(draw, 'XAN', (1288, 854), 147, centered=True)
    large(draw, 'VS', (1000, 894), 73, GOLD, centered=True)
    return image


def translocator():
    image = grade(plate(381, (1030, 440), (1440, 470), 1.12), (24, 59, 84), .09, 1.14)
    image = blend(image, (8, 13, 23), np.clip((1210 - X) / 855, 0, 1))
    image = blend(image, (8, 13, 23), .39 * np.clip((Y - 780) / 300, 0, 1))
    draw = ImageDraw.Draw(image)
    brand(draw, 108, 84, ICE)
    large(draw, 'ONE WAY', (105, 375), 171)
    large(draw, 'OUT', (100, 553), 244, ICE)
    tracking(draw, 'THE OTHER END', (112, 878), font(43), 6, BONE)
    return image


def worlds():
    image = grade(plate(11, (960, 540), (960, 540), scene='face'), (34, 48, 79), .08, 1.28)
    image = blend(image, (7, 13, 25), .88 * np.clip((Y - 680) / 360, 0, 1))
    draw = ImageDraw.Draw(image)
    brand(draw, 94, 66, MINT)
    large(draw, 'THE TOURNAMENT', (960, 762), 113, centered=True)
    large(draw, 'NEVER ENDS', (960, 891), 136, ICE, centered=True)
    return image


def export():
    destination = WORK / 'youtube'
    destination.mkdir(parents=True, exist_ok=True)
    for name, make_image in (('01-brock-vs-xan', faceoff), ('02-one-way-out', translocator), ('03-the-tournament-never-ends', worlds)):
        path = destination / f'{name}.jpg'
        image = make_image()
        for quality in (94, 88, 82):
            image.save(path, quality=quality, optimize=True, subsampling=0)
            if path.stat().st_size < 2_000_000:
                break
        else:
            raise ValueError(f'{path.name} exceeds the 2 MB mobile upload limit')
        print(path)


if __name__ == '__main__':
    export()
