# puc-final-stage-patch — candidate, NOT FLASHED

Built **2026-09-03**. Full 512 KiB image = stock program zone + the **ghost-cam
calibration currently on the car** + two changes. Design and rationale in
[[program-zone-plan]] and [[puc-overrun-map]].

| file | what |
|---|---|
| `FULL_ca654019_ghostcam_pucstage_UNFLASHED.bin` | checksum-corrected candidate (both regions verified with `--correct-checksum`, answer `n`) |

SHA256 (full file) `d5409cd55050c6a9…`, cal zone `e4638e99bf2b30d6…`.

## What changed vs the on-car state

**Program zone — 50 bytes differ from stock** (`roms/stock/FULL_ca654019_stock_merged.bin`):

- `0x10010`–`0x10011`: program checksum (`2e f1` → `d5 10`).
- `0x11000`–`0x11019`: a 26-byte stub in the padding gap inside checksum zone 1:
  ```
  MOV R12,#0x0756 ; MOVBZ R13,[0xC59E] ; CALLS 0x0C,0x4AE4   ; rpm/32 axis search on 0x8757
  MOV R12,#0x3C8B ; CALLS 0x0C,0x4B54                        ; stepped 1-D lookup of cal 0xBC8B
  MOVB [0xC1AB],RL4 ; RETS                                   ; -> injector pattern index
  ```
- `0x14574`–`0x14593`: the overrun-cut state-4 handler. Stock hard-codes pattern
  index `0x0D` (all six injectors). Patched: keeps `BSET M_FD16.12`, sets state
  4, `CALLS 0x09,0x1000` (the stub), applies via `CALLS 0x09,0x4436`, jumps to the
  common exit exactly as stock did. Both stock entry points (`0x14574` from the
  state jump table, `0x14580` from the `>4` reset) are preserved.

**Calibration — 8 bytes differ from the ghost-cam bin:**

- `0xBC8B`–`0xBC90`: new table `ID_PAT_INH_IV_PUC_3__N_32` = `0D 0D 0D 0D 0D 0D`
  in a previously all-FF hole that no def and no code operand references.
- `0xDEE0`–`0xDEE1`: cal checksum.

With the table all `0x0D` the candidate is **behaviourally identical to the
current car** — a rehearsal of the program-flash path with zero functional
change. The pop tune is a later cal-only edit on top (see the plan).

## Flash order, if/when it is flashed

1. `--flash-calibration` this file first (adds an unused table; stock program
   ignores it). Verify by reading back.
2. `--flash-program` this file. If the program flash fails, the car is on a
   stock program + a cal with one unused table — nothing depends on the stub.
3. Never the other way round: a patched program with the table still `FF`
   would index the pattern table with `0xFF`.

Not to be flashed before the capture run in [[next-capture-script]] has shown
the stock cut engaging (prediction A) — that is what validates the model this
patch is built on.
