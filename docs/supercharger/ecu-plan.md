# ECU side — what we can actually change

Our working def `defs/ca654019 2700.xdf` has **42 tables / 13 constants**. The
reference `ca652048 2700.xdf` in the mirror has **725 / 922** — it does not share our
addresses, but it is the inventory of what functions exist in a SIMK43 2.7. If a
boost-relevant function is missing from our def, look there first for its internal
name, then find it in our bin.

## Tables in our def that matter under boost

| Address | Table | Why |
|---|---|---|
| `81B8` | MAF Max | The airflow clip. First thing boost breaks |
| `84B6` | MAF MAX DIAG | Diagnostic ceiling → MIL |
| `B638` | 16x16 16bit MAF Definition | Sensor transfer function |
| `AAEE` | Injection Dead Times | Mandatory rework if injectors change |
| `80A2` | Injection Time Multiplier | Global fuel scaling |
| `D3A8` | 12x16 16bit Closed Loop Pulse Width | Main fuel table |
| `AD0B` | WOT Enrichment | **1-D f(rpm)**, not 12x16 (`IP_TI_FL__N`) — see repo README |
| `9A72` | WOT TPS Trigger | **1-D f(rpm)** (`ID_TPS_FL__N`). When the ECU leaves closed loop |
| `A272` | 16x12 8bit Ignition Table | Where the 3700–4000 rpm trough lives |
| `8222` / `8230` | RPM soft / hard limit | Leave alone. A blown 2.7 has no reason to rev higher |
| — | MAF Calibration Patch E46 330ci | Prebuilt patch for a larger BMW MAF. **Read this first** |

## What is *not* in our def

No boost-specific functions — no boost target, no wastegate/bypass logic, no
compressor-referenced load axis. That is expected: this is a naturally-aspirated
calibration and a supercharger is a mechanical device the ECU never knows about
directly. Everything is done through **airflow, fuel and timing**, which is why the
MAF ceiling is the whole game.

Variable intake manifold tables exist on this platform but are **missing from our
XDF** (`ID_VIM__N_32_VIM__TPS_VIM`, `C_N_HYS_VIM` in `ca652048`). A blower changes what
the VIM should be doing. Worth locating if the build ever gets past scoping.

## Order of operations (nothing here is scheduled)

1. **Baseline logs on the stock tune.** WOT pulls, logged: RPM, MAF, TPS, injector
   duty, ignition advance, knock/retard, coolant, IAT. This is the reference every
   later comparison depends on, and it costs nothing to collect now.
2. **Answer the 3700–4000 rpm trough question** from those logs. If it's knock, the
   whole boost plan changes. If it's transaxle torque limiting, the plan is a
   transaxle conversation.
3. **Read the E46 MAF patch** in our XDF — understand exactly what it moves before
   deciding whether a larger MAF is the path.
4. **Establish the MAF headroom**: where `81B8` clips, where the stock sensor's own
   transfer function flattens, what the logged peak actually is NA.
5. Only then decide a hardware bracket ([`hardware.md`](hardware.md)).
6. Fueling changes, if any, one at a time — dead times and multiplier together, then
   pulse width, then WOT enrichment. Checksum, flash, log, commit each.
7. Timing last, and only with knock feedback in the log.

Steps 1–4 are all read-only or offline. **They can be done now, without buying
anything**, and they are what turns this folder from speculation into a decision.
