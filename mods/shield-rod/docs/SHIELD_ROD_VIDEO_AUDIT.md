# Shield Rod activation reference audit - November 16, 2026

User reference: https://www.youtube.com/watch?v=hIMDNWBR9wQ
AcidGlow, Every Shield Rod Ability Combination, published June 6, 2024.
Inspected paused frames through the browser; no remote video was downloaded.
Times below are video times, not source animation tick numbers.

| Shield | Reference stage sampled | Source replay comparison |
| --- | --- | --- |
| Leather | 0:09.55 cow above caster | Cow, reveal flash and stretching exit are captured. |
| Knight | 0:46.35 held shield; 0:48.35 rainbow horse | Source horse and palette cycling are present. An earlier stale seek screenshot showed Iron instead; no remapping is needed. |
| Iron | 0:25.48 rotating/stretching armored knight | Captured as triangular textured quads, followed by two sword children. Offline preview needed affine triangle rendering; native draw already writes these vertices. |
| Axe Knight / Axe Lord | 1:08.57 blue knight above caster | Parent flash captured; the moving knight is an existing separate runtime actor. Offline atlas does not model that runtime actor and is not proof of its live movement/offset. |
| Herald | about 1:24.2 apparition and blue stars | Main apparition and feather children captured. All 46 secondary feather tracks recaptured in this audit. |
| Dark | about 1:42 skull apparition | Skull and rising secondary effects captured. Video background darkening is outside this isolated geometry preview. |
| Goddess | about 1:56.5 white reveal | Reveal, upright figure, blue child effects and exit captured. |
| Shaman | about 2:15.5 woman with green stars | Figure, palette changes and eight star children per facing captured. |
| Medusa | about 2:35.5 head; 2:36.5 two gold beams | Head and two beam children captured. Actual HoD enemy selection is runtime logic and cannot be verified from an offline capture/video comparison. |
| Skull | about 2:54-2:58 skull group and exit beam | Skull group, beam and exit captured; compare full sequence rather than a single late frame. |
| Fire | about 3:12 orb; 3:14 fire streams | Orb and three staggered fire children per facing captured. |
| Alucart | about 3:29-3:31 circle and failed cast | Source replays circle and small question-mark effect. Question mark was not clearly resolved in the sampled video frames. |
| Alucard | about 3:45 orbit | Previously fixed eleven-shield orbit, contraction and exit retained. |

This establishes the presence and order of the main captured activation stages.
It is not a pixel-perfect match or live HoD gameplay test. The offline preview
uses simplified blending, excludes the caster's own pose,
scene darkening and some runtime actors, and uses a fixed camera/target scene.
Do not infer damage, healing, homing success or exact native blending from it.

Capture comparison: 26 parent + 146 child files; 158 runtime child clips.
Zero-init recapture changes no additional rendered primitive geometry or colors
relative to the already installed Alucard fix. Source durations/events unchanged.
Raw unused RGB differences do not represent visible fixes. The generated game
assets are byte-identical to the previous installed assets.
