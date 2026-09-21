# Burble tune (cal-only) — built 2026-09-07, UNFLASHED

`cal_ca654019_ghostcam_burble_UNFLASHED.bin` = the flashed ghost-cam image
(`roms/tunes/ghostcam_ca654019_2026-08-31.bin`) + 99 bytes + corrected cal
checksum (`0xC217` -> `0x901C`, verified current == new). **This file is
calibration-only: everything outside `0x8000-0xFFFF` is `0xFF`** (so is the
ghost-cam file). It must go in with `--flash-calibration` and nothing else;
`--flash-program` or a full flash with it would erase the program zone. Flash
it exactly like the ghost cams ([[ghost-cams]] procedure). Revert = flash the
ghost-cam image back.

## What it changes

| address | table | stock | tune | effect |
|---|---|---|---|---|
| `0xA91F` (42 B) | `IP_N_MIN_PUC_AT__TCO__GR_MT` | 39-50 (1248-1600 rpm) | 255 (8160 rpm) | overrun fuel cut can never engage (state 5 unreachable) |
| `0xA8C4` (42 B) | `IP_N_ACCIN_MIN_PUC_AT__TCO__GR_MT` | 39-50 | 255 | same, for the `M_FD8C.14` variant |
| `0xA184` (16 B) | `IP_IGA_PU_AT__N__TCO` | warm column 75/61/67/85 | rows 80 / 48 / 32 / 32 (all 4 coolant cells alike) | closed-throttle-coasting ignition: -18 / -30 / -36 / -36 deg at 1200/1600/2400/3500 rpm (stock warm: -19.9 / -25.1 / -22.9 / -16.1) |

**Layout (verified 2026-09-07 in the interpolation helper `0x448B6`:
`addr = base + rpm_idx * 4 + tco_idx`)** — the table is **rpm-major**: each
group of 4 bytes is one rpm row across the coolant axis `0x86FF` = 51/77/104/157
raw = -9.75/9.75/30/69.75 C (`(X-64)*0.75`). The first build of this image had
the rows transposed (caught in review, rebuilt). Note the tune is *milder* than
stock at 1200 rpm and only ~11-14 deg more retarded than stock at 1600-2400.

Absolute timing while coasting is base map + this correction; the base map at
its lowest load row sits ~33-42 deg BTDC from 2000 rpm up, so the tune lands
around 0 .. +6 deg BTDC at 2400+ rpm (stock coasts at ~12-20 deg BTDC). Next notch if too quiet: 24 (-39 deg),
floor is 0 (-48 deg); the running angle clamps at -23.6 deg regardless.

## Why this works (code-verified 2026-09-07)

Engine-state machine (`[0xC20B]`, [[ecu-architecture]] §5f, corrected): state 3
is **throttle open**, state 4 is **throttle closed above idle without a cut**
(PU), state 5 is the cut (PUC). The ignition routine at `0x20CB4` dispatches on
the state; in 3 the PU/PUC correction is reset to zero, in 4 it adds
`IP_IGA_PU_AT` (`0x2100A`), in 5 `IP_IGA_PUC_AT`. Raising the resume tables to
255 makes the 4 -> 5 test (`0x1C3DA`: word add `[0xC20F]+[0xC20C]`, so 261 >
any rpm/32) always fail, and the car coasts in state 4 with fuel on and the PU
retard applied. The only other reader of `[0xC20F]` is the state-5 exit compare
at `0x1C588`, unreachable here. Independently reviewed 2026-09-07 (second
agent, from the binaries): all of the above confirmed; extra findings folded
into the caveats below.

## Caveats

- **Needs closed-throttle recognition.** State 4 requires `M_FD46.0` clear,
  i.e. TPS within `C_TPS_IS` (3) counts of the learned closed value. With the
  bistable TPS ([[closed-throttle-recognition]]) the ECU sits in state 3 on
  lifts whenever the reading is in its high band: no retard, no burble, silent
  (and no cut either — same as stock that day). Intermittent until the TPS is
  replaced. Cal crutch `C_TPS_IS` -> ~20 is *not* included: with -36 deg on
  tap it would fire the burble at light cruise.
- **No fuel lever.** Overrun fuel is the base map in closed loop. Expect a
  burble/crackle from late combustion, not bangs.
- **Cat heat.** Front-manifold cat, late burn on every lift. Short runs;
  avoid long downhill coasts.
- Overrun-based lambda/cat monitors simply never run. Eleven code sites are
  gated "only during a cut"; the reviewer did not trace each to prove none
  raises a fault for a missing test window. Watch for a CEL; short run anyway.
- **Fault-mode cut still exists.** Under fault flags `M_FD56.10/11` the ECU
  substitutes `C_N_MIN_PUC_DIAG` (`0x823F` = 63 -> 2016 rpm) for the table, so a
  cut can engage at ~2528 rpm with stock cut ignition. Stock behaviour, no
  hazard, just no burble while a fault is latched.
- State 4 also needs `M_FD24.13` **clear** (set at `0x30484` under an external
  torque demand, cruise-like); with it set the car stays in state 3.
- Misfire monitor: -36 deg at closed throttle is ~11 deg past the stock *cut*
  retard. Its load gate was not located; slow burns could in principle be
  counted. Ghost cams have not tripped it in a week; still, watch for a CEL.
- Engine braking on lift will be noticeably weaker than stock (fuel on).
- Anti-stall: a stock override (`0x210E8`, `IP_IGAB_INF__TCO`) replaces the
  angle below 1536 rpm when rpm is falling fast with the throttle closed; it
  survives this tune and helps.
- Slew: the retard builds over roughly 0.5-2 s per lift (`0xC0EC` rate), so a
  quick blip-and-lift will not reach full retard.
- Idle drop-in: 4 -> 2 at `[0xCEC0]` (= idle target `[0xCEBE]` + cal word
  `0x84AC`, set at `0x23DC8`), unchanged. The 1200 row (-18 deg) is milder than
  stock's -19.9, so the last few hundred rpm are no worse than stock.
- Confirm in a log: ignition bytes 37-42 should fall on a lift and byte 28
  should read 0 at a warm standstill (TPS in its low band).

## Flashed 2026-09-08 — first drive

Flashed cal-only, ECU verify passed, read-back cal zone byte-identical
(`verify_after_burble_2026-09-08.bin`). Coolant reached 74 C. Logger
(`tools/GKFlasher/log_raw_2026-09-08_1112.csv`) ran 354 s / 1580 frames, then
died on a K-line read timeout — the owner's long foot-off lift came after it
stopped, so it is not in the log. Owner: "definitely feel it coasting further
without engine braking". No CEL.

What the log shows (six short lifts, all from <= 2143 rpm):

- **Cut disabled: confirmed.** Injection never dropped below ~3000 raw on any
  lift; the 2026-09-03 log has two lifts where it went to ~0.
- **State 4 entered and the PU retard applied: confirmed.** On every lift the
  ignition byte (pos 37) went 116 -> ~173 within 0.4 s, with fuel on. So the
  closed-throttle recognition worked despite the TPS reading 53-66 raw with
  the foot off (the learned closed value has drifted up with the key cycles).
- **Retard vs stock at matched rpm:** +1.1 deg at 1300-1399, +1.9 deg at
  1400-1499 (median of 30-50 frames each) — exactly what the tables predict
  there (tune -24 vs stock -22.5 at 1400). Also a rough confirmation of the
  0.375 deg/count scale.
- **The catch, automatic-specific:** on a lift the converter unlocks and rpm
  falls from ~2000 to ~1450 within one second, then sits at 1340-1450 for the
  rest of the coast. Top-gear cruise at ~65 km/h-units is 1450 rpm. So in
  normal driving the coast spends almost all its time in the 1300-1500 band —
  the band where this tune is deliberately mild (rows 1200/1600). The strong
  rows (2400/3500, -36 deg) are only reached on a lift in a low gear at high
  rpm.
- Byte 28 read 0 in every frame today, including stationary with TPS 60-66;
  on 2026-09-03 it was 7/15 whenever the cut was reachable. It is *not* an idle
  flag; it looks cut-related. Re-examine before using it again.

Next version, if the owner wants more than a hint at normal speeds: move the
retard down into the 1200/1600 rows (e.g. 1200 -> 58 = -26 deg, 1600 -> 32 =
-36 deg), keeping the 1200 row within the anti-stall net. Do that after a few
days on this version and a CEL-free check.

Logger: add auto-reconnect on `TimeoutException` to `tools/raw_logger.py` —
a single dropped K-line frame ends the whole capture.

## v2 — flashed 2026-09-08 (same day)

`cal_ca654019_ghostcam_burble_v2_UNFLASHED.bin`: v1 with the `IP_IGA_PU_AT`
rows changed to **58 / 32 / 32 / 32** (-26.25 / -36 / -36 / -36 deg at
1200/1600/2400/3500). Only 8 table bytes + checksum (`0x7578`) differ from v1.
Rationale: the first-drive log showed the auto coasts at 1340-1450 rpm, so the
1200/1600 rows are what the ear gets; at 1400 rpm this is ~-31 deg vs v1's -24
and stock's -22.5. At 1200 rpm base map + correction is ~8 deg BTDC (normal
idle timing); the anti-stall override below ~1500 rpm is untouched.
Flashed cal-only, ECU verify passed, read-back cal zone byte-identical
(`verify_after_burble_v2_2026-09-08.bin`). Revert to v1 or the ghost-cam image
with `--flash-calibration`.

`tools/raw_logger.py` now reconnects after a K-line timeout (new csv per
reconnect).

### v2 first drive — log `log_raw_2026-09-08_1134.csv` (289 s, 1290 frames, no reconnects)

- Nine sustained lifts, one of them from 4785 rpm after a pull to 5441.
- Ignition byte on lifts in the 1300 band: median **181** vs 163 (v1) vs 160
  (stock log) = **+7.9 deg over stock**, as the 58/32 rows predict. On the
  high-rpm lift the byte sat 176-187 all the way from 4234 down to 2201 rpm —
  the flat -36 deg rows applied throughout.
- Two "lifts" (t=133 s, t=192 s) show cruise-level ignition (~105) with TPS
  50-70: light pedal in traffic, ECU in throttle-open state 3, so no retard —
  the expected TPS-window behaviour, not a fault.
- No stall, no idle dip: minimum rpm while moving 684; the only sub-600 frames
  are the key-off at t=282 s. Coolant 77 C. No CEL.
- Owner's verdict: as much as traffic allowed; kept v2.
