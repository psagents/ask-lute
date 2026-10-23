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
| `lute` | `release: dev` (`central:dev`, lute-lcls 0.4.0+dev) |
| `validate` | — |
| `parse` | `python3 bayfai/parse_bayfai_log.py <BayFAIOptimizer*.out>` |

**The search shape is per hutch, and lives in `defaults/<hutch>.yaml`** — data, with
the reason for each value beside it. MFX, CXI and XCS distribute `dist` over ranks with
every tilt fixed. MEC's four Epix10ka quads each need their own `fixed`, `center` and
`max_rings`, so MEC alone has its own DAG: `bayfai_mec.dag.j2` renders a `!param_sweep`
(`zip: true`) from the file's `quads`. Render config and DAG from the same context:

```bash
D=bayfai/defaults/<hutch>.yaml        # default.yaml if the hutch has none
hutch-lute render --template bayfai/bayfai.yaml.j2 --context $D \
    --set-context experiment=… date=… lute_version=… work_dir=… smalldata_tools=… \
    hutch=<hutch> daq=<lcls1|lcls2> detname=… calibrant=… dist=… \
    --whitelist-dir <LUTE>/config/templates --out <work_dir>/lute_output/<hutch>_lute.yaml
hutch-lute render --template bayfai/bayfai.dag.j2 --context $D --set-context daq=… \
    --no-whitelist --out <work_dir>/lute_output/bayfai.dag
```

No `bayfai_params` (`bo_params` before 0.4.0) is written outside MEC's per-quad
`max_rings`, so the model's own hyperparameters apply whatever the version calls them.

`daq` picks the tasks: LCLS-II `SmallDataProducer2 → BayFAIOptimizer2`, LCLS-I
`SmallDataProducer → BayFAIOptimizer`. `slurm_params` come from the defaults file's
`slurm`; `hutch-lute dags` adds account, partition and reservation.

## Walk the operator through

**Required — ask all in one message, render nothing without them:**

| Variable | Ask as | Check |
|---|---|---|
| calibrant run | "Which run is the calibrant?" | record it `--kind operator`; never fire on sample data |
| `detname` | "Which detector?" (offer the file's `detname_hint`) | in `hutch-data detectors` for that run — never a colloquial name. MEC: the four quads come from the file |
| `calibrant` | "Which calibrant?" | a name PyFAI knows (`AgBh`, `LaB6`, `CeO2`) |
| `dist` | "Expected sample–detector distance **at the current detector z**, in metres?" | no default. Each rank searches `center.dist ± rank × resolution` with initial samples around it; mfx101941027 rendered the old 0.1 m against a true 0.1426 m and most of the budget searched below the answer |
| `smalldata_tools` | "Which smalldata_tools checkout?" | has `<daq>_producers/smd_producer.py` |

**Resolved, not asked:** `experiment`, `work_dir`, `date`, `lute_version`, `hutch`
(caller); `daq` (`.xtc2` on disk → `lcls2`).

**Defaults to review** (`defaults/<hutch>.yaml`, one table with each value's comment):
`parallelized`, `fixed`, `bounds`, `resolutions`, `center` (beam centre and tilts),
`slurm`; at MEC also each quad's `center`, `fixed` and `max_rings` — those are
positions, so ask whether the quads moved. A hutch on `default.yaml` has every value
unreviewed for it: say so.

## What to know when setting it up

- **`center.dist` must be within `bounds.dist` of the truth** (model default ±0.01 m;
  MEC's config sets its own). If the distance is only roughly known, widen
  `bounds.dist` with `--set BayFAI.bounds.dist=[-0.05,0.05]` rather than guessing.
- `poni1`/`poni2` bounds default to ±2.5 mm; a beam far off the detector origin needs
  wider ones or a better `center`.
- `in_file` (input metrology) and `powder` are auto-populated from the calib
  directory and the SubmitSMD result; set them only to override.
- `out_file` defaults to `{{ work_dir }}/geom/<run>-end.data`. That `.data` file is the
  calibrated psana geometry — it still has to be deployed to the calib database
  before psana-based analyses pick it up.
- `fixed` comes from the defaults file (MFX/CXI/XCS: all three rotations). Free `rot1`/`rot2`
  only for a refinement pass: without `parallelized`, every rank builds the full
  Cartesian grid (5-D with tilts free: 151 M points, ~19 GB per rank — out of memory
  on 119 ranks).
- **Cost is `n_samples + n_iterations` × one `extract_cp`** (~5 s each on a jungfrau,
  ~83 % of rank time) once the grid is small; `max_rings`, `pts_per_deg` and powder size
  make `extract_cp` cheaper. The grid stops being small when poni resolution is fine:
  at the model's 0.0001 m it is a 1,050,804-row grid that `gp.predict` scans every
  iteration, and it never finished on mfx101941027 (0.0005 m: 16 min, same answer to
  0.02 mm). That is why every defaults file sets all six `resolutions`. Profiling:
  `results/lconreux/BAYFAI_PROFILING.md` in mfx101941027.
- **Two kills, neither "hung".** `UNRESPONSIVE` after 900 s is the executor's
  heartbeat — BayFAI prints nothing inside its BO loop. `Task timed out!` is
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
- `distance_m` is inside `center.dist + bounds.dist` and **not at a bound** — a fit
  sitting on a bound means the search space did not contain the answer; widen it.
- `beam_center_m` likewise not at a `poni` bound.
- `best_score` compares runs of the same detector and calibrant only; it has no
  absolute threshold.
