# MFX TR-SAXS/WAXS — Time-Resolved Solution Scattering

> **Starting point:** `templates/mfx/saxs.yaml`
> This template is a reasonable default for MFX TR-SAXS/WAXS with PyFAI integration.
> It is **not** ground truth — verify every field with the user before writing anything.
> Alternatives and edge cases are documented below.

---

## BayFAI Calibration Prerequisite

**Run this first, on a calibrant run, before setting up the main SAXS workflow.**

`getAzIntPyFAIParams` requires a `.poni` file. Without it, azimuthal integration
cannot run. Ask the user: "Has BayFAI been run on a calibrant run for this experiment?"

If yes → ask for the `.poni` path and proceed to the main workflow.
If no → set up the BayFAI calibration workflow first:

**Template:** `templates/mfx/bayfai.yaml`

**DAG** (separate from the main SAXS workflow, `MANUAL` trigger):
```yaml
!LUTE_DAG
task_name: "SmallDataProducer2"
slurm_params: "--nodes=4 --ntasks-per-node=50 --exclusive"
next:
- task_name: "BayFAIOptimizer2"
  slurm_params: "--nodes=1 --ntasks-per-node=120"
  next: []
```

**What to tell the user:**
1. Take a calibrant run (AgBh or LaB₆ powder scatter, same detector position as experiment)
2. Register and run the BayFAI workflow on that calibrant run number
3. Find the output `.poni` at: `{lute_output_dir}/bayFAI_output/{detector_alias}.poni`
4. Use that path as `getAzIntPyFAIParams.<det_alias>.poni_file` in the main SAXS YAML

Key parameters to verify with the user (see `templates/mfx/bayfai.yaml`):
- `center.dist` — approximate detector distance in meters (MFX: 0.08–0.20 m typical)
- `detname` / detector alias — confirm via `run.detnames` on the calibrant run
- `calibrant` — `"AgBh"` (standard) or `"LaB6"`
- `bounds.dist` — widen to `[-0.1, 0.1]` if distance is very uncertain

---

## Task Chain

```
Calibrant run first (MANUAL):
  SubmitSMD (detSumAlgos: calib_max)  →  BayFAIOptimizer2
  Output: {lute_output_dir}/bayFAI_output/{detector_alias}.poni

Main experiment run (END_OF_RUN or START_OF_RUN):
  └─► SmallData     SubmitSMD (SmallDataProducer2)
        getAzIntPyFAIParams — azimuthal integration via PyFAI    ← default (requires .poni)
        getAzIntParams      — manual azimuthal integration        ← fallback (no poni file)
        ttCalib             — timetool jitter correction          ← if pump-probe
  └─► Analysis      AnalyzeSmallDataXSS (SmallDataXSSAnalyzer)
```

---

## Fields to Verify with the User

### Header
- `experiment` — e.g. `mfxl1013621`
- `work_dir` — typically `{results_dir}/lute_output`

### SubmitSMD
- `producer` — path to `smd_producer.py`; typical: `{{ work_dir }}/smalldata_tools/lcls2_producers/smd_producer.py`
- `lute_template_cfg.template_name` — `"smd2_prod_config_template.py"` (LCLS-II)
- `lute_template_cfg.output_path` — `{{ work_dir }}/smalldata_tools/lcls2_producers/prod_config_mfx.py`
- `directory` — SmallData HDF5 output; default `/sdf/data/lcls/ds/mfx/{exp}/hdf5/smalldata`

### producer_parameters
- `getAzIntPyFAIParams.<det_alias>.poni_file` — path to `.poni` file from BayFAI run; **required**; ask if available
- `<det_alias>` — confirm detector alias via `run.detnames`; typically `"jungfrau"` (Jungfrau 16M since Jul 2025)
- `getAzIntPyFAIParams.<det_alias>.npts` — number of Q bins; start at 512
- `getAzIntPyFAIParams.<det_alias>.int_units` — must be `"q_A^-1"` for SmallDataXSSAnalyzer
- `getAzIntPyFAIParams.<det_alias>.npts_az` — `1` for isotropic SAXS; `>1` for anisotropic/sector analysis
- `ipm_dg2` IPM — confirm alias via `run.detnames`; `ipm_dg2/sum` is the primary I₀ at MFX
- `ttCalib` — ask: "Is there a pump laser?" If yes, include timetool block: `tt/ttCorr`, `tt/AMPL`
- `epicsArchFilePV` — ask: "Any motor positions to save per shot?" (scan motor, lens position)

### AnalyzeSmallDataXSS
- `ipm_var` — `"ipm_dg2/sum"` (primary at MFX); verify with user
- `scan_var` — ask: "What is the pump-probe delay stage?" Typically `"lxt"` or `"lxt_fast"`
- `intensity_thresholds.min_ipm` — adjust to match typical IPM signal level; ask user

---

## Typical Defaults (MFX TR-SAXS)

| Parameter | Typical value | Notes |
|---|---|---|
| Detector | `jungfrau` | Jungfrau 16M since Jul 2025 |
| Integration units | `q_A^-1` | Required for XSSAnalyzer |
| `npts` | 512 | Q bins |
| `npts_az` | 1 | Isotropic; use 36 for anisotropic |
| `ipm_var` | `ipm_dg2/sum` | Primary I₀ at MFX |
| `scan_var` | `lxt` | Pump-probe delay |
| Calibrant | AgBh or LaB₆ | For BayFAI run |

---

## Alternatives

### Manual azimuthal integration (no .poni file)
Use `getAzIntParams` instead of `getAzIntPyFAIParams`:
```yaml
getAzIntParams:
  jungfrau:  # VERIFY ALIAS
    eBeam: ""          # beam energy in keV — VERIFY WITH USER
    center: []         # beam center in micrometers [x, y] — VERIFY WITH USER
    dis_to_sam: ""     # detector distance in mm — VERIFY WITH USER
    int_units: "q_A^-1"
    npts_az: 1
```

### Rayonix (if installed instead of Jungfrau)
Replace `jungfrau` with `Rayonix`. Camera length PV: `"MFX:DET:MMS:04.RBV"`.

---

## Common Failure Modes

| Symptom | Most likely cause | Fix |
|---|---|---|
| Empty or flat scattering profile | Wrong `.poni` file or wrong alias | Re-run BayFAI; check alias |
| No difference signal despite pump | `scan_var` wrong or timetool not applied | Check `lxt` alias; add `ttCalib` |
| Huge `min_ipm` rejection | IPM alias wrong or signal too low | Check `ipm_dg2/sum` field exists in HDF5 |
| Q-axis in wrong units | `int_units` not `q_A^-1` | Change `getAzIntPyFAIParams` units |
