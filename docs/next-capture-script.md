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
| 5 | **2-3 full lifts from 4000+ rpm**, throttle fully released, coast to idle in gear | **the main event** — fuel cut and resume |
| 6 | **One gentle lift from ~2000 rpm**, coasting | contrast case: should show *no* cut region |
| 7 | Back to idle, stop logger | — |

**Step 5 is the one that matters.** Both existing logs miss it entirely — neither
contains a single frame with the engine turning and all six injectors off, so the
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
