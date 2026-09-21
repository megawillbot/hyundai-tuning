# Next capture — session briefing

Updated **2026-09-02**. Supersedes the earlier 5-minute remap routine; its open
goals (road-speed scale, MAF/injection scaling) are folded in below.

Two jobs in one drive:

1. **Validate the PUC map** — [[puc-overrun-map]] locates the overrun fuel-cut
   tables by structural inference. Nothing has confirmed them against the running
   engine. This drive decides whether a pop & bang tune is viable at all.
2. **Finish the logger remap** — road-speed scale and MAF/injection scaling are
   still open in [[logger-remap-ca654019]].

**Read-only session. Nothing gets flashed.** Cable is for logging only.

---

## Pre-flight

- Laptop, OBD cable on **COM7**, engine at **full operating temp** (the fuel-cut
  resume point is coolant-dependent — a cold engine gives the wrong answer).
- **The car currently has Ghost Cams flashed** (`roms/tunes/ghostcam_ca654019_2026-08-31.bin`),
  not stock. Idle is deliberately loping and a misfire CEL is expected — that is
  [[ghost-cams]] behaviour, not a fault, and not something to chase today. It is
  idle-region only so it does not affect overrun, but it does make the ~1250 rpm
  region noisy, which is exactly where fuel comes back. Keep that in mind if the
  resume point looks smeared.
- Connection: **ignition ON, engine off** to start. If reads start failing with
  security-access errors, power-cycle the ECM — ignition OFF, wait 15-20 s for the
  main relay to drop, ignition ON.

## Start the logger

From the repo root. `raw_logger.py` sets `PYTHONUTF8` and its own working
directory internally, so no ceremony needed:

```powershell
.venv\Scripts\python.exe -u tools\raw_logger.py
```

Writes `tools\GKFlasher\log_raw_<timestamp>.csv`, flushed every 10 frames.
Drop-safe — worst case you lose the last <10 frames, so just park and stop when
done.

**Do not touch the laptop while driving.** It runs unattended; that is the whole
point of the flush-every-10-frames design. A passenger to call out speeds is
ideal but not required.

## The routine

Each step needs only ~15 s. Order does not matter except that #1 comes first.

| # | Maneuver | What it settles |
|---|----------|-----------------|
| 1 | **Warm idle**, ~20 s | baseline; confirms full temp |
| 2 | Hold **exactly 50 km/h** ~15 s, then **80 km/h** ~15 s | road-speed byte -> km/h scale (2 points) |
| 3 | Hold **100 km/h** (open-road) ~15 s | cruise rpm — the 2496 threshold margin |
| 4 | **One clean pull**, low gear, ~1500 rpm to as high as is safe | MAF + injection at max; O2 rich |
| 5 | **2-3 full lifts from ~3500 rpm** (4000+ ideal, ~3000 the floor — the mask axis tops at 2496, so the whole mechanism lives below that; keep margin above it), **foot completely off the pedal**, **gearbox held in 2 / manual** so engine braking keeps rpm up through the coast (in D the converter unhooks and rpm free-falls to ~1500 in ~2 s — see the 2026-09-03 run below) | **the main event** — fuel cut and resume |
| 6 | **One gentle lift from ~2000 rpm**, coasting | contrast case: should show *no* cut region |
| 7 | Back to idle, stop logger | — |

**Step 5 is the one that matters.** All three existing logs miss it entirely — none
contain a single frame with the engine turning and all six injectors off, so the
map is still unvalidated. Throttle must come **fully** off; a trailing throttle
keeps fuel flowing and produces another useless log.

Pick a road where a pull to 4000+ and a long closed-throttle coast are safe and
legal. Steps 4 and 5 chain naturally — pull, then lift and let it coast.

## Note down

- The exact **speedo readings** you held in #2 and #3.
- Roughly the **peak rpm** of the pull in #4.
- Anything audible on the coastdowns (there should be nothing yet — useful as a
  before-reference if we do proceed).

## What I check afterwards

Explicit predictions, so this is falsifiable rather than a fishing trip:

| # | Prediction | If it fails |
|---|---|---|
| A | On the 4000+ coastdowns, injection-time pairs at **pos 43-54** all drop to **0** | No cut at all -> map is wrong, or PUC is inactive on this cal. Either way the pop tune route is dead and we stop. |
| B | They return to non-zero at **~1248 rpm** | A different resume rpm means `IP_N_MIN_PUC_AT` @0xA91F is mislocated |
| C | The pairs drop in **stages: one injector, then four, then all six**, within a few engine cycles of the cut starting (code-verified sequence, [[puc-overrun-map]]) | **Confirms the pop patch's mechanism.** Real staging ⇒ the `M_FD12.7` gate is open and the pattern will be honored (already well-supported by the stock staged indices). All six from frame one would be the surprise case ⇒ direct-`[0xF9BA]` contingency. Also settles the bit-to-cylinder order. |
| D | Cruise at 100 km/h is **~2250 rpm** | Recomputes the margin under the 2496 threshold |
| E | Speed byte at 50/80/100 tracks **1:1 with km/h** | Last unverified link in the threshold reasoning |

A and C are the ones that decide whether this goes any further. C now also feeds
the program patch in [[program-zone-plan]] §4 (which injectors a partial pattern
will leave firing).

## Quick reference

Addresses in our cal, if you want to look while you are in there. **Read only
today** — all are inside the checksummed zone 0x8000-0xD780, so any future write
needs `--correct-checksum` before flashing ([[ghost-cams]] has the procedure).

| Table | Address |
|---|---|
| `IP_N_MIN_PUC_AT__TCO__GR_MT` (resume rpm) | `0xA91F` |
| `ID_PAT_INH_IV_PUC_1 / _2` (injector masks) | `0x99D0` / `0x99D6` |
| `IP_IGA_PUC_AT__N` (overrun timing) | `0xA198` |
| rpm axis for the masks (704...2496) | `0x8757` |

Logger channel positions ([[logger-remap-ca654019]]):

| Channel | Pos |
|---|---|
| Coolant | 4 (`0.75a-48` C) |
| TPS | 11 (**closed throttle is raw 33-36**, not 0) |
| Road speed | 19 |
| Engine RPM | 20-21 (16-bit LE) |
| Per-cylinder injection | 43-54 (6x 16-bit LE) |

## Measuring the M_FD12.7 gate directly (added 2026-09-03)

The pop patch's pattern is honored only while `M_FD12.7` is set (= `M_FD38.0`
clear = ADC channel `[0xFA84]` below ~196/1024). To measure how often that gate
is open:

- **The existing logs cannot answer it.** They are the ECU's fixed RDBLI 0x01
  sensor block — the internal flag word `M_FD12` (`0xFD12`) and the raw ADC
  `[0xFA84]` are not (confirmably) in it, and more fundamentally `drive_raw_2026-08-29`
  never entered overrun fuel cut at all (max 3347 rpm, no closed-throttle-high-rpm,
  zero all-injectors-cut frames). No cut ⇒ nothing to observe. (Log byte **pos 61**
  does track warm-vs-cold/running — 0 below ~62 °C/idle, 3 when warmed and driving —
  a candidate status byte, but not the gate.)
- **Direct read via KWP `0x23` ReadMemoryByAddress** on `0xFD12` (bit 7 =
  `M_FD12.7`) and `0xFA84` (the ADC channel, 10-bit), polled alongside rpm/coolant/
  TPS. This is how TunerPro ADX reads live RAM; our `0x23` path already works for
  the calibration read. **First verify `0x23` reaches RAM** (read `0xFD12` at warm
  idle, expect bit 7 set), then a short drive with a few overrun lifts shows: how
  often the gate is open, whether it ever closes while warm, and what `[0xFA84]`
  tracks (correlate with coolant/load). Fold into the capture run.
- **You may not need it:** the gate is open in normal warm overrun by construction
  (stock staged indices require it), so the capture's staging observation already
  confirms the mechanism. The direct read is for curiosity / edge-case confidence.

## Run 2026-09-03 (`log_raw_2026-09-03_1433.csv`, 4369 frames, ~16 min, city)

**Result: inconclusive — no fuel cut occurred anywhere in the log, and the log
shows why.** Predictions A/B/C are untested, not falsified. Coolant was 85-86 C
through the relevant part, so temperature was fine.

- **Foot-off while moving reads TPS raw 34-36** — the same as parked-closed.
  Verified on the roll to a stop at t~750 s (35 -> 4 km/h, TPS 45 -> 34-36).
  So the TPS byte is a reliable closed-throttle indicator on the move.
- **The big lift (3776 rpm peak, t~795 s) never had a closed throttle.** TPS
  bottomed at 57-63 during the decel — partial pedal, not sensor drift. Across
  the whole drive there is **no frame** with wheels turning, rpm > 1500 and
  TPS <= 45. The ECU never saw the entry condition.
- **The automatic collapses the window.** On that lift, rpm fell 3582 -> 2073
  in ~2.3 s while road speed stayed 33-36 km/h: in D the converter unhooks and
  the engine drops toward idle regardless of road speed. Even a perfect release
  in D gives ~2 s in the cut band. Hold 2 / manual for the coast.
- The one truly foot-off window (t~750 s) was already at 1185 rpm and falling
  — below the predicted 1248 resume — so no cut is expected there, and none
  was seen (injectors 510-780). Consistent, but not a test.
- Borderline near-miss at t~688 s: TPS 42-45 (not clearly closed), rpm
  1278 -> 1190 over ~4 s at 40 -> 36 km/h, injectors stayed ~470-520. Sits
  right on the resume threshold, so not diagnostic either way.
- Speed holds captured (raw byte, ~8 s+ each): 57, 60, 45, 38, 33. Speedo
  readings not noted — ask before using for prediction E.

**Next attempt:** a stationary pre-check first (rev to ~3500 in P, snap fully
off; if cut works at all, injector zeros should appear even there), then the
road lift in 2 with foot fully off.
