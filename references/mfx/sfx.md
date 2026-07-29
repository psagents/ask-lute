# MFX SFX — Serial Femtosecond Crystallography

> **Starting point:** `templates/mfx/sfx.yaml`
> This template is a reasonable default for MFX SFX with the CrystFEL pipeline.
> It is **not** ground truth — verify every field with the user before writing anything.
> Alternatives and edge cases are documented below.

---

## Geometry Calibration Prerequisite

BayFAI must be run on a calibrant run **before** SFX indexing. What happens after
depends on whether the user is using CrystFEL or CCTBX.XFEL.

Ask first: "Are you using CrystFEL or CCTBX.XFEL for indexing?"

**Template:** `templates/mfx/bayfai.yaml`

**DAG** (separate workflow, `MANUAL` trigger):
```yaml
!LUTE_DAG
task_name: "SmallDataProducer2"
slurm_params: "--nodes=4 --ntasks-per-node=50 --exclusive"
next:
- task_name: "BayFAIOptimizer2"
  slurm_params: "--nodes=1 --ntasks-per-node=120"
  next: []
```

### After BayFAI — CrystFEL path

BayFAI produces a `.geom` file directly — no conversion needed.

1. Run BayFAI on the calibrant run
2. Find the `.geom` output at `{lute_output_dir}/bayFAI_output/{detector_alias}.geom`
3. Provide that path explicitly as `geometry` in `RunCheetah` and `IndexCrystFEL`

### After BayFAI — CCTBX.XFEL path

BayFAI produces calibrated geometry `.data` files (psana calibration format).
CCTBX.XFEL picks these up **automatically** — no explicit geometry field is needed in the YAML.

1. Run BayFAI on the calibrant run
2. **Deploy the `.data` output to the psana calibration database**
   (ask the instrument scientist for the deploy command — this is a psana calib management step;
   verify which command is used at MFX: likely `calibcopy`, `calibman`, or a beamline script)
3. CCTBX initializes its DataSource and loads calibration constants from the database automatically
4. No `geometry` field is needed in `IndexCCTBXXFEL`

> If a calibrated geometry from a prior experiment at the same detector position is already
> in the database, the deploy step can be skipped — ask the instrument scientist.

---

## Task Chain

```
Calibrant run first (MANUAL):
  SubmitSMD (detSumAlgos: calib_max)  →  BayFAIOptimizer2
  Outputs (all three from the same run):
    .poni → SAXS azimuthal integration
    .geom → CrystFEL path: use directly in IndexCrystFEL + RunCheetah (no conversion)
    .data → CCTBX path: deploy to psana calib database (instrument scientist command)

Main SFX run (END_OF_RUN):
  └─► Hit finding   RunCheetah (CheetahRunner)            ← default at MFX
                    FindPeaksSFX (PeakFinderSFX)          ← fallback if no Cheetah
  └─► Indexing      IndexCrystFEL (CrystFELIndexer)       ← requires .geom; explicit path in YAML
                    IndexCCTBXXFEL (CCTBXIndexer)         ← reads calibration from psana DB automatically
  └─► Concatenate   ConcatenateStreamFiles (StreamFileConcatenator)
  └─► Merge         MergePartialator (PartialatorMerger)
  └─► Statistics    CompareHKL (HKLComparer)
  └─► [optional]    ManipulateHKL (HKLManipulator)  →  DimpleSolve / RunSHELXC
```

If the user chooses CCTBX.XFEL instead of CrystFEL, delegate to `@ask-cctbx-xfel`
for the indexing and merging parameters before filling those blocks.

---

## Fields to Verify with the User

### Header
- `experiment` — e.g. `mfxl1013621`
- `work_dir` — typically `{results_dir}/lute_output`
- `date` — today's date

### RunCheetah
- `source` — psana data source string, e.g. `"exp=mfxl1013621:run=27"`
- `cheetah_subconfig.data_sources.detector_data.psana_name` — confirm alias with `run.detnames`; typically `"jungfrau"` (Jungfrau 16M) since Jul 2025; pre-Jul may be `"epix10k2M"`
- `cheetah_subconfig.data_sources.detector_distance.psana_name` — use `"MFX:ROB:CONT:POS:Z"` for Jungfrau/ePix10k2M; `"MFX:DET:MMS:04.RBV"` for Rayonix
- `cheetah_subconfig.crystallography.geometry_file` — path to `.geom` file; produced by BayFAI/GeometryOptimizer calibration run; ask if available
- `cheetah_subconfig.peakfinder8_peak_detection.adc_threshold` — start at 300 ADU for Jungfrau; adjust based on hit rate
- `cheetah_subconfig.peakfinder8_peak_detection.minimum_snr` — start at 7.0; adjust based on hit rate
- `cheetah_subconfig.cheetah.processed_directory` — where CXI output files land
- `cheetah_subconfig.cheetah.processed_filename_prefix` — typically `"{exp}-{run}"`

### IndexCrystFEL
- `geometry` — same `.geom` file as Cheetah; ask if it's the same run or a different geometry
- `indexing` — start with `"xgandalf"`; alternatives: `"mosflm"`, `"pinkindexer"` (large unit cells), `"asdf"`
- `cell_file` — path to `.cell` or `.pdb` file; ask if unit cell is known
- `multi` — ask: "Do you expect multiple lattices per frame?" Default no

### MergePartialator
- `symmetry` — **required**; point group for merging (e.g. `"mmm"`, `"4/m"`, `"m-3m"`); ask the user

---

## Typical Defaults (MFX SFX — for sanity checks only)

| Parameter | Typical value | Notes |
|---|---|---|
| Detector | `jungfrau` | Jungfrau 16M since Jul 2025; check `run.detnames` |
| `adc_threshold` | 300 ADU | Adjust if hit rate too low/high |
| `minimum_snr` | 7.0 | |
| `min_num_peaks_for_hit` | 15–25 | |
| `indexing` | `xgandalf` | Robust default for proteins |
| `symmetry` | protein-specific | e.g. `mmm` for orthorhombic |
| Expected hit rate | 5–30% | Depends on sample and jet |
| Expected indexing rate | 20–60% of hits | Depends on geometry accuracy |

---

## Common Failure Modes

| Symptom | Most likely cause | Fix |
|---|---|---|
| Indexing rate < 5% | Geometry wrong (beam center or distance off) | Re-run BayFAI; check `.geom` |
| Indexing rate 5–15% | `min_peaks` too high or unit cell not in xgandalf | Lower `min_peaks`; try `mosflm` |
| High R-split (> 30%) | Wrong symmetry or too few patterns | Confirm space group with user |
| Empty stream file | Cheetah not finding hits | Lower `adc_threshold` and `minimum_snr` |
| Missing detector in output | Alias mismatch | Re-run `run.detnames` on a fresh run |

---

## DAQ Generation Note

MFX moved to LCLS-II DAQ in July 2025. **Always confirm with the user:**
- `.xtc` (LCLS-I/psana1) → use `SmallDataProducer` (DAG)
- `.xtc2` (LCLS-II/psana2) → use `SmallDataProducer2` (DAG)

SFX runs directly on XTC/XTC2 — SmallData is not part of the SFX pipeline unless
the user also wants per-shot monitoring (a separate workflow).
