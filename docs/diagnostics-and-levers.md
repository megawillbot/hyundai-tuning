# Diagnostics and tuning levers — ca654019

A tuner/modifier-facing index of the knobs that matter, with their current stock
values and where they live. Built **2026-09-04** from the constants map
([[full-map-ca654019]]) and the disassembly ([[ecu-architecture]],
[[code-derived-tables]]). Constants are single bytes or words in the calibration;
edit, checksum-correct, flash ([[ghost-cams]]).

> Confidence: the limiter and airflow constants are CONFIRMED (code-verified).
> The lambda/closed-loop values are named from the constants map (HIGH tier) but
> their scalings are not all independently checked. Verify against a datalog
> before flashing anything you are not sure of.

---

## 1. Diagnostics — how a DTC matures, and how to suppress one

Fault monitors mature through a **pair of near-identical maturation routines** —
`0x9E128` (the main one, ~109 call sites) and `0x9E934` (the lambda/VIM group,
~22 sites). Both take the same arguments and run byte-identical counter logic:

```
R14 = C_ABC_INC_<monitor>_DIAG    ; counter step when the fault is present
R15 = C_ABC_MAX_<monitor>_DIAG    ; counter value at which the DTC confirms
CALLS 0x09, 0xE128   (or 0xE934)
```

Each adds `INC` to a per-monitor debounce counter while the fault is present and
**confirms the DTC (sets the matured bit, lights the MIL) when the counter
reaches `MAX`**. 40 of the 41 `C_ABC_INC_*` constants are referenced this way.
Therefore:

> **`C_ABC_INC_<monitor>_DIAG = 0` disables that monitor.** The counter never
> rises, the code never confirms, the light never comes on. Verified by reading
> both routines — the increment is the passed constant, and zero never reaches
> the threshold. Holds regardless of which of the two routines a monitor uses.

**On the OBD P-code numbers:** each monitor also carries a descriptor pointer,
but the chain runs through the `0x48000` RAM shadow into a format that did not
resolve cleanly to OBD P-numbers from static analysis — so **this document
deliberately does not publish a monitor→P-code table it can't stand behind.**
The reliable way to get the exact code for a monitor is a live **ReadDTC (KWP
0x18)** over the cable after the fault is set, or the OpenGK/GDS DTC list. The
monitor names below are unambiguous enough to choose the right `C_ABC_INC` edit
without the P-number.

That is the clean lever for a mod that trips a specific code. It is per-monitor,
so you disable exactly the one you need and leave the rest working.

### The 35 monitors and their stock state

`on` = increment is non-zero (monitor active). Names are Siemens symbols; the
plain-language mapping is in the right column.

| monitor (`C_ABC_INC_…_DIAG`) | INC | MAX | state | what it watches |
|---|---|---|---|---|
| `VLS_CAT` | 0 | 255 | **off** | **post-cat lambda / catalyst** — already disabled |
| `VLS` | 5 | 50 | on | main (front) lambda sensor |
| `VLS_LIM` | 0 | 255 | **off** | lambda limit |
| `LSH_UP` / `LSH_DOWN` | 1 / 0 | 20 | on / **off** | O2 heater, upstream / downstream |
| `MAF` | 5 | 100 | on | mass airflow rationality |
| `TPS_MES` | 2 | 200 | on | throttle position |
| `TIA` | 0 | 100 | **off** | intake air temp |
| `TCO` / `TCO_GRD` | 1 / 1 | 10 | on | coolant temp + gradient (thermostat) |
| `CAM` / `CRK` | 1 / 4 | 80 / 20 | on | cam & crank sensors |
| `T_SEG` | 2 | 20 | on | **misfire** (segment timing) |
| `IGC` | 0 | 255 | **off** | spark-advance diagnosis |
| `NL_KNK` | 0 | 10 | **off** | knock level |
| `IV` | 2 | — | on | injector valve |
| `ISA_1`/`ISA_2`/`ISAPWM_H`/`ISAPWM_L` | 1–2 | — | on | idle-speed actuator |
| `RLY_EFP` | 2 | 10 | on | fuel-pump relay |
| `RLY_FAN_H` / `RLY_FAN_L` | 2 / 0 | 255 | on / **off** | cooling-fan relays |
| `T_DLY_AD` | 1 | — | on | fuel-trim / purge delay |
| `CPS` | 1 | 10 | on | canister purge |
| `SOV` / `SPI` | 0 / 0 | — | **off** | shut-off valve / SPI |
| `FTL` / `FTL_INTM` | 0 / 0 | 255 | **off** | fuel-tank level |
| `CAN_BUS_OFF` | 0 | 255 | **off** | CAN bus-off |
| `TIMEOUT_TCU1` / `TIMEOUT_TCS1` | 1 / 0 | 10 | on / **off** | CAN timeout, TCU / TCS |
| `VIM` / `VIM_1` / `VIM_2` | 0 | 255 | **off** | variable intake manifold (dead code) |

**For common mods:**
- **Cat delete / rear-O2 removal:** `VLS_CAT` is already off on this calibration,
  so the post-cat monitor won't complain out of the box. If a rear-O2 code still
  appears from a related monitor, its `C_ABC_INC` is the switch.
- **Header / de-cat with front-sensor relocation:** leave `VLS` (front lambda,
  active) unless you're deleting it — that one is the fuel-control sensor, not
  just a monitor.
- **Anything that shifts airflow (intake, MAF housing):** `MAF` rationality is
  active (INC 5, MAX 100); a big enough scaling error will trip it.
- Misfire (`T_SEG`) and cam/crank are active and should stay so — they protect
  the engine, not just emissions.

(Monitor→P-code numbers: see the note under §1's routine description — not
decoded from static analysis; use a live ReadDTC or the GDS/OpenGK list.)

## 2. Limiters

All CONFIRMED against the code ([[ecu-architecture]] §5d).

| lever | addr | stock | notes |
|---|---|---|---|
| Rev limit — soft (ign cut) | `0x8222` | **6816 rpm** | single byte × 32. Edit = target ÷ 32 |
| Rev limit — hard (fuel cut) | `0x8230` | **6912 rpm** | byte × 32 |
| Launch / rolling fuel-cut 1 | `0x8219` | 4000 rpm | `C_N_FCUT` |
| Launch / fuel-cut 2 | `0x8229` | 2784 rpm | `C_N_MAX_FCUT` — OpenGK notes say these two should match; they don't ship matched |
| Speed limiter 1 / 2 | `0x8370`/`0x8371` | **250 km/h** | effectively off |
| Traction-control rpm/ign cap | `0x822D` | 255 (`C_N_MAX_IGA_TQR`) | max = disabled |

The effective rev limit is the **minimum of a clamp chain**, not just `C_N_MAX` —
raising it alone won't help if a gear/vehicle-speed or diagnostic cap sits lower
([[ecu-architecture]] §5d).

## 3. Airflow ceiling — the forced-induction wall

`C_MAF_MAX = 550.15 mg/stroke` at `0x81B8`. The ignition and fuel map load axes
run to ~580, so the top load column already sits **past the clamp**. This is the
MAF ceiling the E46-sensor swap in [[car-notes]] / `docs/supercharger/` exists to
raise — the single most important constant for any boost/airflow project. Diag
limit `C_MAF_KGH_MAX_DIAG` (1200 kg/h) is separate.

## 4. Fuelling and lambda

- **Base fuel map** `0xD3A8` (`Closed Loop Pulse Width`, 16×12 rpm×MAF, `0.004*X`)
  and **idle/low-rpm map** `0xD528` — both in the hand-made def
  ([[code-derived-tables]]). A hidden RAM bit `M_FD14.12` selects between them.
- **WOT enrichment** `IP_TI_FL__N` (`0xAD0B`) and **WOT TPS trigger** `9A72` —
  1-D f(rpm) ([[full-map-ca654019]] §2), in the hand-made def.
- **Closed-loop lambda adaption**: a block of `C_LAM_*` constants at `0x8195`+ —
  P/I gains (`C_LAM_POS_P_IS`=77, `C_LAM_NEG_P_IS`=77, I-terms=5), authority and
  hysteresis. These set how hard and fast the ECU trims to stoich in closed loop.
  Named (HIGH tier); scalings unverified — treat as a lead, not a calibrated knob.

## 5. Thermal protection (the code-only subsystem)

The **cat-overtemp protection loop** — modelled EGT `0xCA24` (470–1160 °C),
thermal filter, limit, and enrichment/timing factor `0xB9EE` — is documented in
[[code-derived-tables]]. It is what pulls fuel and timing at sustained high load.
Relevant to exhaust/header/FI work: it defines where the ECU believes it is
overheating. It has **no exhaust-side combustion term**, so it cannot see or
react to overrun pops ([[full-map-ca654019]] §6).

## 6. Idle and cooling (already defined)

In the hand-made def, verifiable stationary:
- Idle speed tables `B936` / `BA5A` / `BA82` / `C694`
- Radiator-fan duty map `CB58` (20×6)
- Idle ignition `A336`, idle-actuator ISA maps `A38A`/`A3AD`/`A525`

## 7. Dead / disabled features — don't waste time here

- **Variable intake manifold (VIM):** unconfigured — `C_CONF_VIM=0`, all maps
  zero, diagnostics off. The platform supports it; this engine doesn't use it
  ([[full-map-ca654019]] §3). Not a lever.
- **15 all-FF tables** in the `0xD5E8`-`0xD750` band and elsewhere: real tables
  the code reads but our cal leaves blank — disabled Japan-market/emissions
  features. Editing them does nothing unless whatever gates them is enabled.
- Monitors marked **off** in §1 are already suppressed.

---

## Quick reference — the highest-value edits

| goal | edit | from → to |
|---|---|---|
| Raise soft rev limit | `0x8222` (1 byte) | `0xD5` (6816) → target÷32 |
| Raise hard rev limit | `0x8230` (1 byte) | `0xD8` (6912) → target÷32 |
| Suppress a specific DTC | `C_ABC_INC_<mon>_DIAG` | its value → `0` |
| Raise airflow ceiling (FI) | `0x81B8` `C_MAF_MAX` | 550 mg/stk → higher (+ sensor scaling) |
| Base fuel | `0xD3A8` via hand-made def | — |

Nothing here has been flashed. Always read the stock bin, keep the backup, edit
one thing, checksum-correct, flash, datalog, commit.
