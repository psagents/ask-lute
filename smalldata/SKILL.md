# smalldata — SmallData production and the XSS / XAS / XES analyzers

`SubmitSMD` reduces a run to an HDF5 file; an analyzer then reads named datasets
out of it. **The producer config is the setup**: an analyzer can only use what the
producer was told to write, and a missing dataset is discovered only after the run.

Producer-config details beyond what is below (ROI choice, azav binning, droplets,
photon counting, which PVs exist): **`@ask-smalldata`**, required.

## Contract

| Field | Value |
|---|---|
| `template` | `smalldata/smd.yaml.j2`, with `analyses` = any of `xss`, `xas`, `xes` |
| `dags` | `smd_xss.dag`, `smd_xas.dag`, `smd_xes.dag`, or `smd_xss_xes.dag` for XSS+XES — workflow named after the file, trigger `END_OF_RUN` |
| `lute` | `release: <current lute-lcls>` |
| `validate` | — |
| `parse` | `python3 smalldata/parse_smd_output.py --log <.out> --h5 <run.h5> --analysis <xss\|xas\|xes> --det <alias> [--ipm-var V] [--scan-var V]` |

Every DAG runs the producer on every run and the analyzer only when the eLog
`run_type` is `DATA` (`!run_type`), so DARK and calibrant runs are reduced but not
analyzed. One workflow per experiment: two would produce the same HDF5 twice.

## What each analyzer needs from the producer

Read off `lute/tasks/_smalldata.py`, not inferred:

| Analyzer | Producer must write | Analyzer parameters |
|---|---|---|
| XSS | `<det>/pyfai_azav` (`getAzIntPyFAIParams`) **or** `<det>/azav_azav` (`getAzIntParams`) | `xss_detname`, `ipm_var` |
| XAS | `<det>/ROI_0_sum` (`getROIs`, first ROI) | `xas_detname`, `ipm_var`, `ccm` (readback PV, saved by the producer) |
| XES | `<det>/ROI_0_area` (`getROIs` with `writeArea: true`) | `xes_detname`, `ipm_var` |
| all | `lightStatus/xray`, `lightStatus/laser` (written by default) and the `ipm_var` dataset | `scan_var` optional |

- **XSS `int_units` must be `q_A^-1`.** The producer default is `2th_deg`; the
  analyzer never checks units and reads `pyfai_q` as q regardless.
- **XSS needs a geometry.** `getAzIntPyFAIParams` needs `poni_file` from a
  [`bayfai`](../bayfai/SKILL.md) run; without one, use `getAzIntParams`
  (`eBeam`, `center`, `dis_to_sam` given by hand).
- **XES** projects the ROI along axis 1; `invert_xes_axes: true` if the dispersive
  axis is the other one.
- **`scan_var`** is looked up as `scan/<name>`. If it is absent the analyzer falls
  back to `enc/lasDelay`, then to no binning — it does not fail.
- **Laser on/off** comes from `lightStatus/laser`. A run with no laser-off shots
  has no difference signal, whatever the config.
- **PVs** (`epicsArchFilePV`, e.g. spectrometer crystal positions, a CCM readback)
  must be saved by this run's producer. They cannot be added after the run.

## Context

| Variable | Source | If unknown |
|---|---|---|
| `experiment`, `work_dir`, `date`, `lute_version` | caller | — |
| `smalldata_tools` | the experiment's `smalldata_tools` checkout | ask |
| `smd_dir` | SmallData HDF5 output directory | `/sdf/data/lcls/ds/<hutch>/<exp>/hdf5/smalldata` |
| `xss_det` / `xas_det` / `xes_det` | `run.detnames` — never a colloquial name | blocker: ask |
| `poni_file` | `bayfai` output | ask; else switch to `getAzIntParams` |
| `xas_roi`, `xes_roi` | `[[row0, row1], [col0, col1]]` from a test image | blocker: ask |
| `ipm_var` | an HDF5 dataset path, e.g. `ipm_dg2/sum` | ask; check it with `parse_smd_output.py` on a test run |
| `ccm` (XAS) | the CCM readback PV, also listed in `epics_pvs` | blocker: ask |
| `scan_var` | the scanned motor, e.g. `lxt` | omit — no binning |
| `epics_pvs` | `@ask-smalldata` / instrument scientist | omit |

`producer` and `lute_template_cfg` are set explicitly in the template because a pip
venv (`lute: release`) has no psana to auto-detect them.

## Reading the result

`parse_smd_output.py` reports, from the log, `task_completed`/`task_failed`, the
HDF5 written and distinct error lines; from the HDF5, `n_events`, `laser_on` /
`laser_off` and every analyzer input that is **missing**.

Acceptance (simple, so it lives here):

- `task_completed` true for both producer and analyzer.
- `missing` is empty. Anything listed there is a producer-config fix, and needs a
  re-run of SmallData, not of the analyzer.
- `laser_off > 0` before reading a difference signal.
- `scan_var_present` true if a scan was intended.
