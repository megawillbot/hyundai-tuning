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

## Findings from `log_raw_2026-09-03_1433.csv` (2026-09-03, 4369 frames, 4.46 fps, warm idle -> city)

Correlation sweep of every byte against rpm / TPS / speed / coolant / injection,
then linear fits on the candidates. Numbers are fits on this log, not decoded
scalings.

### Resolved (high confidence)
| Channel | Pos | Evidence |
|---|---|---|
| **Bank injection time x2** | **55-56, 57-58** (16-bit LE) | `= 1.00 x mean(pos43-54)` (r=0.998), same units as the per-cylinder pairs. Bank 1 / bank 2 averages. |
| **Injection-derived x2** | **14-15, 16-17** (16-bit LE) | `= 7.2 x mean injection - 280` (r=0.99), range 1867-20269. Two copies -> per bank. Different unit or pre-correction value; not yet decoded. |
| **Airflow, 16-bit** | **12-13** (16-bit LE) | `= 7.86 x pos8 + 68` (r=0.96), range 42-975. Higher-resolution copy of the pos 8 airflow byte (pos 8 ~ this/8). Looks like a 10-bit ADC or mass-flow word. |
| **Airflow + offset** | 7 | `= pos8 + 13` exactly (r=1.000). Redundant with pos 8. |
| **Coolant, inverse scale** | 3 | `= 192.6 - 1.51 x coolC` (r=-0.998). Sensor-side (NTC voltage) copy of pos 4. |
| **Fuel trims, 2 banks** | **62, 63** (short-term), **64, 65** (long-term) | All centred on 128: means 127 / 132 / 127 / 132. 62/63 wander more (sd 8) than 64/65 (sd 6). Bank 2 sits ~+3% on both. |
| **Speed byte is linear** | 19 | rpm/speed clusters at **24 / ~34-38 / ~56 / ~100-108** — ratio ladder 1 : 1.4-1.6 : 2.3 : 4.2, matching the 4-speed auto's 0.712 : 1.0 : 1.529 : 2.842 (1 : 1.40 : 2.15 : 3.99) once converter slip in 1st/2nd is allowed for. Top gear = **24 rpm per km/h-unit**. Absolute km/h still needs speedo readings (or final-drive + tyre size). |

### Candidates (pattern clear, meaning/scaling open)
| Pos | Behaviour | Guess |
|---|---|---|
| **37-42** | six bytes, identical in 96% of frames; idle 166, WOT (~2900 rpm) 132, light cruise 2k 103 | per-cylinder ignition angle, decreasing encoding (cruise most advanced). 0.375 deg/bit would give ~24 deg idle-to-cruise spread, plausible. Datum unknown. |
| 79 | idle 22, cruise 116, WOT 197; loosely `2 x pos8 + 56` | engine load (%-of-max style) or MAP |
| 80-81 (16-bit LE) | idle ~24200, cruise ~650, WOT ~0, max 65534 | inverse-load with huge range; a period/time or vacuum-like quantity, **not** a plain MAP |
| 59 | idle 50, cruise 36, WOT 39; r=-0.90 vs TPS | inverse with load; not MAP (WOT would be extreme) |
| 5 | `= 374 - 2.9 x coolC` (r=-0.96) | second inverse temperature (IAT or oil sensor raw?) |
| 6 | `= 1.88 x coolC - 28` on this log | tagged oil temp `a-40` earlier; rises faster than coolant here, treat the scaling as unverified |
| 76-77 (16-bit LE) | 0-36468, r=0.65 vs elapsed time, resets to 0 | counter/timer or a slow model (cat temp?) |
| 74, 75 | fall with speed (r=-0.74), 58-128 | weak; maybe gear/converter related |
| 90 | 0 when stopped, 135-255 moving, not linear in speed | pulse/flag, not a speed value |
| 29, 31, 33, 35 | no correlation with anything (as expected for switching O2); 33/35 drift with warm-up | front pair 29/31, rear pair 33/35 |
| 61 | 3 for the whole warm log (0 in 38 frames) | status byte, as noted in [[next-capture-script]] |
| **28** | 0 in 794/797 stationary frames with TPS <= 38; 7 or 15 whenever the ECU is not idling (TPS >= 45 at a standstill, or moving) | **engine-state / idle indicator** — the useful one; see [[closed-throttle-recognition]] |
| 94 | bit 0 set only in a TPS 46-55 band, clear below and at higher loads | part-load flag, not idle |
| 11 | **NOT raw TPS** (disproved 2026-09-19 by RAM read: `[0xF498]` sat at 136 while this read 42-67). ECU-computed, rpm-dependent on closed-throttle decel | see [[closed-throttle-recognition]] 2026-09-19; use `tools/ram_logger.py` for the real TPS cells |

### New max points
- Injection per-cylinder **3262** raw at 2812 rpm, TPS 174 (WOT); airflow pos 8 **178** at 2964 rpm. Still no >4k rpm point (peak 3776, at part throttle).
- Likely injection unit: the ca663056 defs in `flasher/logging.py` scale
  `Cylinder Injection Time-Bank1` as `a * 0.004` ms (4 us/bit). Applied to our
  pairs: idle 565 -> **2.26 ms**, WOT 3262 -> **13.0 ms** — both textbook for a
  2.7 V6, so 43-58 are very likely ms x 250. (The x7.2 pair at 14-17 does not
  reduce to a clean unit under that scale; still open.)
- Closed-throttle TPS: parked idle read **31-49** across the session (typ. 40), foot-off while rolling read **34-36**. The "33-36" figure is the floor; anything keying off closed throttle should use <= ~45.

## Still open
- Road-speed **absolute scale** — linearity is now confirmed via the gear ladder
  (above); the km/h factor still needs a speedo reading (2026-09-03 holds at raw
  57 / 60 / 45 / 38 / 33 are usable once the driver's speedo notes are known).
  Gates the 2496 rpm threshold margin in [[puc-overrun-map]].
- MAF/injection **scaling** and a >4k-RPM point (a road pull would give it). The
  bank-level copies at 55-58 and the x7.2 pair at 14-17 may be the same quantity
  in a decodable unit — check against `flasher/logging.py` scalings for ca663056.
- **Closed throttle is TPS raw 33-36, not 0** (the ~11 deg offset). Anything keying
  off closed throttle needs that.
- Neither existing raw log contains a **fuel-cut event** — no frame with the engine
  above 500 rpm and all six injectors at zero. See [[next-capture-script]].

Analysis scripts: `tools/remap_analyze*.py`, `tools/remap_dump.py`,
`tools/remap_validate.py` (all read-only, operate on the raw CSV).
