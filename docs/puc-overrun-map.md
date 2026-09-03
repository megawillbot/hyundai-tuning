# PUC / overrun fuel cut — located in ca654019

Established **2026-09-02**. Motivation: assessing a decel "pop & bang" tune.
Nothing here has been flashed. **All of it is inference from structure — see
[Before trusting this](#before-trusting-this).**

Overrun fuel cut on SIMK43 is **PUC** — *pull fuel cut-off* (Siemens naming;
`PU` = pull/overrun without cut, `PUC` = pull with cut, `REAC` = reactivation).
None of it is in `defs/ca654019 2700.xdf` (55 entries). All of it exists in our
binary.

---

## Code-verified (2026-09-03) — read this first

The program-zone disassembly ([[ecu-architecture]]) reached every table below.
**All 23 pinned addresses are confirmed**: each is read by an interpolation or
stepped-lookup call whose recovered geometry and axes match this document
(`tools/c166/tables.py` output, symbol column). Two of the "unresolved" tables
are now placed by the code too: `IP_IGA_ACCIN_PUC__N` = `0x9FE4`,
`IP_IGA_ACCIN_PUC_AT__N` = `0x9FE8` (4 × 8-bit on the `0x9078` axis), and
`IP_CDN_REAC_CYCNR__N_32__GR_MT` = `0x9BC8`.

Reading the consuming code corrects three things this document previously
inferred from structure, and answers the gating question properly.

### 1. The injector tables are pattern *indices*, not masks — retraction

`ID_PAT_INH_IV_PUC_1/2` values (4 and 9) are **not** cylinder bitmasks ("cyl 3",
"cyl 1,4" above is wrong). The apply routine at file `0x14436` takes the maximum
of several inhibit *levels* (`[0xC1AB]` from overrun, plus rev-limit / launch /
traction sources) and indexes a **word table at cal `0xB848`** with it
(`MOV R5,[R4+#0x3848]`, DPP0). That table is in the extended def already as
"pattern, inhibition, injection valve" (ca652048 `0xB0D2`). Bits 0-5 are the six
injectors (bit-to-cylinder order not yet verified), bit 12 is a flag:

| index | word | injectors inhibited | count |
|---|---|---|---|
| 0 | `0x0000` | `000000` | 0 |
| 1 | `0x1000` | `000000` | 0 |
| 2 | `0x1040` | `000000` | 0 |
| 3 | `0x1110` | `010000` | 1 |
| **4** | `0x1248` | `001000` | **1** (stage 1, stock) |
| 5 | `0x124A` | `001010` | 2 |
| 6 | `0x14AC` | `101100` | 3 |
| 7 | `0x1555` | `010101` | 3 |
| 8 | `0x19D9` | `011001` | 3 |
| **9** | `0x1B6D` | `101101` | **4** (stage 2, stock) |
| 10 | `0x1BB7` | `110111` | 5 |
| 11 | `0x1EF7` | `110111` | 5 |
| 12 | `0x1FFE` | `111110` | 5 |
| **13** | `0x1FFF` | `111111` | **6** (final stage, hard-coded) |

The stock overrun cut is therefore **staged: one cylinder, then four, then all
six**, each of the first two stages lasting a hard-coded 11 cycles
(`MOVB RL5,#0xB` at `0x14508`/`0x1454A`). The 6-point rpm axis only selects the
index used during those two short stages.

### 2. The state machine

Injector-inhibit state `[0xC1AC]` (function at file `0x144BA`, jump table at
file `0x104CA`), active only while the engine-state machine is in **overrun
(state 5, `M_FD16.0`)**:

| state | does | next |
|---|---|---|
| 0 | look up `PUC_1` on rpm/32 → level `[0xC1AB]`; counter = 11 | 1 |
| 1 | count down | 2 when zero |
| 2 | look up `PUC_2` → level; counter = 11 | 3 |
| 3 | count down | 4 when zero |
| 4 | **level = `0x0D`** (constant, `0x14574`/`0x14586`), set `M_FD16.12` | stays |

On leaving overrun (`M_FD16.0` clear) the reactivation path runs:
`ID_PAT_CYCNR_REAC` (all zero) cycles of `ID_PAT_INH_IV_REAC` (all zero), gated
on coolant > `C_TCO_PAT_REAC_MIN`, a snap-lift test using the
`ID_TPS_GRD_PAT_INH_IV_REAC*` tables against the TPS gradient `[0xF497]`, and
`IP_CDN_REAC_CYCNR` — i.e. stock reactivates everything at once.

The **engine-state machine** `[0xC20B]` (file `0x1BEE0`–`0x1C6B0`) is what
decides overrun. States: 0 stop, 1 crank, **2 idle** (`M_FD14.12`), 3
(`M_FD14.14`), 4 drive (`M_FD14.15`), **5 overrun** (`M_FD16.0`). From drive
(`0x1C3CE`+), the cut engages when all of:

- rpm ≥ the idle-exit threshold `[0xCEC0]` (RAM);
- `N/32 ≥ [0xC20F] + [0xC20C]` where `[0xC20F]` is the coolant×gear lookup of
  `IP_N_MIN_PUC_AT` (or `IP_N_ACCIN_MIN_PUC_AT` under `M_FD8C.14`, or
  `C_N_MIN_PUC_DIAG` under CAN-timeout flags) and `[0xC20C]` is the hysteresis
  (`C_N_HYS_MIN_PUC` = 6 → 192 rpm before a cut, `C_N_HYS_MAX_PUC` = 16 → 512
  rpm after one);
- if `N/32 < C_N_MAX_INF` (48 → 1536 rpm) the rpm gradient `[0xC59F]` must not
  be below `C_N_GRD_MIN` (stall protection);
- the closed-throttle / delay flags `M_FD1A.6` and `M_FD64.0`, and
  `N/32 ≥ C_N_MIN_DHP` (22 → 704 rpm).

It exits overrun (`0x1C52A`+) when the throttle flags drop (→ state 3) or when
`N/32 < [0xC20F]` (→ drive if rpm ≥ `[0xCEC0]`, else idle). So **resume is the
bare `IP_N_MIN_PUC_AT` value — 1248 rpm warm — and there is no upper rpm bound
on the cut**.

### 3. The ignition tables are relative corrections — datum resolved

At file `0x20FBA`–`0x210B6` the overrun ignition value is chosen —
`IP_IGA_PUC_AT__N` while a cut is pending or active (`M_FD16.5`),
`IP_IGA_ACCIN_PUC_AT` under `M_FD8C.14`, `IP_IGA_PU_AT__N__TCO` on a plain
trailing throttle, `IP_IGA_MAX_PUC__N` under `M_FD16.4` — then **slew-limited**
toward the target (`[0xE10E]`, step `[0xE110]`) and finally **added to the
running angle as `value − 128`** (`SUB R4,#0x80; ADD R8,R4`), clamped 0–255.

So the `0.375X − 48` form this document worried about is exactly
`0.375 × (X − 128)`: these tables are **signed retards/advances in 0.375°
units around 128, applied on top of the base angle**. Stock `IP_IGA_PUC_AT` =
`75, 61, 61, 61` → **−19.9° at 1200 rpm, −25.1° from 1600 rpm up**; the
`ACCIN` variant `65, 46, 38, 57` → −23.6 / −30.8 / −33.8 / −26.6°; `IGA_PU_AT`
row 0 `86, 83, 80, 75` → −15.8 … −19.9°. Absolute angles are base map plus
these; no logger channel is needed to fix the datum any more.

### 4. Answer to "pops only when winding down from 3500+"

Pops need fuel in the exhaust *and* late combustion. During a stock cut there is
neither above 1248 rpm (all six cut after ~22 cycles). The levers, honestly:

| approach | rpm-windowed? | verdict |
|---|---|---|
| Raise `IP_N_MIN_PUC_AT` to ~3500 so fuel stays on below it | yes, but **inverted** — pops *below* 3500 on every lift, silent above | no |
| Move the `0x8757` axis and edit `PUC_1/2` | only the two 11-cycle stages change; the steady state is still all-six | no |
| Use `C_N_MAX_INF` / gradient test as an upper bound | it is a stall guard *below* 1536 rpm, not an upper cap | no |
| Coolant / gear columns of `IP_N_MIN_PUC_AT` | not rpm | no |
| **Program patch: final-stage level from a table** ([[program-zone-plan]] §4) | **yes** — the new `ID_PAT_INH_IV_PUC_3` on the rpm/32 axis picks the steady-state pattern per rpm | the route |

**Latched version (decided 2026-09-03).** Rather than a bare rpm window, the
patch carries a latch: a free RAM bit (`M_FD40.15`) is set once rpm/32 reaches
`C_N_ARM_POP` (cal `0xBC91`) and cleared once rpm/32 falls below `C_N_DISARM_POP`
(cal `0xBC92`, default ~1024 rpm). The rpm-windowed pattern applies only while
latched. Net behaviour: no pops until the engine has been revved past the arm
point, then pops on overrun until rpm next returns to idle; and since rpm passes
through the disarm band on shutdown, key-off disarms for free. Both thresholds
are cal bytes. The latch bit is self-contained (a bit no stock code touches), and
the arm/disarm test is hooked by **redirecting the inhibit task's single caller**
(`0x3AC00`) through a stub that tail-calls the unmodified task — the task's
register-save prologue is left stock (an earlier prologue-displacement design had
a stack bug, caught in review; see `roms/tunes/puc-final-stage-patch/notes.md`).

The tune is then cal-only on top of the patch: `0xBC8B` = `0D 0D 0D 0D 0D <p>`,
axis top `0x875C` = 94 (**3008 rpm**; safe — all four tables on that axis are
flat with rpm, verified), `0xBC91` = 125 (**arm at 4000 rpm**), and more retard
in the 3500 column of `IP_IGA_PUC_AT__N` (`0xA19B` 61 → 40, −25° → −33°; the
stock `ACCIN` variant already commands −33.8°). Below 3008 rpm, or unarmed,
nothing changes (all six cut, silent, resume at 1248). Above it when armed, `<p>`
cylinders are cut and the rest fire late: the cut cylinders pump air, the
firing ones burn in the exhaust — the classic recipe.

**Patch caveat found in review (2026-09-03) — the apply routine gates and maxes.**
Writing the pattern index to `[0xC1AB]` is *not* sufficient on its own. The mask
applier at `0x14436` (called `0x4436`):

- **Gates on `M_FD12.7`.** If `M_FD12.7` is **clear** when apply runs, it ignores
  every source and forces the index to `0x0D` (all six). Our patched final stage
  would then be **inert** — stock all-six, no pops. `M_FD12.7` is set/cleared by a
  temperature-like threshold routine at `0x40000`+ (compares `[0xF970]`/`[0xF972]`
  scaled, against `0x62`/`0x93`), not obviously tied to overrun; its state during
  the final cut stage is **not settled statically**.
- **Takes the max**, not our value: `[0xC1AA] = max([0xC19A], [0xC5A0], [0xC57D],
  [0xC1AB], [0xC1AD])`, then outputs `pattern_table[[0xC1AA]]`. Our index 6 only
  wins if the other four sources are ≤6 at that moment. (During a clean coasting
  overrun they are expected to be ~0, but that is unconfirmed.)

Consequences, stated honestly:

- **Safety is unaffected in every case.** The output is always
  `pattern_table[max(...)]`, i.e. somewhere between our pattern and all-six — never
  fewer injectors than intended, never an invalid state, never anything outside a
  closed-throttle overrun. Worst case the patch does nothing.
- **Whether it actually pops depends on `M_FD12.7` being set and the other sources
  low during the final stage** — a runtime fact, not proven here.
- **The capture run settles it empirically** ([[next-capture-script]]): if the
  *stock* overrun shows the staged **1 → 4 → 6** cylinder cut, then `M_FD12.7` is
  set through overrun and the other sources are ≤4 then ≤9 at stages 0/2 — so
  index 6 will be honored at the final stage and the patch works. If the stock cut
  shows **all six from the first frame**, the pattern mechanism is gated off and
  the patch would be inert. **Do not flash the pattern patch until the capture
  confirms real staging.**
- **Contingency if inert:** have the state-4 handler write the injector mask word
  `[0xF9BA]` directly (bit 15 set, cut mask in bits 0-5) and skip apply, rather
  than routing through `[0xC1AB]`. Bigger stub, but bypasses both the gate and the
  max. Only pursue if the capture shows the gated-off case.

With our index 6 at the final stage the nominal cut sequence becomes 1 → 4 → **3**
cylinders (the last stage drops from four to three); the 4→3 step is momentary and
harmless.

Pattern choice: **6** (`101100`, three cut, three firing, *unevenly* spaced).
Even spacing (7 = `010101`, alternate cylinders) reads as a smooth tone; the
uneven set is what people hear as crackle, and three firing cylinders give
three late burns per cycle rather than two. Bit-to-cylinder order is still
unverified (the first patched log settles it); an uneven pattern stays uneven
whichever way the bits map, so the choice does not depend on it. Both images
are built and unflashed: `roms/tunes/puc-final-stage-patch/notes.md`.

The **"Threshold decision: keep the stock 2496 rpm breakpoint"** section below is
**withdrawn** — it assumed the masks were literal and the top cell alone set the
behaviour. Neither holds.

### 5. Still open after the code read

- Bit-to-cylinder order in the `0xB848` patterns (first patched log settles it).
- What `[0xF497]` (TPS gradient) and `M_FD1A.6` / `M_FD64.0` (closed-throttle
  and delay flags) are driven by — the `IP_MAF_INT_DLY_PUC` integrator is the
  obvious candidate for the delay.
- Whether a cut "cycle" is one ignition segment (assumed) — sets how long the
  two stock stages really last.

## How these addresses were derived

`reference/opengk-simk/XDF/Delta-27/ca652048 2700.xdf` is the only richly-named
def (725 tables, full Siemens symbols). Per [chase's writeup](https://chase.cc/blog/chiptuning-the-gk-2-7-ecm/)
ca652048 is a **5WY15** ECM (6520xx cals); ours is **5WY17** (65401x). Different
family — addresses do not transfer directly, confirmed by diffing.

So the map was built by **anchor alignment**:

1. Extract all 725 z-data blocks from the ca652048 XDF.
2. For each block >= 10 bytes and non-degenerate, search our cal zone
   (0x8000-0xDF40) for an exact byte match. Keep only blocks matching in exactly
   one place. -> **157 unique anchors**, deltas rising monotonically
   +0x00E0 ... +0x11D8.
3. For each target table, take the nearest anchor below and above. Where both
   have the same delta, the target address is **pinned**.

Comparison bins pulled from [OpenGK-org/opengk-simk](https://github.com/OpenGK-org/opengk-simk)
(~95 archived bins; our local mirror has 6):
`ca652048_G3N7TS0C`, `ca654012_G4N7TS0A`, `ca654014_G4N7TS0C`.

**Validation:** `IP_N_ACCIN_MIN_PUC_AT` was located *independently* by structural
fingerprinting (6x7 table, rows near-constant across gear columns, non-increasing
with coolant, values in 800-2560 rpm) at **0xA8C4**. The anchor map predicts
**0xA8C4**. Two unrelated methods agreeing is the main reason to believe the rest.

The whole PUC block is **byte-identical across all four calibrations** — both ECM
families — at different base offsets (ours +0x4A4 vs ca652048 in that region;
ca654012 +0x36E, ca654014 +0x370). Deltas are *not* constant across the cal;
they shift per region, which is why per-table bracketing was necessary.

## Address map (our cal, file offsets)

23 of 32 PUC-family tables are pinned **and** byte-identical to ca652048.

| Table | ca652048 | **ours** | len | status |
|---|---|---|---|---|
| `ID_PAT_CYCNR_REAC__N_32__GR_MT` | 0x960A | **0x99A6** | 42 | pinned |
| `ID_PAT_INH_IV_PUC_1__N_32` | 0x9634 | **0x99D0** | 6 | pinned |
| `ID_PAT_INH_IV_PUC_2__N_32` | 0x963A | **0x99D6** | 6 | pinned |
| `ID_PAT_INH_IV_REAC__N_32__GR_MT` | 0x9640 | **0x99DC** | 42 | pinned |
| `ID_TPS_GRD_PAT_INH_IV_REAC__TCO` | 0x9722 | **0x9AE2** | 6 | pinned |
| `ID_TPS_GRD_PAT_INH_IV_REAC_PU__GR_MT` | 0x9728 | **0x9AE8** | 7 | pinned |
| `ID_TPS_GRD_PAT_INH_IV_REAC_PUC__GR_MT` | 0x972F | **0x9AEF** | 7 | pinned |
| `IP_IGA_MAX_PUC__N` | 0x9C02 | **0xA128** | 4 | pinned |
| `IP_IGA_PU__N__TCO` | 0x9C4E | **0xA174** | 16 | pinned |
| `IP_IGA_PU_AT__N__TCO` | 0x9C5E | **0xA184** | 16 | pinned |
| `IP_IGA_PUC__N` | 0x9C6E | **0xA194** | 4 | pinned |
| `IP_IGA_PUC_AT__N` | 0x9C72 | **0xA198** | 4 | pinned |
| `IP_MAF_CRLC_PU__N` | 0xA28F | **0xA733** | 4 | pinned |
| `IP_MAF_MMV_MIN_PU__N` | 0xA35A | **0xA7FE** | 6 | pinned |
| `IP_N_ACCIN_MIN_PUC__TCO__GR_MT` | 0xA3F6 | **0xA89A** | 42 | pinned + fingerprinted |
| `IP_N_ACCIN_MIN_PUC_AT__TCO__GR_MT` | 0xA420 | **0xA8C4** | 42 | pinned + fingerprinted |
| `IP_N_MIN_PUC__TCO__GR_MT` | 0xA451 | **0xA8F5** | 42 | pinned + fingerprinted |
| `IP_N_MIN_PUC_AT__TCO__GR_MT` | 0xA47B | **0xA91F** | 42 | pinned + fingerprinted |
| `IP_TQR_REL_REAC_PU__N_32__GR_MT` | 0xAD05 | **0xB38F** | 42 | pinned |
| `ID_IGA_TCO_LGRD_PU__TCO` | 0xAEB2 | **0xB628** | 8 | pinned |
| `ID_IGA_TCO_LGRD_PU_AT__TCO` | 0xAEBA | **0xB630** | 8 | pinned |
| `IP_IGA_LGRD_PU__N__MAF_MMV` | 0xB2D4 | **0xC0CC** | 32 | pinned |
| `IP_MAF_INT_DLY_PUC__MAF_INT_PUC` | 0xB750 | **0xC5D0** | 12 | pinned |

**Unresolved** — bracketing anchors disagreed, and for the first four the bytes at
the predicted address also differ from ca652048, so those predictions are wrong:
`IP_FAC_CAT_DLY_PUC__CAT_DIAG`, `IP_FAC_TQI_REAC_LGRD_CYCNR__CYC_REAC`,
`IP_IGA_ACCIN_PUC__N`, `IP_IGA_ACCIN_PUC_AT__N` (bytes differ);
`IP_CDN_REAC_CYCNR`, `IP_TQR_REL_REAC_PUC`, `IP_TQR_REL_REAC_TPS_GRD`,
`IP_IGA_LGRD_PU_AT`, `IP_T_DLY_PUC__MAF_KGH` (bytes match, delta unpinned —
probably right, not proven).

### Axes

| Axis | ours | breakpoints |
|---|---|---|
| `ldpm_n_32_id_pat_inh_iv` (N_32, 6pt) | **0x8757** | 704 / 992 / 1312 / 1600 / 2016 / **2496** rpm |
| `sstm_n_3_4` (N, 4pt, 16-bit LE) | **0x9078** | 1200 / 1600 / 2400 / **3500** rpm |
| `sst_n_kf_zw_max_sa` (N, 4pt, 16-bit LE) | **0x9096** | 3000 / 4000 / 5000 / 6000 rpm |
| `sstm_tkw_1_6` (TCO, 6pt) | *(located in ca652048 @0x8757)* | -30 / -9.75 / +9.75 / +30 / +60 / +87 C |

Both 16-bit axes are **little-endian**. Reading them big-endian yields garbage
(47115, 40975 ...) — worth remembering, it cost a pass here.

## Stock behaviour

**`IP_N_MIN_PUC_AT__TCO__GR_MT` @0xA91F** — rpm at which fuel is restored. All
seven gear columns identical, so stock does no gear discrimination (but the table
*supports* it):

| coolant | -30 C | -9.75 | +9.75 | +30 | +60 | +87 |
|---|---|---|---|---|---|---|
| resume rpm | 1600 | 1344 | 1280 | 1248 | 1248 | 1248 |

So warm, on a closed throttle, fuel is cut from wherever you lift down to
**1248 rpm**.

**`IP_IGA_PUC_AT__N` @0xA198** — ignition during fuel cut. Raw values `4B 3D 3D 3D`:

| rpm | 1200 | 1600 | 2400 | 3500 |
|---|---|---|---|---|
| raw | 75 | 61 | 61 | 61 |
| if `0.375X-23.625` | +4.50 | -0.75 | -0.75 | -0.75 |
| if `0.375X-48` | -19.88 | -25.12 | -25.12 | -25.12 |

> **The absolute datum is unresolved** (corrected 2026-09-02). An earlier revision of
> this doc quoted only the first row, using the ignition equation from the **ADX
> logger** definition. But ca652048's XDF assigns these tables `0.375X-48`, not the
> `0.375X-23.625` it uses for the base map `IP_IGAB__N__MAF`. The base map's
> -23.625 is confirmed — its values decode to sensible spark advance and our own
> XDF defines it independently. The -48 offset applies to every ignition
> *correction/limit* table (`IP_IGA_PUC`, `IP_IGA_MAX_PUC`, `IP_IGA_PU`,
> `IP_IGA_MAX_KNK`, `ID_IGA_TRA_KNK`) and is **not** independently verified — the
> min/max metadata on those XDF entries is plainly un-curated (raw 0..255).
>
> What is *not* in doubt is the shape: one value at 1200 rpm and a constant
> **5.25 deg lower** from 1600 rpm up, whichever datum applies. The tuning argument
> below depends only on that shape. Do not quote the absolute figures until a log
> settles them — the ADX **Ignition Angle Idle/Decel** channel would do it directly.

**`IP_IGA_MAX_PUC__N` @0xA128** — clamp, flat across 3000-6000 rpm (raw 53 => -3.75
or -28.12 deg under the two offsets above).

**Injector inhibit patterns** — 6-bit masks over 6 injectors, **flat across all
six rpm breakpoints**:

- `ID_PAT_INH_IV_PUC_1` @0x99D0 = `000100` (cyl 3)
- `ID_PAT_INH_IV_PUC_2` @0x99D6 = `001001` (cyl 1, 4)
- `ID_PAT_INH_IV_REAC` @0x99DC = all zeros (nothing inhibited on reactivation)
- `ID_PAT_CYCNR_REAC` @0x99A6 = all zeros

> **Retracted 2026-09-03:** these are pattern-table *indices* (see the code-verified
> section at the top), not cylinder masks.

Two distinct non-overlapping patterns covering 3 of 6 cylinders. Exact semantics
**unconfirmed** — most likely alternating/staged masks for a soft cut rather than
a single "these cylinders off" set. Worth resolving before relying on it.

## Relevance to a pop & bang tune

The gating question was: *can it fire only when coasting down from a pull, not on
a normal lift at 2-3k?* Yes — three independent gates exist:

| Gate | Table | Note |
|---|---|---|
| **rpm** | `ID_PAT_INH_IV_PUC_1/2` (6 breakpoints) | see axis limit below |
| **coolant** | `IP_N_MIN_PUC_AT` (6 TCO breakpoints) | hot-only is free |
| **gear** | `IP_N_MIN_PUC_AT` (7 gear columns) | unused stock, available |
| **throttle slope** | `ID_TPS_GRD_PAT_INH_IV_REAC_PUC` @0x9AEF | snap lift vs gentle roll-off |

**The rpm axis tops out at 2496 rpm.** Above that the last breakpoint's value
applies, so editing only the top cell gives you ">= 2496 rpm" — lower than the ~4k
you wanted. To move the threshold you must move the axis itself.

**That looks safe.** The axis at 0x8757 is shared by four tables — but all four
are in the overrun family, and **all four are completely flat with rpm**
(verified). Moving breakpoints is therefore inert for the other three. This is
the same precondition the Ghost Cams patch relied on (see [[ghost-cams]], which
compressed `sstm_n_dif_kor_6_6`).

Same story for `sstm_n_3_4` @0x9078: shared by six tables, all in the PU/PUC
ignition family — nothing outside overrun. Not verified flat; check before moving.

Gentlest lever first: **retard `IP_IGA_PUC_AT__N`** (late combustion, hot exhaust,
no liquid fuel). The aggressive lever is the injector patterns, which put raw fuel
into the exhaust.

### Threshold decision: keep the stock 2496 rpm breakpoint

> **Withdrawn 2026-09-03** — see the code-verified section at the top.

**Decided 2026-09-02.** Do not move the axis. Editing only the top breakpoint's
value gives a ~2496 rpm threshold, which is high enough for normal driving, and
it keeps the change to two bytes with the shared axis untouched. Moving the axis
is available later if 2496 proves too low.

Checked against `logs/drive_raw_2026-08-29.csv` (cold-start city drive, 456 s):

- Closed-throttle baseline is **TPS raw 33-36**, not 0 — the ~11 deg zero offset
  from `logger-remap-ca654019.md`. Worth remembering for any overrun trigger logic.
- Top gear works out to **~22.5 rpm per km/h** (lowest ratio observed, speed raw
  10-64). Extrapolated: **~2250 rpm at 100 km/h**, ~2480 rpm at 110 km/h.

So NZ open-road cruise sits roughly **250 rpm below** the threshold — it works,
but the margin is thin. A downhill motorway lift at 110 km/h lands essentially
*on* the boundary. If that turns out to be annoying in practice the fix is to
raise the top axis breakpoint (which the flatness check above says is safe).

Both numbers depend on **road speed (pos 19) being km/h direct**, which
`logger-remap-ca654019.md` still lists as TBD. ~2250 rpm at 100 km/h is very
plausible for this 4-speed auto, which supports the assumption, but it is the one
unverified link in the chain — confirm it against a known speedo reading.

## Risks

- **The integrated-cat front manifold.** The cat sits in the manifold, closest
  possible to the ports, and takes the thermal spike undiluted. It is not a cheap
  bolt-on. The Ghost Cams patch was deliberately timing-only for this reason
  (see [[ghost-cams]]) — a pop tune is the thing its author avoided.
- **4x O2 / cat-efficiency monitoring** -> expect P0420/P0430 on top of the
  misfire CEL ghost cams already risk.
- **Supercharger.** Overrun airflow changes completely under boost. Sequence this
  after the blower or plan to redo it. See `docs/supercharger/`.
- **Checksum.** 0x99D0, 0xA198, 0xA91F, 0x8757 are all inside the checksummed zone
  0x8000-0xD780. `--correct-checksum` before flashing — `--flash-calibration` does
  not do it. See [[ghost-cams]].
- NZ: objectionable/excessive noise is a WoF matter. Keeping it out of the low-rpm
  bands is the point of the gating anyway.

## Before trusting this

This is structural inference — anchor alignment plus fingerprinting — **not a
disassembly**. It is strong (two independent methods agree; 23 tables pinned and
byte-identical across two ECM families) but it has never been confirmed against
running hardware.

**The existing logs do not confirm it.** Checked 2026-09-02: across both
`drive_raw_2026-08-29.csv` and `_run2.csv` there is **not a single frame** with
the engine above 500 rpm and all six injectors at zero — no fuel-cut event was
ever captured. The city drive has only 20 moving closed-throttle frames and all
of them are below 1250 rpm with fuel still flowing. That is *consistent* with the
predicted 1248 rpm resume point, but it is consistent-with, not evidence for —
the log simply never enters the fuel-cut region.

(`logs/drive_2026-08-28.csv`, the decoded log, is unusable for this: its channel
names are the ca663056 map, so `Vehicle Speed` reads flat zero, `Engine Speed`
maxes at 190 and timing sits at -73 deg. Same root cause as the raw-logger remap.)

**So a targeted capture is still required before writing anything.** Per
`docs/logger-remap-ca654019.md` we already have the channels needed:

| Channel | Pos | Use |
|---|---|---|
| Per-cylinder injection time | 43-54 (6x 16-bit LE) | drops to 0 when PUC engages — shows cut *and* pattern |
| Engine RPM | 20-21 | the cut/resume rpm |
| Coolant | 4 | the TCO axis |
| TPS | 11 | closed-throttle + gradient |

Predicted: on a warm closed-throttle coastdown the six injection-time pairs go to
zero and come back at **~1248 rpm**. If that is what the log shows, the map is
right. It also settles the `PAT_INH_IV_PUC_1/2` semantics — whether all six
injectors cut, or only the three named in the masks.

The capture needs to actually reach the fuel-cut region, which neither existing
log does. Minimum useful run, engine at full temp:

1. Two or three **full lifts from 4000+ rpm** to idle, throttle fully released.
2. A **motorway lift from ~110 km/h** — confirms real cruise rpm and the 2496
   margin above.
3. A steady pass at a **known speedo speed** — settles the road-speed scale, the
   last unverified link, and closes an open item in the remap doc.

The stock ADX has an **Overrun Fuel Cut** status bit and an **Ignition Angle
Idle/Decel** channel (`reference/opengk-simk/ADX/`), neither yet remapped to this
cal — both would corroborate directly.

## Open questions

- Semantics of the two `PAT_INH_IV_PUC` masks (staged? alternating? per bank?).
- Row/column orientation of `IP_IGA_PU_AT__N__TCO` (4x4) — not confirmed.
- Whether the six tables sharing `sstm_n_3_4` are rpm-flat.
- The nine unresolved tables above.
- Re-pull the OpenGK mirror: 4 more `ca654019` bins plus the `ca654012` /
  `ca654014` sets are archived and would strengthen every fingerprint here.

## Superseded by the full map

**2026-09-02.** The technique here was generalised to the whole calibration —
**607 symbol-named tables**, emitted as `defs/ca654019 2700 extended.xdf`. See
[[full-map-ca654019]] for the method, confidence tiers and validation. Every
address in this document survived that larger, better-anchored alignment
unchanged, and the ground-truth check went from 4/7 to **7/7**.

Two things from there bear directly on the pop & bang decision:

- **Scaling equations are inherited and unverified** — that is where the ignition
  datum correction above came from.
- **Cat protection is blind to exhaust-side combustion.** `IP_TEG__N_32__MAF`
  @0xCA24 models exhaust gas temperature (470-1160 C) purely from rpm and airflow,
  and drives the protective enrichment. It has no term for fuel burning *in the
  exhaust*, so the mechanism that guards the cat at WOT will not see, and will not
  react to, overrun popping.

## Reproducing

The anchor map and intermediate artifacts were built ad hoc in the scratchpad and
are not committed. The method is fully described in
[How these addresses were derived](#how-these-addresses-were-derived); it needs
only the ca652048 XDF (mirrored) and one ca652048 bin (upstream).
