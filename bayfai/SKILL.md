# bayfai — detector geometry calibration

Fits detector distance, beam center and tilts to the rings of a calibrant powder
run (SmallData accumulates the image, BayFAI optimizes against it). Self-contained:
it needs nothing from another workflow, and its output geometry is an input to
SmallData azimuthal integration and to `cctbx`.

Run it on a **calibrant run**, never on sample data, at the same detector position
as the experiment.

## Contract

| Field | Value |
|---|---|
| `template` | `bayfai/bayfai.yaml.j2` |
| `dags` | `bayfai/bayfai_mec.dag.j2` at MEC, else `bayfai/bayfai.dag.j2` — workflow `bayfai`, trigger `MANUAL` |
| `defaults` | `bayfai/defaults/<hutch>.yaml` (`mfx`, `mec`, `cxi`, `xcs`), else `default.yaml` |
| `lute` | default: `source: slac-lcls/lute@<newest +dev tag>` |
| `validate` | — |
| `resolve` | `daq`; `detnames` on the calibrant run |
| `parse` | `python3 bayfai/parse_bayfai_log.py <BayFAIOptimizer*.out>` |

**The search shape is per hutch, and lives in `defaults/<hutch>.yaml`** — data, with
the reason for each value beside it. MFX, CXI and XCS distribute `dist` over ranks with
every tilt fixed. MEC's four Epix10ka quads each need their own `fixed`, `center`,
`bounds` and `max_rings`, so MEC alone has its own DAG: `bayfai_mec.dag.j2` renders a `!param_sweep`
(`zip: true`) from the file's `quads`. Render config and DAG from the same context.

No `bayfai_params` (`bo_params` before 0.4.0) is written outside MEC's per-quad
`max_rings`, so the model's own hyperparameters apply whatever the version calls them.

`daq` picks the tasks: LCLS-II `SmallDataProducer2 → BayFAIOptimizer2`, LCLS-I
`SmallDataProducer → BayFAIOptimizer`. `slurm_params` come from the defaults file's
`slurm`; the caller adds account, partition and reservation.

## Walk the operator through

**Required — ask all in one message, render nothing without them:**

| Variable | Ask as | Check |
|---|---|---|
| calibrant run | "Which run is the calibrant?" | record it `--kind operator`; never fire on sample data |
| `detname` | "Which detector?" (offer the file's `detname_hint`) | in the run's detector names (`resolve: detnames`) — never a colloquial name. MEC: the four quads come from the file |
| `calibrant` | "Which calibrant?" | a name PyFAI knows (`AgBh`, `LaB6`, `CeO2`) |
| `dist_bounds` | "Loose sample–detector distance range **at the current detector z**, `[low, high]` in metres?" | no default; not at MEC (per-quad bounds come from the file). Becomes `bounds.dist`, split across ranks — make it loose: the answer must be inside, not near the middle, and a fit at an edge means widen it. `0 < low < high`. No central distance is asked: ranks overwrite `center.dist` with their window centre, so the template writes the midpoint only for the validator. mfx101941027 rendered a 0.1 m guess against a true 0.1426 m — a range is harder to get wrong |

**Resolved, not asked:** `experiment`, `work_dir`, `date`, `lute_version`, `hutch`
(caller); `daq` (`.xtc2` on disk → `lcls2`, `.xtc` only → `lcls1`; see the top-level
*`daq` — resolve it first*).

**smalldata_tools is not asked or cloned by hand.** `SmallDataProducer` clones
`slac-lcls/smalldata_tools` into `{{ work_dir }}/smalldata_tools` and applies LUTE's
`smd.patch` on its first run (`clone_smalldata` tasklet). It skips the clone if that
directory exists, so a custom fork goes there before the first run.

**Defaults to review** (`defaults/<hutch>.yaml`, one table with each value's comment):
`parallelized`, `fixed`, `center` (beam centre and tilts), poni/rot `bounds`, `slurm`, and at MEC
`bounds.dist`, `resolutions` and each quad's `center`, `bounds`, `fixed` and `max_rings` —
those are positions, so ask whether the quads moved. Outside MEC, `resolutions` are
the model's (list them as such). A hutch on `default.yaml` has every value
unreviewed for it: say so.

## What to know when setting it up

- **`bounds` are absolute `[low, high]` limits** (lute#157), not offsets around
  `center`. The model validator rejects `low >= high`, `bounds.dist` low ≤ 0, and a
  free parameter whose `center` lies outside its bounds; its message gives the old
  conversion, `[center + old_low, center + old_high]`. Pre-#157 configs with
  `dist: [-0.05, 0.05]` fail at load.
- With `parallelized: dist`, `bounds.dist` is the whole range, one window per rank:
  `geometric` (`dist_spacing` default, finer at short distance) or `linear`. The final
  refinement may move `dist` by `step` window widths.
- `poni1`/`poni2` bounds default to ±2.5 mm around 0; a beam far off the detector
  origin needs wider ones or a better `center`.
- New hyperparameters under `bayfai_params`: `n_cand` (8192 random grid points scored
  per BO step; 0/None = whole grid), `gp_restarts` (10), `min_points` (geometries with
  fewer control points score 0; None = 100 for a dist sweep, else off).
  `n_iterations` default is now 40 (was 80).
- `h5` (the powder) is auto-populated from the SubmitSMD result; set it only to
  override. There is no `in_file`/`powder`: BayFAI builds the detector from the
  LCLSGeom template metrology.
- `out_file` defaults to `{{ work_dir }}/geom/<run>-end_<detname>.data`. That `.data` file is the
  calibrated psana geometry — it still has to be deployed to the calib database
  before psana-based analyses pick it up.
- `fixed` comes from the defaults file (MFX/CXI/XCS: all three rotations). Free `rot1`/`rot2`
  only for a refinement pass: without `parallelized`, every rank builds the full
  Cartesian grid (5-D with tilts free: 151 M points, ~19 GB per rank — out of memory
  on 119 ranks).
- **Cost is `n_samples + n_iterations` × one `extract_cp`** per rank; `max_rings`,
  `pts_per_deg` and powder size make `extract_cp` cheaper. Since lute#157 each rank is
  2.3–3.3× faster (one OpenMP thread per rank, `NUMPY_MADVISE_HUGEPAGE=0`, set by the
  managed Task), and `n_cand` caps what `gp.predict` scans per step, so the model's
  0.0001 m poni resolution no longer stalls (before #157 it never finished on
  mfx101941027's 1,050,804-row grid). Jungfrau max wall in the #157 benchmark: 401 s.
- **Two kills, neither "hung".** `UNRESPONSIVE` after 900 s of silence is the
  executor's heartbeat — BayFAI prints nothing inside its BO loop. Since lute#157 the
  silence counts from submission (before, any Task quiet for its first heartbeat was
  killed at once). `Task timed out!` is
  `task_timeout`. Busy ranks in `sacct` TotalCPU mean it was working.
- **Fire it on the calibrant run only**, the one the operator names. Record the result
  with the detector-z range it holds for (mfx101941027: run 25 → runs 23–40 at ~375 mm).
- **Parallel variants need their own `work_dir`.** Plots are `figs/<exp>_r<run>_<det>.png`
  with no job id, and there is one `lute.db` per `work_dir`.

## Reading the result

`parse_bayfai_log.py` prints `task_completed`/`task_failed`, `distance_m`,
`beam_center_m`, `rotations_rad`, `best_score`, `lowest_q`/`highest_q`, `out_file`,
and the distinct exception lines under `errors`.

Acceptance (simple, so it lives here):

- `task_completed` is true and `out_file` exists.
- `distance_m` is inside `bounds.dist` and **not at a bound** — a fit
  sitting on a bound means the search space did not contain the answer; widen it.
- `beam_center_m` likewise not at a `poni` bound.
- `best_score` compares runs of the same detector and calibrant only; it has no
  absolute threshold.
