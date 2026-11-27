#!/usr/bin/env python3
"""Vol. 4 540p stills animatic (board-o-matic) with real UT voice lines.

Cold open (VHS of Vol. 1-3 + stuck repeat + Prepare for battle!) ->
title cards + Ken-Burns stills for all 8 skits -> end card + winner -> stinger.

Rough level-match ~-14 LUFS. Final two-pass loudnorm is for later.
"""
import os, random, subprocess, wave
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageFilter

ROOT = Path('/workspace/ut99/render/lvps/v4')
STILLS = ROOT / 'stills'
OUT = ROOT / 'animatic'
GFX, TMP = OUT / 'gfx', OUT / 'tmp'
for d in (OUT, GFX, TMP):
    d.mkdir(parents=True, exist_ok=True)

W, H, FPS, SR = 960, 540, 30, 48000
FONT = '/usr/share/fonts/truetype/sand-box/google/Russo One/RussoOne-Regular.ttf'
FONT2 = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
PREPARE = '/workspace/ut99/assets/sounds/voices/Announcer/(All).prepare.wav'
WINNER = '/workspace/ut99/assets/sounds/voices/Announcer/(All).winner.wav'
# Listen/STT check this session (faster-whisper small.en):
#   prepare -> "Prepare for battle!" (1.991 s)
#   winner  -> "Congratulations! You are the winner!" (3.019 s)

# (path, offset_s, gain_db) — per-track gains so firebr (naturally quieter) is audible
MUS = {
    1: ('/workspace/ut99/assets/music/firebr.wav', 20.0, -1.0),
    2: ('/workspace/ut99/assets/music/Razor-ub.wav', 8.0, -8.0),
    3: ('/workspace/ut99/assets/music/Mission.wav', 8.0, -6.0),
    4: ('/workspace/ut99/assets/music/firebr.wav', 40.0, -1.0),
    5: ('/workspace/ut99/assets/music/Mission.wav', 30.0, -6.0),
    6: ('/workspace/ut99/assets/music/Razor-ub.wav', 30.0, -8.0),
    7: ('/workspace/ut99/assets/music/Mission.wav', 50.0, -6.0),
    8: ('/workspace/ut99/assets/music/SaveMe.wav', 4.0, -8.0),
}
VOICE = {
    1: ('/workspace/ut99/assets/sounds/voices/Female1Voice/(All).F1likethat.wav', 'You like that?', 'Ivana', 1.24),
    2: ('/workspace/ut99/assets/sounds/voices/Female2Voice/(All).F2aim.wav', 'Learn how to aim!', 'Isis', 1.02),
    3: ('/workspace/ut99/assets/sounds/voices/Male1Voice/(All).M1sameteam.wav', 'Hey! Same team!', 'Whitman', 1.51),
    4: ('/workspace/ut99/assets/sounds/voices/Male2Voice/(All).M2Medic.wav', 'Medic!', 'Brock', 1.04),
    5: ('/workspace/ut99/assets/sounds/voices/Female1Voice/(All).F1staydown.wav', 'And stay down.', 'Idina', 1.39),
    6: ('/workspace/ut99/assets/sounds/voices/Male2Voice/(All).M2biteme.wav', 'Bite me!', 'Kregore', 0.68),
    7: ('/workspace/ut99/assets/sounds/voices/BossVoice/(All).Bsuperior.wav', 'I am superior.', 'Xan', 1.56),
    8: ('/workspace/ut99/assets/sounds/voices/Female2Voice/(All).F2seeya.wav', 'See ya!', 'Lauren', 0.66),
}
# primary still, optional cutaway on the line
PIX = {
    1: (STILLS / 's1_ivana_coret_v2_profile.png', STILLS / 's1_ivana_coret_front.png'),
    2: (STILLS / 's2_isis_peak.png', None),
    3: (STILLS / 's3_whitman_overlord.png', None),
    4: (STILLS / 's4_brock_medic.png', None),
    5: (STILLS / 's5_idina_staydown.png', None),
    6: (STILLS / 's6_kregore_biteme.png', None),
    7: (STILLS / 's7_xan_gauntlet.png', None),
    8: (STILLS / 's8_lauren_morpheus_skyline.png', None),  # stay on the skyline; the portrait CU drops the towers
}


def run(cmd):
    print('>>', ' '.join(str(c) for c in cmd)[:280], flush=True)
    subprocess.run(cmd, check=True)


def dur(p):
    return float(subprocess.run(
        ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', str(p)],
        capture_output=True, text=True, check=True).stdout.strip())


def font(path, size):
    return ImageFont.truetype(path if os.path.exists(path) else FONT2, size)


def make_card(path, title, sub='', footer='', bg=(8, 8, 12)):
    im = Image.new('RGB', (W, H), bg)
    d = ImageDraw.Draw(im)
    rnd = random.Random(3)
    px = im.load()
    for _ in range(3500):
        x, y = rnd.randint(0, W - 1), rnd.randint(0, H - 1)
        j = rnd.randint(-16, 16)
        r, g, b = px[x, y]
        px[x, y] = (max(0, min(255, r + j)),) * 3
    f1, f2, f3 = font(FONT, 40), font(FONT, 22), font(FONT2, 15)
    def center(text, f, y, col):
        bbox = d.textbbox((0, 0), text, font=f)
        d.text(((W - (bbox[2] - bbox[0])) / 2, H * y), text, font=f, fill=col)
    center(title, f1, 0.36, (240, 240, 245))
    if sub:
        center(sub, f2, 0.52, (200, 180, 80))
    if footer:
        center(footer, f3, 0.80, (140, 140, 150))
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    im.save(path)
    return path


def burn_subs(src, dst, text, who, t0, t1, total):
    """ASS subtitle overlay, official typography."""
    ass = TMP / 'subs.ass'
    fn = 'DejaVu Sans'
    body = [
        '[Script Info]', 'ScriptType: v4.00+', f'PlayResX: {W}', f'PlayResY: {H}', '',
        '[V4+ Styles]',
        'Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, '
        'Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding',
        f'Style: Default,{fn},36,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,-1,0,0,0,100,100,0.5,0,1,3,1,2,30,30,32,1',
        f'Style: Who,{fn},20,&H00D0C0FF,&H00FFFFFF,&H00000000,&H64000000,-1,0,0,0,100,100,1,0,1,2,1,2,30,30,70,1',
        f'Style: Announcer,{fn},40,&H002020FF,&H00FFFFFF,&H00000000,&H00000000,-1,0,0,0,100,100,6,0,1,3,0,8,30,30,70,1',
        '', '[Events]',
        'Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text',
    ]
    def ts(t):
        h, rem = divmod(t, 3600)
        m, s = divmod(rem, 60)
        return f'{int(h)}:{int(m):02d}:{s:05.2f}'
    if who == 'Announcer':
        body.append(f"Dialogue: 0,{ts(t0)},{ts(t1)},Announcer,,0,0,0,,{{\\fad(60,200)}}{text}")
    else:
        body.append(f"Dialogue: 0,{ts(t0)},{ts(t1)},Default,,0,0,0,,{{\\fad(80,200)}}{text}")
        if who:
            body.append(f"Dialogue: 0,{ts(t0)},{ts(t1)},Who,,0,0,0,,{{\\fad(80,200)}}{who.upper()}")
    ass.write_text('\n'.join(body) + '\n')
    run(['ffmpeg', '-hide_banner', '-y', '-i', src,
         '-vf', f"subtitles={ass}:fontsdir=/usr/share/fonts/truetype/dejavu",
         '-c:a', 'copy', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '22',
         '-pix_fmt', 'yuv420p', dst])


def kenburns(img, seconds, out, zoom_end=1.08):
    frames = int(round(seconds * FPS))
    # scale up then zoompan
    run(['ffmpeg', '-hide_banner', '-y', '-loop', '1', '-i', str(img),
         '-vf', f"scale={W*2}:{H*2}:force_original_aspect_ratio=increase,crop={W*2}:{H*2},"
                f"zoompan=z='min(1+({zoom_end}-1)*on/{max(frames-1,1)},{zoom_end})':"
                f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={W}x{H}:fps={FPS}",
         '-frames:v', str(frames), '-an',
         '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '22', '-pix_fmt', 'yuv420p',
         str(out)])
    return out


def mix_av(video, out, length, music=None, voice=None, voice_t=3.2, voice_gain=4, music_gain=-18, duck_db=-9):
    """Mix optional looped/offset music (ducked under voice) + a delayed voice line onto a video."""
    cmd = ['ffmpeg', '-hide_banner', '-y', '-i', str(video)]
    filters = []
    mix = []
    idx = 1
    if music:
        if len(music) == 3:
            path, offset, mg = music
        else:
            path, offset = music
            mg = music_gain
        cmd += ['-ss', str(offset), '-t', str(length), '-i', str(path)]
        duck = 10 ** (duck_db / 20)
        # duck around the voice window
        if voice:
            vt, vd = voice_t, 1.8
            expr = f"if(between(t,{vt-0.08:.2f},{vt+vd:.2f}),{duck:.3f},1)"
            filters.append(
                f"[{idx}:a]aresample={SR},aformat=channel_layouts=stereo,volume={mg}dB,"
                f"volume='{expr}':eval=frame,atrim=0:{length},afade=t=out:st={length-0.8}:d=0.8[mus]")
        else:
            filters.append(
                f"[{idx}:a]aresample={SR},aformat=channel_layouts=stereo,volume={mg}dB,"
                f"atrim=0:{length},afade=t=out:st={length-0.8}:d=0.8[mus]")
        mix.append('[mus]')
        idx += 1
    if voice:
        path = voice
        cmd += ['-i', str(path)]
        delay = int(voice_t * 1000)
        filters.append(
            f"[{idx}:a]aresample={SR},aformat=channel_layouts=stereo,volume={voice_gain}dB,"
            f"adelay={delay}|{delay},apad=whole_dur={length}[voi]")
        mix.append('[voi]')
        idx += 1
    if not mix:
        cmd += ['-f', 'lavfi', '-i', f'anullsrc=r={SR}:cl=stereo']
        filters.append(f"[1:a]atrim=0:{length}[aout]")
    elif len(mix) == 1:
        filters.append(f"{mix[0]}atrim=0:{length}[aout]")
    else:
        filters.append(f"{''.join(mix)}amix=inputs={len(mix)}:normalize=0:duration=first,atrim=0:{length}[aout]")
    graph = ';'.join(filters)
    cmd += ['-filter_complex', graph, '-map', '0:v', '-map', '[aout]',
            '-t', str(length), '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '22',
            '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k', '-ar', str(SR), '-ac', '2', str(out)]
    run(cmd)
    return out


def still_hold(img, seconds, out, audio=None, audio_delay=0.0, audio_gain=3):
    """Static card with optional delayed sound."""
    cmd = ['ffmpeg', '-hide_banner', '-y', '-loop', '1', '-i', str(img),
           '-f', 'lavfi', '-t', str(seconds), '-i', f'anullsrc=r={SR}:cl=stereo']
    if audio:
        cmd += ['-i', str(audio)]
        delay = int(audio_delay * 1000)
        g = 10 ** (audio_gain / 20)
        cmd += ['-filter_complex',
                f'[1:a]atrim=0:{seconds}[base];'
                f'[2:a]aformat=channel_layouts=stereo,volume={g},adelay={delay}|{delay},'
                f'apad=whole_dur={seconds}[ann];'
                f'[base][ann]amix=inputs=2:normalize=0:duration=first,atrim=0:{seconds}[a]',
                '-map', '0:v', '-map', '[a]']
    else:
        cmd += ['-map', '0:v', '-map', '1:a']
    cmd += ['-t', str(seconds), '-s', f'{W}x{H}', '-r', str(FPS),
            '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '22', '-pix_fmt', 'yuv420p',
            '-c:a', 'aac', '-b:a', '192k', '-ar', str(SR), '-ac', '2', str(out)]
    run(cmd)
    return out


def vhs_clip(src, ss, length, name, glitch=False):
    out = TMP / f'{name}.mp4'
    vf = (f'scale={W}:{H}:force_original_aspect_ratio=decrease,'
          f'pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,'
          f'eq=contrast=1.08:saturation=0.85:brightness=-0.02,'
          f'noise=alls=8:allf=t+u,format=yuv420p,setsar=1')
    if glitch:
        vf += ',hue=s=0.45'
    run(['ffmpeg', '-hide_banner', '-y',
         '-ss', str(ss), '-t', str(length), '-i', src,
         '-vf', vf, '-af', f'atrim=0:{length},aformat=channel_layouts=stereo,volume=1.15',
         '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '22', '-pix_fmt', 'yuv420p',
         '-c:a', 'aac', '-ar', str(SR), '-ac', '2', '-t', str(length), str(out)])
    return out


def build_coldopen():
    parts = []
    prev = GFX / 'previously.png'
    make_card(prev, 'PREVIOUSLY ON', 'LITERAL VOICE PACK', 'Vol. 1  ·  Vol. 2  ·  Vol. 3')
    parts.append(Path(still_hold(prev, 0.70, TMP / 'prev.mp4')))
    clips = [
        ('/workspace/ut99/render/lvps/skit1/skit1_sit_down_1080p.mp4', 2.85, 1.15, 'vhs_sit', False),
        ('/workspace/ut99/render/lvps/vol2/skit1/final_v1/skit1_toasted_1080p.mp4', 3.30, 1.15, 'vhs_toast', False),
        ('/workspace/ut99/render/lvps/vol3/skit1/final_v1/skit1_tag_1080p.mp4', 3.35, 1.15, 'vhs_tag', False),
        ('/workspace/ut99/render/lvps/skit1/skit1_sit_down_1080p.mp4', 2.85, 1.00, 'vhs_sit_glitch', True),
    ]
    for src, ss, ln, name, g in clips:
        parts.append(vhs_clip(src, ss, ln, name, g))
    title = GFX / 'title.png'
    make_card(title, 'VOL. 4', 'THE FINAL EPISODE', 'Literal Voice Pack Skits')
    parts.append(Path(still_hold(title, 2.15, TMP / 'title.mp4', audio=PREPARE, audio_delay=0.08, audio_gain=3)))
    # announcer sub on the title beat — burn after concat of cold
    lst = TMP / 'cold.txt'
    # normalize each part first
    norm = []
    for i, p in enumerate(parts):
        o = TMP / f'cold_{i}.mp4'
        run(['ffmpeg', '-hide_banner', '-y', '-i', str(p),
             '-vf', f'scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,fps={FPS},format=yuv420p,setsar=1',
             '-af', f'aresample={SR},aformat=sample_fmts=fltp:channel_layouts=stereo',
             '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '22',
             '-c:a', 'aac', '-b:a', '192k', '-ar', str(SR), '-ac', '2', str(o)])
        norm.append(o)
    lst.write_text(''.join(f"file '{o.resolve()}'\n" for o in norm))
    raw = TMP / 'cold_raw.mp4'
    run(['ffmpeg', '-hide_banner', '-y', '-f', 'concat', '-safe', '0', '-i', str(lst), '-c', 'copy', str(raw)])
    out = OUT / 'coldopen.mp4'
    # Prepare for battle! starts ~0.70+1.15*3+1.00 = 5.15, plus title delay 0.08
    t0 = 0.70 + 1.15 * 3 + 1.00 + 0.08
    burn_subs(str(raw), str(out), 'Prepare for battle!', 'Announcer', t0, t0 + 1.991, dur(raw))
    print('COLDOPEN', out, 'dur', dur(out))
    return out


def build_skit(n):
    wide, cut = PIX[n]
    if not wide.exists():
        raise SystemExit(f'missing still {wide}')
    line, who, vdur, vpath = VOICE[n][1], VOICE[n][2], VOICE[n][3], VOICE[n][0]
    T = 3.20  # voice start inside the skit picture
    if cut and cut.exists():
        pre, post = T + 0.15, 5.2
        a = TMP / f'skit{n}_a.mp4'
        b = TMP / f'skit{n}_b.mp4'
        kenburns(wide, pre, a, 1.06)
        kenburns(cut, post, b, 1.10)
        lst = TMP / f'skit{n}_cut.txt'
        # two video-only clips, then mix audio on the concat
        va, vb = TMP / f'skit{n}_va.mp4', TMP / f'skit{n}_vb.mp4'
        for src, dst in ((a, va), (b, vb)):
            run(['ffmpeg', '-hide_banner', '-y', '-i', str(src),
                 '-vf', f'setsar=1,fps={FPS},format=yuv420p',
                 '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '22', str(dst)])
        lst.write_text(f"file '{va.resolve()}'\nfile '{vb.resolve()}'\n")
        pic = TMP / f'skit{n}_pic.mp4'
        run(['ffmpeg', '-hide_banner', '-y', '-f', 'concat', '-safe', '0', '-i', str(lst), '-c', 'copy', str(pic)])
        length = pre + post
    else:
        length = 8.5
        pic = TMP / f'skit{n}_pic.mp4'
        kenburns(wide, length, pic, 1.08)
    mixed = TMP / f'skit{n}_mix.mp4'
    mix_av(pic, mixed, length, music=MUS[n], voice=vpath, voice_t=T, voice_gain=4,
           music_gain=-17, duck_db=-9)
    out = OUT / f'skit{n}.mp4'
    burn_subs(str(mixed), str(out), line, who, T, T + vdur, length)
    print('SKIT', n, out, 'dur', dur(out))
    return out


def build_end_and_stinger():
    end_png = GFX / 'endcard.png'
    make_card(end_png, "THAT'S A WRAP", 'LITERAL VOICE PACK  ·  The Final Episode',
              'Unreal Tournament (c) Epic Games and Digital Extremes. Fan work.')
    end = still_hold(end_png, 5.0, TMP / 'end_raw.mp4', audio=WINNER, audio_delay=0.35, audio_gain=3)
    end_sub = OUT / 'endcard.mp4'
    burn_subs(end, str(end_sub), 'Congratulations! You are the winner!', 'Announcer', 0.35, 0.35 + 3.019, 5.0)

    # stinger: performed EEVEE motion (Tensor almost raises the sign, drops it, waves)
    # then a hard cut to black. Frames: work/animatic_stinger/frames/0001.png
    seq = ROOT / 'work' / 'animatic_stinger' / 'frames' / '%04d.png'
    nframes = len(list((ROOT / 'work' / 'animatic_stinger' / 'frames').glob('*.png')))
    if nframes < 60:
        raise SystemExit('stinger frames missing: %s' % nframes)
    sting_pic = TMP / 'sting_pic.mp4'
    run(['ffmpeg', '-hide_banner', '-y', '-framerate', str(FPS), '-i', str(seq),
         '-vf', f'scale={W}:{H},fps={FPS},format=yuv420p,setsar=1',
         '-an', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20', '-pix_fmt', 'yuv420p',
         str(sting_pic)])
    body = TMP / 'sting_body.mp4'
    run(['ffmpeg', '-hide_banner', '-y', '-i', str(sting_pic),
         '-f', 'lavfi', '-i', f'anullsrc=r={SR}:cl=stereo',
         '-vf', f'scale={W}:{H},fps={FPS},format=yuv420p,setsar=1',
         '-shortest', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20',
         '-c:a', 'aac', '-b:a', '192k', '-ar', str(SR), '-ac', '2', str(body)])
    black = GFX / 'black.png'
    Image.new('RGB', (W, H), (0, 0, 0)).save(black)
    blk = still_hold(black, 0.8, TMP / 'sting_black.mp4')
    # concat + hard cut (no fade)
    for src, q in ((body, TMP / 'sting_a.mp4'), (blk, TMP / 'sting_b.mp4')):
        run(['ffmpeg', '-hide_banner', '-y', '-i', str(src),
             '-vf', f'scale={W}:{H},fps={FPS},format=yuv420p,setsar=1',
             '-af', f'aresample={SR},aformat=sample_fmts=fltp:channel_layouts=stereo',
             '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '22',
             '-c:a', 'aac', '-b:a', '192k', '-ar', str(SR), str(q)])
    lst = TMP / 'sting.txt'
    lst.write_text(f"file '{(TMP/'sting_a.mp4').resolve()}'\nfile '{(TMP/'sting_b.mp4').resolve()}'\n")
    sting = OUT / 'stinger.mp4'
    run(['ffmpeg', '-hide_banner', '-y', '-f', 'concat', '-safe', '0', '-i', str(lst), '-c', 'copy', str(sting)])
    return end_sub, sting


def normalize(src, dst):
    run(['ffmpeg', '-hide_banner', '-y', '-i', str(src),
         '-vf', f'scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,fps={FPS},format=yuv420p,setsar=1',
         '-af', f'aresample={SR},aformat=sample_fmts=fltp:channel_layouts=stereo',
         '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '22',
         '-c:a', 'aac', '-b:a', '192k', '-ar', str(SR), '-ac', '2', str(dst)])
    return dst


def level_match(src, dst):
    run(['ffmpeg', '-hide_banner', '-y', '-i', str(src),
         '-af', 'loudnorm=I=-14:LRA=11:TP=-1.5',
         '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-ar', str(SR), '-ac', '2', str(dst)])
    return dst


def main():
    cold = build_coldopen()
    skits = [build_skit(n) for n in range(1, 9)]
    end, sting = build_end_and_stinger()
    cards = []
    for n in range(1, 9):
        _, line, who, _ = VOICE[n][0], VOICE[n][1], VOICE[n][2], VOICE[n][3]
        p = GFX / f'card_{n}.png'
        make_card(p, line, who, f'Skit {n} of 8')
        cards.append(Path(still_hold(p, 1.15, TMP / f'card_{n}.mp4')))

    pieces = [cold]
    for c, s in zip(cards, skits):
        pieces += [c, s]
    pieces += [end, sting]

    common = []
    for i, p in enumerate(pieces):
        o = TMP / f'ep_{i:02d}.mp4'
        normalize(p, o)
        common.append(o)
    lst = TMP / 'episode.txt'
    lst.write_text(''.join(f"file '{o.resolve()}'\n" for o in common))
    raw = OUT / 'episode_raw.mp4'
    run(['ffmpeg', '-hide_banner', '-y', '-f', 'concat', '-safe', '0', '-i', str(lst), '-c', 'copy', str(raw)])
    out = OUT / 'lvps_v4_animatic_540p.mp4'
    run(['ffmpeg', '-hide_banner', '-y', '-i', str(raw),
         '-af', 'alimiter=limit=-1.5dB:level=false,aresample=%d' % SR,
         '-c:v', 'libx264', '-preset', 'medium', '-crf', '21', '-pix_fmt', 'yuv420p',
         '-c:a', 'aac', '-b:a', '192k', '-ar', str(SR), '-ac', '2',
         '-movflags', '+faststart', str(out)])
    print('EPISODE', out, 'bytes', out.stat().st_size, 'dur', dur(out))
    # print measured loudness to stderr/stdout
    r = subprocess.run(['ffmpeg', '-hide_banner', '-i', str(out),
                        '-af', 'loudnorm=I=-14:TP=-1.5:print_format=summary', '-f', 'null', '-'],
                       capture_output=True, text=True)
    print(r.stderr[-1200:])


if __name__ == '__main__':
    main()
