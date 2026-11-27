"""Contact sheet of a clip: python sheet.py CLIP OUT.jpg t1 t2 ... [--cols 4] [--w 640] [--crop x,y,w,h]
Times in seconds; each tile is labelled with its time."""
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFont


def grab(clip, t, w, crop=None):
    vf = []
    if crop:
        x, y, cw, ch = crop
        vf.append(f"crop={cw}:{ch}:{x}:{y}")
    vf.append(f"scale={w}:-2")
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", f"{t:.3f}", "-i", clip, "-frames:v", "1",
           "-vf", ",".join(vf), "-f", "image2pipe", "-vcodec", "png", "-"]
    data = subprocess.run(cmd, capture_output=True).stdout
    if not data:
        return None
    import io
    return Image.open(io.BytesIO(data)).convert("RGB")


def main():
    a = sys.argv[1:]
    cols, w, crop = 4, 640, None
    if "--cols" in a:
        i = a.index("--cols"); cols = int(a[i + 1]); del a[i:i + 2]
    if "--w" in a:
        i = a.index("--w"); w = int(a[i + 1]); del a[i:i + 2]
    if "--crop" in a:
        i = a.index("--crop"); crop = [int(x) for x in a[i + 1].split(",")]; del a[i:i + 2]
    clip, out = a[0], a[1]
    times = [float(x) for x in a[2:]]
    tiles = []
    font = ImageFont.truetype("arial.ttf", 22)
    for t in times:
        im = grab(clip, t, w, crop)
        if im is None:
            continue
        d = ImageDraw.Draw(im)
        d.rectangle([4, 4, 96, 32], fill=(0, 0, 0))
        d.text((8, 6), f"{t:.2f}", fill=(255, 255, 0), font=font)
        tiles.append(im)
    if not tiles:
        print("no frames"); return
    tw, th = tiles[0].size
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new("RGB", (tw * cols, th * rows))
    for i, im in enumerate(tiles):
        sheet.paste(im, ((i % cols) * tw, (i // cols) * th))
    sheet.save(out, quality=88)
    print(out, sheet.size)


if __name__ == "__main__":
    main()
