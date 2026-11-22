# Testing Nathan Graves

Thank you for testing. Each check below is something that has not been
confirmed in play yet. You don't have to do all of them: say which ones you
did, and report what you saw, good or bad. A "works" is as useful as a bug.

## How to report

For each problem, one report with:

- **What happened**, and what you expected instead
- **Where**: chapter, Normal or Hard, solo or co-op (how many players)
- **Cards**: the Action + Attribute pair in use (for example "Mars + Golem")
  and roughly how many copies of each you own
- **Facing / pose**: left or right, standing, crouching or in the air
- **Can you make it happen again?** If so, how
- A **screenshot or short clip** if it is something you can see
- **For a crash or freeze**: the newest file in the game folder's `logs/`
  folder (`harmonyrecomp_<number>.log`) and, if it was during setup, the
  setup's full terminal output

## A. Setup

- [ ] `setup_nathan.py` finished without stopping (if it stopped: the message,
      and whether rerunning after fixing it worked)
- [ ] How long the first run took
- [ ] Your existing saves still load, with all characters' progress intact
- [ ] Nathan is on Character Select, with his portrait and name

## B. Basics (one short session)

- [ ] Starts with one Mercury and one Salamander card
- [ ] Whip attacks hit what they visibly touch; holding X spins the whip
- [ ] Feet on the ground (not floating, not sunk in), in every pose
- [ ] Tackle (down, down-forward, forward + X): both directions, goes
      through enemies, hits each once, costs 15 MP
- [ ] Card Swap (hold Y): cycles only owned cards, drawn above the scenery
- [ ] Martial Arts page in the menu shows Tackle with its input
- [ ] Sounds: whip, jump, landing, damage, death, DSS

## C. Getting cards

- [ ] A killed enemy drops its card and picking it up adds the card
      (the Monster Compendium lists each enemy's card once you've seen it)
- [ ] Hard mode boss chests give their card: Saturn (chapters 2 and 9),
      Unicorn (3 and 7), Uranus (4 and 8), Black Dog (5 and 11), Pluto (6 and 10)
- [ ] The pickup shows the card's icon and name; the menu count goes up
- [ ] Drop rates feel right (too rare? too common?)

## D. The 100 card pairs

For each pair you try: turns on with RB, costs the MP shown, looks and sounds
right, hits where it is drawn, does what its description says, and ends
cleanly when turned off, on death and on a room change. Try it facing left,
crouching and in the air too.

| Action | Pairs | Notes |
|---|---|---|
| Mercury | elemental whips | |
| Venus | stat boosts | Pluto + Griffin should double walking speed, Jupiter + Cockatrice halve it |
| Jupiter | shields | Jupiter + Mandragora heals (green numbers) |
| Mars | weapons | |
| Diana | whip projectiles | Salamander stops at the first enemy; Serpent, Golem, Griffin, Unicorn and Black Dog pass through |
| Apollo | thrown spells | |
| Neptune | 50% resistance to one damage type | |
| Saturn | familiars | first-pass behaviour; describe what looks wrong |
| Uranus | summons | Uranus + Unicorn heals other players in range (needs co-op, **with Nathan installed on every machine**) |
| Pluto | specials, Item Crash | |

Also: more copies of a card should make its pairs stronger, and the whip
upgrades at 20 and 180 total copies.

## E. Longer play

- [ ] Every chapter, Normal and Hard; Survival mode
- [ ] Death, revive, room changes and leaving a stage leave nothing stuck on
      screen or switched on
- [ ] Rapid card swapping in the middle of an attack
- [ ] A long session (an hour or more): no slowdown
- [ ] Records and ranking screens show Nathan correctly
- [ ] Co-op (only with players on the same archive): Dual Crush and other
      co-op moves with Nathan as either partner

## F. Online, two or more players (everyone on this archive)

The other players should see what Nathan does. For each check, say what
they saw.

- [ ] Turning a pair on and off with RB: the gold pulse and the pair's effect
      (Mars weapon, Jupiter shield, Saturn familiar, Skeleton...) show up for
      the others and go away again
- [ ] Apollo casts, Item Crash, Uranus summons and Diana shots are seen by the
      others, with damage numbers on the enemies they hit
- [ ] Enemies take the damage once, not twice
- [ ] Uranus + Unicorn heals the other players standing near Nathan
- [ ] Card Swap to another pair mid-stage: the others see the new pair
- [ ] Nobody else's save changes: their MP isn't spent and they get no
      Nathan cards
- [ ] When something doesn't show: send the **other** player's newest
      `logs/harmonyrecomp_*.log`. It lists every Nathan event that player
      received, as `[nathan] online player N DSS on ...`
