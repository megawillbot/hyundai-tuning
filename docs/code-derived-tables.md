# Code-derived tables — the maps the alignment method missed

Built **2026-09-04** from the program-zone disassembly (see [[ecu-architecture]]
for the method and the table-access library). This is the complementary method
[[open-threads]] asked for: where [[full-map-ca654019]] names tables by aligning
our calibration against `ca652048`, this finds tables by watching the code read
them. The two agree closely where they overlap, and each reaches tables the
other cannot.

**Deliverable:** `defs/ca654019 2700 code-derived.xdf` — 464 tables, geometry
and axes certified by the interpolation call that reads each one, scaling left
raw, names provisional. An exploration aid, not a flashing definition.

---

## The headline: the main fuel map was not in the shipped definition

The extended XDF from [[full-map-ca654019]] covers the high-address region very
sparsely — **11 tables between `0xCA00` and `0xD770`**, where the code actually
reads **~44**. The alignment method's own documented ceiling ("permanently
invisible to alignment") is exactly this region, and it swallowed some of the
most important maps in the calibration:

| cal addr | what it is | geometry | in extended XDF? |
|---|---|---|---|
| **`0xD3A8`** | **main fuel / injection pulse width** | 16 rpm × 12 MAF, 16-bit interp | **no** |
| **`0xD528`** | **secondary fuel map** (flag-selected, low rpm) | 8 × 8, 16-bit interp | **no** |
| **`0xCA24`** | modelled EGT | 8 × 8, 16-bit interp | no |
| `0xCAB0` | modelled EGT (2nd) | 8 × 8, 16-bit interp | no |
| `0xCD88`–`0xD148` | six 8 × 12 16-bit maps | rpm × `[0xF4DA]` | no |

`0xD3A8` decodes cleanly against the stock bin — monotonic in load across every
one of its 16 rpm rows, ~325 raw at idle load rising to ~3700 at full load, on
the **same rpm × MAF axes as the ignition map** (`0x8E92` / `0x90E8`). It is
unmistakably the base injection map. It shares those axes with ignition because
the ECU searches both axes once and reuses the indices for several lookups (the
`0xFBE0`-`0xFBE6` scratch slots in [[ecu-architecture]] §3).

The fuel map was known to exist — [[car-notes]] diffed "`D3A8` fuel pulse width"
against the European car — but it never made it into a *definition* with usable
geometry. Now it has one.

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

`0xD528`'s restricted low-rpm axis points to a start/crank or limp path. The
selector is not yet identified. **Anyone tuning fuelling by editing `0xD3A8`
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
