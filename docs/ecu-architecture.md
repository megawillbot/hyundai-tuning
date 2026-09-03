# SIMK43 ca654019 — program-zone architecture

Established **2026-09-03** by disassembling the program zone. Everything here is
derived from the firmware itself, not from another calibration's definitions.

Prior work ([[full-map-ca654019]]) mapped the *data* segment by aligning against
`ca652048`. This document is the *code* side, and it is a different kind of
evidence: where the symbol map says "this address is probably `IP_TI_FL__N`
because a same-family calibration has those bytes in that order", the code says
"this address is read by a 2-D interpolation call whose axes are these two
tables". The two agree far more often than not, and where they disagree the code
wins.

---

## 1. The program read was never broken

`roms/stock/PROGRAM_ca654019_read_2026-08-29.bin` was recorded in
[[car-notes]] and [[open-threads]] as a failed read — "49% `0xFF`, unusable for
disassembly", and the single blocker gating most of the project.

**It is a complete, valid read.** The 49% `0xFF` is simply erased flash past the
end of the program image.

| check | result |
|---|---|
| Code region | file `0x10000`–`0x4A6A6` (239 270 bytes), **2.79% FF** |
| Tail `0x4A6A6`–`0x80000` | **100% FF** — erased flash, not a read defect |
| vs `ca654019_G5E7TM0A` (EU manual) | **0 bytes differ** |
| vs `ca654019_E5N7SB1B` (EF Sonata) | **0 bytes differ** |
| vs `ca654019_S5E7TM0B` (SM Santa Fe) | **0 bytes differ** |
| vs `ca654020` / `ca654021` | 94% differ (different program) |
| SHA256 of code region | `d024e1d1d6177fc75abe07de77be1024677b07aa98a619888e18dacc60bb1541` |

Three independently sourced OpenGK dumps match ours byte-for-byte across all
239 270 bytes. Our read predates the mirror (2026-08-29 vs 2026-08-30), so this
is genuine external corroboration, not a copy.

The ID string at file `0x1004E` reads `654F1010654019KR77035111`, matching the
program code `KR77035111` that `--id` reports.

> **The IOCLID privilege-escalation patch is not needed to read the program
> zone.** What plain `--read` actually loses is the *calibration* region (which
> comes back all-FF), which is why the file looked broken. Read the two regions
> separately — `--read` for program, `--read-calibration` for maps — and both
> are obtainable over K-line with no patch.

Interesting side-note: the EU **automatic** `G4E7TS0A` differs from ours by 44%
of the code region, while the EU **manual** is identical. The program image does
not track the transmission.

## 2. Address model

The C167 is segmented; 16-bit data addresses are paged through DPP0–DPP3. The
model below is not inferred — the firmware states it literally at file `0x439AC`:

```
439AC  e6 00 22 00   MOV DPP0, #0x0022      ; page 0x22 -> physical 0x88000
439B0  e6 02 23 00   MOV DPP2, #0x0023      ; page 0x23 -> physical 0x8C000
```

| region | file offset | physical | notes |
|---|---|---|---|
| (unused / NVM) | `0x00000`–`0x08000` | `0x80000`–`0x88000` | see §6 |
| calibration | `0x08000`–`0x0DF40` | `0x88000`–`0x8DF40` | pages `0x22`,`0x23` |
| program | `0x10000`–`0x4A6A6` | `0x90000`–`0xCA6A6` | segments 9–C |

So a 16-bit data operand maps to a calibration file offset as:

| operand | DPP | maps to | bias |
|---|---|---|---|
| `0x0000`–`0x3FFF` | DPP0 = `0x22` | cal `0x8000`–`0xBFFF` | **+0x8000** |
| `0x4000`–`0x7FFF` | DPP1 | *not calibration* | — |
| `0x8000`–`0xBFFF` | DPP2 = `0x23` | cal `0xC000`–`0xFFFF` | **+0x4000** |
| `0xC000`–`0xFFFF` | DPP3 = 3 | RAM `0xC000`–`0xDFFF`, XRAM `0xE000`, ESFR `0xF000`, IRAM `0xF200`, SFR `0xFC00`+ | — |

Measured enrichment of operands against the independently derived symbol map,
which is what established the two windows before the `MOV DPP` pair was found:

| window | bias | distinct | hits | expected | enrichment |
|---|---|---|---|---|---|
| `0x0000`–`0x3FFF` | +0x8000 | 1307 | 766 | 73.7 | **10.4×** |
| `0x8000`–`0xBFFF` | +0x4000 | 110 | 60 | 2.7 | **21.9×** |
| `0x4000`–`0x7FFF` | either | — | — | — | none |

**Two windows, not one.** Missing the second one silently hides every table
above cal `0xC000` — which includes the main fuel map.

Ground truth: all ten constants whose addresses were known independently
([[full-map-ca654019]] §Constants) are referenced by code at exactly
`address − 0x8000`:

```
C_MAF_MAX  0x81B8 -> operand 0x01B8  (3 refs)   C_N_MAX      0x8222 -> 0x0222 (2)
C_N_FCUT   0x8219 -> operand 0x0219  (1 ref)    C_N_MAX_MAX  0x8230 -> 0x0230 (2)
C_VS_MAX_0 0x8370 -> operand 0x0370  (2 refs)   ... 10 / 10
```

## 3. The table-access library

Every calibration map is read through one of **fifteen routines** at file
`0x44780`–`0x44B5E` (physical `0xC4780`–`0xC4B5E`). Calling convention:

```
MOV   R12, #<axis_addr  - bias>
MOV   R13, <input value>            ; from RAM
CALLS 0x0C, <axis search>           ; -> index + fraction in fixed RAM slots
   ... repeat for the second axis of a 2-D table ...
MOV   R12, #<table_addr - bias>
CALLS 0x0C, <lookup>                ; -> result in RL4 (8-bit z) or R4 (16-bit z)
```

### The routines

| file addr | role | breakpoints | interpolates |
|---|---|---|---|
| `0x44780` | **Y**-axis search | 16-bit | yes |
| `0x447C8` | **Y**-axis search | 8-bit | yes |
| `0x44B10` | **Y**-axis search | 16-bit | no (index only) |
| `0x44AE4` | **Y**-axis search | 8-bit | no |
| `0x44864` | **X**-axis search | 16-bit | yes |
| `0x44812` | **X**-axis search | 8-bit | yes |
| `0x44A8A` | **X**-axis search | 8-bit | no |

| file addr | dims | z width | interpolates |
|---|---|---|---|
| `0x448B6` | 2-D | 8-bit | yes |
| `0x449D4` | 2-D | 16-bit | yes |
| `0x44B3C` | 2-D | 8-bit | no |
| `0x44ACA` | 2-D | 16-bit | no |
| `0x449A2` | 1-D | 8-bit | yes |
| `0x44970` | 1-D | 16-bit | yes |
| `0x44B54` | 1-D | 8-bit | no |
| `0x44ABE` | 1-D | 16-bit | no |

Axis-search results live in fixed RAM scratch, which is why a search can be
shared by several consecutive lookups:

| RAM | holds |
|---|---|
| `0xFBE4` | X (column) index |
| `0xFBE6` | X breakpoint count — **this is the row stride** |
| `0xFBE2` | X fraction, 16-bit |
| `0xFBE5` | Y (row) index |
| `0xFBE0` | Y fraction, 16-bit |
| `M_FD40` bit 7 / bit 6 | X / Y clamped-to-end flag |

### Axis table format

```
16-bit axis:  [count : u16][bp0 : u16][bp1 : u16] ...
 8-bit axis:  [count : u8 ][bp0 : u8 ][bp1 : u8 ] ...
```

**The XDF axis address is always the first breakpoint, i.e. the axis table
address + 2 (word axes) or + 1 (byte axes).** The count prefix is invisible in
every XDF. Confirmed against the hand-made def: code finds the ignition Y axis
table at cal `0x8E92`, the XDF declares its axis at `0x8E94`.

### Storage order and interpolation

From `0x448B6`:

```
MOVBZ R13, [0xFBE5]      ; row index
MOVBZ R5,  [0xFBE6]      ; column count
MULU  R13, R5            ; row * NCOLS
ADD   R12, MDL
ADD   R12, R2            ; + column index
MOVB  RL4, [R12]         ; z
```

**`z[row_index * NCOLS + col_index]` — row-major, NCOLS = the X-axis breakpoint
count.** Interpolation is ordinary bilinear on the *raw* stored values with
round-to-nearest (`MULU` by the 16-bit fraction, then `ADD MDL,MDL` to put the
half-bit in carry, then `ADDC`/`SUBC` on the high word). Out-of-range inputs
**clamp**; there is no extrapolation.

### `IP_` vs `ID_` is a real distinction, and the code proves it

`IP_*` symbols are passed to the interpolating lookups; `ID_*` symbols are
passed to the stepped ones. It is not a naming habit — they are different
routines. An `ID_` table is a staircase; editing one changes the output
discontinuously at the breakpoint.

## 4. Code-derived table geometry

`tools/c166/tables.py` walks every lookup call site and recovers, per table:
dimensionality, element width, interpolated vs stepped, both axis tables, each
axis's breakpoint list, and the RAM variable driving each axis.

**464 distinct tables** with geometry recovered from 557 call sites:

| | 8-bit z | 16-bit z |
|---|---|---|
| 1-D interpolated | 123 | 85 |
| 1-D stepped | 47 | 14 |
| 2-D interpolated | 123 | 55 |
| 2-D stepped | 14 | 3 |

Agreement with the derived symbol map, over the 310 tables in both:

| | count | meaning |
|---|---|---|
| exact match (rows, cols, width) | 100 | — |
| rows/cols transposed | 146 | **all 1-D tables**; `N×1` vs `1×N` is a presentation choice, no conflict |
| same area, different shape | 0 | — |
| **different element width** | **0** | — |
| genuinely different | 4 | 2 are scanner limitations (see below), 2 need review |

Zero width conflicts and zero area conflicts across 310 tables is a strong
independent check on [[full-map-ca654019]]. The alignment method got the
geometry right.

Against the hand-made `defs/ca654019 2700.xdf`, all four 2-D tables the scan
reaches match exactly **including both axis addresses**:

```
0xA272  Ignition Table        xdf 16x12@8b   code 16x12@8b  x:0x90EA y:0x8E94  OK
0xA336  Ignition Table Idle   xdf  4x4 @8b   code  4x4 @8b  x:0x910E y:0x9104  OK
0xA3AD  IP_ISAPWM_DHP_AT      xdf  7x5 @8b   code  7x5 @8b  x:0x8A86 y:0x8A7E  OK
0xA525  IP_ISAPWM_TPS         xdf  7x5 @8b   code  7x5 @8b  x:0x8A86 y:0x8A7E  OK
```

### Known limitation of the scanner

Axis state is tracked linearly, so where a lookup sits *after* a branch join and
the two arms searched different axes, the scanner records whichever came last.
This is exactly what happens at `IP_TI_FL__N` (§5) and accounts for 2 of the 4
disagreements. A backward-CFG version is the fix; until then, treat a 1-D
table's axis as advisory when the enclosing function contains more than one Y
search.

## 5. New findings from the code

### 5a. There is a second, undocumented fuel map

At file `0x2E5C2` the fuelling path forks on a RAM flag:

```
2E5C2  JB  M_FD14.12, 0x2E5EC
       ; --- flag clear: normal path ---
2E5C6  MOV R12,#0x0E92   ; Y axis cal 0x8E92 - 16 pt rpm, 420..6000
2E5D2  MOV R12,#0x10E8   ; X axis cal 0x90E8 - 12 pt MAF
2E5DE  MOV R12,#0x93A8   ; table cal 0xD3A8   <- main fuel pulse width
2E5E2  CALLS LOOKUP2D_16
       ; --- flag set: alternate path ---
2E5EC  MOV R12,#0x1334   ; Y axis cal 0x9334 - 8 pt rpm, 500,650,750,850,1000,1200,1500,1800
2E5F8  MOV R12,#0x1346   ; X axis cal 0x9346
2E604  MOV R12,#0x9528   ; table cal 0xD528   <- second fuel map
2E608  CALLS LOOKUP2D_16
```

`cal 0xD3A8` is the fuel pulse-width map [[car-notes]] already lists, now with
confirmed geometry: **16 rows (rpm) × 12 columns (MAF), 16-bit, interpolated —
the same axes as the ignition map at `0xA272`**.

`cal 0xD528` is a second complete fuel map on a low-rpm axis (500–1800 rpm). The
map itself is already in the hand-made def ("Idle Closed Loop Pulse Width") — the
new part is **the selector**: the fuelling path forks on RAM bit `M_FD14.12`
between it and the main map. The selector is unidentified — the obvious
candidates are cranking/start enrichment or a limp-home path. Worth identifying
before any fuelling work: if it is the start map, it is where cold-start richness
lives, and it is invisible to anyone
editing `0xD3A8` alone.

### 5b. WOT enrichment — the existing reading holds

`IP_TI_FL__N` @ `0xAD0B` is looked up 1-D interpolated 8-bit at `0x2E614`, after
the join above, and there is exactly **one** call site in the whole image. Its
axis is therefore whichever rpm axis the fuel path used — normally the 16-point
`0x8E92`. The README's claim that `AD0B` is a 1-D f(rpm) table on the main rpm
axis is **correct**, and the values [[full-map-ca654019]] §2 quotes (38 at 3200,
then 53/63/77 at 3700/4000/4500) land on the right breakpoints.

One scaling detail the code adds: the result is shifted left 4 (`SHL R4,#4`)
before being stored to `[0xF53A]`, and is forced to zero when the full-load flag
`M_FD0A.13` is clear.

### 5c. The `0x48000` RAM shadow, and where adaptation lives

The routine at file `0x43956` reconfigures a chip-select window and block-copies
the calibration out of flash into external RAM:

```
4395A  MOV SFR_FE1A, #0x0483    ; ADDRSEL2: base 0x048000, 32 KB window
4395E  MOV DPP0, #0x0022        ; source page = calibration (flash 0x88000)
43962  MOV DPP2, #0x0012        ; dest page   = 0x48000 (external RAM)
43966  MOV R12,#0 / R13,#0x8000 / R14,#0x5FF0      ; 0x5FF0 bytes ~ cal size 0x5F40
43970  <8x unrolled word copy, DPP increment on 16 KB boundary>
439AC  MOV DPP0, #0x0022 / DPP2, #0x0023           ; restore
439B4  MOV SFR_FE1A, #0x08E1    ; ADDRSEL2 back to base 0x08E000, 8 KB
```

`0x48000` is **external SRAM** (it sits below the flash's `0x80000`+ address
space, so it cannot be flash), and the whole calibration is shadowed into it.
The copy is guarded: at file `0x42B72` a loop over 12 header entries compares
flash (`[R9+0x10]`) against the shadow (`[R9+0x4068]`) and re-copies if they
differ — a standard "is the RAM shadow still valid" check.

**This is not a live base-map tuning lever.** The ignition map (`0xA272`) and
both fuel maps (`0xD3A8`, `0xD528`) — and in fact all 464 tables the geometry
scan found — are read from **flash**, through DPP0/DPP2 (operands
`0x0000`-`0x3FFF` / `0x8000`-`0xBFFF`). Writing the RAM shadow would not change
fuelling or timing. That closes the "could you tune in RAM without flashing"
question in the negative.

**What the shadow does hold is the adaptive system.** Exactly three lookups read
from the shadow window, and they do it *indirectly*:

```
2428C..242B6  loop index R9 = 0..5   (six cylinders)
  MOV R12, [R4 + #0x5F1A]     ; R4 = index*2 -- a POINTER read from the shadow
  CALLS LOOKUP2D_8_STEP        ; the pointer points at a per-cylinder adaptive map
  ... same for [R4+#0x5F26] and, later, [R7*2+#0x5F32]
```

`0x5F1A`/`0x5F26`/`0x5F32` are shadow offsets = calibration-equivalent
`0x9F1A`/`0x9F26`/`0x9F32`. They are **`ldp_` pointer tables** (the
link/pointer indirection [[open-threads]] flagged as what static analysis
handles worst), relocated to RAM so their entries can point at RAM-resident,
runtime-updated maps. The enclosing routine tracks min/max of rpm/32 (`[0xC4E8]`)
and load (`[0xC4E7]`), searches a knock/correction map, and sets knock flags
(`M_FD1E.10/.13/.14`) — a **per-cylinder knock/adaptation learning loop**.

This resolves the [[open-threads]] note that "adaptive ignition `ID_IGA_AD_0..5`
lives in the program zone and needs a clean read". It does not live in program
flash — it lives in this **RAM shadow, seeded from the flash calibration at boot
and adapted at runtime**. Consequences:

- The learned values are volatile: a battery disconnect (or the shadow failing
  its header check) reloads them from the flash seed. That *is* the "reset
  adaptations" mechanism.
- The flash seed for the adaptive maps is at cal `0x9F1A`-ish and is editable
  like any other calibration data — it sets where adaptation starts from.
- A logger cannot see the live adapted values over the calibration read; they
  are in RAM at `0x48000`+, reachable only by a RAM read (KWP ReadMemByAddress).

## 5d. The rev limiter, confirmed and clamped in stages

The limiter constants are read as **single bytes and compared against rpm/32**
(`CMPB RL4, [0x0222]` at file `0x1319E`), which confirms the `X*32` byte scaling
already in `docs/ca654019-constants-map.csv` — the code agrees with the shipped
CSV exactly:

| constant | byte | rpm | role |
|---|---|---|---|
| `C_N_FCUT` | 0x7D=125 | 4000 | launch/rolling fuel-cut point |
| `C_N_MAX_FCUT` | 0x57=87 | 2784 | second launch limit |
| `C_N_MAX` | 0xD5=213 | 6816 | **soft limit** |
| `C_N_MAX_MAX` | 0xD8=216 | 6912 | **hard limit** |
| `C_N_MAX_HYS` | 0x01=1 | 32 | hysteresis |

To change the rev limit, edit **one byte** = target rpm ÷ 32 (e.g. 7200 rpm →
225 = 0xE1 at `0x8222`). A 2-byte edit would be wrong.

The effective limit is not a single constant — file `0x1319E`-`0x13206` walks a
**clamp chain**: the working limit `[0xC19C]` is successively floored to
`C_N_MAX`, then a gear/vehicle-speed cap `[0x0231]`, then a crank-diagnostic cap
`[0x0233]` (gated by flags), then `[0x0227]` under `M_FD3E.14`. The lowest
applicable cap wins. Raising `C_N_MAX` alone will not lift the limit if another
cap in the chain is lower under the current conditions.

## 5e. The diagnostic / KWP2000 layer

The K-line serial path is a full KWP2000 stack, readable end to end:

- **Byte framing ISR** — an 8-state machine at file `0x44B74`-`0x44C74`,
  dispatched through a jump table at file `0x12D84` (`EXTP #0x024`). States cover
  header, length, service-id, data and checksum bytes; `S0BG` (baud) is set to
  `0x2F` on frame start. This is the layer GKFlasher talks to.
- **Service dispatcher** — file `0x3BE74`, a 30-way compare-and-jump over service
  IDs. Standard services (`0x10` StartDiagSession, `0x11` ECUReset, `0x1A`
  ReadEcuId, `0x23` ReadMemByAddress, `0x27` SecurityAccess, `0x30`
  IOControlByLocalId, `0x31`/`0x32`/`0x33` routines, `0x81`/`0x82`
  Start/StopComm, `0x85` ControlDTCSetting) plus a block of manufacturer
  services (`0x12`/`0x13`/`0x1B`/`0x1C`, `0x61`-`0x66`, `0x71`-`0x76`,
  `0x79`/`0x7A`). A second session dispatcher is at file `0x41FF6`.
- **SecurityAccess (0x27)** — handler at file `0x4219E`. It is per-subfunction:
  the subfunction byte indexes a 12-byte-stride parameter block, a seed is issued
  and the returned key checked. This is the gate on ReadMemByAddress /
  WriteMemByAddress — i.e. the legitimate full-unlock path for an owned ECU, the
  thing GKFlasher currently needs the bench IOCLID patch to substitute for. The
  **mechanism and location are mapped; the exact seed→key transform is not yet
  extracted** — a bounded next step for anyone wanting native full access over
  K-line. Note this is *diagnostic* security only; the immobiliser (SMARTRA) is a
  separate system and is already disabled on this car.

## 5f. The engine-state machine, and what selects the second fuel map

`[0xC20B]` (file `0x1BEE0`–`0x1C6B0`) is a six-state engine-state machine; each
state owns one flag bit, which is how the rest of the firmware tests it:

| state | flag | meaning | entered when |
|---|---|---|---|
| 0 | `M_FD14.8` | stopped | — |
| 1 | `M_FD16.2` | cranking | `N/32 < C_N_MAX_BOL_ST` from any running state (stall) |
| 2 | `M_FD14.12` | **idle** | rpm < the idle-exit threshold `[0xCEC0]` (from 3, 4 or 5) |
| 3 | `M_FD14.14` | throttle transition | `M_FD46.0` or `!M_FD24.13` (throttle flags) from 2, 4, 5 |
| 4 | `M_FD14.15` | drive | rpm ≥ `[0xCEC0]` from 2, 3 or 5 |
| 5 | `M_FD16.0` | overrun (PUC) | from 4, on the conditions in [[puc-overrun-map]] |

**This resolves §5a:** `M_FD14.12` is "engine state == idle", so `0xD528` is the
**idle fuel map** — exactly what the hand-made def calls it — and the fork at
`0x2E5C2` is the idle/non-idle switch, not start enrichment. Cold-start richness
is elsewhere (the `IP_TI_CAST*` tables at `0xAB0E`/`0xAB3E`, read at `0x1C76A`).

The overrun state is what the injector-inhibit machinery keys on; the full
trace, including the discovery that the injector "mask" tables are indices into
a pattern table at cal `0xB848`, is in [[puc-overrun-map]].

## 6. An undocumented non-volatile record area at file `0x4000`

The region file `0x4000`–`0x5000` (physical `0x84000`–`0x85000`) is **not**
covered by `--read-calibration` and is all-`FF` in both of our reads, because we
have never read it. In the OpenGK full dumps it contains **two near-identical
copies** of a structured record:

```
0x4000  81 4c 00 00 "KR77035111" 00 00 01 7f 02 7f 03 7f  81 4c 00 00 ...
0x47F6  ... 82 4c 00 00 "KR77035111" 00 00 01 7f 02 7f 03 7f  82 4c 00 00 ...
```

The leading byte increments `0x81` → `0x82` between the two copies. That is the
classic flash-EEPROM-emulation pattern: alternating banks with a monotonic
sequence number, newest-wins. Each bank carries three sub-blocks
(`0x4000`/`0x42B8`/`0x44B0` and the same three offset by `0x7F6`).

The `0x42B8` sub-block is a run of fixed-size records whose leading 16-bit field
decreases monotonically down the list:

```
7e fd 02 00 01 00 | b2 00 02 28 4a 2c b5 80
7e c4 02 00 00 00 | 78 ff 01 28 1b 11 06 18
7d c4 0e 00 03 00 | b1 00 01 27 52 15 ad 69
...
78 ca 02 00 00 00 | b2 00 01 05 1c 00 59 00
```

A descending counter plus a payload, oldest last — an **age-stamped fault log
with freeze-frame data** is by far the best fit.

This is a genuinely unexplored area for the platform, and it is reachable: it
sits inside the program-zone read range. Reading it would expose learned
adaptation and stored fault history; erasing it is a plausible "reset
adaptations without disconnecting the battery". **All of that is inference from
one reference dump — none of it is verified against a running car, and nothing
here should be written to.**

## 7. Tooling

`tools/c166/` — no public C166 disassembler existed, so this is a new one.

| file | what |
|---|---|
| `c166dis.py` | C166/C167 instruction decoder. 0.15% undefined on a blind linear sweep of the image; phase-independent (sweeps from offset 0 and 2 converge to identical instruction counts) |
| `addrmodel.py` | the §2 address model, one place |
| `analyze.py` | recursive-descent + linear-fill, 702 functions, 78 507 instructions |
| `xref.py` | calibration cross-references — 1321 distinct addresses touched, 767 landing exactly on a mapped symbol |
| `tables.py` | the §4 geometry extractor |

Two encoding quirks worth recording, both found by semantic contradiction and
fixed:

- `MOVBZ`/`MOVBS` register-register form is encoded **`mn`, not `nm`** — the low
  nibble is the word destination, the high nibble the byte source. Everything
  else in the ALU column is `nm`.
- `BSET`/`BCLR`/`JB`/`JNB` take a **bit address**, not a `reg`: `0x00`–`0x7F` is
  RAM at `0xFD00 + 2n`, `0x80`–`0xEF` is SFR at `0xFF00 + 2(n−0x80)`,
  `0xF0`–`0xFF` is a GPR. Decoding these as `reg` produces plausible-looking
  nonsense like `BSET DPP0.15`.

## Open

- The scanner's linear axis tracking (§4) should become a backward-CFG walk.
- ~~`M_FD14.12` — what selects the second fuel map (§5a).~~ Resolved: idle state (§5f).
- ~~Whether `0x48000` is a live shadow or a programming buffer (§5c).~~ Resolved in §5c.
- The `0x4000` record format (§6), and a real read of it from our car.
- The KWP2000 handler beyond the dispatcher (§5e): the SecurityAccess seed→key
  transform is still not extracted.
- The DPP1 page is not constant (`MOV DPP1,#0x12` at init, `MOV DPP1,[0x0000]`
  later); jump tables in the `0x4000`–`0x7FFF` window were found under page
  `0x24` (file `0x104CA` for the injector-inhibit machine). The address model in
  §2 should record DPP1 per call site rather than "not calibration".
