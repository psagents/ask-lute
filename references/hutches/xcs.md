# XCS — X-ray Correlation Spectroscopy

> **Usage note:** This file is a reference for consultation during the LUTE setup
> conversation. Read it to understand what is available at XCS. Do not use it to
> pre-fill YAML values — walk each parameter explicitly with the user and suggest
> values based on what this file says.

---

## Experimental Capacity

Hard X-ray correlation spectroscopy instrument. Primary for XPCS and speckle dynamics
(two-time correlation of dilute or concentrated colloidal/polymer systems), liquid SAXS,
and XES via a vonHamos bent-crystal spectrometer. Also runs TR-XAS and pump-probe
scattering. **XCS is closing; it will be replaced by DXS (Dynamic X-ray Scattering),
first light ~June 2028.** New DXS will use SparkPix detectors and psana2.

---

## DAQ Generation

**LCLS-I — psana1**
SmallData task: `SmallDataProducer` (YAML key `SubmitSMD`)
Raw data path: `/sdf/data/lcls/ds/xcs/<exp>/xtc/`
SmallData output: `/sdf/data/lcls/ds/xcs/<exp>/hdf5/smalldata/`

---

## Experiment Types

| Type | Description |
|---|---|
| XPCS / speckle dynamics | Two-time photon correlation; dilute to dense systems |
| Liquid SAXS / WAXS | Solution scattering; azimuthal integration |
| XES (vonHamos) | X-ray emission spectroscopy via bent-crystal spectrometer |
| TR-XAS | Time-resolved absorption; CCM scan + pump-probe |
| TR-SAXS / TR-WAXS | Pump-probe difference scattering |

---

## Detector Inventory

All aliases below must be confirmed with the user via `event_keys` or `ds.detnames`
on a representative run before use in any LUTE configuration.

| Role | Typical psana alias | psana DetInfo source | Notes |
|---|---|---|---|
| Main area detector (XPCS / scattering) | `epix10k2M` | `XcsEndstation.0:Epix10ka2M.0` | ePix10k2M; primary detector |
| XES / XPCS sparse spectrometer | `epix_2` | `XcsEndstation.0:Epix100a.2` | ePix100a; vonHamos spectrometer or XPCS sparse |
| Secondary ePix (spare / XAS) | `epix_1` | `XcsEndstation.0:Epix100a.1` | ePix100a; alternate spectrometer position |
| Jungfrau 1M (occasional) | `jungfrau1M` | `XcsEndstation.0:Jungfrau.0` | Deployed for some SAXS experiments |
| vonHamos crystal spectrometer | detector depends on configuration | — | Dispersive crystal; signal projected onto ePix100 |

---

## LUTE-Relevant PVs

These are the PVs and smalldata fields that feed directly into LUTE task parameters.
Confirm the exact alias in the user's run.

### Beam Intensity Monitors (`ipm_var`)

| smalldata field | Description | Notes |
|---|---|---|
| `ipm5/sum` | IPM5 intensity sum | Primary in-hutch I₀ at XCS |
| `ipm5/xpos`, `ipm5/ypos` | IPM5 beam position | Available alongside sum |
| `gas_detector/f_11_ENRC` | FEE gas detector reading 1 | Upstream absolute pulse energy in mJ |
| `gas_detector/f_12_ENRC` | FEE gas detector reading 2 | Average with f_11 for best estimate |

### Scan Variables (`scan_var`)

| smalldata field | Description | Notes |
|---|---|---|
| `lxt` | Laser–X-ray timing delay | Primary pump-probe delay stage |
| `lxt_fast` | Fast piezo delay | Fine timing scans |
| `lxe_opa` | OPA pump stage | Wavelength-tunable pump experiments |
| `lens_v` | Vertical lens position | Spatial overlap scan |
| `lens_h` | Horizontal lens position | Spatial overlap scan |

### Monochromator / CCM (`ccm`, `ccm_set` — XAS experiments only)

| smalldata field | Description | Notes |
|---|---|---|
| `epics/ccm_E` | CCM actual photon energy (eV) | Readback; use as `ccm` in AnalyzeSmallDataXAS |
| `epicsUser/ccm_E_setpoint` | CCM requested energy setpoint | Improves binning; use as `ccm_set` |

### Timetool (`ttCalib`)

| smalldata field | Description | Notes |
|---|---|---|
| `tt/ttCorr` | Timetool corrected delay (ps) | Primary jitter-corrected timestamp |
| `tt/AMPL` | Timetool edge amplitude | Quality cut: shots with AMPL < 0.02 unreliable |

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
| XPCS / speckle dynamics | `SubmitSMD` (`getAutocorrParams`) — no standard downstream LUTE task |
| Liquid SAXS / WAXS | `SubmitSMD` (`getAzIntPyFAIParams` or `getAzIntParams`) → `SmallDataXSSAnalyzer` |
| XES (vonHamos) | `SubmitSMD` (`getROIs` + `writeArea=True`) → `SmallDataXESAnalyzer` |
| TR-XAS | `SubmitSMD` (`getROIs` for spectrometer) → `SmallDataXASAnalyzer` |
| TR-SAXS / TR-WAXS | `SubmitSMD` (`getAzIntPyFAIParams` or `getAzIntParams`) → `SmallDataXSSAnalyzer` |

**Hutch YAML config in LUTE repo:** `config/xcs.yaml`

---

## Special Notes

- **XPCS photon counting:** ePix100 (`epix_2`) in sparse regime (occupancy ~10⁻³–10⁻¹
  ph/px). Use `getDropletParams` (single-photon droplets) or `getDroplet2Photons`
  (two-photon discrimination). Ask user for ADU-per-photon at their gain setting.
- **vonHamos XES:** Enable `writeArea=True` in `getROIs` to save the full spectrometer
  image per shot; `SmallDataXESAnalyzer` then projects along the energy axis.
- **Closing status:** XCS end-of-life ~2028. DXS will replace it with SparkPix
  detectors and a psana2 DAQ. Any XCS setup today is for the remaining LCLS-I lifetime.
- **Timetool:** Present at XCS for pump-probe experiments; enable `ttCalib` when a
  pump laser is running.
