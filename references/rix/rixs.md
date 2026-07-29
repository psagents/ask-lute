# RIX RIXS — Resonant Inelastic X-ray Scattering

> **Starting point:** `templates/rix/rixs.yaml`
> This template covers both ChemRIXS (Andor VLS) and qRIXS (Archon CCD) configurations.
> It is **not** ground truth — verify every field with the user before writing anything.
> Always distinguish ChemRIXS from qRIXS before filling parameters.

---

## Task Chain

```
Raw XTC2
  └─► SmallData     SubmitSMD (SmallDataProducer2)
        integrating_detectors — MANDATORY for Andor/Archon
        get_intg              — integrating detector configuration
        getROIs               — spectral ROI extraction
        writeArea: true       — save 2D frames for spectral projection
        getPressioCompression — qRIXS only; must come BEFORE getROIs
        ttCalib               — if pump-probe / time-resolved
  └─► Analysis      AnalyzeSmallDataXES (SmallDataXESAnalyzer)
```

**CRITICAL:** `integrating_detectors` must be set for Andor or Archon. Without it,
psana2 event alignment fails and detector data is corrupt. Never skip this.

---

## ChemRIXS vs qRIXS — Ask First

Ask: "Are you using ChemRIXS (Andor VLS grating spectrometer) or qRIXS (Archon CCD on Rowland circle)?"

| | ChemRIXS | qRIXS |
|---|---|---|
| Spectrometer alias | `andor_vls` (verify) | `archon` (verify) |
| Additional integrating | `andor_norm`, `andor_dir` | none |
| Pressio compression | no | yes — required; before getROIs |
| Typical ROI shape | 1D spectrum (FVB) | 2D energy-transfer map |

---

## Fields to Verify with the User

### Header
- `experiment` — e.g. `rixlr1004924`
- `work_dir` — typically `{results_dir}/lute_output`

### SubmitSMD
- `producer` — `{{ work_dir }}/smalldata_tools/lcls2_producers/smd_producer.py`
- `lute_template_cfg.template_name` — `"smd2_prod_config_template.py"` (always LCLS-II at RIX)
- `lute_template_cfg.output_path` — `{{ work_dir }}/smalldata_tools/lcls2_producers/prod_config_rix.py`
- `directory` — `/sdf/data/lcls/ds/rix/{exp}/hdf5/smalldata`

### producer_parameters
- `integrating_detectors` — **MANDATORY**:
  - ChemRIXS: `["andor_vls", "andor_norm"]` (verify which Andors are active)
  - qRIXS: `["archon"]`
  - Confirm aliases via `run.detnames`
- `get_intg.intg_main` — slowest integrating detector passed to psana:
  - ChemRIXS: `"andor_vls"` (or whichever is the primary spectrometer)
  - qRIXS: `"archon"`
- `get_intg.intg_addl` — additional integrating detectors with commensurate readout (e.g. `["andor_norm"]`)
- `getPressioCompression` (qRIXS only — **must appear before getROIs in YAML**):
  ```yaml
  getPressioCompression:
    archon:
      compressor_id: "sz3"
      compressor_args:
        abs_error_bound: 10
  ```
- `getROIs.<det_alias>` — ask user for spectral ROI bounds; `writeArea: true` always for RIXS
- `ipm_var` — Wave8/FIM alias; run `detnames -e exp=<exp>,run=<N>` to get exact alias; typically one of `mr3k2`, `mr4k2`, or `crix` Wave8 units
- `ttCalib` — ask: "Is this pump-probe?" If yes, include timetool: `RIX:QRIX:ALV:01:TT:TTALL`
- `scan_var` — `"lxt_ttc"` (ATM timing delay) for pump-probe; monochromator energy alias for XAS-mode scans

### AnalyzeSmallDataXES
- `xes_detname` — same alias as spectrometer in `getROIs` (`andor_vls` or `archon`)
- `ipm_var` — Wave8 alias confirmed above; e.g. `"mr4k2/sum"` (format may vary — verify in HDF5)
- `scan_var` — pump-probe delay or mono energy
- `invert_xes_axes` — ask: "Is the dispersive axis along rows or columns?" For Archon in FVB mode, typically `false`

---

## Typical Defaults (RIX RIXS)

| Parameter | Typical value | Notes |
|---|---|---|
| Primary spectrometer (ChemRIXS) | `andor_vls` | Andor Newton FVB |
| Primary spectrometer (qRIXS) | `archon` | Archon CCD; FVB: 4224 active pixels |
| `integrating_detectors` | required | Always set; see above |
| `scan_var` | `lxt_ttc` | ATM delay stage |
| `step_value` | Bluesky scan counter | Auto-generated; use for energy scans |

---

## Common Failure Modes

| Symptom | Most likely cause | Fix |
|---|---|---|
| Corrupted detector data | `integrating_detectors` not set | Add it and rerun SmallData |
| Archon data garbled | `getPressioCompression` after `getROIs` | Reorder blocks in YAML |
| Wave8 alias not found in HDF5 | Alias format varies by run | Run `detnames -e` to get exact string |
| Empty spectrum | ROI misses active pixels | Check Archon FVB active range (4224 px) |
| No difference signal | `scan_var` wrong or laser off | Check `step_value` / `step_docstring` |
