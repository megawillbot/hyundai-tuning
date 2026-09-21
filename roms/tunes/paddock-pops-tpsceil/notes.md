# Paddock pops + raised TPS closed-learn ceiling (built 2026-09-19, UNFLASHED)

Crutch for the +2 V TPS offset found 2026-09-19 ([[closed-throttle-recognition]]):
closed throttle reads raw 135 but `C_TPS_MAX_IS` (cal `0x8338`) caps the learned
closed position at 64, so closed is never recognised and the cut/pops never arm.

`FULL_ca654019_paddock_pops_tpsceil160_UNFLASHED.bin` = the pops image that is on
the car with **`0x8338`: 64 -> 160** (+ cal checksum `0xDEE0/1`). 3 bytes differ
from `paddock-pops/readback_cal_pops.bin`. Cal-only flash (`--flash-calibration`),
program zone untouched. full `2dc62536ae7fde50`, cal `8deecc63575d5916`.

Code check (all 11 references to `[0x0338]` are in the TPS init/learn/key-on
routines `0x13EB2`-`0x142E6`; it is only ever a clamp / init / fault-default):
- learn `0x14160`: clamp; on TPS fault learned := ceiling.
- key-on `0x141E0`: stored value, +`C_TPS_ADD` (6) if raw is above it, clamp.
  From the stored 64 that is ~12 key cycles to reach 135 — watch `[0xF4C1]` with
  `tools/ram_logger.py`. No-valid-record path `0x142A2`: raw+6 (or 128.00),
  clamp — a battery disconnect should adopt in one or two key-ons.

Side effects (why this is a crutch, not the fix):
- Usable range becomes raw 135 -> 249 (`C_TPS_MES_MAX_DIAG`), processed max ~114.
  TPS-to-TCU over CAN (`0x169B0`) is processed/`C_TPS_MAX_CAN` (201), so the
  gearbox sees at most ~56 % throttle at full pedal (today it sees ~35 % at
  foot-off and ~92 % max). The `0x13820` function (3..170 span) tops out ~66 %.
- Past raw 249 the TPS-high fault sets, exactly as it does today.
- After a TPS fault learned := 160 -> processed 0 at closed -> relearns down in
  a few passes. Self-recovering.
Revert = flash the pops image (or burble v2) cal-only. Fix the sensor clocking
and this byte should go back to 64.

## Flashed 2026-09-19 13:20 — verified

Cal-only flash (36 s), read-back `readback_cal_tpsceil.bin` == image (cal
`8deecc63575d5916`). **This is the cal on the car.** After the ECU reset the
learned closed position read 70.00 (was pinned at 64), and **76.00 after one
key cycle** (OFF ~20 s, ON): the +6 key-on step is stored across cycles, as the
code says. 135 needs ~10 more cycles from 76.

## Driveway free-rev test 2026-09-19 13:27 (`log_ram_2026-09-19_132712.csv`)

Battery reset adopted closed in one key-on: learned 135.00, processed 0,
`M_FD0A.12`=1, `M_FD46.0`=0 on every lift (634/680 frames closed). Revs to 6868.
**Still no injector cut** — but for a new, specific reason. On every lift above
~3000 rpm `M_FD16.5` and `M_FD1A.6` are set, i.e. the state-4 handler passes
the throttle, rpm-threshold and gradient gates and reaches the last test at
`0x1C42A`: `N/32 >= C_N_MIN_DHP` (22) **and `M_FD64.0` set -> no cut**.
`M_FD64.0` (only set/cleared at `0x2220C`/`0x22214`) = "dashpot still decaying":
`[0xCE90]` ramps from the `IP_ISAPWM_DHP_AT__N__TPS` value (up to 166 after a
big blip) down to the closed-throttle target (0) by table `0xA498`
(axis `0x8AA9`; 20<<6 per pass at >= 2496 rpm => ~33 passes). Observed > 1.2 s.
A free-rev falls from 6000 to below the 3200 arm point in ~1.3 s, so the
dashpot never finishes in time. On the road in a held gear it would, after ~3 s.

Lever: `C_N_MIN_DHP` @ cal `0x8238`, 22 -> 255. Its only two references are
that test (`0x1C42E`/`0x1C434`); with 255 the `M_FD64.0` wait is skipped and the
cut engages as soon as the other gates pass. Dashpot air itself is unchanged.

## Flashed 2026-09-19 ~13:50 — `..._tpsceil160_nodhp` (verified)

`build_dhp.py`: tpsceil160 + `C_N_MIN_DHP` `0x8238` 22 -> 255. Cal-only flash,
read-back `readback_cal_nodhp.bin` == image (cal `176e2c0436152dab`).
**This is the cal on the car.** Revert = cal-only flash of burble v2 / pops.

## Free-rev retest after the nodhp flash — 2026-09-19 13:42-13:47: **pattern confirmed live**

`log_ram_2026-09-19_134217.csv`, `log_puc_2026-09-19_134455.csv`
(`tools/ram_logger.py puc` reads `0xC1A8..AF`, `0xF9BA`, `0xC20B..0F`).
Every foot-off lift from 4000-5300 rpm: engine state `[0xC20B]` = **5**
(`M_FD16.0`) from the first frame, `[0xC20F]` = 94 (3008 rpm), hysteresis 16,
inhibit state `[0xC1AC]` = 4 (final stage, `M_FD16.12`), **`[0xC1AB]` = 6 and
applied index `[0xC1AA]` = 6, mask word `[0xF9BA]` = `0x14AC` -> bits 0-5 =
`101100`** = pop pattern 6, three injectors inhibited. Held until ~2900 rpm,
then state 4 (burble) with mask 0. So: closed-throttle recognition, the cut,
the program patch's PUC_3 lookup/arm latch and the `M_FD12.7` apply gate all
work. First overrun cut ever recorded on this car.

Logger injection channels (pos 43-54) do **not** go to zero under the mask —
they are computed pulse widths upstream of the inhibit (they read an uneven
287/313/325/352/390 set in state 5). Predictions A/C in
[[next-capture-script]] can only be checked via `[0xF9BA]`, not those bytes.
Ignition byte reads ~204 in state 5 above 4000 rpm.

## Why it is only a "stronger burble" — ignition chain measured 2026-09-19 13:52

`tools/ram_logger.py iga` (`log_iga_2026-09-19_135203.csv`). Encodings settled:
internal angle X -> `0.375*X - 23.625` deg BTDC (same as the public XDF's A272
equation); final per-cylinder bytes `[0xC325..2A]` are the **complement**
(255 - X), and logger pos 37-42 = those bytes. In the cut: `[0xE10E]` = 16
(the -42 deg cell, reached), `[0xE10A]` = final = **X 50-51 = -4.5..-4.9 deg
BTDC**; implied base X ~163 = 37.5 deg = A272 load-column 0. No clamp is
engaged (final == requested). The first cut frame after a lift still shows
~19-24 deg BTDC: the retard ramps in via `C_IGA_LGRD_1` (546/256 counts per
pass), ~0.5 s of a ~1.3 s free-rev window. So the firing cylinders were only
~5 deg ATDC, and only for half the window. Hard floor is X=0 = -23.6 deg.

`build_loud.py` -> `FULL_ca654019_paddock_pops_loud_UNFLASHED.bin` (cal
`6bbec0810eb2bb15`): PUC cells `0xA19A/B` -> 0 (-48 deg), A272 col 0 rows
3200-6000 -> 138 (28.1 deg), `C_IGA_LGRD_1` 546 -> 2184. Expected final ~-20 deg
BTDC in the cut, arriving ~4x sooner. Side effects: A272 col 0 is below idle
load, so only overrun / near-zero-load running above 3200 rpm sees the lower
base; LGRD_1 has one other reference (`0x212AC`).

## Flashed 2026-09-19 ~14:05 — `..._paddock_pops_loud` (verified)

Cal-only flash, read-back `readback_cal_loud.bin` == image (cal
`6bbec0810eb2bb15`). **This is the cal on the car.**

## Loud retest 2026-09-19 13:58 (`log_iga_2026-09-19_135844.csv`)

Delivered as designed: in the cut `[0xE10E]` = 0, `[0xE10A]` = 8-10, final
X 6-10 = **-19.9..-21.4 deg BTDC**, reached by the first or second 0.8 s frame
(one lift caught mid-ramp at -8.6), mask `0x14AC`. Below 3008 rpm (state 4)
the final angle stays ~-20 for another frame while `[0xE10E]` slews back to 32
— the owner's "buffeting from 3k down". Owner: "buffeting from 3k down
generally with a soft pop or two just down from the top". So timing is no
longer the limit; charge mass is (closed throttle, min pulse ~1.3 ms, dashpot
target 0 at closed throttle, IACV restrictor plate, manifold cat).

`build_loud_air.py` -> `FULL_ca654019_paddock_pops_loud_air_UNFLASHED.bin` (cal
`90c0b1fe931cb633`, built, unflashed): `IP_ISAPWM_DHP_AT__N__TPS` col 0 at
3488/5504 rpm 0 -> 0x80 so the idle valve is held open during the cut. Watch
the final angle afterwards: more air may lift load off A272 column 0.

## IACV restrictor plate removed 2026-09-19 14:08 (`log_iga_2026-09-19_140825.csv`)

Loud cal, plate out: idle 779 rpm settled, closed raw 133 (processed 0). In the
cut the pulse rose to 385-590 (was 290-350) and the final angle came back to
-15..-18 deg (E10A 15-23 vs 8-10): base interpolating toward A272 column 1.
Owner: "a little more thunder".

## Flashed 2026-09-19 ~14:20 — `..._paddock_pops_loud_air2` (verified)

`build_loud_air.py` + `build_loud_air2.py`: dashpot closed-throttle cells
(`0xA3C6`, `0xA3CB`) 0 -> 0x80, A272 column 1 rows 3200-6000 -> 138. Read-back
`readback_cal_loud_air2.bin` == image (cal `b8a118f790de6557`).
**This is the cal on the car.**

## First road run on loud_air2 — 2026-09-19 20:50 (`log_drive_2026-09-19_205054.csv`, 268 s) — CEL

`tools/ram_logger.py drive` (TPS cells + FD00..6F + C1A8..C20F + ignition chain, ~1 Hz).
One WOT pull to 3971 rpm: raw TPS railed at **255** -> `M_FD52.0` set for the
railed frames -> **DTC P0123 (TPS high), status 0xB1, CEL on** (the only stored
code). During the fault: CAN TPS byte `[0xC1EC]` = 255 (fault value to the TCU),
learned closed reset to the 160 ceiling, then relearned to 132 at the next
closed throttle. WOT fuelling is fine: O2 bytes 37/40 -> 180/185, injection
~3550, angle 10-15 deg. One cut episode (pattern 6, -20.6 deg). Idle 680-720,
CAN TPS 32 (closed code) at idle.
Fault test (`0x143A4`): raw > `C_TPS_MES_MAX_DIAG` (`0x8339` = 249), only
reference. 255 would make the high-range fault unreachable.

Second leg (`log_drive_2026-09-19_205803.csv`, 484 s, gentle drive home, max
2572 rpm): no WOT, no cut episodes (never above the 3200 arm point), **no TPS
fault frames**, learned closed steady 132-133, raw max 188, CAN TPS 32 at every
closed throttle and max 84 in the drive, stationary idle 720-760 rpm at 92 C.
Owner will re-seat the TPS next; then `0x8338` goes back to 64.

## TPS re-seated 2026-09-19 ~21:15 — sensor now reads correctly

`log_drive_2026-09-19_211928.csv`, key on / engine off hand sweep: closed
**raw 13** (ADC 53, ~0.26 V), full open **raw 214** (ADC 857, ~4.19 V), smooth,
repeatable, never rails, `FD52` = 0 throughout. Span 201 counts = exactly
`C_TPS_MAX_CAN` (201), i.e. the designed geometry — the morning's install had
the sensor ~120 counts round on the shaft. The ECU re-adopted closed by itself
(learned 18 -> 13 within the first frames: processed saturates at 0, so the
closed flag is set and the filter pulls the learned value down) — no battery
disconnect needed. Margin to the low-range fault (`C_TPS_MES_MIN_DIAG` = 7) is
6 counts. `build_final.py` puts `0x8338` back to 64 (built, see below).
Owner decision 2026-09-19 21:25: **do not flash the stock-ceiling image now** —
fold `0x8338` = 64 into the next flash. Car stays on `loud_air2` (cal
`b8a118f790de6557`). No battery reset (learned closed already 13).

## Drive home with the re-seated TPS — 2026-09-19 21:25 (`log_drive_2026-09-19_212553.csv`, 536 s)

- **WOT is healthy:** raw 214-216, processed 201-204, **CAN TPS 245 (= full) to
  the TCU**, zero TPS-fault frames, pulls to 6519 rpm, O2 186-191 (rich),
  injection 3450-3830, angle 13-28 deg BTDC. P0123 did not re-trip.
- Learned closed 12.5-13, CAN TPS 32 at every closed throttle, idle ~776 rpm.
- **4 cut episodes, all pattern 6 (one frame caught stage index 9), -20.6 deg
  BTDC, O2 bytes drop to 2-4 in the cut** (fresh air from the three dead
  cylinders reaching the sensors). Owner: "definite pops on at least one".
- The long one (t=353 s): 3432 -> 3056 rpm over ~3 s at 66 -> 59 km/h (gear held)
  — almost certainly the audible one. The other three lifts from 4500-6500 rpm
  fell through 3000 rpm within ~1 s (converter unhooks / upshift), so the cut
  lasted a frame. Window, not mechanism, is now the limit: lower the 3008 rpm
  resume (and the PUC_3 axis top breakpoint `0x875C`) toward ~2200 for longer
  pops; hold 2/L on the road.

## Flashed 2026-09-19 ~21:42 — `..._paddock_pops_wide` (verified)

`build_final.py` + `build_wide.py` (docstring has the full list): pop window
bottom 3008 -> **2016 rpm** (resume tables 94 -> 63, PUC_3 5th cell -> 6), PUC
ignition 1600 cell -> 0, A272 cols 0/1 rows 2200-3000 -> 138, dashpot hold-open
row 2240 -> 0x40, and **`0x8338` back to stock 64**. Read-back
`readback_cal_wide.bin` == image (cal `c4c7c6d7f404f210`).
**This is the cal on the car for Sunday 2026-09-20.**

### Revert after the event (owner: "reverting to a healthy tune after tomorrow")
Cal-only flash of `roms/tunes/burble/cal_ca654019_ghostcam_burble_v2_UNFLASHED.bin`
(ghost cams + burble v2, the pre-event daily cal) — the patched program stays
and is inert with it (`0xBC91` = FF). Its TPS bytes are stock, which is right
now that the sensor reads 13 closed / 214 open. Optional keeper from today:
`C_N_MIN_DHP` `0x8238` = 255 only matters with a cut enabled; burble v2 has the
cut unreachable, so nothing from today needs carrying over.

## Test drive on `wide` — 2026-09-19 21:41 (`log_drive_2026-09-19_214121.csv`, 380 s, in D)

Healthy: no TPS faults, learned closed 12, idle ~778, CAN TPS 237 at processed
192. Three cut episodes, all now *below* the old 3008 floor (frames at 2308,
1905, ~1700 rpm; -19..-20 deg) — the wider window works. But two of the three
frames show applied index **4** (= stock `PUC_1`, one injector) rather than 6:
the two hard-coded 11-cycle entry stages (`PUC_1` = 4, `PUC_2` = 9 at every
rpm, cal `0x99D0`/`0x99D6`) take ~0.5 s at 5000 rpm but ~1.1 s at 2300 rpm, and
in D the converter lets rpm fall 3400 -> 1900 in about a second, so most of a
D-range lift is spent in the entry stages. Cal-only lever: set `PUC_1`/`PUC_2`
cells to 6 so the pattern runs from the first cycle (note: the entry stages are
not behind the arm latch, so unarmed lifts would get 22 cycles of pattern 6
before the stock all-six cut). Stage length itself is program code
(`0x14508`/`0x1454A`).

## Flashed 2026-09-19 ~22:05 — `..._paddock_pops_instant` (verified) — FINAL FOR SUNDAY

`build_instant.py`: wide + `ID_PAT_INH_IV_PUC_1`/`_2` (`0x99D0`-`0x99DB`) all
-> 6, so the three-cylinder pattern runs from the first cycle of every cut.
Read-back `readback_cal_instant.bin` == image (cal `a6800ec551104a02`).
**This is the cal on the car for Sunday 2026-09-20.** Untested on the road as of
the flash (owner called it a day). Build chain: paddock-pops/build.py ->
build.py (tpsceil) -> build_dhp -> build_loud -> build_loud_air ->
build_loud_air2 -> build_final -> build_wide -> build_instant.
Revert after the event: cal-only flash of
`roms/tunes/burble/cal_ca654019_ghostcam_burble_v2_UNFLASHED.bin`.
