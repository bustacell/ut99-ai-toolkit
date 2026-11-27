#!/usr/bin/env python3
"""Assemble UT99 Bot Yearbook YouTube Shorts from existing yearbook assets.

1080x1920 (9:16), 24 fps. No new Cycles renders. Does not delete sources.
"""
from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

# Path resolution: prefer yb_paths.py (yearbook toolkit), then $YEARBOOK_ROOT
# / config.json. No machine-absolute defaults.
_HERE = Path(__file__).resolve().parent
_YEARBOOK_TOOLS = _HERE.parent
if str(_YEARBOOK_TOOLS) not in sys.path:
    sys.path.insert(0, str(_YEARBOOK_TOOLS))


def _resolve_paths() -> tuple[Path, Path, Path, Path]:
    """Return YEARBOOK_ROOT, FINAL, MUSIC, FONT_DIR."""
    try:
        from yb_paths import YEARBOOK_ROOT, FINAL, MUSIC, FONT_DIR
        return Path(YEARBOOK_ROOT), Path(FINAL), Path(MUSIC), Path(FONT_DIR)
    except Exception:
        pass
    cfg: dict = {}
    pipeline = os.environ.get("PIPELINE")
    if pipeline:
        for name in ("config.json", "config.linux.json"):
            p = Path(pipeline).expanduser() / name
            if p.is_file():
                cfg = json.loads(p.read_text(encoding="utf-8-sig"))
                break

    def _abs(raw: str | None, default_rel: str | None = None) -> Path | None:
        val = raw or default_rel
        if not val:
            return None
        p = Path(os.path.expanduser(str(val)))
        if not p.is_absolute() and pipeline:
            p = (Path(pipeline).expanduser() / p).resolve()
        return p

    root = _abs(os.environ.get("YEARBOOK_ROOT") or cfg.get("yearbookRoot"), "output/yearbook/v1")
    if root is None:
        raise RuntimeError(
            "Set $YEARBOOK_ROOT or config.json 'yearbookRoot' "
            "(typically $PIPELINE/output/yearbook/v1)."
        )
    final = root / "final"
    music = _abs(
        os.environ.get("YEARBOOK_MUSIC") or cfg.get("yearbookMusic"),
        "assets/ut/music/Mission.wav",
    )
    fonts = _abs(
        os.environ.get("YEARBOOK_FONTS") or cfg.get("yearbookFontsDir") or cfg.get("lvpsFontsDir")
    )
    if fonts is None:
        raise RuntimeError("Set $YEARBOOK_FONTS or config.json 'yearbookFontsDir'.")
    return root, final, music, fonts


ROOT, FINAL, MUSIC, FONT_DIR = _resolve_paths()
SHORTS = ROOT / "shorts"
TEST = SHORTS / "test"
WORK = SHORTS / "work"
QA = SHORTS / "qa"
SHORTS_FINAL = SHORTS / "final"

W, H, FPS = 1080, 1920, 24
SAFE = (40, 200, 900, 1380)  # left, top, right, bottom
SAFE_CX = (SAFE[0] + SAFE[2]) // 2
CONTENT_Y = 100  # where the 1080x1440 3:4 plate is pasted
PLATE_H = 1440

CINZEL = FONT_DIR / "Cinzel Decorative" / "CinzelDecorative-Bold.ttf"
CINZEL_BLK = FONT_DIR / "Cinzel Decorative" / "CinzelDecorative-Black.ttf"
CINZEL_REG = FONT_DIR / "Cinzel Decorative" / "CinzelDecorative-Regular.ttf"
PASSION = FONT_DIR / "Passion One" / "PassionOne-Black.ttf"
CRIMSON = FONT_DIR / "Crimson Text" / "CrimsonText-Regular.ttf"
CRIMSON_I = FONT_DIR / "Crimson Text" / "CrimsonText-Italic.ttf"
CRIMSON_B = FONT_DIR / "Crimson Text" / "CrimsonText-Bold.ttf"
INTER = FONT_DIR / "Inter" / "Inter-VariableFont_opsz,wght.ttf"
TEKTUR = FONT_DIR / "Tektur" / "Tektur-VariableFont_wdth,wght.ttf"

CREAM = (236, 226, 208)
CREAM_DIM = (168, 156, 136)
GOLD = (214, 176, 88)
GOLD_HI = (236, 210, 140)
GOLD_LO = (120, 92, 48)
INK = (12, 10, 9)
EPIC = "© Epic Games, Inc. and Digital Extremes  ·  unofficial fan project"
GOTY_LINE = "UNREAL TOURNAMENT (1999)"
KICKER = "UT99  BOT  YEARBOOK"
END_H1 = "FULL YEARBOOK"
END_H2 = "ALL 81 BOTS"
END_H3 = "Comment your number."

SR = 48000
MUSIC_VOL = 0.10
TAUNT_VOL = 3.2
MUSIC_FADE_IN = 0.5
MUSIC_FADE_OUT = 1.8
CRF = 18


def font(path: Path, size: int, weight: int | None = None, width: int | None = None):
    f = ImageFont.truetype(str(path), size)
    if weight is None or not hasattr(f, "set_variation_by_axes"):
        return f
    try:
        name = path.name.lower()
        if "inter" in name:
            opsz = min(max(float(size), 14.0), 32.0)
            f.set_variation_by_axes([opsz, float(weight)])
        elif "tektur" in name:
            f.set_variation_by_axes([float(width or 100), float(weight)])
    except Exception:
        pass
    return f



CATALOG: dict | None = None
CROPS: dict | None = None
BOTS: dict[int, dict] | None = None


def load_catalog() -> None:
    """Load catalog.json and closeup crop map from $YEARBOOK_ROOT.

    Deferred so the module can be imported (and compiled) without a local
    yearbook tree. Call once from main() or all_specs().
    """
    global CATALOG, CROPS, BOTS
    if BOTS is not None:
        return
    cat_path = ROOT / "inventory" / "catalog.json"
    crops_path = ROOT / "status" / "closeup_crops.json"
    if not cat_path.is_file():
        raise FileNotFoundError(
            f"Yearbook catalog not found: {cat_path}. Set $YEARBOOK_ROOT."
        )
    CATALOG = json.loads(cat_path.read_text())
    CROPS = json.loads(crops_path.read_text())["bots"]
    BOTS = bots_by_number()


def bots_by_number() -> dict[int, dict]:
    return {int(b["number"]): b for b in CATALOG["bots"]}


def official_name(b: dict) -> str:
    return b.get("skin_name") or b.get("face") or b.get("roster_name")


def alias_as(b: dict) -> str:
    note = (b.get("alias_note") or "").strip()
    if note:
        return note if note.lower().startswith("as ") else f"as {note}"
    also = b.get("also_roster") or []
    if also:
        names = [a["name"] for a in also if a.get("name")]
        if names:
            return "as " + " / ".join(names)
    return ""


def portrait_path(b: dict) -> Path:
    p = FINAL / "portraits" / f"{b['portrait']}.png"
    if not p.is_file():
        raise FileNotFoundError(p)
    return p


def closeup_path(b: dict) -> Path:
    p = FINAL / "closeups" / f"n{b['number']:03d}_{b['portrait']}.png"
    if not p.is_file():
        matches = list((FINAL / "closeups").glob(f"n{b['number']:03d}_*.png"))
        if not matches:
            raise FileNotFoundError(p)
        p = matches[0]
    return p


def clip_dir(b: dict) -> Path:
    matches = sorted((FINAL / "showcase_clips").glob(f"n{b['number']:03d}_*"))
    dirs = [p for p in matches if p.is_dir()]
    if not dirs:
        raise FileNotFoundError(f"clip for #{b['number']}")
    return dirs[0]


def clip_frames(b: dict) -> list[Path]:
    d = clip_dir(b)
    frames = sorted(d.glob("f*.png"))
    if not frames:
        raise FileNotFoundError(d)
    return frames


def accent_of(b: dict) -> tuple[int, int, int]:
    a = b.get("accent")
    if a and len(a) >= 3:
        return (int(a[0]), int(a[1]), int(a[2]))
    return GOLD


# ---------- drawing / safe-zone tracking ----------

@dataclass
class Box:
    x0: int
    y0: int
    x1: int
    y1: int
    text: str
    kind: str = "text"


class Painter:
    def __init__(self, img: Image.Image):
        self.img = img
        self.d = ImageDraw.Draw(img)
        self.boxes: list[Box] = []

    def _bbox(self, xy, text, fnt, anchor=None, stroke=0):
        x, y = xy
        if anchor:
            box = self.d.textbbox((x, y), text, font=fnt, anchor=anchor, stroke_width=stroke)
        else:
            box = self.d.textbbox((x, y), text, font=fnt, stroke_width=stroke)
        return box

    def text(self, xy, text, fnt, fill, *, anchor=None, shadow=True, kind="text"):
        if not text:
            return
        stroke = 2 if shadow else 0
        if shadow:
            # hard shadow, not a wide stroke into the unsafe zone
            for dx, dy in ((2, 2), (1, 2), (2, 1)):
                if anchor:
                    self.d.text((xy[0] + dx, xy[1] + dy), text, font=fnt, fill=(0, 0, 0), anchor=anchor)
                else:
                    self.d.text((xy[0] + dx, xy[1] + dy), text, font=fnt, fill=(0, 0, 0))
        if anchor:
            self.d.text(xy, text, font=fnt, fill=fill, anchor=anchor)
        else:
            self.d.text(xy, text, font=fnt, fill=fill)
        x0, y0, x1, y1 = self._bbox(xy, text, fnt, anchor=anchor, stroke=0)
        if shadow:
            x1 += 2
            y1 += 2
        self.boxes.append(Box(int(x0), int(y0), int(x1), int(y1), text, kind))

    def left_text(self, x, y, text, fnt, fill, *, kind="text"):
        """Left-aligned text, shifted right if the glyph bearing crosses SAFE left."""
        box = self.d.textbbox((x, y), text, font=fnt)
        if box[0] < SAFE[0]:
            x += SAFE[0] - box[0]
        self.text((x, y), text, fnt, fill, kind=kind)

    def fit_centered(self, text, fnt_path, size, y, fill, *, max_width=None, weight=None):
        max_width = max_width or (SAFE[2] - SAFE[0])
        while size >= 18:
            fnt = font(fnt_path, size, weight=weight)
            box = self.d.textbbox((0, 0), text, font=fnt)
            tw = box[2] - box[0]
            if tw <= max_width:
                self.text((SAFE_CX, y), text, fnt, fill, anchor="mt")
                return size
            size -= 2
        fnt = font(fnt_path, 18, weight=weight)
        self.text((SAFE_CX, y), text, fnt, fill, anchor="mt")
        return 18


def violations(boxes: list[Box], pad: int = 6) -> list[str]:
    L, T, R, B = SAFE
    out = []
    for b in boxes:
        if b.x0 < L - pad or b.y0 < T - pad or b.x1 > R + pad or b.y1 > B + pad:
            out.append(
                f"OUT {b.kind!r} {b.text!r} box=({b.x0},{b.y0})-({b.x1},{b.y1}) "
                f"safe=({L},{T})-({R},{B})"
            )
    return out


# ---------- plates ----------

def dark_blur_bg(src: Image.Image) -> Image.Image:
    bg = src.convert("RGB").resize((W, H), Image.Resampling.LANCZOS)
    bg = bg.filter(ImageFilter.GaussianBlur(28))
    bg = ImageEnhance.Brightness(bg).enhance(0.28)
    bg = ImageEnhance.Color(bg).enhance(0.6)
    return bg


def plate_34_legacy(src: Image.Image, y: int = CONTENT_Y) -> Image.Image:
    """Original Phase-1 layout: 1080x1440 plate in a middle band (kept for before/after)."""
    src = src.convert("RGB")
    if src.size != (1080, 1440):
        src = src.resize((1080, 1440), Image.Resampling.LANCZOS)
    canvas = dark_blur_bg(src)
    canvas.paste(src, (0, y))
    scrim = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(scrim)
    d.rectangle((0, 0, W, 210), fill=(8, 6, 5, 80))
    d.rectangle((0, 1180, W, H), fill=(8, 6, 5, 110))
    return Image.alpha_composite(canvas.convert("RGBA"), scrim).convert("RGB")


def plate_fill(src: Image.Image, scale: float = 1920 / 1440, feather: int = 40) -> Image.Image:
    """Scale a 3:4 full-body still/clip to fill 9:16.

    Default scale is 4/3 so the full body (head through feet) stays in frame
    and the empty studio at the sides is cropped. Remaining edges are feathered
    into a blurred, darkened, slightly zoomed copy of the same frame — no hard
    letterbox band.
    """
    src = src.convert("RGB")
    if src.size != (1080, 1440):
        src = src.resize((1080, 1440), Image.Resampling.LANCZOS)
    sw, sh = src.size
    cover = max(W / sw, H / sh) * 1.18
    bw, bh = int(sw * cover), int(sh * cover)
    bg = src.resize((bw, bh), Image.Resampling.LANCZOS)
    bx, by = (bw - W) // 2, (bh - H) // 2
    bg = bg.crop((bx, by, bx + W, by + H))
    bg = bg.filter(ImageFilter.GaussianBlur(36))
    bg = ImageEnhance.Brightness(bg).enhance(0.34)
    bg = ImageEnhance.Color(bg).enhance(0.55)

    fw, fh = int(round(sw * scale)), int(round(sh * scale))
    fg = src.resize((fw, fh), Image.Resampling.LANCZOS)
    if fh >= H:
        y0 = (fh - H) // 2
        fg = fg.crop((0, y0, fw, y0 + H))
        fh, fy = H, 0
    else:
        fy = (H - fh) // 2
    if fw >= W:
        x0 = (fw - W) // 2
        fg = fg.crop((x0, 0, x0 + W, fg.size[1]))
        fw, fx = W, 0
    else:
        fx = (W - fw) // 2

    canvas = bg.convert("RGBA")
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    layer.paste(fg.convert("RGBA"), (fx, fy))
    mask = Image.new("L", (fw, fh), 255)
    px = mask.load()
    fe = min(feather, max(8, fw // 6), max(8, fh // 8))
    # Always feather the cropped sides. Feather top/bottom only when letterboxed.
    fade_tb = not (fy == 0 and fh == H)
    for i in range(fe):
        a = int(255 * (i + 1) / fe)
        for y in range(fh):
            px[i, y] = min(px[i, y], a)
            px[fw - 1 - i, y] = min(px[fw - 1 - i, y], a)
        if fade_tb:
            for x in range(fw):
                px[x, i] = min(px[x, i], a)
                px[x, fh - 1 - i] = min(px[x, fh - 1 - i], a)
    full = Image.new("L", (W, H), 0)
    full.paste(mask, (fx, fy))
    layer.putalpha(full)
    return Image.alpha_composite(canvas, layer).convert("RGB")


def plate_34(src: Image.Image, y: int = CONTENT_Y) -> Image.Image:
    """Default body plate: fill the 9:16 frame (see plate_fill)."""
    return plate_fill(src)


def closeup_916(b: dict, zoom: float = 1.0, eyes_at: float = 0.46) -> Image.Image:
    """Vertical window from the 2560x1440 v1 close-up.

    eyes_at is the fraction of the 9:16 frame where the eyes land (0.38 is
    a mid-upper Shorts portrait; 0.58 sits the face below a title panel).
    zoom > 1 tightens the window around the face.
    """
    im = Image.open(closeup_path(b)).convert("RGB")
    cw, ch = im.size  # 2560x1440
    info = CROPS.get(str(b["number"])) or CROPS.get(b["number"]) or {}
    cx = int(info.get("cx", cw // 2))
    eyes = int(info.get("eyes", ch // 3))
    if eyes / ch <= 0.42:
        crop_h = ch
        y0 = 0
    else:
        crop_h = min(ch, int((ch - eyes) / max(0.15, 1.0 - eyes_at)))
        crop_h = max(crop_h, int(ch * 0.72))
        y0 = max(0, int(round(eyes - eyes_at * crop_h)))
        if y0 + crop_h > ch:
            y0 = ch - crop_h
    crop_h = max(64, int(crop_h / max(zoom, 1.0)))
    crop_w = int(round(crop_h * 9 / 16))
    # re-anchor eyes after zoom
    y0 = int(round(eyes - eyes_at * crop_h))
    y0 = max(0, min(y0, ch - crop_h))
    x0 = max(0, min(int(cx - crop_w // 2), cw - crop_w))
    crop = im.crop((x0, y0, x0 + crop_w, y0 + crop_h))
    return crop.resize((W, H), Image.Resampling.LANCZOS)


def veil(img: Image.Image, alpha: int = 140) -> Image.Image:
    v = Image.new("RGBA", img.size, (8, 6, 5, alpha))
    return Image.alpha_composite(img.convert("RGBA"), v).convert("RGB")


def left_rule(img: Image.Image, color=GOLD):
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, 8, H), fill=color)
    return img


def brand_tag(p: Painter, accent=GOLD):
    p.text((48, 214), GOTY_LINE, font(CINZEL_REG, 22), accent, kind="brand")


def name_stack(p: Painter, b: dict, *, big_alias: bool = False, show_line: bool = True):
    num = f"#{b['number']:02d}"
    name = official_name(b)
    alias = alias_as(b)
    team = b.get("team") or ""
    if team in ("Also in the Yearbook", "Tournament Champion", "SkeletalChars"):
        team = {"Tournament Champion": "Tournament Champion",
                "SkeletalChars": "SkeletalChars",
                "Also in the Yearbook": ""}.get(team, "")
    acc = accent_of(b)
    y = 1120
    p.left_text(48, y, num, font(PASSION, 96), GOLD_HI, kind="number")
    y = 1220
    # shrink name to safe width
    size = 72
    fnt = font(CINZEL_BLK, size)
    while size >= 32:
        fnt = font(CINZEL_BLK, size)
        box = p.d.textbbox((48, y), name, font=fnt)
        if box[2] <= SAFE[2] - 4:
            break
        size -= 2
    p.left_text(48, y, name, fnt, CREAM, kind="name")
    y = box[3] + 8 if False else y + size + 4
    # recompute y from last box
    y = p.boxes[-1].y1 + 6
    if alias:
        asize = 56 if big_alias else 36
        p.left_text(48, y, alias, font(CRIMSON_I, asize), GOLD_HI if big_alias else CREAM_DIM, kind="alias")
        y = p.boxes[-1].y1 + 4
    if team and not big_alias:
        p.left_text(48, min(y, 1338), team, font(CINZEL_REG, 26), acc, kind="team")
    if show_line and b.get("taunt_line") and not big_alias:
        line = b["taunt_line"]
        if p.boxes[-1].y1 < 1348:
            fnt = font(CRIMSON_I, 26)
            box = p.d.textbbox((48, p.boxes[-1].y1 + 4), f"“{line}”", font=fnt)
            if box[3] <= SAFE[3] and box[2] <= SAFE[2]:
                p.left_text(48, p.boxes[-1].y1 + 4, f"“{line}”", fnt, CREAM_DIM, kind="line")


def portrait_grid(bots: list[dict], cols: int, cell_w: int, cell_h: int) -> Image.Image:
    rows = math.ceil(len(bots) / cols)
    grid = Image.new("RGB", (cols * cell_w, rows * cell_h), INK)
    for i, b in enumerate(bots):
        r, c = divmod(i, cols) if False else (i // cols, i % cols)
        im = Image.open(portrait_path(b)).convert("RGB").resize((cell_w, cell_h), Image.Resampling.LANCZOS)
        grid.paste(im, (c * cell_w, r * cell_h))
    return grid


_GRID81 = None


def grid_81() -> Image.Image:
    global _GRID81
    if _GRID81 is None:
        all_bots = [BOTS[i] for i in range(1, 82)]
        g = portrait_grid(all_bots, 9, 120, 160)  # 1080x1440
        _GRID81 = g
    return _GRID81.copy()


# ---------- cards ----------

def hook_brand_card() -> tuple[Image.Image, list[Box]]:
    img = Image.new("RGB", (W, H), INK)
    g = grid_81().resize((W, PLATE_H), Image.Resampling.LANCZOS)
    img.paste(g, (0, CONTENT_Y))
    img = veil(img, 195)
    left_rule(img, GOLD)
    p = Painter(img)
    p.fit_centered(KICKER, TEKTUR, 30, 420, GOLD, weight=600)
    p.fit_centered(GOTY_LINE, CINZEL_BLK, 46, 520, GOLD_HI)
    p.fit_centered("BOT YEARBOOK", PASSION, 88, 620, CREAM)
    return img, p.boxes


def hook_team_card(team: str, bots: list[dict], question: str) -> tuple[Image.Image, list[Box]]:
    """4-wide portrait grid fully inside the safe zone, title above, question below."""
    n = len(bots)
    # Prefer a wide grid so 8 teammates stay large and above the 25% line.
    if n <= 4:
        cols = n
    elif n <= 6:
        cols = 3
    else:
        cols = 4
    rows = math.ceil(n / cols)
    # Grid lives between the title (~y 500) and the question (~y 1180)
    grid_top, grid_bot = 500, 1160
    max_w = SAFE[2] - SAFE[0]  # 860
    max_h = grid_bot - grid_top
    cell_w = max_w // cols
    cell_h = int(cell_w * 4 / 3)
    if rows * cell_h > max_h:
        cell_h = max_h // rows
        cell_w = int(cell_h * 3 / 4)
    g = portrait_grid(bots, cols, cell_w, cell_h)
    img = Image.new("RGB", (W, H), INK)
    # blurred team bed
    bed_src = portrait_grid(bots, cols, cell_w, cell_h)
    img.paste(dark_blur_bg(bed_src), (0, 0))
    gx = SAFE_CX - g.size[0] // 2
    gy = grid_top + (max_h - g.size[1]) // 2
    img.paste(g, (gx, gy))
    # light scrim behind title / question, not over the faces
    scrim = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(scrim)
    d.rectangle((0, 0, W, 490), fill=(8, 6, 5, 140))
    d.rectangle((0, 1160, W, H), fill=(8, 6, 5, 150))
    img = Image.alpha_composite(img.convert("RGBA"), scrim).convert("RGB")
    left_rule(img, accent_of(bots[0]))
    p = Painter(img)
    brand_tag(p, accent_of(bots[0]))
    p.fit_centered(team.upper(), CINZEL_BLK, 78, 300, GOLD_HI)
    p.fit_centered("WHICH NUMBER", PASSION, 64, 1188, CREAM)
    p.fit_centered("IS YOURS?", PASSION, 64, 1268, CREAM)
    return img, p.boxes


def hook_title_card(title_lines: list[str], bg_bot: dict | None, sub: str = "",
                    use_closeup: bool = True, shift_down: int = 0) -> tuple[Image.Image, list[Box]]:
    if bg_bot is not None and use_closeup:
        # Sit the face below the title panel so type does not cover it.
        img = closeup_916(bg_bot, eyes_at=0.58)
        img = veil(img, 40)
    elif bg_bot is not None:
        fr = Image.open(clip_frames(bg_bot)[0]).convert("RGB")
        img = plate_fill(fr)
        if shift_down > 0:
            # Slide the subject down so a tall head/crest sits below the title
            # panel. The vacated top is the already-blurred studio fill.
            canvas = img.copy()
            top = canvas.crop((0, 0, W, min(H, shift_down + 80))).resize((W, shift_down), Image.Resampling.LANCZOS)
            from PIL import ImageFilter, ImageEnhance
            top = top.filter(ImageFilter.GaussianBlur(28))
            top = ImageEnhance.Brightness(top).enhance(0.45)
            img = Image.new("RGB", (W, H), INK)
            img.paste(top, (0, 0))
            keep_h = H - shift_down
            img.paste(canvas.crop((0, 0, W, keep_h)), (0, shift_down))
        img = veil(img, 70)
    else:
        img = Image.new("RGB", (W, H), INK)
        g = grid_81()
        img.paste(g, (0, CONTENT_Y))
        img = veil(img, 200)
    left_rule(img, GOLD)
    # Draw type first, then a panel that hugs the text (not a tall face-covering band).
    p = Painter(img)
    brand_tag(p)
    y = 260
    for i, line in enumerate(title_lines):
        path = PASSION if i == 0 else CINZEL_BLK
        sz = 70 if i == 0 else 56
        fill = GOLD_HI if i == 0 else CREAM
        p.fit_centered(line, path, sz, y, fill)
        y = p.boxes[-1].y1 + 10
    if sub:
        p.fit_centered(sub, CRIMSON_I, 28, min(y + 14, 660), CREAM_DIM)
    text_bottom = max(b.y1 for b in p.boxes) + 24
    band = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(band).rounded_rectangle((36, 210, 870, text_bottom), radius=16, fill=(8, 6, 5, 210))
    img = Image.alpha_composite(img.convert("RGBA"), band).convert("RGB")
    # Re-draw type on top of the now-opaque panel (boxes stay the same).
    p2 = Painter(img)
    brand_tag(p2)
    y = 260
    for i, line in enumerate(title_lines):
        path = PASSION if i == 0 else CINZEL_BLK
        sz = 70 if i == 0 else 56
        fill = GOLD_HI if i == 0 else CREAM
        p2.fit_centered(line, path, sz, y, fill)
        y = p2.boxes[-1].y1 + 10
    if sub:
        p2.fit_centered(sub, CRIMSON_I, 28, min(y + 14, 660), CREAM_DIM)
    return img, p2.boxes


def hook_cow_surprise(b: dict) -> tuple[Image.Image, list[Box]]:
    # first frame of the cow clip, almost no type — the hook is the image
    fr = Image.open(clip_frames(b)[0]).convert("RGB")
    img = plate_34(fr, CONTENT_Y)
    left_rule(img, GOLD)
    p = Painter(img)
    brand_tag(p)
    return img, p.boxes


def end_card() -> tuple[Image.Image, list[Box]]:
    img = Image.new("RGB", (W, H), INK)
    img.paste(grid_81(), (0, CONTENT_Y))
    img = veil(img, 175)
    # central panel inside safe zone
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    d.rounded_rectangle((50, 280, 870, 1320), radius=18, fill=(8, 6, 5, 165))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    left_rule(img, GOLD)
    p = Painter(img)
    p.fit_centered(GOTY_LINE, CINZEL_REG, 28, 310, GOLD_HI)
    p.fit_centered(KICKER, TEKTUR, 26, 360, GOLD, weight=600)
    p.fit_centered(END_H1, CINZEL_BLK, 72, 470, GOLD_HI)
    p.fit_centered(END_H2, CINZEL_BLK, 72, 570, CREAM)
    p.fit_centered(END_H3, PASSION, 58, 700, GOLD_HI)
    p.fit_centered("Pick your favourite  ·  #1–#81", CRIMSON, 28, 800, CREAM)
    p.fit_centered(EPIC, INTER, 18, 1260, CREAM_DIM, weight=400)
    return img, p.boxes


def bot_clip_frame(b: dict, src: Image.Image, *, reveal: bool = False, show_line: bool = True) -> tuple[Image.Image, list[Box]]:
    img = plate_fill(src)
    scrim = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(scrim).rectangle((0, 1080, W, H), fill=(8, 6, 5, 100))
    img = Image.alpha_composite(img.convert("RGBA"), scrim).convert("RGB")
    left_rule(img, accent_of(b))
    p = Painter(img)
    brand_tag(p, accent_of(b))
    name_stack(p, b, big_alias=False, show_line=show_line)
    return img, p.boxes


def alias_still(b: dict, phase: str) -> tuple[Image.Image, list[Box]]:
    """phase: 'face' (catalog name only) or 'alias' (as Y dominant).

    Type sits at the TOP of the safe zone so it does not cover the face.
    """
    img = closeup_916(b)
    scrim = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(scrim).rectangle((0, 190, W, 720), fill=(8, 6, 5, 135))
    img = Image.alpha_composite(img.convert("RGBA"), scrim).convert("RGB")
    left_rule(img, accent_of(b))
    p = Painter(img)
    brand_tag(p, accent_of(b))
    num = f"#{b['number']:02d}"
    name = official_name(b)
    alias = alias_as(b)
    p.left_text(48, 270, num, font(PASSION, 80), GOLD_HI, kind="number")
    if phase == "face":
        size = 70
        fnt = font(CINZEL_BLK, size)
        while size >= 36 and p.d.textbbox((48, 360), name, font=fnt)[2] > SAFE[2]:
            size -= 2
            fnt = font(CINZEL_BLK, size)
        p.left_text(48, 360, name, fnt, CREAM, kind="name")
    else:
        p.left_text(48, 360, name, font(CINZEL_REG, 34), CREAM_DIM, kind="name")
        label = alias or name
        size = 68
        y = 410
        fnt = font(CINZEL_BLK, size)
        while size >= 36 and p.d.textbbox((48, y), label, font=fnt)[2] > SAFE[2]:
            size -= 2
            fnt = font(CINZEL_BLK, size)
        p.left_text(48, y, label, fnt, GOLD_HI, kind="alias")
    return img, p.boxes



def closeup_card(b: dict, zoom: float = 1.0, eyes_at: float = 0.46) -> tuple[Image.Image, list[Box]]:
    """Close-up with typography at the TOP of the safe zone (not over the face)."""
    img = closeup_916(b, zoom=zoom, eyes_at=eyes_at)
    scrim = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(scrim).rectangle((0, 190, W, 560), fill=(8, 6, 5, 140))
    img = Image.alpha_composite(img.convert("RGBA"), scrim).convert("RGB")
    left_rule(img, accent_of(b))
    p = Painter(img)
    brand_tag(p, accent_of(b))
    p.left_text(48, 270, f"#{b['number']:02d}", font(PASSION, 80), GOLD_HI, kind="number")
    name = official_name(b)
    size = 60
    fnt = font(CINZEL_BLK, size)
    while size >= 32 and p.d.textbbox((48, 360), name, font=fnt)[2] > SAFE[2]:
        size -= 2
        fnt = font(CINZEL_BLK, size)
    p.left_text(48, 360, name, fnt, CREAM, kind="name")
    alias = alias_as(b)
    if alias:
        p.left_text(48, p.boxes[-1].y1 + 6, alias, font(CRIMSON_I, 32), GOLD_HI, kind="alias")
    return img, p.boxes


def hook_spotlight_card(b: dict) -> tuple[Image.Image, list[Box]]:
    # Eyes further down so tall caps / crests sit below the title panel, not under the type.
    img = closeup_916(b, eyes_at=0.66)
    panel = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(panel).rounded_rectangle((36, 210, 870, 600), radius=16, fill=(8, 6, 5, 210))
    img = Image.alpha_composite(img.convert("RGBA"), panel).convert("RGB")
    left_rule(img, accent_of(b))
    p = Painter(img)
    brand_tag(p, accent_of(b))
    p.fit_centered(KICKER, TEKTUR, 24, 250, GOLD, weight=600)
    p.fit_centered(f"#{b['number']:02d}", PASSION, 100, 300, GOLD_HI)
    p.fit_centered(official_name(b).upper(), CINZEL_BLK, 60, 410, CREAM)
    alias = alias_as(b)
    y = 500
    if alias:
        p.fit_centered(alias, CRIMSON_I, 34, 500, GOLD_HI)
        y = 548
    team = b.get("team") or ""
    if team and team not in ("Also in the Yearbook", "SkeletalChars"):
        p.fit_centered(team, CINZEL_REG, 26, y, accent_of(b))
    return img, p.boxes


def spotlight_name_card(b: dict) -> tuple[Image.Image, list[Box]]:
    # Prefer a mid-clip body frame (already performing) over a static portrait.
    frames = clip_frames(b)
    src = Image.open(frames[min(len(frames)//2, len(frames)-1)]).convert("RGB")
    img = plate_fill(src)
    scrim = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(scrim).rectangle((0, 1000, W, H), fill=(8, 6, 5, 120))
    img = Image.alpha_composite(img.convert("RGBA"), scrim).convert("RGB")
    left_rule(img, accent_of(b))
    p = Painter(img)
    brand_tag(p, accent_of(b))
    name_stack(p, b, show_line=True)
    return img, p.boxes


# ---------- short specs ----------

@dataclass
class Event:
    """A visual segment: one still held, or a clip played, then optional hold."""
    kind: str  # still, clip, alias, closeup
    dur: float
    bot: dict | None = None
    still: Image.Image | None = None
    still_boxes: list[Box] = field(default_factory=list)
    alias_phase_at: float | None = None  # seconds into event when alias slams
    taunt: bool = False
    music_offset: float = 0.0
    zoom0: float = 1.0
    zoom1: float = 1.0
    eyes_at: float = 0.46


@dataclass
class ShortSpec:
    sid: str
    filename: str
    title: str
    concept: str
    bots: list[dict]
    events: list[Event] = field(default_factory=list)
    music_offset: float = 0.0
    planned_s: float = 0.0


def _still_event(img, boxes, dur, taunt_bot=None) -> Event:
    return Event(kind="still", dur=dur, still=img, still_boxes=boxes, bot=taunt_bot, taunt=taunt_bot is not None)


def build_team_short(sid, filename, title, team, numbers, music_offset=0.0,
                     beat=3.0, close_dur=0.0, concept="team") -> ShortSpec:
    bots = [BOTS[n] for n in numbers]
    hook1, b1 = hook_brand_card()
    hook2, b2 = hook_team_card(team, bots, "Which number is yours?")
    end, be = end_card()
    events = [
        _still_event(hook1, b1, 0.75),
        _still_event(hook2, b2, 1.65),
    ]
    for b in bots:
        events.append(Event(kind="clip", dur=beat, bot=b, taunt=True))
        if close_dur > 0:
            events.append(Event(kind="closeup", dur=close_dur, bot=b, zoom0=1.0, zoom1=1.06, eyes_at=0.46))
    events.append(_still_event(end, be, 4.9))
    events.append(_still_event(hook1, b1, 0.60))  # loop back
    planned = sum(e.dur for e in events)
    return ShortSpec(sid, filename, title, concept, bots, events, music_offset, planned)


def build_alias_short(sid, filename, title, numbers, music_offset=0.0,
                      use_closeup: bool = True, shift_down: int = 0) -> ShortSpec:
    bots = [BOTS[n] for n in numbers]
    hook1, b1 = hook_brand_card()
    hook2, b2 = hook_title_card(
        ["THEY WEAR", "SOMEONE ELSE'S", "FACE"],
        bg_bot=bots[0],
        sub="Official name first  ·  ladder name second",
        use_closeup=use_closeup,
        shift_down=shift_down,
    )
    end, be = end_card()
    events = [
        _still_event(hook1, b1, 0.70),
        _still_event(hook2, b2, 1.80),
    ]
    for b in bots:
        ev = Event(kind="alias", dur=2.80, bot=b, taunt=True, alias_phase_at=0.95)
        events.append(ev)
    events.append(_still_event(end, be, 4.90))
    events.append(_still_event(hook1, b1, 0.60))
    planned = sum(e.dur for e in events)
    return ShortSpec(sid, filename, title, "alias", bots, events, music_offset, planned)


def build_bonus_short(sid, filename, title, numbers, music_offset=0.0) -> ShortSpec:
    bots = [BOTS[n] for n in numbers]
    cow = BOTS[78]
    hook0, bz = hook_cow_surprise(cow)
    hook1, b1 = hook_brand_card()
    hook2, b2 = hook_title_card(
        ["BONUS PACK", "SKAARJ, NALI", "& COWS"],
        bg_bot=cow,
        sub="All 12 official Bonus Pack faces",
        use_closeup=False,
    )
    end, be = end_card()
    events = [
        _still_event(hook0, bz, 1.10),
        _still_event(hook2, b2, 1.70),
    ]
    for b in bots:
        events.append(Event(kind="clip", dur=2.40, bot=b, taunt=True))
    events.append(_still_event(end, be, 4.90))
    events.append(_still_event(hook1, b1, 0.60))
    planned = sum(e.dur for e in events)
    return ShortSpec(sid, filename, title, "bonus", bots, events, music_offset, planned)


def test_specs() -> list[ShortSpec]:
    return [s for s in all_specs() if s.sid in ("S01", "S10", "S12")]


def build_spotlight(sid, filename, title, number, music_offset=0.0) -> ShortSpec:
    b = BOTS[number]
    hook1, b1 = hook_brand_card()
    hook2, b2 = hook_spotlight_card(b)
    card, cb = spotlight_name_card(b)
    end, be = end_card()
    events = [
        _still_event(hook1, b1, 0.70),
        _still_event(hook2, b2, 1.60),
        Event(kind="clip", dur=3.50, bot=b, taunt=True),
        Event(kind="closeup", dur=6.50, bot=b, zoom0=1.0, zoom1=1.08, eyes_at=0.46),
        _still_event(card, cb, 4.00),
        _still_event(end, be, 5.00),
        _still_event(hook1, b1, 0.60),
    ]
    planned = sum(e.dur for e in events)
    return ShortSpec(sid, filename, title, "spotlight", [b], events, music_offset, planned)


def build_bosses(sid, filename, title, numbers, music_offset=0.0) -> ShortSpec:
    bots = [BOTS[n] for n in numbers]
    hook1, b1 = hook_brand_card()
    hook2, b2 = hook_title_card(
        ["BOSSES", "XAN, XAN MARK II", "& WAR BOSS"],
        bg_bot=bots[-1],
        sub="The tournament's final machines",
        use_closeup=False,
    )
    end, be = end_card()
    events = [
        _still_event(hook1, b1, 0.70),
        _still_event(hook2, b2, 1.80),
    ]
    for b in bots:
        events.append(Event(kind="clip", dur=3.50, bot=b, taunt=True))
        events.append(Event(kind="closeup", dur=4.00, bot=b, zoom0=1.0, zoom1=1.07, eyes_at=0.46))
    events.append(_still_event(end, be, 4.90))
    events.append(_still_event(hook1, b1, 0.60))
    planned = sum(e.dur for e in events)
    return ShortSpec(sid, filename, title, "bosses", bots, events, music_offset, planned)


def _off(n: int) -> float:
    """Stagger Mission.wav so neighbouring Shorts do not share the same bar."""
    return float((n * 13) % 200)


def all_specs() -> list[ShortSpec]:
    load_catalog()
    return [
        build_team_short("S01", "s01_thunder_crash.mp4",
            "Thunder Crash — which number is yours? | UT99 Bot Yearbook",
            "Thunder Crash", [1, 2, 3, 4, 5, 6, 7, 8], music_offset=_off(1)),
        build_team_short("S02", "s02_iron_guard.mp4",
            "Iron Guard — which number is yours? | UT99 Bot Yearbook",
            "Iron Guard", [9, 10, 11, 12, 13, 14, 15, 16], music_offset=_off(2)),
        build_team_short("S03", "s03_blood_reavers.mp4",
            "Blood Reavers — which number is yours? | UT99 Bot Yearbook",
            "Blood Reavers", [17, 18, 19, 20, 21, 22, 23, 24], music_offset=_off(3)),
        build_team_short("S04", "s04_black_legion.mp4",
            "Black Legion — which number is yours? | UT99 Bot Yearbook",
            "Black Legion", [25, 26, 27, 28, 29, 30, 31, 32], music_offset=_off(4)),
        build_team_short("S05", "s05_raw_steel.mp4",
            "Raw Steel — which number is yours? | UT99 Bot Yearbook",
            "Raw Steel", [33, 34, 35, 36, 37], music_offset=_off(5), beat=4.0),
        build_team_short("S06", "s06_venom.mp4",
            "Venom — which number is yours? | UT99 Bot Yearbook",
            "Venom", [38, 39, 40, 41, 42], music_offset=_off(6), beat=4.0),
        build_team_short("S07", "s07_dark_phalanx.mp4",
            "Dark Phalanx — which number is yours? | UT99 Bot Yearbook",
            "Dark Phalanx", [43, 44, 45, 46, 47, 48, 49, 50], music_offset=_off(7)),
        build_team_short("S08", "s08_red_claw.mp4",
            "Red Claw — which number is yours? | UT99 Bot Yearbook",
            "Red Claw", [68, 69, 70], music_offset=_off(8), beat=3.5, close_dur=2.5),
        build_team_short("S09", "s09_iron_skull.mp4",
            "Iron Skull — which number is yours? | UT99 Bot Yearbook",
            "Iron Skull", [71, 72, 73, 74], music_offset=_off(9), beat=3.5, close_dur=1.8),
        build_alias_short("S10", "s10_alias_faces.mp4",
            "They wear someone else's face | UT99 Bot Yearbook",
            [7, 30, 33, 34, 35, 38, 40, 41, 44, 49], music_offset=_off(10)),
        build_alias_short("S11", "s11_bonus_aliases.mp4",
            "Bonus Pack aliases: one face, two names | UT99 Bot Yearbook",
            [68, 69, 70, 71, 72, 73], music_offset=_off(11), use_closeup=False, shift_down=640),
        build_bonus_short("S12", "s12_bonus_pack.mp4",
            "Bonus Pack: Skaarj, Nali & Cows | UT99 Bot Yearbook",
            [68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79], music_offset=_off(12)),
        build_bosses("S13", "s13_bosses.mp4",
            "Bosses: Xan, Xan Mark II & War Boss | UT99 Bot Yearbook",
            [67, 80, 81], music_offset=_off(13)),
        build_team_short("S14", "s14_also_in_yearbook_p1.mp4",
            "Also in the yearbook, part 1 | UT99 Bot Yearbook",
            "Also in the Yearbook", [51, 52, 53, 54, 55, 56, 57, 58],
            music_offset=_off(14), concept="leftovers"),
        build_team_short("S15", "s15_also_in_yearbook_p2.mp4",
            "Also in the yearbook, part 2 | UT99 Bot Yearbook",
            "Also in the Yearbook", [59, 60, 61, 62, 63, 64, 65, 66],
            music_offset=_off(15), concept="leftovers"),
        build_spotlight("S16", "s16_malcom.mp4",
            "#04 Malcom — UT99 Bot Yearbook", 4, music_offset=_off(16)),
        build_spotlight("S17", "s17_olga.mp4",
            "#07 Olga as Tamika — UT99 Bot Yearbook", 7, music_offset=_off(17)),
        build_spotlight("S18", "s18_kyla.mp4",
            "#17 Kyla — UT99 Bot Yearbook", 17, music_offset=_off(18)),
        build_spotlight("S19", "s19_xan.mp4",
            "#67 Xan, Tournament Champion — UT99 Bot Yearbook", 67, music_offset=_off(19)),
        build_spotlight("S20", "s20_warcow.mp4",
            "#78 WarCow — UT99 Bot Yearbook", 78, music_offset=_off(20)),
        build_spotlight("S21", "s21_war_boss.mp4",
            "#81 War Boss — UT99 Bot Yearbook", 81, music_offset=_off(21)),
    ]


# ---------- frame expansion / encode ----------

def hold_last(frames: list[Path], dur: float) -> list[Path]:
    """12 fps frames, doubled to 24 fps, then hold last to dur."""
    seq = []
    for p in frames:
        seq.extend([p, p])  # 24 fps
    need = int(round(dur * FPS))
    if len(seq) < need:
        seq.extend([seq[-1]] * (need - len(seq)))
    elif len(seq) > need:
        seq = seq[:need]
    return seq


def render_frames(spec: ShortSpec, framedir: Path) -> list[list[Box]]:
    framedir.mkdir(parents=True, exist_ok=True)
    # clean previous frames in this dir only
    for old in framedir.glob("*.jpg"):
        old.unlink()
    all_boxes: list[list[Box]] = []
    idx = 0
    counts = [int(round(e.dur * FPS)) for e in spec.events]
    n_planned = int(round(sum(e.dur for e in spec.events) * FPS))
    drift = n_planned - sum(counts)
    if counts:
        counts[-1] = max(1, counts[-1] + drift)

    def write(img: Image.Image, boxes: list[Box]):
        nonlocal idx
        dest = framedir / f"{idx:05d}.jpg"
        img.convert("RGB").save(dest, "JPEG", quality=93, subsampling=0, optimize=True)
        all_boxes.append(boxes)
        idx += 1

    for ev, n in zip(spec.events, counts):
        if ev.kind == "still":
            for _ in range(n):
                write(ev.still, ev.still_boxes)
        elif ev.kind == "clip":
            srcs = hold_last(clip_frames(ev.bot), n / FPS)
            # cache composited unique sources
            cache: dict[str, tuple[Image.Image, list[Box]]] = {}
            for pth in srcs:
                key = str(pth)
                if key not in cache:
                    im, boxes = bot_clip_frame(ev.bot, Image.open(pth))
                    cache[key] = (im, boxes)
                im, boxes = cache[key]
                write(im, boxes)
        elif ev.kind == "alias":
            n_face = int(round((ev.alias_phase_at or 0.95) * FPS))
            n_alias = n - n_face
            face_img, face_boxes = alias_still(ev.bot, "face")
            alias_img, alias_boxes = alias_still(ev.bot, "alias")
            for _ in range(n_face):
                write(face_img, face_boxes)
            for _ in range(n_alias):
                write(alias_img, alias_boxes)
        elif ev.kind == "closeup":
            for i in range(n):
                u = 0 if n <= 1 else i / (n - 1)
                z = ev.zoom0 + (ev.zoom1 - ev.zoom0) * u
                im, boxes = closeup_card(ev.bot, zoom=z, eyes_at=ev.eyes_at)
                write(im, boxes)
        else:
            raise ValueError(ev.kind)
    assert idx == n_planned or abs(idx - n_planned) <= 1, (idx, n_planned)
    return all_boxes


def run(cmd: list[str], log: Path | None = None) -> subprocess.CompletedProcess:
    r = subprocess.run(cmd, capture_output=True, text=True)
    if log:
        log.write_text((r.stdout or "") + "\n" + (r.stderr or ""))
    if r.returncode != 0:
        raise RuntimeError(f"cmd failed {cmd[:6]}…\n{r.stderr[-4000:]}")
    return r


def mix_audio(spec: ShortSpec, wav_path: Path) -> None:
    dur = sum(e.dur for e in spec.events)
    # build taunt list
    taunts = []
    t = 0.0
    for ev in spec.events:
        if ev.taunt and ev.bot:
            delay = t + (0.35 if ev.kind != "alias" else (ev.alias_phase_at or 0.95))
            taunts.append((Path(ev.bot["taunt_file"]), delay, ev.bot))
        t += ev.dur

    args = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]
    args += ["-ss", f"{spec.music_offset:.3f}", "-t", f"{dur:.4f}", "-i", str(MUSIC)]
    for path, _, _ in taunts:
        args += ["-i", str(path)]
    filters = []
    filters.append(
        f"[0:a]aresample={SR},aformat=channel_layouts=stereo,volume={MUSIC_VOL},"
        f"afade=t=in:st=0:d={MUSIC_FADE_IN:.3f}:curve=hsin,"
        f"afade=t=out:st={max(0.0, dur - MUSIC_FADE_OUT):.4f}:d={MUSIC_FADE_OUT:.3f}:curve=hsin[m]"
    )
    mix_ins = ["[m]"]
    for i, (path, delay, _) in enumerate(taunts, start=1):
        ms = int(round(delay * 1000))
        filters.append(
            f"[{i}:a]aresample={SR},aformat=channel_layouts=stereo,"
            f"adelay={ms}|{ms},volume={TAUNT_VOL}[t{i}]"
        )
        mix_ins.append(f"[t{i}]")
    n = 1 + len(taunts)
    filters.append(
        "".join(mix_ins)
        + f"amix=inputs={n}:duration=first:dropout_transition=0,alimiter=limit=0.95:level=false[a]"
    )
    args += ["-filter_complex", ";".join(filters), "-map", "[a]", "-t", f"{dur:.4f}",
             "-c:a", "pcm_s16le", str(wav_path)]
    run(args, WORK / f"{spec.sid}_mix.log")


def loudnorm_encode(framedir: Path, wav: Path, out: Path, dur: float, log_stem: Path) -> dict:
    raw = log_stem.parent / "pre_loudnorm.mp4"
    run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-framerate", str(FPS), "-i", str(framedir / "%05d.jpg"),
        "-i", str(wav),
        "-map", "0:v", "-map", "1:a",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", str(CRF),
        "-preset", "medium", "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart", "-shortest", str(raw),
    ], log_stem.with_suffix(".encode.log"))

    # pass 1
    r = subprocess.run([
        "ffmpeg", "-hide_banner", "-i", str(raw),
        "-af", "loudnorm=I=-14:TP=-2.0:LRA=20:print_format=json",
        "-f", "null", "-",
    ], capture_output=True, text=True)
    text = r.stderr or r.stdout
    jstart = text.rfind("{")
    jend = text.rfind("}")
    if jstart < 0:
        raise RuntimeError("loudnorm json missing:\n" + text[-2000:])
    j = json.loads(text[jstart:jend + 1])
    af = (
        f"loudnorm=I=-14:TP=-2.0:LRA=20:measured_I={j['input_i']}:"
        f"measured_TP={j['input_tp']}:measured_LRA={j['input_lra']}:"
        f"measured_thresh={j['input_thresh']}:offset={j['target_offset']}:"
        f"linear=true,alimiter=limit=0.8222:level=false,aresample={SR}"
    )
    run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(raw),
        "-c:v", "copy",
        "-af", af, "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart", str(out),
    ], log_stem.with_suffix(".loudnorm.log"))
    # keep the pre-loudnorm file (do not delete)
    (log_stem.with_suffix(".loudnorm_pass1.json")).write_text(json.dumps(j, indent=2) + "\n")
    return j


def measure(path: Path) -> dict:
    r = subprocess.run([
        "ffmpeg", "-hide_banner", "-i", str(path),
        "-af", "ebur128=peak=true", "-f", "null", "-",
    ], capture_output=True, text=True)
    text = r.stderr or ""
    info = {"I": None, "TP": None, "LRA": None, "duration": None, "size": path.stat().st_size}
    # Parse the Summary: block (not the per-frame lines).
    tail = text
    if "Summary:" in text:
        tail = text[text.rfind("Summary:"):]
    for line in tail.splitlines():
        s = line.strip()
        if s.startswith("I:"):
            try:
                info["I"] = float(s.split()[1])
            except Exception:
                pass
        if s.startswith("LRA:"):
            try:
                info["LRA"] = float(s.split()[1])
            except Exception:
                pass
        if s.startswith("Peak:"):
            try:
                info["TP"] = float(s.split()[1])
            except Exception:
                pass
    # duration
    p = subprocess.run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=nw=1:nk=1", str(path),
    ], capture_output=True, text=True)
    try:
        info["duration"] = float(p.stdout.strip())
    except Exception:
        pass
    # video stream duration / frames
    p2 = subprocess.run([
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=nb_frames,r_frame_rate,width,height",
        "-of", "json", str(path),
    ], capture_output=True, text=True)
    try:
        st = json.loads(p2.stdout)["streams"][0]
        info["nb_frames"] = int(st.get("nb_frames") or 0)
        info["wh"] = (st.get("width"), st.get("height"))
    except Exception:
        pass
    info["log_tail"] = "\n".join(text.strip().splitlines()[-20:])
    return info



def trim_loudness(src: Path, meas: dict, log_stem: Path, target_i=-14.0, tol=0.35) -> dict:
    """If integrated loudness missed -14 by more than tol LU, apply a constant gain and re-encode audio."""
    I = meas.get("I")
    if I is None:
        return meas
    err = I - target_i  # positive = too loud
    if abs(err) <= tol:
        return meas
    gain = 10 ** ((target_i - I) / 20.0)
    tmp = src.with_name(src.stem + "_loud_trim.mp4")
    run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(src),
        "-c:v", "copy",
        "-af", f"volume={gain:.6f},alimiter=limit=0.8222:level=false,aresample={SR}",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart", str(tmp),
    ], log_stem.with_suffix(".trim.log"))
    # keep the missed-target encode; install the trimmed file as the master
    backup = src.with_name(src.stem + "_pre_trim.mp4")
    if not backup.exists():
        src.replace(backup)
    else:
        src.unlink()
    tmp.replace(src)
    meas2 = measure(src)
    meas2["trimmed_from_I"] = I
    meas2["trim_gain"] = gain
    meas2["pre_trim"] = str(backup)
    return meas2


def maybe_compress(src: Path, limit=25 * 1024 * 1024) -> Path | None:

    if src.stat().st_size <= limit:
        return None
    dest = src.with_name(src.stem + "_under25mb.mp4")
    # raise CRF until under limit, keep source
    for crf in (23, 26, 28, 30, 32):
        run([
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(src),
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", str(crf),
            "-preset", "medium", "-c:a", "aac", "-b:a", "128k",
            "-movflags", "+faststart", str(dest),
        ])
        if dest.stat().st_size <= limit:
            return dest
    return dest


def qa_boxes(spec: ShortSpec, all_boxes: list[list[Box]]) -> list[str]:
    fails = []
    for i, boxes in enumerate(all_boxes):
        v = violations(boxes)
        if v:
            t = i / FPS
            fails.append(f"{spec.sid} t={t:.3f}s frame={i}: " + " | ".join(v))
    return fails


def draw_guides(img: Image.Image) -> Image.Image:
    out = img.convert("RGBA")
    o = Image.new("RGBA", out.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(o)
    L, T, R, B = SAFE
    # unsafe regions in translucent red
    d.rectangle((0, 0, W, T), fill=(180, 30, 30, 70))
    d.rectangle((0, B, W, H), fill=(180, 30, 30, 70))
    d.rectangle((R, T, W, B), fill=(180, 30, 30, 70))
    d.rectangle((0, T, L, B), fill=(180, 30, 30, 70))
    # safe outline
    d.rectangle((L, T, R, B), outline=(40, 220, 90, 200), width=3)
    # official 25% line
    d.line((0, int(H * 0.75), W, int(H * 0.75)), fill=(255, 200, 0, 180), width=2)
    return Image.alpha_composite(out, o).convert("RGB")


def contact_sheet(specs: list[ShortSpec], frame_dirs: dict[str, Path], out: Path, qa_out: Path) -> None:
    # 3 rows x 6 key times
    picks_frac = [0.02, 0.08, 0.20, 0.50, 0.82, 0.98]
    cell_w, cell_h = 216, 384  # 1080x1920 / 5
    cols, rows = 6, len(specs)
    pad, label_h, head = 12, 36, 70
    sheet_w = cols * cell_w + (cols + 1) * pad
    sheet_h = head + rows * (cell_h + label_h + pad) + pad
    sheet = Image.new("RGB", (sheet_w, sheet_h), (18, 16, 14))
    qa_sheet = sheet.copy()
    d = ImageDraw.Draw(sheet)
    dq = ImageDraw.Draw(qa_sheet)
    title_f = font(CINZEL_REG, 22)
    lab_f = font(INTER, 14, weight=500)
    d.text((pad, 20), "UT99 Bot Yearbook Shorts — Phase 1 tests  ·  1080×1920", font=title_f, fill=GOLD_HI)
    dq.text((pad, 20), "Safe-zone QA  ·  red = avoid (top bar, right UI, bottom 25%)  ·  green = text box", font=title_f, fill=GOLD_HI)
    for r, spec in enumerate(specs):
        fd = frame_dirs[spec.sid]
        frames = sorted(fd.glob("*.jpg"))
        n = max(1, len(frames))
        y0 = head + r * (cell_h + label_h + pad)
        d.text((pad, y0), f"{spec.sid}  {spec.filename}  planned {spec.planned_s:.1f}s", font=lab_f, fill=CREAM)
        dq.text((pad, y0), f"{spec.sid}  {spec.filename}", font=lab_f, fill=CREAM)
        y1 = y0 + label_h
        for c, frac in enumerate(picks_frac):
            i = min(n - 1, max(0, int(frac * (n - 1))))
            im = Image.open(frames[i]).convert("RGB")
            thumb = im.resize((cell_w, cell_h), Image.Resampling.LANCZOS)
            x = pad + c * (cell_w + pad)
            sheet.paste(thumb, (x, y1))
            qa_sheet.paste(draw_guides(im).resize((cell_w, cell_h), Image.Resampling.LANCZOS), (x, y1))
    sheet.save(out, "PNG")
    qa_sheet.save(qa_out, "PNG")


def write_sidecar(spec: ShortSpec, mp4: Path, meas: dict) -> None:
    txt = mp4.with_suffix(".txt")
    lines = [
        f"id: {spec.sid}",
        f"file: {mp4.name}",
        f"title: {spec.title}",
        f"concept: {spec.concept}",
        f"planned_s: {spec.planned_s:.3f}",
        f"measured_s: {meas.get('duration')}",
        f"size_bytes: {meas.get('size')}",
        f"loudness_I_LUFS: {meas.get('I')}",
        f"true_peak_dBTP: {meas.get('TP')}",
        f"LRA: {meas.get('LRA')}",
        f"bots: " + ", ".join(f"#{b['number']:02d} {official_name(b)} {alias_as(b)}".strip() for b in spec.bots),
        f"credit: {EPIC}",
    ]
    txt.write_text("\n".join(lines) + "\n")


def is_finished(spec: ShortSpec, out_dir: Path) -> bool:
    mp4 = out_dir / spec.filename
    side = mp4.with_suffix(".txt")
    qa = QA / f"{spec.sid}_textbox_qa.txt"
    if not mp4.is_file() or mp4.stat().st_size < 100_000:
        return False
    if not side.is_file() or not qa.is_file():
        return False
    if not qa.read_text().lstrip().startswith("OK"):
        return False
    txt = side.read_text()
    if "loudness_I_LUFS:" not in txt or "loudness_I_LUFS: None" in txt:
        return False
    return True


def assemble_one(spec: ShortSpec, out_dir: Path | None = None) -> dict:
    out_dir = out_dir or SHORTS_FINAL
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"== {spec.sid} {spec.filename} planned {spec.planned_s:.2f}s ==")
    if spec.planned_s > 60:
        raise RuntimeError(f"{spec.sid} planned {spec.planned_s:.2f}s exceeds 60 s")
    framedir = WORK / spec.sid / "frames"
    framedir.mkdir(parents=True, exist_ok=True)
    boxes = render_frames(spec, framedir)
    fails = qa_boxes(spec, boxes)
    (QA / f"{spec.sid}_textbox_qa.txt").write_text(
        "\n".join(fails) if fails else f"OK  {len(boxes)} frames, all text boxes inside {SAFE}\n"
    )
    if fails:
        print(f"  QA FAIL {len(fails)} violations (first 5):")
        for line in fails[:5]:
            print("   ", line)
        # still encode so we can visually debug; report later
    wav = WORK / spec.sid / "mix.wav"
    mix_audio(spec, wav)
    out = out_dir / spec.filename
    ln = loudnorm_encode(framedir, wav, out, spec.planned_s, WORK / spec.sid / "ff")
    meas = measure(out)
    meas["loudnorm_pass1"] = ln
    meas = trim_loudness(out, meas, WORK / spec.sid / "ff")
    meas["qa_fails"] = len(fails)
    meas["qa_examples"] = fails[:8]
    compact = maybe_compress(out)
    meas["compressed"] = str(compact) if compact else None
    write_sidecar(spec, out, meas)
    # Keep a mid-short keyframe for the overview sheet; drop the rest to free disk.
    thumbs = SHORTS_FINAL / "keyframes"
    thumbs.mkdir(parents=True, exist_ok=True)
    kf_src = framedir / f"{int(3.0 * FPS):05d}.jpg"
    if not kf_src.is_file():
        jpgs = sorted(framedir.glob("*.jpg"))
        kf_src = jpgs[len(jpgs)//3] if jpgs else None
    if kf_src and kf_src.is_file():
        Image.open(kf_src).save(thumbs / f"{spec.sid}.jpg", "JPEG", quality=92)
    for oldf in framedir.glob("*.jpg"):
        oldf.unlink()
    print(f"  wrote {out}  {meas['size']} bytes  {meas.get('duration')}s  I={meas.get('I')} TP={meas.get('TP')}")
    return {"spec": spec, "boxes": boxes, "meas": meas, "framedir": framedir, "fails": fails}


def preview_stills(specs: list[ShortSpec]) -> None:
    """Write a handful of stills for visual typography QA before a full encode."""
    dest = QA / "preview_stills"
    dest.mkdir(parents=True, exist_ok=True)
    for spec in specs:
        # first still, team/title still, first bot, end
        evs = spec.events
        stills = [(e, e.still, e.still_boxes) for e in evs if e.kind == "still" and e.still is not None]
        for i, (e, im, boxes) in enumerate(stills[:3]):
            p = dest / f"{spec.sid}_still{i}.png"
            im.save(p)
            draw_guides(im).save(dest / f"{spec.sid}_still{i}_guides.png")
        # one bot / alias frame
        for e in evs:
            if e.kind == "clip":
                im, boxes = bot_clip_frame(e.bot, Image.open(clip_frames(e.bot)[12 if len(clip_frames(e.bot)) > 12 else 0]))
                im.save(dest / f"{spec.sid}_bot_{e.bot['number']:03d}.png")
                draw_guides(im).save(dest / f"{spec.sid}_bot_{e.bot['number']:03d}_guides.png")
                print("preview", spec.sid, official_name(e.bot), "violations", violations(boxes))
                break
            if e.kind == "alias":
                im, boxes = alias_still(e.bot, "alias")
                im.save(dest / f"{spec.sid}_alias_{e.bot['number']:03d}.png")
                draw_guides(im).save(dest / f"{spec.sid}_alias_{e.bot['number']:03d}_guides.png")
                print("preview", spec.sid, official_name(e.bot), alias_as(e.bot), "violations", violations(boxes))
                break
        end = [e for e in evs if e.kind == "still" and e.still is not None][-2]  # end card before loop
        if end.still:
            end.still.save(dest / f"{spec.sid}_end.png")
            draw_guides(end.still).save(dest / f"{spec.sid}_end_guides.png")
            print("preview end", spec.sid, "violations", violations(end.still_boxes))



def _meas_from_sidecar(mp4: Path) -> dict:
    side = mp4.with_suffix(".txt")
    meas = {"duration": None, "size": mp4.stat().st_size if mp4.is_file() else None,
            "I": None, "TP": None, "LRA": None, "qa_fails": 0, "qa_examples": []}
    if not side.is_file():
        return meas
    for line in side.read_text().splitlines():
        key, _, raw = line.partition(":")
        raw = raw.strip()
        key = key.strip()
        if key in ("duration_s", "measured_s") and raw:
            try:
                meas["duration"] = float(raw)
            except ValueError:
                pass
        elif key == "loudness_I_LUFS":
            try:
                meas["I"] = float(raw)
            except ValueError:
                meas["I"] = None
        elif key in ("loudness_TP_dBTP", "true_peak_dBTP"):
            try:
                meas["TP"] = float(raw)
            except ValueError:
                meas["TP"] = None
        elif key in ("loudness_LRA", "LRA"):
            try:
                meas["LRA"] = float(raw)
            except ValueError:
                pass
        elif key == "size_bytes":
            try:
                meas["size"] = int(raw)
            except ValueError:
                pass
    qa = QA / f"{mp4.stem.split('_')[0].upper()}_textbox_qa.txt"
    # sid is S01 etc, filename is s01_thunder_crash.mp4 — recover from stem prefix
    sid = mp4.stem.split("_")[0].upper()
    qap = QA / f"{sid}_textbox_qa.txt"
    if qap.is_file():
        body = qap.read_text()
        if not body.lstrip().startswith("OK"):
            lines = [ln for ln in body.splitlines() if ln.strip()]
            meas["qa_fails"] = len(lines)
            meas["qa_examples"] = lines[:5]
    return meas


def _write_status(results: list[dict], skipped: list[str]) -> None:
    lines = ["# Shorts batch status (resume-friendly)", ""]
    done = 0
    for r in results:
        s = r["spec"]
        m = r["meas"]
        flag = "SKIP" if r.get("skipped") else ("FAIL" if m.get("qa_fails") else "OK")
        if flag in ("OK", "SKIP"):
            done += 1
        lines.append(
            f"- {flag}  {s.sid}  {s.filename}  planned {s.planned_s:.2f}s  "
            f"meas {m.get('duration')}s  I={m.get('I')}  TP={m.get('TP')}  "
            f"qa_fails={m.get('qa_fails')}  size={m.get('size')}"
        )
    lines.append("")
    lines.append(f"Finished in this run's list: {done}/{len(results)}. Skipped (already done): {len(skipped)}.")
    (SHORTS_FINAL / "STATUS.md").write_text("\n".join(lines) + "\n")


def write_metadata_file(specs: list[ShortSpec], out_dir: Path, measures: dict) -> None:
    link = "https://youtu.be/VIDEO_ID_PLACEHOLDER"
    parts: list[str] = []
    parts.append("# UT99 Bot Yearbook — YouTube Shorts metadata")
    parts.append("")
    parts.append(
        "Unofficial fan project. Unreal Tournament (1999) and its characters, "
        "names, likenesses, voice lines, meshes, textures, music and official "
        "text are © Epic Games, Inc. and Digital Extremes. Not affiliated with "
        "or endorsed by Epic Games or Digital Extremes."
    )
    parts.append("")
    parts.append(f"Main yearbook video (all 81 bots): {link}")
    parts.append("")
    parts.append(
        "Pinned comment (all Shorts): Full yearbook: all 81 bots. Comment your number — #1–#81."
    )
    parts.append("")
    for s in specs:
        bots_line = "  ".join(
            f"#{b['number']:02d} {official_name(b)}"
            + (f" {alias_as(b)}" if alias_as(b) else "")
            for b in s.bots
        )
        desc = "\n".join([
            s.title.split("|")[0].strip().rstrip(".") + ".",
            "",
            "Which number is yours? Comment it.",
            "",
            f"Full yearbook: all 81 bots, one video: {link}",
            "Unreal Tournament (1999) · GOTY · unofficial fan project.",
            "",
            bots_line,
            "",
            "Unreal Tournament © Epic Games, Inc. and Digital Extremes.",
            "Not affiliated with or endorsed by Epic Games or Digital Extremes.",
            "",
            "#UnrealTournament #UT99 #UT99Bots #Shorts #Yearbook",
        ])
        m = measures.get(s.sid) or {}
        meas = ""
        if m.get("duration") is not None:
            meas = (
                f"  ·  measured {m.get('duration')}s"
                f"  I={m.get('I')} LUFS  TP={m.get('TP')} dBTP"
            )
        parts.append(f"## {s.sid} — {s.filename}")
        parts.append("")
        parts.append(f"- Concept: {s.concept}")
        parts.append(f"- Planned: {s.planned_s:.2f}s{meas}")
        parts.append("- Title:")
        parts.append(f"  {s.title}")
        parts.append("- Description:")
        parts.append("```")
        parts.append(desc)
        parts.append("```")
        parts.append("- Hashtags: #UnrealTournament #UT99 #UT99Bots #Shorts #Yearbook")
        parts.append("")
    (out_dir / "shorts_metadata.md").write_text("\n".join(parts) + "\n")
    print("wrote", out_dir / "shorts_metadata.md")


def _grab_keyframe(spec: ShortSpec, framedir: Path) -> Image.Image | None:
    """A representative mid-body / mid-short frame, falling back to the mp4."""
    # Prefer a filled body frame (clip) around the first bot, else mid sequence.
    thumb = SHORTS_FINAL / "keyframes" / f"{spec.sid}.jpg"
    if thumb.is_file():
        return Image.open(thumb).convert("RGB")
    if framedir.is_dir():
        frames = sorted(framedir.glob("*.jpg")) or sorted(framedir.glob("f*.png"))
        if frames:
            idx = min(len(frames) - 1, max(0, int(3.0 * FPS)))
            return Image.open(frames[idx]).convert("RGB")
    mp4 = SHORTS_FINAL / spec.filename
    if mp4.is_file():
        tmp = WORK / f"kf_{spec.sid}.png"
        tmp.parent.mkdir(parents=True, exist_ok=True)
        # ~3s in, after the hook
        cmd = [
            "ffmpeg", "-y", "-ss", "3.0", "-i", str(mp4),
            "-frames:v", "1", "-q:v", "2", str(tmp),
        ]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode == 0 and tmp.is_file():
            return Image.open(tmp).convert("RGB")
    return None


def write_overview_sheet(specs: list[ShortSpec], out_dir: Path, measures: dict) -> None:
    """21 key frames + a before/after of the fill fix."""
    thumbs: list[tuple[str, Image.Image]] = []
    for s in specs:
        im = _grab_keyframe(s, WORK / s.sid / "frames")
        if im is None:
            # placeholder
            im = Image.new("RGB", (W, H), (16, 12, 10))
        thumbs.append((s.sid, im))

    before_after = None
    ba_path = SHORTS_FINAL / "fill_fix_before_after.png"
    if not ba_path.is_file():
        ba_path = WORK / "fill_preview" / "pair_n004.jpg"
    if not ba_path.is_file():
        # regenerate a compact before/after from Malcom frame 0
        try:
            b = BOTS[4]
            frames = clip_frames(b)
            src = Image.open(frames[0]).convert("RGB")
            left = plate_34_legacy(src)
            right = plate_fill(src)
            # side by side
            pair = Image.new("RGB", (W * 2, H), (0, 0, 0))
            pair.paste(left, (0, 0))
            pair.paste(right, (W, 0))
            d = ImageDraw.Draw(pair)
            d.rectangle((20, 40, 420, 140), fill=(8, 6, 5))
            d.text((36, 60), "BEFORE", font=font(TEKTUR, 36), fill=GOLD)
            d.rectangle((W + 20, 40, W + 420, 140), fill=(8, 6, 5))
            d.text((W + 36, 60), "AFTER", font=font(TEKTUR, 36), fill=GOLD)
            ba_path.parent.mkdir(parents=True, exist_ok=True)
            pair.save(ba_path, quality=92)
            before_after = pair
        except Exception as e:
            print("before/after regen failed:", e)
            before_after = None
    else:
        before_after = Image.open(ba_path).convert("RGB")

    # Layout: 7 columns x 3 rows of 21 thumbs, then a full-width before/after row.
    cols, rows = 7, 3
    tw, th = 180, 320  # 1080x1920 scaled
    pad = 16
    label_h = 36
    header_h = 80
    ba_h = int(tw * 2 * (H / (W * 2))) + 40  # before/after is 2x width
    sheet_w = pad + cols * (tw + pad)
    sheet_h = header_h + rows * (th + label_h + pad) + pad + ba_h + 60
    sheet = Image.new("RGB", (sheet_w, sheet_h), (12, 10, 9))
    d = ImageDraw.Draw(sheet)
    d.text((pad, 22), "UT99 Bot Yearbook  ·  Shorts S01–S21  ·  fill-fix overview",
           font=font(TEKTUR, 22), fill=CREAM)

    for i, (sid, im) in enumerate(thumbs):
        r, c = divmod(i, cols)
        x = pad + c * (tw + pad)
        y = header_h + r * (th + label_h + pad)
        thumb = im.resize((tw, th), Image.Resampling.LANCZOS)
        sheet.paste(thumb, (x, y))
        d.text((x, y + th + 4), sid, font=font(TEKTUR, 16), fill=GOLD_HI)

    # before/after strip at the bottom, scaled to sheet width minus pad
    by = header_h + rows * (th + label_h + pad) + 8
    d.text((pad, by), "Fill fix  ·  #04 Malcom  ·  before (letterbox band)  |  after (full-bleed + blur sides)",
           font=font(INTER, 16), fill=GOLD)
    by += 28
    if before_after is not None:
        ba_w = sheet_w - 2 * pad
        ba_hh = int(ba_w * before_after.height / before_after.width)
        ba = before_after.resize((ba_w, ba_hh), Image.Resampling.LANCZOS)
        sheet.paste(ba, (pad, by))

    dest = out_dir / "shorts_overview_sheet.png"
    sheet.save(dest, "PNG")
    print("wrote", dest, sheet.size)


def main(argv: list[str]) -> int:
    load_catalog()
    TEST.mkdir(parents=True, exist_ok=True)
    WORK.mkdir(parents=True, exist_ok=True)
    QA.mkdir(parents=True, exist_ok=True)
    SHORTS_FINAL.mkdir(parents=True, exist_ok=True)
    args = argv[1:]
    specs = all_specs()
    if args[:1] == ["preview"]:
        preview_stills(test_specs())
        return 0
    if args[:1] == ["--only"]:
        want = {a.upper() for a in args[1:]}
        specs = [s for s in specs if s.sid in want]
    for s in specs:
        print(f"spec {s.sid}: {s.planned_s:.2f}s  {len(s.events)} events  {len(s.bots)} bots")
        if s.planned_s > 60:
            print(f"  ERROR planned duration {s.planned_s:.2f}s > 60")
            return 2

    results: list[dict] = []
    skipped: list[str] = []
    any_fail = False
    for s in specs:
        if is_finished(s, SHORTS_FINAL):
            print(f"SKIP {s.sid} already finished in {SHORTS_FINAL / s.filename}")
            skipped.append(s.sid)
            results.append({
                "spec": s,
                "framedir": WORK / s.sid / "frames",
                "meas": _meas_from_sidecar(SHORTS_FINAL / s.filename),
                "fails": [],
                "skipped": True,
            })
            continue
        try:
            r = assemble_one(s, SHORTS_FINAL)
            r["skipped"] = False
            results.append(r)
            if r["meas"].get("qa_fails"):
                any_fail = True
        except Exception as e:
            print(f"ERROR {s.sid}: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            results.append({
                "spec": s,
                "framedir": WORK / s.sid / "frames",
                "meas": {"qa_fails": -1, "qa_examples": [f"exception: {e}"],
                         "duration": None, "I": None, "TP": None, "size": None},
                "fails": [str(e)],
                "skipped": False,
            })
            any_fail = True
        _write_status(results, skipped)

    measures = {r["spec"].sid: r["meas"] for r in results}
    for s in all_specs():
        if s.sid not in measures and is_finished(s, SHORTS_FINAL):
            measures[s.sid] = _meas_from_sidecar(SHORTS_FINAL / s.filename)

    write_metadata_file(all_specs(), SHORTS_FINAL, measures)
    try:
        write_overview_sheet(all_specs(), SHORTS_FINAL, measures)
    except Exception as e:
        print("overview sheet deferred:", type(e).__name__, e)

    summary = []
    for r in results:
        m = r["meas"]
        summary.append({
            "id": r["spec"].sid,
            "file": str(SHORTS_FINAL / r["spec"].filename),
            "planned_s": r["spec"].planned_s,
            "measured_s": m.get("duration"),
            "size": m.get("size"),
            "I": m.get("I"),
            "TP": m.get("TP"),
            "LRA": m.get("LRA"),
            "qa_fails": m.get("qa_fails"),
            "qa_examples": m.get("qa_examples"),
            "skipped": r.get("skipped"),
        })
    (QA / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    (SHORTS_FINAL / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    return 1 if any_fail else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
