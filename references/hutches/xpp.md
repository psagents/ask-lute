# XPP — X-ray Pump-Probe

> **Usage note:** This file is a reference for consultation during the LUTE setup
> conversation. Read it to understand what is available at XPP. Do not use it to
> pre-fill YAML values — walk each parameter explicitly with the user and suggest
> values based on what this file says.

---

## Experimental Capacity

Hard X-ray pump-probe station, 2–12 keV, 120 Hz (LCLS-I NC linac). Primary workhorse
for time-resolved solution and solid-state scattering, X-ray absorption, and emission
spectroscopy. Nearly all experiments include an optical pump laser; a timetool is
routinely deployed for laser–X-ray jitter correction. Samples are typically in flowing
liquid jets, capillaries, or thin films on a rotating wheel.

---

## DAQ Generation

**LCLS-I — psana1**
SmallData task: `SmallDataProducer` (YAML key `SubmitSMD`)
Raw data path: `/sdf/data/lcls/ds/xpp/<exp>/xtc/`
SmallData output: `/sdf/data/lcls/ds/xpp/<exp>/hdf5/smalldata/`

---

## Experiment Types

| Type | Description |
|---|---|
| TR-SAXS / TR-WAXS | Time-resolved solution scattering; azimuthal integration of area detector |
| TR-XAS | Time-resolved X-ray absorption; transmission through thin film or solution |
| TR-XES | Time-resolved X-ray emission; dispersive spectrometer (ePix100) |
| XPCS | X-ray photon correlation spectroscopy; split-pulse or multi-pulse |
| Geometry calibration | AgBh or LaB₆ powder run for PyFAI geometry optimization |

---

## Detector Inventory

All aliases below must be confirmed with the user via `event_keys` or `ds.detnames`
on a representative run before use in any LUTE configuration.

| Role | Typical psana alias | psana DetInfo source | Notes |
|---|---|---|---|
| Main area detector (scattering) | `epix10k2M` | `XppEndstation.0:Epix10ka2M.0` | ePix10k2M; primary detector for SAXS/WAXS |
| XAS / XES spectrometer | `epix_1` | `XppEndstation.0:Epix100a.1` | ePix100a; dispersive spectrometer |
| Wide-angle SAXS | `Rayonix` | `XppEndstation.0:Rayonix.0` | Rayonix MX340-HS; not always installed |
| Beam intensity monitor | `wave8` | `XppEndstation.0:Wave8.0` | Wave8 waveform digitizer; beam monitor diodes |
| Secondary ePix (XPCS / spare) | `epix_2` | `XppEndstation.0:Epix100a.2` | ePix100a; used for XPCS or second spectrometer |
| Jungfrau 1M (occasional) | `jungfrau1M` | `XppEndstation.0:Jungfrau.0` | Deployed for some SAXS experiments |
| CSPAD 140k (legacy) | `cspad140k` | `XppSb3Pim.1:Cspad2x2.0` | Legacy diffraction diagnostic; rarely used |

---

## LUTE-Relevant PVs

These are the PVs and smalldata fields that feed directly into LUTE task parameters
(`ipm_var`, `scan_var`, `ccm`, `ttCalib`). Confirm the exact alias in the user's run.

### Beam Intensity Monitors (`ipm_var`)

| smalldata field | Description | Notes |
|---|---|---|
| `ipm2/sum` | IPM2 intensity sum | Primary upstream in-hutch I₀; standard choice |
| `ipm2/xpos`, `ipm2/ypos` | IPM2 beam position | Available alongside sum |
| `ipm3/sum` | IPM3 intensity sum | Secondary downstream IPM; closer to sample |
| `ipm3/xpos`, `ipm3/ypos` | IPM3 beam position | Available alongside sum |
| `gas_detector/f_11_ENRC` | FEE gas detector reading 1 | Upstream absolute pulse energy in mJ |
| `gas_detector/f_12_ENRC` | FEE gas detector reading 2 | Average with f_11 for best estimate |

### Scan Variables (`scan_var`)

| smalldata field | Description | Notes |
|---|---|---|
| `lxt` | Laser–X-ray timing delay | Primary pump-probe delay stage |
| `lxt_fast` | Fast piezo delay | Fine timing scans; used with lxt for coarse+fine |
| `lens_v` | Vertical lens position | Spatial overlap scan |
| `lens_h` | Horizontal lens position | Spatial overlap scan |
| `lxe_opa` | OPA pump wavelength stage | Wavelength-tunable pump experiments |

### Monochromator / CCM (`ccm`, `ccm_set` — XAS experiments only)

| smalldata field | Description | Notes |
|---|---|---|
| `epics/ccm_E` | CCM actual photon energy (eV) | Readback; use as `ccm` in AnalyzeSmallDataXAS |
| `epicsUser/ccm_E_setpoint` | CCM requested energy setpoint | Improves binning quality; use as `ccm_set` |

### Timetool (`ttCalib`)

| smalldata field | Description | Notes |
|---|---|---|
| `tt/ttCorr` | Timetool corrected delay (ps) | Primary jitter-corrected timestamp |
| `tt/AMPL` | Timetool edge amplitude | Quality cut: shots with AMPL < 0.02 unreliable |
| `tt/fltpos` | Raw timetool position (pixels) | Pre-correction position |
| `tt/fltpos_ps` | Timetool position in ps | Before calibration correction |

### Standard Shot Flags (always present in SmallData)

| smalldata field | Description |
|---|---|
| `lightStatus/xray` | X-ray present this shot (bool, from EVR) |
| `lightStatus/laser` | Laser present this shot (bool, from EVR) |
| `ebeam/ebeamL3Energy` | Electron beam L3 energy (MeV) per shot |

---

## LUTE Analysis Chains

| Technique | LUTE task chain |
|---|---|
| TR-SAXS / TR-WAXS | `SubmitSMD` (`getAzIntPyFAIParams` or `getAzIntParams`) → `SmallDataXSSAnalyzer` |
| TR-XAS | `SubmitSMD` (`getROIs` for spectrometer) → `SmallDataXASAnalyzer` |
| TR-XES | `SubmitSMD` (`getROIs` + `writeArea=True`) → `SmallDataXESAnalyzer` |
| XPCS | `SubmitSMD` (`getAutocorrParams`) — no standard downstream LUTE task |
| Geometry calibration | `BayFAIOptimizer` (LCLS-I) — separate calibrant run, independent of main chain |

**Hutch YAML config in LUTE repo:** `config/xpp.yaml`

---

## Special Notes

- **PyFAI `.poni` file:** If a `.poni` calibration file exists for the detector, use
  `getAzIntPyFAIParams`; otherwise use `getAzIntParams` with manual geometry
  (beam energy, center, sample-to-detector distance).
- **Timetool:** Standard at XPP; enable `ttCalib` in `producer_parameters`. Shots with
  `tt/AMPL < 0.02` should be cut in downstream analysis.
- **XPCS photon counting:** ePix100 (`epix_1` or `epix_2`) in sparse regime; use
  `getDropletParams` or `getDroplet2Photons` depending on occupancy. Ask user for
  ADU-per-photon at their gain setting.
- **Detector accumulation:** `detSumAlgos` defaults to `calib`, `calib_dropped`,
  `calib_dropped_square` for all detectors unless overridden.
