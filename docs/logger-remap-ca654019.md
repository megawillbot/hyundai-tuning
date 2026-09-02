# Logger channel remap — ca654019 (RDBLI 0x01 block)

Derived from `logs/drive_raw_2026-08-29.csv` (raw ReadDataByLocalIdentifier(0x01)
block, 103 bytes/frame, cold-start city drive). Byte positions are 0-based into
the raw block. The stock GKFlasher `flasher/logging.py` positions are for
**ca663056** and only the early bytes happen to align on our car.

## Confirmed
| Channel | Pos | Size/Endian | Conversion | Evidence |
|---|---|---|---|---|
| Battery voltage | 1 | byte | `a*0.10159` V | aligned w/ old def, sane 12–14 V |
| Coolant temp | 4 | byte | `0.75a-48` °C | clean 24→76 °C warmup ramp |
| Oil temp | 6 | byte | `a-40` °C | plausible, slow rise |
| Throttle (TPS) | 11 | byte | `a*0.468627` ° | 0→82°; carries the ~11° zero offset (modified IAC / worn TPS) |
| **Engine RPM** | **20–21** | **16-bit LE** | **raw = RPM** | 0 engine-off, 767 warm idle, 1200 cold idle, confirmed linear to **4095** (neutral rev hold) |
| **Road speed** | **19** | byte | likely km/h direct (TBD scale) | **stayed 0 through stationary neutral revs 1k→4k, nonzero only when moving** (run2) |

## Strong candidates (need a targeted capture to confirm scaling)
| Channel | Pos | Notes |
|---|---|---|
| MAF / airflow | 8 | byte, ~0 at idle, **rises with RPM during stationary neutral revs** (2800→15, 3934→23) → airflow, not speed |
| 4× O2 sensors | 29, 31, 33, 35 | four channels (matches the 4×O2 car), swing with load; scaling TBD |
| Per-cylinder injection time | 43-44, 45-46, 47-48, 49-50, 51-52, 53-54 | six 16-bit LE pairs, idle ~565 → pull ~2660 (6 injectors) |
| MAP / vacuum (inverse) | 80–81 | high at idle, →low under load |
| Load-related | 14, 62, 90 | move with load/RPM; scaling + exact meaning TBD |

## Confirmed via run2 (2026-08-29, `logs/drive_raw_2026-08-29_run2.csv`)
Stationary neutral rev-holds at 1k/1.5k/3k/4k separated **road speed (pos19)** from
**airflow (pos8)** — pos19 stays 0 while parked+revving, pos8 climbs with RPM.

## Do not use `logs/drive_2026-08-28.csv`

**Flagged 2026-09-02.** That decoded CSV carries the **ca663056** channel names, not
ours, so it looks trustworthy and is not. `Vehicle Speed` reads flat zero for the
whole log, `Engine Speed` maxes at 190, `Camshaft Position` is a constant 60 and
ignition timing sits around -73 deg. Same root cause this whole document exists to
fix. Use the **raw** CSVs with the positions above; treat the decoded one as
unusable until re-decoded with this map.

## Still open
- Road-speed **scale** (need a steady known speedo speed to confirm km/h). Now also
  gates a conclusion elsewhere — the 2496 rpm threshold margin in
  [[puc-overrun-map]] assumes pos 19 is km/h direct.
- MAF/injection **scaling** and a >4k-RPM point (a road pull would give it).
- **Closed throttle is TPS raw 33-36, not 0** (the ~11 deg offset). Anything keying
  off closed throttle needs that.
- Neither existing raw log contains a **fuel-cut event** — no frame with the engine
  above 500 rpm and all six injectors at zero. See [[next-capture-script]].

Analysis scripts: `tools/remap_analyze*.py`, `tools/remap_dump.py`,
`tools/remap_validate.py` (all read-only, operate on the raw CSV).
