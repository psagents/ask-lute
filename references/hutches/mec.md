# MEC — Matter in Extreme Conditions

> **Usage note:** This file is a reference for consultation during the LUTE setup
> conversation. Read it to understand what is available at MEC. Do not use it to
> pre-fill YAML values — walk each parameter explicitly with the user and suggest
> values based on what this file says.

---

## Experimental Capacity

High-energy-density (HED) and warm dense matter (WDM) science. Drive laser (Nd:glass
or Nd:YAG) fires at 1–10 Hz; LCLS X-rays at 120 Hz. Single-shot destructive
experiments: shock compression (XRD, VISAR), XRTS (X-ray Thomson scattering),
phase-contrast imaging (PCI), and equation-of-state measurements.

---

## Current LUTE Limitation

**MEC currently outputs per-detector TIFF files, not XTC.** LUTE's `SmallDataProducer`
reads XTC/XTC2 data and cannot process raw MEC data until the XTC2 migration completes.

**What LUTE can do today at MEC:**
- `BayFAIOptimizer` — geometry calibration on powder calibrant runs (CeO₂ or LaB₆),
  once data is available in XTC format or via a compatibility path.

Once XTC2 migration is complete, the full SmallData + downstream analysis chain will
become applicable.

---

## DAQ Generation

**LCLS-I — psana1** (TIFF-only until XTC2 migration)
When migration completes: `SmallDataProducer` (YAML key `SubmitSMD`)

---

## Experiment Types

| Type | Description |
|---|---|
| Shock XRD | Single-shot diffraction on shock-compressed sample |
| XRTS | X-ray Thomson scattering; plasma diagnostics |
| PCI (phase-contrast imaging) | Single-shot phase contrast; alvium cameras |
| VISAR | Velocity interferometry; optical diagnostic |

---

## Detector Inventory

All aliases below must be confirmed with the user via `event_keys` on a representative
run before use in any LUTE configuration.

| Role | Typical psana alias | psana DetInfo source | Notes |
|---|---|---|---|
| XRD area detector (quad 0) | `Epix10kaQuad0` | `MecTargetChamber.0:Epix10kaQuad.0` | ePix10ka quad; one of four panels |
| XRD area detector (quad 1) | `Epix10kaQuad1` | `MecTargetChamber.0:Epix10kaQuad.1` | ePix10ka quad |
| XRD area detector (quad 2) | `Epix10kaQuad2` | `MecTargetChamber.0:Epix10kaQuad.2` | ePix10ka quad |
| XRD area detector (quad 3) | `Epix10kaQuad3` | `MecTargetChamber.0:Epix10kaQuad.3` | ePix10ka quad |
| XRTS spectrometer | `Epix100` | `MecTargetChamber.0:Epix100a.0` | ePix100a; dispersive XRTS spectrometer |
| VISAR / streak camera | run-specific | `MecEndstation.0:Andor.N` | Andor streak; N is run-specific |
| Optical cameras | run-specific | `MecEndstation.0:Opal1000.N` | OPAL cameras; N is run-specific |
| PI-MTE / PI-PIXIS (legacy) | run-specific | `MecTargetChamber.0:Princeton.0` | Princeton CCD; legacy experiments |

---

## LUTE-Relevant PVs

### Beam Intensity Monitors (`ipm_var`)

| smalldata field | Description | Notes |
|---|---|---|
| `ipm3/sum` | IPM3 intensity sum | Primary near-sample I₀ at MEC |
| `gas_detector/f_11_ENRC` | FEE gas detector reading 1 | Upstream absolute pulse energy in mJ |

### Camera Length PVs (`pv_camera_length` — when running BayFAI geometry calibration)

Detector distance PVs at MEC are endstation-specific. Ask the MEC instrument scientist
for the correct EPICS PV for the Epix10ka panel being calibrated.

---

## LUTE Analysis Chains

| Task | LUTE task / ManagedTask | Notes |
|---|---|---|
| Geometry calibration (CeO₂ or LaB₆) | `BayFAIOptimizer` / `BayFAIOptimizer` | Separate calibrant run; one per Epix10ka quad |

**BayFAI calibrant at MEC:** CeO₂ (standard) or LaB₆. The mec.yaml in the LUTE repo
contains geometry priors for each of the four Epix10kaQuad panels.

**Hutch YAML config in LUTE repo:** `config/mec.yaml`

---

## Special Notes

- **TIFF limitation:** Until XTC2 migration is complete, do not attempt to configure
  `SubmitSMD` for raw MEC data — it will find no XTC files.
- **BayFAI per-quad:** Each Epix10ka quad has different geometry parameters. The
  `mec.yaml` in the LUTE repo contains example `center` and `fixed` parameters for
  each quad (Quad0–3); consult it when building the BayFAI config block.
- **Single-shot analysis:** MEC experiments typically have 1–10 real laser shots per
  "run". Per-event TIFF output (not HDF5) is the current standard.
