# MFX — Macromolecular Femtosecond Crystallography

> **Usage note:** This file is a reference for consultation during the LUTE setup
> conversation. Read it to understand what is available at MFX. Do not use it to
> pre-fill YAML values — walk each parameter explicitly with the user and suggest
> values based on what this file says.

---

## Experimental Capacity

Primary SFX instrument (~70% of beam time), also running liquid SAXS/WAXS + pump-probe
and XES (~30%). Beam energy hard X-ray. Jungfrau 16M arriving 2025 for SFX. Some
endstations already run LCLS-II DAQ — always confirm `.xtc` vs `.xtc2` with the user
before choosing the SmallData task. Timetool is deployed for pump-probe experiments.

---

## DAQ Generation

**LCLS-I/II — Moved to LCLS-II since July 2025. Always confirm with the user.**

> Ask: "Are your raw files `.xtc` (LCLS-I/psana1) or `.xtc2` (LCLS-II/psana2)?"

- LCLS-I: `SmallDataProducer` (YAML key `SubmitSMD`); raw data at `.../xtc/`
- LCLS-II: `SmallDataProducer2` (YAML key `SubmitSMD`); raw data at `.../xtc2/`

SmallData output (both): `/sdf/data/lcls/ds/mfx/<exp>/hdf5/smalldata/`

---

## Experiment Types

| Type | Fraction | Description |
|---|---|---|
| SFX (serial femtosecond crystallography) | ~70% | Hit finding → indexing → merging → phasing |
| TR-SAXS / TR-WAXS | ~20% | Solution scattering + pump-probe |
| XES | ~10% | Dispersive emission spectrometer (ePix100 or Andor) |
| TR-XAS | occasional | CCM scan + pump-probe |

---

## Detector Inventory

All aliases below must be confirmed with the user via `event_keys` (psana1) or
`run.detnames` (psana2) on a representative run before use in any LUTE configuration.

| Role | Typical psana alias | psana DetInfo source | Notes |
|---|---|---|---|
| Main SFX / scattering area det | `jungfrau` | `MfxEndstation.0:Jungfrau.0` | Jungfrau 16M; primary for SFX and SAXS since Jul 2025 |
| XES / XAS spectrometer | `epix100_0` | `MfxEndstation.0:Epix100a.0` | ePix100a; dispersive spectrometer |
| Wide-angle SAXS | `Rayonix` | `MfxEndstation.0:Rayonix.0` | Rayonix MX340-HS; not always installed |

---

## LUTE-Relevant PVs

### Beam Intensity Monitors (`ipm_var`)

| smalldata field | Description | Notes |
|---|---|---|
| `ipm_dg2/sum` | IPM DG2 intensity sum | Primary in-hutch I₀ at MFX |
| `ipm_dg2/xpos`, `ipm_dg2/ypos` | IPM DG2 beam position | Available alongside sum |
| `gas_detector/f_11_ENRC` | FEE gas detector reading 1 | Upstream absolute pulse energy in mJ |
| `gas_detector/f_12_ENRC` | FEE gas detector reading 2 | Average with f_11 for best estimate |

### Scan Variables (`scan_var`)

| smalldata field | Description | Notes |
|---|---|---|
| `lxt` | Laser–X-ray timing delay | Primary pump-probe delay stage |
| `lxt_fast` | Fast piezo delay | Fine timing scans |
| `lens_v` | Vertical lens position | Spatial overlap scan |
| `lens_h` | Horizontal lens position | Spatial overlap scan |

### Von Hamos Spectrometer (`epicsArchFilePV` — XES experiments)

| EPICS PV | Alias | Description |
|---|---|---|
| `MFX:SPEC:C1:TILT.RBV` | `vh_cr1_pitch` | Crystal 1 tilt |
| `MFX:SPEC:C1:X.RBV` | `vh_cr1_trans` | Crystal 1 translation |
| `MFX:SPEC:C1:ROT.RBV` | `vh_cr1_yaw` | Crystal 1 yaw |
| `MFX:SPEC:C2:TILT.RBV` | `vh_cr2_pitch` | Crystal 2 tilt |
| `MFX:SPEC:C2:X.RBV` | `vh_cr2_trans` | Crystal 2 translation |
| `MFX:SPEC:C2:ROT.RBV` | `vh_cr2_yaw` | Crystal 2 yaw |
| `MFX:SPEC:C3:TILT.RBV` | `vh_cr3_pitch` | Crystal 3 tilt |
| `MFX:SPEC:C3:X.RBV` | `vh_cr3_trans` | Crystal 3 translation |
| `MFX:SPEC:C3:ROT.RBV` | `vh_cr3_yaw` | Crystal 3 yaw |
| `MFX:SPEC:C4:TILT.RBV` | `vh_cr4_pitch` | Crystal 4 tilt |
| `MFX:SPEC:C4:X.RBV` | `vh_cr4_trans` | Crystal 4 translation |
| `MFX:SPEC:C4:ROT.RBV` | `vh_cr4_yaw` | Crystal 4 yaw |
| `MFX:SPEC:C5:TILT.RBV` | `vh_cr5_pitch` | Crystal 5 tilt |
| `MFX:SPEC:C5:X.RBV` | `vh_cr5_trans` | Crystal 5 translation |
| `MFX:SPEC:C5:ROT.RBV` | `vh_cr5_yaw` | Crystal 5 yaw |
| `MFX:SPEC:C6:TILT.RBV` | `vh_cr6_pitch` | Crystal 6 tilt |
| `MFX:SPEC:C6:X.RBV` | `vh_cr6_trans` | Crystal 6 translation |
| `MFX:SPEC:C6:ROT.RBV` | `vh_cr6_yaw` | Crystal 6 yaw |
| `MFX:SPEC:ROT.RBV` | `vh_rot` | Spectrometer overall rotation |
| `MFX:SPEC:T1.RBV` | `vh_y` | Spectrometer Y translation |
| `MFX:SPEC:T2.RBV` | `vh_x1` | Spectrometer X1 translation |
| `MFX:SPEC:T3.RBV` | `vh_x2` | Spectrometer X2 translation |

Save via `epicsArchFilePV` (archiver, shot-to-shot). Confirmed from `mfx101592326`.

### Monochromator / CCM (`ccm`, `ccm_set` — XAS/XES experiments only)

| smalldata field | Description | Notes |
|---|---|---|
| `epics/ccm_E` | CCM actual photon energy (eV) | Readback; use as `ccm` in AnalyzeSmallDataXAS |
| `epicsUser/ccm_E_setpoint` | CCM requested energy setpoint | Improves binning; use as `ccm_set` |

### Timetool (`ttCalib`)

| smalldata field | Description | Notes |
|---|---|---|
| `tt/ttCorr` | Timetool corrected delay (ps) | Primary jitter-corrected timestamp |
| `tt/AMPL` | Timetool edge amplitude | Quality cut: shots with AMPL < 0.02 unreliable |

### Camera Length PVs (`pv_camera_length` — SFX only)

These PVs feed the `pv_camera_length` parameter in `FindPeaksSFX` / `FindPeaksPyAlgos`
to read the detector distance per run.

| EPICS PV | Detector | Notes |
|---|---|---|
| `MFX:ROB:CONT:POS:Z` | jungfrau / ePix10k2M | Robot Z-axis position; detector distance in mm |
| `MFX:DET:MMS:04.RBV` | Rayonix | Motor readback; detector distance in mm |

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
| SFX (Cheetah path) | `CheetahRunner` → `CrystFELIndexer` → `StreamFileConcatenator` → `PartialatorMerger` → `HKLComparer` / `HKLManipulator` / `DimpleSolver` |
| SFX (psana-native path) | `PeakFinderSFX` → `CrystFELIndexer` → `StreamFileConcatenator` → `PartialatorMerger` → `HKLComparer` / `HKLManipulator` / `DimpleSolver` |
| SFX (CCTBX path) | `PeakFinderSFX` or `CheetahRunner` → `CCTBXIndexer` → `CCTBXMerger` |
| TR-SAXS / TR-WAXS | `SubmitSMD` (`getAzIntPyFAIParams` or `getAzIntParams`) → `SmallDataXSSAnalyzer` |
| XES | `SubmitSMD` (`getROIs` + `writeArea=True`) → `SmallDataXESAnalyzer` |
| TR-XAS | `SubmitSMD` (`getROIs` for spectrometer) → `SmallDataXASAnalyzer` |
| Geometry calibration | `SubmitSMD` (`detSumAlgos` on area detector) → `BayFAIOptimizer` (LCLS-I) or `BayFAIOptimizer2` (LCLS-II) — separate calibrant run |

**Hutch YAML config in LUTE repo:** `config/mfx.yaml`

---

## SFX Analysis Chain (Full)

SFX is the most complex LUTE pipeline. The complete chain from raw XTC to structure
factors:

```
XTC / XTC2 data
  └─► Hit finding (peak detection on each diffraction pattern)
        └─► Indexing (lattice determination per hit)
              └─► Stream concatenation (merge per-node .stream outputs)
                    └─► Merging (scale + merge partial reflections)
                          ├─► Merge statistics (R-split, CC*, completeness)
                          ├─► HKL manipulation (format conversion / scaling)
                          └─► Phasing (molecular replacement or ab initio)
```

### Peak finding — choose one backend

| Backend | LUTE task class | ManagedTask name | When to use |
|---|---|---|---|
| Cheetah | `RunCheetah` | `CheetahRunner` | Standard at MFX/CXI; Cheetah must be installed separately; outputs `.cxi` or stream |
| psana peakfinder8 | `FindPeaksSFX` | `PeakFinderSFX` | No external dependency; native psana peakfinder; use when Cheetah unavailable |

### Indexing — choose one backend

| Backend | LUTE task class | ManagedTask name | When to use |
|---|---|---|---|
| CrystFEL `indexamajig` | `IndexCrystFEL` | `CrystFELIndexer` | Standard; algorithms: xgandalf (default), mosflm, asdf, dirax, pinkindexer |
| CCTBX.XFEL | `IndexCCTBXXFEL` | `CCTBXIndexer` | Alternative when CCTBX environment available |

### Post-indexing (CrystFEL path)

| Step | LUTE task class | ManagedTask name | Notes |
|---|---|---|---|
| Concatenate streams | `ConcatenateStreamFiles` | `StreamFileConcatenator` | Merges per-node `.stream` files |
| Merge | `MergePartialator` | `PartialatorMerger` | CrystFEL `partialator`; symmetry required |
| Merge statistics | `CompareHKL` | `HKLComparer` | R-factors, CC*, completeness |
| HKL manipulation | `ManipulateHKL` | `HKLManipulator` | Scaling, format conversion (e.g. → mtz) |
| Molecular replacement | `DimpleSolve` | `DimpleSolver` | DIMPLE; requires reference PDB |
| Ab initio phasing | `RunSHELXC` | `SHELXRunner` | SHELXC/D/E; when no reference structure exists |

### Post-indexing (CCTBX path)

| Step | LUTE task class | ManagedTask name |
|---|---|---|
| Merge | `MergeCCTBXXFEL` | `CCTBXMerger` |

---

## Special Notes

- **DAQ confirmation is mandatory at MFX.** Some endstations are already on LCLS-II
  DAQ. Never assume psana1 — always ask the user for file extension (`.xtc` vs `.xtc2`).
- **SFX + SmallData in parallel:** SmallData can run simultaneously with SFX for online
  monitoring, but it is not part of the SFX pipeline.
- **Andor XES:** If the XES spectrometer is an Andor camera (integrating, slower than
  120 Hz), use `get_intg` in `producer_parameters` with the Andor as `intg_main`.
- **BayFAI calibrant at MFX:** AgBh or LaB₆ powder for geometry optimization before
  the main experiment.
- **`detSumAlgos` for BayFAI:** `detSumAlgos` accumulates detector frames across all
  events in a run into a single image. It is **not** azimuthal integration. BayFAI
  takes this accumulated image and fits the AgBh powder ring positions to optimize
  detector geometry. Use `"calib_max"` (per-pixel maximum across all shots) — this
  outperforms `"calib"` (sum) for BayFAI because bright AgBh rings stand out more
  clearly against background noise in a max-projection. Configure on the area detector
  (e.g. `jungfrau`) in `SubmitSMD.producer_parameters` for the geometry calibration run:
  ```yaml
  detSumAlgos:
    jungfrau:
      - "calib_max"
  ```
