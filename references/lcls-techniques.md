# LCLS Instruments and Experiment Types

This reference supports Phase 4 inference. Use it to understand what kind of science runs
at each hutch, which detectors are involved, and which LUTE tasks are relevant — so the
skill can propose an analysis chain tailored to the user's experiment rather than asking
open-ended questions from scratch.

**The skill builds a workflow from scratch every time.** This file describes the science
and infrastructure context. The analysis chain (which tasks, in what order, with what
parameters) is assembled live in Phase 4–6. Nothing here is a menu of pre-built options.

---

## LCLS-I vs LCLS-II — Not Fixed by Hutch

**Do not assume generation from hutch name alone.** Several LCLS-I instruments are
mid-transition to LCLS-II DAQ on rolling schedules:

| Hutch | Status |
|---|---|
| XPP, XCS, AMO, SXR, MEC | LCLS-I (psana1), no active transition |
| MFX | Partially transitioned; some endstations run LCLS-II DAQ |
| CXI | Transitioning 2025–2027; nanofocus endstation LCLS-II first light ~June 2027 |
| TMO, RIX, TXI, UED | LCLS-II (psana2) |

**For hutches actively transitioning (MFX, CXI):** always confirm with the user:
> "Are your raw files `.xtc` (LCLS-I/psana1) or `.xtc2` (LCLS-II/psana2)?"

**For pure LCLS-II hutches (TMO, RIX, TXI, UED):** DAQ generation can be inferred
confidently from the hutch. Ask only as a formality or if the user mentions legacy data.

Consequence for LUTE:
- LCLS-I → `SmallDataProducer` (wraps `smalldata_tools` `smd_producer.py`)
- LCLS-II → `SmallDataProducer2` (psana2-based equivalent)

---

## "Smalldata" Is Overloaded

Two distinct things share the name:
1. **`smalldata_tools` `smd_producer.py`** — LCLS-I batch reduction script; this is what
   LUTE's `SmallDataProducer` wraps. Output: per-run HDF5 at
   `/sdf/data/lcls/ds/<hutch>/<exp>/hdf5/smalldata/`.
2. **psana2 `ds.smalldata()`** — built-in HDF5 output API in psana2, unrelated to
   `smalldata_tools`. Used internally by `SmallDataProducer2`.

When a user says "smalldata", clarify which they mean before assuming.

---

## Hutch Reference (LUTE-relevant instruments)

LUTE has been actively used at the five LCLS-I hard-X-ray hutches. LCLS-II instruments
use LUTE less commonly (AMI2 handles online analysis there), but deployment is growing.

| Hutch | Full name | Energy | Primary experiment types | Key detectors | LUTE usage |
|---|---|---|---|---|---|
| **XPP** | X-ray Pump-Probe | 2–12 keV | TR-SAXS/WAXS, XAS, pump-probe diffraction, XPCS (split-pulse) | Jungfrau 1M/4M, ePix10ka, Rayonix, CSPAD 140k, wave8 | Primary — SmallData + downstream analysis |
| **XCS** | X-ray Correlation Spectroscopy | Hard X-ray | XPCS, speckle dynamics, liquid SAXS, XES (vonHamos) | ePix100, ePix10ka2M, vonHamos spectrometer | Active — *closing; replaced by DXS ~2028* |
| **MFX** | Macromolecular Femtosecond Crystallography | Hard X-ray | SFX (~70%), liquid SAXS/WAXS + pump-probe (~30%), XES | Jungfrau 15M (arriving 2025), ePix10k2M, ePix100, Rayonix, wave8 | Primary — SFX chain + SmallData |
| **CXI** | Coherent X-ray Imaging | 4–12 keV | SFX (~50%), SPI, gas-phase ion imaging, CDI | CSPAD, Jungfrau 4M, ePix140k, Opal (jet imaging) | Active — SFX chain |
| **MEC** | Matter in Extreme Conditions | 4–10 keV | Shock/HED/WDM: XRD, XRTS, PCI, VISAR; single-shot or 5 Hz | ePix10k quad, ePix100, alvium cameras, PI-PIXIS CCD | Limited — **currently outputs TIFFs** (non-standard); transitioning to XTC2; LUTE applicable once XTC2 migration complete |
| **AMO** | Atomic, Molecular & Optical | Soft ~0.3–2 keV | Photoionization, ion/electron coincidence, TOF, RIXS | pnCCD, delay-line + MCP, Andor, Acqiris digitizers | Light — waveform/TOF analysis mostly custom |
| **TMO** | Time-resolved Molecular & Optical | Soft X-ray (NEH) | Ultrafast AMO, pump-probe, electron TOF, coincidence | HSD/FEX, Tixel (under consideration) | Growing — psana2; AMI2 handles online; LUTE for batch |
| **RIX** | Resonant Inelastic X-ray | ~250–1500 eV | RIXS (qRIXS + ChemRIX), time-resolved XAS, pump-probe | Andor Newton CCD, Archon CCD, ePix10k, ePixM 0.3 MP | Active — integrating detectors need special config |
| **TXI** | Time-resolved X-ray Imaging | ~1.3–7 keV | TR-SAXS/WAXS, SPI, XPP-style spectroscopy at 10 kHz | ePixHR 2M, vonHamos spectrometer, wave8 × 2 | Growing — psana2; SAXS/SPI pipeline |

---

## Per-Hutch Analysis Chains

### XPP

**Pump-probe TR-SAXS / TR-WAXS (most common):**
- Confirm: `.poni` geometry file exists? If yes → PyFAI integration path. If no → manual
  beam geometry (energy keV, center µm, sample distance mm).
- SmallData production with azimuthal integration (`getAzIntPyFAIParams` or
  `getAzIntParams`) + beam monitors (`getROIs` for wave8/FIM diode waveforms) +
  `detSumAlgos`.
- Downstream: difference scattering signal (`SmallDataXSSAnalyzer`).
- Timetool: if pump-probe delay is scanned, ask whether a timetool was running. If yes,
  `ttCalib` needed in `SubmitSMD` for jitter correction.

**XAS / pump-probe absorption:**
- SmallData with beam monitor ROIs (`getROIs`) for I₀ normalization.
- Downstream: absorption signal (`SmallDataXASAnalyzer`).

**XPCS (split-pulse):**
- SmallData with `getAutocorrParams`; speckle contrast is the key output quantity.
- No standard downstream LUTE task — user does offline correlation analysis.

**Geometry calibration run:**
- Separate AgBh (or similar powder) run before main experiment.
- `BayFAIOptimizer` (LCLS-I) — Bayesian PyFAI geometry optimization.
- Run independently from main analysis chain; requires prior SmallData run.

**Has dedicated `xpp.yaml` hutch config in LUTE.**

---

### XCS

**XPCS / speckle dynamics:**
- SmallData with `getAutocorrParams`; two-time correlation computed offline.
- `dropletFunc` / photon counting if occupancy is sparse (~10⁻³–10⁻¹ ph/px):
  `getDropletParams` or `getDroplet2Photons` depending on occupancy regime.

**XES (vonHamos spectrometer):**
- SmallData with `getROIs` (projection onto energy axis); `writeArea=True` to save
  full spectrometer image.
- Downstream: `SmallDataXESAnalyzer`.

**Note: XCS is closing; being replaced by DXS (first light June 2028).** New instruments
there will use SparkPix detectors and psana2.

**Has dedicated `xcs.yaml` hutch config in LUTE.**

---

### MFX

Three experiment types — ask which applies before proceeding:

**1. SFX (serial femtosecond crystallography) — ~70% of MFX beam time:**
- Hit finding → indexing → merging → structure factors. Does NOT require SmallData as a
  prerequisite; hit finding operates directly on XTC.
- See the SFX Analysis Chain section below.
- If running simultaneously with SFX: SmallData can be run in parallel for online
  monitoring, but is not part of the SFX pipeline itself.
- Has dedicated `mfx.yaml` hutch config in LUTE.

**2. Liquid SAXS/WAXS + pump-probe (~30%):**
- Same as XPP TR-SAXS path above. Jungfrau or ePix10k2M as area detector.
- wave8 for beam monitoring. Timetool if timing jitter matters.

**3. XES (often coupled to pump-probe or SFX):**
- Andor or ePix as spectrometer detector.
- If Andor (integrating, slow): `get_intg` in `SubmitSMD` (`intg_main` = detector name).
- If ePix (fast, sparse photon): `getDroplet2Photons` with correct `aduspphot`.
- Then `getROIs` with `writeArea=True`; downstream: `SmallDataXESAnalyzer`.

**Transitional status:** some MFX endstations already run LCLS-II DAQ. Verify `.xtc`
vs `.xtc2` before choosing the SmallData producer task.

---

### CXI

**SFX (dominant use case):**
- Same SFX analysis chain as MFX. See SFX Analysis Chain section.
- CSPAD or Jungfrau 4M as main detector; Opal camera for jet imaging (not in LUTE pipeline).
- Has dedicated `cxi.yaml` hutch config in LUTE.

**CDI / ptychography (minority):**
- Requires psana image extraction + motor positions → external tools (Ptypy,
  PtychoShelves). LUTE is not the right tool for this path; SmallData can handle
  the reduction step but the iterative phase retrieval is outside LUTE's scope.

**SPI (single-particle imaging):**
- Sparse hit triggering (1–5% hit rate); rebinning + background subtraction + radial
  integration. Partially handled by SmallData; no dedicated LUTE downstream task.

**Transitional status:** nanofocus endstation transitioning to LCLS-II ~June 2027.

---

### MEC

**Current limitation:** MEC historically outputs per-detector TIFF files, not XTC.
LUTE reads XTC/XTC2 data. Until the XTC2 migration is complete, LUTE's SmallData
producer tasks cannot process raw MEC data directly.

Once XTC2 migration is live:
- Single-shot or 5 Hz acquisition; each shot often destroys the sample.
- SmallData with `getROIs` for diode waveforms (VISAR velocity, XRD diodes).
- Area detector images (XRD, XRTS): `detSumAlgos` + possibly `getAzIntParams`.
- Deep analysis (plasma diagnostics, EOS) is offline and outside LUTE scope.

**Has dedicated `mec.yaml` hutch config in LUTE.**

---

### TMO, RIX, TXI (LCLS-II)

All three use psana2 → `SmallDataProducer2`. AMI2 handles real-time online analysis;
LUTE handles the batch/offline production run triggered by ARP.

**TMO:**
- HSD/FEX digitizers for electron/ion TOF: `getROIs` on waveform channels.
- L3T event veto may reduce effective event count — normal, not an error.
- No standard LUTE downstream analysis task; SmallData output feeds user notebooks.

**RIX:**
- Integrating detectors (Andor Newton, Archon CCD): always enable `get_intg` in
  `SubmitSMD`. `intg_main` = slowest detector name.
- Then `getROIs` with `writeArea=True` for spectrometer images.
- qRIXS: 2D energy-transfer × energy-loss maps → `SmallDataXESAnalyzer` can help.
- ePixM 0.3 MP (installed 4/2025): fast area detector, may use `getDroplet2Photons`.
- Downstream: `SmallDataXESAnalyzer` or `SmallDataXASAnalyzer` depending on mode.

**TXI:**
- ePixHR 2M at 5 kHz for TR-SAXS: `getAzIntPyFAIParams` (preferred if `.poni` file
  exists) or `getAzIntParams`.
- wave8 × 2 for I₀ normalization: `getROIs` waveform windows.
- Downstream: `SmallDataXSSAnalyzer` for difference scattering.
- SPI mode: custom rebinning + background subtraction; no standard LUTE downstream task.

---

## SFX Analysis Chain

SFX is the most complex LUTE pipeline. The full chain from XTC to structure factors:

```
XTC data
  └─► Hit finding (peak detection on each diffraction pattern)
        └─► Indexing (lattice determination per pattern)
              └─► Stream concatenation (merge per-node outputs)
                    └─► Merging (scale + merge partial reflections)
                          ├─► Merge statistics
                          ├─► HKL manipulation (format conversion / scaling)
                          └─► Phasing (molecular replacement or ab initio)
```

### Peak finding backends

**Cheetah (standard at MFX/CXI):**
- LUTE task: `RunCheetah` (ManagedTask: `CheetahRunner`)
- Reads XTC directly; Cheetah must be installed and configured separately
- Outputs `.cxi` files or stream files consumed by CrystFEL

**LUTE-native psana peakfinder8 / PyAlgos:**
- LUTE task: `FindPeaksSFX` (ManagedTask: `PeakFinderSFX`)
- No external Cheetah dependency; runs within the psana environment
- Use when Cheetah is not available or for LCLS-II native psana2 workflows

### Indexing backends

**CrystFEL (`indexamajig`):**
- LUTE task: `IndexCrystFEL` (ManagedTask: `CrystFELIndexer`)
- Algorithms: xgandalf (default), mosflm, asdf, dirax, pinkindexer
- Standard at both MFX and CXI

**CCTBX.XFEL:**
- LUTE task: `IndexCCTBXXFEL` (ManagedTask: `CCTBXIndexer`)
- Alternative when CCTBX environment is available; common at CXI

### Post-indexing chain (CrystFEL path)

| Step | LUTE task class | ManagedTask | Notes |
|---|---|---|---|
| Concatenate streams | `ConcatenateStreamFiles` | `StreamFileConcatenator` | Merges per-node `.stream` files |
| Merge | `MergePartialator` | `PartialatorMerger` | CrystFEL `partialator`; needs symmetry |
| Merge statistics | `CompareHKL` | `HKLComparer` | R-factors, CC*, completeness |
| HKL manipulation | `ManipulateHKL` | `HKLManipulator` | Scaling, format conversion |
| Molecular replacement | `DimpleSolve` | `DimpleSolver` | DIMPLE; requires reference PDB |

### Post-indexing chain (CCTBX path)

| Step | LUTE task class | ManagedTask |
|---|---|---|
| Merge | `MergeCCTBXXFEL` | `CCTBXMerger` |

### Phasing alternative

`RunSHELXC` → SHELXC/D/E pipeline (ab initio phasing when no reference structure exists).

---

## Detector Alias Verification

Detector names in `producer_parameters` (e.g., `getROIs`, `getAzIntPyFAIParams`,
`getDroplet2Photons`) must match the **psana alias** for that detector in the specific
run, not the physical detector type. The alias is set in the DAQ configuration and may
differ across experiments or even across run periods at the same hutch.

**Before filling in detector names, ask the user to confirm the alias:**

> "What is the psana detector name for your [detector]? You can check by running:
> ```python
> import psana
> ds = psana.DataSource('exp={exp}:run={run}:smd')
> det = next(ds.events())
> print([k for k in det.keys()])
> ```
> or for psana2:
> ```python
> from psana import DataSource
> ds = DataSource(exp='{exp}', run={run})
> run = next(ds.runs())
> print(run.detnames)
> ```"

Common examples (not guaranteed — always verify):
- ePix10k2M at XPP: typically `epix10k2M` or `epix10k2M_0`
- wave8 at XPP: typically `wave8` or `XPP:WAVE8:0`
- ePix100 at XCS: typically `epix100`
- Andor at MFX: typically `andor` or the alias set by the instrument scientist

If the alias is wrong, `producer_parameters` silently produces no output for that
detector — there is no error, just missing data.

---

## Standard Variables to Capture in SubmitSMD

These are present in virtually all smalldata files and should be included by default
in `producer_parameters` unless the user explicitly doesn't need them:

| Variable | Source | Why |
|---|---|---|
| `lightStatus/xray` | EVR event code | X-ray present this shot (bool) |
| `lightStatus/laser` | EVR event code | Laser present this shot (bool) |
| `ipm2/sum`, `ipm3/sum` | IPM (intensity monitor) | Relative I₀ for normalization |
| `tt/ttCorr` | Timetool | Laser–X-ray timing jitter correction (ps); NaN if not running |
| `tt/AMPL` | Timetool | Signal amplitude; shots with AMPL < 0.02 should be cut |
| `ebeam/ebeamL3Energy` | Beam diagnostics | Electron beam energy (eV) |
| `evr/code_<N>` | EVR | Event code flags (laser on, special modes) |

Enable via `epicsPV` or `epicsOncePV` lists in `producer_parameters`, or they are
auto-populated by the per-hutch `smd_producer` config if using the hutch's standard
config file.

---

## LUTE Hutch Config Files

LUTE ships pre-populated YAML configs for the five LCLS-I hard-X-ray hutches:

| File | Hutch | Pre-populated blocks |
|---|---|---|
| `config/xpp.yaml` | xpp | SubmitSMD + AzInt defaults |
| `config/xcs.yaml` | xcs | SubmitSMD defaults |
| `config/mfx.yaml` | mfx | SubmitSMD + SFX task blocks |
| `config/cxi.yaml` | cxi | SubmitSMD + SFX task blocks |
| `config/mec.yaml` | mec | SubmitSMD + diode ROI blocks |
| `config/test.yaml` | fallback | Used when no hutch-specific file exists |

LCLS-II hutches (`tmo`, `txi`, `rix`) have no dedicated hutch config — `test.yaml` is
the intended starting point. The skill must write the full assembled YAML directly (Phase
4/5.4); `install_lute.py` does not copy any template file.

---

## Glossary

For full definitions see `lcls_experiments.md` (the source document for this reference).
Key terms relevant to LUTE setup:

| Term | Notes |
|---|---|
| ARP | Automatic Run Processor — Slurm job auto-submitted at run end; this is what triggers LUTE workflows |
| FFB | Fast Feedback Buffer — live XTC2 at `/sdf/data/lcls/drpsrcf/ffb/`; last ~1–2 hrs |
| HSD/FEX | High Speed Digitizer with onboard FPGA peak-finding; used at TMO/RIX |
| IPM | Intensity Position Monitor; `ipm2/sum` is standard I₀ proxy |
| L3T | Level-3 Trigger — event veto decision made in DRP; reduces event count seen by LUTE |
| vonHamos | Bent-crystal X-ray emission spectrometer at XCS and TXI |
| AMI2 | LCLS-II online analysis tool (not LUTE); runs from shared memory / FFB |
