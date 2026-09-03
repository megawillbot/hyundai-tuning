# puc-final-stage-patch — candidates, NOT FLASHED

Built **2026-09-03**. Two full 512 KiB images, same program zone, different
calibration. Design and rationale in [[program-zone-plan]] §4 and
[[puc-overrun-map]] (code-verified §4).

| file | what | full SHA256 | cal-zone SHA256 |
|---|---|---|---|
| `FULL_ca654019_ghostcam_pucstage_UNFLASHED.bin` | **rehearsal**: patched program + ghost-cam cal + new tables at their *inert* values. Behaviourally identical to the car today. | `a70ed546612c526b…` | `e4638e99bf2b30d6…` |
| `FULL_ca654019_ghostcam_poptune_UNFLASHED.bin` | **pop tune**: same program, cal-only changes on top of the rehearsal (armed latch, pattern, retard). | `c61220933f1c5ea7…` | `614b1896204eb2b4…` |

Both pass `--correct-checksum` (answer `n`) with current == new in both regions.

## Program zone — 89 bytes differ from stock, identical in both images

| where | bytes | what |
|---|---|---|
| `0x10010`–`0x10011` | 2 | program checksum |
| `0x11000`–`0x11025` | 38 | **stub B** — final-stage pattern: `JNB M_FD40.15 → index 0x0D` (unarmed), else axis-search rpm/32 on `0x8757` and stepped lookup of `ID_PAT_INH_IV_PUC_3` at cal `0xBC8B` → `[0xC1AB]` |
| `0x11040`–`0x11057` | 24 | **stub A** — task-entry hook: the two displaced pushes; `BCLR M_FD40.15` while cranking (`M_FD16.2`); `BSET M_FD40.15` when rpm/32 ≥ `C_N_ARM_POP` (cal `0xBC91`) |
| `0x144BA`–`0x144BD` | 4 | entry of the injector-inhibit task (`0x144BA`, single caller, no other entry) → `CALLS 0x09,0x1040` |
| `0x14574`–`0x14593` | 21 | overrun state-4 handler: keeps `BSET M_FD16.12`, sets state 4, `CALLS 0x09,0x1000`, applies via `CALLS 0x09,0x4436`, jumps to the common exit. Both stock entry points (`0x14574` from the jump table, `0x14580` from the `>4` reset) preserved |

The latch bit `M_FD40.15` (word `0xFD40`, bit address `0x20`) has no
whole-word, bitfield or bit access anywhere in the stock program; bits 0, 6, 7
of that word are the table library's clamp flags. It is cleared on every
crank, so "disabled at key-off" holds without relying on RAM initialisation.
The hooked task is skipped only in engine-state 0 (stopped), so it does run
while cranking.

## Calibration

Rehearsal image, vs the ghost-cam cal on the car (8 bytes):

| addr | value | meaning |
|---|---|---|
| `0xBC8B`–`0xBC90` | `0D ×6` | `ID_PAT_INH_IV_PUC_3__N_32` — all six cut at every rpm = stock behaviour |
| `0xBC91` | `FF` | `C_N_ARM_POP` (rpm/32) — 8160 rpm, never arms |
| `0xDEE0`–`0xDEE1` | | cal checksum |

Pop-tune image, vs the rehearsal (6 bytes):

| addr | from → to | meaning |
|---|---|---|
| `0x875C` | 78 → **94** | top breakpoint of the `0x8757` rpm/32 axis: 2496 → **3008 rpm**. Safe: all four tables on the axis are flat with rpm |
| `0xA19B` | 61 → **40** | `IP_IGA_PUC_AT__N` 3500-rpm cell: −25.1° → **−33.0°** relative (stock already commands −33.8° in the ACCIN variant) |
| `0xBC90` | 13 → **6** | pattern above 3008 rpm: `101100`, three injectors cut, uneven spacing |
| `0xBC91` | 255 → **125** | arm when rpm/32 ≥ 125 = **4000 rpm** |
| `0xDEE0`–`0xDEE1` | | cal checksum |

Behaviour with the tune: after any excursion past 4000 rpm since the last
crank, a closed-throttle overrun above 3008 rpm cuts three injectors and fires
the other three 33° late; below 3008 it is the stock full cut, silent, resuming
at 1248 rpm. Never armed → exactly stock. Three bytes to taste: `0xBC91` (arm
rpm ÷ 32), `0x875C` (active rpm ÷ 32), `0xBC90` (pattern index, see the table
in [[puc-overrun-map]]).

## Flash order, if/when

1. Capture run first ([[next-capture-script]]) — validates the cut model.
2. `--flash-calibration` the **rehearsal** image; read back; cal zone must hash
   `e4638e99bf2b30d6…`.
3. `--flash-program` the rehearsal image; read back; program bytes must match.
   Drive: no change expected.
4. `--flash-calibration` the **pop-tune** image (cal-only step); read back
   `614b1896204eb2b4…`. Rev past 4000 once, lift above 3000.
5. Never program-before-cal: a patched program with `0xBC8B` still `FF` would
   index the pattern table with `0xFF` once armed. (Unarmed it is harmless, and
   `0xBC91 = FF` cannot arm — but keep the order anyway.)
