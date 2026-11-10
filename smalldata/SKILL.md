# smalldata — SmallData production, droplets, and the XSS / XAS / XES analyzers

`SubmitSMD` reduces a run to an HDF5 file; an analyzer then reads named datasets
out of it. **The producer config is the setup**: an analyzer can only use what the
producer was told to write, and a missing dataset is discovered only after the run.

`droplets` is producer-only: `getDropletParams` writes sparse droplets per event and
no analyzer Task follows it.

Producer-config details beyond what is below (ROI choice, azav binning, droplets,
photon counting, which PVs exist): **`@ask-smalldata`**, required.

## Contract

| Field | Value |
|---|---|
| `template` | `smalldata/smd.yaml.j2`, with `analyses` = any of `xss`, `xas`, `xes`, `droplets` |
| `dags` | `smalldata/smd.dag.j2`, same context — workflow `smd_<analyses joined by _>` (e.g. `smd_xss_xes`, `smd_droplets`), trigger `END_OF_RUN` |
| `defaults` | `smalldata/defaults/<hutch>.yaml`, else `default.yaml` |
| `lute` | `release: dev` (`central:dev`, lute-lcls 0.4.0+dev). Not v0.3.0 for droplets: see traps |
| `validate` | — |
| `smoke` | the same template with `--set-context nevents=100 smd_dir=<scratch>/smd_test`, one `SmallDataProducer[2]` Task on the operator's representative run, then `parse` on its `.h5`. Required for `droplets` (units are only visible in the output) |
| `parse` | `python3 smalldata/parse_smd_output.py --log <.out> --h5 <run.h5> --analysis <xss\|xas\|xes\|droplets> --det <alias> [--ipm-var V] [--scan-var V]` |

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
| droplets | `<det>/droplet_nDroplets`, `<det>/var_droplet_sparse/{data,row,col,npix}` (`getDropletParams`, `nData: null`) | — (no analyzer) |

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
| `droplet_det` (droplets) | "Which detector to dropletize?" | in the run's detector names, as for the others |
| photon energy range (droplets) | "Lowest and highest photon energy you will run at?" | `droplet_thresADU` comes from the **lowest** energy (~0.4 photon there); higher energies only make it a smaller fraction of a photon |
| a representative run (droplets) | "Which run has signal on this detector?" | the smoke test and the histogram are read on it, not on whatever run is newest — a quiet run has no photon peak |

**Resolved, not asked — droplets:** the calibration units of `droplet_det`, from
`median(det.gain(run))` in psana. ≪ 1 (epix100 at CXI: 0.0597 = 1/16.75 ADU/keV) means
calib is in **keV**: set `droplet_use_rms: false` and give `droplet_threshold`,
`droplet_threshold_low` and `droplet_thresADU` in keV, with `droplet_threshold` ≈
5 × `median(det.rms × det.gain)`. ≈ 1 means calib is in ADU and `droplet_use_rms: true`
with `droplet_threshold: 5` (σ) is the usual start. See *Calibration units* below.

**Optional — ask once, omit if no answer:** `scan_var` (the scanned motor; must be in
the run's `scan/` group, else the analyzer silently bins by event), `epics_pvs`
(`@ask-smalldata` / instrument scientist; cannot be added after the run).

**Resolved, not asked:** `experiment`, `work_dir`, `date`, `lute_version`, `hutch`
(caller); `daq` (`.xtc2` on disk → `lcls2`, `.xtc` only → `lcls1`; see the top-level
*`daq` — resolve it first*); `smd_dir` (default
`/sdf/data/lcls/ds/<hutch>/<exp>/hdf5/smalldata`).

**smalldata_tools is not asked or cloned by hand.** `SmallDataProducer` clones
`slac-lcls/smalldata_tools` into `{{ work_dir }}/smalldata_tools` and applies LUTE's
`smd.patch` on its first run (`clone_smalldata` tasklet). It skips the clone if that
directory exists, so a custom fork goes there before the first run.

**Defaults to review** (`defaults/<hutch>.yaml`): `slurm.smd`, `slurm.analyzer`, and
for droplets the per-detector `droplets` thresholds and `calib_units` where the file
has them. A hutch on `default.yaml` has every droplet value unreviewed: say so.

## What to know when setting it up

### Calibration units

**`useRms: true` assumes calib is in ADU.** `dropletFunc` cuts at
`threshold × rms / gain` (`ana_funcs/droplet.py`, `setFromDet`). When a detector's gain
constants are 1/(ADU/keV), psana's `calib` is already in keV and that product is in
ADU²/keV: on cxi101933627 run 94 (`epix100_1`, gain 0.0597, rms 2.8) a "5σ" cut sat at
~235 keV, and **every event had zero droplets with no error anywhere**. Resolve the
units before rendering (*Walk the operator through*), and on a keV detector use
`useRms: false` with thresholds in keV — there, 5σ = 5 × 0.17 = 0.85 keV.

### Traps

| Trap | What happens | Do |
|---|---|---|
| LUTE's `nData` default (`1e5`) | five fixed 100 000-wide arrays per event, ~4 MB/event | `nData: null` (the template sets it) — variable-length `var_droplet_sparse/` |
| `detnames` unset, LCLS-I | `smd1_prod_config_template.py` renders `detnames = ` → `SyntaxError` when the producer imports `prod_config_<hutch>.py` (cxi101933627, first smoke test) | the template always sets it |
| `userMask` under `getDropletParams` | rendered into the config, but `dropletFunc` reads `mask` (from `det.mask`), so it has **no effect** | mask through the detector's calib status mask, or AND a mask into `det.mask` in the workspace's `smd_producer.py`. Upstream bug: drop the workaround when fixed |
| two first runs at once | both `mkdir` a new `directory`; one dies with `FileExistsError` (cxi101933627, backfilling runs 72 and 73 together) | create `directory` before registering, or launch the first run alone. Upstream: `exist_ok=True` |
| LUTE v0.3.0 | its `smd1` template emits `getDropletParams()` / `getDroplet2Photons()`; the current producer only calls `get_droplet()` / `get_droplet2photon()` — droplets silently not produced | `release: dev` |
| `getDroplet2Photons` on dev | the template returns a dict where the producer iterates a list, and puts `nData` where `droplet2Photons` ignores it | do not use it until fixed; histogram `var_droplet_sparse/data` instead |
| a hot pixel | a droplet at the same `(row, col)` in ~100 % of events, often far above one photon | `top_repeat_fraction` ≈ 1 in `parse`; mask it, then re-check |
| a quiet run | a few droplets per event and no photon peak — looks like a threshold problem and is not | read the histogram on the run the operator names as representative |
| file size | scales with hit density: 2.8 and 8.4 GB for two 36 k-event runs (cxi101933627 runs 73/72). `tile` is always 0 on a single-panel detector and is 1/5 of it | budget disk per run before registering on `END_OF_RUN` |
| photon pile-up | at 10⁴ droplets per frame neighbouring photons merge; 2- and 3-photon peaks appear at 2× and 3× | a physics cut, not a config fix — say so when reporting counts |

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

For `droplets` it also reports, from at most 5 M droplets: `droplets_per_event_median`,
`events_with_droplets`, `photon_peak` (histogram mode, calib units) and
`top_repeat_fraction` (share of events with a droplet at the single most repeated
pixel). Facts only:

- `droplets_per_event_median` 0 on a run with signal → thresholds in the wrong units.
- `photon_peak` near the photon energy (cxi101933627 runs 72/73: 10.5–10.7 keV for
  10.5 keV photons) → units and thresholds are right.
- `top_repeat_fraction` ≈ 1 → a hot pixel; mask it before trusting counts.

### Loading droplets

The sparse arrays hold every droplet of the run end to end; `var_droplet_sparse_len`
says how many belong to each event:

```python
import h5py, numpy as np
f = h5py.File(h5_path, "r")
g = f[f"{det}/var_droplet_sparse"]
n = f[f"{det}/var_droplet_sparse_len"][:]          # droplets per event
off = np.concatenate([[0], np.cumsum(n)])          # event i owns off[i]:off[i+1]
energy = g["data"][off[i]:off[i + 1]]              # droplet sums, calib units
row, col, npix = (g[k][off[i]:off[i + 1]] for k in ("row", "col", "npix"))
evt = np.repeat(np.arange(len(n)), n)              # event index per droplet (whole run)
```

Per-event datasets (`event_time`, `gas_detector/`, `lightStatus/`, `epics/`, `scan/`)
are in the same event order. A busy run holds 10⁸+ droplets (1.6 GB per column at
float64): slice with `off` rather than reading `[:]`.
