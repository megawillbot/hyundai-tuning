# Diagnostics and tuning levers — ca654019

A tuner/modifier-facing index of the knobs that matter, with their current stock
values and where they live. Built **2026-09-03** from the constants map
([[full-map-ca654019]]) and the disassembly ([[ecu-architecture]],
[[code-derived-tables]]). Constants are single bytes or words in the calibration;
edit, checksum-correct, flash ([[ghost-cams]]).

> Confidence: the limiter and airflow constants are CONFIRMED (code-verified).
> The monitor table in §1 is **code-paired** (2026-09-03 revision — see the
> correction note). The lambda/closed-loop values are named from the constants
> map (HIGH tier) but their scalings are not all independently checked. Verify
> against a datalog before flashing anything you are not sure of.

---

## 1. Diagnostics — how a DTC matures, and how to suppress one

### Correction (2026-09-03)

The first revision of this table took its monitor names from the alignment-derived
constants map. Cross-checking every maturation call site showed the code pairs
`INC[k]` with `MAX[k + 0x2F]` for all of `0x80B0`–`0x80D5`; the map's `MAX` names
were consistent with that, its `INC` names were **one address too high** for
`0x80BB`–`0x80C3` and `0x80C6`–`0x80C8`. The function each call site lives in
(knock, immobiliser, tank-pressure, misfire, coolant, intake-air constants)
confirms the corrected assignment. Net effect on the old table: **NL_KNK and TIA
are ON, not off; TCO_GRD and RLY_FAN_H are OFF, not on; there is no T_DLY_AD
monitor** (that byte is SPI). The CSV and extended XDF are corrected.

### Mechanism

Fault monitors mature through a **pair of byte-identical maturation routines** —
`0x9E128` (the main one) and `0x9E934` (used by the lambda and VIM monitors).
Both take the same arguments:

```
R12 = monitor descriptor (RAM)     R13 = fault-status byte (RAM shadow)
R14 = C_ABC_INC_<monitor>_DIAG     R15 = C_ABC_MAX_<monitor>_DIAG
CALLS 0x09, 0xE128   (or 0xE934)
```

Read from the routine itself (file `0x1E128`):

- If the descriptor's **bit 0x20 is already set**, or `MAX == 0`, do nothing.
- If the fault nibble (`[R13] & 0x0F`) is set: `counter += INC` (saturating byte
  add at `0xC3FB4`); when `counter >= MAX`, **set bit 0x20**.
- If the fault byte is entirely clear: **set bit 0x20** as well.

So bit 0x20 is a **"test complete" flag, set on either outcome** — not "DTC
confirmed". The MIL/DTC decision is made elsewhere from the fault nibble plus
this flag. What the routine does establish:

> **`C_ABC_INC_<monitor>_DIAG = 0` stops that monitor maturing.** The counter
> never rises, so a present fault never completes as a fail. Holds for both
> routines. **Not verified:** whether any *substitute-value* or limp strategy
> keys off the raw fault nibble (which the detector still sets). Treat it as
> "stops the DTC", not "nothing happens".

**On the OBD P-code numbers:** each monitor also carries a descriptor pointer,
but the chain runs through the `0x48000` RAM shadow into a format that did not
resolve cleanly to OBD P-numbers from static analysis — so **this document
deliberately does not publish a monitor→P-code table it can't stand behind.**
The reliable way to get the exact code for a monitor is a live **ReadDTC (KWP
0x18)** over the cable after the fault is set, or the OpenGK/GDS DTC list. The
monitor names below are unambiguous enough to choose the right `C_ABC_INC` edit
without the P-number.

### The monitors and their stock state (code-paired)

`INC` at `0x80xx`, `MAX` at `INC + 0x2F` (`+0x2D`/`+0x2E` for the first rows —
two MAX-only slots, `ER` at `0x80DD` and an unnamed one at `0x80E6`, sit between).
`on` = INC non-zero. Every disabled monitor ships as `0 / 255`, which is itself a
consistency check the old table failed. Evidence column: **fn** = the call site's
function reads that subsystem's constants; **pair** = position in the paired
block only.

| INC addr | monitor | INC | MAX | state | what it watches | evidence |
|---|---|---|---|---|---|---|
| `0x80A9` | CAM | 1 | 80 | on | cam sensor | pair |
| `0x80AA` | CAN_BUS_OFF | 0 | 255 | off | CAN bus-off | pair |
| `0x80AB` | CPS | 1 | 10 | on | canister purge (electrical) | pair |
| `0x80AC` | CPS_MECHA | 0 | 255 | off | canister purge (mechanical) | pair |
| `0x80AD` | CRK | 4 | 20 | on | crank sensor | pair |
| `0x80AE` | DTP_NOISE | 0 | 255 | off | tank-pressure sensor noise | pair |
| `0x80AF` | DTP_SENS | 0 | 255 | off | tank-pressure sensor | pair |
| `0x80B0` | FTL | 0 | 255 | off | fuel-tank level | pair |
| `0x80B1` | FTL_INTM | 0 | 255 | off | fuel-tank level (intermittent) | pair |
| `0x80B2` | IGC | 0 | 255 | off | spark-advance diagnosis | fn |
| `0x80B3` | ISA_1 | 2 | 8 | on | idle actuator 1 | pair |
| `0x80B4` | ISA_2 | 2 | 10 | on | idle actuator 2 | pair |
| `0x80B5` | ISAPWM_H | 1 | 35 | on | idle actuator PWM high | pair |
| `0x80B6` | ISAPWM_L | 1 | 35 | on | idle actuator PWM low | pair |
| `0x80B7` | IV | 2 | 10 | on | injector valves | pair |
| `0x80B8` | LSH_DOWN | 0 | 255 | off | O2 heater, downstream | pair |
| `0x80B9` | LSH_UP | 1 | 20 | on | O2 heater, upstream | pair |
| `0x80BA` | MAF | 5 | 100 | on | mass-airflow rationality | fn |
| `0x80BB` | MIL | 0 | 255 | off | MIL lamp circuit | pair |
| `0x80BC` | **NL_KNK** | 1 | 10 | **on** | knock level | fn |
| `0x80BD` | NON_IMOB | 2 | 2 | on | immobiliser absent check | fn |
| `0x80BE` | RLY_EFP | 2 | 10 | on | fuel-pump relay | pair |
| `0x80BF` | **RLY_FAN_H** | 0 | 255 | **off** | fan relay, high | pair |
| `0x80C0` | RLY_FAN_L | 0 | 255 | off | fan relay, low | pair |
| `0x80C1` | SOV | 0 | 255 | off | canister shut-off valve (electrical) | pair |
| `0x80C2` | SOV_MECHA | 0 | 255 | off | shut-off valve (via tank pressure) | fn |
| `0x80C3` | SPI | 1 | 10 | on | SPI driver-chip bus | pair |
| `0x80C4` | T_SEG | 2 | 20 | on | **misfire** (segment timing) | fn |
| `0x80C5` | TCO | 1 | 10 | on | coolant temp sensor | fn |
| `0x80C6` | **TCO_GRD** | 0 | 255 | **off** | coolant gradient (thermostat) | fn |
| `0x80C7` | **TIA** | 1 | 100 | **on** | intake-air temp sensor | fn |
| `0x80C8` | TIA (2nd, unnamed) | 0 | 255 | off | second intake-air-temp check | fn |
| `0x80C9` | TIMEOUT_TCS1 | 0 | 255 | off | CAN timeout, TCS | pair |
| `0x80CA` | TIMEOUT_TCU1 | 1 | 10 | on | CAN timeout, TCU | pair |
| `0x80CB` | TPS_MES | 2 | 200 | on | throttle position | pair |
| `0x80CC`–`0x80CF` | VB + three unnamed | 0 | 255 | off | battery voltage and three monitors not in ca652048 | pair |
| `0x80D0`–`0x80D2` | VIM / VIM_1 / VIM_2 | 0 | 255 | off | variable intake manifold (dead code) | pair |
| `0x80D3` | VLS | 5 | 50 | on | main (front) lambda sensor | pair |
| `0x80D4` | **VLS_CAT** | 0 | 255 | **off** | post-cat lambda / catalyst — already disabled | pair |
| `0x80D5` | VLS_LIM | 0 | 255 | off | lambda limit | pair |

Four call sites pass immediates (`INC=1, MAX=1` or `MAX=230`/`255`) — those
monitors have no calibration switch. The exact placement of `VB` and the three
unnamed monitors inside `0x80CC`–`0x80CF` is not pinned (all four are off).

**For common mods:**
- **Cat delete / rear-O2 removal:** `VLS_CAT` is already off on this calibration,
  so the post-cat monitor won't complain out of the box. If a rear-O2 code still
  appears from a related monitor, its `C_ABC_INC` is the switch.
- **Header / de-cat with front-sensor relocation:** leave `VLS` (front lambda,
  active) unless you're deleting it — that one is the fuel-control sensor, not
  just a monitor.
- **Intake / IAT relocation:** `TIA` (`0x80C7`) **is active** (INC 1, MAX 100),
  contrary to the first draft. A relocated or unplugged IAT will mature a code.
- **Anything that shifts airflow (intake, MAF housing):** `MAF` rationality is
  active (INC 5, MAX 100); a big enough scaling error will trip it.
- **Timing work:** `NL_KNK` (knock level, `0x80BC`) **is active** (INC 1, MAX 10).
- Misfire (`T_SEG`) and cam/crank are active and should stay so — they protect
  the engine, not just emissions. Ghost cams has run several days with no CEL
  as of 2026-09-03 ([[ghost-cams]]).

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

`C_MAF_MAX` at `0x81B8` is **one byte, raw 101, scaled × 5.447 = 550.15 mg/stroke**
(max representable 255 → 1389 mg/stk). The ignition and fuel map load axes run
to ~580, so the top load column already sits **past the clamp**. This is the MAF
ceiling the E46-sensor swap in [[car-notes]] / `docs/supercharger/` exists to
raise — the single most important constant for any boost/airflow project. The
`C_MAF_KGH_*_DIAG` airflow diagnostic limits (`0x8470`+) are separate.

## 4. Fuelling and lambda

- **Base fuel map** `0xD3A8` (`Closed Loop Pulse Width`, 16×12 rpm×MAF, `0.004*X`)
  and **idle fuel map** `0xD528` — both in the hand-made def
  ([[code-derived-tables]]). The selector is the engine-state machine: state 2
  = **idle** selects `0xD528` ([[ecu-architecture]] §5f).
- **WOT enrichment** `IP_TI_FL__N` (`0xAD0B`) and **WOT TPS trigger** `9A72` —
  1-D f(rpm) ([[full-map-ca654019]] §2), in the hand-made def.
- **Closed-loop lambda adaption**: a block of `C_LAM_*` constants at `0x8195`+ —
  P/I gains (`C_LAM_POS_P_IS`=77, `C_LAM_NEG_P_IS`=77, I-terms=5), authority and
  hysteresis. Named (HIGH tier); **scalings unverified** — treat as a lead, not a
  calibrated knob.

## 5. Overrun fuel cut and the pop-and-bang question

Fully traced in [[puc-overrun-map]] (code-verified section). Short version: the
cut is a **staged state machine** (1 cylinder → 4 cylinders → all six, stock),
the injector tables are **indices into a 14-entry pattern table at `0xB848`**,
and the steady-state "all six" stage is hard-coded in the program — so an
rpm-windowed pop tune needs the small program patch prepared in
[[program-zone-plan]], not a calibration-only edit.

## 6. Thermal protection (the code-only subsystem)

The **cat-overtemp protection loop** — modelled EGT `0xCA24` (470–1160 °C),
thermal filter, limit, and enrichment/timing factor `0xB9EE` — is documented in
[[code-derived-tables]]. It is what pulls fuel and timing at sustained high load.
Relevant to exhaust/header/FI work: it defines where the ECU believes it is
overheating. It has **no exhaust-side combustion term**, so it cannot see or
react to overrun pops ([[full-map-ca654019]] §6).

## 7. Idle and cooling (already defined)

In the hand-made def, verifiable stationary:
- Idle speed tables `B936` / `BA5A` / `BA82` / `C694`
- Radiator-fan duty map `CB58` (20×6)
- Idle ignition `A336`, idle-actuator ISA maps `A38A`/`A3AD`/`A525`

## 8. Dead / disabled features — don't waste time here

- **Variable intake manifold (VIM):** unconfigured — `C_CONF_VIM=0`, all maps
  zero, diagnostics off. The platform supports it; this engine doesn't use it
  ([[full-map-ca654019]] §3). Not a lever.
- **15 all-FF tables** in the `0xD5E8`-`0xD750` band and elsewhere: real tables
  the code reads but our cal leaves blank — disabled Japan-market/emissions
  features. Editing them does nothing unless whatever gates them is enabled.
- Monitors marked **off** in §1 are already suppressed.

---

## Quick reference — the highest-value edits

| goal | edit | from → to | confidence |
|---|---|---|---|
| Raise soft rev limit | `0x8222` (1 byte) | `0xD5` (6816) → target÷32 | confirmed |
| Raise hard rev limit | `0x8230` (1 byte) | `0xD8` (6912) → target÷32 | confirmed |
| Stop a specific DTC maturing | `C_ABC_INC_<mon>_DIAG` (1 byte, §1 table) | its value → `0` | confirmed mechanism; see caveat |
| Raise airflow ceiling (FI) | `0x81B8` `C_MAF_MAX` (1 byte × 5.447) | 101 (550 mg/stk) → higher, + sensor scaling | confirmed |
| Base fuel | `0xD3A8` via hand-made def | — | confirmed geometry, def scaling |
| Overrun pops above an rpm | program patch + `0xBC8B` table | see [[program-zone-plan]] | prepared, unflashed |

Nothing here has been flashed except the ghost-cam patch. Always read the stock
bin, keep the backup, edit one thing, checksum-correct, flash, datalog, commit.
