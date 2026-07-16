# TMO — Time-resolved Molecular & Optical

> **Usage note:** This file is a reference for consultation during the LUTE setup
> conversation. Read it to understand what is available at TMO. Do not use it to
> pre-fill YAML values — walk each parameter explicitly with the user and suggest
> values based on what this file says.

---

## Experimental Capacity

LCLS-II NEH soft X-ray pump-probe station for ultrafast molecular and optical science.
Runs electron/ion time-of-flight (TOF), coincidence imaging, ultrafast molecular
dynamics, and photoionization at up to 1 MHz burst rate. Seven HSD (High-Speed
Digitizer) boards with onboard FEX (feature extraction) provide per-shot TOF waveform
peak-finding. AMI2 handles real-time online analysis; LUTE runs batch/offline production
triggered by ARP after the run completes.

---

## DAQ Generation

**LCLS-II — psana2**
SmallData task: `SmallDataProducer2` (YAML key `SubmitSMD`)
Raw data path: `/sdf/data/lcls/ds/tmo/<exp>/xtc2/`
FFB (live): `/sdf/data/lcls/drpsrcf/ffb/tmo/<exp>/xtc2/`
SmallData output: `/sdf/data/lcls/ds/tmo/<exp>/hdf5/smalldata/`

---

## Experiment Types

| Type | Description |
|---|---|
| Electron / ion TOF | Per-shot FEX peaks from HSD boards; COLTRIMS-style or single-channel TOF |
| Pump-probe AMO | Ultrafast molecular dynamics; XUV + optical pump |
| Photoionization | Differential cross-sections; angle-resolved ion/electron detection |
| Coincidence imaging | Multi-hit coincidence on TOF + position-sensitive detector |

---

## Detector Inventory

All aliases must be confirmed with the user via `run.detnames` on a representative run.
For LCLS-II, run:
```python
ds = DataSource(exp='<exp>', run=<N>)
run = next(ds.runs())
print(run.detnames)
```

| Role | Typical psana alias | Notes |
|---|---|---|
| HSD waveform digitizer | `mrco_hsd` or `hsd` | 7 boards; FEX peaks via `det.raw.peaks(evt)`; per-shot TOF |
| ATM OPAL camera (primary) | `tmo_atmopal` | Opal 1k; at-the-machine imaging |
| OPAL camera (secondary) | `tmo_opal1` | Second OPAL |
| FZP Piranha line camera | `tmo_fzppiranha_0` | Fresnel zone plate focus monitor |
| GMD streamed | `gmdstr0` | Gas Monitor Detector; streamed per shot |
| Electron beam BLD | `ebeam` | `det.raw.ebeamPhotonEnergy(evt)` for per-shot photon energy |
| Timing system | `timing` | `det.raw.eventcodes(evt)`, `det.raw.pulseId(evt)` |

**HSD board IDs at TMO:** 1A, 1B, 3D, 3E, 5E, B2, DA (7 boards total).
Each board has two FEX sub-channels (A and B).
EPICS IOC prefix: `DAQ:TMO:HSD:1_<ID>` (e.g. `DAQ:TMO:HSD:1_1A`).
Physical signal → board mapping is experiment-specific; check the `.cnf` file or
ask the TMO instrument scientist.

---

## LUTE-Relevant PVs

### Beam Intensity Monitors (`ipm_var`)

For psana2, beam monitor PVs are accessed as EPICS detectors via their psana alias
(name from `run.detnames`) or directly by EPICS PV string.

| psana alias | EPICS PV | Description | Notes |
|---|---|---|---|
| `Keithley_Sum` | `EM2K0:XGMD:HPS:KeithleySum` | XGMD (X-ray Gas Monitor); primary I₀ | Most direct X-ray fluence measurement |
| `IM2K4_XrayPower` | `IM2K4:PPM:SPM:VOLT_RBV` | Power/position monitor (PPM) upstream | Alternative I₀; verify alias via `detnames -e` |
| `IM3K4_XrayPower` | `IM3K4:PPM:SPM:VOLT_RBV` | PPM midstream | Verify alias via `detnames -e` |
| `IM4K4_XrayPower` | `IM4K4:PPM:SPM:VOLT_RBV` | PPM downstream | Verify alias via `detnames -e` |

> Access EPICS detectors in psana2 with `det(evt)` (parentheses), not `det.raw.xxx`.

### Scan Variables (`scan_var`)

| psana alias / field | Description | Notes |
|---|---|---|
| `lxt_ttc` | ATM timing delay stage | Primary pump-probe delay; laser–X-ray timing |
| `step_value` | 1-based step counter | Auto-generated in every Bluesky scan |
| `step_docstring` | JSON string with motor names and positions | Human-readable step description |
| mono energy | Grating monochromator position | Alias varies; verify via `detnames -s` |

To enumerate all scan variables for a run:
```bash
detnames -s exp=<exp>,run=<N>
```

### Standard Shot Flags (psana2)

| psana field | Description |
|---|---|
| `timing.raw.eventcodes(evt)` | List of EVR event codes fired this shot |
| `timing.raw.pulseId(evt)` | Pulse ID for this shot |
| `ebeam.raw.ebeamPhotonEnergy(evt)` | Per-shot photon energy |

---

## LUTE Analysis Chains

| Technique | LUTE task chain |
|---|---|
| Electron / ion TOF | `SubmitSMD` (HSD waveform ROIs via `getROIs`) — further analysis is custom |
| Pump-probe AMO | `SubmitSMD` — SmallData HDF5 feeds user notebooks; no standard downstream LUTE task |

**Note:** TMO has no standard downstream LUTE analysis task. `SmallDataProducer2` is
the primary LUTE deliverable; the SmallData HDF5 is consumed by user-written notebooks.

---

## Special Notes

- **HSD / FEX access in psana2:**
  ```python
  det = run.Detector('mrco_hsd')
  for evt in run.events():
      fex = det.raw.peaks(evt)  # dict: segment → channel → (startpos, peaks)
  ```
- **L3T event veto:** TMO uses Level-3 Trigger event vetoing; the effective event count
  seen by LUTE may be significantly lower than the shot count — this is normal.
- **Shared memory (live):** `DataSource(shmem='tmo')` for at-the-machine online access.
- **ARP trigger:** Use `END_OF_RUN` trigger for batch SmallData production.
