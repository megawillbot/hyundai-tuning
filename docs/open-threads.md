# Open threads

Index of everything unresolved, and what would resolve it. Written **2026-09-03**,
top section rewritten **2026-09-03**, updated later the same day.
Individual docs hold the detail; this is the map of what is still owed.

---

## The blocker that turned out not to be one

The 2026-09-03 version of this file opened with "the one blocker that unblocks
the most: a clean program-zone read", believed to require the IOCLID
privilege-escalation patch flashed via bench.

**Resolved 2026-09-04 — we already had the read.**
`roms/stock/PROGRAM_ca654019_read_2026-08-29.bin` is a *complete, valid* program
dump. The 49% `0xFF` is erased flash past the end of the image; the 239 KB code
region is byte-identical to three independent OpenGK dumps. See
[[ecu-architecture]] §1. The program zone reads fine over K-line with plain
`--read` — what `--read` loses is the *calibration* region (all-FF), which is
why the file looked empty. No BSL, no bench, no IOCLID patch.

That unblocked, in one session, most of what this section said it would:

- **A C166 disassembler** ([[ecu-architecture]] §7) — none existed publicly.
- **The address model** — two DPP windows, not one ([[ecu-architecture]] §2).
- **The table-access library** — storage order, axis format, interpolation,
  `IP_`/`ID_` semantics, all certain ([[ecu-architecture]] §3).
- **Code-certified geometry for 464 tables**, including the main fuel map and
  EGT map the alignment method missed ([[code-derived-tables]]).

Still genuinely gated on more work (not on a read):

- **Scaling equations** remain the largest unverified thing. The arithmetic is
  in the code now; it needs the per-table decode routines read, not just the
  lookup library. A tractable next step, no longer a hardware gate.
- **The ~240 diagnostic/timer/threshold tables no logger can see** — many now
  have geometry from the code scan; names still want a second source.
- Below: the historical note on what the read would unlock, left for context.

<details><summary>Original 2026-09-03 framing (superseded)</summary>

- **Tables our calibration has that ca652048 does not.** The alignment method has a
  hard ceiling: it can only ever name things present in ca652048. We already know
  of a ~297-byte region near the lambda tables where our cal carries content the
  reference simply does not define. That is permanently invisible to alignment and
  trivial for a disassembly.

### Ghidra and the symbol map are complementary, not redundant

Worth writing down because it determines the order of work:

- **Ghidra gives certain structure, zero names.** The binary has no symbols, and
  the repo's `c167_symbol_descriptions.py` covers **C167 CPU registers only**
  (`DPP0`, `PSW`, `SYSCON` …) — nothing calibration-related.
- **The map gives names with uncertain structure.** All naming traces back to the
  one richly-named def, ca652048.

So the productive order is: use [[full-map-ca654019]] as a **symbol file for the
data segment**, let named data identify the code that touches it, then let the code
certify the map back. Two specifics make the head start real:

- **274 of our 607 entries are axes and pointer tables.** `ldp_` means
  link/pointer — code reads a table to find another table. Data-driven indirection
  is exactly what static analysis handles worst.
- **C167 is segmented.** Data access goes through the DPP registers, so resolving
  "which calibration address does this instruction touch" means tracking dynamic
  page-pointer context. Having ~600 expected target addresses turns discovery into
  confirmation.

Neither blocks the other. The map is usable now; the program read makes it certain.

</details>

---

## New since the program zone opened (2026-09-04)

Detail in [[ecu-architecture]] and [[code-derived-tables]]. Still open:

| Item | Resolved by |
|---|---|
| **Scaling equations** for all tables | Reading the per-table decode routines (the arithmetic around each lookup call) — no longer a hardware gate |
| ~~**`M_FD14.12`** — selector between main fuel `0xD3A8` and alternate `0xD528`~~ | **Resolved 2026-09-03** — it is the engine-state **idle** flag; `0xD528` is the idle fuel map ([[ecu-architecture]] §5f) |
| ~~Is `0x48000` external RAM (live cal shadow)?~~ | **Resolved 2026-09-04** — external SRAM shadow of the cal, header-validated against flash. Base maps read from **flash**, so not a live-tuning lever; but the **adaptive/knock learning system lives there** (pointer tables at cal `0x9F1A`/`26`/`32`, per-cylinder loop). See [[ecu-architecture]] §5c |
| **Security Access (0x27) seed/key** | Handler at file `0x4219E`, per-subfunction param table; the compute path past the `0x3812` memcpy is not yet read. The legitimate full-unlock path for an owned ECU |
| The `0x4000` NVM record format (fault log?) | A real read of file `0x4000`-`0x5000` from our car (it is inside program-read range) |
| Scanner's linear axis tracking | Backward-CFG walk in `tools/c166/tables.py` |
| ~240 diagnostic tables named | A second same-family named def, or per-table decode |
| **Monitor names in the constants map** | **Corrected 2026-09-03** for `0x80BB`–`0x80C8` by code-pairing INC/MAX ([[diagnostics-and-levers]] §1). The same pairing trick should be run over every other paired constant family (`C_*_MIN`/`_MAX`, `_ST`/`_AT` twins) before their names are trusted |
| **Program-zone flash path** on a 5WY17 over K-line | Never exercised here; see [[program-zone-plan]] §2 — ask chase / OpenGK first |
| Bit-to-cylinder order of the injector pattern table `0xB848` | First patched log, per-cylinder injection channels |

## Open by area

### Symbol map — [[full-map-ca654019]]

| Item | Resolved by |
|---|---|
| **Equations inherited from ca652048, unverified** | Program read, or the ignition-datum log below |
| 112 UNCERTAIN tables excluded | More sibling bins would pin some |
| 154 constants unplaced, 118 MEDIUM | Program read; a same-family named def would also do it |
| Row/column orientation unconfirmed | Program read |

The equation problem is not hypothetical — it has already produced one real error
(the `-23.625` vs `-48` ignition datum, corrected in [[puc-overrun-map]]).

### Overrun / pop & bang — [[puc-overrun-map]]

| Item | Resolved by |
|---|---|
| **Whole map unvalidated against running hardware** | The capture run |
| ~~Semantics of the two `PAT_INH_IV_PUC` masks (3-of-6 or 6-of-6?)~~ | **Resolved 2026-09-03** — indices into the `0xB848` pattern table; staged 1 → 4 → 6 cylinders ([[puc-overrun-map]] code-verified §1) |
| ~~Absolute ignition datum for the PUC tables~~ | **Resolved 2026-09-03** — relative corrections, `0.375 × (X − 128)` deg added to the base angle ([[puc-overrun-map]] code-verified §3) |
| ~~Are the six tables sharing `sstm_n_3_4` rpm-flat?~~ | **Checked 2026-09-03** — no (only `IP_IGA_MAX_PUC` is flat); the pop tune does not need to move that axis. The four tables on `0x8757` **are** all flat |
| Nine unresolved PUC tables | Three placed by the code (`IP_IGA_ACCIN_PUC(_AT)` `0x9FE4`/`0x9FE8`, `IP_CDN_REAC_CYCNR` `0x9BC8`); the rest still want anchors |
| 2496 rpm threshold margin at motorway cruise | Depends on road-speed scale below |

### Logger — [[logger-remap-ca654019]]

| Item | Resolved by |
|---|---|
| **Road-speed scale still TBD** | One steady pass at a known speedo speed |
| MAF / injection scaling, and a >4k point | A road pull |
| `logs/drive_2026-08-28.csv` unusable (ca663056 channel names) | Re-decode with our map |

### Car — [[car-notes]]

Three long-standing questions closed on 2026-09-02 (ignition trough, the 407-byte
Japan/Europe delta, 5WY17). Still open:

- The **emissions oddity** — conflicting `SPEED DENSITY` / `NON SPEED DENSITY` flags
  in the VIN DB on a 4xO2 car. Partly explained now: our cal has 330 bytes of
  emissions/diagnostic tables *unpopulated* where the European one has data. Whether
  that fully accounts for it is unconfirmed.
- **Supercharger** work in `docs/supercharger/` — note `c_maf_max` clamps at
  **550.15 mg/stk** while the ignition map's load axis runs to 580, so the top
  column already sits past the clamp. That is the ceiling the E46 MAF patch exists
  to address.

---

## Cheap wins available now

No hardware access, no risk:

- Check whether the six tables sharing `sstm_n_3_4` are rpm-flat (the `0x8757`
  axis check was done; this one was not).
- Re-pull the OpenGK mirror. Upstream has ~95 bins; `reference/` has 6. Four more
  ca654019 bins and the full ca654012/014/015 sets are there, and more siblings
  pin more tables.
- Re-decode `drive_2026-08-28.csv` with the correct channel map.
- **newtiburon.com is readable and mined (2026-09-08).** The forum sits behind a
  plain proof-of-work interstitial, not a real bot wall; `tools/newtiburon/fetch.py`
  (Playwright Chromium) dumps threads. TollBit (`tools/Tollbit/`) is abandoned.
  ~110 threads and a 21k-title index are in `reference/newtiburon/`; the digest is
  [[forum-digest-newtiburon]]. Net: chase's NA reflash recipe is public (advance for
  98 RON, WOT AFR 12.5:1, open-loop TPS threshold 50 %, limiter ~7300), the OpenGK
  group ships a "crackle" option and a "ghost IACV restrictor" rev-hang patch that
  overlap our [[puc-overrun-map]] work — ask chase what they edit before flashing
  the program patch. Blower market: MP62 kits only, stage 0/1 on the OEM tune, stage
  2 needs a reflash we can now write ourselves.

One session with the cable, no driving:

- **Cooling fan map** (`0xCB58`) vs `Engine Cooling Fan PWM` — stationary.
- **Idle speed tables** (B936 / BA5A / BA82 / C694) vs `Target Idle Speed` — one
  cold start covers the whole coolant axis.

Both bank a table family each and need nothing but an idling engine.

---

## Decisions pending (not technical)

- **The pop & bang tune itself** is gated on the capture run, and now on the
  program-zone patch in [[program-zone-plan]] §4 — a cal-only version cannot be
  rpm-windowed ([[puc-overrun-map]] code-verified §4).
- **The fork.** `https://github.com/megawillbot/opengk-simk`, branch
  `derived-symbol-maps`, is **committed locally and not pushed**. Push is a
  one-liner when wanted.
- **Whether to offer any of it upstream.** Nothing has been proposed to the OpenGK
  maintainers. The stronger opening is "here is a method and its validation, does
  this look sound?" rather than a large diff.
- **Sequencing vs the supercharger.** Overrun airflow changes completely under
  boost, so any overrun work either waits or gets redone.

## From the 2026-09-08 drive log (`log_raw_2026-09-08_1134.csv`) — added 2026-09-08

- **Per-cylinder ignition divergence under load.** The six ignition bytes
  (37-42) are equal on overrun/idle/cruise but split by 9-19 counts (3-7 deg)
  on individual cylinders during the WOT pull (t=203-205 s, cyl 5 and 6 most)
  and by a steady ~12 counts at part throttle (TPS 150-160, 2300 rpm). This is
  knock control (live retard and/or the per-cylinder adaptive maps in the
  `0x48000` shadow) actively pulling timing on today's fuel. **Implication: no
  ignition headroom to add; the question is why it pulls.** Check fuel grade,
  IAT, and whether the pattern is stable across drives (adaptive) or eventful
  (live knock).
- **Load byte (pos 8) sits flat at 203 from 2500 to 5300 rpm at WOT.** 203 ×
  2.71 = 550 mg/stroke = `C_MAF_MAX` (`0x81B8`, raw 101 × 5.447). So pos 8 is
  load in ~2.7 mg/stroke units and the NA engine already reaches the clamp at
  WOT — every WOT lookup above 2500 rpm uses the clamped load, and the only
  rpm-resolved WOT fuelling is `IP_TI_FL__N`. Confirms the clamp is the first
  thing to move for the blower, and that NA WOT AFR work needs a wideband.

## Pop-on-upshift (idea, 2026-09-19)

Owner wants an Audi-style soft pop on automatic upshifts. The ECU already has a
gear-shift torque-reduction path: `IP_IGA_DIF_MAX_TQR_GS__N_32__MAF` (cal
`0xA0C0`, 8x8, up to 107 = 40 deg of retard allowed during a shift; lookup at
`0x3020A`), the request-to-efficiency curves `IP_FAC_IGA_TQR` (`0x9E27`) /
`IP_FAC_TQR` (`0x9FCA`), `C_TCO_MAX_IGA_GS` (`0x82DE` = 254, always allowed) and
a **single-cylinder cut during gear shift that is disabled by temperature**
(`C_TCO_MIN_SCC_GS` `0x82EF` = 254 -> 142 C). Not yet known: whether/how hard
the TCU requests torque reduction on this car, how long the event lasts, what
the SCC_GS pattern is. First step = a fast (>=5 Hz) RAM log of the final
ignition angle + the torque-request cells through a few part- and full-throttle
upshifts, then trace `0x301FE`-`0x3020A` and the SCC_GS code. Levers, in order:
deeper GS retard (curve/limit), then enabling SCC_GS (cut cylinders pump air
while the rest burn late = the pops recipe, on throttle, with real charge).
More torque reduction is gearbox-friendly; heat is brief.

### First measurement, 2026-09-19 21:50 (`log_shift_2026-09-19_215054.csv`, 3 Hz, 356 s, `tools/ram_logger.py shift`)

- `[0xC592]` is **not a timer** (first reading of `0x301BC` was wrong): at
  `0x30550`-`0x30568` it is loaded as `0x100 - f([0xC584])` while `M_FD26.2`
  (gear shift in progress, from the TCU) is set = the **gear-shift torque
  reduction request**; `[0xC591]` is the sibling request, `[0xC597]` =
  max(requests, `[0xC1B0]`) = the value that goes on to the ignition path.
- Seen non-zero twice: **82** (~32 %) in the sample right at a full-throttle
  6464 rpm upshift, and **78** at ~930 rpm (t=257 s, during the owner's
  manual-gate shifts / low-speed gear engagement). ~14 part-throttle upshift
  candidates (rpm steps at steady spark) showed **no** request and no spark dip
  (22-31 deg BTDC throughout), so the TCU asks for reduction only on hard
  shifts, or for < 0.3 s.
- The one WOT shift was followed immediately by a lift (pops cut), so the depth
  and duration of the stock retard are still unmeasured. Next: a single-block
  fast log (`0xC584..0xC59F` alone is ~5 Hz) over several full-throttle upshifts
  held through the shift, final angle from a second pass.

## Knock retard is readable from the `drive` log — first table, 2026-09-19 (91 RON)

No new RAM cells needed. In the `0xC320` block: `[0xC335]` = base angle X,
`[0xC337]` = X after the global correction (`[0xC332]` − 128), and the final
per-cylinder bytes `[0xC325..2A]` are `255 − X_cyl`. So **per-cylinder retard =
`([0xC325+i] − (255 − [0xC337])) × 0.375` deg**. Steps arrive as ~9 counts
(3.4 deg) on one cylinder and decay 1-2 counts per sample = knock control.
A uniform offset on all six (seen at part load, 2000-2500 rpm) may be another
global term, not knock; only the per-cylinder differences are certain.

Evening drives 2026-09-19 (`log_drive_2026-09-19_2*.csv`, 1 Hz, owner on
**91 RON**, stock WOT ignition columns), load byte >= 190:

| rpm | n | base deg | mean retard | max |
|---|---|---|---|---|
| 2500-2999 | 1 | 26.2 | 4.3 | 7.1 |
| 3000-3499 | 3 | 24.6 | 3.9 | 7.5 |
| 3500-3999 | 3 | 18.5 | 3.2 | 6.4 |
| 4000-4499 | 2 | 18.6 | 3.4 | 6.0 |
| 4500-4999 | 1 | 20.2 | 1.6 | 3.4 |
| 5500-5999 | 2 | 24.8 | 1.3 | 4.5 |
| 6500+ | 2 | 29.2 | 1.2 | 3.8 |

Too few samples to cut a map from (1-3 per bin). Next: held-gear WOT pulls
2500-6000 with a fast single-block log (`0xC320` alone, ~5 Hz) + rpm from
`[0xC59E]`; then a 91 RON map = WOT columns minus the measured mean + ~1 deg,
mostly 2500-4500 rpm. See [[car-notes]] (fuel) .
