# This car — 2004 Tiburon 2.7 V6 auto

## ECU identity (read 2026-08-28 via GKFlasher --id)

| Field | Value |
|-------|-------|
| ECU | Siemens **SIMK43** — GKFlasher `--id` matched the **5WY17** profile; chase206 (OpenGK), comparing program zones, believed the hardware was actually a **5WY18**. Evidence now leans 5WY17 — see [Hardware revision](#hardware-revision-5wy17-vs-5wy18) below. Still not conclusively settled. |
| Calibration description | **ca654019** |
| Calibration version | **G5J7TS0A** (G=GK chassis, 5=MY2005, J=emissions region **Japan**, 7=2.7 engine; `TS`=auto) |
| Bootloader (0x8c) | KR77035202 |
| Program code (0x8d) | KR77035111 |
| EEPROM size | 512 KiB (bin_offset −0x80000) |
| Immobilizer | **Non-immo car** (confirmed via vin.opengk.org) |
| VIN in ECU | blank (0xFF) — normal for 02–04 |

**The public OpenGK XDF matches this car exactly** — `defs/ca654019 2700.xdf` is the
right definition file; no cross-flashing to another calibration is needed. Open a
stock bin in TunerPro with that XDF and the maps line up.

## Provenance & quirks (per chase206 / OpenGK, 2026-08-28)

- **Japan-market import**, now in NZ (Christchurch). VIN **KMHHN61FR5U161849**; production date **2004-11-15**, model year **2005** (late-04 build titled as MY05 — CarJam showed 2004). Sometimes badged **'FX'** (old RD-chassis moniker).
- ca654019 is **rare** — chase had only OEM samples from an EF Sonata and a France (Cedric's) car; both were **5WY18**. This is why he suspects 5WY18 hardware here.
- **Emissions oddity:** the OpenGK VIN DB shows *conflicting* flags — both `[3931] NON SPEED DENSITY` and `[3933] SPEED DENSITY`, and it's a **4× O2-sensor car** (front manifold has an integrated cat). First 4×O2 car chase had seen flagged this way. Possible the car was **emissions-swapped for its market** or the VIN DB is off — NZ imports are messy. Program zone differs slightly vs a 2005 EU ca654019 file.
- Stock calibration bin **shared to the OpenGK repo** (chase confirmed the cal zone contains **no IMMO/keyfob/critical secrets**).

## Our calibration vs the European car — the maps are identical

Established **2026-08-30** by diffing our stock cal zone (0x8000–0xDF40) against
`ca654019 / G4E7TS0A` — same calibration, GK chassis, automatic, **Europe MY04** —
mirrored locally at `reference/opengk-simk/EEPROMS/ca654019_G4E7TS0A_GK27.bin`.

```
cal bytes differing: 407 / 24384 (1.7%)
  A272 ignition table    IDENTICAL
  AD0B WOT enrichment    IDENTICAL
  9A72 WOT TPS trigger   IDENTICAL
  D3A8 fuel pulse width  IDENTICAL
  81B8 MAF max           IDENTICAL
  8222/8230 rev limits   IDENTICAL
```

**Every power-relevant map is byte-identical to the European car.** The `J` (Japan)
in `G5J7TS0A` does *not* buy a separate power calibration.

Consequences for tuning:

- The high-load ignition trough at **3700–4000 rpm** (~4.5° below both neighbours,
  right at the 245 Nm torque peak) is **not** Japanese-regular-fuel margin. It ships
  in a car sold into a 95 RON market. Treat it as the common Delta 2.7 *automatic*
  calibration — most likely transaxle torque limiting or a knock-prone resonance
  region, not octane headroom waiting to be reclaimed.

  > **Resolved 2026-09-02** — see [[full-map-ca654019]] §2. It is **neither**.
  > Transaxle limiting is ruled out: `ca654019_G5E7TM0A`, the **manual**, has a
  > byte-identical ignition map. A knock resonance is ruled out: `ID_FAC_KNK_0` and
  > the knock windows run perfectly smooth through 3700–4000. The dip is
  > load-dependent (0.5° at load 50, **5.2°** at load 330) and WOT enrichment ramps
  > at the same rpm (38 → 53 → 63 → 77). Same dip in the Sonata and Santa Fe cals.
  > It is the knock/thermal limit tracked through the VE peak — engine-wide, both
  > transmissions. The conclusion stands and strengthens: **not headroom.**
- Do **not** assume extra timing is available just because NZ has 98 RON. Any timing
  work needs knock feedback, not an octane assumption.

The 407 differing bytes are 25 scattered singles/pairs in the constants block
(0x8001–0x848D — likely emissions and diagnostic configuration, consistent with the
emissions oddity above) plus four runs at `0xAA7E–0xAA83`, `0xC9B8–0xC9C3`,
`0xD010–0xD057` (70 bytes) and `0xD5E8–0xD707` (288 bytes). **None of those runs are
covered by any table in our XDF** — worth mapping if the emissions question matters.

> **Mapped 2026-09-02** — see [[full-map-ca654019]] §1. **330 of the 407 bytes are
> places where our cal is blank/filler and the EU cal has data; zero bytes go the
> other way.** `0xD5E8–0xD707` is all-FF in ours, `0xD010–0xD057` is `00 10` filler,
> both in lambda-diagnostic territory. Of the 77 real value differences, 17 are two
> **coolant rationality (thermostat) diagnostics** — `IP_TCO_MES_DIF_MIN_DIAG`
> @0xAA7E and `IP_TCO_SUB_DIF_MIN_DIAG` @0xC9B8 — and 2 are the checksum. All
> emissions/diagnostic; nothing power-relevant. Not a read defect: our cal has
> 2618 FF bytes vs 2815–2886 in siblings ca654012/014.

For scale: the EF Sonata build of the same calibration differs by 17.5% of the cal
zone and the SM by 24.2%, with all major maps differing.

## Hardware revision: 5WY17 vs 5WY18

Recorded above as unresolved. As of **2026-08-30** three independent sources say
**5WY17**:

1. GKFlasher `--id` auto-detect: `Found! SIMK43 V6 4mbit (5WY17)` (`logs/program_read.log`)
2. The OpenGK repo's GK-27 ca654019 dump is named `..._5WY1708B_...`
3. The OpenGK repo's EF-27 ca654019 dump is named `..._5WY1785D_...`
4. GKFlasher's checksum `detect_offsets()` — a *separate* mechanism from `--id`, keyed on
   calibration-zone layout rather than the ECU's ID response — reports `v6 (5WY17)`
   (observed 2026-08-31 during the ghost-cam flash).

Both repo filenames encode `5WY17`, which is the opposite of the note above that
chase's EF and France samples "were both 5WY18". Either the filename convention
differs from what he was reading, or his 5WY18 samples were never uploaded.
**Worth putting to him directly** — it's the last open question on our hardware.

> **Closed 2026-09-02** — see [[full-map-ca654019]] §4. Across 26 archived
> calibrations the ECM family tracks the calibration number exactly, and the
> boundary falls at ours: **ca654011/012/014/015/019 are all 5WY17; ca654020 and
> everything after are 5WY18.** ca654019 is the *last* 5WY17 calibration. Every
> archived ca654019 file is 5WY17 — the European GK is `5WY1708B`, the EF Sonata is
> `5WY1785D`. Those are the two samples chase cited for 5WY18; the files say
> otherwise. That is a fifth independent line of evidence. Likely explanation for
> his recollection: ca654020+ cars *are* 5WY18, one calibration step away.
Wiki pages for both revisions are mirrored at
`reference/opengk-wiki/Siemens_5WY17_PCB_Components.wiki` and
`Siemens_5WY18_V2_PCB_Components.wiki`.

> **Corroborated 2026-09-03** by a sixth, independent source: the OpenGK
> `5WY_ECM_Identification` wiki maps calibrations to revisions directly —
> **ca654011/012/014/015/016/019 = 5WY17** (2003–2004, 4Mbit AM29F400),
> **ca654020/021 = 5WY18 v1** (2005), **ca654024/025 = 5WY18 v2** (2006). ca654019
> is 5WY17, unambiguously. (This also adds ca654016 to the 5WY17 set, which the
> archived-bin survey missed.)
>
> **And it explains chase's 5WY18 prior.** chase's own writeup car is a **2006**
> GK 2.7 — which the same table places at **ca654024/025 / 5WY18 v2**. His daily
> and his newest OEM samples were genuinely 5WY18; ours (a late-2004 build) is the
> last 5WY17 calibration, one step earlier. Nobody was wrong about a part number;
> the two cars are simply a model year apart across the 5WY17→5WY18 boundary.

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

## Owner modifications (hardware)

- **Intake resonator removed** (reported 2026-09-19) — the stock airbox now
  draws cold air from the fender. MAF-metered, so fuelling follows it; no cal
  change needed. No header or exhaust work.
- **Fuel: 91 RON** as of 2026-09-19. The cal is a 95 RON calibration (above),
  and the WOT logs of 2026-09-08 and 2026-09-19 both show knock control pulling
  3-6 deg on individual cylinders above 2500 rpm. First power step is 95/98 in
  the tank, then re-log; no ignition advance before knock control is quiet.

- **IACV restrictor plate** fitted (confirmed 2026-09-03). Idle air is
  throttled, so the throttle stop is set open: closed-throttle TPS reads ~31-36
  raw (~11 deg) instead of ~0. Handled by the ECU's learned closed position
  ([[closed-throttle-recognition]]); the problem seen on 2026-09-03 is a
  bistable TPS reading (31-36 vs 47-51), not the offset itself.
