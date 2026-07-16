# RIX — Resonant Inelastic X-ray

> **Usage note:** This file is a reference for consultation during the LUTE setup
> conversation. Read it to understand what is available at RIX. Do not use it to
> pre-fill YAML values — walk each parameter explicitly with the user and suggest
> values based on what this file says.

---

## Experimental Capacity

LCLS-II NEH soft X-ray RIXS and XAS station at ~250–1500 eV. Two endstations:
**ChemRIX** (Andor Newton VLS spectrometer; chemistry focus, liquid jets, gas phase)
and **qRIXS** (Archon CCD on a curved Rowland circle; high-resolution RIXS). Also
runs time-resolved XAS and pump-probe XES. Integrating detectors (Andor Newton, Archon)
read out slower than the DAQ event rate and require special psana2 configuration.
ePixHR 2x2 provides fast area detection for scattering or beam monitoring.
ePixM 0.3 MP (4/2025) for additional fast detection.

---

## DAQ Generation

**LCLS-II — psana2**
SmallData task: `SmallDataProducer2` (YAML key `SubmitSMD`)

> **Integrating detector requirement:** Andor and Archon detectors must be listed in
> `integrating_detectors` in the `SubmitSMD` parameters. Without this, psana2 will
> misalign events and the detector data will be garbage.

Raw data path: `/sdf/data/lcls/ds/rix/<exp>/xtc2/`
FFB (live): `/sdf/data/lcls/drpsrcf/ffb/rix/<exp>/xtc2/`
SmallData output: `/sdf/data/lcls/ds/rix/<exp>/hdf5/smalldata/`

---

## Experiment Types

| Type | Endstation | Description |
|---|---|---|
| ChemRIXS | ChemRIX | VLS Andor spectrometer; energy-loss spectra at ~120 Hz (FVB mode) |
| qRIXS | qRIXS | Archon CCD on Rowland circle; high-resolution 2D energy-transfer maps |
| TR-XAS | both | Time-resolved X-ray absorption; CCM scan + pump laser |
| Pump-probe XES | both | Emission spectra as a function of pump-probe delay |

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
| Fast area detector | `epixhr` | ePixHR2x2 (psana type `epixhr2x2`); DAQ instance `epixhr_0`; gain modes: H/M/L/AHL/AML |
| VLS spectrometer (ChemRIXS) | `andor_vls` | Andor Newton; FVB at up to 120 Hz; EPICS prefix `RIX:VLS:CAM:01`; integrating |
| Normalization Andor | `andor_norm` | Andor Newton normalization camera; EPICS prefix `RIX:NORM:CAM:01`; integrating |
| Direct-beam Andor | `andor_dir` | Andor Newton direct beam; EPICS prefix `RIX:DIR:CAM:01`; integrating |
| qRIXS spectrometer | `archon` | Archon CCD; EPICS prefix `QRIX:STA:CCD:01`; 4800×1200 px full frame; FVB: 1×4800 (4224 active px); integrating |
| ATM OPAL camera | `atmopal` | At-the-machine OPAL; imaging and beam alignment |
| ePixM (installed 4/2025) | verify via `run.detnames` | ePixM 0.3 MP; fast area detector; alias not yet standardized |

**Andor Newton modes:**
- Full Vertical Binning (FVB): 1D spectrum per shot at up to 120 Hz
- Crop mode: sub-region readout for higher rates
- Integrating: must be passed to `integrating_detectors` in `SubmitSMD`

**Archon CCD geometry (FVB):**
- Full frame: 4800 × 1200 pixels
- Active pixels in FVB: 4224 (= 4800 − 36×16 test pixels from 16 parallel readout banks)
- Pass to `integrating_detectors` in `SubmitSMD`

---

## LUTE-Relevant PVs

### Beam Intensity Monitors (`ipm_var`)

RIX has three Wave8/FIM units. The exact psana alias for each unit must be confirmed
via `detnames -e` on a representative run.

| Unit name (IOC) | IOC instance | Notes |
|---|---|---|
| `mr3k2` | `ioc-rix-pgpw8-01` | Wave8 upstream of first mirror |
| `mr4k2` | `ioc-rix-pgpw8-02` | Wave8 second position |
| `crix` / `chemrix` | `ioc-rix-pgpw8-03` | Wave8 at ChemRIX endstation |

To enumerate the exact psana alias for each Wave8:
```bash
detnames -e exp=<exp>,run=<N>
```

### Scan Variables (`scan_var`)

| psana alias / field | Description | Notes |
|---|---|---|
| `lxt_ttc` | ATM timing delay stage | Primary pump-probe delay |
| mono energy | Grating monochromator energy | Alias varies; verify via `detnames -s` |
| `step_value` | 1-based step counter | Auto-generated in every Bluesky scan |
| `step_docstring` | JSON string with motor names and positions | Human-readable step description |

To enumerate scan variables:
```bash
detnames -s exp=<exp>,run=<N>
```

### Timetool

| EPICS PV | Description | Notes |
|---|---|---|
| `RIX:QRIX:ALV:01:TT:TTALL` | FEX timetool output array | Edge position + quality; on Alvium camera |
| `RIX:QRIX:ALV:01:TT:EnableFEX` | Enable/disable FEX | `caput RIX:QRIX:ALV:01:TT:EnableFEX 1` |

### Standard Shot Flags (psana2)

| psana field | Description |
|---|---|
| `timing.raw.eventcodes(evt)` | EVR event codes fired this shot |
| `timing.raw.pulseId(evt)` | Pulse ID |
| `ebeam.raw.ebeamPhotonEnergy(evt)` | Per-shot photon energy |

---

## LUTE Analysis Chains

| Technique | LUTE task chain |
|---|---|
| ChemRIXS | `SubmitSMD` (`get_intg` + `getROIs` + `writeArea=True`) → `SmallDataXESAnalyzer` |
| qRIXS | `SubmitSMD` (`get_intg` + `getPressioCompression` + `getROIs` + `writeArea=True`) → `SmallDataXESAnalyzer` |
| TR-XAS | `SubmitSMD` (`get_intg` + `getROIs`) → `SmallDataXASAnalyzer` |
| Pump-probe XES | `SubmitSMD` (`get_intg` + `getROIs` + `writeArea=True`) → `SmallDataXESAnalyzer` |
| ePixHR scattering | `SubmitSMD` (`getAzIntPyFAIParams` or `getDroplet2Photons`) — no standard downstream task |

---

## Special Notes

- **`integrating_detectors` is mandatory at RIX.** Always set this field in
  `SubmitSMD` for Andor (ChemRIXS) or Archon (qRIXS). Without it, psana2 event
  alignment will be wrong and the detector data will be corrupt.
  - ChemRIXS: `integrating_detectors: ["andor_vls", "andor_norm"]` (or whichever
    Andors are active — confirm with user)
  - qRIXS: `integrating_detectors: ["archon"]`
- **Pressio compression for qRIXS:** The `getPressioCompression` block must appear
  **before** `getROIs` in the YAML. It applies SZ3 lossy compression to the Archon
  images before ROI extraction.
- **ePixHR calibration:**
  ```bash
  epix10ka_pedestals_calibration -k exp=<exp>,run=<N> -d epixhr
  epix10ka_deploy_constants -k exp=<exp>,run=<N> -d epixhr -D
  ```
- **Shared memory (live):** `DataSource(shmem='rix')` for at-the-machine access.
- **ARP trigger:** Use `END_OF_RUN` for SmallData; downstream analyzers use
  `RUN_PARAM_IS_VALUE:SmallData:done`.
