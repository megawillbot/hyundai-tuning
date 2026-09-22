# Hyundai Tiburon GK Tuning — 2004 2.7 V6 (auto)

Diagnostics and ECU tuning workspace for the Siemens SIMK ECM, using the
OpenGK ecosystem over K-line with an FTDI KKL cable.

## Warning: the program-zone patches are lightly tested

This repo contains **modified ECU program code** (not just calibration maps) for
the Siemens SIMK43 5WY17, calibration ca654019 / G5J7TS0A, automatic. As of
2026-09-22 the whole of the evidence that it works is:

- one car, one calibration, one ECU hardware revision;
- the first patch (`roms/tunes/puc-final-stage-patch/`, 89 bytes from stock)
  flashed 2026-09-18 and driven for three days including one paddock event;
- the second, larger patch (`roms/tunes/daily-latch-91/`, several table-lookup
  sites redirected to stubs) flashed 2026-09-21 and driven for about a day.

Nothing here has months of road time, a second car, or a bench recovery that we
have actually had to perform. The patches were reviewed on paper (one stack bug
was caught before flashing, see the notes), and every image passes GKFlasher's
checksum check, but "it ran fine for a few days" is the strongest claim anyone
can make. Long-term effects on the catalyst, the engine and the ECU are unknown.
The pops-and-bangs behaviour in particular runs the exhaust hot on purpose.

If you use any of it on your own car: read `docs/program-zone-plan.md` first
(mechanism, risk case, recovery ladder), read the `notes.md` in the tune folder,
check the calibration version matches exactly, keep two verified stock reads off
the car, and do not flash the program zone with upstream GKFlasher; the
`--flash-program` start-address fix is only in
[megawillbot/GKFlasher](https://github.com/megawillbot/GKFlasher). Everything
here is offered as-is, with no warranty of any kind.

## Hardware

- **Cable:** FTDI FT232R KKL (genuine FTDI, VID 0403 / PID 6001) — enumerates as **COM7**
  (check Device Manager if the port number changes after replugging into a different USB port)
- **ECU:** Siemens SIMK (Infineon C167), 4Mbit AM29F400 flash on 2003+ cars.
  Run `--id` against the car to get the exact calibration version before touching anything.

## Software

- [GKFlasher](https://github.com/Dante383/GKFlasher) — cloned at `tools/GKFlasher/` (gitignored). Our fixes
  (program-zone read range, `--flash-program` start address, logger conversions) are on
  [megawillbot/GKFlasher](https://github.com/megawillbot/GKFlasher), branch
  `fix/read-program-range-and-logger-conversions`; the clone tracks it as remote `fork`.
- Python venv at `.venv/` with GKFlasher requirements installed
  (**rebuilt 2026-09-03** from `C:\Python313`; the original base interpreter under
  `AppData` had vanished and every `.venv\Scripts\python.exe` call failed). If it
  breaks again: `C:\Python313\python -m venv --clear .venv` then
  `.venv\Scripts\python -m pip install -r tools\GKFlasherequirements.txt`.
  OneDrive will ask about the mass delete; that is the venv, say yes.
- [TunerPro](https://tunerpro.net/) + XDF definitions from [opengk-simk](https://github.com/opengk-org) for map editing
- [opengk.org](https://opengk.org) — wiki: K-line protocol docs, pinouts, GKFlasher instructions
- [Chase's GK 2.7 chiptuning writeup](https://chase.cc/blog/chiptuning-the-gk-2-7-ecm/) — background on the ECM internals

## This car

Siemens **SIMK43 (5WY17)**, calibration **ca654019 / G5J7TS0A** (auto). Immo disabled.
The public XDF `defs/ca654019 2700.xdf` matches exactly. Full details and the verified
stock backup are in [`docs/car-notes.md`](docs/car-notes.md).

## Running GKFlasher

It must be run **from its own directory** (it loads `gkflasher.yml` from the
current working directory and ignores `-c` in this version), and needs
**`$env:PYTHONUTF8=1`** on Windows or the progress bar crashes before saving:

```powershell
cd tools\GKFlasher
$env:PYTHONUTF8=1
..\..\.venv\Scripts\python.exe -u gkflasher.py --protocol kline --interface COM7 --id
```

**Use `--read-calibration`, not `--read`** — plain `--read` attempts a privilege
escalation we can't do and corrupts the session (see car-notes.md). The calibration
zone holds all the tunable maps.

- `--id` — identify ECU (KWP service 0x1A); do this first, it's read-only
- `--read -o ..\..\roms\stock\stock_YYYY-MM-DD.bin` — full EEPROM dump
- `--read-calibration` — just the calibration zone
- `--flash <file>` / `--flash-calibration <file>` — write (verifies calibration version and asks for confirmation)
- `--correct-checksum <file>` — fix checksums after editing maps
- `--logger` — KWP2000 datalogger

## Repo layout

```
roms/stock/   Untouched factory dumps. Read-only — never edit these files.
              FULL_ca654019_stock_merged.bin = program read + cal read in one 512 KiB
              image; passes --correct-checksum unchanged in both regions.
roms/tunes/   Modified bins, one subfolder per tune with a notes.md changelog.
defs/         TunerPro XDF definition files matching our calibration version.
logs/         Datalogs (before/after each change).
docs/         Notes, wiring, references.
reference/    Mirror of OpenGK wiki + GitHub definitions (see below).
tools/        External tools (gitignored — GKFlasher lives here).
```

## Reference mirror — read this before researching anything

`reference/` is a local copy of everything from [opengk.org](https://opengk.org) and
the [OpenGK-org GitHub](https://github.com/OpenGK-org) relevant to this car, mirrored
**2026-08-30**. **Check here before searching the web** — most questions about this
ECU are already answered offline.

**[`reference/INDEX.md`](reference/INDEX.md) is the annotated index.** Read it first;
it explains what each file is, which ones don't apply to our calibration and why, and
what was deliberately left out.

| Path | What |
|---|---|
| `reference/opengk-wiki/` | 41 wiki pages as MediaWiki source: ECM pinouts, K-line/CAN protocol, GKFlasher instructions, injector/cam specs, VIN and chassis decoding |
| `reference/opengk-simk/XDF/Delta-27/` | All five Delta 2.7 XDFs. **`ca652048 2700.xdf` has 725 tables / 922 constants** vs our 42 — the reference for what functions exist in a SIMK43 2.7 |
| `reference/opengk-simk/XDF/docs/` | Human-readable table listings per calibration |
| `reference/opengk-simk/ADX/` | TunerPro datalogging definitions (ca663056-based — offsets don't match ours, scalings do) |
| `reference/opengk-simk/DBC/` | CAN message definitions, 500 kb/s, 10 ms broadcast |
| `reference/opengk-simk/EEPROMS/` | Six sibling ROM dumps closest to our calibration |
| `reference/ghidra_scripts/` | SIMK4x Ghidra loader, C167 symbol annotations, KWP2000/CCP command sets |

Three things from the mirror that change how you should read the rest of this repo:

- **Our power maps are identical to the European car.** The cal zone differs from
  `ca654019 / G4E7TS0A` (GK, auto, Europe MY04) by only 1.7%, and the ignition table,
  WOT enrichment, WOT TPS trigger, fuel pulse width, MAF max and rev limits are all
  byte-identical. The `J` (Japan) in our platform version buys no separate power
  calibration.
- **`AD0B WOT Enrichment` and `9A72 WOT TPS Trigger` are 1-D f(rpm) tables**, not the
  "12x16" their XDF titles claim. Their internal names `IP_TI_FL__N` / `ID_TPS_FL__N`
  confirm it (`__N` = function of engine speed only).
- **Variable intake manifold tables exist on this platform but are missing from our
  XDF** (`ID_VIM__N_32_VIM__TPS_VIM`, `C_N_HYS_VIM` and friends in `ca652048`).

**Upstream moves.** The `ca654019` XDF was updated 2026-08-29, one day after our
first download. Re-check before any flash:
```powershell
gh api repos/OpenGK-org/opengk-simk/commits --jq '.[0:5][] | "\(.commit.author.date[0:10])  \(.commit.message)"'
```

## Workflow rules

1. **First connection:** `--id` only. Record the calibration version in `docs/`.
2. **Before any flash ever happens:** read the full stock ROM **twice**, compare
   hashes (`Get-FileHash a.bin b.bin`). Only trust a dump when two reads match.
   Commit it, and keep a copy somewhere off this machine too.
3. **Battery:** flash only with a charged battery, ideally on a charger/maintainer.
   A voltage sag mid-write can brick the ECM. Never unplug mid-flash.
4. **One change at a time.** Edit, checksum-correct, flash, datalog, commit.
   Small diffs make it obvious which change caused what.
5. **Calibration versions must match.** A bin built for a different calibration
   (e.g. 652048 vs 654012) is not safe to flash even if it "loads fine".
6. Commit every bin that ever touches the car, with a message saying what changed.
