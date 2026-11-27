"""Hand-lettered blood marks for the Deck16 pool wall.

The word comes from UTDD_TAG (default "clueless"); only the letters in LETTERS below are drawn: b u s t a c e l.
"""
import math
import os
import random

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from paths import WORK as ROOT
SIZE = (1536, 480)

# Each stroke starts with a point, followed by cubic Bezier handles and ends.
LETTERS = {
    'b': (.93, [((.29,.18),(.22,.72,.16,1.43,.13,2.06)),
                ((.20,1.30),(.62,.96,1.00,1.19,.91,1.59),(.86,1.95,.49,2.21,.13,2.06))]),
    'u': (.91, [((.16,1.03),(.02,1.44,.02,2.15,.36,2.10),(.64,2.05,.77,1.53,.82,1.03)),
                ((.82,1.03),(.76,1.46,.66,1.92,.86,2.06))]),
    's': (.83, [((.75,1.14),(.52,.91,.14,1.11,.14,1.40),(.16,1.64,.71,1.52,.69,1.81),(.66,2.12,.30,2.24,.06,2.02))]),
    't': (.64, [((.37,.49),(.30,.95,.07,1.86,.34,2.07),(.44,2.14,.58,2.06,.65,1.99)),
                ((.03,1.14),(.21,1.08,.45,1.01,.63,1.03))]),
    'a': (.91, [((.73,1.16),(.49,.92,.12,1.24,.09,1.65),(.05,2.02,.28,2.21,.55,1.96),(.71,1.81,.78,1.38,.81,1.09)),
                ((.81,1.09),(.75,1.55,.68,1.90,.87,2.07))]),
    'c': (.84, [((.75,1.16),(.53,.91,.14,1.24,.09,1.67),(.04,2.08,.44,2.23,.75,1.99))]),
    'e': (.88, [((.12,1.61),(.34,1.65,.80,1.40,.73,1.20),(.61,.92,.19,1.19,.09,1.61),(.01,2.04,.37,2.22,.78,1.95))]),
    'l': (.50, [((.12,1.60),(.38,1.12,.61,.40,.39,.25),(.12,.22,.02,1.36,.10,1.87),(.15,2.17,.36,2.18,.51,1.94))]),
}
TAG = os.environ.get('UTDD_TAG', 'clueless').lower()
if not TAG or any(c not in LETTERS for c in TAG):
    raise SystemExit(f'UTDD_TAG may only use the letters {"".join(LETTERS)}')


def path_points(stroke, scale=1):
    start = np.array(stroke[0], dtype=float)
    points = [start]
    for segment in stroke[1:]:
        a, b, end = np.array(segment, dtype=float).reshape(3, 2)
        length = sum(np.linalg.norm(delta) for delta in (a-start, b-a, end-b))
        samples = max(25, math.ceil(length * scale / 2.6))
        for t in np.linspace(0, 1, samples)[1:]:
            points.append((1-t)**3*start+3*(1-t)**2*t*a+3*(1-t)*t*t*b+t**3*end)
        start = end
    return points


def brush(draw, points, width, opacity):
    for i, point in enumerate(points):
        phase = i/max(1,len(points)-1)
        taper = min(1, .54+phase*8, .20+(1-phase)*6)
        pressure = .92 + .14*math.sin(phase*math.pi*1.15) + .05*math.sin(phase*10)
        radius = width*pressure*taper*.5
        x,y=point
        draw.ellipse((x-radius,y-radius,x+radius,y+radius),fill=opacity)


def paint_tag():
    main = Image.new('L',SIZE)
    ink = ImageDraw.Draw(main)
    x_offset = 0
    scale = 157
    for index, letter in enumerate(TAG):
        advance, strokes = LETTERS[letter]
        for stroke in strokes:
            points = [(140+scale*(x_offset+x+.16*(2.1-y)),
                       45+scale*(y-.028*x_offset+.036*math.sin(index*1.8)))
                      for x,y in path_points(stroke, scale)]
            brush(ink,points,24 if letter not in 'tl' else 22,246)
        x_offset += advance + .08

    runs = Image.new('L', SIZE)
    draw = ImageDraw.Draw(runs)
    span = scale * x_offset / 1203.0                 # the drips were placed for a 9 letter word 1203 px wide
    for x, length, width in ((225, 56, 11), (561, 38, 8), (813, 71, 10), (1210, 46, 9)):
        x = int(140 + (x - 140) * span)
        inked = [y for y in range(SIZE[1]) if main.getpixel((x, y)) > 200]
        if not inked:
            continue
        bottom = max(inked)
        for step in range(length):
            phase = step / length
            center = x + 3 * phase**2
            y = bottom - 5 + step
            radius = width * (.5 - .38 * phase)
            draw.ellipse((center-radius, y-1, center+radius, y+1), fill=223)
        draw.ellipse((center-2, y-5, center+2, y+2), fill=239)
    brush(draw, path_points(((246,401),(591,419,1069,362,1379,350))), 11, 167)
    brush(draw, path_points(((1123,396),(1199,384,1254,382,1322,379))), 5, 129)

    canvas=Image.new('RGBA',SIZE)
    rim = main.filter(ImageFilter.MaxFilter(7))
    for mask, color in ((rim, (75,12,16)), (runs, (122,22,25)), (main, (157,30,32))):
        layer=Image.new('RGBA',SIZE,(*color,0))
        layer.putalpha(mask)
        canvas.alpha_composite(layer)
    rng=random.Random(1999)
    alpha=canvas.getchannel('A')
    draw=ImageDraw.Draw(alpha)
    for _ in range(2600):
        x=rng.randrange(SIZE[0]); y=rng.randrange(SIZE[1])
        if alpha.getpixel((x,y))>60:
            width=rng.choice((1,1,2,3,6))
            draw.ellipse((x,y,x+width,y+1),fill=rng.randrange(18,120))
    canvas.putalpha(alpha.filter(ImageFilter.GaussianBlur(.30)))
    output=ROOT/'assets'/'graffiti-tag.png'
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output)
    return output


if __name__=='__main__':
    print(paint_tag())
