# newtiburon.com digest — what the forum knows that bears on this ECU

Written **2026-09-08** from ~110 threads pulled with `tools/newtiburon/fetch.py`
(all saved under `reference/newtiburon/`, one Markdown file per thread, named
`<slug>.<thread-id>.md`). Thread indexes of the three relevant sections
(Engine Management, V6 NA, V6 FI: ~20 000 titles) are in
`reference/newtiburon/index.tsv` for future title searches without a re-crawl.

The forum's tuning knowledge is thin compared with what this repo already has
(disassembler, verified constants, engine-state machine). Its value is
**chase206's practical numbers** (chase = OpenGK, the same person in
[[car-notes]]), the hardware ceilings people have actually measured, and the
blower market. Everything below cites the thread file it came from.

---

## 1. What chase's NA reflash actually changes (the recipe for our cal)

chase sells an I/H/E "spicy tune" for 98 RON and has described it in enough
detail to reproduce on our calibration:

| Lever | chase's setting | Source |
|---|---|---|
| Ignition | "significantly advanced ignition for 93 octane (98 RON)"; "adds significant ignition timing" | `ecu-tune.481880.md` #2, `tune-needed.484834.md` #4 |
| WOT AFR | leaned to **12.5:1** ("cleans up the WOT enrichment so it's not so pig rich") | `ecu-tune.481880.md` #2 |
| Open-loop entry | **WOT TPS trigger lowered to 50 % throttle** | `ecu-tune.481880.md` #2 |
| Rev limit | customers run 7300-7400 (chase's own car: "my redline of 7300") | `log-request-with-supercharger.481269.md` #4, `the-deltas-performance-real-talk.485438.md` |
| Rev hang | "ghost IACV restrictor" patch — emulates the mechanical IAC restrictor plate people fit; "kill rev hang" | `iac-valve-control-interception-causing-p0102.485508.md` #2 (Sep 2026) |
| Crackles | GKFlasher users report "make some fun crackles too" as a menu-level option | `the-deltas-performance-real-talk.485438.md` |

A GKFlasher user's rule of thumb for the ignition table
(`the-deltas-performance-real-talk.485438.md`, Jul 2026): load axis
**90-120 = cruise, <90 = closed throttle, 280-480 = WOT**, "beyond that is
supercharged"; **don't add more than ~4 deg past 3000 rpm on 98 RON without knock
ears**. Those load numbers are mg/stroke and agree with our own axis
([[full-map-ca654019]]: main ignition load axis runs to 580 mg/stk).

chase on what the OEM cal does at idle: 8-12 deg advance, idle map targets
10-12; the single highest cell in the OEM ignition map is at 3200 rpm in a
deceleration-only load row (`ignition-timing-advance.482377.md` #2). Both
consistent with our decoded tables.

**Implication for the burble work.** The OpenGK community already ships a
"crackle" and a rev-hang patch. Our [[puc-overrun-map]] approach (never enter
PUC, retard in state 4) may or may not be what theirs does. Worth asking chase
directly: *what does the GKFlasher crackle option change — resume tables,
`IP_IGA_PU_AT`, or a program patch?* That answer either validates our cal-only
burble or saves us the program patch.

---

## 2. Numbers the ECU side confirms or adds

- **Rev limiter.** chase: SIMK43 ignition and fuel cut both at **6816 rpm**,
  "revs bob at 320 rpm intervals" when hit (`so-does-the-tiburon-have-a-rev-limiter.482265.md` #4).
  Our code-verified value is 6816 soft / 6912 hard, byte x 32
  ([[diagnostics-and-levers]] §2). Same number.
- **Ceiling.** "The stock ECU is unknown territory beyond 8190 rpm, set your
  limiter 8100 or below" (`the-deltas-performance-real-talk.485438.md`). 255 x 32 =
  8160, i.e. the byte-scaled limit; nobody has run the tables past it.
- **Fuel-trim clamps.** LTFT max **+25 %**, STFT **+/-32 %**, lean CEL fires when
  LTFT reaches +20..25 % (`do-i-need-a-tune-for-cai-exhaust.483431.md` #5,
  `alpine-supercharged-stage-1-lean-condition-help.484136.md` #5).
- **MAF scale.** OEM fuel table reaches 580 mg/stroke at 6000 rpm; MAF clips at
  ~205 g/s at 5 V; a healthy NA car with I/H/E logs 125-140 g/s at 6500 rpm
  (`log-request-with-supercharger.481269.md` #6-#9). Useful sanity bounds for our
  logger ([[logger-remap-ca654019]]).
- **Generation split.** 05/06 and especially 07/08 ECUs lean out and throw
  P0171 with a CAI; 03/04 (5WY17) are tolerant, which is why "swap to an 04 ECU"
  is the folk fix (`do-i-need-a-tune-for-cai-exhaust.483431.md` #5,
  `tune-needed.484834.md` #2). Ours is a 5WY17-profile ca654019 — we are on the
  tolerant side.
- **5WY17+ barrier.** Swapping ECU generations means changing **5 V narrowband
  O2 sensors to 1 V** (`iac-valve-control-interception-causing-p0102.485508.md` #10).
- **Variable intake.** 5WY18 / 5WY1F can be flashed with Tucson/Sportage
  firmware to enable the variable-runner solenoid outputs; one car runs it
  (`iac-valve-control-interception-causing-p0102.485508.md` #8, `diy-mu-intake.483579.md` #4).
  Not applicable to 5WY17 as far as anyone has tried.
- **Sensors the ECU will tolerate.** Upstream O2: NTK, Denso, Mando only.
  MAF: Hyundai, Siemens/VDO/Continental, Delphi. TPS: Hyundai/DAC or NTK.
  IACV: Hyundai "HMC" (`ignition-timing-advance.482377.md` #6,
  `04-v6-2-7l-6spd-rev-hang-idle-fluctuation.482990.md` #4). Full list on
  opengk.org "Sensor Information".
- **Knock sensors.** Cannot be unplugged (limp mode); on the OEM NA tune faking
  them with a matched resistor is tolerated, but chase's advice is "if they
  detect knock you're probably knocking" (`is-there-any-way-to-bypass-the-knock-sensors.483294.md`).
- **OBD "timing advance" PIDs are wrong** on generic tools for this ECU; only
  Hi-Scan gives trustworthy per-cylinder data (`ignition-timing-advance.482377.md` #2).
  Relevant if we ever compare our logger against a scan tool.
- **Old canned reflashes (NGM/Fiebruz/SFR) disabled emissions monitors**
  outright and failed Ontario OBD tests; a TCU-less manual ECU in an auto car
  throws P1602, an auto ECU in a manual throws P0501
  (`obdii-e-test-w-reflash.453690.md`, `ngm-200-whp-n-a-reflash-2003-2008-2-7l-p0501.221276.md`).
  Our car is an auto; keep the TCU handshake intact in any tune.

---

## 3. NA power: what has actually been measured

| Setup | Result | Source |
|---|---|---|
| Stock, manual | ~140-145 whp | `i-want-more-performance.484120.md` #6 |
| Intake + headers + catback ("FBO"), no tune | ~170 whp | `dyno-r-esults-2-7-na-v6.311729.md` #7 |
| I/H/E + chase tune | 170-190 whp claimed | `the-deltas-performance-real-talk.485438.md` |
| I/H/E + ported intakes, best case | ~200 whp ceiling | `ecu-tune.481880.md` #4 |
| + Crower .351 regrind (F7589) | ~210 whp | `i-want-more-performance.484120.md` #6 |
| + NGM stage IV manifolds, BBTB, cams, reflash | 208 whp | `2-7l-high-compression-12-1-pistons.446386.md` #10 |
| Forum record NA | 265 whp (rushking19) | `g6ba-all-motor-theoretical.485078.md` #7 |
| 10.8:1 pistons + .349 cams, piggyback-tuned auto | 137 whp (no better than stock, +60 lb-ft) | `high-compression-cammed-dyno-results.452786.md` |

chase's ordering of NA gains: **headers and cat delete first** (most of it), then
a free-flowing single-exit catback (the stock dual-exit Y is the restriction),
intake last. Port the upper/lower to ~40 mm and port-match; a bigger throttle
body shows nothing NA back-to-back (56 mm OEM vs 70 mm NGM); head porting only
pays with cams over .351 lift (`anyone-tune-a-v6-tiburon-in-new-zealand.484512.md` #7,
`tune-needed.484834.md` #4). E85 is pointless NA below very high compression
(`g6ba-all-motor-theoretical.485078.md` #7).

Cam cards chase recommends (Crower regrinds, need lash caps): **F7589**
(.351 lift), **E65701** (214 dur / 14 overlap), and an unconfirmed .399/198
grind (`crower-cams-regrind-help.482330.md` #8). Cam card aggregation is on
opengk.org "Camshaft Specifications". Stock springs are good to ~7400; BC1260
springs to ~8300 (`the-deltas-performance-real-talk.485438.md`).

Headers available now: DNA/OBX eBay units (~USD 150, poor Y, crack),
Maintec (~USD 1500), Hurricane/Wildcat in Australia. **Don't buy RPW** — same
eBay header rebadged (`anyone-tune-a-v6-tiburon-in-new-zealand.484512.md` #7).
RPW actually lists two different G6BA products (checked Sep 2026):
`extractor-3-1-race-design-kit-hyundai-g6ba-bw-delta-2` (AUD 880, "long tube",
polished stainless, includes 2.5" Y-pipe with flex joints + high-flow cat,
"special order") — its product photo is the catalogue shot of the OBX/DNA
3-piece kit (crossed polished primaries, test pipe, four gaskets, loose
hardware) and it is priced below the RPW-made item despite including a cat, so
this is the one chase's warning applies to. The other listing, without the
`-2`, is the 2025 group-buy item cm256 mentions (`n-a-vs-supercharge.484634.md`
#15): AUD 1100, tuned-length **short tube** 3-1, 1-5/8" primaries, 2" collector,
2.5" flex pipe, cat optional, orders closed 30 May 2025, still shows
back-order. No forum dyno or fitment report exists for either RPW product;
the only RPW-header dyno (`high-compression-cammed-dyno-results.452786.md`) is
a 2019 built motor with too many variables to isolate the headers. DNA units
fit with only alternator-cover trimming and no CEL/lean complaint
(`2-7l-dna-motoring-headers.484702.md`); DC Sports headers are ceramic-coated
mild steel and rust (`are-these-dc-headers-legit.484884.md`).
The NZ-relevant part: the car chase referred to in that thread ran CAI + DNA
headers + custom single exit + chase's 98 RON tune.

---

## 4. Blower decision — what the forum settles

- **Stage 0 / stage 1 (3.4"-class blower pulley, ~3-5 psi) runs on the OEM tune**; injectors
  near 100 % duty at stage 1. **Stage 2 (2.8" pulley, 6-8 psi) needs a reflash
  and 360 cc injectors**; stage 3 (6.5" crank pulley) is the stock-block limit
  (`hi-scan-pro-...320121.md` #316, `supercharging-soon.481426.md` #2,
  `ngm-stage2-sputtering-over-5k.469714.md` #29, `just-bought-alpine-kit-few-questions.480698.md` #2).
  Belt part numbers per stage are in `definitive-supercharger-parts-almanac-217082.md`.
- chase can produce a stage 2 flash, and says a 07/08 ECU conversion is needed
  for stage 2 on those years; on 03-06 it's a direct reflash
  (`hi-scan-pro-...320121.md` #316). With our own toolchain we would do it ourselves;
  the maps that matter are the ones our cal already exposes (WOT enrichment,
  ignition vs load above 480 mg/stk, MAF scaling to ~205 g/s).
- **IAT placement is the trap for boosting the OEM ECU.** With the IAT ahead of
  the blower the ECU sees cool air and gives full timing; every stock-ECU boost
  failure story in the section traces to that or to a lost rotor coating
  (`ignition-advance-issues-with-stock-ecu.469738.md` #8, `ngm-reflash-issue-suggestions-needed-long.479628.md` #9).
- **Market.** MP62 kits (Alpine, NGM Sniper) are what exist; MP90 kits number
  about 7 worldwide. Rebuilds cost USD 900-1200+; GM M62/M90 cores are cheap
  but the bolt pattern, snout and throat are wrong, so a custom manifold is
  required — at which point chase says "you might as well fab a turbo". A TVS
  1320/1740 is the modern replacement people talk about but nobody has fitted
  (`current-options-for-supercharging.485081.md`, `blower-options.485216.md`,
  `a-new-supercharger-build.480966.md`). Alpine's cast intercooled intake is
  stronger and more portable than NGM's sheet-metal one
  (`hopeful-supercharge-purchase.483358.md` #8).
- Scam hygiene when buying: ask for photos of an angle not in the listing,
  reverse-image them, buyer-protected payment only
  (`superchargers-for-an-05-tib-v6.482776.md` #4).
- **chase's cost view:** NA past 200 whp costs more than a turbo to 300-400 whp
  on E85; "these 2.7s will take 400 whp all day on E85 with a late-spooling turbo
  without opening the motor" (`i-want-more-performance.484120.md` #6). Stock
  compression is 10:1 (Mitchell), not 9:1 (`what-its-like-changing-compression.484970.md` #4).

---

## 5. Things to ask chase, ranked

1. What the GKFlasher **crackle** option edits (see §1). Our overrun map is in
   [[puc-overrun-map]]; a two-line answer tells us if the cal-only burble is
   already what everyone runs.
2. Whether the **ghost IACV restrictor** patch is cal-only or program. Rev hang
   on lift is exactly the state-4 window our burble tune lives in
   ([[closed-throttle-recognition]]).
3. His **98 RON ignition delta** by load band — even "+N deg from 280 mg/stk up"
   would calibrate the "no more than 4 deg" folk rule.
4. Whether he has a **5WY17 stage 2 base** for an auto car, if a blower turns up.

---

## 6. What is *not* on the forum

No one there has the ignition/fuel table layout, the engine-state machine, the
PUC mechanism, or checksum details we have — those all live on opengk.org and
in chase's Discord. The forum's Engine Management section before 2019 is
piggyback and canned-reflash era; the "Open Source ECU Tuning" thread (2006,
411 posts) is the pre-history of OpenGK and contains nothing we need.
