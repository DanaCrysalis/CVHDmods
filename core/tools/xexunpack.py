"""Unpack an encrypted, LZX-compressed XEX2 module into its memory image.

AES runs through .NET (aesdec.ps1); LZX runs through Windows expand.exe by
wrapping the XEX's LZX chunks as CAB data blocks.
"""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import os, struct, subprocess, sys, tempfile, zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
# The retail XEX key is not carried here: it is read from the recomp's own
# runtime (every HarmonyRecomp install has it), found by its SHA-256.
RETAIL_KEY_SHA256 = 'a0bd3f5f56adf2b0238a2702c0c0cd8548fb34b3dc19345943dc011010723fe4'
_key = None

def retail_key():
    global _key
    if _key is None:
        import hashlib
        root = hodpaths.GAME/'.setup/package'
        for dll in (root/'sdk/bin/rexruntime.dll', root/'src/out/build/win-amd64-release/rexruntime.dll'):
            if not dll.is_file(): continue
            b = dll.read_bytes()
            _key = next((b[i:i+16].hex().upper() for i in range(0, len(b)-16, 16)
                         if hashlib.sha256(b[i:i+16]).hexdigest() == RETAIL_KEY_SHA256), None)
            if _key: break
        assert _key, 'XEX key not found in the HarmonyRecomp runtime (.setup/package/sdk/bin/rexruntime.dll)'
    return _key

def be32(b, o): return struct.unpack_from('>I', b, o)[0]

def headers(x):
    count = be32(x, 0x14)
    out = {}
    for i in range(count):
        k, v = struct.unpack_from('>II', x, 0x18 + i * 8)
        out[k] = v
    return out

def aes(key_hex, mode, data):
    with tempfile.TemporaryDirectory() as t:
        i, o = Path(t, 'in.bin'), Path(t, 'out.bin')
        i.write_bytes(data)
        subprocess.run(['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
                        str(hodpaths.tool('aesdec.ps1')), key_hex, mode, str(i), str(o)], check=True)
        return o.read_bytes()

def lzx_via_cab(frames, window_bits, out_size):
    """frames: list of compressed LZX frames, each expanding to <= 32768 bytes."""
    n = len(frames)
    folder_hdr = struct.pack('<IHH', 0, n, 0x0003 | (window_bits << 8))   # offset patched below
    name = b'image.bin\0'
    hdr_size = 36
    folder_off = hdr_size
    file_off = folder_off + 8
    data_off = file_off + 16 + len(name)
    cfdata = b''
    left = out_size
    for f in frames:
        unc = min(32768, left)
        left -= unc
        cfdata += struct.pack('<IHH', 0, len(f), unc) + f
    total = data_off + len(cfdata)
    cab = struct.pack('<4sIIIIIBBHHHHH', b'MSCF', 0, total, 0, file_off, 0, 3, 1, 1, 1, 0, 0x1234, 0)
    folder = struct.pack('<IHH', data_off, n, 0x0003 | (window_bits << 8))
    cfile = struct.pack('<IIHHHH', out_size, 0, 0, 0x2121, 0, 0x20) + name
    blob = cab + folder + cfile + cfdata
    assert len(blob) == total
    with tempfile.TemporaryDirectory() as t:
        c = Path(t, 'x.cab'); c.write_bytes(blob)
        od = Path(t, 'out'); od.mkdir()
        r = subprocess.run(['expand.exe', str(c), '-F:*', str(od)], capture_output=True, text=True)
        # expand.exe names a single-file output after the cabinet.
        outs = [p for p in od.iterdir() if p.is_file()]
        if len(outs) != 1 or outs[0].stat().st_size != out_size:
            raise RuntimeError('expand.exe failed: ' + r.stdout + r.stderr)
        return outs[0].read_bytes()

def unpack(path):
    x = Path(path).read_bytes()
    assert x[:4] == b'XEX2'
    pe_off, sec_off = be32(x, 0x08), be32(x, 0x10)
    h = headers(x)
    ff = h[0x000003FF]
    enc, comp = struct.unpack_from('>HH', x, ff + 4)
    image_size = be32(x, sec_off + 0x04)
    load_addr = be32(x, sec_off + 0x110)
    data = x[pe_off:]
    if enc == 1:
        session = aes(retail_key(), 'ECB', x[sec_off + 0x150:sec_off + 0x160]).hex()
        data = aes(session, 'CBC', data[:len(data) // 16 * 16])
    if comp == 2:
        window = be32(x, ff + 8)
        wbits = window.bit_length() - 1
        block_size = be32(x, ff + 12)
        frames, p = [], 0
        while block_size:
            block = data[p:p + block_size]
            p += block_size
            next_size = be32(block, 0)
            q = 24
            while True:
                n = struct.unpack_from('>H', block, q)[0]; q += 2
                if n == 0:
                    break
                frames.append(block[q:q + n]); q += n
            block_size = next_size
        image = lzx_via_cab(frames, wbits, image_size)
    elif comp == 0:
        image = data[:image_size]
    else:
        raise NotImplementedError(f'compression {comp}')
    return x, image, load_addr

if __name__ == '__main__':
    x, image, base = unpack(sys.argv[1])
    Path(sys.argv[2]).write_bytes(image)
    print(f'base {base:#x}, image {len(image):#x} bytes, starts {image[:2]!r}')
