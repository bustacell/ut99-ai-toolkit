"""Stills at every cut of the Vol. 2 episode + labelled contact sheet.  python tools/blender/compile/lvps2_cutsheet.py EP.mp4 CHAPTERS.json OUTDIR"""
import json, os, subprocess, sys
from PIL import Image, ImageDraw
mp4, cj, out = sys.argv[1:4]
os.makedirs(out, exist_ok=True)
j = json.load(open(cj)); c = j['cuts']; XD = j['xfade']; CARD = j['card']
T = [(0.4, 'cold open: VHS rewind'), (1.5, 'VHS rewind (Vol. 1 lever/cake)'), (2.6, 'title VOL. 2'), (4.2, 'title before star wipe')]
for k in ['1', '2', '3', '4', '5']:
    t = c[k]
    T += [(t + XD / 2, f'#{k} transition'), (t + XD + 0.6, f'#{k} title card'), (t + CARD + 0.5, f'#{k} skit start')]
T += [(c['end'] + XD / 2, 'into end card'), (c['end'] + 2.5, 'end card (Epic credit)'), (c['stinger'] - 0.2, 'black beat'),
      (c['stinger'] + 0.5, 'stinger'), (c['stinger'] + 2.3, 'stinger lights out')]
tw, th, cols = 480, 270, 5
rows = (len(T) + cols - 1) // cols
sheet = Image.new('RGB', (tw * cols, th * rows), (30, 30, 30))
for i, (t, lab) in enumerate(T):
    p = os.path.join(out, f'cut_{i:02d}_{t:06.2f}s.png')
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', f'{t:.3f}', '-i', mp4, '-frames:v', '1', p], check=True)
    im = Image.open(p).convert('RGB').resize((tw, th))
    d = ImageDraw.Draw(im); d.rectangle((0, 0, tw, 22), fill=(0, 0, 0)); d.text((5, 5), f'{t:.2f}s  {lab}', fill=(255, 220, 0))
    sheet.paste(im, ((i % cols) * tw, (i // cols) * th))
sheet.save(os.path.join(out, 'cut_sheet.png')); print(os.path.join(out, 'cut_sheet.png'), len(T), 'stills')
