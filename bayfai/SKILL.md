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
| `dags` | `bayfai/bayfai.dag` — workflow `bayfai`, trigger `MANUAL` (fired on the one calibrant run) |
| `lute` | `release: <current lute-lcls>` |
| `validate` | — |
| `parse` | `python3 bayfai/parse_bayfai_log.py <BayFAIOptimizer*.out>` |

`bayfai.dag` branches on DAQ generation (`!branch_daq2`): LCLS-II runs
`SmallDataProducer2 → BayFAIOptimizer2`, LCLS-I `SmallDataProducer → BayFAIOptimizer`.

## Context

| Variable | Source | If unknown |
|---|---|---|
| `experiment`, `work_dir`, `date` | caller | — |
| `lute_version` | the `release` installed | — |
| `detname` | `run.detnames` on the calibrant run — never a colloquial name | blocker: ask |
| `calibrant` | operator; a name PyFAI knows (`AgBh`, `LaB6`, `CeO2`) | `AgBh`, list as unreviewed |
| `dist` | approximate sample-detector distance, **metres** | `0.1`, list as unreviewed |
| `smalldata_tools` | the experiment's `smalldata_tools` checkout | ask |

## What to know when setting it up

- **`center.dist` must be within `bounds.dist` of the truth** (±0.05 m by default).
  If the distance is only roughly known, widen `bounds.dist` with
  `--set BayFAI.bounds.dist=[-0.1,0.1]` rather than guessing a centre.
- `poni1`/`poni2` bounds are ±5 mm; a beam far off the detector origin needs wider
  ones or a better `center`.
- `in_file` (input metrology) and `powder` are auto-populated from the calib
  directory and the SubmitSMD result; set them only to override.
- `out_file` defaults to `{{ work_dir }}/geom/<run>-end.data`. That `.data` file is the
  calibrated psana geometry — it still has to be deployed to the calib database
  before psana-based analyses pick it up.
- `fixed` defaults to `["rot3"]`. Add `rot1`/`rot2` when the rings are too few to
  constrain tilts.

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
