"""Extract the teaser's extra sound exports and prop meshes from a local UT install."""
import argparse
from pathlib import Path
import struct

import json
import numpy as np
from paths import WORK as ROOT
from ut_mesh import Package, Reader, read_mesh


def old_exports(path):
    data = path.read_bytes()
    reader = Reader(data, 12)
    name_count, name_offset, count, offset, _, _ = [reader.u32() for _ in range(6)]
    reader.p = name_offset
    names = []
    for _ in range(name_count):
        end = data.index(b'\0', reader.p)
        names.append(data[reader.p:end].decode('latin1'))
        reader.p = end + 5
    reader.p = offset
    exports = []
    for _ in range(count):
        reader.idx(); reader.idx(); reader.i32()
        name = names[reader.idx()]
        reader.u32()
        size = reader.idx()
        start = reader.idx() if size else 0
        exports.append(dict(name=name, size=size, off=start))
    return data,exports


def export(package_path, names):
    if package_path.suffix == '.uax':
        data, exports = old_exports(package_path)
    else:
        package=Package(package_path)
        data, exports = package.data, [e for e in package.exports if package.class_name(e)=='Sound']
    folder = ROOT / 'assets' / 'audio'
    folder.mkdir(parents=True, exist_ok=True)
    for name in names:
        sound = next(e for e in exports if e['name'].lower()==name.lower())
        content = data[sound['off']:sound['off']+sound['size']]
        offset = content.index(b'RIFF')
        size = struct.unpack_from('<I', content, offset+4)[0]+8
        riff = content[offset:offset+size]
        if len(riff)!=size or riff[8:12]!=b'WAVE':
            raise ValueError(f'Invalid RIFF for {name}')
        (folder/(name+'.wav')).write_bytes(riff)
        print(package_path.name, name, size)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Extract the teaser props and extra sounds from a local UT99 install.')
    parser.add_argument('--ut-root', type=Path, required=True)
    game = parser.parse_args().ut_root
    export(game/'Sounds/AmbModern.uax', ('Fan2','hum11','mclang2','steam3'))
    export(game/'System/UnrealShare.u', ('Loading','EightAltFire'))
    botpack = Package(game/'System/Botpack.u')
    for name in ('Trans3loc', 'EightHand', 'Module', 'UTRocket'):
        mesh = read_mesh(botpack, name)
        mesh['info'] = json.dumps(mesh['info'])
        np.savez_compressed(ROOT/'assets'/f'{name}.npz', **mesh)
