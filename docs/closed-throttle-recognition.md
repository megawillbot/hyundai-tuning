# Closed-throttle recognition — how the ECU decides the pedal is off

Written **2026-09-03** from the program disassembly (`ca654019`, listing via
`tools/c166/c166dis.py`) and `log_raw_2026-09-03_1433.csv`. Motivation: the
road lift that day never produced a fuel cut, the parked TPS reading wandered
31-51 raw, and the car runs an **IACV restrictor plate** (owner-fitted), which
forces the throttle stop open and is the likely origin of the ~11 deg closed
offset noted in [[logger-remap-ca654019]].

## The mechanism (code-verified)

RAM cells (all bytes unless noted):

| Cell | Meaning |
|---|---|
| `[0xFA96]` & 0x3FF | TPS ADC, 10-bit |
| `[0xF498]` | raw TPS, 8-bit (ADC >> 2). **This is what the logger's pos 11 shows.** |
| `[0xF49D]` / `[0xF4C6]` | debounced raw (8-bit / 10-bit): updated only when the ADC moves by more than `C_TPS_HYS` (`0x8592` = 2); a jump >= `C_TPS_GRD_MAX` (`0x832D` = 53) needs a second pass to be accepted (`M_FD0A.10`) |
| `[0xF4C0]` (word) / `[0xF4C1]` (its high byte) | **learned closed position**, 8.8 fixed point |
| `[0xF496]` | **processed TPS = debounced raw − learned closed**, saturating at 0 (helper `0x2FFF4`) |
| `M_FD0A.12` | closed-throttle flag: `[0xF496] < C_TPS_IS` (`0x8335` = **3**), set at `0x13FC4` |
| `M_FD46.0` | "throttle open" — same test at `0x1400C`; drives the overrun exit at `0x1C52E` |

TPS processing function: file `0x13E80`-`0x13FFC`. Diagnostic substitutes:
TPS fault (`M_FD52.0`) -> modelled TPS from MAF/rpm (`[0xC1A9]`); `M_FD52.2`
-> `C_TPS_SUB_DIAG` (`0x833C` = 54).

### Learning the closed position (`0x14160`)

Runs every TPS cycle but does nothing unless **`M_FD0A.12` is already set**
(and no TPS fault). Then:

1. `[0xF4C0] += (debounced_raw − [0xF4C0]) × C_TPS_AD_CRLC/256` — a low-pass
   filter toward the current reading, coefficient `0x8325` = 51 -> ~20 % per pass
   (helper `0x44628`).
2. Upward movement is clamped to `previous + C_TPS_ADD` (`0x8326` = 6) per pass.
3. Clamped at `C_TPS_MAX_IS` (`0x8338` = 64 raw, ~30 deg): a closed position
   above that resets to 64.

So the learned value **tracks the closed reading in both directions, but only
while the reading is within 3 counts of it**. A reading that steps up by more
than ~2-3 counts leaves the closed window; the flag drops; learning stops; the
ECU now believes the throttle is open by that amount, indefinitely.

### Key-on (`0x141E0`)

The learned value is restored from the non-volatile record (page-3 pointer
`[0x34F4]`, bytes +0x5E/+0x5F, checksum word +0x60 — see [[ecu-architecture]]
§6). If the current raw reading is *above* the stored value, the stored value
is bumped by `C_TPS_ADD` (6) once. That is the only automatic re-adoption of a
higher closed position; it covers a 6-count (~3 deg) shift per key cycle, not
more. With no valid record (`M_FD0E.6`), closed := current raw + 6.

### Consequences

- Closed throttle == raw within **~3 counts** of the learned value. Warm
  overrun entry (`M_FD1A.6` path, [[puc-overrun-map]] §2) needs it; so does
  idle state (`M_FD14.12`), idle timing, idle-speed control.
- `C_TPS_IS` = 3 is the width of the window. `C_TPS_ADD` = 6 is the per-key-on
  grace. `C_TPS_MAX_IS` = 64 is the ceiling for the learned position — the
  restrictor-plate offset (~34 raw) sits under it, so the offset itself is
  **not** the problem.

## What the 2026-09-03 log shows

- Parked and foot-off, the raw reading sat at **31-40** during the warm-up and
  the last 8 s of the log, but at **47-51** at every in-drive stop and for the
  first 65 s of the final idle.
- At t = 973 s it stepped **50 -> 34 in one frame** while parked, and the ECU
  changed state in the same frame: ignition bytes 37-42 went 145 -> 191, fuel
  per cylinder 855 -> 624 raw, short-term trims 131/134 -> 118/120, rpm
  805 -> 765, log byte 28 went 15 -> 0 and byte 94 went 3 -> 0.
- Across the whole log, **byte 28 is 0 in 794/797 stationary frames with TPS
  <= 38 and 7 or 15 in every stationary frame with TPS >= 45** (7 while
  moving). It behaves as an engine-state / idle indicator. Byte 94 bit 0 is set
  in a 46-55 band and clear both below and at higher loads — a part-load flag,
  not the idle flag.
- So: with the reading at 47-51 the ECU was in a **drive** state at a standstill —
  no idle control, drive-mode timing, and no possibility of an overrun cut. The
  learned value cannot follow a 15-count step.

**Is it the plate or the sensor?** A 17-count step is ~8 deg of plate. That
much extra air at idle would raise rpm by hundreds; instead rpm *fell* 40 rpm
and fuel fell 27 % when the reading dropped, which is the idle-state transition
itself, not a big airflow change. The reading is bistable (65 s at 47-50, then
steady 31-34), which is the classic worn-track / dirty-wiper TPS signature at
the closed position — the spot the wiper sits on most. A ground/reference
offset under load is the other candidate. Either way it is the **sensor
reading**, not the throttle stop.

## What to do

1. **Sensor first.** Back-probe the TPS signal at closed throttle, warm engine:
   look for a two-level reading (~0.6 V vs ~0.95 V if 5 V / 255 counts), tap the
   sensor, cycle the pedal. Check the sensor ground. A replacement TPS is cheap
   and the restrictor plate does not need to change. After any TPS work the
   learned value re-adopts at key-on (+6) and then filters in, or clears on a
   battery disconnect.
2. **Only if a cal-side crutch is wanted for the pop-tune test:** raise
   `C_TPS_IS` (`0x8335`) from 3 to ~20 counts. Closed would then be "within
   ~9 deg of learned". Side effect: light pedal (up to ~9 deg) is treated as
   closed — overrun cut and idle state on a trailing throttle, which will feel
   like a surge/jerk at very light pedal. Not a keeper. `C_TPS_ADD` (6) only
   widens the key-on grace and does not help a mid-drive step.
3. **Before the driveway free-rev test**, glance at pos 11 at warm idle: it must
   sit at the low level (31-36 today). If it shows 47-50, the ECU is not in idle
   state and the test will fail for the wrong reason — cycle the key (the +6
   grace) or wait for it to drop.

Related: [[next-capture-script]] (2026-09-03 run), [[puc-overrun-map]] §2 (entry
conditions), [[open-threads]].

## Forum corroboration on the TPS (added 2026-09-18, from `reference/newtiburon/`)

The 2026-09-18 test drives confirmed the sensor reads a steady low band at warm
idle (raw 33-35) but jumps to a high band (raw 49-81) when the throttle is
worked and released on a lift — so the cut never sees closed. Forum data backs
this and guides the replacement:

- **Same false-high symptom on record.** `ngm-reflash-issue-suggestions-needed-long.479628`:
  a member's TPS read "49% throttle at cruise" it shouldn't have; cause was
  contamination down the throttle shaft into the sensor. Others in the thread:
  "verify the TPS voltage sweep... faulty telling the ECU more/less throttle
  than you really have" and "double check the power line to the TPS — if the
  reference voltage is wonky the TPS voltage will be wonky... hard to
  troubleshoot." Mechanism for "fine at idle, wrong off-idle": the wiper rests
  on one clean point at idle, but crosses the worn/fouled mid-track on every
  sweep.
- **Brand guidance (chase206, `04-v6-2-7l-6spd-rev-hang-idle-fluctuation.482990`):**
  **TPS = Hyundai/DAC or NTK. Duralast rejected** ("white-labelled low tier,
  won't run well, our ECU is finicky"). MAF = Hyundai/Siemens/VDO/Delphi;
  IACV = Hyundai "HMC". A member who fitted Duralast sensors chased idle/rev-hang
  problems from it. The TPS is the **same part across throttle bodies**, so a
  donor TB carries a usable sensor.
- **Check before condemning:** TPS and IACV harness connectors not swapped (a
  named common Tiburon mix-up), and the TPS 5V reference steady. Then verify the
  new sensor's sweep is smooth (matches the plan to bench-sweep the wrecker
  donor before pulling).

## Donor sourcing (2026-09-19)

**Part number: 35170-37100** (3-pin; aftermarket cross-refs TPS4120 / TH293 /
5S5186). It is the Delta V6 sensor only — no newer superseding number found on
the OEM catalogues. Fitment per the catalogues: Tiburon/Coupe GK 2.7, Tucson JM
2.7 (04-09), Santa Fe SM 2.7 (00-06), Sonata EF 2.5/2.7 (98-05), Trajet 2.7,
Kia Optima/Magentis MS 2.5/2.7 (01-06), Kia Sportage KM 2.7 (05-10).
**Not donors:** Santa Fe CM 2.7 (2006-on, Mu engine — outside the part's
fitment), any 2.0/2.4 four. The 2.0 Beta Tiburon/Elantra/Tucson uses a
different number (**35170-22600**, replaces -23500); physical interchange with
the V6 part is *unverified* — don't assume. The Sirius 2.4 Santa Fe/Sonata uses
35102-38610, also different.

Pick-a-Part NZ stock, 2.7 V6 cars, checked 2026-09-19 (the engine field on the
old eziparts pages is unreliable — it shows "1.8" Tucsons — so confirm under
the bonnet):

| Yard | Car | Year | Odo km | Lot / row | Note |
|---|---|---|---|---|---|
| Christchurch | Tucson JM 2.7 auto | 2006 | 208,041 | lot 860 | the original pair |
| Christchurch | Tucson JM 2.7 auto | 2005 | 234,202 | lot 882 | |
| Takanini (Akl) | Tucson JM 2.7 auto | 2007 | **136,066** | row 366, ACQ256870 | lowest km in the country; in stock since 2026-04-08 |
| Wellington | Santa Fe SM auto | 2002 | 208,689 | lot 197, ACQ254984 | new system says 2.7, old page says 2.4 — check |
| Mangere (Akl) | Kia Sportage KM auto | 2009 | 246,404 | row 738, ACQ259959 | listed "2.5" (no such engine) — may be the 2.7 |
| Mangere (Akl) | Santa Fe 2.7 auto | 2007 | 277,075 | row 475 | CM / Mu engine — not a donor |

Avondale, New Plymouth, Tauranga: no Delta cars. How to re-query: new system
`POST home.pickapart.co.nz/Home/GetVehiclesByBranchID {BranchID}` then
`/Home/LoadVehiclesByBranch {MakeID,ModelID,SeriesID,BodyTypePL:0,BranchID}`
(branches 2 Avondale, 3 Mangere, 4 Takanini, 6 Wellington, 7 Christchurch,
70008 New Plymouth; Hyundai 14, Kia 505); Auckland yards are only complete on
the old `eziparts/Display_Vehicles.asp?MakeID=14|18&LocationID=n` pages.

## 2026-09-19 — new TPS fitted; RAM read overturns the pos-11 assumption

First direct read of the TPS cells over KWP `0x23` (`tools/ram_logger.py`,
read-only; RAM is readable at its segment-0 address in both the reprogramming
and default sessions). Warm idle, new sensor, `log_ram_2026-09-19_130527.csv`:

| Cell | Value at closed throttle |
|---|---|
| `[0xF4C4]` 10-bit ADC | **543** (~2.65 V of 5 V) |
| `[0xF498]` raw 8-bit | **135-136**, rock steady, returns to exactly 136 after every blip |
| `[0xF49D]` debounced | 136 |
| `[0xF4C0]` learned closed | **64.00 — pinned at the `C_TPS_MAX_IS` ceiling** |
| `[0xF496]` processed | **72** (= 136 − 64; needs < 3 for closed) |
| `M_FD0A.12` closed flag / `M_FD46.0` open flag | **0 / 1, always** |

The model in this doc is confirmed cell-for-cell (processed = debounced −
learned on every frame: 173→109, 204→140, 160→96). Pedal to the floor saturates
raw at 255. So the sensor signal is **offset up by ~100 counts (~2 V)**, not
noisy: the ECU can never see closed throttle, the learned value is stuck on its
ceiling, and no overrun cut / idle state via this path is possible. A sensor
swap alone did not change that.

**Logger pos 11 is NOT `[0xF498]`.** It read 41-43 at idle and a repeatable
64-67 on every foot-off decel above ~2000 rpm, sliding to 42 by ~1300 rpm, while
the real raw TPS sat at 136 throughout. It is an ECU-computed, rpm-dependent
quantity (not found in `0xF490-0xF4CF` or `0xFD00-0xFD4F`). Every earlier
conclusion drawn from pos 11 — "bistable sensor", "33-36 = closed", "fails under
load" — was about that quantity, not the sensor. Byte 28 stayed 0 throughout
(even on blips) while `M_FD0A.12` was 0, so it is not the closed/idle flag
either.

Candidates for a pure +2 V offset that still tracks and tops out at 5.0 V:
sensor clocked wrong on the shaft / tang engaged on the wrong side; high
resistance in the sensor ground; wrong-variant sensor or throttle body. Decide
with a multimeter at the connector, key on, throttle closed: signal should be
~0.3-0.9 V, sensor ground < 0.1 V above battery negative, reference 5.0 V.

### Same day, engine off, hand sweep (`log_ram_2026-09-19_130902.csv`)

Key on, engine off: closed = **ADC 542 / raw 135, a hard repeatable floor**
(identical to running, so not vacuum, charging voltage or shaft pull). Opening
by hand climbs smoothly 135 → 162 → 198 → 228 and **rails at ADC 1023 / raw 255
(5.0 V) before or at full open**, held there for seconds. Railing at exactly
Vref rules out a resistive ground fault (that model tops out ~4.7 V); it is the
wiper running off the top of the track — the sensor sits ~100 counts (~40 % of
its travel) too far round relative to the shaft: clocking / tang engagement /
wrong-variant sensor or throttle body. Railing also tripped the ECU's TPS
range fault: processed TPS `[0xF496]` was substituted to 0 for ~23 s
(expect a stored TPS-high DTC from this test).
