# Fuel and air — the physical limits

## Injectors

Stock Delta 2.7 injector, per `reference/opengk-wiki/Fuel_Injector_Specifications.wiki`:

| Brand | Part # | Type | Flow @ 45 psi | Impedance | Application |
|---|---|---|---|---|---|
| Kefico / Hyundai | 9260930004 / 35310-37150 | EV6 | 194 cc | 14.2 Ω | 2.0 G4GC Beta 2, **2.7 G6BA Delta** |

The wiki's full injector matrix lists drop-in EV6 alternatives from other makes with
flow ratings and hole counts — that page is the reference when sizing up.

Kit guidance from the forced-induction page: **290cc minimum, 360cc typical** at
Stage II (5–6 psi). At Stage 0/I (2–3 psi, no tune) the stock 194cc injectors are
assumed adequate by the kit vendors. **Verify that with logged injector duty cycle,
not by assumption** — an auto holds load longer than a manual through the midrange.

Changing injectors is not free on this ECU: it needs `AAEE Injection Dead Times` and
`80A2 Injection Time Multiplier` reworked, plus the closed-loop pulse-width table.
See [`ecu-plan.md`](ecu-plan.md).

## MAF — the real ceiling

This car is **MAF-based**. Two tables govern how much air the ECU can even perceive:

- **`81B8 MAF Max`** — the airflow clip. Once measured flow saturates this, fuel and
  timing stop tracking reality. This is the first thing boost breaks.
- **`B638 16x16 16bit MAF Definition`** — the sensor transfer function (voltage → flow).
- **`84B6 MAF MAX DIAG`** — the diagnostic ceiling; expect a MIL if flow exceeds it.

Stock sensor is Siemens/VDO **5WK9643** (Hyundai 28164-37200); the wiki notes BMW
**5WK96050Z** is compatible (`reference/opengk-wiki/Sensor_Information.wiki`).

Our XDF ships a patch titled **`MAF Calibration Patch E46 330ci`** — i.e. someone has
already done the work of recalibrating this ECU for a larger BMW MAF. That is very
likely the sanctioned path past the sensor's own flow limit, and it is sitting in
`defs/ca654019 2700.xdf` unexamined. **Read that patch before designing anything else.**

The commercial kits' answer to the same problem was a "MafExtender" / "Mafterburner" —
an external signal-clamping box. We have the actual tables, which is strictly better.

## Fuel supply

Unknown: stock pump capacity, rail pressure, and whether the regulator is
manifold-referenced. Nothing in the mirror covers it. Stage III+ kit lists include a
fuel pump; Stage 0–II do not. **TODO: measure rail pressure before and under load.**

## Sensors worth having first

The car has **4× O2 sensors** but no wideband. Any tuning above "verify it's safe"
needs a wideband AFR input. The mirror's ADX (`SIMK43 with OpenTG AFR support.adx`)
has AFR channels, which suggests OpenTG-based wideband logging is a solved problem on
this platform — worth checking what hardware that assumes.

Knock: knock-sensor feedback is the deciding evidence for the 3700–4000 rpm ignition
trough question. Confirm the logger exposes a knock/retard channel before any boost
goes near the car.
