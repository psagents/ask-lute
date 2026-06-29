# LUTE Refine

This command drives the **inspect → adjust → re-run** loop after an initial LUTE
workflow has produced its first output. It assumes setup (lute-setup.md) is complete
and at least one SmallData HDF5 file exists.

The loop is:
1. Locate and inspect the first output file
2. Identify what needs adjustment (ROI, thresholds, field names)
3. Edit `mfx_lute.yaml` (or the relevant hutch YAML) in place
4. Re-trigger the workflow for a representative run

---

## Step R.1 — Locate the first output

Find the most recent SmallData HDF5 file:

```bash
ls -lt /sdf/data/lcls/ds/{hutch}/{experiment}/hdf5/smalldata/*.h5 | head -5
```

If no files exist yet, the workflow has not run or failed. Check the eLog run table for
the workflow status before continuing.

---

## Step R.2 — Inspect field names and verify assumptions

Open-ended inspection — the user should run this and paste the output:

```python
import h5py, numpy as np

f = h5py.File('<smd_path>', 'r')

def print_tree(name, obj):
    if isinstance(obj, h5py.Dataset):
        print(f'{name:60s} {obj.shape}  {obj.dtype}')
h5py.File.visititems(f, print_tree)
```

Or for targeted checks (use when specific fields are in doubt):

```python
# Check beam monitor field path
print(f['<alias>/totalIntensityJoules'][:10])

# Check scan variable field
print(f['<scan_var>'][:10])   # e.g. f['ccm_E'][:10]

# Check detector ROI shape
print(f['<det_alias>/ROI_0_area'][:3].shape)
```

Ask the user to confirm:
1. **`ipm_var` path** — does the field exist and contain non-trivial values?
2. **`scan_var` path** — does the field exist and step as expected?
3. **ROI coverage** — does the saved area capture the spectral signal?

If a field is missing or mis-named, identify the correct name from the HDF5 tree and
update `mfx_lute.yaml` accordingly (Step R.3).

---

## Step R.3 — Edit the YAML

The config file is at:
```
{lute_output_dir}/{hutch}_lute.yaml
```

Common adjustments after first inspection:

| What's wrong | Field to change | Location in YAML |
|---|---|---|
| `scan_var` field not found in HDF5 | `scan_var` | `AnalyzeSmallDataXES` / `XSS` / `XAS` block |
| `ipm_var` values all near zero or negative | `ipm_var`, `min_ipm` | downstream task block |
| ROI misses the signal stripe | `ROI` under `getROIs` | `SubmitSMD.producer_parameters` |
| Spectrum projected along wrong axis | `invert_xes_axes` | `AnalyzeSmallDataXES` block |
| Too many shots rejected | `min_ipm`, `min_Iscat` | `intensity_thresholds` block |

Make the edit directly in the YAML, then set permissions:
```bash
chmod 666 {lute_output_dir}/{hutch}_lute.yaml
```

**No need to re-run `install_lute.py`** for YAML-only changes — the DAG and eLog
registration are unchanged. The next workflow trigger will pick up the new config
automatically.

---

## Step R.4 — Re-trigger for a representative run

Re-run `SubmitSMD` (and the downstream chain) for a single run to validate the changes
before the next beamtime. Two options:

**Option A — Manual trigger via eLog UI**
```
https://pswww.slac.stanford.edu/lgbk/lgbk/{experiment}/
→ Run table → select run → trigger lute_{wf_name}
```

**Option B — Submit directly via SLURM**
```bash
{lute_path}/install/bin/submit_launch_slurm.sh \
  -c {config_path} \
  -t SmallDataProducer2 \
  --run {run_number} \
  --experiment {experiment}
```

---

## Step R.5 — Iterate

Repeat R.2 → R.3 → R.4 until:
- `scan_var` bins the signal correctly across the expected range
- `ipm_var` filters bad shots without over-rejecting
- ROI contains the full spectral stripe with no clipping
- Downstream analysis plots (XES spectra, difference maps) look physically reasonable

Once satisfied, the config is production-ready. No further action needed — the eLog
workflow trigger will apply it to all subsequent runs automatically.

---

## Quick Reference — Field name patterns in SmallData HDF5

| Source | Typical HDF5 path | Notes |
|---|---|---|
| Area detector ROI sum | `{det_alias}/ROI_0_sum` | Sum of ROI pixels per shot |
| Area detector ROI image | `{det_alias}/ROI_0_area` | Full 2D ROI frame (if `writeArea: true`) |
| bmmon intensity | `{det_alias}/totalIntensityJoules` | Pre-computed by firmware |
| EPICS PV (per-shot) | `epics/{pv_alias}` | Saved via `epicsPV` in producer_parameters |
| Scan motor | `{motor_alias}` or `epicsUser/{alias}` | Depends on how PV was registered |
| Timing tool | `tt/ttCorr`, `tt/AMPL` | Only if `ttCalib` block present |
| Shot flags | `lightStatus/xray`, `lightStatus/laser` | Always present |
