"""Assemble the Vol. 4 540p animatic: cold open + cards + 8 skits + end card + stinger.
Rough level-match (~-14 LUFS). Final two-pass loudnorm is for later, not this file.
python3 assemble_episode.py
"""
import json, os, subprocess, wave
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

ROOT = Path('/workspace/ut99/render/lvps/v4')
OUTDIR = ROOT / 'animatic'
GFX = OUTDIR / 'gfx'
TMP = OUTDIR / 'tmp'
OUTDIR.mkdir(parents=True, exist_ok=True)
GFX.mkdir(exist_ok=True)
TMP.mkdir(exist_ok=True)

W, H, FPS, SR = 960, 540, 30, 48000
FONT = '/usr/share/fonts/truetype/sand-box/google/Russo One/RussoOne-Regular.ttf'
FONT2 = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
ASSEMBLE = '/workspace/ut99/pipeline/tools/blender/assemble_skit.py'
PREPARE = '/workspace/ut99/assets/sounds/voices/Announcer/(All).prepare.wav'
WINNER = '/workspace/ut99/assets/sounds/voices/Announcer/(All).winner.wav'
STING = '/workspace/ut99/assets/sounds/Botpack/ASMD.TazerSelect.wav'

# Verified by faster-whisper this session:
#   prepare: "Prepare for battle!" (1.991 s)
#   winner:  "Congratulations! You are the winner!" (3.019 s)

SKITS = [
    ('skit1', 'skit1', '"You like that?"', 'Ivana'),
    ('skit2', 'skit2', '"Learn how to aim!"', 'Isis'),
    ('skit3', 'skit3', '"Hey! Same team!"', 'Whitman'),
    ('skit4', 'skit4', '"Medic!"', 'Brock'),
    ('skit5', 'skit5', '"And stay down."', 'Idina'),
    ('skit6', 'skit6', '"Bite me!"', 'Kregore'),
    ('skit7', 'skit7', '"I am superior."', 'Xan'),
    ('skit8', 'skit8', '"See ya!"', 'Lauren'),
]

CLIPS = [
    # (mp4, start, dur) punchlines for the VHS cold open
    ('/workspace/ut99/render/lvps/skit1/skit1_sit_down_1080p.mp4', 2.85, 1.15),
    ('/workspace/ut99/render/lvps/vol2/skit1/final_v1/skit1_toasted_1080p.mp4', 3.30, 1.15),
    ('/workspace/ut99/render/lvps/vol3/skit1/final_v1/skit1_tag_1080p.mp4', 3.35, 1.15),
    # glued repeat of "Sit down!" — the tape sticks
    ('/workspace/ut99/render/lvps/skit1/skit1_sit_down_1080p.mp4', 2.85, 1.00),
]


def run(cmd, cwd=None):
    print('>>', ' '.join(str(c) for c in cmd)[:300], flush=True)
    subprocess.run(cmd, check=True, cwd=cwd)


def dur(p):
    return float(subprocess.run(
        ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', str(p)],
        capture_output=True, text=True, check=True).stdout.strip())


def font(path, size):
    return ImageFont.truetype(path if os.path.exists(path) else FONT2, size)


def card(path, title, sub='', footer='', bg=(8, 8, 12)):
    im = Image.new('RGB', (W, H), bg)
    d = ImageDraw.Draw(im)
    # grain
    import random
    rnd = random.Random(3)
    px = im.load()
    for i in range(4000):
        x, y = rnd.randint(0, W - 1), rnd.randint(0, H - 1)
        j = rnd.randint(-18, 18)
        r, g, b = px[x, y]
        px[x, y] = (max(0, min(255, r + j)),) * 3
    f1, f2, f3 = font(FONT, 42), font(FONT, 22), font(FONT2, 16)
    # title
    bbox = d.textbbox((0, 0), title, font=f1)
    tw = bbox[2] - bbox[0]
    d.text(((W - tw) / 2, H * 0.38), title, font=f1, fill=(240, 240, 245))
    if sub:
        bbox = d.textbbox((0, 0), sub, font=f2)
        tw = bbox[2] - bbox[0]
        d.text(((W - tw) / 2, H * 0.52), sub, font=f2, fill=(200, 180, 80))
    if footer:
        bbox = d.textbbox((0, 0), footer, font=f3)
        tw = bbox[2] - bbox[0]
        d.text(((W - tw) / 2, H * 0.78), footer, font=f3, fill=(140, 140, 150))
    im.save(path)
    return path


def still_bg(path, duration, audio=None, audio_delay=0.0, audio_gain=0):
    """Make a video of a still card, optional delayed sound."""
    out = str(path) + '.mp4'
    cmd = ['ffmpeg', '-hide_banner', '-y', '-loop', '1', '-i', str(path),
           '-f', 'lavfi', '-i', f'anullsrc=r={SR}:cl=stereo']
    maps = ['-map', '0:v', '-map', '1:a']
    af = f'atrim=0:{duration},aformat=sample_fmts=s16:channel_layouts=stereo'
    if audio:
        cmd += ['-i', str(audio)]
        g = 10 ** (audio_gain / 20)
        delay = int(audio_delay * 1000)
        af = (f'[1:a]atrim=0:{duration},aformat=sample_fmts=s16:channel_layouts=stereo,volume=0[base];'
              f'[2:a]aformat=sample_fmts=s16:channel_layouts=stereo,volume={g},adelay={delay}|{delay},'
              f'apad=pad_dur={duration}[ann];[base][ann]amix=inputs=2:normalize=0:duration=first,atrim=0:{duration}[aout]')
        maps = ['-filter_complex', af, '-map', '0:v', '-map', '[aout]']
        af = None
    v = ['-c:v', 'libx264', '-preset', 'veryfast', '-crf', '22', '-pix_fmt', 'yuv420p',
         '-r', str(FPS), '-t', str(duration), '-s', f'{W}x{H}']
    a = ['-c:a', 'aac', '-b:a', '192k', '-ar', str(SR), '-ac', '2']
    if af and audio is None:
        cmd += v + ['-filter_complex', f'[1:a]{af}[aout]', '-map', '0:v', '-map', '[aout]'] + a + [out]
    elif audio:
        cmd += v + maps + a + [out]
    else:
        cmd += v + maps + ['-af', af] + a + [out]
    run(cmd)
    return out


def build_coldopen():
    """~6 s previously-on VHS + stuck punchline + title + Prepare for battle!"""
    parts = []
    # 0.7s previously-on card
    prev = GFX / 'previously.png'
    card(prev, 'PREVIOUSLY ON', 'LITERAL VOICE PACK', 'Vol. 1  ·  Vol. 2  ·  Vol. 3')
    parts.append(still_bg(prev, 0.70))

    def vhs_clip(src, ss, length, name, glitch=False):
        out = TMP / f'{name}.mp4'
        vf = (f'scale={W}:{H}:force_original_aspect_ratio=decrease,'
              f'pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,'
              f'eq=contrast=1.08:saturation=0.85:brightness=-0.02,'
              f'noise=alls=8:allf=t+u,format=yuv420p')
        if glitch:
            vf += ',hue=s=0.4,rgbashift=rh=3:bv=-3'
        run(['ffmpeg', '-hide_banner', '-y', '-ss', str(ss), '-t', str(length), '-i', src,
             '-f', 'lavfi', '-i', f'anullsrc=r={SR}:cl=stereo',
             '-vf', vf, '-af', f'atrim=0:{length},volume=1.1',
             '-map', '0:v', '-map', '1:a',
             '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '22', '-pix_fmt', 'yuv420p',
             '-c:a', 'aac', '-ar', str(SR), '-ac', '2', '-t', str(length), str(out)])
        # keep original audio of the punchline too, mixed
        out2 = TMP / f'{name}_mix.mp4'
        run(['ffmpeg', '-hide_banner', '-y', '-i', str(out), '-ss', str(ss), '-t', str(length), '-i', src,
             '-filter_complex',
             f'[0:v]setsar=1[v];[1:a]aformat=channel_layouts=stereo,atrim=0:{length},volume=1.2[a]',
             '-map', '[v]', '-map', '[a]',
             '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '22', '-pix_fmt', 'yuv420p',
             '-c:a', 'aac', '-ar', str(SR), '-t', str(length), str(out2)])
        return str(out2)

    parts.append(vhs_clip(CLIPS[0][0], CLIPS[0][1], CLIPS[0][2], 'vhs_sit'))
    parts.append(vhs_clip(CLIPS[1][0], CLIPS[1][1], CLIPS[1][2], 'vhs_toast'))
    parts.append(vhs_clip(CLIPS[2][0], CLIPS[2][1], CLIPS[2][2], 'vhs_tag'))
    parts.append(vhs_clip(CLIPS[3][0], CLIPS[3][1], CLIPS[3][2], 'vhs_sit_glitch', glitch=True))

    title = GFX / 'title.png'
    card(title, 'VOL. 4', 'THE FINAL EPISODE', 'Literal Voice Pack Skits')
    # title + prepare (1.991 s). Card is 2.15 s so the line fits.
    parts.append(still_bg(title, 2.15, audio=PREPARE, audio_delay=0.08, audio_gain=3))

    # concat
    lst = TMP / 'cold.txt'
    lst.write_text(''.join(f"file '{os.path.abspath(p)}'\n" for p in parts))
    out = OUTDIR / 'coldopen.mp4'
    run(['ffmpeg', '-hide_banner', '-y', '-f', 'concat', '-safe', '0', '-i', str(lst),
         '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '22', '-pix_fmt', 'yuv420p',
         '-c:a', 'aac', '-ar', str(SR), '-ac', '2', '-movflags', '+faststart', str(out)])
    print('COLDOPEN', out, 'dur', dur(out))
    return str(out)


def assemble_skit(piece):
    work = ROOT / 'work' / f'animatic_{piece}'
    frames = work / 'frames'
    tl = work / 'timeline.json'
    out = OUTDIR / f'{piece}.mp4'
    n = len(list(frames.glob('*.png'))) if frames.exists() else 0
    print('ASSEMBLE', piece, 'frames', n, 'timeline', tl.exists())
    if n < 10 or not tl.exists():
        raise SystemExit(f'missing frames/timeline for {piece}: frames={n}')
    run(['python3', ASSEMBLE, str(work), str(out)])
    return str(out)


def level_match(src, dst, I=-14, TP=-1.5):
    """Single-pass loudnorm — rough watchable level, not the final two-pass master."""
    run(['ffmpeg', '-hide_banner', '-y', '-i', src,
         '-af', f'loudnorm=I={I}:LRA=11:TP={TP}',
         '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-ar', str(SR), '-ac', '2', dst])
    return dst


def build_endcard():
    p = GFX / 'endcard.png'
    im = Image.new('RGB', (W, H), (6, 6, 8))
    d = ImageDraw.Draw(im)
    f1, f2, f3 = font(FONT, 36), font(FONT2, 18), font(FONT2, 14)
    for text, f, y, col in (
        ("LITERAL VOICE PACK", f1, 0.28, (240, 240, 245)),
        ("THAT'S A WRAP", f1, 0.42, (200, 180, 80)),
        ('The Final Episode', f2, 0.56, (180, 180, 190)),
        ('Unreal Tournament (c) Epic Games and Digital Extremes. Fan work.', f3, 0.78, (140, 140, 150)),
    ):
        bbox = d.textbbox((0, 0), text, font=f)
        tw = bbox[2] - bbox[0]
        d.text(((W - tw) / 2, H * y), text, font=f, fill=col)
    im.save(p)
    # 5 s, winner at 0.35 s (3.019 s line)
    return still_bg(p, 5.0, audio=WINNER, audio_delay=0.35, audio_gain=3)


def main():
    cold = build_coldopen()
    skit_mp4s = []
    for piece, _, line, who in SKITS:
        raw = assemble_skit(piece)
        lm = str(OUTDIR / f'{piece}_lm.mp4')
        level_match(raw, lm)
        skit_mp4s.append((lm, line, who))

    stinger_raw = assemble_skit('stinger')
    stinger = str(OUTDIR / 'stinger_lm.mp4')
    level_match(stinger_raw, stinger)

    end = build_endcard()
    # cards
    card_files = []
    for i, (_, _, line, who) in enumerate(SKITS, 1):
        p = GFX / f'card_{i}.png'
        card(p, line, who, f'Skit {i} of 8')
        card_files.append(still_bg(p, 1.20))

    # concat list: cold, then (card, skit) x 8, end, stinger
    pieces = [cold]
    for c, (s, _, _) in zip(card_files, skit_mp4s):
        pieces += [c, s]
    pieces += [end, stinger]

    lst = TMP / 'episode.txt'
    # concat demuxer needs identical codecs; re-encode everything to a common stream first
    common = []
    for i, p in enumerate(pieces):
        o = TMP / f'p{i:02d}.mp4'
        run(['ffmpeg', '-hide_banner', '-y', '-i', p,
             '-vf', f'scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,fps={FPS},format=yuv420p,setsar=1',
             '-af', f'aresample={SR},aformat=sample_fmts=fltp:channel_layouts=stereo',
             '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '22',
             '-c:a', 'aac', '-b:a', '192k', '-ar', str(SR), '-ac', '2',
             str(o)])
        common.append(o)
    lst.write_text(''.join(f"file '{o.resolve()}'\n" for o in common))
    raw = OUTDIR / 'episode_raw.mp4'
    run(['ffmpeg', '-hide_banner', '-y', '-f', 'concat', '-safe', '0', '-i', str(lst),
         '-c', 'copy', str(raw)])
    # rough episode loudnorm (single pass). Finals will get the two-pass -14 / -1.5 later.
    out = OUTDIR / 'lvps_v4_animatic_540p.mp4'
    run(['ffmpeg', '-hide_banner', '-y', '-i', str(raw),
         '-af', 'loudnorm=I=-14:LRA=11:TP=-1.5',
         '-c:v', 'libx264', '-preset', 'medium', '-crf', '21', '-pix_fmt', 'yuv420p',
         '-c:a', 'aac', '-b:a', '192k', '-ar', str(SR), '-ac', '2',
         '-movflags', '+faststart', str(out)])
    print('EPISODE', out, 'bytes', out.stat().st_size, 'dur', dur(out))
    # measure
    run(['ffmpeg', '-hide_banner', '-i', str(out), '-af', 'loudnorm=I=-14:TP=-1.5:print_format=summary',
         '-f', 'null', '-'], )


if __name__ == '__main__':
    main()
