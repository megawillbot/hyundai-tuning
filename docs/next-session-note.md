# Note for the next session

Written **2026-09-03**, end of the review-and-correct session (Fable 5.1).
Previous note's content is folded in; the docs it pointed at are still the
entry points.

## Start here
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
- `.venv` was dead (base interpreter gone); rebuilt from `C:\Python313`.
- Ghost cams: several days, no CEL.

## Next steps, in order
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
