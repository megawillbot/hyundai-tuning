# Code-derived tables — the maps the alignment method missed

Built **2026-09-03** from the program-zone disassembly (see [[ecu-architecture]]
for the method and the table-access library). This is the complementary method
[[open-threads]] asked for: where [[full-map-ca654019]] names tables by aligning
our calibration against `ca652048`, this finds tables by watching the code read
them. The two agree closely where they overlap, and each reaches tables the
other cannot.

**Deliverable:** `defs/ca654019 2700 code-derived.xdf` — 464 tables, geometry
and axes certified by the interpolation call that reads each one, scaling left
raw, names provisional. **152 of the 464 are in no other def**; the rest overlap
and serve as cross-checks. An exploration aid, not a flashing definition — for
the named maps (fuel, ignition, idle), use the hand-made `ca654019 2700.xdf`,
which has real scaling. (16-bit cells carry `mmedtypeflags="0x02"` for
little-endian — omitting it makes TunerPro read every 16-bit table byte-swapped.)

---

## Correction (2026-09-03): the fuel maps were already defined

An earlier draft of this file headlined "the main fuel map was not in the
shipped definition." **That was wrong and is retracted.** The hand-made
`defs/ca654019 2700.xdf` — 41 tables, the primary working def — already carries
`0xD3A8` ("Closed Loop Pulse Width", 16×12×16, scaling `0.004*X`, 0–30
mg/stroke) and `0xD528` ("Idle Closed Loop Pulse Width", 8×8×16), both present
in the Aug-28 pre-session backup. [[car-notes]] referenced the fuel map too. So
the fuel maps were known and defined before this work.

What was actually true is narrower: the fuel maps are missing from the
*auto-derived extended* XDF ([[full-map-ca654019]]), because the byte-alignment
method goes sparse above `0xCA00` (11 tables in `0xCA00`-`0xD770` where the code
reads ~44). The extended XDF is not the working def, so this is a limitation of
that one artifact, not a gap in the project's knowledge.

**For working the fuel map, use the hand-made `ca654019 2700.xdf`** — it has the
name, real `0.004*X` scaling, and the correct little-endian flag. The
code-derived def's raw values are for exploration only.

### What the code scan genuinely adds here

- **Independent confirmation** of the fuel-map geometry, axes and orientation.
  `0xD3A8` decodes little-endian into a textbook surface — monotonic in load
  across all 16 rpm rows — on the **same rpm × MAF axes as ignition** (`0x8E92` /
  `0x90E8`), which the code proves by reusing one axis search across both
  lookups (the `0xFBE0`-`0xFBE6` scratch in [[ecu-architecture]] §3). Two methods
  from unrelated evidence agreeing is the value, not novelty.
- **152 tables that are in *neither* def** (not the hand-made 41, not the
  extended 607), recovered with code-certified geometry. This is the real
  additive set — see below.
- The **modelled-EGT map `0xCA24`** is in neither def, so it *is* a genuine
  recovery (though [[full-map-ca654019]] §6 discussed it by address).

## Confirmed identities of novel tables (2026-09-03)

Two functional clusters among the 152 traced through the code that consumes them.

### The cat-overtemp protection subsystem

A complete, coherent thermal-protection loop, none of it in either def:

| cal addr | role | scaling / evidence |
|---|---|---|
| **`0xCA24`** | **modelled steady-state EGT**, 8×8 rpm/32 × load | raw ÷16 = **470–1160 °C** — matches [[full-map-ca654019]] §6 exactly, from an unrelated source |
| `0xCAB0` | duplicate of `0xCA24` (byte-identical) | second reference copy |
| `0xBA06` | thermal time-constant, 1-D f(airflow) | feeds the first-order filter |
| `0xB9EE` | **protection factor**, 1-D | applied when modelled EGT exceeds the limit |

The wiring (file `0x2D280`-`0x2D346`): `0xCA24` gives a steady-state EGT from
rpm/32 × load; it is filtered into a running estimate `[0xE5A6]` with a time
constant from `0xBA06`; that estimate is compared to a limit `[0xD020]`, and
above it the factor from `0xB9EE` drives protective enrichment/timing into
`[0xCFEA]`. **This is the system that pulls fuel and timing at sustained high
load to save the cat** — directly relevant to anyone doing exhaust, headers, or
forced induction, because it defines where the ECU thinks it is overheating.
(As [[full-map-ca654019]] §6 noted, the model has no exhaust-side combustion
term, so it cannot see overrun pops.)

### A warmup / cold-enrichment injection factor

`0xCC48` (and its twin `0xCC98`), 5 rpm × 8 temp, 16-bit, sits in the
**injection-time correction chain** (file `0x2E546`): its output multiplies into
the injection-time working value `[0xF560]`, just upstream of the altitude factor
`IP_TI_FAC_ALTI`. The values fall steeply from cold to hot and with rpm —
the signature of **warmup / cold-enrichment fuelling**. The exact multiplier
scaling is unconfirmed (the raw range is large), and the temperature axis is
`[0xC53F]`, identified as coolant-temp-like but not certain. Treat as a strong
lead for cold-start/warmup driveability, not yet a calibrated lever.

## RAM inputs identified

The axis a table is read on is whatever RAM variable the code passes to the axis
search. Decoding those variables' breakpoint arrays, and cross-referencing the
`__N_32` / `__MAF` suffix convention in the symbol names, identifies the engine
inputs that drive the maps:

| RAM | drives N axes | identity | evidence |
|---|---|---|---|
| `[0xF564]` | 34 | **engine speed (rpm)** | it is the ignition and fuel map Y-axis; axis `0,700,…,6900` |
| `[0xC59E]` | 139 | **engine speed / 32** | breakpoints ×32 give 700–6000 rpm; matches the `__N_32` suffix, the commonest axis type |
| `[0xF500]` | 16 | **air load / MAF** | the ignition and fuel map X-axis (`2359…27365`, /8 = 295–3420 mg/stk) |
| `[0xF501]` | 55 | **air load** (second scaling) | 8-point load axes 11–94 |
| `[0xF502]` | 22 | load / time index | — |
| `[0xC53F]` | 135 | temperature or rpm-derived index | 24–184 range, universal corrector |
| `[0xC543]`,`[0xC544]` | 29,14 | temperature-domain axes | — |
| `[0xF4DA]` | 9 | pedal / throttle | 0–200 clamped |

`[0xF564]` and `[0xF500]` are certain (they are the ignition map's axes, which
the hand-made def labels). `[0xC59E] = rpm/32` is strongly supported by the
breakpoint scaling and the symbol convention, not independently proven — its
writers land in the interrupt-vector region where linear decode is unreliable.
The temperature identities are provisional.

## Agreement with the symbol map

Over the 310 tables in both the code scan and the derived symbol map:

- **zero element-width conflicts, zero area conflicts**
- 100 exact geometry matches
- 146 pure 1-D transpositions (`N×1` vs `1×N`, no information conflict)
- 4 genuine disagreements, 2 of them the known scanner limitation below

Against the hand-made `defs/ca654019 2700.xdf`, **4/4 of the 2-D tables the scan
reaches match exactly, including both axis addresses**. This is strong mutual
corroboration: two methods from unrelated evidence (byte-alignment vs
control-flow) agreeing on 310 tables' shapes.

## `0xD5E8` — a real table our calibration leaves blank

The code reads a 6 × 6 × 16 interpolated map at `0xD5E8`, but in our calibration
those 72 bytes are **all-`FF`**. [[car-notes]] and [[full-map-ca654019]] §1 noted
the `0xD5E8`-`0xD707` run as unpopulated and inferred it was lambda-diagnostic
filler. The code confirms it is a **real, read table that our application
disables by leaving blank** — a Japan-market or emissions feature the Delta 2.7
does not use. Four such all-FF tables sit in `0xD5E8`-`0xD750`, all on
`[0xC59E]` × `[0xF500]` (rpm/32 × load) axes. Editing them does nothing unless
whatever gates them is also enabled.

## The second fuel map and its selector

At file `0x2E5C2` the injection path forks on RAM bit `M_FD14.12`:

- clear → main map `0xD3A8` (16 × 12, full rpm range)
- set → alternate map `0xD528` (8 × 8, rpm axis 500–1800 only)

**Resolved 2026-09-03:** `M_FD14.12` is the engine-state machine's **idle** flag
([[ecu-architecture]] §5f), so `0xD528` is the idle fuel map — as the hand-made
def names it. Not start or limp. **Anyone tuning fuelling by editing `0xD3A8`
alone will not touch `0xD528`** — if it is the cold-start map, that is where
start richness lives.

## Scanner limitation

Axis state is tracked linearly, so a lookup after a branch join whose arms
searched different axes records whichever arm came last. This affects tables
read once at a shared exit (e.g. `IP_TI_FL__N`, whose single call site sits past
the fuel-path fork). Where a table's function contains more than one Y search,
treat its 1-D axis as advisory. A backward-CFG walk is the fix (open).

## Reproducing

```
SCRATCH=<scratch> python tools/c166/tables.py      # geometry -> table_geometry.json
SCRATCH=<scratch> python tools/c166/emit_xdf.py    # -> defs/...code-derived.xdf
```

Inputs: the program read and the stock cal, both in `roms/stock/`. No external
data — unlike the alignment method, this needs no other calibration.
