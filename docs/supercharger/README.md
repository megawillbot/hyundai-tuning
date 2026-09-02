# Supercharger planning — ca654019 GK 2.7 auto

Planning folder. **Nothing here has been done to the car.** This is scoping only:
what a blower would take, what the ECU side looks like, and what we don't know yet.

Status: **research / not committed to a build.**

| File | What |
|---|---|
| [`hardware.md`](hardware.md) | Kits, stages, parts. Sourced from the OpenGK wiki mirror |
| [`fuel-and-air.md`](fuel-and-air.md) | Injectors, MAF ceiling, fuel system — the physical limits |
| [`ecu-plan.md`](ecu-plan.md) | Which maps in our XDF actually matter, and in what order |
| `logs/` | Baseline and post-install datalogs (create when there's something to log) |

## Why this car is not the wiki's car

The wiki's supercharger figures are community numbers from **manual** 2.7s, mostly
US-market. Ours is:

- **Automatic** (`TS` in `G5J7TS0A`). The transaxle is the first thing to worry about,
  not the engine. See the ignition-trough note below.
- **4× O2 sensors**, front manifold with integrated cat, conflicting speed-density /
  non-speed-density flags in the OpenGK VIN DB (see [`../car-notes.md`](../car-notes.md)).
- **MAF-based** load calculation with a hard MAF ceiling (`81B8 MAF Max`) — that clip
  is the single biggest ECU-side obstacle to boost on this platform.
- A stock calibration whose power maps are **byte-identical to the European car**, so
  there is no hidden Japan-market margin to reclaim.

The high-load ignition trough at **3700–4000 rpm** (~4.5° below both neighbours, right
at the 245 Nm torque peak) is present in the European calibration too. `car-notes.md`
reads it as most likely **transaxle torque limiting or a knock-prone resonance region**.
Under boost that trough is either a warning about the auto's torque capacity or a hole
in the timing curve exactly where a blower makes its first real torque. Resolve which
before adding boost — it is the top open question of this whole exercise.

## Open questions

1. **Transaxle.** What does the 04–05 auto actually hold? No data in the mirror.
   Ask OpenGK — this decides whether the project is a Stage 0/I "no tune" kit or nothing.
2. **The 3700–4000 rpm trough** — torque limiting or knock region? Needs knock-sensor
   logging on the stock tune first.
3. **MAF ceiling.** Where does `81B8 MAF Max` sit in real airflow, how much headroom is
   in the `B638` MAF transfer function, and does the `MAF Calibration Patch E46 330ci`
   in our XDF mean a larger BMW MAF is the accepted path? (See `ecu-plan.md`.)
4. **Kit availability.** Every kit in the wiki went out of production in the early 2010s.
   Is anything obtainable in NZ, or is this a custom build?
5. **Fuel.** 98 RON is available here. Does that change the answer to (2)?

## Rules this project inherits

Everything in the repo [`README.md`](../../README.md) workflow rules still applies —
one change at a time, verified stock backup, checksum before flash, log before and after.
A boosted tune does not get to skip steps; it gets more of them.
