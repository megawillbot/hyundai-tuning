# Daily tune: stock overrun + NZ 91 timing, event setup behind the latch (built and FLASHED 2026-09-21)

`FULL_ca654019_daily_latch_91_UNFLASHED.bin` — full `0d73265be10efc12`, cal
`e1ee07148a512aaa`, program `3c798d4b25e25b1d` (`build.py`, which prints the
disassembled stubs and does the byte accounting). **Both zones change: flash the
calibration first, then the program.**

Owner's brief (2026-09-21, after the grasskhana): back to a regular / longevity
tune, but burbles and pops come back once the revs exceed 6000 and go away the
next time rpm drops below 900; and set the timing up for NZ 91.

## Behaviour

| | unarmed (every start, every return to idle) | armed (after a rev past 6016 rpm, until rpm < 896) |
|---|---|---|
| overrun fuel | stock: staged cut 1 -> 4 -> all six, resume 1248-1600 rpm, dashpot wait | the 2026-09-20 event cal (`paddock_pops_instant`): pattern 6 (three injectors) from the first cycle, 2016 rpm up; fuel on below 2016 |
| overrun ignition | stock `IP_IGA_PU_AT` / `IP_IGA_PUC_AT` | burble v2 rows (state 4), -48 deg PUC cells, base cols 0/1 at 28 deg, `C_IGA_LGRD_1` x4 |
| idle valve in the cut | stock (closed) | held open from 2240 rpm |
| base ignition under load | 91 RON map | same 91 RON map |
| ghost cams | yes (unchanged since 2026-08-31) | yes |

Arm `0xBC93` = 188 (6016 rpm; **this program reads its arm threshold from `0xBC93`**,
`0xBC91` is kept equal for the old program), disarm `C_N_DISARM_POP` `0xBC92` =
28 (896 rpm); all plain cal bytes. Warm idle is 680-780 rpm, so every
stop disarms. If the idle ever sits above ~900 (cold fast idle, heavy A/C
idle-up) the latch holds until it drops — raise `0xBC92` if that annoys.

## Why a program change was needed

The 2026-09-18 patch only latches the **final** cut stage. Everything else that
made the event cal loud was unconditional calibration: burble retard in state 4,
the cut-entry stages, the 2016 rpm resume, -48 deg PUC cells, the lowered base
columns, the dashpot hold-open, no dashpot wait, the faster retard slew. A
cal-only "daily" could only have been the stock cut with a feeble armed mode, or
an event cal that leaks on every lift.

Every one of those tables has exactly one `MOV R12,#table` site (the two scalars
have two sites each). Each 4-byte site becomes `CALLS 0x09,<stub>`:

```
stub:  <the stock 4-byte instruction>      ; MOV R12,#stock | CMPB RL5,[stock] | MOV Rn,[stock]
       JNB  M_FD40.15, +                   ; latch clear -> keep stock
       <same instruction, alternate copy>  ; table/constant in free cal 0xBC94..0xBDB9
   +:  RETS
```

| site | stock operand | armed alternate (cal) |
|---|---|---|
| `0x144FC` | `ID_PAT_INH_IV_PUC_1` `0x99D0` | `PUC_3` `0xBC8B` |
| `0x1453E` | `ID_PAT_INH_IV_PUC_2` `0x99D6` | `PUC_3` `0xBC8B` |
| `0x20FD6` | `IP_IGA_PUC_AT__N` `0xA198` | `0xBC98` (4 B) |
| `0x2101A` | `IP_IGA_PU_AT__N__TCO` `0xA184` | `0xBC9C` (16 B) |
| `0x1C874` | `IP_N_MIN_PUC_AT` `0xA91F` | `0xBCAC` (42 B) |
| `0x1C8AA` | `IP_N_ACCIN_MIN_PUC_AT` `0xA8C4` | `0xBCAC` (shared) |
| `0x221C6` | `IP_ISAPWM_DHP_AT__N__TPS` `0xA3AD` | `0xBCD6` (35 B) |
| `0x20E3E` | `IP_IGAB__N__MAF` `0xA272` | `0xBCFA` (192 B) = 91 map + cols 0/1 rows 2200-6000 at 28 deg |
| `0x1C42E`, `0x1C434` | `C_N_MIN_DHP` `0x8238` | `0xBC96` = 255 |
| `0x21102`, `0x212AC` | `C_IGA_LGRD_1` `0x83FA` | `0xBC94` = 2184 |

Stubs at `0x11060`-`0x1110D` (11 x 14 B, 16 B pitch), after stub A. 205 program
bytes differ from the program on the car: 154 stub + 48 site + 1 (stub A) + 2 checksum.
Properties: the stock instruction always executes first, so unarmed is stock by
construction; CALLS/JNB/RETS leave the flags alone (matters for the two CMPB
sites); every site is followed at the same stack level by a CALLS of its own, so
peak system-stack depth does not grow.

**Inert on older cals — by construction, after a review catch (2026-09-21).** The
event cals arm at 3200 rpm via `0xBC91` and have FF where the alternates live;
this program on such a cal would have armed and read FF tables (base map 255 =
~72 deg, resume 8160 rpm) until rpm < 1024. So stub A's arm compare now reads a
new byte, **`0xBC93`** (`0x1104E`: `91` -> `93`), which is FF in every older
image in this repo (every `roms/**/*.bin` scanned 2026-09-21): on any cal without
the alternates the latch never arms. **Rule for future cals on this program:
set `0xBC93` only in a cal that carries all the alternate tables.** Still flash
cal first, and never use GKFlasher's full `--flash` (program before cal).

Independent review (second agent, from the binaries, 2026-09-21): byte
accounting, site decode / no mid-instruction targets, flags across
CALLS/JNB/RETS, CALLS/RETS pairing (all enclosing routines entered by CALLS, no
PUSH/POP), stack peak, lookup routines take the table via R12 only with strides
from the axis scratch, table geometry vs axis counts, alt-table contents,
checksums: all confirmed. Not verified: flag behaviour on silicon, task
priorities.

Armed mode is tuned from now on by editing the **alternate** tables (cal-only).
The PUC axis top breakpoint `0x875C` is back at stock 78 (2496 rpm); the top two
`PUC_3` cells are both 6, so the pattern still covers 2016 rpm up.

## NZ 91 timing

Evidence (all on 91 RON, stock map): `log_shift_2026-09-19_*` + `log_drive_2026-09-19_2*`
(true per-cylinder retard vs `[0xC337]`) and the WOT frames of the raw logs of
09-08/18/19 (split vs least-retarded cylinder, a lower bound, ~50 frames):

- **2000-3000 rpm, mid/high load (tall-gear acceleration): the worst region.**
  3.0-3.4 deg knock steps stacking to 10.5 deg on cyl 6 / 3 / 5, all six pulled
  4+ deg at 2400-2900 rpm; mean 3.5 (2000-2499) and 5.6 deg (2500-2999).
  Base angle 24-30 deg there = load columns 6-7 (280-330 mg/stroke).
- WOT 3000-5000 rpm: mean 2-3 deg, peaks 5-7. WOT runs in columns 8-9; columns
  10-11 are above the NA load clamp and only keep the surface smooth.
- >= 5500 rpm: ~1 deg mean. <= 1800 rpm: almost nothing.

Cut = measured mean + ~1 deg (the plan in [[open-threads]]), in counts of
0.375 deg on `IP_IGAB__N__MAF`, columns 0-4 (< 230 mg/stroke: idle, cruise,
overrun) untouched:

| rpm | col 5 (230) | col 6 (280) | cols 7-11 (330+) |
|---|---|---|---|
| 1500 | 0 | -1.5 | -1.5 |
| 1800 | -1.5 | -3.0 | -3.0 |
| 2200, 2600 | -2.25 | -4.5 | -4.5 |
| 3000, 3200 | -1.5 | -3.75 | -3.75 |
| 3700, 4000, 4500 | 0 | -1.5 | -3.0 |
| 5050 | 0 | -0.75 | -2.25 |
| 5550, 6000 | 0 | 0 | -1.5 |

Knock control stays fully active on top, so this is a starting point, not a
ceiling: it should turn frequent 3-10 deg knock events into rare ones. The
per-cylinder adaptives learned on the old map will take a few drives to relax.
Verify with `tools/ram_logger.py shift` on a normal drive (per-cylinder retard =
`([0xC325+i] - (255 - [0xC337])) x 0.375`); where retard is still > ~2 deg mean,
take another 1.5 deg out of that cell (unarmed map **and** the alternate at
`0xBCFA`, same row/column offsets). On 95/98 this map gives away a few hp — keep
the ghost-cam cal as the 95+ image.

## Runbook

Battery on the charger, ignition ON engine OFF, from `tools\GKFlasher` with
`$env:PYTHONUTF8=1`. `gkflasher.py` must still carry the local program-address
fix ([[program-zone-plan]] §2). Cal first: the new cal on the old program is a
sane tune by itself (stock overrun + 91 map; armed = final-stage pattern only).

```powershell
$img = "..\..\roms\tunes\daily-latch-91\FULL_ca654019_daily_latch_91_UNFLASHED.bin"
$py  = "..\..\.venv\Scripts\python.exe"
& $py -u gkflasher.py --protocol kline --interface COM7 --flash-calibration $img
& $py -u gkflasher.py --protocol kline --interface COM7 --read-calibration -o ..\..\roms\tunes\daily-latch-91\readback_cal.bin
& $py ..\..\roms\tunes\paddock-pops\check.py ..\..\roms\tunes\daily-latch-91\readback_cal.bin $img cal
# only if MATCH:
& $py -u gkflasher.py --protocol kline --interface COM7 --flash-program $img      # ~6 min, touch nothing
& $py -u gkflasher.py --protocol kline --interface COM7 --read-program -o ..\..\roms\tunes\daily-latch-91\readback_program.bin   # wait ~10 s after the reset
& $py ..\..\roms\tunes\paddock-pops\check.py ..\..\roms\tunes\daily-latch-91\readback_program.bin $img program
```

Program flash fails -> recovery ladder in [[program-zone-plan]] §2c (re-run; key
cycle, ECU `2` from the menu; fall back to
`paddock-pops-tpsceil\FULL_..._instant` `--flash-program` = the program that was
on the car, which is inert with this cal apart from the final-stage latch).

First drive: (1) unarmed — lifts should feel stock (engine braking back, silent);
`tools/ram_logger.py puc` should show mask `0x3F`-style all-six cuts and the
staged 4 -> 9 -> 13 indices. (2) One pull past 6000, lift: event behaviour.
(3) Stop, idle, drive off: stock again.

## Flashed 2026-09-21 ~17:30-18:00 — verified, THIS IS ON THE CAR

Pre-flight: `--id` OK (5WY17, G5J7TS0A, boot KR77035202), cal on the car ==
`paddock_pops_instant` (`readback_cal_before.bin`), one stored DTC P0123 (history
from the 2026-09-19 mis-clocked TPS), battery 12.5 V (new battery, no charger —
owner's call). Cal flash 35.8 s, read-back `readback_cal.bin` == image (cal
`e1ee07148a512aaa`). Program flash 5 min 49 s at 10400, ECU verify passed,
read-back `readback_program.bin` == image (program `3c798d4b25e25b1d`; the full
program read takes ~11 min). Not yet driven.

## First drive 2026-09-21 17:54 (`log_drive_2026-09-21_175406.csv`, first 129 s only, ~1 Hz, max 2758 rpm in the logged part)

A first drive straight after the flash went unlogged (COM7 had dropped off USB);
this is the second one, and **the logger lost the cable again 2 min in** (17:56:15,
K-line timeout then COM7 gone; drive ran to ~17:58), so the owner's pull past
6500 rpm is not in the log. Idle 675-795 rpm, 74-79 C, 13.5+ V, ghost-cam
lope unchanged, raw TPS 13 closed, **no TPS fault frames, latch never set**
(never near 6016). Resume threshold `[0xC20F]` = 39 = **1248 rpm = the stock
table** (armed would read 63), state-4 coast ignition 10-13 deg BTDC from a 33
deg base = the stock `IP_IGA_PU_AT` retard, not burble. No state-5 frame: all
six lifts were from <= 1700 rpm, at or below the stock cut-in — staged cut still
to be seen. Base angle 20.2 deg at 2758 rpm / load 204 = the 91 map (stock
would be ~23-25). Only two loaded frames, both with a *uniform* 3.8-4.5 deg on
all six cylinders (the global term noted in [[open-threads]], not per-cylinder
knock steps); far too little to judge the 91 cut. Still to do: lifts from
2500-4000 (staged cut 4 -> 9 -> 13), one pull past 6016 (arm), idle (disarm),
and a longer loaded drive for the knock table.

Cable: on both drives the FTDI adapter dropped off USB within minutes of moving
(Windows shows both devices `CM_PROB_PHANTOM`; no sleep/wake events; it held for
25 min of flashing while parked) -> intermittent USB connection. Owner will try
another adapter. USB selective suspend was enabled (AC+DC); **disabled 2026-09-21** on the laptop's
current power plan (`powercfg` index 0 on both). **Owner's report for the whole run, incl. the pull
past 6500: "everything seemed fine".** Arm/disarm and the staged cut remain
unconfirmed by data.
