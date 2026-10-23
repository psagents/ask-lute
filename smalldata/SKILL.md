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
| `dags` | `smalldata/smd.dag.j2`, same context — workflow `smd_<analyses joined by _>` (e.g. `smd_xss_xes`), trigger `END_OF_RUN` |
| `defaults` | `smalldata/defaults/<hutch>.yaml`, else `default.yaml` |
| `lute` | `release: <current lute-lcls>` |
| `validate` | — |
| `parse` | `python3 smalldata/parse_smd_output.py --log <.out> --h5 <run.h5> --analysis <xss\|xas\|xes> --det <alias> [--ipm-var V] [--scan-var V]` |

The DAG runs the producer on every run and the analyzer only when the eLog
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

## Walk the operator through

**Required — ask all in one message, render nothing without them:**

| Variable | Ask as | Check |
|---|---|---|
| `analyses` | "Which analyses: XSS, XAS, XES?" | — |
| `xss_det` / `xas_det` / `xes_det` | "Which detector records the scattering / XAS / XES signal?" | in `hutch-data detectors` for a recent run — never a colloquial name (`epix_0_0` was `epix100_0`) |
| `xas_roi`, `xes_roi` | "ROI as `[[row0, row1], [col0, col1]]`?" | inside the detector shape; a full-detector XES ROI is large (704×768 float64 per event) |
| `ipm_var` | "Which beam-intensity monitor?" | an HDF5 **field** (`MfxDg1BmMon/totalIntensityJoules`), not a happi prefix (`MFX:DG1:IPM`); read its range on a test run before picking a cut |
| `ccm` (XAS) | "CCM readback PV?" | also listed in `epics_pvs` |
| `poni_file` (XSS) | "Geometry from a BayFAI run?" | exists; else `getAzIntParams` with `eBeam`, `center`, `dis_to_sam` by hand |
| T-jump delays (XSS) | "How are pump-probe delays encoded — a scan motor, or event codes?" | event codes per delay, or bits (needs the LUTE PR for `xss_delay_bits`) |

**Optional — ask once, omit if no answer:** `scan_var` (the scanned motor; must be in
the run's `scan/` group, else the analyzer silently bins by event), `epics_pvs`
(`@ask-smalldata` / instrument scientist; cannot be added after the run).

**Resolved, not asked:** `experiment`, `work_dir`, `date`, `lute_version`, `hutch`
(caller); `daq` (`.xtc2` on disk → `lcls2`); `smd_dir` (default
`/sdf/data/lcls/ds/<hutch>/<exp>/hdf5/smalldata`).

**smalldata_tools is not asked or cloned by hand.** `SmallDataProducer` clones
`slac-lcls/smalldata_tools` into `{{ work_dir }}/smalldata_tools` and applies LUTE's
`smd.patch` on its first run (`clone_smalldata` tasklet). It skips the clone if that
directory exists, so a custom fork goes there before the first run.

**Defaults to review** (`defaults/<hutch>.yaml`): `slurm.smd`, `slurm.analyzer`.

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
