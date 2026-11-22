"""Cerberus's sounds: an enemy voice bank like the official DLC bosses' (8-bit Dracula ships
VX_ENEMY_FC_DRACULA with cue VX_EN_FC_DRACULA_LAND; Beelzebub VX_ENEMY_BEELZEBUB), built from
the user's own CotM ROM.

The game asks each enemy module for its bank through vtable slot 103 (Dracula 0x8BF11540
returns the name; Legion returns 0) and plays a cue when the module appends {cue name,
x, y} to its list at module +0xFC (Dracula 0x8BF13E34). cerberus_module.py points
DLL_Cm068's slot 103 at a function src/cerberus_module.cpp overrides to return the name.

Sounds (CotM sound IDs, from the boss's code; CERBERUS_SPEC.md), rendered by agbplay
(cotm_extract.py renders into modding/build/cotm/audio/pcm16):
  0x163 howl (before each attack)      0x164 leap          0x165 growl (shakes, B0, D0)
  0x167 landing thud                   0x166 laser hum (CotM: 0xB3 << 1; loops, cut to 3 s here)
  0x169 orb flare                      0x186 death howl
Stored mono 22050 Hz PCM16 (the game's sound heap is 16 MB and drops banks that do not
fit; the GBA sources are lower quality than this anyway).

  python modding/tools/cerberus_audio.py     # writes modding/build/cerberus/sound/*.xsb/.xwb
"""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import struct
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import nathan_audio_assets as na

BANK = 'VX_ENEMY_CERBERUS'
BANK_JP = 'VXJ_ENEMY_CERBERUS'
CUES = [('VX_EN_CERB_HOWL', 0x163), ('VX_EN_CERB_LEAP', 0x164), ('VX_EN_CERB_GROWL', 0x165),
        ('VX_EN_CERB_LAND', 0x167), ('VX_EN_CERB_LASER', 0x166), ('VX_EN_CERB_FLARE', 0x169),
        ('VX_EN_CERB_DEATH', 0x186)]
MAX_SECONDS = {0x166: 3.0}           # the laser hum loops in CotM (stopped after the sweep)
RATE = 22050
CATEGORY = 7                      # as VX_ENEMY_FC_DRACULA's sound
VOLUME = 110                      # XACT byte (FAudio curve: 80 = -14 dB, 110 = -8.6 dB, 180 = 0 dB);
                                  # was 80, user 2026-11-21: "a bit quiet". Dracula's bank 64, Nathan's 90
PEAK = 29000                      # all clips scaled by one gain so the loudest peaks here (-1 dBFS): CotM's mix kept
OUT = na.hodpaths.legacy('modding/build/cerberus/sound')


def clip(sid):
    """Mono 22050 Hz float samples of a rendered CotM sound, silence trimmed."""
    data, frames, _ = na.pcm(sid)                        # trimmed 48 kHz stereo, big endian
    st = np.frombuffer(data, dtype='>i2').reshape(-1, 2).astype(np.float32)
    mono = st.mean(axis=1)
    n = int(len(mono) * RATE / 48000)
    mono = np.interp(np.linspace(0, len(mono) - 1, n), np.arange(len(mono)), mono)
    if sid in MAX_SECONDS:
        mono = mono[:int(MAX_SECONDS[sid] * RATE)]
    return mono


def pcm16(mono, gain):
    out = np.clip(np.round(mono * gain), -32768, 32767).astype('>i2')
    return out.tobytes(), len(out)


def wavebank(name, clips):
    meta, payload = bytearray(), bytearray()
    for data, frames in clips:
        offset = na.align(len(payload)); payload.extend(bytes(offset - len(payload))); payload.extend(data)
        fmt = (1 << 2) | (RATE << 5) | (2 << 23) | (1 << 31)      # PCM, mono, 22050, block 2, 16-bit
        meta.extend(struct.pack('>6I', frames << 4, fmt, offset, len(data), 0, 0))
    bankdata = struct.pack('>II64sIIIIQ', 0, len(clips), name.encode(), 24, 0, 2048, 0, 0)
    start = na.align(52 + 96 + len(meta))
    header = b'DNBW' + struct.pack('>II', 46, 44) + struct.pack('>10I', 52, 96, 148, len(meta), 0, 0, 0, 0, start, len(payload))
    return header + bankdata + meta + bytes(start - 148 - len(meta)) + payload


def soundbank(name, cue_names):
    """As nathan_audio_assets.soundbank, with our cue names, category and volume."""
    count = len(cue_names)
    sound_offset = 202; cue_offset = sound_offset + count * 12
    hash_offset = cue_offset + count * 5; index_offset = hash_offset + 32; name_offset = index_offset + count * 6
    sound, cue, indexes, strings = bytearray(), bytearray(), bytearray(), bytearray()
    for i, label in enumerate(cue_names):
        sound.extend(struct.pack('>BHBhBHHB', 0, CATEGORY, VOLUME, 0, 255, 12, i, 0))
        cue.extend(struct.pack('>BI', 4, sound_offset + i * 12))
        indexes.extend(struct.pack('>IH', name_offset + len(strings), i + 1 if i < count - 1 else 0xffff))
        strings.extend(label.encode() + b'\0')
    header = bytearray(b'KBDS' + struct.pack('>HHH', 46, 43, 0) + bytes(8) + b'\x03')
    header.extend(struct.pack('>HHHHBHHH', count, 0, 0, 16, 1, count, 0, len(strings)))
    header.extend(struct.pack('>10I', cue_offset, 0xffffffff, name_offset, 0xffffffff, 0xffffffff, 0xffffffff, 138,
                              hash_offset, index_offset, sound_offset))
    header.extend(name.encode().ljust(64, b'\0')); assert len(header) == 138
    return bytes(header + name.encode().ljust(64, b'\0') + sound + cue + bytes(32) + indexes + strings)


def build(out_dir=OUT):
    out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    raw = [clip(sid) for _, sid in CUES]
    gain = PEAK / max(float(np.abs(m).max()) for m in raw)
    clips = [pcm16(m, gain) for m in raw]
    names = [c for c, _ in CUES]
    files = []
    for bank in (BANK, BANK_JP):
        (out_dir / f'{bank}.xwb').write_bytes(wavebank(bank, clips))
        (out_dir / f'{bank}.xsb').write_bytes(soundbank(bank, names))
        files += [f'{bank}.xsb', f'{bank}.xwb']
    total = sum(len(d) for d, _ in clips)
    print(f'Cerberus sound bank: {len(clips)} cues, gain {20 * np.log10(gain):+.1f} dB, {total / 1e6:.2f} MB of audio per bank ->', out_dir)
    return files


if __name__ == '__main__':
    build()
