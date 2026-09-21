# OpenGK reference mirror

Local copy of everything from [opengk.org](https://opengk.org) and the
[OpenGK-org GitHub](https://github.com/OpenGK-org) that is relevant to **this car**
(2004 Tiburon GK 2.7 V6 auto, Siemens SIMK43, calibration `ca654019` / `G5J7TS0A`).

Mirrored **2026-08-30**. Upstream is live — re-pull before trusting anything critical.
See [Refreshing this mirror](#refreshing-this-mirror) at the bottom.

---

## Start here — the five files that matter most

| File | Why |
|---|---|
| [`opengk-simk/XDF/Delta-27/ca652048 2700.xdf`](opengk-simk/XDF/Delta-27/) | **725 tables / 922 constants** with full Siemens internal naming. Our own def has 42/13. Different calibration so addresses do NOT transfer, but it is the map of *what functions exist* in a SIMK43 2.7 |
| [`opengk-simk/ADX/SIMK43 with OpenTG AFR support.adx`](opengk-simk/ADX/) | TunerPro datalogging definition, 104 channels, by dmg210. Built for ca663056 — see [Logger channels](#logger-channels-adx) |
| [`opengk-simk/DBC/Tiburon_SIMK4x.dbc`](opengk-simk/DBC/) | CAN message/signal definitions. 500 kb/s, 10 ms broadcast — potentially ~20× our K-line log rate |
| [`opengk-wiki/GKFlasher_Instructions.wiki`](opengk-wiki/) | Canonical flashing procedure |
| [`opengk-simk/EEPROMS/ca654019_G4E7TS0A_GK27.bin`](opengk-simk/EEPROMS/) | The European sibling of our exact calibration — see [Sibling ROM comparison](#sibling-rom-comparison) |

---

## opengk-simk (definitions and ROMs)

### XDF — TunerPro map definitions, `opengk-simk/XDF/Delta-27/`

| File | Tables / Constants | Note |
|---|---|---|
| `ca654019 2700.xdf` | 42 / 13 | **Our calibration.** Copied to `defs/` as the working def |
| `ca652048 2700.xdf` | **725 / 922** | The rich one. Full internal naming, see below |
| `ca654021 2700.xdf` | 42 / 14 | Next calibration up (MY05). Same tables, different addresses |
| `ca655022 2700.xdf` | 43 / 13 | Later 2.7 |
| `ca655038 2700.xdf` | 43 / 13 | Later 2.7 |

`XDF/docs/*.md` are the auto-generated human-readable table listings for each
(produced upstream by `.github/workflows/xdf2readme.yml`). `ca652048 2700.md` is
176 KB and is the fastest way to browse the full function inventory without
opening TunerPro.

**What `ca652048` reveals that our def is missing entirely:**

| Function | Symbols | Why it matters |
|---|---|---|
| Variable intake manifold | `ID_VIM__N_32_VIM__TPS_VIM`, `ID_VIM_1/2`, `C_N_HYS_VIM`, `C_TPS_HYS_VIM`, `C_VS_MIN_VIM` | Switchover point is a real mid-range torque lever. **Completely absent from our def** |
| Per-cylinder knock control | `ID_FAC_KNK_0..5__N__MAF`, `ID_KNKWB_0..5` (window begin), `ID_KNKWE_0..5` (window end) | Six of each = one per cylinder, V6 confirmed |
| Adaptive ignition | `ID_IGA_AD_0..5__N__MAF` @ 0x11000–0x11140 | Learned knock adaptation. Note: lives in the **program zone**, outside our calibration region (0x8000–0xDF40) |
| Catalyst protection | `ID_CRLC_TEG_INC__MAF_KGH`, `IP_TEG_ADD_IGA__POW_DIF`, `IP_TEG_FAC_LAM__LAM_SUB` | Modelled exhaust gas temperature drives both enrichment and timing — this is *why* WOT enrichment is so rich |
| Torque model | `IP_TQI__N_32__MAF` (indicated), `IP_TQFR__N_32__MAF` (friction) | |
| Gearshift torque reduction | `IP_IGA_DIF_MAX_TQR_GS__N_32__MAF` | Separate path from the base ignition map |

**Naming convention** (from `ACRONYMS-for-XDF.txt` plus the symbol names):
`ID_` indexed table · `IP_` interpolated table · `C_` constant · `sst_`/`sstm_` axis
(German *Stützstellen*) · `ldp_` link/pointer · `__N__MAF` = f(rpm, airflow) ·
`__N` = f(rpm) only · `_AT` = automatic transmission variant · `TR:` = author initials.

> The `__N` suffix is why `AD0B WOT Enrichment` and `9A72 WOT TPS Trigger` are
> **1-D f(rpm) tables**, despite both being titled "12x16" in our XDF. Their proper
> names are `IP_TI_FL__N` and `ID_TPS_FL__N`. The titles are wrong; the 16×1
> embedded data is right. Verified against the binary.

### Logger channels (ADX)

`opengk-simk/ADX/SIMK43 with OpenTG AFR support.adx` — 104 channels, header says
*"Values based on SIMK43 4mbit ECU running ca663056"*. **Not our calibration**, so
byte offsets do not transfer, but the scalings and channel inventory do.

Channels worth knowing about, with the ADX's own `packetoffset` (ca663056):

| Channel | Offset | Size | Scaling | ADX desc |
|---|---|---|---|---|
| Engine Load Ignition | 0x13 | 16-bit | `0.021194781 * X` mg/stk | `maf_iga` — **this is the load value that indexes the ignition map** |
| Engine Load Test | 0x12 | 8-bit | `5.447058823529412 * X` mg/stk | `maf_hb` — marked **"Prob incorrect"** upstream |
| Ignition Angle Cyl 1–4 | 0x3A | 8-bit | `(0.375 * X) - 23.625` | `iga_0`; GDS conv. `-0.375*X + 72.0` |
| Knock Retard Cyl 1–4 | 0x44 | 16-bit | `-0.00146484375 * X` | `IGA_KNK_0?` |
| RON Adaptation Factor | 0x3F | 8-bit | `100/255 * X` | ECU adapts to fuel octane |
| Indexed Engine Torque | 0x40 | 16-bit | Nm | |

Also carries wideband definitions (Spartan2, Innovate MTX, AEM UEGO X-Series) and
separate load channels per subsystem (`maf_mmv`, `maf_inj`, `maf_vanos`).

**There is no ADX for any Delta-27 calibration.** Our `docs/logger-remap-ca654019.md`
is filling a genuine gap.

### CAN — `opengk-simk/DBC/Tiburon_SIMK4x.dbc`

500 kb/s, OBD2 pin 6 (H) / pin 14 (L). ECM broadcasts every **10 ms**:

| Msg | ID | Signals |
|---|---|---|
| DME1 | 0x316 (790) | `N_ENG` (16-bit, 0.15625 rpm), `TQI_CAN` (indicated torque %), `TQI_TQR_CAN`, `TQ_LOSS_CAN`, `TQI_MAF_CAN`, `VS_CAN`, `PUC_STAT` (fuel cutoff) |
| DME2 | 0x329 (809) | `TEMP_ENG`, `AMP_CAN` (ambient hPa), `TPS_CAN` |
| DME4 | 0x545 (1349) | `FCO` (fuel consumption), `VB` |
| DME5 | 0x2A0 (672) | marked unverified for Tiburon |
| ASC1/ASC2 | 0x153 / 0x1F0 | from ESP — wheel speeds `VSS1..4`, TCS/ESP status |
| EGS1 | 0x43F (1087) | from the TCM (automatic) |

For comparison our K-line logs run at **4.5 Hz** (2036 frames / 455.9 s), so CAN
would be roughly 20× faster. It does *not* carry MAF/load or ignition angle, so it
complements K-line rather than replacing it.

**Unverified for this car:** whether a 2004 GK has CAN populated at the OBD2 port.
The wiki's worked examples are a 2008 2.0L. Check pins 6 and 14 at the connector
(behind the fusebox cover under the steering wheel). `python-can` is already in `.venv`.

### Sibling ROM comparison

`opengk-simk/EEPROMS/` — six dumps chosen for proximity to our car. All are 512 KB
full-EEPROM images (`bin_offset` −0x80000, same as ours).

| File | Platform | Relationship |
|---|---|---|
| `ca654019_G4E7TS0A_GK27.bin` | G4E7TS0A | **Same calibration, GK chassis, auto, Europe MY04** — closest sibling |
| `ca654019_G5E7TM0A_GK27_PARTIAL.bin` | G5E7TM0A | Same cal, GK, **manual**, MY05 |
| `ca654019_E5N7SB1B_EF27.bin` | E5N7SB1B | Same cal, **EF Sonata** |
| `ca654019_S5E7TM0B_SM27_PARTIAL.bin` | S5E7TM0B | Same cal, SM chassis |
| `ca654020_G5N7TS0A_GK27.bin` | G5N7TS0A | Next cal up, GK auto MY05 |
| `ca654021_G5N7TS0B_GK27.bin` | G5N7TS0B | GK auto MY05 |

**Key finding (2026-08-30).** Comparing our stock cal zone (0x8000–0xDF40) against
the European MY04 auto `G4E7TS0A`:

```
cal bytes differing: 407 / 24384 (1.7%)
  A272 ignition table    IDENTICAL
  AD0B WOT enrichment    IDENTICAL
  9A72 WOT TPS trigger   IDENTICAL
  D3A8 fuel pulse width  IDENTICAL
  81B8 MAF max           IDENTICAL
  8222/8230 rev limits   IDENTICAL
```

Every power-relevant map is byte-identical to the European car. **The `J` (Japan)
in our platform version does not buy a different power calibration** — so the
3700–4000 rpm high-load timing dip is not Japanese-regular-fuel margin, it is the
common Delta 2.7 automatic calibration. This retires the "we're moving from 90 RON
to 98 RON so there's extra headroom" argument.

The 407 differing bytes are 25 scattered single bytes/pairs in the constants block
(0x8001–0x848D, likely emissions and diagnostic configuration) plus four larger runs
at `0xAA7E-0xAA83`, `0xC9B8-0xC9C3`, `0xD010-0xD057` (70 bytes) and
`0xD5E8-0xD707` (288 bytes). None of those runs are covered by any table in our XDF.

For contrast, the EF Sonata differs by 17.5% of the cal zone and the SM by 24.2%,
with all major maps differing — different vehicle, exhaust and gearing.

---

## opengk-wiki (`opengk-wiki/*.wiki`, MediaWiki source)

### Directly about our ECU / engine
| Page | Contents |
|---|---|
| `5WY_ECM_Identification.wiki` | Maps 5WY part numbers to ECU families |
| `Siemens_5WY17_PCB_Components.wiki` | Our ECM per GKFlasher's auto-ID |
| `Siemens_5WY18_V2_PCB_Components.wiki` | The alternative chase206 suspects — see the open question in `docs/car-notes.md` |
| `Siemens_5WY_2_Connector_Pinout.wiki`, `Siemens_5WY_5_Connector_Pinout.wiki` | Full ECM connector pinouts (22 KB each — the big ones) |
| `2.7L_V6_PCB_Layouts.wiki`, `2.7L_V6_Valvetrain.wiki`, `2.7L_V6_Forced_Induction.wiki` | |
| `Camshaft_Specifications.wiki`, `Fuel_Injector_Specifications.wiki`, `Sensor_Information.wiki` | Hardware specs for parts changes |
| `Transmissions.wiki` | |

### Protocol and tooling
| Page | Contents |
|---|---|
| `K-Line.wiki` | 10400 baud KWP2000, fast init, connection points. **Note for 2.7:** K-line at the OBD2 port routes through the BCM "Diagnosis" pin, and 2.7 ECUs share one integrated K/W line pin (C133-1 pin 3) |
| `W-Line.wiki` | |
| `CAN_Bus_messages.wiki` | Message definitions (`SIMK43_CAN_Bus` redirects here) |
| `CAN_Bus_ID_0x153_ASC1.wiki`, `CAN_Bus_ID_0x1F0_ASC2.wiki` | |
| `Data_link_connector_(OBD2).wiki` | Pinout; K-line pin 7, CAN 6/14, L-line 15 |
| `GKFlasher_Instructions.wiki` | Canonical flashing procedure |
| `Bootstrap_Loader.wiki` | BSL / bench access |
| `Creating_a_test_bench_setup.wiki` | Bench rig |
| `GDS_VCI.wiki` | The OEM diagnostic tool the channel definitions come from |
| `Map_Definitions.wiki`, `Checksum.wiki` | Both stubs; Checksum points at GKFlasher's `flasher/checksum.py` |

### Vehicle / identification / immobiliser
`Hyundai_Tiburon.wiki` · `Chassis_identifiers.wiki` · `ECU_family.wiki` (stub) ·
`Vehicle_identification_number_(VIN).wiki` · `Immobiliser.wiki` · `SMARTRA.wiki` ·
`SMARTRA_Protocol.wiki` · `Instrument_Cluster.wiki` · `Bosch_Chip_Part_Numbers.wiki` ·
`Cross_Flash_Kia_Spectra.wiki`

*(Immobiliser pages are background only — this is a confirmed non-immo car.)*

### Community / general
`Main_Page.wiki` · `Getting_started.wiki` · `Acronyms.wiki` ·
`Aftermarket_Tune_Labeling_Convention.wiki` · `GK_Timeslips.wiki` (real-world
performance numbers) · `GK_Weight_Reduction.wiki`

---

## ghidra_scripts (`ghidra_scripts/`)

From [OpenGK-org/ghidra_scripts](https://github.com/OpenGK-org/ghidra_scripts).

| File | Purpose |
|---|---|
| `sim4x_load.py` | Detects the variant and splits a SIMK4x binary into correct memory segments. Run **only** when starting a fresh Ghidra project — it deletes existing blocks |
| `c167_apply_symbol_descriptions.py` + `assets/c167_symbol_descriptions.py` | Annotates Infineon C167 registers (`EXISEL` → *External Interrupt Select register*) |
| `assets/kwp2000_services.h`, `assets/kwp2000_negative_status.h` | KWP2000 service and error codes |
| `assets/ccp_commands.h` | **CAN Calibration Protocol** command set — includes DAQ list commands, i.e. arbitrary high-rate logging of any RAM variable over CAN. Unknown whether SIMK43 actually implements it |

**Why this matters for our logger remap.** We have been inferring byte positions
statistically from drive logs. The definitive method is to disassemble the
`ReadDataByLocalIdentifier(0x01)` handler and read off exactly which variables it
copies into the response buffer, in order. We already have the program dump —
`roms/stock/PROGRAM_ca654019_read_2026-08-29.bin`, covering ECU 0x90000–0x100000,
verified as real code (not a padded/failed read) — so `sim4x_load.py` plus that file
is a complete path to a definitive `ca654019` channel map.

---

## newtiburon (`newtiburon/`, forum threads, added 2026-09-08)

~110 threads from newtiburon.com's Engine Management / V6 NA / V6 FI sections, as
Markdown, plus `index.tsv` with every thread title in those sections (21 321 rows) so
future title searches need no crawl. Fetched with `tools/newtiburon/fetch.py` (the
site sits behind a proof-of-work interstitial; TollBit was a dead end). The digest of
what matters for this ECU is `docs/forum-digest-newtiburon.md`; see `newtiburon/README.md`
for how to pull more.

---

## Deliberately not mirrored

| What | Size | Why / how to get it |
|---|---|---|
| Full `EEPROMS/` archive (GK-20, GK-27, EF, BK, FC, SM…) | ~35 MB+ | Only the six closest to our calibration are here. `gh api repos/OpenGK-org/opengk-simk/git/trees/HEAD?recursive=1` to list, then raw.githubusercontent to fetch |
| `OpenGK-org/ecu-reverse-engineering` | ~25 MB | Full KiCad reversal of the **5wy19** board (not our variant) — schematics incl. `can.kicad_sch`, gerbers, and datasheets for the `tpic8101` knock-sensor interface IC and AM29F400B flash. Clone if doing hardware work |
| Beta-20 and Kefico XDFs | ~60 MB | Wrong engine family |
| `OpenGK-org/gds4all` | small | Live tool, not reference data — clone it if parsing GDS definitions |
| `opengk.org/files/...` PDF library | varies | e.g. *OBDII Specifications - KWP2000 DaimlerChrysler 2002.pdf*, linked from `K-Line.wiki` |

---

## Refreshing this mirror

Wiki pages (MediaWiki raw wikitext):
```bash
curl -sL "https://opengk.org/index.php?title=PAGE_TITLE&action=raw" -o reference/opengk-wiki/PAGE_TITLE.wiki
```
Full page list: `https://opengk.org/index.php?title=Special:AllPages`

GitHub assets:
```bash
curl -sfL "https://raw.githubusercontent.com/OpenGK-org/opengk-simk/master/<url-encoded path>" -o <dest>
gh api repos/OpenGK-org/opengk-simk/git/trees/HEAD?recursive=1 --jq '.tree[].path'   # list everything
```

**Upstream moves.** The `ca654019` XDF was updated 2026-08-29 (fan trigger address
`0x82B9` → `0x8675`) one day after our first download, which left `defs/` stale for
two days. Check `gh api repos/OpenGK-org/opengk-simk/commits` before any flash.
