# MFX XES — X-ray Emission Spectroscopy

> **Starting point:** `templates/mfx/xes.yaml`
> This template is a reasonable default for MFX XES with the Von Hamos ePix100 spectrometer.
> It is **not** ground truth — verify every field with the user before writing anything.
> Alternatives (Andor integrating spectrometer) are documented below.

---

## Task Chain

```
Raw XTC2
  └─► SmallData     SubmitSMD (SmallDataProducer2)
        getROIs           — ROI extraction from XES detector
        writeArea: true   — save 2D ROI frames for spectral projection
        epicsArchFilePV   — Von Hamos spectrometer motor positions (MANDATORY)
        ttCalib           — timetool jitter correction (if pump-probe)
  └─► Analysis      AnalyzeSmallDataXES (SmallDataXESAnalyzer)
```

---

## Fields to Verify with the User

### Header
- `experiment` — e.g. `mfxl1013621`
- `work_dir` — typically `{results_dir}/lute_output`

### SubmitSMD
- `producer` — `{{ work_dir }}/smalldata_tools/lcls2_producers/smd_producer.py`
- `lute_template_cfg.template_name` — `"smd2_prod_config_template.py"` (LCLS-II)
- `lute_template_cfg.output_path` — `{{ work_dir }}/smalldata_tools/lcls2_producers/prod_config_mfx.py`
- `directory` — SmallData HDF5 output; default `/sdf/data/lcls/ds/mfx/{exp}/hdf5/smalldata`

### producer_parameters
- `getROIs.<det_alias>` — confirm spectrometer alias via `run.detnames`; typically `"epix100_0"` (ePix100a)
- `getROIs.<det_alias>[0].ROI` — spectral stripe ROI; **ask the user** for row/column bounds from a test shot; format: `[[row_start, row_end], [col_start, col_end]]`
- `getROIs.<det_alias>[0].writeArea` — must be `true` for XES (saves 2D frame for projection)
- `epicsArchFilePV` — **all Von Hamos spectrometer PVs are mandatory** — do not skip:
  ```
  MFX:SPEC:C1:TILT.RBV  MFX:SPEC:C1:X.RBV  MFX:SPEC:C1:ROT.RBV
  MFX:SPEC:C2:TILT.RBV  MFX:SPEC:C2:X.RBV  MFX:SPEC:C2:ROT.RBV
  MFX:SPEC:C3:TILT.RBV  MFX:SPEC:C3:X.RBV  MFX:SPEC:C3:ROT.RBV
  MFX:SPEC:C4:TILT.RBV  MFX:SPEC:C4:X.RBV  MFX:SPEC:C4:ROT.RBV
  MFX:SPEC:C5:TILT.RBV  MFX:SPEC:C5:X.RBV  MFX:SPEC:C5:ROT.RBV
  MFX:SPEC:C6:TILT.RBV  MFX:SPEC:C6:X.RBV  MFX:SPEC:C6:ROT.RBV
  MFX:SPEC:ROT.RBV  MFX:SPEC:T1.RBV  MFX:SPEC:T2.RBV  MFX:SPEC:T3.RBV
  ```
  These cannot be recovered after the run — include all of them.
- `ttCalib` — ask: "Is there a pump laser?" If yes, add: `tt/ttCorr`, `tt/AMPL`, `lxtDelay`
- CCM PVs (if XES is scanning photon energy):
  - `epicsPV`: `[["SP1L0:DCCM:*", "ccm_*"]]` (DCCM monochromator; ask if in use)

### AnalyzeSmallDataXES
- `xes_detname` — same alias as in `getROIs`; typically `"epix100_0"`
- `ipm_var` — `"ipm_dg2/sum"` (primary at MFX); verify with user
- `scan_var` — ask: "What is the scan variable?" Typically `"lxt"` (pump-probe delay) or `"ccm_E"` (energy scan)
- `invert_xes_axes` — ask: "Is the dispersive axis along row or column direction?" Default `false` (axis 1 = columns)

---

## Typical Defaults (MFX XES)

| Parameter | Typical value | Notes |
|---|---|---|
| XES detector | `epix100_0` | ePix100a; confirm via `run.detnames` |
| ROI | user-defined | Ask for spectral stripe bounds |
| `ipm_var` | `ipm_dg2/sum` | Primary I₀ at MFX |
| `scan_var` | `lxt` | Pump-probe delay |
| Von Hamos PVs | all 22 PVs | Always include — cannot recover post-run |

---

## Alternative: Andor Integrating Spectrometer

If the user says the XES spectrometer is an **Andor camera** (not ePix100):
- Add `integrating_detectors: ["<andor_alias>"]` to `SubmitSMD`
- Add `get_intg` block with `intg_main: "<andor_alias>"`
- Use `getROIs` on the Andor alias as the `xes_detname`

```yaml
integrating_detectors:
  - andor   # VERIFY ALIAS
get_intg:
  intg_main: "andor"
```

---

## Common Failure Modes

| Symptom | Most likely cause | Fix |
|---|---|---|
| Flat spectrum (no emission line) | ROI misses spectral stripe | Ask user to re-draw ROI from AMI image |
| Spectrum projected along wrong axis | `invert_xes_axes` set incorrectly | Toggle and rerun |
| Missing Von Hamos PVs in HDF5 | `epicsArchFilePV` not set | Edit YAML; re-run SmallData |
| `ipm_var` all zeros | Alias wrong or IPM offline | Check `ipm_dg2/sum` in HDF5 |
| No difference signal | `scan_var` wrong or no laser shots | Check `lightStatus/laser` shot flags |
