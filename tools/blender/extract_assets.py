"""Extract the UT99 assets the Blender pipeline needs from YOUR OWN UT install into assets/ut (never committed).

python tools/blender/extract_assets.py [--maps CTF-Face DM-Morpheus ...] [--map-file X:/path/Map.unr ...]

- meshes:   tools/blender/ut_mesh.py on System/Botpack.u (ucc has no LodMesh exporter)
- maps:     tools/blender/ut_map.py on Maps/<name>.unr -> maps/<name>.json; then every texture package the
            map references is exported, plus the map's own MyLevel textures (-> textures/MyLevel_<name>)
- textures: ucc batchexport <pkg> texture bmp (24-bit, files named Group.Name.bmp)
- sounds:   ucc batchexport <pkg>.uax sound wav (+ Botpack.u weapon sounds)
- music:    ucc batchexport <song>.umx music it, then ffmpeg (libopenmpt) -> wav
UT must not be running ucc in parallel. Existing outputs are skipped, so it is safe to re-run.

ucc is System/ucc.exe on Windows. On Linux it is the first of System64/ucc-bin-amd64,
System/ucc-bin-amd64, System64/ucc-bin, System/ucc-bin, run with that directory as cwd.
"""
import argparse
import glob
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.dirname(HERE), HERE]
import ddconfig  # noqa: E402  (UT root + binDirs on PATH)
from assetpaths import ASSETS, MAPS, MESHES, MUSIC, SOUNDS, TEXTURES  # noqa: E402


def resolve_ucc(ut_root):
    """Candidate commandlet binaries for this OS, most preferred first.

    Windows stays System/ucc.exe, which is the binary the rest of the toolkit already calls.
    Linux 469 ships System64/ucc-bin-amd64 (32-bit and older installs use ucc-bin). The amd64
    name is preferred in either System64 or System, then ucc-bin.
    """
    system = os.path.join(ut_root, 'System')
    if os.name == 'nt':
        return [os.path.join(system, 'ucc.exe')]
    system64 = os.path.join(ut_root, 'System64')
    names = ('ucc-bin-amd64', 'ucc-bin')
    dirs = (system64, system)
    return [os.path.join(directory, name) for name in names for directory in dirs]


def find_ucc(ut_root):
    candidates = resolve_ucc(ut_root)
    for path in candidates:
        if os.path.isfile(path):
            return path
    return candidates[0]


UT = ddconfig.UT
SYSTEM = os.path.join(UT, 'System')
UCC = find_ucc(UT)
UCC_CWD = os.path.dirname(UCC)

STOCK_MAPS = ['CTF-Face', 'DM-Morpheus', 'DM-Deck16][', 'CTF-Coret', 'CTF-LavaGiant', 'DM-Liandri']
MESH_NAMES = ['Soldier', 'Commando', 'FCommando', 'SGirl', 'Boss', 'ASMD2pick']
SKIN_PKGS = ['Soldierskins', 'commandoskins', 'FCommandoSkins', 'SGirlSkins', 'BossSkins',
             'HDSkinsUT99']                       # HDSkinsUT99 = optional HD skin pack (shock rifle texture); skipped if absent
SKY_PKGS = ['GenFluid', 'ShaneSky', 'shaneDAY']   # sky domes used by scenes/face_set.py and academy/chapters.py
SOUND_PKGS = ['Announcer', 'MaleSounds', 'FemaleSounds', 'Male1Voice', 'Male2Voice', 'Female1Voice', 'Female2Voice',
              'BossVoice', 'AmbOutside']
MUSIC_SONGS = ['utmenu23', 'Uttitle', 'Mech8', 'Godown', 'Botpck10', 'Foregone', 'Suprfist']
CUTS = {'Foregone_60s': ('Foregone', 60), 'Suprfist_90s': ('Suprfist', 90)}   # trimmed beds used by the scene configs


def ucc_export(src, kind, ext, out):
    os.makedirs(out, exist_ok=True)
    r = subprocess.run([UCC, 'batchexport', src, kind, ext, out], cwd=UCC_CWD, capture_output=True, text=True,
                       errors='replace')
    n = len(os.listdir(out))
    print(f'  {os.path.basename(src)} -> {os.path.relpath(out, ASSETS)} ({n} files)')
    if n == 0:
        print('   ', (r.stdout + r.stderr).strip().splitlines()[-1:] or 'ucc gave no output')


def find_pkg(name, exts):
    for d, ext in exts:
        hits = [p for p in glob.glob(os.path.join(UT, d, '*' + ext)) if os.path.basename(p).lower() == (name + ext).lower()]
        if hits:
            return hits[0]
    return None


def texture_pkg(name):
    if os.path.isdir(os.path.join(TEXTURES, name)) and os.listdir(os.path.join(TEXTURES, name)):
        return
    src = find_pkg(name, [('Textures', '.utx'), ('System', '.u')])
    if not src:
        print(f'  texture package {name}: not found (skipped)')
        return
    ucc_export(src, 'texture', 'bmp', os.path.join(TEXTURES, name))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--maps', nargs='*', default=STOCK_MAPS, help='map names in UT/Maps')
    ap.add_argument('--map-file', nargs='*', default=[], help='extra .unr files (e.g. a Cache .uxx copied to .unr)')
    a = ap.parse_args()
    if not os.path.isfile(UCC):
        if os.name == 'nt':
            raise SystemExit(f'ucc.exe not found in {SYSTEM} (check utRoot in config.json)')
        raise SystemExit(
            f'ucc not found (looked for ucc-bin-amd64 and ucc-bin in {os.path.join(UT, "System64")} and {SYSTEM}; '
            f'check utRoot in config.json)')
    for d in (MESHES, MAPS, TEXTURES, SOUNDS, MUSIC):
        os.makedirs(d, exist_ok=True)

    print('meshes')
    botpack = os.path.join(SYSTEM, 'Botpack.u')
    for m in MESH_NAMES:
        out = os.path.join(MESHES, m + '.npz')
        if not os.path.exists(out):
            subprocess.run([sys.executable, os.path.join(HERE, 'ut_mesh.py'), botpack, m, out], check=True)

    print('maps')
    tex_pkgs = set(SKIN_PKGS + SKY_PKGS + ['Botpack'])
    map_files = [os.path.join(UT, 'Maps', n + '.unr') for n in a.maps] + a.map_file
    for mf in map_files:
        name = os.path.splitext(os.path.basename(mf))[0].replace('[', '').replace(']', '')   # DM-Deck16][ -> DM-Deck16
        js = os.path.join(MAPS, name + '.json')
        if not os.path.exists(mf):
            print(f'  {mf}: missing (skipped)')
            continue
        if not os.path.exists(js):
            subprocess.run([sys.executable, os.path.join(HERE, 'ut_map.py'), mf, js], check=True)
        d = json.load(open(js, encoding='utf-8'))
        tex_pkgs |= {t['package'] for t in d['textures'].values() if t.get('package') and t['package'] != 'MyLevel'}
        ml = os.path.join(TEXTURES, f'MyLevel_{name}')
        if not os.path.isdir(ml):
            ucc_export(os.path.abspath(mf), 'texture', 'bmp', ml)

    print('textures')
    for p in sorted(tex_pkgs, key=str.lower):
        texture_pkg(p)

    print('sounds')
    for p in SOUND_PKGS:
        out = os.path.join(SOUNDS, p)
        src = find_pkg(p, [('Sounds', '.uax')])
        if src and not (os.path.isdir(out) and os.listdir(out)):
            ucc_export(src, 'sound', 'wav', out)
    out = os.path.join(SOUNDS, 'Botpack')
    if not (os.path.isdir(out) and os.listdir(out)):
        ucc_export(botpack, 'sound', 'wav', out)

    print('music')
    for s in MUSIC_SONGS:
        wav = os.path.join(MUSIC, s + '.wav')
        src = find_pkg(s, [('Music', '.umx')])
        if not src or os.path.exists(wav):
            continue
        subprocess.run([UCC, 'batchexport', src, 'music', 'it', MUSIC], cwd=UCC_CWD, capture_output=True)
        it = next(iter(glob.glob(os.path.join(MUSIC, s + '.*'))), None)
        if it:
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', it, '-ar', '48000', wav], check=True)
            print(f'  {s}.wav')
    for cut, (s, sec) in CUTS.items():
        wav, out = os.path.join(MUSIC, s + '.wav'), os.path.join(MUSIC, cut + '.wav')
        if os.path.exists(wav) and not os.path.exists(out):
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', wav, '-t', str(sec), '-af', f'afade=t=out:st={sec - 3}:d=3',
                            out], check=True)
    print('done:', ASSETS)


if __name__ == '__main__':
    main()
