# Program-zone work — plan

Written **2026-09-03**. Everything the calibration cannot do lives in the
program zone: the hard-coded "all six injectors" final stage of the overrun cut,
the SecurityAccess seed/key, the rev-limit clamp chain, launch/2-step, and so on.
This is the plan for touching it safely. **Test 0 (byte-identical stock program)
was flashed over K-line on 2026-09-18** — see §2e for what it took. The first
patch candidate is built and verified offline (`roms/tunes/puc-final-stage-patch/`,
carried into `roms/tunes/paddock-pops/`).

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
- ~~So **GKFlasher's `RequestDownload` address is ignored** on this family.~~
  **Wrong — corrected 2026-09-18 after Test 0 failed with `0x40 download not
  accepted`.** The write *pointer* is fixed by the erase routine, but the
  `RequestDownload` handler (boot `0x0F42`+) still parses the request: the top
  address byte is masked `AND 0x1F` into `[0xF30E]` (segment), the other two
  bytes into `[0xF30D]/[0xF30C]`, the 3-byte length into `[0xF310]`-`[0xF312]`,
  the format byte must be 0, and the check routine `0x2D2C` runs the range
  classifier over exactly those values: segment 9 with offset ≥ `0x0010` for the
  program, segment 8 for the calibration. GKFlasher's calibration address
  `(0x80000<<4)+0x88000` = `0x888000` masks to `08:8000` — that is why it always
  worked — but its program address `write.size + 16` = `0x070010` masks to
  segment 7 and is rejected. Upstream GKFlasher has the same line (checked
  against `origin` the same day), so `--flash-program` had never worked on this
  family over K-line. **Local fix** in `tools/GKFlasher/gkflasher.py` (the
  directory is gitignored, so the diff is recorded here):

  ```diff
  -		flash_start = ecu.get_region('program').write.size + 16
  +		# same addressing as the calibration path: ECU-style address of the zone, +16 past the flag window
  +		flash_start = ecu.calculate_memory_write_offset(ecu.get_region('program').write.address) + 16
  ```

  i.e. `0x890010`, which masks to `09:0010`. With it the stock program flashed
  and verified on 2026-09-18 (see §2e).
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
   5WY17 over K-line. **chase's own car does not answer this** (checked
   2026-09-03): his writeup car is a **2006 GK 2.7 = 5WY18 v2** (ca654024/025),
   and his documented method is **bench flashing** — chip desolder + Willem
   GQ-4X — not the K-line bootloader path at all. So his experience covers
   neither our revision nor our flash channel. Still worth asking whether anyone
   in OpenGK has K-line `--flash-program`'d a 5WY17; until then this remains the
   one genuinely open item.
2. Whether verify routine `0x02` checks anything beyond the four checksum zones.
   Irrelevant while patches stay inside them, which is the rule.

**Bench flash is the documented fallback.** chase's chip-pull + Willem GQ-4X
method writes the whole 4Mbit AM29F400 regardless of the K-line bootloader, so
even if a K-line `--flash-program` on this 5WY17 fails in a way KWP recovery
can't fix, the recovery of last resort — desolder, write
`roms/stock/FULL_ca654019_stock_merged.bin`, resolder — is a known, documented
procedure, not a hope. That bounds the worst case of the whole program-zone plan.

**Do not apply the shipped IOCLID patch to our bin.** The `KWP IOCLID Privilege
Escalation` patch in `defs/ca654019 2700.xdf` was authored against a different
program image: its hook at file `0x3CEF4` expects basedata `E7FC3100`, but our
(OpenGK-verified) image has `22308A2B` there — that reject-stub sits at a
different address in our program. Applying it blind would corrupt `0x3CEF4`. We
do not need it anyway: our program reads fine, and `--flash-program` needs only
the Hyundai-level security GKFlasher already performs (§2).

## 2c. Why K-line program flash is low-risk on *this* car, and the recovery guarantee

The desolder route works but is horrible; K-line is the goal. The case that it is
safe here rests on mechanism, not optimism:

- **We have already done a successful K-line erase/write/verify on this exact
  car** — the ghost-cam **calibration** flash (2026-08-31, [[ghost-cams]]).
  Program flash is the *same* GKFlasher call (`cli_flash_eeprom`), the *same*
  reprogramming session (`FLASH_REPROGRAMMING`), the *same* Hyundai-level
  security (`enable_security_access` → `calculate_key`, `key=0x9360; 0x24×
  (key=key*2 ^ seed)`), and the *same* bootloader machinery (RequestDownload /
  TransferData / StartRoutine). The only differences are the erase routine
  number (`0x00` program vs `0x01` calibration) and the fixed write pointer
  (`0x90010` vs `0x88000`). Nothing on the unproven list is in the flash path.
- **The erase/write code runs *from the boot sector*.** The AM29F400 command
  sequences (unlock writes `0x5554`/`0xAAAA`) live at boot file `0x0422`,
  `0x052A`, `0x3266`+ — all below `0x8000`. Flash cannot erase a sector while
  executing from it, so a program erase **cannot touch the boot sector**. The
  boot loader therefore survives *any* botched program flash and still answers
  KWP2000 in reprogramming mode — which is exactly what makes a reflash possible.
  (The bootloader's own range classifier at boot `0x2FC2` independently refuses
  any write target outside program / calibration / NVM; boot is never a target.)
- **Coherence holds by construction.** The verify routine checks a coherence
  identifier tying the program image to the boot software (reprogramming-status
  bit 12, `ecu_sw_does_not_fit_to_boot_sw`). Our candidate is built on **our own
  program read**, whose ID/coherence block at file `0x1004E`
  (`…654019KR77035111--11165401`) pairs with our boot `KR77035202` already, and
  our patches never touch it (all 89 changed bytes are at `0x10010`–`0x1458F`,
  none in `0x10012`–`0x11000`). **Rule: only ever flash a program image derived
  from our own read — never a sibling dump**, whose coherence ID pairs with a
  different boot and would be rejected at verify (or worse, accepted wrongly).

**Recovery ladder if a program flash fails.** In order of use:

1. Verify fails → GKFlasher prints the reprogramming-status word and "flash a
   valid file". The boot loader is intact and in reprogramming mode. **Re-run the
   same `--flash-program`.** Most transient comms drops end here.
2. Power-cycle the ECM (ignition off ~20 s for the main relay to drop, ignition
   on) and re-run. Clears a wedged session.
3. Flash `roms/stock/FULL_ca654019_stock_merged.bin --flash-program` to return to
   a known-good stock program (its coherence pairs with our boot; the cal it
   leaves is whatever was last written — flash the stock cal too if unsure).
4. Only if the boot loader itself stops answering (power lost mid-erase, hardware
   fault) does the bench come out: desolder, write `FULL_ca654019_stock_merged.bin`
   with the Willem GQ-4X (chase's method), resolder. This is the documented
   backstop, not the expected path.

Decoding the status word (routine `0x03`, `ReprogrammingStatus` in
`ecu_definitions.py`) when a verify fails — the bits that matter:

| bit | name | meaning if 0 |
|---|---|---|
| 0 | `checksum_of_calibration_data_is_correct` | cal checksum bad → re-run `--correct-checksum` |
| 3 | `calibration_data_is_correct` | cal write incomplete |
| 4 | `checksum_of_ecu_sw_is_correct` | **program checksum bad** → `--correct-checksum` before reflash |
| 7 | `ecu_sw_is_correct` | program write incomplete → reflash program |
| 8 | `ecu_reprogramming_successfully_completed` | the all-clear; 1 = done |
| 11 | `calibration_data_does_not_fit_to_ecu_sw` | cal/program coherence mismatch (wrong pair) |
| 12 | `ecu_sw_does_not_fit_to_boot_sw` | **flashed a program from the wrong boot family** — see the coherence rule above |

## 2e. Test 0 as it actually happened (2026-09-18)

1. First attempt (unpatched GKFlasher): erase routine `0x00` **completed**, then
   `RequestDownload` was refused with `0x40`. The car sat with an erased program
   zone: the bootloader kept answering, exactly as §2c predicts. Reads were then
   denied (`0x33`) even after a correct seed/key handshake — the bootloader does
   not serve `ReadMemoryByAddress` while there is no valid program — so GKFlasher
   cannot auto-identify the ECU in this state. Pick it from the menu (`2` =
   5WY17) and answer `y` to "calibration not found, continue?". When piping
   answers, that is **three** lines: `printf '2
y
y
'`.
2. After an ignition cycle (a failed session leaves the ECU handing out a zero
   seed, which GKFlasher misreads as "already unlocked"), the patched flasher
   erased again, wrote 239,268 bytes in 5 min 52 s at 10400 baud, verify routine
   `0x02` passed, ECU reset. A read-back within seconds of the reset gets `0x37`
   (time delay not expired); wait ~10 s.

## 2d. Baud rate — shrink the exposure window

The stock read and the cal flash ran at the **10400** default (`~680 B/s`; the
239 KB program read took 11 min). A program *write* at that rate is ~6 min of
continuous K-line traffic — the main incremental risk over the 35 s cal flash is
simply the length of the window. GKFlasher can negotiate up to **120000** baud
(`--desired-baudrate 0x05`; `BAUDRATES` in `ecu_definitions.py`), which would cut
the write to well under a minute.

**Prove the fast baud on a read first** (read-only, no erase, fully safe): do a
`--read-program --desired-baudrate 0x05` and compare the result to the known
stock read (code region must hash `d024e1d1…`). If a full program read at 120000
succeeds and matches, the rate is reliable on this cable/car and can be used for
the flash. If it drops packets, stay at 10400 and accept the longer window — it
is still recoverable, just slower.

## 2b. Runbook for the first program flash

Battery on a charger, laptop on mains, both stock images at hand. Everything
below is from `tools\GKFlasher` with `$env:PYTHONUTF8=1` and the venv python.

```powershell
# 0. identity + fresh backups of what is on the car right now
python -u gkflasher.py --protocol kline --interface COM7 --id
python -u gkflasher.py --protocol kline --interface COM7 --read-calibration -o ..\..\roms\stock\cal_before_program_flash.bin
python -u gkflasher.py --protocol kline --interface COM7 --read-program     -o ..\..\roms\stock\program_before_program_flash.bin
#    cal must hash 65DA7B7F… (ghost cams), program code region d024e1d1… (stock)

# 0b. (optional, recommended) prove 120000 baud on a READ before trusting it on a write
python -u gkflasher.py --protocol kline --interface COM7 --desired-baudrate 0x05 --read-program -o ..\..\roms\stock\program_fastbaud_test.bin
#    code region 0x10000-0x4A6A6 must hash d024e1d1… (== stock). If it does, add --desired-baudrate 0x05
#    to the flash commands below to cut the ~6 min window to <1 min. If not, drop it and stay at 10400.

# 0c. TEST 0 — prove the program-flash PATH with a byte-identical stock program (zero behaviour change)
python -u gkflasher.py --protocol kline --interface COM7 --flash-program ..\..\roms\stock\FULL_ca654019_stock_merged.bin
python -u gkflasher.py --protocol kline --interface COM7 --read-program -o ..\..\roms\stock\program_after_test0.bin
#    code region must still hash d024e1d1…  This is the single highest-value de-risk: it exercises
#    erase+write+verify of the PROGRAM sector on this car/cable/boot rev with nothing to lose if it fails.

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
- **Stub A** (`0x11040`): self-contained arm/disarm on rpm/32 — sets the latch
  once rpm/32 ≥ `C_N_ARM_POP` (cal `0xBC91`), clears it once rpm/32 <
  `C_N_DISARM_POP` (cal `0xBC92`, ~1024 rpm) — then tail-calls the real inhibit
  task. Hooked by **redirecting the task's single caller** (`0x3AC00`), leaving
  the task prologue stock; a first design that displaced the prologue had a
  stack bug and was replaced (notes.md). Both thresholds are cal bytes; the
  disarm-on-rpm-dip also covers key-off, with no dependency on RAM init.
- Latch bit `M_FD40.15`: unreferenced anywhere in the stock program (the word
  has no whole-word or bitfield access).

**Runtime dependency reviewed (2026-09-03).** The mask applier the final stage
feeds (`0x4436`) gates on `M_FD12.7` (= NOT `M_FD38.0`, a debounced ADC-threshold
flag) and outputs `pattern_table[max` of five sources incl. `[0xC1AB]`]. The patch
is **safe in all cases** (output between our pattern and all-six, overrun-only).
The gate is **open in normal warm overrun by construction** — the stock cal's real
staged indices (`PUC_1=4`, `PUC_2=9`) require it — so the pattern is honored under
the same conditions the stock staged cut runs; low residual risk. The capture run
confirms it (stock staging 1 → 4 → 6) and is still worth having before flashing.
Full analysis and the direct-`[0xF9BA]` contingency in [[puc-overrun-map]].

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
3. Battery on a charger, laptop on mains. Optionally prove 120000 baud on a read
   (§2d), then **Test 0**: flash the byte-identical **stock** program (§2b step 0c)
   to prove the K-line program-flash path with nothing at stake. Then flash the
   **rehearsal** image **cal first, then program**, read both back, compare, start,
   idle, drive — behaviour must be indistinguishable from today.
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
