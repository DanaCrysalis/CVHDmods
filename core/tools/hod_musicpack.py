"""Build Harmony of Despair music packs (BGM DLC) from your own audio files.

A music pack is a data-only DLC package, laid out like the official BGM packs
(package 28 and 29):

  000info/packageNN.dat            "PackageInfo\\r\\n"; NN is the pack number
  data/sound/bgmNN_def.dat         track list, 36 bytes per track:
                                     u16 text group id = NN << 10 | 12
                                     u16 string index of the title in that group
                                     char[32] bank name
  data/sound/<bank>.xsb / .xwb     one XACT sound bank and wave bank per track
  data/text/textresNN_<lang>.txrc  titles in text group 12 (de en es fr it ja)

The game opens <device>:\\data\\sound\\bgmNN_def.dat on every mounted package
(format string at 821F3E20, read at 82599BE0), so a new pack needs no change
to the game. The official tracks are XMA; this tool writes 16-bit PCM, which
the same XACT runtime plays (the Nathan voice banks use it too).

Size matters: every sound bank is loaded into one 16 MB sound heap shared with
the sound effects and the voices of the characters in play, and a bank that
does not fit is skipped without any message (the track is listed but silent).
So each track gets a budget (max_mb, default 5 MB, the size of the largest
official DLC track) and the tool picks the highest sample rate that fits it,
48 kHz at most, stereo down to 16 kHz and mono below that. Only the intro and
one pass of the loop are kept, which is what keeps the rate up (so cutting the
tail raises the rate rather than shrinking the file). 16-bit stereo PCM takes
11 MB per minute at 48 kHz, so most songs land near 20-24 kHz; "mono" doubles
the rate, and "sample_rate" forces one (over the budget the game may skip it).
The official music is XMA, about ten times smaller, but there is no freely
available XMA encoder.

Each bank holds one cue in the music category (3) with a PlayWave event that
loops forever (loop count 255) over the wave's loop region, exactly as the
official music banks do. Loop points come from the pack file, or are found
automatically: soundtrack rips usually play the loop twice and fade out, so
the tool finds the repeat, keeps the intro plus one loop, and crossfades the
last 20 ms into the loop start so the seam is continuous.

Usage:
  hod_musicpack.py init  <audio folder> <pack.json>   start a pack file
  hod_musicpack.py build <pack.json> [--out DIR]      build the one-file pack and verify
  hod_musicpack.py install <pack.json>                build, then install
  hod_musicpack.py install-file <pack file>           install a pack file someone shared
  hod_musicpack.py uninstall <pack.json>              remove an installed pack

pack.json (paths are relative to the pack file):
  {
    "name": "Circle of the Moon Music Pack",
    "package": 18,                       optional; first free number otherwise
    "match_game_volume": true,           default: bring every song to the loudness of
                                         the game's own music (-8.5 LUFS), limiting
                                         peaks by up to 6 dB
    "tracks": [
      {"file": "17 Proof of Blood.flac",
       "title": "Proof of Blood",        every language unless "titles" says otherwise
       "titles": {"ja": "..."},          optional, per language
       "loop": "auto",                   or "whole" (loop the full file), or
                                         {"start": 12.0, "end": 66.25} seconds
       "gain_db": 0,                     optional, on top of the automatic volume
       "max_mb": 5.0},                   optional bank budget (see above)
                                         (pack-wide defaults for every track:)
    "sample_rate": "auto",               or a fixed rate such as 48000; a fixed rate
                                         can go over max_mb (the build warns)
    "mono": false,                       true: one channel, twice the rate in the
                                         same size
      {"xwb": "BGM_CSTM_01.xwb",         or a ready Xbox 360 wave bank (e.g. XMA):
       "title": "..."}                   its waves and loop are kept, it is renamed
    ]                                    to the pack's bank name, and the cue file
  }                                      is generated (any .xsb next to it is unused)

Build writes the pack as one file, an Xbox 360 package like the official DLC
(see "single-file package" below), named by its 42-character package id.
Install puts that file into <game>/dlc/ and adds "<id>\\tpackageNN" to
dlc_packages.txt; HarmonyRecomp unpacks it into its content folder when the
game starts, as it does official DLC (it deletes packages missing from the
list). A copy also goes into the DLC folder the HarmonyRecomp setup builds
from (setup.log), so re-running the setup keeps the pack listed.

Needs: numpy, soundfile, soxr (pip install numpy soundfile soxr).
Nothing from the game or from the audio is stored in this tool.
"""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import argparse
import hashlib
import json
import re
import shutil
import struct
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import txrc  # noqa: E402  (sibling tool: TXRC text encoder)

FROZEN = getattr(sys, 'frozen', False)  # running as the bundled .exe
def _writable(folder):
    try:
        folder.mkdir(parents=True, exist_ok=True)
        probe = folder / '.write_test'
        probe.write_bytes(b'')
        probe.unlink()
        return True
    except OSError:
        return False


if FROZEN:
    # Standalone: packs and builds go in "Music Packs" next to the exe (or in
    # Documents when that folder is read-only, e.g. under Program Files). The
    # game folder is chosen in the window (or --game) and remembered.
    ROOT = Path(sys.executable).resolve().parent
    WORK = ROOT / 'Music Packs'
    if not _writable(WORK):
        WORK = Path.home() / 'Documents' / 'HoD Music Packs'
    PACKS = WORK
    BUILDS = WORK / 'builds'
else:
    ROOT = hodpaths.GAME  # the game folder (this repo)
    PACKS = hodpaths.legacy('modding/music')
    BUILDS = hodpaths.legacy('modding/build/musicpacks')
CONTENT = Path.home() / 'Documents/harmonyrecomp/0000000000000000/58410A7A'
TITLE_ID = 0x58410A7A
RATE = 48000             # highest rate written (the official banks' rate)
MIN_STEREO_RATE = 16000  # below this the budget is spent on one channel instead
DEFAULT_MAX_MB = 5.0     # per track; the largest official DLC track is 5.1 MB
# Loudness of the game's own music: median of all 56 official tracks (base
# game and every DLC), measured with loudness_lufs() on FFmpeg-decoded XMA on
# 2026-11-12. Stage and DLC music lies between -7 and -9.5 LUFS.
GAME_MUSIC_LUFS = -8.5
PEAK_CEILING = 0.989     # -0.1 dBFS
MAX_LIMIT_DB = 6.0       # most peak reduction allowed when matching the volume
LANGS = ('de', 'en', 'es', 'fr', 'it', 'ja')
TEXT_GROUP = 12          # official BGM packs keep track titles in group 12 of 17
TEXT_GROUPS = 17
MUSIC_CATEGORY = 3       # category of every official BGM cue
OFFICIAL_PACKAGES = {1, 2, 3, 4, 7, 11, 12, 13, 14, 15, 16, 28, 29}
USED_PACKAGES = OFFICIAL_PACKAGES | {17, 19}  # 17: the Nathan character mod, 19: the Shield Rod
AUDIO_EXT = ('.flac', '.wav', '.ogg', '.mp3', '.aiff', '.aif')


# ----------------------------------------------------------------- audio ----

def load_audio(path):
    import soundfile as sf
    data, rate = sf.read(str(path), dtype='float64', always_2d=True)
    if data.shape[1] == 1:
        data = np.repeat(data, 2, axis=1)
    elif data.shape[1] > 2:
        data = data[:, :2]
    return data, rate


def resample(data, rate, out_rate):
    if rate == out_rate:
        return data
    import soxr
    return soxr.resample(data, rate, out_rate, quality='VHQ')


def fit_format(seconds, max_bytes, rate=None, mono=False):
    """(rate, channels) of the bank: the highest rate whose 16-bit PCM fits
    the bank budget, or the fixed rate asked for (which may not fit).

    Every sound bank lives in the game's 16 MB sound heap (allocated at
    822217DC, checked by 82590AC8, which silently refuses a bank larger than
    the biggest free block). Sound effects and the voices of the characters
    in play share it, so a music bank must stay near the official sizes
    (largest DLC track 5.1 MB).
    """
    if rate:
        return int(rate), 1 if mono else 2
    # Any rate plays (the XACT voice resamples, as for 19544 Hz banks), so the
    # whole budget goes into the rate instead of rounding to a standard one.
    for channels in (1,) if mono else (2, 1):
        rate = min(RATE, int(max_bytes / (seconds * 2 * channels)) // 10 * 10)
        if rate >= MIN_STEREO_RATE or channels == 1:
            return max(rate, 8000), channels
    raise AssertionError('unreachable')


def track_format(seconds, t):
    """(rate, channels, bank bytes, over budget) a song of this length gets."""
    max_mb = float(t.get('max_mb', DEFAULT_MAX_MB))
    fixed = t.get('sample_rate', 'auto')
    fixed = None if fixed in (None, 'auto', 0, '') else int(fixed)
    rate, channels = fit_format(seconds, max_mb * 2**20 - 4096, fixed, bool(t.get('mono')))
    size = 2048 + int(round(seconds * rate)) * 2 * channels
    return rate, channels, size, size > max_mb * 2**20


def _features(mono, rate, hop):
    """Log band energies per hop, normalised per frame (for repeat search)."""
    win = 4096
    n = (len(mono) - win) // hop
    frames = np.lib.stride_tricks.sliding_window_view(mono, win)[::hop][:n] * np.hanning(win)
    spec = np.abs(np.fft.rfft(frames, axis=1))[:, :1024]
    edges = np.unique(np.geomspace(2, 1024, 65).astype(int))
    bands = np.stack([spec[:, a:b].sum(1) for a, b in zip(edges[:-1], edges[1:])], 1)
    f = np.log1p(bands * 10)
    f -= f.mean(1, keepdims=True)
    f /= np.linalg.norm(f, axis=1, keepdims=True) + 1e-9
    return f


def _longest_run(mask):
    """(start, end) of the longest stretch of True values."""
    edges = np.flatnonzero(np.diff(np.concatenate(([0], mask.astype(np.int8), [0]))))
    if not len(edges):
        return 0, 0
    starts, ends = edges[::2], edges[1::2]
    i = int(np.argmax(ends - starts))
    return int(starts[i]), int(ends[i])


def find_loop(data, rate, min_loop=8.0, min_run=4.0):
    """Find (start, end) in samples so that data[end] continues like data[start].

    Coarse: the frame lag with the longest stretch of near-identical spectra.
    Fine: the sample lag with the smallest waveform error in that stretch.
    Start: the best-matching point in the first seconds of the stretch.
    Returns None when the audio does not repeat.
    """
    mono = data.mean(1)
    hop = 1024
    f = _features(mono, rate, hop)
    n = len(f)
    best = None
    smooth = np.ones(max(1, rate // hop)) / max(1, rate // hop)  # about 1 s
    for lag in range(int(min_loop * rate / hop), n - int(min_run * rate / hop)):
        sim = np.convolve((f[:-lag] * f[lag:]).sum(1), smooth, 'same')
        a, b = _longest_run(sim > 0.95)
        if best is None or b - a > best[2] - best[1]:
            best = (lag, a, b)
    if best is None or (best[2] - best[1]) * hop < min_run * rate:
        return None
    lag, a, b = best
    run_a, run_b = a * hop, b * hop

    # Sample-accurate lag from a 2 s piece in the middle of the stretch.
    seg_len = min(2 * rate, (run_b - run_a) // 2)
    seg_a = (run_a + run_b - seg_len) // 2
    seg = data[seg_a:seg_a + seg_len]
    energy = (seg ** 2).sum() + 1e-12
    coarse = lag * hop
    errs = []
    for d in range(-2 * hop, 2 * hop + 1):
        o = seg_a + coarse + d
        if o < 0 or o + seg_len > len(data):
            continue
        errs.append((((data[o:o + seg_len] - seg) ** 2).sum() / energy, coarse + d))
    err, lag = min(errs)

    # Sample-level error profile at that lag. The repeat begins where the
    # error first stays low for 2 s (the intro before it never matches); the
    # seam is the best-matching point in the 5 s after that.
    diff = ((data[:len(data) - lag] - data[lag:]) ** 2).sum(1)
    level = (data[:len(data) - lag] ** 2).sum(1)
    w = rate // 20
    kernel = np.ones(w) / w
    rel = np.convolve(diff, kernel, 'same') / (np.convolve(level, kernel, 'same') + 1e-9)
    good = rel < max(0.02, 4 * err)
    run_a = None
    edges = np.flatnonzero(np.diff(np.concatenate(([0], good.astype(np.int8), [0]))))
    for a, b in zip(edges[::2], edges[1::2]):
        if b - a >= 2 * rate:
            run_a, run_b = int(a), int(b)
            break
    if run_a is None:
        return None
    lo = run_a + rate // 4
    hi = min(run_a + 5 * rate, run_b - rate // 4)
    start = lo + int(np.argmin(rel[lo:hi]))
    return start, start + lag, float(rel[start]), float(err)


def _biquad_response(b, a, w):
    z = np.exp(-1j * w)
    return (b[0] + b[1] * z + b[2] * z * z) / (a[0] + a[1] * z + a[2] * z * z)


def loudness_lufs(data, rate):
    """Integrated loudness (ITU-R BS.1770-4: K-weighting, 400 ms blocks, gates).

    The two K-weighting filters are the standard ones (as in pyloudnorm),
    applied in the frequency domain so no extra library is needed.
    """
    x = np.asarray(data, dtype=np.float64)
    if x.ndim == 1:
        x = x[:, None]
    if len(x) < rate // 2:
        return -70.0
    # shelf: +4 dB above ~1.7 kHz; high pass: ~38 Hz
    G, fc, Q = 3.99984385397, 1681.9744509555319, 0.7071752369554193
    A, w0 = 10 ** (G / 40), 2 * np.pi * fc / rate
    al, c = np.sin(w0) / (2 * Q), np.cos(w0)
    shelf_b = [A * ((A + 1) + (A - 1) * c + 2 * np.sqrt(A) * al), -2 * A * ((A - 1) + (A + 1) * c),
               A * ((A + 1) + (A - 1) * c - 2 * np.sqrt(A) * al)]
    shelf_a = [(A + 1) - (A - 1) * c + 2 * np.sqrt(A) * al, 2 * ((A - 1) - (A + 1) * c),
               (A + 1) - (A - 1) * c - 2 * np.sqrt(A) * al]
    fc, Q = 38.13547087602444, 0.5003270373238773
    w0 = 2 * np.pi * fc / rate
    al, c = np.sin(w0) / (2 * Q), np.cos(w0)
    hp_b = [(1 + c) / 2, -(1 + c), (1 + c) / 2]
    hp_a = [1 + al, -2 * c, 1 - al]
    n = 1 << int(np.ceil(np.log2(len(x) + rate)))  # room for the filters' tails
    w = 2 * np.pi * np.fft.rfftfreq(n)
    H = _biquad_response(shelf_b, shelf_a, w) * _biquad_response(hp_b, hp_a, w)
    y = np.fft.irfft(np.fft.rfft(x, n, axis=0) * H[:, None], n, axis=0)[:len(x)]
    # mean square per 400 ms block, 75 % overlap, summed over channels
    sq = np.concatenate([np.zeros((1, y.shape[1])), np.cumsum(y * y, axis=0)])
    size, step = int(0.4 * rate), int(0.1 * rate)
    starts = np.arange(0, len(y) - size + 1, step)
    z = ((sq[starts + size] - sq[starts]) / size).sum(1)
    lk = -0.691 + 10 * np.log10(np.maximum(z, 1e-12))
    z = z[lk > -70]
    if not len(z):
        return -70.0
    rel = -0.691 + 10 * np.log10(z.mean()) - 10
    z = z[-0.691 + 10 * np.log10(z) > rel]
    return float(-0.691 + 10 * np.log10(z.mean()))


def crossfade_seam(data, start, end, rate, ms=20):
    """Blend the last few ms before `end` into the audio before `start`."""
    w = min(int(rate * ms / 1000), start, end - start)
    if w <= 0:
        return data
    out = data.copy()
    ramp = np.linspace(0.0, 1.0, w)[:, None]
    out[end - w:end] = data[end - w:end] * (1 - ramp) + data[start - w:start] * ramp
    return out


def to_pcm16(data):
    peak = float(np.abs(data).max()) if len(data) else 0.0
    return np.clip(np.round(data * 32767.0), -32768, 32767).astype('>i2').tobytes(), peak


# ------------------------------------------------------------ XACT files ----

def align(n, a=2048):
    return (n + a - 1) // a * a


def wavebank(name, pcm, frames, loop_start, loop_len, rate, channels):
    """One-entry in-memory wave bank (v46), PCM16 big endian."""
    # mini format: tag 0 (PCM), channels, rate, block align, 16-bit
    fmt = 0 | (channels << 2) | (rate << 5) | (2 * channels << 23) | (1 << 31)
    meta = struct.pack('>6I', frames << 4, fmt, 0, len(pcm), loop_start, loop_len)
    bankdata = struct.pack('>II64sIIIIQ', 0, 1, name.encode(), 24, 0, 2048, 0, 0)
    start = align(52 + 96 + len(meta))
    header = b'DNBW' + struct.pack('>II', 46, 44) + struct.pack(
        '>10I', 52, 96, 148, len(meta), 0, 0, 0, 0, start, len(pcm))
    return header + bankdata + meta + bytes(start - 148 - len(meta)) + pcm


def soundbank(name):
    """One-cue sound bank laid out like the official BGM banks.

    0x000 header (138)        0x08A wave bank name (64)
    0x0CA sound (36): complex, category 3, one track, one PlayWave event
          with loop count 255 (forever) on wave 0 of wave bank 0
    0x0EE complex cue (15)    0x0FD cue name hash table (16 buckets)
    0x11D hash entry (6)      0x123 cue name
    Every bucket points at entry 0: lookup walks the entry and compares the
    name, so the platform's hash function is not needed.
    """
    raw = name.encode()
    sound_off, cue_off, hash_off, entry_off, name_off = 0xCA, 0xEE, 0xFD, 0x11D, 0x123
    h = bytearray(b'KBDS' + struct.pack('>HHH', 46, 43, 0) + bytes(8) + b'\x03')
    h += struct.pack('>HHHHBHHH', 0, 1, 0, 16, 1, 1, 0, len(raw) + 1)
    h += struct.pack('>10I', 0xFFFFFFFF, cue_off, name_off, 0xFFFFFFFF, 0xFFFFFFFF,
                     0xFFFFFFFF, 0x8A, hash_off, entry_off, sound_off)
    h += raw.ljust(64, b'\0')
    assert len(h) == 0x8A
    out = h + raw.ljust(64, b'\0')
    # sound: flags 1 (complex), category, volume 0x5A, pitch 0, priority 0, size 36, 1 track
    sound = struct.pack('>BHBhBHB', 1, MUSIC_CATEGORY, 0x5A, 0, 0, 36, 1)
    # track: volume 0xB4, event table offset, filter bytes as in the official banks
    sound += struct.pack('>BIBBH', 0xB4, sound_off + len(sound) + 9, 0x5D, 0xC0, 1000)
    # event table: 1 event, PlayWave (type 1), no random offset, flags 0x0C,
    # wave 0, bank 0, loop count 255, no pan
    sound += struct.pack('>BIHBBHBBHH', 1, 0x20000001, 0, 0xFF, 0x0C, 0, 0, 0xFF, 0, 0)
    assert len(sound) == 36
    out += sound
    out += struct.pack('>BIIBHHB', 5, sound_off, 0, 1, 0, 0, 0)  # complex cue -> sound
    out += struct.pack('>16H', *([0] * 16))
    out += struct.pack('>IH', name_off, 0xFFFF)
    assert len(out) == name_off
    return bytes(out + raw + b'\0')


def verify_banks(name, xsb, xwb, frames, loop_start, loop_len, rate, channels):
    assert xsb[:4] == b'KBDS' and xwb[:4] == b'DNBW'
    assert xsb[74:138].rstrip(b'\0') == name.encode() == xsb[0x8A:0xCA].rstrip(b'\0')
    assert xsb[0xCA] == 1 and struct.unpack_from('>H', xsb, 0xCB)[0] == MUSIC_CATEGORY
    ev = struct.unpack_from('>I', xsb, 0xD5)[0]
    assert ev == 0xDD and xsb[ev] == 1 and struct.unpack_from('>I', xsb, ev + 1)[0] & 0x1F == 1
    assert xsb[ev + 12] == 0xFF, 'loop count'
    assert xsb[0x123:].rstrip(b'\0') == name.encode()
    segs = struct.unpack_from('>10I', xwb, 12)
    flags, count = struct.unpack_from('>II', xwb, 52)
    assert count == 1 and flags & 0xF == 0 and xwb[60:124].rstrip(b'\0') == name.encode()
    dur, fmt, off, size, ls, ll = struct.unpack_from('>6I', xwb, segs[2])
    assert fmt & 3 == 0 and (fmt >> 2) & 7 == channels and (fmt >> 5) & 0x3FFFF == rate
    assert (fmt >> 23) & 0xFF == 2 * channels and fmt >> 31 == 1
    assert dur >> 4 == frames and size == frames * 2 * channels and segs[8] + segs[9] == len(xwb)
    assert (ls, ll) == (loop_start, loop_len) and ls + ll <= frames


# ------------------------------------------------------------- the pack ----

def content_id(package):
    """42-character package file name, unique per pack number."""
    return '0' * 30 + '4D5000' + f'{package:04X}' + '58'


def bank_name(package, index):
    return f'BGM_MP{package:02d}_{index + 1:02d}'


def bgm_def(package, count):
    out = b''
    for i in range(count):
        out += struct.pack('>HH', package << 10 | TEXT_GROUP, i) + bank_name(package, i).encode().ljust(32, b'\0')
    return out


def text_file(package, titles, lang):
    groups = [[] for _ in range(TEXT_GROUPS)]
    groups[TEXT_GROUP] = [t.get(lang) or t['en'] for t in titles]
    key = hashlib.sha256(f'hod-musicpack-{package}-{lang}'.encode()).digest()[:4]
    return txrc.encode({'key': key.hex(), 'sections': [groups]})



def load_pack(path):
    path = Path(path).resolve()
    pack = json.loads(path.read_text(encoding='utf-8'))
    assert pack.get('tracks'), 'pack has no tracks'
    for t in pack['tracks']:
        assert ('file' in t) != ('xwb' in t), 'each track needs "file" (audio) or "xwb" (a ready wave bank)'
        f = Path(t.get('file') or t['xwb'])
        t['_path'] = f if f.is_absolute() else path.parent / f
        t.setdefault('file', str(f))
        assert t['_path'].is_file(), f'missing file {t["_path"]}'
        assert t.get('title'), f'{t["file"]}: no title'
    return path, pack


def prebuilt_wavebank(t, name, report):
    """Take a ready one-entry wave bank (e.g. XMA made with Microsoft's tools).

    The wave data and loop region are kept as they are; only the bank's
    internal name is changed to the pack's bank name, so that it matches the
    generated cue file and cannot collide with another package's bank.
    """
    xwb = bytearray(t['_path'].read_bytes())
    assert xwb[:4] == b'DNBW' and struct.unpack_from('>I', xwb, 4)[0] == 46, \
        f'{t["file"]}: not a big-endian (Xbox 360) XACT v46 wave bank'
    segs = struct.unpack_from('>10I', xwb, 12)
    flags, count = struct.unpack_from('>II', xwb, 52)
    assert count == 1, f'{t["file"]}: {count} waves; one music track per bank'
    assert flags & 1 == 0, f'{t["file"]}: streaming bank; the game loads music in memory'
    dur, fmt, off, size, ls, ll = struct.unpack_from('>6I', xwb, segs[2])
    frames, rate, channels = dur >> 4, (fmt >> 5) & 0x3FFFF, (fmt >> 2) & 7
    assert segs[8] + segs[9] == len(xwb) and off + size <= segs[9], f'{t["file"]}: truncated'
    if ll == 0:
        print(f'  warning: {t["file"]}: no loop region; the track plays once')
    assert ls + ll <= frames, f'{t["file"]}: loop outside the wave'
    max_mb = float(t.get('max_mb', DEFAULT_MAX_MB))
    if len(xwb) > max_mb * 2**20:
        print(f'  warning: {t["file"]}: {len(xwb) / 2**20:.2f} MB is over the {max_mb} MB budget; '
              'it may be skipped silently in game')
    xwb[60:124] = name.encode().ljust(64, b'\0')
    report.append({'xwb': str(t['_path']), 'source_sha256': hashlib.sha256(t['_path'].read_bytes()).hexdigest(),
                   'format': {0: 'PCM', 1: 'XMA', 2: 'ADPCM', 3: 'WMA'}[fmt & 3], 'rate': rate,
                   'channels': channels, 'frames': frames, 'seconds': frames / max(rate, 1),
                   'loop': 'from wave bank', 'loop_start_seconds': ls / max(rate, 1),
                   'loop_end_seconds': (ls + ll) / max(rate, 1), 'max_mb': max_mb})
    return bytes(xwb)


# ------------------------------------------------- single-file package ----
#
# Official DLC ships as one read-only STFS file ("LIVE"), which HarmonyRecomp
# installs from its dlc/ folder at start (src/dlc.cpp, if the file is listed in
# dlc_packages.txt) and its setup includes like any DLC. Layout per the
# recomp's reader (scripts/extract_game.py) and the SDK (stfs_xbox.h):
#   header (0x971A bytes, padded to a 4 KB block), then 4 KB blocks with one
#   hash table per level: level 0 covers 170 data blocks (SHA-1 + next block
#   in the file's chain), level 1 covers 170 level-0 tables, level 2 covers
#   170 level-1 tables. The volume descriptor holds the top table's SHA-1.
# The signature is left empty: the recomp does not check it (a console would
# refuse the file, which is not the point).

STFS_BLOCK = 0x1000
STFS_HEADER = 0x971A
STFS_L0, STFS_L1 = 0xAA, 0xAA * 0xAA
STFS_END = 0xFFFFFF


def _fat_datetime(t=None):
    import time
    t = time.localtime(t)
    date = ((t.tm_year - 1980) << 9) | (t.tm_mon << 5) | t.tm_mday
    clock = (t.tm_hour << 11) | (t.tm_min << 5) | (t.tm_sec // 2)
    return date, clock


def _stfs_layout(n):
    """Physical block (after the header) of every data block and hash table."""
    data, l0, l1, l2 = [], [], [], None
    pos = 0
    for b in range(n):
        if b % STFS_L0 == 0:
            if b and b % STFS_L1 == 0:
                if l2 is None:
                    l2, pos = pos, pos + 1
                l1.append(pos)
                pos += 1
            elif b == STFS_L0:
                l1.append(pos)
                pos += 1
            l0.append(pos)
            pos += 1
        data.append(pos)
        pos += 1
    if n == 0:
        l0.append(0)
        pos = 1
    return data, l0, l1, l2, pos


def write_stfs(src, out, display_name, package):
    """Pack folder `src` into one LIVE package at `out` (file name = content id)."""
    src = Path(src)
    entries = []  # (name, is_dir, parent index, path)
    index = {src: 0xFFFF}
    queue = [src]
    while queue:  # directories first, breadth first, then files (as official packs)
        d = queue.pop(0)
        for p in sorted(x for x in d.iterdir() if x.is_dir()):
            index[p] = len(entries)
            entries.append((p.name, True, index[d], p))
            queue.append(p)
    for d in list(index):
        for p in sorted(x for x in d.iterdir() if x.is_file()):
            entries.append((p.name, False, index[d], p))
    for name, *_ in entries:
        assert len(name) <= 40 and name.isascii(), f'file name not allowed in a package: {name}'

    table_blocks = max(1, -(-len(entries) // 64))
    blocks = [None] * table_blocks
    chains = [(0, table_blocks)]
    raw_entries = []
    date, clock = _fat_datetime()
    for name, is_dir, parent, p in entries:
        if is_dir:
            start = count = size = 0
        else:
            data = p.read_bytes()
            size, count, start = len(data), -(-len(data) // STFS_BLOCK), len(blocks)
            for i in range(count):
                blocks.append(data[i * STFS_BLOCK:(i + 1) * STFS_BLOCK].ljust(STFS_BLOCK, b'\0'))
            if count:
                chains.append((start, count))
        e = bytearray(0x40)
        e[:len(name)] = name.encode()
        e[0x28] = len(name) | (0x80 if is_dir else 0)
        e[0x29:0x2C] = count.to_bytes(3, 'little')
        e[0x2C:0x2F] = count.to_bytes(3, 'little')
        e[0x2F:0x32] = start.to_bytes(3, 'little')
        struct.pack_into('>HIHHHH', e, 0x32, parent, size, date, clock, date, clock)
        raw_entries.append(bytes(e))
    table = b''.join(raw_entries).ljust(table_blocks * STFS_BLOCK, b'\0')
    for i in range(table_blocks):
        blocks[i] = table[i * STFS_BLOCK:(i + 1) * STFS_BLOCK]

    n = len(blocks)
    nxt = [STFS_END] * n
    for start, count in chains:
        for i in range(start, start + count - 1):
            nxt[i] = i + 1
    data_pos, l0_pos, l1_pos, l2_pos, total = _stfs_layout(n)
    body = bytearray(total * STFS_BLOCK)
    for i, blk in enumerate(blocks):
        body[data_pos[i] * STFS_BLOCK:(data_pos[i] + 1) * STFS_BLOCK] = blk

    def table_block(hashes_infos):
        t = bytearray(STFS_BLOCK)
        for k, (h, info) in enumerate(hashes_infos):
            t[k * 0x18:k * 0x18 + 0x14] = h
            struct.pack_into('>I', t, k * 0x18 + 0x14, info)
        return bytes(t)

    l0_tables = []
    for g, pos in enumerate(l0_pos):
        rng = range(g * STFS_L0, min(n, (g + 1) * STFS_L0))
        t = table_block([(hashlib.sha1(blocks[i]).digest(), 0x80000000 | nxt[i]) for i in rng])
        body[pos * STFS_BLOCK:(pos + 1) * STFS_BLOCK] = t
        l0_tables.append(t)
    top = l0_tables[0]
    l1_tables = []
    for k, pos in enumerate(l1_pos):
        rng = l0_tables[k * STFS_L0:(k + 1) * STFS_L0]
        t = table_block([(hashlib.sha1(x).digest(), 0) for x in rng])
        body[pos * STFS_BLOCK:(pos + 1) * STFS_BLOCK] = t
        l1_tables.append(t)
    if l1_tables:
        top = l1_tables[0]
    if l2_pos is not None:
        top = table_block([(hashlib.sha1(x).digest(), 0) for x in l1_tables])
        body[l2_pos * STFS_BLOCK:(l2_pos + 1) * STFS_BLOCK] = top

    h = bytearray(-(-STFS_HEADER // STFS_BLOCK) * STFS_BLOCK)
    h[0:4] = b'LIVE'
    struct.pack_into('>QII', h, 0x22C, 0xFFFFFFFFFFFFFFFF, 1, 1)   # licensed to everyone
    struct.pack_into('>I', h, 0x340, STFS_HEADER)
    struct.pack_into('>II', h, 0x344, 2, 2)                          # marketplace content, metadata v2
    struct.pack_into('>Q', h, 0x34C, total * STFS_BLOCK)
    struct.pack_into('>I', h, 0x360, TITLE_ID)
    vd = bytearray(0x24)
    vd[0], vd[1], vd[2] = 0x24, 0, 1                                  # read-only format
    vd[3:5] = table_blocks.to_bytes(2, 'little')
    vd[5:8] = (0).to_bytes(3, 'little')
    vd[8:0x1C] = hashlib.sha1(top).digest()
    struct.pack_into('>II', vd, 0x1C, n, 0)
    h[0x379:0x379 + 0x24] = vd
    name = display_name.encode('utf-16-be')[:0xFE]
    for lang in range(9):                                             # every language slot
        h[0x411 + lang * 0x100:0x411 + lang * 0x100 + len(name)] = name
    title = 'Castlevania Harmony of Despair'.encode('utf-16-be')
    h[0x1691:0x1691 + len(title)] = title
    h[0x1711] = 0xC0
    h[0x32C:0x340] = hashlib.sha1(bytes(h[0x344:STFS_HEADER])).digest()
    out = Path(out)
    out.write_bytes(bytes(h) + bytes(body))
    return out


def read_stfs(path, verify=True):
    """Files of a LIVE/PIRS package as {path: bytes}; checks every hash if asked."""
    b = Path(path).read_bytes()
    assert b[:4] in (b'LIVE', b'PIRS', b'CON '), 'not an Xbox 360 package'
    hs = int.from_bytes(b[0x340:0x344], 'big')
    base = -(-hs // STFS_BLOCK)
    vd = b[0x379:0x379 + 0x24]
    ft_blocks = int.from_bytes(vd[3:5], 'little')
    ft_start = int.from_bytes(vd[5:8], 'little')
    n = int.from_bytes(vd[0x1C:0x20], 'big')
    data_pos, l0_pos, l1_pos, l2_pos, _ = _stfs_layout(n)

    def blk(phys):
        o = (base + phys) * STFS_BLOCK
        return b[o:o + STFS_BLOCK]

    def entry(logical):
        t = blk(l0_pos[logical // STFS_L0])
        k = logical % STFS_L0
        return t[k * 0x18:k * 0x18 + 0x14], int.from_bytes(t[k * 0x18 + 0x15:k * 0x18 + 0x18], 'big')

    if verify:
        for i in range(n):
            assert entry(i)[0] == hashlib.sha1(blk(data_pos[i])).digest(), f'block {i} hash'
        for k, pos in enumerate(l1_pos):
            t = blk(pos)
            for j, p0 in enumerate(l0_pos[k * STFS_L0:(k + 1) * STFS_L0]):
                assert t[j * 0x18:j * 0x18 + 0x14] == hashlib.sha1(blk(p0)).digest(), 'level-1 hash'
        top = blk(l2_pos) if l2_pos is not None else blk(l1_pos[0]) if l1_pos else blk(l0_pos[0])
        assert hashlib.sha1(top).digest() == vd[8:0x1C], 'top hash'

    def chain(start, count):
        out, cur = [], start
        for i in range(count):
            out.append(cur)
            if i + 1 < count:
                cur = entry(cur)[1]
        return out

    raw = b''.join(blk(data_pos[i]) for i in chain(ft_start, ft_blocks))
    entries = []
    for k in range(len(raw) // 0x40):
        e = raw[k * 0x40:(k + 1) * 0x40]
        if not e[0x28] & 0x3F:
            break
        entries.append((e[:e[0x28] & 0x3F].decode('ascii'), bool(e[0x28] & 0x80),
                        int.from_bytes(e[0x2F:0x32], 'little'), int.from_bytes(e[0x29:0x2C], 'little'),
                        int.from_bytes(e[0x32:0x34], 'big'), int.from_bytes(e[0x34:0x38], 'big')))

    def full(i):
        name, _, _, _, parent, _ = entries[i]
        return name if parent == 0xFFFF else full(parent) + '/' + name

    files = {}
    for i, (name, is_dir, start, count, parent, size) in enumerate(entries):
        if not is_dir:
            files[full(i)] = b''.join(blk(data_pos[x]) for x in chain(start, count))[:size] if count else b''
    return files


def package_number(files):
    """Package number from a package's 000info/packageNN.dat."""
    for p in files:
        m = re.fullmatch(r'000info/package(\d+)\.dat', p, re.I)
        if m:
            return int(m.group(1))
    return None


def installed_packages(game=None):
    """Pack numbers already in use: official, unpacked, or listed for the game."""
    used = set(USED_PACKAGES)
    if game:
        try:
            for line in (Path(game) / 'dlc_packages.txt').read_text(errors='replace').splitlines():
                m = re.fullmatch(r'package(\d+)', line.split('\t')[-1].strip())
                if m:
                    used.add(int(m.group(1)))
        except OSError:
            pass
    root = CONTENT / '00000002'
    if root.is_dir():
        for p in root.glob('*/000info/package*.dat'):
            m = re.match(r'package(\d+)\.dat$', p.name, re.I)
            if m:
                used.add(int(m.group(1)))
    return used


def choose_package(pack):
    if pack.get('package'):
        n = int(pack['package'])
        assert 1 <= n <= 63, 'package number must be 1..63 (the text id keeps 6 bits)'
        return n
    used = installed_packages()
    for n in list(range(18, 28)) + list(range(30, 64)):
        if n not in used:
            return n
    raise RuntimeError('no free package number')


def _sliding_min(a, w):
    """min(a[i:i+w]) for every i (van Herk / Gil-Werman, O(n))."""
    n = len(a)
    ap = np.concatenate([a, np.ones((-n) % w + w)])
    blocks = ap.reshape(-1, w)
    prefix = np.minimum.accumulate(blocks, axis=1).ravel()
    suffix = np.minimum.accumulate(blocks[:, ::-1], axis=1)[:, ::-1].ravel()
    i = np.arange(n)
    return np.minimum(suffix[i], prefix[i + w - 1])


def limit_peaks(x, rate, ceiling=PEAK_CEILING, attack_ms=5, hold_ms=40):
    """Look-ahead peak limiter: gain ramps down over `attack_ms` before a peak,
    holds `hold_ms`, then ramps back. Returns (audio, largest reduction in dB)."""
    peak = np.abs(x).max(1)
    need = np.minimum(1.0, ceiling / np.maximum(peak, 1e-12))
    if need.min() >= 1.0:
        return x, 0.0
    a, h = max(2, int(rate * attack_ms / 1000)), max(2, int(rate * hold_ms / 1000))
    held = _sliding_min(np.concatenate([np.ones(a), need]), a + h)[:len(need)]
    c = np.concatenate([[0.0], np.cumsum(np.concatenate([np.ones(a // 2), held, np.ones(a - a // 2)]))])
    gain = (c[a:a + len(held)] - c[:len(held)]) / a
    gain = np.minimum(gain, 1.0)
    y = np.clip(x * gain[:, None], -ceiling, ceiling)
    return y, float(-20 * np.log10(gain.min()))


def prepare_track(t, report):
    data, rate = load_audio(t['_path'])
    loop = t.get('loop', 'auto')
    info = {'file': str(t['_path']), 'source_rate': rate, 'source_seconds': len(data) / rate}
    if loop == 'whole':
        s, e = 0, len(data)
        info['loop'] = 'whole file'
    elif isinstance(loop, dict):
        s, e = int(round(loop['start'] * rate)), int(round(loop['end'] * rate))
        assert 0 <= s < e <= len(data), f'{t["file"]}: loop outside the audio'
        info['loop'] = 'from pack file'
    else:
        found = find_loop(data, rate)
        if found is None:
            print(f'  warning: {t["file"]}: no repeat found; the whole file loops')
            s, e = 0, len(data)
            info['loop'] = 'auto: no repeat found, whole file'
        else:
            s, e, seam_err, lag_err = found
            info['loop'] = 'auto'
            info['seam_error'] = seam_err
            info['lag_error'] = lag_err
            if seam_err > 0.05:
                print(f'  warning: {t["file"]}: weak loop match ({seam_err:.3f}); check the seam preview')
    # Volume: match the official music (measured over the part that is kept),
    # plus the song's own adjustment.
    gain = float(t.get('gain_db', 0))
    if t.get('auto_volume', True):
        before = loudness_lufs(data[:e], rate)
        info['loudness_source_lufs'] = before
        gain += GAME_MUSIC_LUFS - before
    if gain:
        data = data * 10 ** (gain / 20)
    # Pick the bank format from the budget, then resample: loop points scale
    # with the rate, and the audio stops at the loop end.
    max_mb = float(t.get('max_mb', DEFAULT_MAX_MB))
    out_rate, channels, _, over_budget = track_format(e / rate, t)
    src = data[:e] if channels == 2 else data[:e].mean(1, keepdims=True)
    out = resample(src, rate, out_rate)
    if out.ndim == 1:
        out = out[:, None]
    s48 = int(round(s * out_rate / rate))
    e48 = min(len(out), int(round(e * out_rate / rate)))
    out = out[:e48]
    if s48 > 0:
        out = crossfade_seam(out, s48, e48, out_rate)
    # Peaks: limit at most MAX_LIMIT_DB; anything beyond that lowers the whole
    # song instead (it then ends up quieter than the game's music).
    peak = float(np.abs(out).max()) if len(out) else 0.0
    over = 20 * np.log10(max(peak, 1e-12) / PEAK_CEILING) - MAX_LIMIT_DB
    if over > 0:
        out = out * 10 ** (-over / 20)
        gain -= over
        print(f'  note: {t["file"]}: {over:.1f} dB quieter than the game\'s music, to avoid squashing it')
    pre = out
    out, limited = limit_peaks(pre, out_rate)
    level = loudness_lufs(out, out_rate)
    # Limiting takes a little loudness back; nudge up to the target again
    # while the peak reduction stays within MAX_LIMIT_DB.
    for _ in range(3):
        if not t.get('auto_volume', True) or over > 0 or GAME_MUSIC_LUFS - level < 0.15:
            break
        peak_db = 20 * np.log10(max(float(np.abs(pre).max()), 1e-12) / PEAK_CEILING)
        extra = min(GAME_MUSIC_LUFS - level, MAX_LIMIT_DB - peak_db)
        if extra < 0.05:
            break
        pre = pre * 10 ** (extra / 20)
        gain += extra
        out, limited = limit_peaks(pre, out_rate)
        level = loudness_lufs(out, out_rate)
    info.update(gain_db=gain, limited_db=limited, loudness_lufs=level)
    info.update(loop_start_seconds=s / rate, loop_end_seconds=e / rate, rate=out_rate,
                channels=channels, max_mb=max_mb, over_budget=over_budget, loop_start_sample=s48,
                loop_length=e48 - s48, frames=e48, seconds=e48 / out_rate)
    report.append(info)
    return out, s48, e48 - s48, out_rate, channels


def seam_preview(audio, start, length, rate, path, seconds=4):
    """Loop end followed by the loop start, as the game will play it."""
    import soundfile as sf
    end = start + length
    a = audio[max(start, end - seconds * rate):end]
    b = audio[start:start + seconds * rate]
    sf.write(str(path), np.concatenate([a, b]), rate, subtype='PCM_16')


def build(pack_path, out_dir=None):
    pack_path, pack = load_pack(pack_path)
    package = choose_package(pack)
    pid = content_id(package)
    out_dir = Path(out_dir) if out_dir else BUILDS / pack_path.stem
    if out_dir.exists():
        shutil.rmtree(out_dir)
    pkg = out_dir / 'contents'  # the package's files; out_dir/<id> is the package itself
    (pkg / '000info').mkdir(parents=True)
    (pkg / 'data/sound').mkdir(parents=True)
    (pkg / 'data/text').mkdir(parents=True)
    (out_dir / 'preview').mkdir()
    (pkg / '000info' / f'package{package:02d}.dat').write_bytes(b'PackageInfo\r\n')

    report, titles = [], []
    print(f'Pack {pack.get("name", pack_path.stem)!r}: package {package:02d}, id {pid}')
    for i, t in enumerate(pack['tracks']):
        name = bank_name(package, i)
        print(f'  {name}: {t["title"]}')
        if 'xwb' in t:
            xwb = prebuilt_wavebank(t, name, report)
            xsb = soundbank(name)
            r = report[-1]
            (pkg / 'data/sound' / f'{name}.xwb').write_bytes(xwb)
            (pkg / 'data/sound' / f'{name}.xsb').write_bytes(xsb)
            r.update(bank=name, title=t['title'], xwb_bytes=len(xwb))
            print(f'    ready-made {r["format"]} bank, loop {r["loop_start_seconds"]:.3f}s -> '
                  f'{r["loop_end_seconds"]:.3f}s, {r["rate"]} Hz, {len(xwb) / 2**20:.2f} MB')
            titles.append({'en': t['title'], **t.get('titles', {})})
            continue
        t.setdefault('auto_volume', pack.get('match_game_volume', True))
        t.setdefault('sample_rate', pack.get('sample_rate', 'auto'))
        t.setdefault('mono', pack.get('mono', False))
        audio, ls, ll, rate, channels = prepare_track(t, report)
        pcm, peak = to_pcm16(audio)
        if peak > 1.0:
            print(f'  warning: {t["file"]}: clipped (peak {peak:.2f}); lower gain_db')
        frames = len(audio)
        xwb = wavebank(name, pcm, frames, ls, ll, rate, channels)
        xsb = soundbank(name)
        verify_banks(name, xsb, xwb, frames, ls, ll, rate, channels)
        r = report[-1]
        if len(xwb) > r['max_mb'] * 2**20:
            assert t['sample_rate'] not in (None, 'auto', 0, ''), f'{name}: {len(xwb)} bytes is over the budget'
            print(f'  warning: {t["file"]}: {len(xwb) / 2**20:.2f} MB at {rate} Hz is over the '
                  f'{r["max_mb"]} MB limit; the game may skip it (listed but silent)')
        (pkg / 'data/sound' / f'{name}.xwb').write_bytes(xwb)
        (pkg / 'data/sound' / f'{name}.xsb').write_bytes(xsb)
        seam_preview(audio, ls, ll, rate, out_dir / 'preview' / f'{i + 1:02d}_{name}_seam.wav')
        r.update(bank=name, title=t['title'], peak=peak, xwb_bytes=len(xwb))
        print(f'    loop {r["loop_start_seconds"]:.3f}s -> {r["loop_end_seconds"]:.3f}s '
              f'({r["loop"]}), {r["seconds"]:.1f} of {r["source_seconds"]:.1f}s kept, {rate} Hz '
              f'{"stereo" if channels == 2 else "mono"}, {len(xwb) / 2**20:.2f} MB')
        vol = f'    volume {r["gain_db"]:+.1f} dB -> {r["loudness_lufs"]:.1f} LUFS'
        if 'loudness_source_lufs' in r:
            vol += f' (was {r["loudness_source_lufs"]:.1f}; game music {GAME_MUSIC_LUFS})'
        if r['limited_db'] > 0.05:
            vol += f', peaks limited by up to {r["limited_db"]:.1f} dB'
        print(vol)
        titles.append({'en': t['title'], **t.get('titles', {})})

    (pkg / 'data/sound' / f'bgm{package:02d}_def.dat').write_bytes(bgm_def(package, len(titles)))
    for lang in LANGS:
        data = text_file(package, titles, lang)
        back = txrc.decode(data)['sections'][0][TEXT_GROUP]
        assert back == [t.get(lang) or t['en'] for t in titles]
        (pkg / 'data/text' / f'textres{package:02d}_{lang}.txrc').write_bytes(data)
    package_file = write_stfs(pkg, out_dir / pid, pack.get('name', pack_path.stem), package)
    back = read_stfs(package_file)  # every hash, and every file byte for byte
    assert back == {p.relative_to(pkg).as_posix(): p.read_bytes() for p in pkg.rglob('*') if p.is_file()}
    (out_dir / 'report.json').write_text(json.dumps(
        {'name': pack.get('name'), 'package': package, 'id': pid, 'tracks': report}, indent=2) + '\n')
    print(f'Built and verified {len(titles)} track(s): {out_dir}')
    print(f'DLC file: {package_file} ({package_file.stat().st_size / 2**20:.1f} MB)')
    if any((out_dir / 'preview').iterdir()):
        print(f'Listen to the loop seams in {out_dir / "preview"}')  # none for ready-made banks
    return out_dir, package, pid


def package_file_of(out_dir, pid):
    return Path(out_dir) / pid


# --------------------------------------------------------------- install ----

def running_processes():
    """Lower-case names of running programs, read straight from Windows.

    (Running "tasklist" instead flashes a console window from the GUI.)
    """
    import ctypes
    from ctypes import wintypes

    class PROCESSENTRY32W(ctypes.Structure):
        _fields_ = [('dwSize', wintypes.DWORD), ('cntUsage', wintypes.DWORD),
                    ('th32ProcessID', wintypes.DWORD), ('th32DefaultHeapID', ctypes.c_size_t),
                    ('th32ModuleID', wintypes.DWORD), ('cntThreads', wintypes.DWORD),
                    ('th32ParentProcessID', wintypes.DWORD), ('pcPriClassBase', ctypes.c_long),
                    ('dwFlags', wintypes.DWORD), ('szExeFile', ctypes.c_wchar * 260)]

    k32 = ctypes.WinDLL('kernel32', use_last_error=True)
    k32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    snap = k32.CreateToolhelp32Snapshot(0x2, 0)  # TH32CS_SNAPPROCESS
    if not snap or snap == wintypes.HANDLE(-1).value:
        return set()
    names = set()
    try:
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(entry)
        ok = k32.Process32FirstW(snap, ctypes.byref(entry))
        while ok:
            names.add(entry.szExeFile.lower())
            ok = k32.Process32NextW(snap, ctypes.byref(entry))
    finally:
        k32.CloseHandle(snap)
    return names


def game_running():
    try:
        return 'harmonyrecomp.exe' in running_processes()
    except (OSError, AttributeError):
        return False


def is_game_folder(game):
    """A HarmonyRecomp install: the exe plus the DLC list its build wrote."""
    game = Path(game) if game else None
    return bool(game) and (game / 'harmonyrecomp.exe').is_file() and (game / 'dlc_packages.txt').is_file()


def setup_dlc_folder(game):
    """The DLC folder the HarmonyRecomp setup builds from (its setup.log says)."""
    log = Path(game) / 'setup.log'
    folder = None
    try:
        for line in log.read_text(encoding='utf-8', errors='replace').splitlines():
            if line.startswith('DLC folder:'):
                folder = line.split(':', 1)[1].strip()
    except OSError:
        return None
    folder = Path(folder) if folder else None
    return folder if folder and folder.is_dir() else None


def _setup_copies(game, name):
    """Copies of a package file inside the setup's DLC folder."""
    folder = setup_dlc_folder(game)
    if not folder:
        return []
    return [p for p in folder.rglob(name) if p.is_file()]


def dlc_lists(game):
    lists = [game / 'dlc_packages.txt']
    gen = game / '.setup/package/src/generated/dlc_packages.txt'
    if gen.exists():
        lists.append(gen)
    return lists


def set_listed(path, pid, line, present):
    text = path.read_bytes().decode('utf-8') if path.exists() else ''
    newline = '\r\n' if '\r\n' in text else '\n'
    lines = [l for l in text.splitlines() if l.split('\t')[0].strip() != pid]
    if present:
        lines.append(line)
    new = newline.join(lines) + (newline if lines else '')
    if new != text:
        path.write_bytes(new.encode('utf-8'))
        print(('Listed in ' if present else 'Removed from ') + str(path))


def _remove_installed_copy(name):
    """The unpacked copy the recomp made from a package, so it unpacks the new one."""
    for p in (CONTENT / '00000002' / name, CONTENT / 'Headers/00000002' / f'{name}.header'):
        if p.is_dir():
            shutil.rmtree(p)
            print('Removed', p)
        elif p.exists():
            p.unlink()
            print('Removed', p)


def install_file(package_file, game, music=True):
    """Install one music pack file the way official DLC is installed.

    The file goes into <game>/dlc/ and is listed in dlc_packages.txt; the recomp
    unpacks it into its content folder the next time it starts. A copy also
    goes into the setup's DLC folder (from setup.log), so re-running the
    HarmonyRecomp setup keeps the pack.
    """
    game, package_file = Path(game), Path(package_file)
    if game_running():
        raise RuntimeError('Close HarmonyRecomp first')
    assert (game / 'dlc_packages.txt').exists(), (
        f'No dlc_packages.txt in {game}. Choose the HarmonyRecomp folder (the one with harmonyrecomp.exe); '
        'the list is written by the recomp setup when it is built with DLC.')
    files = read_stfs(package_file)
    package = package_number(files)
    assert package, f'{package_file.name}: not a Harmony of Despair DLC package (no 000info/packageNN.dat)'
    assert not any(p.lower().endswith(('.dll', '.xex')) for p in files), (
        f'{package_file.name} contains game code; only the HarmonyRecomp setup can add such DLC')
    if music:  # other data-only packs (shield_rod.py) install the same way
        assert f'data/sound/bgm{package:02d}_def.dat' in files, f'{package_file.name} is not a music pack'
    if package in OFFICIAL_PACKAGES:
        raise RuntimeError(f'package {package} is official DLC')
    name = package_file.name
    assert len(name) <= 42 and name.isalnum(), f'{name}: the file name must be the 42-character package id'
    others = [l for l in (game / 'dlc_packages.txt').read_text(encoding='utf-8', errors='replace').splitlines()
              if l.split('\t')[-1].strip() == f'package{package:02d}' and l.split('\t')[0].strip() != name]
    assert not others, f'package {package} is already used by {others[0].split(chr(9))[0]}'

    dlc = game / 'dlc'
    dlc.mkdir(exist_ok=True)
    if package_file.resolve() != (dlc / name).resolve():
        shutil.copyfile(package_file, dlc / name)
    print('Copied to', dlc / name)
    folder = setup_dlc_folder(game)
    if folder:
        sub = folder / '00000002' if (folder / '00000002').is_dir() else folder
        copies = _setup_copies(game, name) or [sub / name]
        for c in copies:
            if c.resolve() != package_file.resolve():
                shutil.copyfile(package_file, c)
            print('Copied to', c, '(kept when the HarmonyRecomp setup is run again)')
    else:
        print('Note: no HarmonyRecomp setup DLC folder found; after re-running the setup, install again.')
    _remove_installed_copy(name)
    legacy = game / '.setup/package/src/mods' / name  # earlier versions of this tool
    if legacy.is_dir():
        shutil.rmtree(legacy)
        print('Removed', legacy)
    for path in dlc_lists(game):
        set_listed(path, name, f'{name}\tpackage{package:02d}', True)
    print(f'Installed {"music pack" if music else "package"} {package}. HarmonyRecomp unpacks it when the game starts.')
    return package


def install(pack_path, game):
    out_dir, package, pid = build(pack_path)
    return install_file(package_file_of(out_dir, pid), game)


def uninstall_package(package, game):
    game = Path(game)
    if game_running():
        raise RuntimeError('Close HarmonyRecomp first')
    assert package not in OFFICIAL_PACKAGES, f'package {package} is official DLC'
    names = {content_id(package)}
    for path in dlc_lists(game):  # a pack file someone shared may have another name
        if path.exists():
            for l in path.read_text(encoding='utf-8', errors='replace').splitlines():
                if l.split('\t')[-1].strip() == f'package{package:02d}':
                    names.add(l.split('\t')[0].strip())
    for name in names:
        for p in [game / 'dlc' / name, game / '.setup/package/src/mods' / name] + _setup_copies(game, name):
            if p.is_dir():
                shutil.rmtree(p)
                print('Removed', p)
            elif p.exists():
                p.unlink()
                print('Removed', p)
        _remove_installed_copy(name)
        for path in dlc_lists(game):
            set_listed(path, name, '', False)
    print(f'Music pack {package} removed.')


def uninstall(pack_path, game):
    pack = json.loads(Path(pack_path).read_text(encoding='utf-8'))  # the songs may be gone by now
    assert pack.get('package'), 'uninstall needs "package" in the pack file'
    uninstall_package(int(pack['package']), game)


def installed_state(package, game):
    """'installed', 'pending' (file in place, unpacked at next start) or None."""
    name = content_id(package)
    listed = False
    if game:
        try:
            listed = any(l.split('\t')[-1].strip() == f'package{package:02d}'
                         for l in (Path(game) / 'dlc_packages.txt').read_text(errors='replace').splitlines())
        except OSError:
            pass
    if (CONTENT / '00000002' / name).is_dir():
        return 'installed'
    if listed:
        return 'pending'
    return None


def init(folder, pack_path):
    import soundfile as sf
    folder = Path(folder)
    pack_path = Path(pack_path)
    files = sorted(p for p in folder.iterdir() if p.suffix.lower() in AUDIO_EXT)
    assert files, f'no audio files in {folder}'
    tracks = []
    for p in files:
        try:
            title = sf.SoundFile(str(p)).copy_metadata().get('title')
        except RuntimeError:
            title = None
        title = title or re.sub(r'^\d+[\s._-]*', '', p.stem)
        tracks.append({'file': str(p.resolve()), 'title': title, 'loop': 'auto'})
    pack = {'name': folder.name + ' Music Pack', 'package': choose_package({}), 'tracks': tracks}
    pack_path.parent.mkdir(parents=True, exist_ok=True)
    pack_path.write_text(json.dumps(pack, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(f'Wrote {pack_path} with {len(tracks)} track(s); edit titles and loops, then build')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('init'); p.add_argument('folder'); p.add_argument('pack')
    p = sub.add_parser('build'); p.add_argument('pack'); p.add_argument('--out')
    for name in ('install', 'uninstall', 'install-file'):
        p = sub.add_parser(name); p.add_argument('pack' if name != 'install-file' else 'file')
        p.add_argument('--game', default=str(ROOT), help='folder with harmonyrecomp.exe')
    a = ap.parse_args()
    if a.cmd == 'init':
        init(a.folder, a.pack)
    elif a.cmd == 'build':
        build(a.pack, a.out)
    elif a.cmd == 'install':
        install(a.pack, Path(a.game))
    elif a.cmd == 'install-file':
        install_file(a.file, Path(a.game))
    else:
        uninstall(a.pack, Path(a.game))


if __name__ == '__main__':
    main()
