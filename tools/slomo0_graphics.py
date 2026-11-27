"""Comment card for the slomo 0 intro: a captured YouTube comment on a rounded card with shadow (1920x1080 RGBA).

  python slomo0_graphics.py COMMENT_SCREENSHOT.png OUTDIR

Capture the comment in a browser at 2x page zoom (sharper text), crop to avatar + handle + text. The card keeps the
comment as captured (handle and avatar); ask the user whether to show them and consider telling the commenter.
The UI layer (slomo0_ui.py) animates the card (rise, marker sweep over the key words, typed "(> yes.").
"""
import os, sys
from PIL import Image, ImageDraw, ImageFilter

W, H = 1920, 1080


def comment_card(src, out, keep_h=0.62, keep_w=0.86):
    shot = Image.open(src).convert("RGB")
    w, h = shot.size
    shot = shot.crop((0, 0, int(w * keep_w), int(h * keep_h)))       # drop YouTube's Reply row and menu dots
    ImageDraw.Draw(shot).rectangle((15, 68, 70, shot.height), fill=(255, 255, 255))   # reply-thread line under the avatar
    scale = 1500 / shot.width
    shot = shot.resize((int(shot.width * scale), int(shot.height * scale)), Image.LANCZOS)
    pad = 48
    cw, ch = shot.width + 2 * pad, shot.height + 2 * pad
    card = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    m = Image.new("L", (cw, ch), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, cw - 1, ch - 1), radius=36, fill=255)
    bg = Image.new("RGBA", (cw, ch), (255, 255, 255, 255))
    bg.paste(shot, (pad, pad))
    card.paste(bg, (0, 0), m)
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    x, y = (W - cw) // 2, (H - ch) // 2
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle((x + 10, y + 22, x + cw + 10, y + ch + 22), radius=40, fill=(0, 0, 0, 170))
    canvas = Image.alpha_composite(canvas, shadow.filter(ImageFilter.GaussianBlur(28)))
    canvas.paste(card, (x, y), card)
    canvas.save(out)
    return out


if __name__ == "__main__":
    os.makedirs(sys.argv[2], exist_ok=True)
    print(comment_card(sys.argv[1], os.path.join(sys.argv[2], "comment_card.png")))
