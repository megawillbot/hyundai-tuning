# Hyundai Tiburon GK Tuning — 2004 2.7 V6 (auto)

Diagnostics and ECU tuning workspace for the Siemens SIMK ECM, using the
OpenGK ecosystem over K-line with an FTDI KKL cable.

## Hardware

- **Cable:** FTDI FT232R KKL (genuine FTDI, VID 0403 / PID 6001) — enumerates as **COM7**
  (check Device Manager if the port number changes after replugging into a different USB port)
- **ECU:** Siemens SIMK (Infineon C167), 4Mbit AM29F400 flash on 2003+ cars.
  Run `--id` against the car to get the exact calibration version before touching anything.

## Software

- [GKFlasher](https://github.com/Dante383/GKFlasher) — cloned at `tools/GKFlasher/` (gitignored; `git pull` it for updates)
- Python venv at `.venv/` with GKFlasher requirements installed
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
roms/tunes/   Modified bins, one subfolder per tune with a notes.md changelog.
defs/         TunerPro XDF definition files matching our calibration version.
logs/         Datalogs (before/after each change).
docs/         Notes, wiring, references.
tools/        External tools (gitignored — GKFlasher lives here).
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
