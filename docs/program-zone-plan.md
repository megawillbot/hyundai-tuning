# Program-zone work — plan

Written **2026-09-03**. Everything the calibration cannot do lives in the
program zone: the hard-coded "all six injectors" final stage of the overrun cut,
the SecurityAccess seed/key, the rev-limit clamp chain, launch/2-step, and so on.
This is the plan for touching it safely. **Nothing in the program zone has been
flashed yet.** The first candidate is built and verified offline
(`roms/tunes/puc-final-stage-patch/`).

## 1. What is established

| fact | evidence |
|---|---|
| Program image = file `0x10000`–`0x4A6A6` (physical `0x90000`–`0xCA6A6`), identical to three OpenGK dumps | [[ecu-architecture]] §1 |
| **Checksum: four chained CRC-16 zones**, header at file `0x10010`, init at `0x10052`: `0x10210`–`0x1FFFC`, `0x20000`–`0x30000`, `0x30000`–`0x40000`, `0x40000`–`0x4A6A6` | GKFlasher `--correct-checksum` on `roms/stock/FULL_ca654019_stock_merged.bin` reports current == computed (`0x2ef1`) for Program and Calibration |
| GKFlasher's `v6 (5WY17)` checksum type covers Boot (skipped, we never read it), Calibration and Program | `flasher/checksum.py` |
| **Free space inside the checksummed zones:** `0x10FFE`–`0x11F02` (3844 bytes, zone 1), `0x100EA` (294 bytes), `0x12D94` (366 bytes, right after the KWP jump table — avoid) | scan of FF runs in the code region |
| Free space **outside** the zones: `0x4A6A6`–`0x80000` (erased flash) — flashable, but unverified by the checksum; don't use it | zone table |
| `--flash-program` exists in GKFlasher: routine `0x00` erase, `RequestDownload`, `TransferData` in 254-byte packets from `program.write.address + 16` to the last non-FF byte, then routine `0x02` verify/mark-executable | `gkflasher.py` `cli_flash_eeprom`, `flasher/memory.py` |
| The Boot region (`0x0000`–`0x8000`, bootloader) is **not** written by either flash path | same |
| Program-zone flashing needs only the Hyundai-level security access GKFlasher already does for the cal. The IOCLID escalation is for *reading* the boot/NVM areas | [[car-notes]] |

## 2. How the bootloader actually writes — the "offset math" question

Three OpenGK dumps carry the boot region (`ca654019_E5N7SB1B` and the two
`ca65402x` files, bootloader `KR77035402`; the EU car has `KR77035401`). Ours
reports `KR77035202`, a different revision we have never read, so the reading
below is **from a sibling bootloader**, disassembled from the EF Sonata dump at
file `0x0000`–`0x4000`. The mechanism is unlikely to differ in shape.

- **The flash write pointer is set by the erase routine, not by the download
  address.** The `StartRoutine` handler (boot `0x146E`) sets the internal
  pointer `[0xF30C]:[0xF30E]` to a **constant**: routine `0x00` → physical
  `0x09:0010` (program, 16 bytes past the start), routine `0x01` → `0x08:8000`
  (calibration). `TransferData` (boot `0x2DEC`) writes each packet at that
  pointer and advances it. Nothing in the bootloader assembles a 24-bit address
  from a request (no `SHL #8`/`#16` sites at all).
- So **GKFlasher's `RequestDownload` address is ignored** on this family. That is
  why the "magic" calibration formulas in its history (`(offset-0x7000)<<4`,
  then `(0x80000<<4)+offset`) all worked, and why the odd program value
  (`write.size + 16` = `0x70010`) is harmless. The `+16` in GKFlasher's payload
  start matches the ECU's own `0x90010` starting point.
- **Range classifier** (boot `0x2FC2`): pointer and pointer+length must stay in
  one zone — program `0x090010`–`0x0FFFFF`, calibration `0x088000`–`0x08DFEF`,
  NVM `0x083E00`+ — with the 16-byte flag windows `0x08DFF0`–`0x08DFFF` and
  `0x090000`–`0x09000F` explicitly rejected. The download *length* therefore
  matters: GKFlasher sends the payload length to the last non-FF byte, which
  fits.
- **The flags GKFlasher cannot write are written by the ECU itself.** After the
  verify routine (`0x02`) the bootloader writes 4 bytes at `0x08DFF0` (cal) or
  `0x090000` (program) (boot `0x2C1C`/`0x2C88`) — the "this zone is valid" marker.
  A failed verify leaves the flag unwritten, the ECU boots into the bootloader
  again, and a fresh flash fixes it. That is the whole basis of GKFlasher's
  "soft-bricked, flash a valid file" message, and it is structural, not luck.
- Program-zone flashing needs only the Hyundai-level security access GKFlasher
  already performs for the cal. The bootloader's own key table sits at boot
  `0x3E1A`; the IOCLID escalation is for *reading* boot/NVM, not for writing.

Still not established:

1. That `KR77035202` behaves like `KR77035402` here. Almost certainly, but the
   one way to remove "almost" is someone who has done `--flash-program` on a
   5WY17 — **ask chase / OpenGK**.
2. Whether verify routine `0x02` checks anything beyond the four checksum zones.
   Irrelevant while patches stay inside them, which is the rule.

## 2b. Runbook for the first program flash

Battery on a charger, laptop on mains, both stock images at hand. Everything
below is from `tools\GKFlasher` with `$env:PYTHONUTF8=1` and the venv python.

```powershell
# 0. identity + fresh backups of what is on the car right now
python -u gkflasher.py --protocol kline --interface COM7 --id
python -u gkflasher.py --protocol kline --interface COM7 --read-calibration -o ..\..\roms\stock\cal_before_program_flash.bin
python -u gkflasher.py --protocol kline --interface COM7 --read-program     -o ..\..\roms\stock\program_before_program_flash.bin
#    cal must hash 65DA7B7F… (ghost cams), program code region d024e1d1… (stock)

# 1. calibration first (adds the unused PUC_3 table; stock program ignores it)
python -u gkflasher.py --protocol kline --interface COM7 --flash-calibration ..\..\roms\tunes\puc-final-stage-patch\FULL_ca654019_ghostcam_pucstage_UNFLASHED.bin
python -u gkflasher.py --protocol kline --interface COM7 --read-calibration -o ..\..\roms\tunes\puc-final-stage-patch\readback_cal.bin
#    cal zone must hash e4638e99bf2b30d6…

# 2. program (the real step). Ignition on, engine off, do not touch anything until it says Done.
python -u gkflasher.py --protocol kline --interface COM7 --flash-program ..\..\roms\tunes\puc-final-stage-patch\FULL_ca654019_ghostcam_pucstage_UNFLASHED.bin
python -u gkflasher.py --protocol kline --interface COM7 --read-program -o ..\..\roms\tunes\puc-final-stage-patch\readback_program.bin
#    file 0x10000-0x4A6A6 must equal the candidate's (50 bytes differ from stock, listed in notes.md)

# 3. if step 2 fails at verify: power-cycle the ECM (ignition off 20 s), re-run step 2
#    with the same file; if it fails twice, flash roms\stock\FULL_ca654019_stock_merged.bin
#    --flash-program to go back to stock program (the cal with PUC_3 is harmless).
```

Then start, idle, short drive with the logger running: behaviour must be
indistinguishable from today. Only after that, the cal-only pop tune.

## 3. Toolchain and rules for a patch

- **No assembler.** Stubs are hand-encoded from instruction forms already present
  in the listing (every opcode used so far has a byte-identical twin in the stock
  code) and **verified by disassembling the patched file** with
  `tools/c166/c166dis.py`. Keep stubs tiny; if a patch needs more than a few
  dozen bytes, write the assembler first.
- **Place stubs in the zone-1 padding at `0x11000`+.** Segment `0x09`, so a
  stub at file `0x11000` is `CALLS 0x09, 0x1000`.
- **Preserve every entry point** into a patched block (jump-table targets,
  branch targets from elsewhere). Find them by grepping the listing for the
  address before overwriting.
- **Mirror stock call sequences** for library routines (axis search →
  lookup) so register/RAM-scratch conventions are exactly what the stock code
  already relies on.
- **Account for every differing byte** against
  `roms/stock/FULL_ca654019_stock_merged.bin` before flashing; the count must
  equal checksum bytes + stub + patch.
- `--correct-checksum` the full image, then re-run it answering `n` and confirm
  both regions report current == new.
- Cal changes a patch depends on are flashed **first**, so a failed program
  flash leaves a stock program on a cal it ignores — never a patched program
  looking at a table that is still `FF`.
- Read back both zones after flashing (`--read-program`, `--read-calibration`)
  and compare to the candidate byte-for-byte before starting the engine.

## 4. Patch 1 — latched, rpm-windowed overrun pattern (prepared)

Why: the stock cut sequence is `ID_PAT_INH_IV_PUC_1` (rpm-indexed) for 11
cycles, then `ID_PAT_INH_IV_PUC_2` for 11, then a **hard-coded pattern index
`0x0D`** = all six injectors until fuel resumes. The rpm-indexed stages are far
too short to matter; the steady state is the only stage that can carry an rpm
window, and it is not in the calibration. Full mechanism in [[puc-overrun-map]].

What (two stubs, 89 program bytes, two new cal bytes):

- **Stub B** (`0x11000`): the final stage reads a new table
  `ID_PAT_INH_IV_PUC_3__N_32` at cal `0xBC8B` on the existing `0x8757` rpm/32
  axis — but only while a **latch bit** is set; otherwise the stock `0x0D`.
- **Stub A** (`0x11040`), hooked at the entry of the injector-inhibit task
  (`0x144BA`): clears the latch while cranking, sets it once rpm/32 reaches
  `C_N_ARM_POP` (cal `0xBC91`). So pops are only possible after a deliberate
  excursion past the arm rpm, and every start disarms them — the "latching"
  behaviour, without depending on how RAM is initialised.
- Latch bit `M_FD40.15`: unreferenced anywhere in the stock program (the word
  has no whole-word or bitfield access). The hooked task runs in every engine
  state except 0 (stopped), so the crank-clear always executes.

Two images in `roms/tunes/puc-final-stage-patch/` (`notes.md` has the byte
accounting): a **rehearsal** whose new cal bytes are inert (`0x0D` pattern, arm
never) — behaviourally identical to the car today — and a **pop tune** that
differs from it by six cal bytes: arm at 4000 rpm, active above 3008 rpm,
pattern 6 (three injectors cut, uneven), −33° in the 3500 cell of
`IP_IGA_PUC_AT`.

## 5. Sequence

1. **Capture run** ([[next-capture-script]]). Still the gate. It validates the
   overrun model on hardware and now has a sharper prediction: on a warm 4000+
   lift, per-cylinder injection (logger pos 43–54) drops **one cylinder first,
   then four, then all six** within a few engine cycles, and returns at ~1248 rpm.
   Which injector drops first is the bit-to-cylinder order for the pattern table.
2. **Confirm the flash path** with chase / OpenGK (§2: the bootloader ignores the
   download address and fixes the write pointer itself, so the only open point
   is the `KR77035202` revision). Asked 2026-09-03, awaiting reply.
3. Battery on a charger, laptop on mains, stock merged image and the ghost-cam
   cal at hand. Flash the **rehearsal** image **cal first, then program** (§2b
   runbook), read both back, compare, start, idle, drive — behaviour must be
   indistinguishable from today.
4. Flash the **pop-tune** cal (`--flash-calibration` only), read back, drive:
   rev past 4000 once, then lift from above 3000. Adjust to taste via three cal
   bytes (`0xBC91` arm, `0x875C` window, `0xBC90` pattern; `0xA19B` retard).
5. One change at a time, datalog each, commit each bin.

## 6. Later program-zone candidates (not started)

- **SecurityAccess seed→key** (handler `0x4219E`): would give native
  ReadMemByAddress / WriteMemByAddress and a way to read the `0x48000` adaptive
  shadow live. Reading the algorithm out is bounded work; nothing to flash.
- **Rev-limit clamp chain** (`0x1319E`): raising `C_N_MAX` may be enough; if a
  lower cap in the chain bites, that is a patch.
- **Overrun-cut entry conditions** (`0x1C3CE`+): an rpm *upper* bound for the
  cut (fuel on above X) would be a 10-byte patch if the pattern approach in §4
  turns out not to give the sound wanted.
- **2-step / launch**: `C_N_FCUT` / `C_N_MAX_FCUT` (cal) first; only if a
  clutch/brake-conditioned variant is wanted.

## 7. Risks, plainly

- First program flash on this ECU with this tool: the only step in the whole
  project with a non-trivial brick risk. Mitigate with §2 and §3; accept that the
  fallback is a bench BSL session.
- Ghost cams is on the car; the candidate carries it forward unchanged. If the
  ghost-cam cal is ever reverted, rebuild the candidate on the new base.
- Pops on a 4×O2 car with the cat in the front manifold: thermal risk is real
  and the cat-protection model cannot see it ([[full-map-ca654019]] §6). Keep
  windows short and high-rpm only; that is the point of the rpm gate.
