# Paddock pops & bangs — built 2026-09-18, FLASHED 2026-09-18 19:11

For the paddock session on **Sunday 2026-09-20**; revert afterwards. Two full
512 KiB images, built by `build.py` in this folder (re-runnable, self-checking):

| file | what | full SHA256 | cal-zone SHA256 |
|---|---|---|---|
| `FULL_ca654019_burblev2_pucstage_rehearsal_UNFLASHED.bin` | **rehearsal**: the reviewed program patch + the burble v2 cal that is on the car now + the new cal bytes at *inert* values. Behaviourally identical to today. | `97380ca1abb6cebf…` | `091f1a6a6abd26fe…` |
| `FULL_ca654019_burblev2_paddock_pops_UNFLASHED.bin` | **pops**: same program, cal-only changes on top of the rehearsal. | `102e70e6db2a4f57…` | `c911dc39087b3907…` |

Program zone of both = `roms/tunes/puc-final-stage-patch/` (SHA `d5f5ac502fd95fe5…`
over `0x10000-0x80000`, program checksum `0xFBD7`, 89 bytes from stock — the
stubs and the mechanism are documented and reviewed there; nothing in the
program was changed for this build). Both images pass `--correct-checksum`
(answer `n`) with current == new in both regions.

## What it does

The burble tune keeps fuel on during every lift and retards the spark
(state 4). It cannot make bangs because the ECU has no cal-only way to put
unburnt fuel *and* oxygen into the exhaust at the same time. This tune adds the
program patch's rpm-windowed cut on top of it, and sets the overrun-cut resume
point to the bottom of that window, so the two mechanisms stack:

| lift rpm | engine state | injectors | ignition | sound |
|---|---|---|---|---|
| above ~3200 (cut engages) down to 3008 | 5 (cut) | **three cut, three firing** (pattern 6, `101100`) | firing cylinders **-42 deg** relative | bangs: the cut cylinders pump air, the firing ones burn late into it |
| 3008 down to idle | 4 (burble v2, unchanged) | all six on | -26 / -36 deg (v2 rows) | the burble you have now |

The pattern only applies while the latch `M_FD40.15` is set; it arms whenever
rpm passes **3200** and clears whenever rpm drops below **1024** (every return
to idle, and key-off). So any lift from above ~3200 rpm pops. The arm point is
inside the window on purpose: this is a paddock tune, not a daily one.

## Calibration changes

Rehearsal vs the burble v2 cal on the car (9 bytes):

| addr | value | meaning |
|---|---|---|
| `0xBC8B`-`0xBC90` | `0D` x6 | `ID_PAT_INH_IV_PUC_3__N_32` — all six cut at every rpm = stock final stage |
| `0xBC91` | `FF` | `C_N_ARM_POP` = 8160 rpm, never arms (stock bytes here are `FF` too, so the stock and burble cals are also inert on this program) |
| `0xBC92` | `20` | `C_N_DISARM_POP` = 1024 rpm |
| `0xDEE0`-`0xDEE1` | `09A5` | cal checksum |

Pops vs the rehearsal (91 bytes):

| addr | from -> to | meaning |
|---|---|---|
| `0xA91F` (42 B) | `FF` -> `5E` | `IP_N_MIN_PUC_AT__TCO__GR_MT`: cut resume 3008 rpm in every coolant/gear cell (burble v2 had 255 = cut unreachable; stock 1248 warm) |
| `0xA8C4` (42 B) | `FF` -> `5E` | `IP_N_ACCIN_MIN_PUC_AT__TCO__GR_MT`: same for the `M_FD8C.14` variant |
| `0x875C` | `4E` -> `5E` | top breakpoint of the `0x8757` rpm/32 axis: 2496 -> 3008 rpm (all four tables on this axis are flat with rpm; verified 2026-09-03) |
| `0xA19A`, `0xA19B` | `3D` -> `10` | `IP_IGA_PUC_AT__N` 2400 and 3500 cells: -25.1 -> **-42.0 deg** relative for the firing cylinders (stock `ACCIN` variant already commands -33.8) |
| `0xBC90` | `0D` -> `06` | `PUC_3` top cell: pattern 6, three injectors cut, uneven spacing |
| `0xBC91` | `FF` -> `64` | arm at 3200 rpm |
| `0xDEE0`-`0xDEE1` | | cal checksum `1D4F` |

Why resume = window bottom: the state machine exits the cut when `N/32 <
[0xC20F]` (the resume lookup) and the pattern table is stepped on the same
rpm/32 scale, so with both at 94 the cut exists *only* where the three-cylinder
pattern applies. Below it the ECU falls straight into state 4 and the burble v2
retard takes over. The cut engages at resume + hysteresis (`C_N_HYS_MIN_PUC` 6
-> ~3200 rpm; after a recent cut `C_N_HYS_MAX_PUC` 16 -> ~3520). The first two
cut stages (11 cycles of 1 cylinder, 11 of 4 — about 0.1 s at 4000 rpm) are
stock and left alone: seeing 1 -> 4 -> 3 in a per-cylinder log is the proof the
mechanism is live.

Absolute timing for the firing cylinders: base map at the lowest load row is
~33-42 deg BTDC above 2000 rpm, so -42 lands at roughly TDC to 9 deg ATDC. The
running angle clamps at -23.6 deg regardless.

## Saturday runbook (2026-09-19)

This is the **first program-zone flash on this ECU**. Read
[[program-zone-plan]] §2c (why it is low-risk here, and the recovery ladder)
before starting. Battery on a charger, laptop on mains, ignition ON engine
OFF, nothing else on the K-line. Budget ~1.5 h with drives. All commands from
`tools\GKFlasher`:

```powershell
cd tools\GKFlasher
$env:PYTHONUTF8=1
$py = "..\..\.venv\Scripts\python.exe"
$pp = "..\..\roms\tunes\paddock-pops"

# 0. identity + confirm what is on the car (cal must MATCH burble v2)
& $py -u gkflasher.py --protocol kline --interface COM7 --id
& $py -u gkflasher.py --protocol kline --interface COM7 --read-calibration -o $pp\readback_cal_before.bin
& $py $pp\check.py $pp\readback_cal_before.bin ..\..\roms\tunes\burble\cal_ca654019_ghostcam_burble_v2_UNFLASHED.bin cal

# 0c. TEST 0 - flash the byte-identical STOCK program. Proves erase/write/verify of the
#     program sector on this car with zero behaviour change. ~6 min write + ~11 min read-back.
& $py -u gkflasher.py --protocol kline --interface COM7 --flash-program ..\..\roms\stock\FULL_ca654019_stock_merged.bin
& $py -u gkflasher.py --protocol kline --interface COM7 --read-program -o $pp\readback_program_test0.bin
& $py $pp\check.py $pp\readback_program_test0.bin ..\..\roms\stock\FULL_ca654019_stock_merged.bin program
#     Start the engine, idle 30 s. Must be exactly today's car.

# 1. rehearsal CALIBRATION first (adds the inert table; the stock program ignores it)
& $py -u gkflasher.py --protocol kline --interface COM7 --flash-calibration $pp\FULL_ca654019_burblev2_pucstage_rehearsal_UNFLASHED.bin
& $py -u gkflasher.py --protocol kline --interface COM7 --read-calibration -o $pp\readback_cal_rehearsal.bin
& $py $pp\check.py $pp\readback_cal_rehearsal.bin $pp\FULL_ca654019_burblev2_pucstage_rehearsal_UNFLASHED.bin cal

# 2. rehearsal PROGRAM (the real step). Do not touch anything until it says Done.
& $py -u gkflasher.py --protocol kline --interface COM7 --flash-program $pp\FULL_ca654019_burblev2_pucstage_rehearsal_UNFLASHED.bin
& $py -u gkflasher.py --protocol kline --interface COM7 --read-program -o $pp\readback_program_rehearsal.bin
& $py $pp\check.py $pp\readback_program_rehearsal.bin $pp\FULL_ca654019_burblev2_pucstage_rehearsal_UNFLASHED.bin program
#     Start, idle, short drive with the logger running: must be indistinguishable from today.

# 3. the POPS cal (cal-only, 35 s)
& $py -u gkflasher.py --protocol kline --interface COM7 --flash-calibration $pp\FULL_ca654019_burblev2_paddock_pops_UNFLASHED.bin
& $py -u gkflasher.py --protocol kline --interface COM7 --read-calibration -o $pp\readback_cal_pops.bin
& $py $pp\check.py $pp\readback_cal_pops.bin $pp\FULL_ca654019_burblev2_paddock_pops_UNFLASHED.bin cal
```

Test drive with `tools/raw_logger.py` running: warm up, hold 2 (or manual), pull
to ~4500, lift fully. Expect bangs until ~3000, then the burble. In D the
converter unhooks on a lift and rpm collapses to ~1450 within about a second
(seen in every log), so the bang window is short unless a low gear is held.

If step 0c or 2 fails at verify: ignition off 20 s, ignition on, re-run the
same command. If it fails twice, `--flash-program
..\..\roms\stock\FULL_ca654019_stock_merged.bin`. Full ladder in
[[program-zone-plan]] §2c. Optional before 0c: prove 120000 baud on a read
(`--desired-baudrate 0x05 --read-program`, compare with `check.py`) and add the
flag to the flash commands to cut the ~6 min window to under a minute.

**Do not** skip Test 0 to save time, and **never** flash the program before its
calibration.

## Log

### 2026-09-18 — pre-flight and Test 0 (done)

- Pre-flight: `--id` OK, 0 DTCs, cal read-back == burble v2, program read-back
  == stock (11 min at 10400, no dropped frames). The FTDI driver had been
  removed by a Windows driver-store cleanup; reinstalled from Windows Update
  (2.12.36.20), COM7 back. Check the port exists before starting on Saturday.
- **Test 0 first attempt failed and left the program zone erased**: the erase
  routine completed, then `RequestDownload` was refused (`0x40`). Root cause is
  GKFlasher's program download address (`0x070010`, masks to segment 7; the
  bootloader wants segment 9). Fixed locally in `tools/GKFlasher/gkflasher.py`
  (diff recorded in [[program-zone-plan]] §2). Upstream has the same bug, so
  `--flash-program` had never worked on this family over K-line.
- While the program zone is erased the bootloader denies all reads, so
  GKFlasher cannot auto-identify: choose `2` (5WY17) from its menu and answer
  `y` to "calibration not found, continue?" and `y` to "ready to flash?". After a
  failed session the ECU hands out a zero seed and denies everything until an
  ignition cycle (off 20 s).
- **Second attempt with the fix: erase, 239,268 B written in 5:52, verify
  passed, ECU reset.** `--id` auto-identifies again; program read-back == stock
  (`readback_program_test0.bin`); cal read-back still == burble v2
  (`readback_cal_after_test0.bin`). The K-line program-flash path on this
  5WY17 / KR77035202 is proven, including the recovery from an erased zone.

### 2026-09-18 evening — steps 1 and 2 (done)

- Post-Test-0 drive around the block: fine, no CEL.
- **Step 1**: rehearsal cal flashed (36 s), read-back == image
  (`readback_cal_rehearsal.bin`). Reads within ~10 s of the post-flash reset get
  `0x37`; wait and retry.
- **Step 2**: rehearsal program flashed with the patched flasher (5:52, verify
  passed, reset), read-back == image (`readback_program_rehearsal.bin`, 89 bytes
  from stock, program checksum `0xFBD7`). **The patched program is now on the
  car**, pop table inert (arm byte `FF`). A first attempt aborted harmlessly
  because a queued menu answer landed on the "ready to flash?" prompt — when
  the ECU auto-identifies there is no menu, so the only prompt is that one.
- Rehearsal drive: fine, no CEL.
- **Test drive (log `log_raw_2026-09-18_1913/1915.csv`, 957 s, coolant to 79 C,
  max 6553 rpm, one first-gear foot-off pull): NO POP. The fuel cut never
  engaged — in the whole session not one injector ever dropped below ~300 raw
  (zero frames with any injector < 100). Every lift went into state-4 burble
  (all six firing at ~330 min fuel, ignition byte 154-204) instead of the
  state-5 cut. The pop pattern lives inside the cut, so with no cut there is no
  pop.**
  - Root cause = closed-throttle recognition, exactly the flagged TPS risk.
    Idle/closed TPS median is **46 raw**; on a lift TPS only falls to **50**
    (4+ counts above closed, `C_TPS_IS` window is 3). The ECU reads a lift as
    trailing-throttle, applies the PU retard (burble), and never promotes to
    the fuel cut.
  - The first-gear pull (4762 -> 2615, foot off, ~3 s above 3008 rpm) **rules
    out** the automatic-converter rpm-collapse explanation from 2026-09-03: the
    window was wide open and still no cut. It is the TPS, not the gearing.
  - Consistent with every prior log on this car: the overrun cut has never once
    been observed (2026-09-03 capture, both burble drives).
  - **The tune is safe and inert** — the max/gate logic was never even reached
    (no state 5), so nothing downstream matters. Audible result: strong
    crackle/burble on lifts, no bangs.
  - **Path to actual bangs = the pending TPS replacement**, so the ECU sees a
    properly closed throttle and enters the cut. A cal-only alternative
    (widening `C_TPS_IS`) is NOT recommended: with the cut now live it would
    fire the cut/pattern at light cruise. Hardware fix first, then retest.
  - DTC read after the drive timed out (ignition was off by then); no CEL was
    seen during the drive and no misfire-inducing cut occurred, so codes are
    unlikely. Re-read with ignition on if wanted.
- **Step 3**: pops cal flashed 19:11 (36 s), read-back == image
  (`readback_cal_pops.bin`, cal `c911dc39087b3907…`). **The pops tune is on the
  car.** Test drive and Sunday outcome below when known.

The runbook above is unchanged; the interactive prompts are answered by hand
when run from a terminal.

### 2026-09-18 second drive — confirms the sensor under load

Retested after the live TPS check showed **33-35 raw steady at warm idle** (the
low, healthy band). Second drive (`log_raw_2026-09-18_1953.csv`, 1989 frames,
coolant to 94, max 6266 rpm): **still no cut, no injector below ~285 on any
lift.** Decisive detail: idle TPS median **36** (low band) but across all 44
overrun frames TPS read **49-81** (high band). So working the throttle and
lifting kicks the faulty sensor into its high band; processed TPS stays well
above the 3-count closed window; the cut never arms. This is the sensor failing
*under load*, not just a power-up-band lottery — a new TPS is the fix, confirmed
twice.

## Plan after the test drive (decided 2026-09-18)

Owner is fitting a **new TPS tomorrow (2026-09-19)** and will retest the pops
tune **as-is** — no software window change. The cut never engaged because the
throttle never reads cleanly closed (state-4→5 gate is `M_FD46.0`, the
`C_TPS_IS`=3 test; verified in the disassembly, first gate at `0x1C3AA`). A
sensor that reads true-closed should let the cut, and the pattern, engage with
no cal change. The C_TPS_IS-widening option (one byte `0x8335`, 3→~15) was
weighed and **declined** for now — it works but false-cuts at light throttle and
drifts idle learning; keep it in reserve if the new TPS still won't hold closed.

**The car keeps the pops tune on it** (program patch + pops cal, verified). It is
the correct image for the retest; no reflash needed. It stays inert until the
TPS is sorted.

### Retest procedure after the TPS swap

1. **Battery disconnect** after fitting (clears the learned closed position, which
   has drifted up — [[closed-throttle-recognition]]). Reconnect, warm idle.
2. Confirm with `tools/raw_logger.py`: TPS (pos 11) steady in the **low 30s** at
   warm idle, byte 28 = 0. That is the sign closed-throttle recognition is healthy
   again — the whole point of the swap.
3. **Driveway free-rev cut test**: in park/neutral, blip past 3200 and let it
   drop with foot fully off. If closed is recognised, the injection channels
   (pos 43–54) should show three cut above 3008 rpm — the pop pattern. This
   settles bit-to-cylinder order too.
4. If it cuts on the driveway, road-test as in the runbook (held low gear, lift
   from above 4000). If it still won't cut, the sensor still isn't reading closed
   — then reconsider the C_TPS_IS lever.

## Revert after Sunday

The patched program is inert with any cal whose `0xBC91` is `FF` — the stock
cal, the ghost-cam cal and burble v2 all are. So the revert is **cal-only**
(35 s, the proven path); the program can stay:

```powershell
# back to the daily cal (ghost cams + burble v2):
& $py -u gkflasher.py --protocol kline --interface COM7 --flash-calibration ..\..\roms\tunes\burble\cal_ca654019_ghostcam_burble_v2_UNFLASHED.bin
# or to true stock (checksum already correct):
& $py -u gkflasher.py --protocol kline --interface COM7 --flash-calibration ..\..\roms\stock\cal_ca654019_G5J7TS0A_read1.bin
```

Read back and `check.py` against the file flashed. To also put the stock
*program* back: cal first as above, then `--flash-program
..\..\roms\stock\FULL_ca654019_stock_merged.bin` and read back — another 6-minute
program flash, only worth doing if you want the ECU byte-for-byte stock. Next
event: step 3 alone (cal-only) brings the pops back, as long as the program
was left in place.

## Caveats

- **Brick risk is concentrated in Test 0 and step 2**, the first program flash
  over K-line on a 5WY17 here. The mechanism case in [[program-zone-plan]] §2c
  is strong (same GKFlasher call, same session and security as the three cal
  flashes already done; the bootloader survives any program erase). The worst
  case is a bench chip-pull, which would mean no car on Sunday. chase / OpenGK
  were asked on 2026-09-03 whether anyone has done this; no reply is recorded.
- **May be inert, never unsafe.** The mask applier takes the max of five inhibit
  sources and gates on `M_FD12.7`. Worst case it forces all six cut above 3008
  (silent, stock-like) and the burble below. The per-cylinder injection
  channels (logger pos 43-54) show which it is: three at zero = working.
- **Cat heat.** Three cylinders pumping oxygen plus three late burns is exactly
  the load the front-manifold cat hates. The window is above 3008 rpm only and
  the auto shortens it further; keep coastdowns short, no long downhill drags,
  and revert after the event as planned.
- **CEL is plausible**: misfire monitor (three dead cylinders, and -42 deg on the
  others), cat-efficiency and lambda monitors that never see a clean cut. Any
  code should clear with the revert; note which one if it comes.
- **TPS.** State 4/5 need closed-throttle recognition; the bistable sensor
  ([[closed-throttle-recognition]]) worked on both burble drives but is still
  the original part. A lift the ECU reads as part-throttle gives nothing.
- Engine braking above 3008 is stronger than the burble (half the cylinders
  cut), weaker than stock below it. Fault-mode cut (`C_N_MIN_PUC_DIAG`, 2016
  rpm) is unchanged and would give a stock all-six cut while a fault is latched.
- Ghost cams ride along unchanged.

## Knobs (cal-only, rebuild with `build.py` and re-check)

- Louder / quieter bangs: `0xA19A`/`0xA19B` (8 = -45 deg, 0 = -48 deg; 0x28 =
  -33 as the original candidate). Pattern `0xBC90`: 7 = alternate cylinders
  (smoother tone), 10 = five cut (leaner, sharper, more cat heat), 5 = two cut.
- Window: `0x875C` and both resume tables must move **together** (same rpm/32
  value). Arm `0xBC91` at or just above it.
- Burble below the window: `0xA184` rows (v2 = 58/32/32/32); the 2400/3500 rows
  only matter between 2400 and 3008 now.
- To make the first 0.1 s of the cut pop too, set the top cells of
  `ID_PAT_INH_IV_PUC_1/2` (`0x99D5`, `0x99DB`) to 6 — at the cost of the
  1 -> 4 -> 3 staging diagnostic.
