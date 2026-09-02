# Full symbol map for ca654019 — method, confidence, findings

Built **2026-09-02**. Grew out of the PUC hunt in [[puc-overrun-map]]: the alignment
technique used there for 32 overrun tables generalises to the whole calibration.

**Result: 607 symbol-named tables and 768 constants located in our calibration**,
up from 42 tables / 13 constants in `defs/ca654019 2700.xdf`. Emitted as
`defs/ca654019 2700 extended.xdf` (607 tables + the 650 highest-confidence
constants) and `docs/ca654019-constants-map.csv` (all 768).

Tables and constants were mapped by **two different techniques with different
confidence** — see [Confidence](#confidence) and [Constants](#constants-768-of-922).

**Nothing here has been flashed. The working def was not modified.**

---

## Method

`reference/opengk-simk/XDF/Delta-27/ca652048 2700.xdf` is the only richly-named
SIMK43 definition (725 tables, 922 constants, full Siemens symbols). It is a
**5WY15** ECM; ours is **5WY17**. Addresses do not transfer.

1. **Extract** all 725 z-data blocks from the ca652048 def and pull their bytes
   from a ca652048 binary.
2. **Search** our cal zone (0x8000-0xDF40) for each block. Keep tables matching in
   1..60 places -> 537 candidate tables, 967 candidate positions.
3. **Align** by weighted monotonic DP: relative table order must be preserved
   between calibrations, so pick the maximum-weight chain of (source -> ours)
   pairs that is strictly increasing on both sides, weighted by table size.
   -> **530-table chain, 10 087 bytes**, deltas rising +0x00E0 .. +0x11D8.
4. **Interpolate** the remaining tables. Where the nearest chain entries above and
   below agree on the delta, the address is **PINNED**; otherwise UNCERTAIN.

Deltas are *not* constant across the calibration — they step per region (77 changes
across 530 tables), which is why a single offset fails and per-table bracketing is
required.

### Why not simple bracketing

The first attempt used only 157 globally-unique anchors and got 4/7 ground-truth
tables right. All three misses were unpinned. Raising the anchor count to 530 via
monotonic alignment took it to **7/7**.

## Confidence

| Tier | Count | Meaning |
|---|---|---|
| **VERIFIED** | 530 | Bytes found in our cal, position consistent with the global monotonic chain |
| **PINNED** | 77 | Not byte-matched, but bracketing chain entries agree on the delta |
| UNCERTAIN | 112 | Bracketing entries disagree — **excluded from the XDF** |

Constants were mapped separately by a different technique — see
[Constants](#constants-768-of-922) below.

Four independent checks, all passing:

1. **Ground truth 7/7.** Seven tables are named identically in both defs
   (`IP_ISAPWM_DHP__N__TPS`, `IP_ISAPWM_DHP_AT__N__TPS`, `IP_ISAPWM_TPS__N__TPS`,
   `sstm_dk_2_3`, `sstm_n_4_3`, `sstm_n_7_3`, `sstm_n_dif_kor_6_6`). Every
   predicted address matches our XDF exactly. `sstm_n_2_3` independently lands on
   0x8E94, which our def calls "rpm 16 axis".
2. **Zero overlaps.** 607 tables tile the span with **no collisions**. Random
   misplacement would collide constantly.
3. **Checksum boundary.** The mapped span ends at **0xD780** — precisely the end of
   the checksummed zone documented in [[ghost-cams]], which was derived from the
   checksum algorithm, an entirely unrelated source.
4. **Sibling cross-check.** ~317 of the 607 tables match verbatim in each of
   ca654012 / 014 / 015 / 021 / 024, with only 12-13 unmatched in the closest
   relatives.

### What is NOT verified

- **Scaling equations are inherited from ca652048 and are not independently
  checked.** This bit already: `IP_IGA_PUC_AT__N` was first reported using the
  ADX logger's ignition equation (`0.375X-23.625`), but ca652048 assigns the
  ignition *correction* tables `0.375X-48` — a 24.375 deg difference. See the
  correction note in [[puc-overrun-map]]. Table shapes are reliable; absolute
  values need a datalog or a second source.
- **Row/column orientation** is taken from ca652048 and is not confirmed per table.
- **Constants are mapped by a separate, weaker method** — see below. Treat the tiers
  there as genuinely different from the table tiers.

## Constants (768 of 922)

The table technique fails on constants — single scalars give no unique byte
signature, and they sit below the first table anchor. A different structural
property makes them tractable instead.

### The enabling structure

In ca652048 the constants block is a **densely packed, alphabetically sorted
array**:

- 922 constants spanning 0x8092-0x8592
- **904 of 921 adjacent pairs are exactly contiguous** (no gap, no overlap)
- 96.1% alphabetically ascending
- Cleanly partitioned by size: **1-byte constants run 0x8092-~0x8380, 2-byte
  constants ~0x8380-0x857F**, a handful of 1-byte at the end

So the layout is fully determined by *which* constants exist. Mapping to our cal
reduces to finding the insertions and deletions — a sequence-alignment problem.

### Method

Edit-distance DP (Needleman-Wunsch style) aligning ca652048's ordered constant
list against our raw byte stream. Placing a constant scores on byte equality;
inserting bytes (constants added in our cal) and deleting constants (removed in
ours) are penalised.

Two refinements mattered:

1. **Segmented on hard anchors.** A single end-to-end run drifts — it hit
   `C_MAF_MAX` and `C_VS_MAX_0` exactly but missed `C_MAF_KGH_MAX_DIAG` by 66
   bytes as error accumulated. Splitting at the three symbol-name anchors stops
   error propagating between segments.
2. **Stability filter.** The DP is run under five different scoring settings;
   only placements identical in all five are kept. 831 -> **768 stable**.

The block-end position is independently corroborated: the alignment says our
constants block ends at **0x8673**, and the first mapped table sits at 0x8674.

### Validation

**10/10 correct** against every constant whose address we know independently:

| symbol | predicted | truth | how we knew |
|---|---|---|---|
| `C_MAF_MAX` | 0x81B8 | 0x81B8 | anchor (symbol in our def) |
| `C_VS_MAX_0` | 0x8370 | 0x8370 | anchor |
| `C_VS_MAX_1_2` | 0x8371 | 0x8371 | our def: Speed Limiter 2 |
| `C_N_MAX` | 0x8222 | 0x8222 | our def: RPM Soft Limit |
| `C_N_MAX_MAX` | 0x8230 | 0x8230 | our def: RPM Hard Limit |
| `C_N_MAX_HYS` | 0x822B | 0x822B | our def: Hysteresis 1 |
| `C_N_MAX_HYS_MAX` | 0x822C | 0x822C | our def: Hysteresis 2 |
| `C_N_MAX_VS_DIAG` | 0x8233 | 0x8233 | our def: VS Diag Limit |
| `C_N_FCUT` | 0x8219 | 0x8219 | our def: Launch Limit 1 |
| `C_N_MAX_FCUT` | 0x8229 | 0x8229 | our def: Launch Limit 2 |

Supporting evidence:

- **89.7% of adjacent stable placements are exactly contiguous, with zero
  overlaps** — the reconstructed block has the dense packed structure the source
  block has.
- 86.5% of 1-byte and 88.3% of 2-byte stable placements also match ca652048's
  bytes.
- The soft/hard limit pair decodes to 6816 / 6912 rpm — a 96 rpm gap, exactly what
  the OpenGK notes say to expect.
- An alphabetical anomaly in the source (`C_N_MIS_FTP_MAX` sitting between
  `C_N_MAX_FCUT` and `C_N_MAX_HYS`) is faithfully reproduced in our block.

### Tiers

| Tier | Count | Meaning |
|---|---|---|
| **CONFIRMED** | 10 | Address known independently (table above) |
| **HIGH** | 640 | Stable across all 5 settings, bytes match, contiguous with a neighbour |
| MEDIUM | 118 | Stable but fails one of those checks |
| (unplaced) | 154 | No stable placement — **absent from the XDF and the CSV** |

`docs/ca654019-constants-map.csv` lists all 768 with tier, address, raw value,
decoded value, equation and description. CONFIRMED + HIGH (650) are also in the
extended XDF under their own two categories.

### What this does not establish

The semantic-plausibility check I first tried is **not** valid evidence and is not
claimed as such: for 1-byte constants "rpm <= 8500" is vacuously true (255x32 =
8160), so it passes at 100% on random addresses too. The seven `C_N_*` placements
that look implausible are all 2-byte, where the assumed scaling is probably just
wrong rather than the placement.

Confidence is **lower than for tables** and the failure mode is different: a
mis-placed constant is off by a few bytes and lands on a *neighbouring, plausible*
constant. Verify against a second source before writing to any of these,
especially MEDIUM.

## The extended XDF

`defs/ca654019 2700 extended.xdf` — **607 tables + 650 constants**, XML validated,
decodes correctly against our stock bin (spot-checked against values derived
independently).

Categories: Axes/pointers 274, Fuel/injection/lambda 77, Ignition/knock 74,
Air/MAF/throttle 63, Idle/ISA 40, Overrun PUC 31, Other 23, Diagnostics 11,
Thermal/cat 11, Torque model 3.

Each table's description carries its confidence tier and its ca652048 source
address. Axes are wired to the mapped axis tables where those are themselves
high-confidence, otherwise fall back to index labels.

**This is a reading and exploration tool.** It is auto-derived. Treat every value
as provisional until cross-checked, and do not flash anything edited through it
without the usual checksum step ([[ghost-cams]]).

---

## Scope: what these addresses apply to

**Calibration-specific, not car-specific.** Every ca654019 build shares this
layout, so the map applies to any ca654019 car, not just ours:

| build | tables byte-identical to ours |
|---|---|
| `G5J7TS0A` (ours, JP auto) | 607/607 |
| `G4E7TS0A` (EU auto) | 605/607 (99.7%) |
| `G5E7TM0A` (**manual**) | 605/607 (99.7%) |
| `E5N7SB1B` (EF Sonata) | 470/607 (77.4%) |
| `S5E7TM0B` (SM Santa Fe) | 421/607 (69.4%) |

The Sonata and Santa Fe differ heavily in *values* but the layout still holds —
same calibration, different application tuning. A **different** calibration number
gives 0/607 at the same addresses; nothing transfers.

## Generality: the method reruns on other calibrations

The pipeline was run unchanged against two calibrations never previously examined,
each scored against its own thin upstream XDF:

| calibration | chain | VERIFIED+PINNED | overlaps | ground truth |
|---|---|---|---|---|
| ca654019 (ours) | 530 | **607** | 0 | 7/7 |
| ca654021 | 504 | **575** | 0 | 7/7 |
| ca655022 | 463 | **532** | 0 | 7/7 |

Both upstream defs currently carry ~56 tables. So the reusable output here is not
the address list — that is ours alone — but the **method**, which takes any
calibration in the OpenGK archive from ~56 tables to 500-600 with the same
validation behaviour (zero overlaps, full ground-truth agreement).

Requirements to run it for another calibration: the ca652048 def, a ca652048 bin,
and a bin of the target calibration. All are in the OpenGK archive.

## Constants-block archaeology

The constants block is sorted, so **out-of-order entries mark later additions** —
constants inserted into whatever space was free beside functionally related
neighbours instead of triggering a re-sort.

First, a correction to my own measurement: 36 adjacent pairs look out of order
under naive ASCII sorting, but 21 of those are an artifact — `_` is 0x5F, which
sorts *after* `P`, so `C_ABC_INC_ISA_2_DIAG` / `C_ABC_INC_ISAPWM_H_DIAG` looks
inverted when it is correctly human-sorted. Under natural sort there are **15 real
anomalies**, and the block is even more strictly ordered than first reported.

The clearest case is a matched pair:

```
0x81AD  C_MAF_MIS_FTP_MAX   wedged inside the C_MAF_MAX_* run
0x821F  C_N_MIS_FTP_MAX     wedged inside the C_N_MAX_* run
```

Misfire / Federal-Test-Procedure thresholds for airflow and engine speed —
plainly added in one revision, each dropped into the nearest free slot beside its
functional relatives. Same signature for variants appended after their base
constant (`C_VLS_MAX_DIAG` -> `C_VLS_CAT_MAX_DIAG`, and the `VIM` / `VIM_1` /
`VIM_2` group), and for the tail past ~0x8582, which is an **append region**: a
run of constants that are neither alphabetical nor size-grouped, added after the
block was already laid out.

**The hoped-for payoff did not appear.** The obvious prediction — that alignment
should fail near these anomalies, since they are what differs between versions —
tests negative: UNPLACED+MEDIUM runs **32.6%** within 8 bytes of an anomaly vs
**28.7%** elsewhere. That difference is noise. The anomalies tell you how the
block was built; they do not predict where the mapping is weak, and are not used
in the tiering.

## Findings

### 1. The Japan-vs-Europe difference is entirely emissions/diagnostics

[[car-notes]] recorded 407 differing bytes vs the European `G4E7TS0A` and flagged
four runs as "not covered by any table in our XDF — worth mapping". Now mapped:

| Category | Bytes |
|---|---|
| **Ours blank/filler, EU has data** | **330** |
| Both have data, values differ | 77 |
| EU blank, ours has data | **0** |

The asymmetry is total — our calibration never carries data where the European one
is blank. Of the 77 genuine value differences: 6 bytes are
`IP_TCO_MES_DIF_MIN_DIAG__TCO_ST` @0xAA7E, 11 are `IP_TCO_SUB_DIF_MIN_DIAG__TCO_ST`
@0xC9B8 (both **coolant-temperature rationality diagnostics**, i.e. thermostat
monitoring), 2 are the checksum at 0xDEE0, and the rest are scattered singles in
the constants block plus 36 bytes adjacent to the D010 filler run.

The two largest runs are simply unpopulated in our cal: **0xD5E8-0xD707 (288 B) is
all-FF** and **0xD010-0xD057 is `00 10` filler**, in lambda-sensor-diagnostic
territory (`IP_VLS_CYC_AFL_MAX` / `IP_VLS_CYC_AFR_MAX` — O2 rich/lean switching
limits).

**This is not a read defect.** Our cal has 2618 FF bytes in the cal zone; siblings
ca654012/014 have 2815-2886. We have *fewer* blanks than our relatives, and both
independent reads agree exactly. Filler is normal structure here.

> Strengthens the existing conclusion: the `J` in `G5J7TS0A` buys no separate power
> calibration. It is stronger than that — the differences are mostly *absences*, in
> emissions monitors alone.

### 2. The 3700-4000 rpm ignition trough is not transaxle limiting

[[car-notes]] suspected "transaxle torque limiting or a knock-prone resonance".

- **`ca654019_G5E7TM0A` — the manual — has a byte-identical ignition map to ours**
  (`IP_IGAB__N__MAF` @0xA272, same SHA). That rules out automatic-transaxle
  torque limiting outright.
- The EF Sonata and SM Santa Fe calibrations show the same dip. It is an
  **engine-wide characteristic**, not chassis- or transmission-specific.
- **Knock control is perfectly smooth through the region.** `ID_FAC_KNK_0` steps
  51 -> 56 -> 61 across 3700/4000/4500, and the knock windows (`ID_KNKWB_0`,
  `ID_KNKWE_0`) just widen and saturate. No heightened sensitivity, no window
  shift. Evidence *against* a special resonance.
- The dip is **strongly load-dependent** — 0.2-1.0 deg at light load, up to
  **5.2 deg** at load >= 330:

  | load | 50 | 130 | 230 | 330 | 430 | 530 |
  |---|---|---|---|---|---|---|
  | dip @3700 | 0.5 | 0.7 | 1.8 | **5.2** | **5.1** | 4.0 |

- **WOT enrichment ramps at exactly the same rpm.** `IP_TI_FL__N` (AD0B) raw:
  38 at 3200, then **53, 63, 77** at 3700/4000/4500.

Timing pulled and fuel added together, only at high load, right at the engine's
torque peak, in every application and both transmissions. That is the calibration
tracking the knock/thermal limit through the volumetric-efficiency peak — **not
headroom waiting to be reclaimed.** Taking it out removes knock margin at the
single highest-cylinder-pressure point in the map.

### 3. Variable intake manifold is dead code

[[car-notes]] lists VIM as "a real mid-range torque lever ... completely absent
from our def". It is absent because it is **unconfigured**:

- `C_CONF_VIM = 0`
- All three 8x8 switchover maps (`ID_VIM`, `ID_VIM_1`, `ID_VIM_2`) all-zero
- All six `ldp_*_vim_*` axis/pointer tables all-zero
- Every threshold constant zero: `C_N_HYS_VIM`, `C_TPS_HYS_VIM`, `C_VB_MIN_VIM`,
  `C_VS_MIN_VIM`
- Diagnostics disabled (`C_ABC_INC_VIM_DIAG=0`, `C_ABC_MAX_VIM_DIAG=0xFF`)

Read in **ca652048 at its own XDF-documented addresses**, so this does not depend
on my mapping being right. The SIMK43 platform supports VIM; the Delta 2.7
application does not use it. Not a tuning lever on this engine — worth striking
from the wish list.

### 4. 5WY17 confirmed — the hardware question is closed

[[car-notes]] calls this "the last open question on our hardware". The archive
settles it. Across 26 calibrations the ECM family tracks the calibration number
exactly, and the boundary falls at ours:

| Calibration | ECM |
|---|---|
| ca654011, 012, 014, 015, **019** | **5WY17** |
| ca654020, 021, 024, 025 | 5WY18 |
| ca655016, 019, 022 | 5WY18 / 5WY1F |

**ca654019 is the last 5WY17 calibration.** Every archived ca654019 file is 5WY17:
the European GK is `5WY1708B`, the EF Sonata is `5WY1785D`. Those are the two
samples chase cited as evidence for 5WY18 — the archived files say otherwise. That
is now five independent lines of evidence for 5WY17 (GKFlasher `--id`, GKFlasher
`detect_offsets`, two repo filenames, and this boundary).

Likely explanation for the 5WY18 recollection: cars from ca654020 onward *are*
5WY18, and the transition is a single calibration step away from ours.

### 5. Reference values now readable

| Item | Value |
|---|---|
| RPM soft limit (ignition cut) | **6816 rpm** |
| RPM hard limit (fuel cut) | **6912 rpm** |
| Launch limit 1 / 2 | 4000 / **2784** rpm |
| Speed limiter 1 / 2 | 250 km/h (effectively off) |
| MAF max (`c_maf_max`) | **550.15 mg/stk** |
| MAF max diag | 1200 kg/h |
| Modelled EGT range (`IP_TEG__N_32__MAF` @0xCA24) | **470-1160 C** |

Two observations worth carrying forward:

- **Launch limits 1 and 2 are not equal** (4000 vs 2784), and the OpenGK notes say
  they should be set the same. Currently untouched stock, so this is how it ships —
  but it matters if launch control is ever enabled.
- **The ignition map's load axis runs to 580 mg/stk while `c_maf_max` clamps at
  550.** The top load column is past the clamp. That is the MAF ceiling the E46 MAF
  patch exists to address — directly relevant to `docs/supercharger/`.

### 6. Cat protection is blind to exhaust-side combustion

`IP_TEG__N_32__MAF` @0xCA24 is a clean, monotonic modelled-EGT map, 470 C to
1160 C over rpm x airflow, and it drives protective enrichment and timing
(`IP_TEG_FAC_LAM`, `IP_TEG_ADD_IGA__POW_DIF`).

It is a function of **rpm and airflow only**. It has no term for combustion
occurring *in the exhaust*. So the protection that guards the cat at 1000 C+ under
WOT cannot see, and will not respond to, unburnt fuel igniting downstream during
overrun. Relevant to the pop & bang question in [[puc-overrun-map]]: the usual
"the ECU protects the cat" reassurance does not apply to that failure mode.

## Reproducing

Scratchpad-only; not committed. Inputs: the ca652048 XDF (mirrored), one ca652048
bin, and our stock cal. The upstream archive was shallow-cloned (309 MB, ~95 bins)
for the sibling comparisons — the local `reference/` mirror has only 6.

## Open

- 154 constants still unplaced, and 118 MEDIUM ones want a second source.
- 112 UNCERTAIN tables excluded; more sibling bins would pin some.
- Equations unverified — the `-48` vs `-23.625` ignition-offset question is the
  live example.
- Program zone (0x10000-0x80000) untouched. `roms/stock/PROGRAM_..._2026-08-29.bin`
  is a failed read (49% FF, cal region 100% FF); adaptive ignition
  `ID_IGA_AD_0..5` lives there and needs a clean read via the IOCLID patch.
