"""DDSpark texture set: a warm, Claude-inspired futuristic look (cream and warm-grey surfaces, charcoal floors,
terracotta/coral light). The "Spark" emblem is an own symmetric starburst design (16 tapered rays of alternating
length around a ring), not the Claude logo.

blender -b --factory-startup --python textures_spark.py -- <outdir> [name ...]
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import textures_blender as tb            # noqa: E402  (shared helpers + render setup)
from textures_blender import box, prism, bolt, material, render   # noqa: E402

CREAM = (0.50, 0.43, 0.35)
CREAM_L = (0.62, 0.55, 0.46)
WGREY = (0.17, 0.15, 0.135)
CHAR = (0.035, 0.032, 0.03)
CHAR_L = (0.075, 0.068, 0.062)
CORAL = (1.0, 0.24, 0.09)
WARMW = (1.0, 0.82, 0.62)
TEAM_RED, TEAM_BLUE = (1.0, 0.16, 0.08), (0.12, 0.42, 1.0)


def glow(name, color, emit=0.95):
    return material(name, (0.05, 0.05, 0.05), grime=0.0, emission=color, emit=emit)


def floor_dark(w, h):
    """Charcoal tiles (4x4) with fine grooves; coral inlay lines along two seams (circuit feel)."""
    base = material("fdbase", CHAR, grime=0.35, noise_seed=31)
    tile = material("fdtile", CHAR_L, grime=0.45, noise_seed=32)
    line = glow("fdline", CORAL, 0.95)
    box(-w, -h, -4, 2 * w, 2 * h, 0, base, bevel=0)
    s = w / 4
    for i in range(4):
        for j in range(4):
            box(i * s + 3, j * s + 3, 0, (i + 1) * s - 3, (j + 1) * s - 3, 5, tile, bevel=2.5)
            if (i + j) % 3 == 0:     # subtle groove pattern on some tiles
                for k in range(1, 4):
                    box(i * s + 14, j * s + k * s / 4 - 1, 5, (i + 1) * s - 14, j * s + k * s / 4 + 1, 5.4, base, bevel=0)
    box(-w, s * 2 - 2, 0, 2 * w, s * 2 + 2, 1.5, line, bevel=0)       # horizontal inlay
    box(s * 1 - 2, -h, 0, s * 1 + 2, 2 * h, 1.5, line, bevel=0)       # vertical inlay


def floor_plate(w, h):
    """Warm-grey large plates with rounded seams and small light studs."""
    gap = material("fpgap", CHAR, grime=0.0)
    plate = material("fpplate", WGREY, grime=0.45, noise_seed=33)
    stud = glow("fpstud", WARMW, 0.95)
    box(-w, -h, -4, 2 * w, 2 * h, 0, gap, bevel=0)
    half = w / 2
    for i in range(2):
        for j in range(2):
            x0, y0 = i * half + 4, j * half + 4
            box(x0, y0, 0, x0 + half - 8, y0 + half - 8, 7, plate, bevel=6)
            for bx, by in ((x0 + 18, y0 + 18), (x0 + half - 26, y0 + 18), (x0 + 18, y0 + half - 26), (x0 + half - 26, y0 + half - 26)):
                prism(bx, by, 4, 7, 8, 12, stud, bevel=0)


def wall_cream(w, h):
    """Cream wall: two tall soft panels with deep rounded seams, a slot strip and a thin coral line."""
    gap = material("wcgap", WGREY, grime=0.2, noise_seed=34)
    panel = material("wcpanel", CREAM, rough=0.8, grime=0.35, noise_seed=35)
    line = glow("wcline", CORAL, 0.95)
    box(-w, -h, -6, 2 * w, 2 * h, 0, gap, bevel=0)
    for x0 in (6, w / 2 + 6):
        box(x0, 6, 0, x0 + w / 2 - 12, h - 6, 8, panel, bevel=7)
        for k in range(5):        # small slots near the top
            box(x0 + 30 + k * 26, h - 70, 8, x0 + 44 + k * 26, h - 40, 8.6, gap, bevel=1)
    box(-w, 150, 0, 2 * w, 154, 9, line, bevel=0)


def wall_rib(w, h):
    """Vertical fins on warm grey: rhythm for long walls."""
    base = material("wrbase", WGREY, grime=0.4, noise_seed=36)
    fin = material("wrfin", CREAM_L, grime=0.3, noise_seed=37)
    box(-w, -h, -6, 2 * w, 2 * h, 0, base, bevel=0)
    for x in range(0, w, 32):
        box(x + 6, -h, 0, x + 22, 2 * h, 10, fin, bevel=3)


def wall_tech(w, h):
    """Warm-grey tech panel: soft frame, horizontal vent, recessed light slot."""
    base = material("wtbase", WGREY, grime=0.45, noise_seed=38)
    frame = material("wtframe", CREAM, grime=0.35, noise_seed=39)
    dark = material("wtdark", CHAR, grime=0.0)
    lamp = glow("wtlamp", WARMW, 0.95)
    box(-w, -h, -6, 2 * w, 2 * h, 0, base, bevel=0)
    box(6, 6, 0, w - 6, h - 6, 6, frame, bevel=6)
    box(30, 30, 6, w - 30, h - 30, 6.5, base, bevel=4)
    box(70, 260, 6.5, w - 70, 430, 7, dark, bevel=0)
    for y in range(270, 430, 16):
        box(76, y, 6.5, w - 76, y + 8, 11, frame, bevel=2.5)
    box(70, 90, 6.5, w - 70, 130, 8, dark, bevel=2)
    box(84, 100, 8, w - 84, 120, 8.5, lamp, bevel=0)


def trim(w, h):
    """Warm-grey band with a thin coral light line in a groove."""
    base = material("trbase", WGREY, grime=0.4, noise_seed=40)
    edge = material("tredge", CREAM, grime=0.3, noise_seed=41)
    line = glow("trline", CORAL, 0.95)
    box(-w, -h, -4, 2 * w, 2 * h, 0, base, bevel=0)
    box(-w, 4, 0, 2 * w, 18, 6, edge, bevel=2.5)
    box(-w, h - 18, 0, 2 * w, h - 4, 6, edge, bevel=2.5)
    box(-w, 28, 0, 2 * w, 36, 1.5, line, bevel=0)


def flow(w, h):
    """Dashes of light for the flowing 'thought lines' (panned in the map)."""
    base = material("flbase", CHAR, grime=0.0)
    line = glow("flline", CORAL, 0.95)
    soft = glow("flsoft", (0.55, 0.14, 0.07), 0.6)
    box(-w, -h, -2, 2 * w, 2 * h, 0, base, bevel=0)
    x = 0
    for L, g in ((70, 20), (18, 12), (110, 26), (8, 10)):
        box(x, h / 2 - 5, 0, x + L, h / 2 + 5, 1, line, bevel=0)
        box(x - 6, h / 2 - 9, 0, x + L + 6, h / 2 + 9, 0.5, soft, bevel=0)
        x += L + g


def light_panel(w, h):
    frame = material("lpframe", CREAM, grime=0.3, noise_seed=42)
    lamp = glow("lplamp", WARMW, 0.95)
    box(-w, -h, -4, 2 * w, 2 * h, 0, frame, bevel=0)
    box(4, 4, 0, w - 4, h - 4, 6, frame, bevel=5)
    box(18, 18, 6, w - 18, h - 18, 6.5, lamp, bevel=0)


def ceiling(w, h):
    rib = material("cerib", CREAM, grime=0.35, noise_seed=43)
    panel = material("cepanel", WGREY, grime=0.4, noise_seed=44)
    box(-w, -h, -10, 2 * w, 2 * h, 0, panel, bevel=0)
    for k in range(-1, 3):
        box(-w, k * 256 - 14, 0, 2 * w, k * 256 + 14, 16, rib, bevel=6)
        box(k * 256 - 14, -h, 0, k * 256 + 14, 2 * h, 16, rib, bevel=6)
    for i in range(2):
        for j in range(2):
            box(i * 256 + 40, j * 256 + 40, 0, i * 256 + 216, j * 256 + 216, 5, rib, bevel=10)


def pillar(w, h):
    body = material("pibody", CREAM, grime=0.35, noise_seed=45)
    band = material("piband", WGREY, grime=0.4, noise_seed=46)
    line = glow("piline", CORAL, 0.95)
    box(-w, -h, -4, 2 * w, 2 * h, 0, body, bevel=0)
    for y in (0, 128):
        box(-w, y + 4, 0, 2 * w, y + 36, 8, band, bevel=4)
        box(-w, y + 18, 8, 2 * w, y + 22, 8.5, line, bevel=0)
    for x in range(0, w, 64):
        box(x + 8, 52, 0, x + 56, 116, 4, body, bevel=4)
        box(x + 8, 180, 0, x + 56, 244, 4, body, bevel=4)


def spark_shape(cx, cy, z, mat, r_in=46, r_long=210, r_short=135, n=16, width=26, h=5):
    """Own starburst: n tapered rays (alternating long/short) starting at a ring, plus a centre node."""
    import bpy
    for k in range(n):
        a = 2 * math.pi * k / n
        r1 = r_long if k % 2 == 0 else r_short
        wd = width if k % 2 == 0 else width * 0.75
        ca, sa = math.cos(a), math.sin(a)
        px, py = -sa, ca
        p0 = (cx + ca * r_in + px * wd / 2, cy + sa * r_in + py * wd / 2)
        p1 = (cx + ca * r_in - px * wd / 2, cy + sa * r_in - py * wd / 2)
        p2 = (cx + ca * r1, cy + sa * r1)
        me = bpy.data.meshes.new("ray")
        vs = [(p0[0], p0[1], z), (p1[0], p1[1], z), (p2[0], p2[1], z),
              (p0[0], p0[1], z + h), (p1[0], p1[1], z + h), (p2[0], p2[1], z + h)]
        me.from_pydata(vs, [], [(0, 2, 1), (3, 4, 5), (0, 1, 4, 3), (1, 2, 5, 4), (2, 0, 3, 5)])
        tb._obj("ray", me, mat, 1.2)
    prism(cx, cy, r_in - 10, z, z + h, 32, mat, bevel=1.2)


def spark_emblem(w, h, color, suffix, ring=True):
    """Floor / wall emblem: charcoal disc, warm-grey ring with a light line, glowing Spark in the centre."""
    floorm = material("seflr" + suffix, CHAR_L, grime=0.4, noise_seed=47)
    ringm = material("sering" + suffix, WGREY, grime=0.35, noise_seed=48)
    disc = material("sedisc" + suffix, CHAR, grime=0.2, noise_seed=49)
    light = glow("seglow" + suffix, color, 0.95)
    box(-w, -h, -4, 2 * w, 2 * h, 0, floorm, bevel=0)
    c = (w / 2, h / 2)
    if ring:
        prism(*c, 246, 0, 8, 64, ringm, bevel=3)
        prism(*c, 228, 8, 8.6, 64, light, bevel=0)
        prism(*c, 220, 8, 10, 64, disc, bevel=2)
        spark_shape(c[0], c[1], 10, light)
    else:
        prism(*c, 250, 0, 4, 64, disc, bevel=3)
        spark_shape(c[0], c[1], 4, light, r_long=236, r_short=150, width=30)


def strip(w, h, color, suffix):
    frame = material("stfr" + suffix, WGREY, grime=0.35, noise_seed=50)
    light = glow("stgl" + suffix, color, 0.95)
    box(-w, -h, -4, 2 * w, 2 * h, 0, frame, bevel=0)
    box(-w, 8, 0, 2 * w, h - 8, 5, frame, bevel=3)
    box(-w, 18, 5, 2 * w, h - 18, 5.5, light, bevel=0)


render("SP_FloorDark", 512, 512, floor_dark)
render("SP_FloorPlate", 512, 512, floor_plate)
render("SP_WallCream", 512, 512, wall_cream)
render("SP_WallRib", 256, 256, wall_rib)
render("SP_WallTech", 512, 512, wall_tech)
render("SP_Trim", 512, 64, trim)
render("SP_Flow", 256, 32, flow)
render("SP_Light", 256, 128, light_panel)
render("SP_Ceiling", 512, 512, ceiling)
render("SP_Pillar", 256, 256, pillar)
render("SP_Spark", 512, 512, lambda w, h: spark_emblem(w, h, CORAL, "c", ring=False))
render("SP_SparkRed", 512, 512, lambda w, h: spark_emblem(w, h, TEAM_RED, "r"))
render("SP_SparkBlue", 512, 512, lambda w, h: spark_emblem(w, h, TEAM_BLUE, "b"))
render("SP_StripRed", 256, 64, lambda w, h: strip(w, h, TEAM_RED, "r"))
render("SP_StripBlue", 256, 64, lambda w, h: strip(w, h, TEAM_BLUE, "b"))
render("SP_StripCoral", 256, 64, lambda w, h: strip(w, h, CORAL, "c"))
