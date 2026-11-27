"""Assemble a Blender skit: frames + timeline.json (sound cues, subtitles, end card) -> MP4.

python assemble_skit.py WORKDIR OUT.mp4
WORKDIR contains frames/NNNN.png and timeline.json (written by the scene script).
"""
import json
import os
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from assetpaths import find_font  # noqa: E402  (also puts config binDirs/ffmpeg on PATH)

work, out = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
tl = json.load(open(os.path.join(work, 'timeline.json'), encoding='utf-8'))
fps, dur = tl['fps'], tl['duration']
W, H = Image.open(os.path.join(work, 'frames', '0001.png')).size


def font(size, bold=False):
    names = (('bahnschrift.ttf', 'arialbd.ttf', 'DejaVuSans-Bold.ttf') if bold
             else ('bahnschrift.ttf', 'arial.ttf', 'DejaVuSans.ttf'))
    for name in names:
        p = find_font(name)
        if p:
            f = ImageFont.truetype(p, size)
            if name == 'bahnschrift.ttf':
                try:
                    f.set_variation_by_name('Bold' if bold else 'SemiBold')
                except Exception:
                    pass
            return f
    return ImageFont.load_default()


# ---- end card (transparent PNG over the faded-out picture)
card = Image.new('RGBA', (W, H), (0, 0, 0, 0))
dr = ImageDraw.Draw(card)
ec = tl.get('end_card') or dict(t0=dur + 10, text='', sub='')  # a compilation can supply its own card
f1, f2 = font(int(H * 0.055), True), font(int(H * 0.03))
for text, f, y, col in ((ec['text'], f1, 0.45, (235, 235, 240, 255)), (ec['sub'], f2, 0.54, (160, 140, 255, 255))):
    w = dr.textlength(text, font=f)
    dr.text(((W - w) / 2, H * y), text, font=f, fill=col)
card_path = os.path.join(work, 'endcard.png')
card.save(card_path)

# ---- subtitles (ASS)


def ts(t):
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return f'{int(h)}:{int(m):02d}:{s:05.2f}'


SUBK = float(tl.get('sub_scale', 1.0))   # LVPS draws a larger line
FN = 'Bahnschrift' if find_font('bahnschrift.ttf') else 'DejaVu Sans'
ass = [
    '[Script Info]', 'ScriptType: v4.00+', f'PlayResX: {W}', f'PlayResY: {H}', '',
    '[V4+ Styles]',
    'Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, '
    'Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding',
    f'Style: Default,{FN},{int(H * 0.052 * SUBK)},&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,-1,0,0,0,100,100,0.5,0,1,{max(2, int(H * SUBK) // 240)},1,2,40,40,{int(H * 0.07)},1',
    f'Style: Who,{FN},{int(H * 0.03 * SUBK)},&H00D0C0FF,&H00FFFFFF,&H00000000,&H64000000,-1,0,0,0,100,100,1,0,1,{max(2, H // 300)},1,2,40,40,{int(H * 0.07) + int(H * 0.058 * SUBK)},1',
    # UT announcer: red, top centre
    f'Style: Announcer,{FN},{int(H * 0.075)},&H002020FF,&H00FFFFFF,&H00000000,&H00000000,-1,0,0,0,100,100,6,0,1,{max(2, H // 200)},0,8,40,40,{int(H * 0.16)},1',
    # Lower third: name tag bottom-left
    f'Style: Lower,{FN},{int(H * 0.05)},&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,-1,0,0,0,100,100,1,0,1,{max(2, H // 300)},1,1,{int(W * 0.05)},40,{int(H * 0.1)},1',
    '', '[Events]', 'Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text',
]
for s in tl['subs']:
    if s.get('style') == 'lower':
        sub = f"\\N{{\\fs{int(H * 0.028)}\\c&HFFB0A0&}}{s['who']}" if s.get('who') else ''
        ass.append(f"Dialogue: 0,{ts(s['t0'])},{ts(s['t1'])},Lower,,0,0,0,,{{\\fad(150,250)}}{s['text']}{sub}")
        continue
    style = 'Announcer' if s.get('style') == 'announcer' else 'Default'
    fade = r'{\fad(80,200)}' if style == 'Default' else r'{\fad(60,300)\t(0,250,\fscx115\fscy115)\t(250,500,\fscx100\fscy100)}'
    ass.append(f"Dialogue: 0,{ts(s['t0'])},{ts(s['t1'])},{style},,0,0,0,,{fade}{s['text']}")
    if s.get('who'):
        ass.append(f"Dialogue: 0,{ts(s['t0'])},{ts(s['t1'])},Who,,0,0,0,,{{\\fad(80,200)}}{s['who'].upper()}")
with open(os.path.join(work, 'subs.ass'), 'w', encoding='utf-8') as f:
    f.write('\n'.join(ass) + '\n')

# ---- audio graph
inputs = ['-framerate', str(fps), '-i', os.path.join('frames', '%04d.png'), '-loop', '1', '-i', card_path]
filters = []
mix = []
idx = 2
mu = tl.get('music')
voice_windows = [(c['t'] - 0.1, c['t'] + 1.4) for c in tl['cues'] if c.get('voice')]
duck = '+'.join(f'between(t,{a:.2f},{b:.2f})' for a, b in voice_windows) or '0'
if mu:
    duck_gain = 10 ** (mu['duck_db'] / 20)
    inputs += ['-ss', str(mu['offset']), '-t', str(dur), '-i', mu['file']]
    filters.append(f"[{idx}:a]aresample=48000,aformat=channel_layouts=stereo,volume={mu['gain_db']}dB,"
                   f"volume='if(gt({duck},0),{duck_gain:.3f},1)':eval=frame,afade=t=out:st={dur - 2.5}:d=2.5[mus]")
    mix.append('[mus]')
    idx += 1
for i, c in enumerate(tl['cues']):
    if c.get('loop'):
        inputs += ['-stream_loop', '-1', '-t', str(dur), '-i', c['file']]
    else:
        inputs += ['-i', c['file']]
    delay = int(c['t'] * 1000)
    chain = f"[{idx}:a]aresample=48000,aformat=channel_layouts=stereo,volume={c['gain_db']}dB"
    if c.get('loop'):
        chain += f',atrim=0:{dur},afade=t=out:st={dur - 2}:d=2'
    chain += f',adelay={delay}|{delay}[c{i}]'
    filters.append(chain)
    mix.append(f'[c{i}]')
    idx += 1
limit = tl.get('limit', 0.95)
level = ':level=0' if 'limit' in tl else ''
filters.append(
    f"{''.join(mix)}amix=inputs={len(mix)}:normalize=0:duration=longest,atrim=0:{dur},"
    f"volume={tl.get('master_db', 0)}dB,alimiter=limit={limit}{level}[aout]")

# ---- video graph: fade to black, end card, subtitles
t_card = ec['t0']
filters.append(f"[0:v]format=yuv420p,fade=t=out:st={t_card - 0.7}:d=0.6[vf]")
filters.append(f"[1:v]format=rgba,fade=t=in:st={t_card}:d=0.5:alpha=1,trim=0:{dur}[card]")
filters.append(f"[vf][card]overlay=0:0:enable='gte(t,{t_card})',subtitles=subs.ass,format=yuv420p[vout]")

graph_path = os.path.join(work, 'graph.txt')
with open(graph_path, 'w') as f:
    f.write(';\n'.join(filters))
cmd = ['ffmpeg', '-hide_banner', '-y', *inputs, '-/filter_complex', 'graph.txt', '-map', '[vout]', '-map', '[aout]',
       '-t', str(dur), '-c:v', 'libx264', '-preset', 'slow', '-crf', '18', '-r', str(fps), '-pix_fmt', 'yuv420p',
       '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', os.path.abspath(out)]
print(' '.join(cmd))
subprocess.run(cmd, cwd=work, check=True)
probe = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration:stream=codec_name,width,height,r_frame_rate',
                        '-of', 'json', os.path.abspath(out)], capture_output=True, text=True)
print(probe.stdout)
