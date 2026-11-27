r"""Copy one file out of an ISO9660 CD image, local or remote (HTTP range requests: only that file is downloaded).

  python iso_fetch.py IMAGE --list [DIR]          e.g. --list SOUNDS
  python iso_fetch.py IMAGE PATH/IN/IMAGE OUTFILE  e.g. SOUNDS/ANNOUN~1.UAX Announcer.uax

IMAGE is a path to an .iso or an http(s) URL. Names are the ISO9660 short names (no Joliet), e.g. ANNOUN~1.UAX.
Used to get the ORIGINAL UT99 announcer package (Sounds\Announcer.uax) from the user's own Unreal Tournament CD image
when the installed one is modded (docs/HEADSHOT.md). Ask the user before reading anything from the internet.
"""
import struct
import sys
import urllib.request

SECTOR = 2048
_final = None


def reader(image):
    if not image.lower().startswith(("http://", "https://")):
        f = open(image, "rb")

        def get(off, n):
            f.seek(off)
            return f.read(n)
        return get

    def get(off, n):
        global _final
        req = urllib.request.Request(_final or image, headers={"Range": f"bytes={off}-{off + n - 1}",
                                                                "User-Agent": "iso-range-reader"})
        with urllib.request.urlopen(req, timeout=60) as r:
            if _final is None:
                _final = r.geturl()
            if r.status != 206:
                raise SystemExit(f"server ignored the range request (status {r.status})")
            return r.read()
    return get


def records(get, lba, size):
    data = get(lba * SECTOR, size)
    i, out = 0, []
    while i < len(data):
        ln = data[i]
        if ln == 0:
            i = (i // SECTOR + 1) * SECTOR
            continue
        rec = data[i:i + ln]
        name = rec[33:33 + rec[32]]
        if name not in (b"\x00", b"\x01"):
            out.append((name.decode("latin-1").split(";")[0].upper(), struct.unpack("<I", rec[2:6])[0],
                        struct.unpack("<I", rec[10:14])[0], bool(rec[25] & 2)))
        i += ln
    return out


def walk(get, parts, lba, size):
    for p in parts:
        e = next((r for r in records(get, lba, size) if r[0] == p), None)
        if e is None:
            raise SystemExit(f"not found in image: {p}")
        lba, size = e[1], e[2]
    return lba, size


def main():
    image = sys.argv[1]
    get = reader(image)
    pvd = get(16 * SECTOR, SECTOR)
    if pvd[1:6] != b"CD001":
        raise SystemExit("not an ISO9660 image")
    root = pvd[156:156 + 34]
    lba, size = struct.unpack("<I", root[2:6])[0], struct.unpack("<I", root[10:14])[0]
    print("volume:", pvd[40:72].decode("latin-1").strip())
    if sys.argv[2] == "--list":
        parts = [p for p in (sys.argv[3] if len(sys.argv) > 3 else "").upper().strip("/").split("/") if p]
        lba, size = walk(get, parts, lba, size)
        for r in records(get, lba, size):
            print(("DIR  " if r[3] else "     ") + r[0], r[2])
        return
    parts = sys.argv[2].upper().strip("/").split("/")
    lba, size = walk(get, parts, lba, size)
    data = get(lba * SECTOR, size)
    open(sys.argv[3], "wb").write(data)
    print("wrote", sys.argv[3], len(data), "bytes")


if __name__ == "__main__":
    main()
