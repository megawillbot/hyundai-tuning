# Program-zone work — plan

Written **2026-09-03**. Everything the calibration cannot do lives in the
program zone: the hard-coded "all six injectors" final stage of the overrun cut,
the SecurityAccess seed/key, the rev-limit clamp chain, launch/2-step, and so on.
This is the plan for touching it safely. **Nothing in the program zone has been
flashed yet.** The first candidate is built and verified offline
(`roms/tunes/puc-final-stage-patch/`).

## 1. What is established

| fact | evidence |
|---|---|
| Program image = file `0x10000`–`0x4A6A6` (physical `0x90000`–`0xCA6A6`), identical to three OpenGK dumps | [[ecu-architecture]] §1 |
| **Checksum: four chained CRC-16 zones**, header at file `0x10010`, init at `0x10052`: `0x10210`–`0x1FFFC`, `0x20000`–`0x30000`, `0x30000`–`0x40000`, `0x40000`–`0x4A6A6` | GKFlasher `--correct-checksum` on `roms/stock/FULL_ca654019_stock_merged.bin` reports current == computed (`0x2ef1`) for Program and Calibration |
| GKFlasher's `v6 (5WY17)` checksum type covers Boot (skipped, we never read it), Calibration and Program | `flasher/checksum.py` |
| **Free space inside the checksummed zones:** `0x10FFE`–`0x11F02` (3844 bytes, zone 1), `0x100EA` (294 bytes), `0x12D94` (366 bytes, right after the KWP jump table — avoid) | scan of FF runs in the code region |
| Free space **outside** the zones: `0x4A6A6`–`0x80000` (erased flash) — flashable, but unverified by the checksum; don't use it | zone table |
| `--flash-program` exists in GKFlasher: routine `0x00` erase, write from `program.write.address + 16` to the last non-FF byte, then routine `0x02` verify/mark-executable | `gkflasher.py` `cli_flash_eeprom` |
| The Boot region (`0x0000`–`0x8000`, bootloader) is **not** written by either flash path | same |
| Program-zone flashing needs only the Hyundai-level security access GKFlasher already does for the cal. The IOCLID escalation is for *reading* the boot/NVM areas | [[car-notes]] |

## 2. What is *not* established — verify before the first flash

1. **The write-offset arithmetic for the program zone.** `flash_start =
   program.write.size + 16` (= `0x70010` for our definition) is generic upstream
   code; the cal path uses a different formula with a "don't know why" comment.
   Nobody in our records has run `--flash-program` on a 5WY17 over K-line. **Ask
   chase / the OpenGK channel whether anyone has, and on which ECU.** If not, the
   candidate should be the first, with the recovery plan below in place.
2. **Recovery after a failed verify.** GKFlasher prints "soft-bricked, flash a
   valid file" — i.e. the bootloader still answers KWP after a bad program image.
   Plausible (the boot region is separate and untouched) but untested by us.
   Worst case is a BSL bench flash; the wiki mirror has the SIMK BSL docs
   (`reference/opengk-wiki/`).
3. **Whether routine `0x02` checks anything beyond the four zones** (e.g. that
   bytes after `0x4A6A6` are erased). Irrelevant as long as patches stay inside
   the zones — which is the rule.

## 3. Toolchain and rules for a patch

- **No assembler.** Stubs are hand-encoded from instruction forms already present
  in the listing (every opcode used so far has a byte-identical twin in the stock
  code) and **verified by disassembling the patched file** with
  `tools/c166/c166dis.py`. Keep stubs tiny; if a patch needs more than a few
  dozen bytes, write the assembler first.
- **Place stubs in the zone-1 padding at `0x11000`+.** Segment `0x09`, so a
  stub at file `0x11000` is `CALLS 0x09, 0x1000`.
- **Preserve every entry point** into a patched block (jump-table targets,
  branch targets from elsewhere). Find them by grepping the listing for the
  address before overwriting.
- **Mirror stock call sequences** for library routines (axis search →
  lookup) so register/RAM-scratch conventions are exactly what the stock code
  already relies on.
- **Account for every differing byte** against
  `roms/stock/FULL_ca654019_stock_merged.bin` before flashing; the count must
  equal checksum bytes + stub + patch.
- `--correct-checksum` the full image, then re-run it answering `n` and confirm
  both regions report current == new.
- Cal changes a patch depends on are flashed **first**, so a failed program
  flash leaves a stock program on a cal it ignores — never a patched program
  looking at a table that is still `FF`.
- Read back both zones after flashing (`--read-program`, `--read-calibration`)
  and compare to the candidate byte-for-byte before starting the engine.

## 4. Patch 1 — overrun-cut final stage from a table (prepared)

Why: the stock cut sequence is `ID_PAT_INH_IV_PUC_1` (rpm-indexed) for 11
cycles, then `ID_PAT_INH_IV_PUC_2` for 11, then a **hard-coded pattern index
`0x0D`** = all six injectors until fuel resumes. The rpm-indexed stages are far
too short to matter; the steady state is the only stage that can carry an rpm
window, and it is not in the calibration. Full mechanism in [[puc-overrun-map]].

What: replace the constant with a stepped 1-D lookup of a **new table
`ID_PAT_INH_IV_PUC_3__N_32` at cal `0xBC8B`** (a 24-byte FF hole no def or
operand references) on the existing `0x8757` rpm/32 axis. 26-byte stub at
`0x11000`, 32-byte handler rewrite at `0x14574` preserving both entry points.
Candidate image, byte accounting and flash order:
`roms/tunes/puc-final-stage-patch/notes.md`.

With the new table set to `0D ×6` the candidate is **functionally identical to
the car as it is** — a rehearsal of the flash path with no behaviour change.

## 5. Sequence

1. **Capture run** ([[next-capture-script]]). Still the gate. It validates the
   overrun model on hardware and now has a sharper prediction: on a warm 4000+
   lift, per-cylinder injection (logger pos 43–54) drops **one cylinder first,
   then four, then all six** within a few engine cycles, and returns at ~1248 rpm.
   Also settles which logger channel is engine state, if any.
2. **Confirm the flash path** (§2 item 1) with chase / OpenGK.
3. Battery on a charger, laptop on mains, stock merged image and the ghost-cam
   cal at hand. Flash the candidate **cal first, then program**, read both back,
   compare, start, idle, drive — behaviour must be indistinguishable from today.
4. **The pop tune itself is then cal-only:** `0xBC8B` = `0D 0D 0D 0D 0D <p>`,
   move the top breakpoint of the `0x8757` axis (`0x875C`, currently 78 = 2496
   rpm) to 109 = 3488 rpm — safe, all four tables on that axis are flat with
   rpm — and add retard in the 3500-rpm column of `IP_IGA_PUC_AT__N` (`0xA198`,
   already the top breakpoint of its axis, so no axis move). Pattern `<p>`
   choice and the datum for the retard are in [[puc-overrun-map]].
5. One change at a time, datalog each, commit each bin.

## 6. Later program-zone candidates (not started)

- **SecurityAccess seed→key** (handler `0x4219E`): would give native
  ReadMemByAddress / WriteMemByAddress and a way to read the `0x48000` adaptive
  shadow live. Reading the algorithm out is bounded work; nothing to flash.
- **Rev-limit clamp chain** (`0x1319E`): raising `C_N_MAX` may be enough; if a
  lower cap in the chain bites, that is a patch.
- **Overrun-cut entry conditions** (`0x1C3CE`+): an rpm *upper* bound for the
  cut (fuel on above X) would be a 10-byte patch if the pattern approach in §4
  turns out not to give the sound wanted.
- **2-step / launch**: `C_N_FCUT` / `C_N_MAX_FCUT` (cal) first; only if a
  clutch/brake-conditioned variant is wanted.

## 7. Risks, plainly

- First program flash on this ECU with this tool: the only step in the whole
  project with a non-trivial brick risk. Mitigate with §2 and §3; accept that the
  fallback is a bench BSL session.
- Ghost cams is on the car; the candidate carries it forward unchanged. If the
  ghost-cam cal is ever reverted, rebuild the candidate on the new base.
- Pops on a 4×O2 car with the cat in the front manifold: thermal risk is real
  and the cat-protection model cannot see it ([[full-map-ca654019]] §6). Keep
  windows short and high-rpm only; that is the point of the rpm gate.
