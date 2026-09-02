# Ghost Cams — applied 2026-08-31

Community patch by **KimchiSpiceWorks**, shipped inside `defs/ca654019 2700.xdf`.
Built to `roms/tunes/ghostcam_ca654019_2026-08-31.bin`. **Flashed and verified 2026-08-31.**

Read-back cal zone is byte-identical to the flashed image:
`65DA7B7F342160450B63EB2D5E737FF146173B5C530EAC4375BD529D0DD11865`
(stock, for comparison: `A8C104...25DFDE6D`). 22 bytes differ from stock — the 20 patch
bytes plus the 2 checksum bytes.

```powershell
.venv\Scripts\python.exe tools\apply_xdf_patch.py "defs\ca654019 2700.xdf" `
  "roms\stock\cal_ca654019_G5J7TS0A_read1.bin" `
  "roms\tunes\ghostcam_ca654019_2026-08-31.bin" "Ghost Cams"
```

## Checksum — do not skip this

`--flash-calibration` does **not** correct the calibration checksum. `cli_flash_eeprom()`
erases, writes, then runs routine 0x02 (verify-blocks / mark-executable) — it never calls
`correct_checksum`. The cal checksum must be fixed **in the file, before flashing**:

```powershell
$env:PYTHONUTF8=1
..\..\.venv\Scripts\python.exe -u gkflasher.py --correct-checksum <file.bin>
```

Checksummed zone on this cal is **0x8000-0xD780**, stored at **0xDEE0**; init value 0x3931.
All three patch regions fall inside it. Ours went `0xE13` -> `0xC217`.

Sanity check the algorithm before trusting it on a tune: run `--correct-checksum` against
the *stock* bin and answer `n`. It should report current == new (`0xe13` / `0xe13`). It does.

All three `basedata` blocks matched our verified stock cal **byte-for-byte**, so this
patch was authored against exactly this calibration — no adaptation needed.

Diff vs stock: **20 bytes**, all within the cal zone, all inside the three target ranges
(`0x90A0-0x90AE`, `0xA12E-0xA134`, `0xA13A-0xA140`). Nothing else moved.

## What it actually does

It converts the idle ignition PID into a **relaxation oscillator**.

`A138 Dynamic IGA corr. in Idle AT` (kf 113a) trims ignition advance as a function of
idle rpm error. Stock it is a smooth proportional ramp through zero:

| rpm error | -240 | -160 | -120 | -60 | -20 | 0 | +20 | +50 | +80 | +120 | +160 | +200 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **stock °** | -30.0 | -30.0 | -25.1 | -18.0 | -10.1 | **0.0** | +10.1 | +16.1 | +18.0 | +19.9 | +19.9 | +19.9 |

Patched, the axis is squeezed to a **5 rpm deadband** and the table becomes a step:

| rpm error | -320 | -240 | -120 | -60 | -5 | 0 | +5 | +37 | +80 | +120 | +160 | +200 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **ghost °** | -30.0 | -30.0 | -22.9 | -22.9 | -22.9 | **+19.9** | +19.9 | +19.9 | +19.9 | +19.9 | +19.9 | +19.9 |

The key line is the `0` column: stock commands **0°** at zero error (settle), ghost commands
**+19.9°** (never settle). Sag 5 rpm → slam +19.9° advance → torque spike → overshoot →
slam -22.9° retard → rpm falls → repeat. That oscillation is the lope.

It is **timing-only** — no per-cylinder fuel cut — so it isn't dumping raw fuel into the
cats, which matters on this 4×O2 car with the integrated-cat front manifold.

Axis `0x90A0` (`sstm_n_dif_kor_6_6`) is referenced *only* by A12C and A138 (verified: no
other table links `0x59A6`), so compressing it has no collateral effect elsewhere.

Both the MT (`A12C`) and AT (`A138`) tables are patched. **This car is an automatic**
(`G5J7TS0A`, `TS`), so `A138` is the live one; the MT copy is inert.

## Expect these

- **Misfire CEL (P0300-family) is likely.** The misfire monitor detects misfires by
  crankshaft velocity deviation. A deliberate idle lope looks exactly like that signal.
  This is the most commonly reported ghost-cam side effect and it is not a real misfire.
- **Automatic-specific:** in D at a stoplight the ±20° swing works against a loaded torque
  converter, so it surges against the brakes rather than just lumping in Park. Nothing here
  conditions the lope on gear selection. Worth deciding whether you like it in gear.
- **Degraded disturbance rejection.** The proportional region is gone, so the controller is
  worse at catching AC clutch engage, power steering lock-to-lock, and alternator load.
  Watch for stalling, especially cold.
- Idle-region only. Nothing above idle is touched, so it is independent of the
  supercharger work — but it will need revisiting once boost changes idle airflow.

Logger RPM is still misaligned on this cal (see `logger-remap-ca654019.md`), so idle rpm
can't be trusted on a datalog yet. The lope is an ear/tach judgement for now.

## Revert

Fastest path is flashing the stock cal straight back (its checksum is already correct):

```powershell
cd tools\GKFlasher
$env:PYTHONUTF8=1
..\..\.venv\Scripts\python.exe -u gkflasher.py --protocol kline --interface COM7 `
  --flash-calibration ..\..oms\stock\cal_ca654019_G5J7TS0A_read1.bin
```

Or rebuild a reverted image with the script (then re-run `--correct-checksum` on it):

```powershell
.venv\Scripts\python.exe tools\apply_xdf_patch.py "defs\ca654019 2700.xdf" `
  "roms\tunes\ghostcam_ca654019_2026-08-31.bin" "roms\tunes\reverted.bin" "Ghost Cams" --revert
```
