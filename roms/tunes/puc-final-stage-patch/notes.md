# puc-final-stage-patch — candidates, NOT FLASHED

Built **2026-09-03**, latch design revised same day (see "Correctness" below). Two
full 512 KiB images, same program zone, different calibration. Rationale in
[[program-zone-plan]] §4 and [[puc-overrun-map]] (code-verified §4).

| file | what | full SHA256 | cal-zone SHA256 |
|---|---|---|---|
| `FULL_ca654019_ghostcam_pucstage_UNFLASHED.bin` | **rehearsal**: patched program + ghost-cam cal + new tables at *inert* values. Behaviourally identical to the car today. | `61f4da6c5f7a2ef9…` | `1015a95c35fb1690…` |
| `FULL_ca654019_ghostcam_poptune_UNFLASHED.bin` | **pop tune**: same program, cal-only changes on top of the rehearsal. | `7e2dbe0f9d4b173e…` | `d24a75a1d1fe9459…` |

Both pass `--correct-checksum` (answer `n`) with current == new in both regions.
The pop tune's **program zone is byte-identical to the rehearsal's** — it is a
pure `--flash-calibration` step on top.

## How it works

The stock overrun cut ends in a hard-coded "all six injectors" stage
([[puc-overrun-map]] §1-2). The patch makes that final stage read a new
rpm-indexed table, but only after the engine has been revved past an arm point —
a **latch** — so ordinary driving never pops.

- **Stub B** (`0x11000`, 38 B): final-stage index = `M_FD40.15 ? PUC_3[rpm/32] :
  0x0D`. Latched → the new table `ID_PAT_INH_IV_PUC_3__N_32` at cal `0xBC8B` on
  the `0x8757` rpm/32 axis; unlatched → stock all-six.
- **Stub A** (`0x11040`, 26 B): self-contained arm/disarm on rpm/32 (`[0xC59E]`),
  then tail-calls the real task:
  ```
  MOVB RL4,[0xC59E]         ; rpm/32
  CMPB RL4,[0x3C92]         ; C_N_DISARM_POP (cal 0xBC92)
  JMPR cc_NC, +             ; rpm >= disarm -> keep latch
  BCLR M_FD40.15            ; rpm <  disarm -> DISARM
  CMPB RL4,[0x3C91]         ; C_N_ARM_POP    (cal 0xBC91)
  JMPR cc_C, +              ; rpm <  arm     -> leave as-is
  BSET M_FD40.15            ; rpm >= arm     -> ARM
  CALLS 0x09,0x44BA         ; run the real, unmodified inhibit task
  RETS
  ```
- **Latch** `M_FD40.15`: a bit no stock instruction reads or writes (its word has
  no whole-word/bitfield access). Set once rpm/32 ≥ arm; cleared once rpm/32 <
  disarm. Because rpm passes through the disarm band on every return to idle *and*
  on shutdown, the latch also clears at key-off — no dependency on how RAM is
  initialised.

## Correctness — the caller-redirect design, and the bug it replaced

Stub A is reached by **redirecting the inhibit task's single caller** (`0x3AC00`,
the only `CALLS 0x09,0x44BA` in the image) to `CALLS 0x09,0x1040`. Stub A does its
work, then `CALLS` the real task at `0x44BA` (prologue **left stock**) and `RETS`.
Stack stays balanced.

> The first draft hooked the task's *prologue* instead (replaced the two
> register pushes at `0x144BA` with a `CALLS`, and had the stub redo the pushes).
> That was a **stack bug**: the pushes landed on top of the `CALLS` return
> address, so the stub's `RETS` returned into a pushed register value → watchdog
> reset. Caught in review before any flash; do not reintroduce. The task's
> prologue is now untouched.

The latch condition was also moved off the cranking flag (`M_FD16.2`) onto the
rpm-dip disarm above — simpler, self-contained, and covers key-off for free.

## Program zone — 89 bytes differ from stock, identical in both images

| where | bytes | what |
|---|---|---|
| `0x10010`–`0x10011` | 2 | program checksum |
| `0x11000`–`0x11025` | 38 | stub B |
| `0x11040`–`0x11059` | 26 | stub A |
| `0x3AC00`–`0x3AC03` | 4 (2 differ) | caller redirect `CALLS 0x09,0x44BA → 0x1040` |
| `0x14574`–`0x14593` | 21 | overrun state-4 handler → `CALLS stub B`, both stock entry points preserved |

The `0x144BA` prologue is stock. The ID/coherence block at `0x1004E` is untouched
(pairs the program with our boot `KR77035202` — see [[program-zone-plan]] §2c).

## Calibration

Rehearsal, vs the ghost-cam cal on the car (9 bytes):

| addr | value | meaning |
|---|---|---|
| `0xBC8B`–`0xBC90` | `0D ×6` | `ID_PAT_INH_IV_PUC_3__N_32` — all six cut at every rpm = stock |
| `0xBC91` | `FF` | `C_N_ARM_POP` (rpm/32) = 8160 rpm, never arms |
| `0xBC92` | `20` | `C_N_DISARM_POP` (rpm/32) = **1024 rpm** disarm point |
| `0xDEE0`–`0xDEE1` | | cal checksum |

Pop tune, vs the rehearsal (6 bytes):

| addr | from → to | meaning |
|---|---|---|
| `0x875C` | 78 → **94** | top breakpoint of the `0x8757` rpm/32 axis: 2496 → **3008 rpm** (safe: all four tables on the axis are flat with rpm) |
| `0xA19B` | 61 → **40** | `IP_IGA_PUC_AT__N` 3500-rpm cell: −25.1° → **−33.0°** relative |
| `0xBC90` | 13 → **6** | pattern above 3008 rpm: `101100`, three injectors cut, uneven |
| `0xBC91` | 255 → **125** | arm at **4000 rpm** |
| `0xDEE0`–`0xDEE1` | | cal checksum |

Behaviour with the tune: once revved past 4000 rpm, a closed-throttle overrun
above 3008 rpm cuts three injectors and fires the other three 33° late; the latch
clears when rpm next falls below ~1024 (each return to idle, and key-off). Below
3008, or before the first 4000-rpm hit, it is the stock full cut — silent, resume
at 1248. Four cal bytes to taste: `0xBC91` arm, `0xBC92` disarm, `0x875C` window,
`0xBC90` pattern (`0xA19B` for retard depth).

## Flash order, if/when

1. Capture run first ([[next-capture-script]]) — validates the cut model.
2. (Optional) prove 120000 baud on a read, then **Test 0**: flash byte-identical
   stock program ([[program-zone-plan]] §2b) to prove the K-line program path.
3. `--flash-calibration` the **rehearsal**; read back (cal `1015a95c35fb1690…`).
4. `--flash-program` the rehearsal; read back (program bytes match). Drive: no
   change expected.
5. `--flash-calibration` the **pop tune** (cal-only); read back (`d24a75a1…`). Rev
   past 4000 once, then lift from above 3000.
6. Never program-before-cal.

## Review addendum (2026-09-03, Fable 5.1) — the apply gate/max

Verified the mask applier (`0x14436`, called `0x4436`) that consumes our
`[0xC1AB]` level. It **gates on `M_FD12.7`** (clear ⇒ forces index `0x0D` = all
six, ignoring us) and outputs `pattern_table[max([0xC19A],[0xC5A0],[0xC57D],
[0xC1AB],[0xC1AD])]`. Implications:

- **Safe in every case** — output is always between our pattern and all-six, only
  during a closed-throttle overrun. Worst case the patch is inert.
- **Pops only if `M_FD12.7` is set and the other four sources are ≤6 at the final
  stage** — a runtime fact, unproven statically.
- **Capture-run gate:** flash the pattern patch only after the capture shows the
  stock cut staging 1 → 4 → 6 (proves the mechanism is live). If the stock cut is
  all-six from frame one, the patch is inert; contingency is to write `[0xF9BA]`
  directly from the state-4 handler. See [[puc-overrun-map]] and [[next-capture-script]].
- Nominal cut with our index 6 goes 1 → 4 → **3** cylinders (last stage drops 4→3;
  momentary, harmless).

Also re-verified this pass: the state dispatch (jump table entry `state 4 →
0x14574`, plus the state-3-expiry fall-through and the `>4` reset at `0x14580`) is
preserved by the patch; `M_FD16.12` is still set only on the `0x14574` entry, not
the `0x14580` entry, matching stock; both stubs' register use (RL4/R12/R13) is
scratch here and clobbers nothing the caller or the real task relies on.
