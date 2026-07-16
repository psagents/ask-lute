# CXI — Coherent X-ray Imaging

> **Usage note:** This file is a reference for consultation during the LUTE setup
> conversation. Read it to understand what is available at CXI. Do not use it to
> pre-fill YAML values — walk each parameter explicitly with the user and suggest
> values based on what this file says.

---

## Experimental Capacity

Two endstations: **Nanofocus** (100 nm focus, primarily SFX and SPI) and
**Microfocus** (1–10 µm focus, CDI/ptychography). Primary use is SFX (~50%),
followed by SPI and CDI. The Opal camera monitors the liquid jet; it is not part of
the LUTE analysis pipeline. Nanofocus endstation transitioning to LCLS-II DAQ
~June 2027 — confirm DAQ generation with the user.

---

## DAQ Generation

**LCLS-I/II — transitional. Always confirm with the user.**

> Ask: "Are your raw files `.xtc` (LCLS-I/psana1) or `.xtc2` (LCLS-II/psana2)?"

- LCLS-I: `SmallDataProducer` (YAML key `SubmitSMD`); raw data at `.../xtc/`
- LCLS-II: `SmallDataProducer2` (YAML key `SubmitSMD`); raw data at `.../xtc2/`

SmallData output: `/sdf/data/lcls/ds/cxi/<exp>/hdf5/smalldata/`

---

## Experiment Types

| Type | Fraction | Description |
|---|---|---|
| SFX (serial femtosecond crystallography) | ~50% | Hit finding → indexing → merging → phasing |
| SPI (single-particle imaging) | ~30% | Sparse hit triggering; radial integration + background subtraction |
| CDI / ptychography | ~20% | Phase retrieval via external tools (Ptypy, PtychoShelves) — not LUTE scope |

---

## Detector Inventory

All aliases below must be confirmed with the user via `event_keys` (psana1) or
`run.detnames` (psana2) on a representative run before use in any LUTE configuration.

| Role | Typical psana alias | psana DetInfo source | Notes |
|---|---|---|---|
| Main SFX area detector | `jungfrau4M` | `CxiEndstation.0:Jungfrau.0` | Jungfrau 4M; primary SFX detector |
| Legacy SFX detector | `cspad` | `CxiDs1.0:Cspad.0` | CSPAD 2.3M; used in older experiments |
| Jet imaging camera | `Opal_0` | `CxiEndstation.0:Opal1000.0` | Opal 1k; monitors the liquid jet; not a LUTE input |

---

## LUTE-Relevant PVs

### Beam Intensity Monitors (`ipm_var`)

CXI does not have a single canonical upstream IPM alias. Ask the user or the CXI
instrument scientist for the correct I₀ monitor alias for their run.

| smalldata field | Description | Notes |
|---|---|---|
| `gas_detector/f_11_ENRC` | FEE gas detector reading 1 | Upstream absolute pulse energy in mJ; always available |
| `gas_detector/f_12_ENRC` | FEE gas detector reading 2 | Average with f_11 for best estimate |
| (in-hutch IPM) | Ask IS for alias | Run-specific; verify via `event_keys` |

### Scan Variables (`scan_var`)

CXI SFX experiments are typically not pump-probe scans; scan variables are
experiment-specific. Ask the user or verify via `event_keys`.

### Camera Length PVs (`pv_camera_length` — SFX only)

The detector distance PV at CXI is endstation- and run-specific. Ask the CXI
instrument scientist for the correct EPICS PV for the detector being used.

| Notes |
|---|
| Typical format: a motor readback PV for the detector stage Z-position |
| Verify with IS before configuring `FindPeaksSFX` or `FindPeaksPyAlgos` |

### Standard Shot Flags (always present in SmallData)

| smalldata field | Description |
|---|---|
| `lightStatus/xray` | X-ray present this shot (bool, from EVR) |
| `ebeam/ebeamL3Energy` | Electron beam L3 energy (MeV) per shot |

---

## LUTE Analysis Chains

| Technique | LUTE task chain |
|---|---|
| SFX (Cheetah path) | `CheetahRunner` → `CrystFELIndexer` → `StreamFileConcatenator` → `PartialatorMerger` → `HKLComparer` / `HKLManipulator` / `DimpleSolver` |
| SFX (psana-native path) | `PeakFinderSFX` → `CrystFELIndexer` → `StreamFileConcatenator` → `PartialatorMerger` → `HKLComparer` / `HKLManipulator` / `DimpleSolver` |
| SFX (CCTBX path) | `PeakFinderSFX` or `CheetahRunner` → `CCTBXIndexer` → `CCTBXMerger` |
| SPI | `SubmitSMD` (radial integration + background subtraction) — no standard LUTE downstream task |
| CDI / ptychography | `SubmitSMD` (reduction only) — phase retrieval via external tools, out of LUTE scope |

**Hutch YAML config in LUTE repo:** `config/cxi.yaml`

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
| CCTBX.XFEL | `IndexCCTBXXFEL` | `CCTBXIndexer` | Common at CXI when CCTBX environment available |

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

- **DAQ confirmation is mandatory at CXI.** Nanofocus endstation moves to LCLS-II
  ~June 2027. Never assume psana1 — always ask the user for file extension.
- **Camera length PV:** CXI's detector distance PV is endstation-specific and not
  documented in the LUTE hutch config. Always ask the IS or user.
- **Opal jet camera:** The Opal camera monitoring the liquid jet is not a LUTE input
  and should not appear in `detnames` for LUTE configuration.
- **CDI/ptychography:** SmallData can handle the reduction step, but iterative phase
  retrieval is outside LUTE's scope (use Ptypy or PtychoShelves externally).
