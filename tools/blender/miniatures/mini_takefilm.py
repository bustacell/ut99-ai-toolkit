r"""Assemble the MINIATURES single take: rendered frames + museum labels + songs, then credits.

  python mini_takefilm.py draft|master [--src FRAMES_DIR]
Reads output\work\miniatures\take_timeline.json and <src>\####.png (missing frames hold the last one, so a draft
works mid-render). draft: 1920x1080 -> output\miniatures_draft.mp4; master: 3840x2160 (Lanczos, type drawn at 4K),
-14 LUFS -> output\miniatures.mp4 + output\miniatures_1080p.mp4.

Music: UT's title theme over the opening, then each model's own song from the moment the camera arrives (crossfaded;
consecutive models with the same song share one stretch), the menu music over the finale and the credits.
"""
import argparse
import json
import os
import subprocess

from PIL import Image, ImageDraw, ImageFilter

import mini_film as MF
import mini_type as T
import prev

FPS = 24
END_S = 9.0
from paths import FRAMES, OUT  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('mode', choices=['draft', 'master'])
    ap.add_argument('--src', default=FRAMES, help='frame folder (default: paths.FRAMES)')
    o = ap.parse_args()
    W, H, K = (3840, 2160, 2) if o.mode == 'master' else (1920, 1080, 1)
    T.set_k(K)
    tl = json.load(open(os.path.join(prev.WORK, 'take_timeline.json')))
    src = o.src
    n_take = tl['check']['frames']
    total_s = n_take / FPS + END_S

    # ---------------------------------------------------------------- music
    segs = []
    first_arrive = tl['models'][0]['arrive']
    segs.append((0.0, 'Uttitle', first_arrive + 1.5, 0.0, 0.8, 2.0, 0.85))
    runs = []                                            # (song, start, end)
    for i, m in enumerate(tl['models']):
        start = m['arrive'] - 1.0
        end = (tl['models'][i + 1]['arrive'] - 1.0) if i + 1 < len(tl['models']) else tl['finale'] - 1.0
        if runs and runs[-1][0] == m['song']:
            runs[-1][2] = end
        else:
            runs.append([m['song'], start, end])
    for song, a, b in runs:
        segs.append((a, song, b - a + 1.6, None, 1.4, 1.8, 0.9))
    segs.append((tl['finale'] - 1.2, 'utmenu23', total_s - tl['finale'] + 1.2, 0.0, 1.8, 3.5, 0.9))
    wav = os.path.join(prev.WORK, f'take_{o.mode}.wav')
    MF.build_audio(segs, total_s, wav)

    # ---------------------------------------------------------------- video
    name = 'miniatures' if o.mode == 'master' else 'miniatures_draft'
    tmp = os.path.join(OUT, name + '_v.mp4')
    ff = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}',
                           '-r', str(FPS), '-i', '-', '-c:v', 'libx264', '-preset', 'slow',
                           '-crf', '16' if o.mode == 'master' else '20', '-pix_fmt', 'yuv420p', tmp],
                          stdin=subprocess.PIPE)
    black = Image.new('RGB', (W, H), (0, 0, 0))
    # soft lower-left scrim behind the museum labels (readable on bright models)
    sm = Image.new('L', (W // 8, H // 8), 0)
    ImageDraw.Draw(sm).ellipse((-W // 12, H // 8 - H // 14, W // 8 * 0.55, H // 8 + H // 10), fill=150)
    sm = sm.filter(ImageFilter.GaussianBlur(W // 70)).resize((W, H), Image.BICUBIC)
    scrim = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    scrim.putalpha(sm)
    last = None
    for f in range(1, n_take + 1):
        p = os.path.join(src, f'{f:04d}.png')
        if os.path.exists(p) and os.path.getsize(p) > 0:
            last = p
        fr = Image.open(last).convert('RGB').resize((W, H), Image.LANCZOS) if last else black.copy()
        if o.mode == 'master':
            fr = fr.filter(ImageFilter.UnsharpMask(radius=2, percent=35, threshold=2))
        t = f / FPS
        g = min(1.0, t / 1.2)                            # out of black at the start
        if g < 1:
            fr = Image.blend(black, fr, g)
        fr = fr.convert('RGBA')
        T.title(fr, t - tl['title'][0], t_out=tl['title'][1] - tl['title'][0])
        for i, m in enumerate(tl['models']):
            mode = T.MODES[m['map'].split('-')[0]]
            nice = m['map'].split('-', 1)[1]
            scale = int(round(m['span'] / 5.0) * 5)
            dur = min(6.5, m['skim_end'] - m['skim'] - 0.5)
            a = t - m['skim'] + 0.2
            sop = max(0.0, min(1.0, (a + 0.3) / 0.8, (dur + 1.4 - a) / 0.9))
            if sop > 0:
                s = scrim if sop >= 1 else Image.merge('RGBA', scrim.split()[:3] + (
                    scrim.split()[3].point(lambda v: int(v * sop)),))
                fr.alpha_composite(s)
            T.exhibit(fr, int((t - m['skim'] + 0.2) * FPS), i + 1, nice, mode, scale, t_in=0.0, t_out=dur)
        T.caption(fr, t - tl['finale'] - 1.5, 'TO SCALE', 'Every arena, side by side', t_out=6.5)
        ff.stdin.write(fr.convert('RGB').tobytes())
    for f in range(int(END_S * FPS)):
        fr = black.copy().convert('RGBA')
        MF.credits(fr, f / FPS)
        ff.stdin.write(fr.convert('RGB').tobytes())
    ff.stdin.close()
    ff.wait()
    final = os.path.join(OUT, name + '.mp4')
    af = 'loudnorm=I=-14:TP=-1.5:LRA=11' if o.mode == 'master' else 'loudnorm=I=-16:TP=-1.5'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', tmp, '-i', wav, '-map', '0:v', '-map', '1:a', '-c:v', 'copy',
                    '-af', af, '-ar', '48000', '-c:a', 'aac', '-b:a', '256k', '-shortest', final], check=True)
    os.remove(tmp)
    if o.mode == 'master':
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', final, '-vf', 'scale=1920:1080:flags=lanczos',
                        '-c:v', 'libx264', '-crf', '18', '-preset', 'slow', '-c:a', 'copy',
                        os.path.join(OUT, 'miniatures_1080p.mp4')], check=True)
    print('->', final, f'{total_s:.1f}s')


if __name__ == '__main__':
    main()
