"""Give the whip's hit object spin hitboxes, so the held spin deals damage.

The whip hit object (weapon sprite wp/p_wpf0..f2) is created once per attack
by the shared game code and plays weapon animation 0 (standing). It stays
alive while its animation runs and the player's attack phase is active
(nathan_spin.py keeps the phase active while the spin is held). This appends enough turns of the
spin hitboxes (measured from body slot 28's whip pixels, see nathan_spin_hitboxes.py)
to animation 0 of the three weapon sprites. Timing comes from the body sprite.

Run after nathan_whip_hitboxes.py and nathan_spin_hitboxes.py; rerunning
nathan_whip_hitboxes.py undoes it.

usage: nathan_spin_weapon.py <package folder> [<package folder> ...]
"""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(next(p for p in _pl.Path(__file__).resolve().parents if (p / 'hodmods.json').is_file()) / 'core' / 'tools')); import hodpaths  # noqa: E402  hod-mods tool bootstrap
import sys
import math
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from hodsprite import read_opd, write_opd, clone
from nathan_whip_hitboxes import BODY, WEAPONS
from nathan_spin_hitboxes import measure

RESTS = {28: 0, 29: 2}  # spin slot -> resting-pose slot

SPINS = ((0, 16, 28), (1, 17, 29))  # weapon animation, swing slot, spin slot
MIN_SPIN_TICKS = 960     # preserve the existing hit object's 16-second lifetime

def main(packages):
    for pkg in map(Path, packages):
        body_path = pkg / BODY
        body = read_opd(body_path)
        for wid in WEAPONS:
            path = pkg / f'data/opd/weapon/wp/p_wp{wid}.opd'
            sp = read_opd(path)
            for weapon_anim, swing_slot, spin_slot in SPINS:
                if spin_slot >= len(body.anims): continue
                delays = [st[1] for st in body.anims[spin_slot].steps]
                revolutions = max(60, math.ceil(MIN_SPIN_TICKS / sum(delays)))
                boxes = measure(body, spin_slot, RESTS[spin_slot], body_path.parent)
                assert any(boxes), 'no whip pixels found in the spin frames'
                anim = sp.anims[weapon_anim]
                assert len(anim.steps) == len(body.anims[swing_slot].steps), 'run nathan_whip_hitboxes.py first'
                assert [s[1] for s in anim.steps] == [s[1] for s in body.anims[swing_slot].steps], 'swing timing differs from body'
                first = len(sp.frames)
                for b in boxes:
                    f = clone(sp.frames[0]); f.parts = []; f.hitboxes = list(b)
                    sp.frames.append(f)
                tail = anim.steps[-1]
                for _ in range(revolutions):
                    for i in range(len(boxes)):
                        st = clone(tail); st[0] = first + i; st[1] = delays[i]
                        anim.steps.append(st)
            write_opd(path, sp)
        print(f'{pkg.name[:12]}…: standing/crouching weapon animations preserve body spin timings and hitboxes')

if __name__ == '__main__':
    main(sys.argv[1:])
