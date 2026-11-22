"""Render the familiars' sounds from the user's own SotN disc to an XACT bank.

SotN plays each familiar's own sounds (voices) from that familiar's VAB,
loaded as sound bank 2 while it is out (SERVANT/SD_FAIRY, SD_DEVIL, SD_SWORD
.VH/.VB); its other sounds come from the shared bank 0 in DRA.BIN. Which
sound each familiar plays, and when, is from sotn-decomp src/servant (ghost:
the attack ring's SFX_GLASS_SHARDS; sword.c: a sweep or wing flap as an
attack starts, "Slash!"/"Slice!" now and then; demon.c: the spear's name as
it casts; faerie.c: her lines). SotN's Bat makes no sound when it attacks;
its screech (heard around bat form) is used for its dives. The DRA.BIN
sound-table rows give the bank, program, note, volume and tone, as for every
SotN sound. Rendering (the disc's own pitch conversion and the PSX SPU renderer),
the sample rate and the XACT bank format are build_shield_audio.py's; only
the bank name (SE_FAMILIAR) and the cue prefix (SE_FM_) differ.

No downloaded audio: everything comes from the disc recorded for Shield Rod.
  python modding/tools/build_familiar_audio.py           build the bank
  python modding/tools/build_familiar_audio.py install   build and copy it into the game assets
"""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import hashlib, json, shutil, struct, subprocess, sys, wave
from pathlib import Path
from array import array
import build_shield_audio as sa
from shield_rod import ROOT, open_disc

OUT = hodpaths.legacy('modding/build/familiar_audio')
STAGE = OUT/'data/sound'
BANK, PREFIX = 'SE_FAMILIAR', 'SE_FM_'
RATE = sa.RATE
# Header constant -> (sound ID, bank): 'common' = DRA.BIN's bank 0, else the servant
# VAB loaded as bank 2. Names from sotn-decomp include/sfx.h.
SOUNDS = {
    'kFaerieCueHealing': (0x885, 'SD_FAIRY'), 'kFaerieCuePotion': (0x886, 'SD_FAIRY'),
    'kFaerieCueRegeneration': (0x887, 'SD_FAIRY'), 'kFaerieCueOhNo': (0x891, 'SD_FAIRY'),
    'kDemonCueFireSpear': (0x8A3, 'SD_DEVIL'), 'kDemonCueIceSpear': (0x8A4, 'SD_DEVIL'),
    'kDemonCueThunderSpear': (0x8A5, 'SD_DEVIL'),
    'kSwordCueSlash': (0x8B2, 'SD_SWORD'), 'kSwordCueSlice': (0x8B3, 'SD_SWORD'),
    'kSwordCueSweep': (0x672, 'common'), 'kSwordCueWingFlap': (0x6C6, 'common'),
    'kGhostCueGlassShards': (0x6B0, 'common'), 'kBatCueScreech': (0x64E, 'common'),
    # Sword Brothers (sword.c func_us_801758C8): swoosh, "Gather, brother soul blades!", the wheel's chime.
    'kSwordCueSwoosh': (0x63F, 'common'), 'kSwordCueBrothers': (0x8B6, 'SD_SWORD'),
    'kSwordCueMagicSwitch': (0x69D, 'common'),
    # Ghost soul steal: the orb reaching Alucard (SotN's HP-restore sound, SFX_HEALTH_PICKUP).
    'kGhostCueHeal': (0x68E, 'common'),
}
HEADER = ROOT/'.setup/package/src/src/alucard_familiar_audio.h'
# XACT category and volume byte per kind. Voices use category 30 like
# Alucard's own voice bank (VX_ALUCARD), so the voice volume slider controls
# them; effects use the player effects category 9. Volumes follow the game's
# own banks (voices about 90-101, effects about 56-71). All carry the native
# distance curves (build_shield_audio.RPC_BLOCK).
VOICE, EFFECT = (30, 90), (9, 68)
KIND = {'kGhostCueGlassShards': (9, 56)}   # the ring sound, quieter (user, November 18)
TARGETS = (ROOT/'assets/data/sound', ROOT/'.setup/package/src/assets/data/sound')


def vab(vh, vb):
    """Samples and programs of a VAB (the same layout build_shield_audio.bank_data reads)."""
    assert vh[:4] == b'pBAV'
    count = struct.unpack_from('<H', vh, 18)[0]; n = struct.unpack_from('<H', vh, 22)[0]
    at = 0x820 + count * 512; offset = struct.unpack_from('<H', vh, at)[0] * 8; samples = {}
    for i in range(1, n + 1):
        size = struct.unpack_from('<H', vh, at + i * 2)[0] * 8
        assert offset + size <= len(vb) and size % 16 == 0
        samples[i] = (offset, size); offset += size
    programs = {}; packed = 0
    for p in range(128):
        start = 32 + p * 16; tones = vh[start]
        if not tones: continue
        assert tones <= 16
        programs[p] = {'volume': vh[start + 1], 'pan': vh[start + 4], 'tones': []}
        for t in range(tones):
            pos = 0x820 + packed * 512 + t * 32
            programs[p]['tones'].append(dict(volume=vh[pos + 2], pan=vh[pos + 3], center=vh[pos + 4], fine=vh[pos + 5],
                adsr1=struct.unpack_from('<H', vh, pos + 16)[0], adsr2=struct.unpack_from('<H', vh, pos + 18)[0],
                sample=struct.unpack_from('<H', vh, pos + 22)[0]))
        packed += 1
    return samples, programs


def render(dra, sid, samples, programs, pitch_from_disc, vab_slot, ram):
    """build_shield_audio.render for a sound of one bank (vab_slot 0 shared, 2 servant)."""
    row, events = sa.sound_events(dra, sid)
    commands = [(0, 0x180, 0x1fff), (0, 0x182, 0x1fff), (0, 0x1aa, 0xc000)]
    voices = []; pair_ends = [0, 0]; tail = 0
    for e in events:
        assert e['vab'] == vab_slot, ('sound not in this bank', sid, e)
        p = programs[e['prog']]; start = round(e['tick'] * RATE / 60)
        pair = next((i for i, t in enumerate(pair_ends) if t <= start), min(range(2), key=lambda i: pair_ends[i]))
        pair_end = start
        for j, t in enumerate(p['tones'][e['tone']:e['tone'] + 2]):
            if not t['sample'] or not t['volume']: continue
            offset, size = samples[t['sample']]; voice = pair * 2 + j; at = voice * 16
            pitch = pitch_from_disc(t, e['note'])
            volume = (((e['volume'] * p['volume']) >> 7) * t['volume']) >> 7
            pan = max(0, min(127, t['pan'] + p['pan'] - 64))
            left = (volume * min(64, 127 - pan) * 0x3fff) // (127 * 64); right = (volume * min(64, pan) * 0x3fff) // (127 * 64)
            for reg, value in [(0, left), (2, right), (4, pitch), (6, (0x1010 + offset) // 8), (8, t['adsr1']), (10, t['adsr2'])]:
                commands.append((start, at + reg, value))
            commands.append((start, 0x188, 1 << voice))
            duration = round((size // 16) * 28 * 4096 / pitch); pair_end = max(pair_end, start + duration)
            voices.append(dict(event=e, tone=t, voice=voice, pitch=pitch, sample_offset=offset, sample_bytes=size,
                               start_frame=start, estimated_frames=duration))
        pair_ends[pair] = pair_end; tail = max(tail, pair_end)
    commands.sort(key=lambda c: c[0])
    command_file = OUT/f'{sid:04x}.registers'; command_file.write_bytes(b''.join(struct.pack('<III', *c) for c in commands))
    raw = OUT/f'{sid:04x}.pcm'; end = min(RATE * 20, max(tail + RATE * 2, RATE * 3))
    subprocess.run([str(sa.OUT/'render_sotn_spu.exe'), str(ram), str(command_file), str(raw), str(end)],
                   check=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    # Trim after the last audible frame, keeping 20 ms (as build_shield_audio; no
    # numerical library, so the standalone installer runs this file unchanged).
    values = array('h'); values.frombytes(raw.read_bytes())
    if sys.byteorder != 'little': values.byteswap()
    total = len(values) // 2
    last = next((i for i in range(total - 1, -1, -1) if max(abs(values[2 * i]), abs(values[2 * i + 1])) > 2), None)
    assert last is not None, (sid, 'silent')
    assert last < total - RATE // 4, (sid, 'non-terminating loop/envelope')
    frames = min(total, last + 1 + RATE // 50)
    del values[2 * frames:]
    peak = max(abs(v) for v in values)
    path = OUT/f'sound_{sid:04x}.wav'
    little = array('h', values)
    if sys.byteorder != 'little': little.byteswap()
    with wave.open(str(path), 'wb') as w: w.setparams((2, 2, RATE, 0, 'NONE', 'not compressed')); w.writeframes(little.tobytes())
    if sys.byteorder == 'little': values.byteswap()
    return values.tobytes(), frames, dict(id=sid, cue=f'{PREFIX}{sid:04X}', sound_table_row=row, voices=voices,
        wav_sha256=sa.sha(path.read_bytes()), frames=frames, seconds=frames / RATE, peak=peak)


def soundbank(ids):
    """build_shield_audio.soundbank with this bank's name and cue prefix."""
    n = len(ids); sound_offset = 202; cue_offset = sound_offset + n * (12 + len(sa.RPC_BLOCK)); hash_offset = cue_offset + n * 15
    index_offset = hash_offset + 32; name_offset = index_offset + n * 6
    sound = bytearray(); cue = bytearray(); indexes = bytearray(); strings = bytearray()
    size = 12 + len(sa.RPC_BLOCK)
    for i, sid in enumerate(ids):
        name, (_, bank) = next((k, v) for k, v in SOUNDS.items() if v[0] == sid)
        category, volume = KIND.get(name, VOICE if bank != 'common' else EFFECT)
        sound.extend(struct.pack('>BHBhBHHB', 2, category, volume, 0, 255, size, i, 0) + sa.RPC_BLOCK)
        cue.extend(struct.pack('>BIIBHHB', 4, sound_offset + i * size, 0xffffffff, 1, 0, 0, 2 << 3))
        indexes.extend(struct.pack('>IH', name_offset + len(strings), i + 1 if i < n - 1 else 0xffff))
        strings.extend(f'{PREFIX}{sid:04X}'.encode() + b'\0')
    head = bytearray(b'KBDS' + struct.pack('>HHH', 46, 43, 0) + bytes(8) + b'\x03')
    head.extend(struct.pack('>HHHHBHHH', 0, n, 0, 16, 1, n, 0, len(strings)))
    head.extend(struct.pack('>10I', 0xffffffff, cue_offset, name_offset, 0xffffffff, 0xffffffff, 0xffffffff, 138,
                            hash_offset, index_offset, sound_offset))
    head.extend(BANK.encode().ljust(64, b'\0')); assert len(head) == 138
    return head + BANK.encode().ljust(64, b'\0') + sound + cue + bytes(32) + indexes + strings


def wavebank(clips):
    saved = sa.BANK; sa.BANK = BANK
    try: return sa.wavebank(clips)
    finally: sa.BANK = saved


def build():
    OUT.mkdir(parents=True, exist_ok=True); STAGE.mkdir(parents=True, exist_ok=True)
    assert (sa.OUT/'render_sotn_spu.exe').exists(), 'run build_shield_audio.py once first (it builds the SPU renderer)'
    disc_path, disc = open_disc()
    dra = disc.get('DRA.BIN'); pitch = sa.OriginalPitch(disc.get('SLUS_000.67'))
    banks, sources = {}, {}
    for bank in sorted({b for _, b in SOUNDS.values()}):
        if bank == 'common':
            vh, vb, samples, programs = sa.bank_data(dra)
        else:
            vh, vb = disc.get(f'SERVANT/{bank}.VH'), disc.get(f'SERVANT/{bank}.VB'); samples, programs = vab(vh, vb)
        ram = bytearray(512 * 1024); ram[0x1010:0x1010 + len(vb)] = vb
        (OUT/f'spu_{bank}.bin').write_bytes(ram)
        banks[bank] = (samples, programs, 0 if bank == 'common' else 2, OUT/f'spu_{bank}.bin')
        sources[bank] = {'vh_sha256': sa.sha(vh), 'vb_sha256': sa.sha(vb)}
    bank_of = {sid: bank for sid, bank in SOUNDS.values()}
    ids = sorted(bank_of); clips = []; report = []
    for sid in ids:
        samples, programs, slot, ram = banks[bank_of[sid]]
        data, frames, entry = render(dra, sid, samples, programs, pitch, slot, ram)
        assert entry['peak'] < 32767, 'clipped render'
        clips.append((data, frames)); report.append(entry); print(f'{sid:04X}: {frames / RATE:.2f} s, peak {entry["peak"]}')
    xwb = wavebank(clips); xsb = soundbank(ids)
    (STAGE/f'{BANK}.xwb').write_bytes(xwb); (STAGE/f'{BANK}.xsb').write_bytes(xsb)
    manifest = dict(disc_path=str(disc_path), disc_serial=disc.serial, dra_sha256=sa.sha(dra), banks=sources,
                    bank=BANK, sample_rate=RATE, effects=report,
                    files={f'{BANK}.xwb': sa.sha(xwb), f'{BANK}.xsb': sa.sha(xsb)})
    (OUT/'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    rows = [f'constexpr const char* {name} = "{PREFIX}{sid:04X}";' for name, (sid, _) in SOUNDS.items()]
    HEADER.write_text('// Generated from the user\'s own SotN disc by modding/tools/build_familiar_audio.py.\n#pragma once\n'
                      'namespace harmony::alucard_familiar {\n'
                      f'constexpr const char* kFamiliarBankXsb = "D:\\\\data\\\\sound\\\\{BANK}.xsb";\n'
                      f'constexpr const char* kFamiliarBankXwb = "D:\\\\data\\\\sound\\\\{BANK}.xwb";\n'
                      + '\n'.join(rows) + '\n}\n', encoding='utf-8', newline='\n')
    print('Built', STAGE, 'and', HEADER.name)
    return [STAGE/f'{BANK}.xsb', STAGE/f'{BANK}.xwb']


def install():
    files = build()
    for target in TARGETS:
        target.mkdir(parents=True, exist_ok=True)
        for f in files:
            tmp = target/(f.name + '.new'); shutil.copyfile(f, tmp); tmp.replace(target/f.name)
            assert (target/f.name).read_bytes() == f.read_bytes()
    print('Installed', BANK, 'into', ', '.join(str(t) for t in TARGETS))


if __name__ == '__main__':
    install() if sys.argv[1:] == ['install'] else build()
