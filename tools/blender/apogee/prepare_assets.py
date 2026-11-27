"""Extract the stock maps and game assets used by the APOGEE recipe."""
import subprocess
import sys

from paths import ASSETS, TOOLS
import extract_assets

MAPS = [
    'CTF-Face', 'CTF-Coret', 'DM-Deck16][', 'DM-Liandri',
    'DM-Morpheus', 'DM-Phobos', 'CTF-LavaGiant', 'DM-HyperBlast',
]
MESHES = ('ASMD2hand', 'FlakHand', 'EightHand', 'UTRocket', 'ShockWavem')
SOUNDS = {
    'AmbModern': ('Looping.Fan2.wav', 'Looping.mclang2.wav', 'Looping.steam3.wav'),
    'UnrealShare': ('Eightball.Loading.wav', 'Eightball.EightAltFire.wav', 'Eightball.Ignite.wav',
                    'General.Expl03.wav', 'General.Explo1.wav', 'Menu.Select4.wav'),
}


def main():
    for name in MAPS:
        if not extract_assets.find_pkg(name, [('Maps', '.unr')]):
            raise FileNotFoundError(f'Could not find {name}.unr in the configured UT installation')
    argv = sys.argv
    try:
        sys.argv = [str(TOOLS / 'extract_assets.py'), '--maps', *MAPS]
        extract_assets.main()
    finally:
        sys.argv = argv
    extract_assets.texture_pkg('SpaceFX')
    if not (ASSETS / 'textures' / 'SpaceFX' / 'earth.bmp').is_file():
        raise FileNotFoundError('SpaceFX export is missing earth.bmp')
    botpack = extract_assets.find_pkg('Botpack', [('System', '.u')])
    if not botpack:
        raise FileNotFoundError('Could not find Botpack.u in the configured UT installation')
    for name in MESHES:
        target = ASSETS / 'meshes' / (name + '.npz')
        if not target.is_file():
            subprocess.run([sys.executable, str(TOOLS / 'ut_mesh.py'), botpack, name, str(target)],
                           check=True)

    for package, required in SOUNDS.items():
        folder = ASSETS / 'sounds' / package
        if all((folder / item).is_file() for item in required):
            continue
        source = extract_assets.find_pkg(package, [('Sounds', '.uax'), ('System', '.u')])
        if not source:
            raise FileNotFoundError(f'Could not find {package} in the configured UT installation')
        extract_assets.ucc_export(source, 'sound', 'wav', str(folder))
        missing = [name for name in required if not (folder / name).is_file()]
        if missing:
            raise FileNotFoundError(f'{package} export is missing: {", ".join(missing)}')


if __name__ == '__main__':
    main()
