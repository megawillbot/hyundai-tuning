# Hardware options

Source: `reference/opengk-wiki/2.7L_V6_Forced_Induction.wiki` (mirrored 2026-08-30).
Read that page directly before trusting this summary — it is the community's list,
not measured data, and **all these kits ended production in the early 2010s**. The
wiki's own recommendation is to custom-build from existing examples.

## Eaton MP62 kits (NGM / Alpine)

Same Eaton case and rotors between NGM and Alpine; snout length and pulley boss
offsets differ. Alpine's intake design makes less power unless the upper manifold
is ported.

| Stage | Claimed | Boost | Tune needed | Adds |
|---|---|---|---|---|
| 0 | 210 whp | 2–3 psi | No | MP62, 3.4" blower pulley, IceBox intake, billet plenum, brackets |
| I | 225 whp | 2–3 psi | No | Heat exchanger, reservoir, intercooler pump |
| II | 260–270 whp | 5–6 psi | **Yes** | 360cc injectors (290cc min), 2.8" blower pulley |
| III | 280–300 whp | 8–10 psi | **Yes** | 6.5" crank pulley, fuel pump. "Pushes the limits of stock blocks" |
| IV | 320–340 whp | 12–13 psi | **Yes** | 7.0" crank pulley, meth/alcohol. **Not recommended on a stock engine** |

## Eaton MP90

MP90 Stage I: 370–385 whp at ~7 psi, ~400 whp on other pulleys. Needs 460cc (or Subaru
440cc) injectors, MafExtender + Mafterburner. Wiki recommends a **standalone ECM** at
this level — which puts it outside what this repo is for.

## Vortech

Wiki section is empty ("coming soon"). Nothing to plan from.

## What's realistic here

Given an **automatic** transaxle of unknown torque capacity and a car that must stay
road-legal in NZ, the honest bracket is **Stage 0/I** — low boost, no tune required —
with the ECU work in this folder aimed at *verifying* the car is safe there rather
than chasing Stage II+ numbers. Anything above Stage I is a transaxle conversation
before it is a tuning conversation.

## Open

- Nothing here is sourced to an automatic car. Every claimed whp figure should be
  assumed to be from a manual.
- Sourcing: no idea what's obtainable in NZ. TODO.
- Intercooling: NZ ambient is mild, but an IceBox air-to-water on a 2–3 psi kit is
  mostly heat-soak insurance. Reassess if the pulley ever changes.
