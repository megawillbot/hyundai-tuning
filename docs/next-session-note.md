# Note for the next session

Written **2026-09-03**, end of the review-and-correct session (Fable 5.1).
Previous note's content is folded in; the docs it pointed at are still the
entry points.

## Start here
- [[closed-throttle-recognition]] — **new 2026-09-03**: how the ECU decides
  the pedal is off (learned closed position, `C_TPS_IS` = 3-count window) and
  why the road lift produced no cut (TPS reading bistable 31-36 / 47-51 —
  sensor, not the restrictor plate). Sensor check before the next capture.
- [[program-zone-plan]] — the plan for the first program-zone flash, and the
  prepared (unflashed) candidate in `roms/tunes/puc-final-stage-patch/`.
- [[puc-overrun-map]] — read the **code-verified section at the top**; the
  older structural inference below it is kept for history and partly retracted.
- [[diagnostics-and-levers]] §1 — the monitor table was wrong for ~a third of
  its rows and is now code-paired. `docs/ca654019-constants-map.csv` and the
  extended XDF carry the corrected `C_ABC_INC_*` names.
- [[ecu-architecture]] §5f — engine-state machine; `M_FD14.12` = idle.
- Tooling: `tools/c166/`. `SCRATCH=<dir> python tools/c166/tables.py` writes
  `table_geometry.csv` (not `.json`). A full linear listing is
  `python tools/c166/c166dis.py <bin> 10000 4A6A6 > full.lst`; grep it.

## Facts established this session (all verified against the binaries)
- Program read, DPP model, limiter bytes, sibling-dump identity, 464-table
  scan, little-endian XDF flag: all re-checked and hold.
- Maturation routine: bit 0x20 is *test complete* (set on pass too), so
  `C_ABC_INC=0` "stops the DTC", not "nothing happens".
- Overrun cut: staged 1 → 4 → 6 cylinders via a pattern table at cal `0xB848`;
  final stage hard-coded in the program; PUC ignition tables are relative
  (`0.375×(X−128)` deg); no cal-only rpm window exists.
- Program checksum = 4 chained zones, verified with GKFlasher on
  `roms/stock/FULL_ca654019_stock_merged.bin`.
- `.venv` was dead (base interpreter gone); rebuilt 2026-09-03 from
  `C:\Users\megaw\AppData\Local\Programs\Python\Python313` (the old
  `C:\Python313` install is gone — use `py -3.13` if it breaks again).
- Ghost cams: several days, no CEL.

## Added 2026-09-07
- Engine states 3/4 relabelled (3 = throttle open, 4 = closed-throttle coast
  without cut). Cal-only **burble** image built, unflashed:
  `roms/tunes/burble/` (cal-only file, `--flash-calibration` only) — reviewed by a
  second agent, **flashed 2026-09-08**, verified by read-back, first-drive log
  analysed in its notes.md. Cut disabled and retard engaging: confirmed. In this
  auto a lift drops rpm to ~1400 within a second, so the mild 1200/1600 rows are
  what the ear hears. **v2 (rows 58/32/32/32) flashed the same day**, verified.
  Running calibration as of 2026-09-08 evening: ghost cams + burble v2.
- `tools/raw_logger.py` now reconnects after a K-line timeout (was dying at the
  first one); it writes a new csv per reconnect.

## Next steps, in order
0. **TPS replacement first** (decided 2026-09-03). Owner is sourcing from two
   G6BA Tucsons (2005/06, ~200,000 km) at a wrecker — bench-sweep the donor
   sensor for dropouts before pulling; whole throttle body preferred. After the
   swap: battery disconnect (clears the learned closed position), warm idle,
   confirm log byte 11 steady in the low 30s and byte 28 = 0. Then the
   driveway free-rev cut test, then the road capture. See
   [[closed-throttle-recognition]].
1. **Capture run** ([[next-capture-script]]) — unchanged, still the gate; the
   staged-cut prediction is now specific (one injector, then four, then six).
2. **Ask chase / OpenGK** whether `--flash-program` has been done on a 5WY17
   over K-line ([[program-zone-plan]] §2). Also worth showing him the INC/MAX
   code-pairing check — same idea as the fuel-map auto-derive he liked.
3. If both are good: flash the candidate (cal first, then program), read back,
   confirm no behaviour change; then the cal-only pop tune on top.
4. Run the code-pairing trick over the other paired constant families before
   trusting their names ([[open-threads]]).
5. Scaling equations for the remaining tables — still the largest unverified
   area; the PUC ignition case shows the per-table decode read is tractable.

Full open list: [[open-threads]].

## Added 2026-09-18 — paddock pops & bangs for Sunday 2026-09-20

`roms/tunes/paddock-pops/` (built, **unflashed**, checksums verified): the
reviewed program patch + burble v2 cal, with the cut resume raised to 3008 rpm
so the three-cylinder pop pattern (-42 deg on the firing cylinders) runs above
3008 and burble v2 runs below it. `notes.md` there has the Saturday runbook
(Test 0 -> rehearsal cal -> rehearsal program -> pops cal, `check.py` after
every read-back) and the cal-only revert for after the event. This would be the
first program-zone flash on this ECU; the 2026-09-03 question to chase / OpenGK
about K-line `--flash-program` on a 5WY17 has no recorded reply.


## Added 2026-09-18 (evening) — paddock pops flashed, no pop, TPS is the blocker

The paddock pops tune (`roms/tunes/paddock-pops/`) was **flashed and verified**
this evening — program patch first (Test 0 → rehearsal cal → rehearsal program →
pops cal, all read-back-matched). This is the **first program-zone flash on this
ECU**; GKFlasher's stock `--flash-program` sends a wrong download address
(segment 7, bootloader wants 9) and left the program erased on the first try —
fixed locally in `tools/GKFlasher/gkflasher.py`, root cause and recovery in
[[program-zone-plan]] §2/§2e.

Test drive: **no pop.** The fuel cut never engaged (no injector cut in 957 s,
incl. a first-gear foot-off pull). Root cause = closed-throttle recognition: the
state-4→5 gate `M_FD46.0` is the `C_TPS_IS`=3 test, and the drifted TPS never
reads within 3 counts of closed on a lift. Same reason the cut has never been
seen on this car. Full analysis and next steps in
`roms/tunes/paddock-pops/notes.md`.

**Next (2026-09-19):** owner fits a new TPS, battery-disconnect, then retest the
pops tune as-is (procedure in the notes). No reflash needed — the pops tune is on
the car and inert until the TPS reads closed.
## Added 2026-09-19 — TPS saga resolved, pops working, final event cal on the car

Read `roms/tunes/paddock-pops-tpsceil/notes.md` (chronological, the whole day)
and [[closed-throttle-recognition]] (2026-09-19 sections). Short version:
- **Logger pos 11 is not the TPS** and byte 28 is not the idle flag; every
  "bistable sensor" conclusion was wrong. Real cells via `tools/ram_logger.py`
  (modes: default TPS, `puc`, `iga`, `drive`, `shift`).
- The new TPS was **mis-clocked** on fitting (closed 135, railed 255 -> P0123 at
  WOT); re-seated the same evening: closed 13 / open 214, no faults.
- Two more gates found between "closed throttle" and a cut: the dashpot wait
  (`M_FD64.0`, bypassed with `C_N_MIN_DHP` = 255) and the 22-cycle entry stages.
  Ignition encodings settled (X -> 0.375X - 23.625; logger 37-42 = 255 - X).
- **Cal on the car: `..._paddock_pops_instant`** (verified 22:05, not yet
  road-tested). Event Sunday 2026-09-20; then revert cal-only to burble v2.
- Next project: pop-on-upshift ([[open-threads]]).
- Nothing from 2026-09-18/19 is committed to git yet.

## Added 2026-09-21 — after the grasskhana: daily tune with the event setup behind the latch, NZ 91 timing

`roms/tunes/daily-latch-91/` (**flashed 2026-09-21, cal + program verified by read-back**; notes.md there has the design,
knock evidence and runbook). Unarmed = stock overrun behaviour + ghost cams + a
91 RON cut on `IP_IGAB__N__MAF`; one rev past 6016 rpm arms the whole
2026-09-20 event setup until rpm next drops below 896. Needs **cal then
program**: 11 latch-switch stubs (205 program bytes; arm byte moved to `0xBC93` so older cals can never arm it) redirect each event-modified
table/constant to an alternate copy in free cal `0xBC94`-`0xBDB9` while
`M_FD40.15` is set. Not yet road-tested; first-drive checks and the knock follow-up log are in its notes.md.
