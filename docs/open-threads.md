# Open threads

Index of everything unresolved, and what would resolve it. Written **2026-09-03**,
top section rewritten **2026-09-04**.
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
| **`M_FD14.12`** — selector between main fuel `0xD3A8` and alternate `0xD528` | Trace its writers; or datalog cold-start vs warm |
| ~~Is `0x48000` external RAM (live cal shadow)?~~ | **Resolved 2026-09-04** — external SRAM shadow of the cal, header-validated against flash. Base maps read from **flash**, so not a live-tuning lever; but the **adaptive/knock learning system lives there** (pointer tables at cal `0x9F1A`/`26`/`32`, per-cylinder loop). See [[ecu-architecture]] §5c |
| **Security Access (0x27) seed/key** | Handler at file `0x4219E`, per-subfunction param table; the compute path past the `0x3812` memcpy is not yet read. The legitimate full-unlock path for an owned ECU |
| The `0x4000` NVM record format (fault log?) | A real read of file `0x4000`-`0x5000` from our car (it is inside program-read range) |
| Scanner's linear axis tracking | Backward-CFG walk in `tools/c166/tables.py` |
| ~240 diagnostic tables named | A second same-family named def, or per-table decode |

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
| Semantics of the two `PAT_INH_IV_PUC` masks (3-of-6 or 6-of-6?) | Per-cylinder injection times during a real fuel cut |
| Absolute ignition datum for the PUC tables | ADX `Ignition Angle Idle/Decel` on a coastdown |
| Are the six tables sharing `sstm_n_3_4` rpm-flat? | Desk check, not yet done |
| Nine unresolved PUC tables | More anchors |
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

One session with the cable, no driving:

- **Cooling fan map** (`0xCB58`) vs `Engine Cooling Fan PWM` — stationary.
- **Idle speed tables** (B936 / BA5A / BA82 / C694) vs `Target Idle Speed` — one
  cold start covers the whole coolant axis.

Both bank a table family each and need nothing but an idling engine.

---

## Decisions pending (not technical)

- **The pop & bang tune itself** is gated on the capture run. If injectors never cut,
  the route is dead — see the pass/fail table in [[next-capture-script]].
- **The fork.** `https://github.com/megawillbot/opengk-simk`, branch
  `derived-symbol-maps`, is **committed locally and not pushed**. Push is a
  one-liner when wanted.
- **Whether to offer any of it upstream.** Nothing has been proposed to the OpenGK
  maintainers. The stronger opening is "here is a method and its validation, does
  this look sound?" rather than a large diff.
- **Sequencing vs the supercharger.** Overrun airflow changes completely under
  boost, so any overrun work either waits or gets redone.
