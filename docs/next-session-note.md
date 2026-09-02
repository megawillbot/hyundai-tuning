# Note for the next session

Written **2026-09-04**, end of the disassembly session.

## Start here
- The program zone **is readable** — `roms/stock/PROGRAM_ca654019_read_2026-08-29.bin`
  is a valid, complete dump (the "failed read" was a myth). Everything below came
  from disassembling it. See [[ecu-architecture]] §1.
- New this session, all committed on `master` (not pushed):
  [[ecu-architecture]] (address model, table library, KWP layer, adaptation),
  [[code-derived-tables]] (464 tables from code; 152 in no other def; EGT +
  warmup clusters identified), [[diagnostics-and-levers]] (the tuner reference).
- Tooling is in `tools/c166/` (our own C166 disassembler). Run e.g.
  `SCRATCH=<dir> python tools/c166/tables.py`.

## Two things I got wrong and corrected (don't reintroduce)
1. **"The main fuel map was missing from the shipped def"** — wrong. `0xD3A8`/
   `0xD528` were always in the hand-made `ca654019 2700.xdf` (with real `0.004*X`
   scaling). The code scan only *confirms* them. Use the hand-made def for named
   maps.
2. **Diagnostics "one common routine"** — there are two (`0x9E128` main,
   `0x9E934` lambda/VIM). The `C_ABC_INC=0` disable lever still holds for both.

## Gotcha
- When emitting 16-bit tables to XDF, **set `mmedtypeflags="0x02"`** (little-
  endian) or TunerPro reads every cell byte-swapped. `emit_xdf.py` does this now.

## Best next steps (none are blockers)
- **Live ReadDTC (KWP 0x18)** over the cable → the one clean way to get real OBD
  P-codes for the monitors in [[diagnostics-and-levers]] §1. Static analysis
  didn't resolve them (descriptor chain through the `0x48000` RAM shadow).
- **Scaling equations** — still the biggest unverified thing; needs the per-table
  decode routines read, not just the lookup library.
- `M_FD14.12` — the selector between the two fuel maps (start vs main?).
- The `0x4000` NVM area — looks like a sequence-numbered fault/freeze-frame log;
  worth a real read (it's inside the program-read range).

Full open list: [[open-threads]].
