# smalldata — droplets

Read when `droplets` is in `analyses`. `droplets` is producer-only: `getDropletParams`
writes sparse droplets per event and no analyzer Task follows it.

## Walk the operator through

**Required — asked with the rest of `SKILL.md`'s required values, in the same message:**

| Variable | Ask as | Check |
|---|---|---|
| `droplet_det` | "Which detector to dropletize?" | in the run's detector names (`resolve: detnames`) |
| photon energy range | "Lowest and highest photon energy you will run at?" | `droplet_thresADU` comes from the **lowest** energy (~0.4 photon there); higher energies only make it a smaller fraction of a photon |
| a representative run | "Which run has signal on this detector?" | the smoke test and the histogram are read on it, not on whatever run is newest — a quiet run has no photon peak |

**Resolved, not asked:** the calibration units of `droplet_det`, from
`median(det.gain(run))` in psana (*Calibration units* below), and from them
`droplet_use_rms`, `droplet_threshold`, `droplet_threshold_low` and `droplet_thresADU`.
`defaults/cxi.yaml` holds them for CXI's epix100_1. **On a hutch with only `default.yaml`
they have no default: resolve all four before rendering** — unset, they render as null and
LUTE rejects the config only when the Task starts.

## Calibration units

**`useRms: true` assumes calib is in ADU.** `dropletFunc` cuts at
`threshold × rms / gain` (`ana_funcs/droplet.py`, `setFromDet`). When a detector's gain
constants are 1/(ADU/keV), psana's `calib` is already in keV and that product is in
ADU²/keV: on cxi101933627 run 94 (`epix100_1`, gain 0.0597, rms 2.8) a "5σ" cut sat at
~235 keV, and **every event had zero droplets with no error anywhere**.

- `median(det.gain)` ≪ 1 (epix100 at CXI: 0.0597 = 1/16.75 ADU/keV) → calib is in
  **keV**: `droplet_use_rms: false`, all three thresholds in keV, `droplet_threshold` ≈
  5 × `median(det.rms × det.gain)` (5 × 0.17 = 0.85 keV there).
- ≈ 1 → calib is in ADU: `droplet_use_rms: true`, `droplet_threshold: 5` (σ) is the
  usual start.

## Traps

| Trap | What happens | Do |
|---|---|---|
| LUTE's `nData` default (`1e5`) | five fixed 100 000-wide arrays per event, ~4 MB/event | `nData: null` (the template sets it) — variable-length `var_droplet_sparse/` |
| `userMask` under `getDropletParams` | rendered into the config, but `dropletFunc` reads `mask` (from `det.mask`), so it has **no effect** | mask through the detector's calib status mask, or AND a mask into `det.mask` in the workspace's `smd_producer.py`. Upstream bug: drop the workaround when fixed |
| LUTE v0.3.0 | its `smd1` template emits `getDropletParams()` / `getDroplet2Photons()`; the current producer only calls `get_droplet()` / `get_droplet2photon()` — droplets silently not produced | `release: dev` |
| `getDroplet2Photons` on dev | the template returns a dict where the producer iterates a list, and puts `nData` where `droplet2Photons` ignores it | do not use it until fixed; histogram `var_droplet_sparse/data` instead |
| a hot pixel | a droplet at the same `(row, col)` in ~100 % of events, often far above one photon | `top_repeat_fraction` ≈ 1 in `parse`; mask it, then re-check |
| a quiet run | a few droplets per event and no photon peak — looks like a threshold problem and is not | read the histogram on the run the operator names as representative |
| file size | scales with hit density: 2.8 and 8.4 GB for two 36 k-event runs (cxi101933627 runs 73/72). `tile` is always 0 on a single-panel detector and is 1/5 of it | budget disk per run before registering on `END_OF_RUN` |
| photon pile-up | at 10⁴ droplets per frame neighbouring photons merge; 2- and 3-photon peaks appear at 2× and 3× | a physics cut, not a config fix — say so when reporting counts |

## Reading the result

`parse --analysis droplets` also reports, from at most 5 M droplets:
`droplets_per_event_median`, `events_with_droplets`, `photon_peak` (histogram mode, calib
units) and `top_repeat_fraction` (share of events with a droplet at the single most
repeated pixel). Facts only:

- `droplets_per_event_median` 0 on a run with signal → thresholds in the wrong units.
- `photon_peak` near the photon energy (cxi101933627 runs 72/73: 10.5–10.7 keV for
  10.5 keV photons) → units and thresholds are right.
- `top_repeat_fraction` ≈ 1 → a hot pixel; mask it before trusting counts.

## Loading droplets

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
