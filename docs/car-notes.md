# This car — 2004 Tiburon 2.7 V6 auto

## ECU identity (read 2026-08-28 via GKFlasher --id)

| Field | Value |
|-------|-------|
| ECU | Siemens **SIMK43 V6 4mbit (5WY17)** |
| Calibration description | **ca654019** |
| Calibration version | **G5J7TS0A** (`TS` = automatic trans variant) |
| Bootloader (0x8c) | KR77035202 |
| Program code (0x8d) | KR77035111 |
| EEPROM size | 512 KiB (bin_offset −0x80000) |
| Immobilizer | Reported **disabled** |
| VIN in ECU | blank (0xFF) — normal for 02–04 |

**The public OpenGK XDF matches this car exactly** — `defs/ca654019 2700.xdf` is the
right definition file; no cross-flashing to another calibration is needed. Open a
stock bin in TunerPro with that XDF and the maps line up.

## Memory regions (from ecu_definitions.py, this ECU)

| Region | ECU address | Size | File offset (bin_offset −0x80000) |
|--------|-------------|------|-----------------------------------|
| calibration (maps — tunable) | 0x88000 | 0x5F40 | 0x8000 – 0xDF40 |
| program (code) | 0x90000 | 0x70000 | 0x10000 – 0x80000 |

## Stock backup — VERIFIED

`roms/stock/cal_ca654019_G5J7TS0A_read1.bin` and `_read2.bin` are two independent
reads. The **calibration region (file 0x8000–0xDF40) is byte-identical** between them:

```
Cal SHA256: A8C104ACF3D8E58A82CC330C0F40EFD88DD9BC340AA993C5F8AD1E4725DFDE6D
```

The two files' *full-file* hashes differ only in the ~8 KB over-read tail past
0x8DF40 (live adaptive/learned values) — that area is outside the calibration and
is never written back by `--flash-calibration`, so it doesn't matter for backup.

## How to run GKFlasher on this machine (working invocation)

Two Windows-specific gotchas were solved:
1. Must run **from the GKFlasher directory** (it loads `gkflasher.yml` from cwd, ignores `-c`).
2. Must set **`$env:PYTHONUTF8=1`** or the `alive_progress` bar crashes with a cp1252
   UnicodeEncodeError when output is redirected — and the crash happens *before* the
   file is written, so you get no output despite a successful read.

```powershell
cd tools\GKFlasher
$env:PYTHONUTF8=1
..\..\.venv\Scripts\python.exe -u gkflasher.py --protocol kline --interface COM7 --read-calibration -o ..\..\roms\stock\<name>.bin
```

## Reading gotcha: use --read-calibration, NOT --read

Plain `--read` calls the code path with `escalate_privileges=True`, which attempts a
**Siemens-level IOCLID privilege escalation** that requires an OpenGK patch to already
be flashed to the ECM (we don't have it — `0x31 out of range`). The *failed* attempt
issues `StartDiagnosticSession` calls that reset the standard (Hyundai-level) security
access, so every following read block returns `0x33 Security Access Denied` and the file
is padded entirely with 0xFF. `--read-calibration` skips escalation and reads fine.

Full program-zone / full-eeprom reads over OBD2 would need that IOCLID patch (normally
installed via BSL/bench). Not needed for map tuning — all maps are in the calibration zone.

## Connection procedure that works

Ignition ON, engine off. If a read ever starts failing with security-access errors,
power-cycle the ECM: ignition OFF, wait ~15–20 s for the main relay to drop, ignition ON.
