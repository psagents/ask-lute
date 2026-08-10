# CCTBX SFX Workflow (IndexCCTBXXFEL → ScaleCCTBXXFEL → MergeCCTBXXFEL)

This file captures lessons from real, hard-won debugging of a full CCTBX-only SFX
pipeline (no CrystFEL/Cheetah): six rounds of a job dying before a correct run was
reached. Read it **before** building or submitting this specific workflow. It
supplements, and takes precedence over, the general guidance in
`workflow-creation.md`, `result-passing.md`, and `slurm-submission.md` for this one
task chain.

**Managed Task → Task class name** (verify against the actual installed
`lute/managed_tasks.py`, not just this table):

| Managed Task | Task class (YAML key) |
|---|---|
| `CCTBXIndexer` | `IndexCCTBXXFEL` |
| `CCTBXScaler` | `ScaleCCTBXXFEL` |
| `CCTBXMerger` | `MergeCCTBXXFEL` |

---

## 1. Required information — ask the user, do not guess or default silently

Before writing a single line of YAML, walk the user through these. Every one of
them materially changes indexing/scaling/merging quality, and defaulting them
silently produces a technically-running but scientifically weak first pass:

| Parameter | Why it matters | If unknown |
|---|---|---|
| **Space group** (e.g. `"P 43 21 2"`) | Constrains indexing + filtering | OK to skip for a deliberate P1 first pass, but say so explicitly and warn about the memory cost (see §5) |
| **Unit cell** (e.g. `"78 78 39 90 90 90"`) | Same as above | Same as above |
| **High-resolution cutoff / `merging_d_min`** | Required by `cctbx.xfel.merge` even in scaling-only mode; wrong values silently produce empty or garbage merged output | Do NOT invent a placeholder value silently — tell the user you're using one and that it must be revisited after inspecting first-pass stats |
| **Reference detector geometry** (a refined `.expt` file, e.g. from a prior BayFAI/geometry-optimization run) | `IndexCCTBXXFEL`'s `phil_parameters.input_reference_geometry` — using a refined geometry instead of raw image-header geometry can substantially change indexing rate | Ask if a refined geometry file exists for this experiment (often under a shared/common results directory) before falling back to image-header geometry |
| **Reference PDB/MTZ for scaling** (`scaling_model`, mark0 algorithm) | Better absolute scaling than internal Wilson/KB scaling | OK to leave unset (see §3 for how to leave it unset *correctly*) |
| **Detector alias** (`data_spec.detector_address`) | Must match `run.detnames`/`event_keys` for this experiment, not guessed from the hutch table | Confirm with the user; use `references/hutches/{hutch}.md` only as a starting menu of plausible aliases, never as ground truth |
| **Run number(s)** | — | Ask explicitly |

**If a previous CCTBX run exists for this same experiment** (check the
experiment's results area for prior `configs/*.yaml` + rendered `.phil` files from
a completed run), read it first — it is usually the single best source for
correct unit cell/space group/geometry/reference-model values and a
verified-working SLURM resourcing pattern (see §6). Prefer reusing its values
over asking the user to re-derive them from scratch, but confirm with the user
before copying them into a new run.

---

## 2. `data_spec` is an open dict, unlike `phil_parameters`

`IndexCCTBXXFEL.data_spec` is a bare `Optional[Dict[str, Union[str, float, int]]]`:
every key becomes a `key=value` line in the generated psana locator (`.loc`) file,
with no per-key validation — unlike `phil_parameters`, which is a structured
sub-model. Always required: `experiment`, `run`, `detector_address`. For other
available locator/calibration keys, consult the `ask-cctbx-xfel` skill.

---

## 3. PHIL template gotcha: blank string defaults crash the parser

`config/templates/cctbx_scale.phil` and `config/templates/cctbx_merge.phil` (Jinja
templates rendered from `phil_parameters`) render several `{{ var }}`
substitutions **unconditionally** — no `{% if %}` guard. If the corresponding
Pydantic field's default is `""` and the YAML doesn't override it, the rendered
`.phil` file contains a bare `key = ` with nothing after the `=`, and
`libtbx.phil` throws:

```
RuntimeError: Missing value for <key> (file ".../cctbx_scale.phil", line N)
```

**Known landmines** (str-typed fields defaulting to `""`, rendered unconditionally
in both `ScaleCCTBXXFEL` and `MergeCCTBXXFEL`):

- `scaling_model` → renders as `scaling.model = `
- `output_prefix` → renders as `output.prefix = `

**Fix:** give these a real value, or the **literal string `"None"`** (not Python
`None`, not omitted, not `""`) when there truly is no reference model — the PHIL
grammar accepts the bare word `None` as "unset" for a `path`-typed parameter, but
not a blank right-hand side. `output_prefix` just needs *any* non-empty string;
its content is purely cosmetic (prefixes output filenames), so the parser doesn't
care what it says as long as it isn't blank.

**Contrast — fields that ARE safely guarded** (leaving them blank/unset in YAML is
fine, don't add `"None"` to these): `filter_unit_cell_value_target_unit_cell`,
`filter_unit_cell_value_target_space_group`, `filter_unit_cell_cluster_covariance_file`,
`scaling_unit_cell`, `scaling_space_group`, `merging_d_max`,
`statistics_cciso_mtz_file`, `output_tmp_dir` — each uses a Jinja `{% if %}` guard
or an `... if x else "..."` fallback in the template.

**When debugging any "Missing value for X" crash:** read the actual rendered
`.phil` file in `work_dir` (`cctbx_index.phil` / `cctbx_scale.phil` /
`cctbx_merge.phil`) — it shows exactly which line is blank. Don't guess from the
YAML alone; the template may render a field you didn't expect.

---

## 4. Output directories must exist before submission — LUTE does not create them

`dials.stills_process` (indexing) and `cctbx.xfel.merge` (scale/merge) open
per-MPI-rank log files directly inside `output.output_dir`. **Neither program
creates that directory.** If it's missing, every rank crashes with
`FileNotFoundError: ... log_rank0109.out`, and the whole SLURM job dies within
seconds.

Any submission script for this workflow **must** `mkdir -p` the index/scale/merge
output directories before calling `launch_slurm`/`submit_slurm`:

```bash
mkdir -p "${WORK_DIR}/index" "${WORK_DIR}/scale" "${WORK_DIR}/merge"
```
(or whatever directory names the YAML's `output_output_dir` fields use).

---

## 5. Result chaining is NOT uniform across this task chain

This differs from the general CrystFEL guidance in `result-passing.md` — read
carefully:

- **`IndexCCTBXXFEL`** does not depend on a prior task at all; it reads raw psana
  data directly via `data_spec` and does spotfinding + indexing + integration in
  one call.
- **`ScaleCCTBXXFEL.phil_parameters.input_path` has NO database auto-resolution**
  from `IndexCCTBXXFEL`. Its validator only normalizes the given value to a list —
  it never calls `read_latest_db_entry`. You must set it explicitly to the same
  directory `IndexCCTBXXFEL.phil_parameters.output_output_dir` used (both are
  static, parse-time-known paths under `work_dir`, so `{{ work_dir }}/index`
  substitution is correct here — this is NOT a case for task-result chaining).
- **`MergeCCTBXXFEL.phil_parameters.input_path` DOES auto-resolve** from the LUTE
  DB (`read_latest_db_entry(work_dir, "ScaleCCTBXXFEL", "result.payload")`),
  because `ScaleCCTBXXFEL` sets `Config.set_result = True` and publishes
  `result_output_dir` as the result. Leave `input_path` blank here — this is the
  one place standard auto-chaining applies in this chain.

**Memory pressure during `CCTBXIndexer` scales with indexing search breadth, not
just rank density.** Indexing in P1 (no known symmetry) must search and refine
far more candidate lattice solutions per still than indexing with a known unit
cell + space group, and can OOM-kill individual MPI ranks at rank counts that are
perfectly safe with known symmetry. This is one more reason to get the crystal's
space group/unit cell from the user up front (§1) rather than defaulting to a P1
pass — it isn't just about indexing quality, it changes the resource profile of
the job.

---

## 6. SLURM submission — the entry points have one correct, fixed location

**Do not guess where LUTE's entry points live, and do not look in
`~/.cache/lute_build_env_*`.** After `./build.sh -e` is run inside a LUTE
installation directory (call it `LUTE_DIR`), the usable entry points and their
supporting Python packages always land at these two fixed paths, unconditionally,
regardless of which Python version built them:

- `${LUTE_DIR}/install/bin/` — contains `launch_slurm`, `submit_slurm`,
  `submit_launch_slurm.sh`, `activate_installation`, `run_task`, etc. Each script
  has its own fixed shebang into a specific conda env, so these are directly
  runnable once on `PATH` — no venv activation needed for the *interpreter*.
- `${LUTE_DIR}/install/lib/python<ver>/site-packages/` — contains the actual
  Python packages these entry points import (e.g. `launch_scripts`). This is why
  `PATH` alone isn't enough: without this on `PYTHONPATH`, `launch_slurm` runs but
  crashes with `ModuleNotFoundError: No module named 'launch_scripts'`.

**`${LUTE_DIR}/install/bin/activate_installation` sets both of these for you** —
always source it rather than manually reconstructing `PATH`/`PYTHONPATH`, and
never substitute a `~/.cache/lute_build_env_*` glob in its place. Those cache
directories are keyed by an MD5 hash of the install path and Python version; one
existing there proves nothing about whether it has usable entry points for *this*
specific `LUTE_DIR` — they can be stale, empty, or built for an entirely
unrelated installation.

**`activate_installation` alone is not reliable — pin `PYTHONPATH` explicitly
too.** It computes its Python version via `python3 -c '...'` on whatever is
first on `PATH` at the moment it runs, not the version LUTE was actually built
with. On S3DF login nodes a personal conda env commonly shadows the intended
`python3` (e.g. resolves to `3.13` when LUTE was built for `3.9`), silently
pointing `PYTHONPATH` at a directory that doesn't exist. The symptom is
`ModuleNotFoundError: No module named 'launch_scripts'` immediately on
`launch_slurm`/`submit_slurm` invocation, with no other error. Confirm the real
version and pin it after sourcing `activate_installation`, don't just trust it:

```bash
source "${LUTE_DIR}/install/bin/activate_installation"
LUTE_PYVER="$(basename "$(ls -d "${LUTE_DIR}"/install/lib/python*/ | head -1)")"
export PYTHONPATH="${LUTE_DIR}/install/lib/${LUTE_PYVER}/site-packages:${PYTHONPATH}"
```

Standard submission, verified against a real successful run of this pipeline:

```bash
source "${LUTE_DIR}/install/bin/activate_installation"
LUTE_PYVER="$(basename "$(ls -d "${LUTE_DIR}"/install/lib/python*/ | head -1)")"
export PYTHONPATH="${LUTE_DIR}/install/lib/${LUTE_PYVER}/site-packages:${PYTHONPATH}"
"${LUTE_DIR}/install/bin/submit_launch_slurm.sh" \
  "${LUTE_DIR}/install/bin/launch_slurm" \
  -c <config.yaml> -W <workflow.dag> \
  -e <experiment> -r <run> \
  --partition=milano --account=lcls:<experiment>
```

**Always `cd` into the config's `work_dir` before submitting.** SLURM writes
`slurm-*.out` and the per-task `CCTBXIndexer_*.out`/etc. logs relative to the
submitting shell's current directory, not `work_dir` — submitting from
somewhere else (e.g. `$HOME`) silently scatters logs where you won't think to
look for them.

Other confirmed points:

- **Do not source `psconda.sh` separately.** `activate_installation` plus each
  entry point's shebang is sufficient. If you do source it anyway, its conda
  deactivate hooks reference unset variables and will crash a `set -euo pipefail`
  script with `unbound variable` — keep `set +u` across that one line if so.
- **Never pass `--mem` explicitly** in `slurm_params` for any of these three
  tasks. The cluster's default memory allocation is the standard, verified-working
  choice for this workload — adding an explicit `--mem` is not the pattern used in
  known-good runs and isn't necessary.
- **Every per-task `slurm_params` in the DAG needs its own `--partition` and
  `--account`.** `launch_slurm`/`submit_slurm` spawns a separate `sbatch` call per
  task — these do not inherit anything from an outer wrapper job.
- **Typical resourcing** (from a verified successful run): `CCTBXIndexer` —
  `--ntasks-per-node=60 --nodes=4 --cpus-per-task=1`; `CCTBXScaler` /
  `CCTBXMerger` — `--ntasks-per-node=60 --nodes=1 --cpus-per-task=1`. Scale/Merge
  don't benefit from multi-node the way indexing does.

---

## 7. Processing multiple runs into one merge

A single run's statistics are too noisy to judge data quality from — always
plan to merge several runs, not one.

**Layout — one shared `work_dir`, one subfolder per run:**
```
{work_dir}/
  r0035/cctbx_indexed/   r0035/cctbx_scaled/
  r0036/cctbx_indexed/   r0036/cctbx_scaled/
  ...
  cctbx_merged/          # one shared final merge, not per-run
```

Each run gets its own `IndexCCTBXXFEL` + `ScaleCCTBXXFEL` config (index →
integrate → scale only, no per-run merge — merging happens once at the end
across all runs), with `output_output_dir`/`input_path` pointed at that run's
own `r00XX/` subfolder.

**Critical: give every run's `IndexCCTBXXFEL` and `ScaleCCTBXXFEL` an explicit,
unique `phil_file`** (e.g. `{{ work_dir }}/r0037/cctbx_index.phil`), even
though it's optional and normally auto-populated. The auto-populated default
(`{{ work_dir }}/cctbx_index.phil`) does **not** include the run number — if
multiple runs share one `work_dir` and are submitted in parallel (the normal
case for multi-run processing), they race to write/read the *same* phil file,
and the reader picks up a corrupted/interleaved file mid-write from another
run's job. Failure signature: instant segfault (return code -11) with zero
per-rank logs written (the crash happens before MPI even dispatches work) —
easy to misdiagnose as a data problem with the specific run rather than this
collision, especially since it's intermittent (only whichever run loses the
race fails, and a bare retry can succeed).

**The final `MergeCCTBXXFEL.phil_parameters.input_path` accepts a list** —
this is how multiple runs get combined into one merge:
```yaml
input_path:
  - "{{ work_dir }}/r0035/cctbx_scaled"
  - "{{ work_dir }}/r0036/cctbx_scaled"
  - "{{ work_dir }}/r0037/cctbx_scaled"
```
Don't rely on the §5 auto-chaining here — set the list explicitly, since it's
reading from multiple runs at once rather than one `ScaleCCTBXXFEL` result.

**The per-run workflow DAG should stop after Scale** (no `next` entry for a
per-run Merge) — the combined Merge is a separate, single-task submission
(e.g. `submit_slurm --taskname CCTBXMerger`), run once after every run's Scale
stage has finished.

**Ask about the experiment's node/core budget before submitting many runs at
once.** Each `CCTBXIndexer` job needs its own nodes (verified baseline: 4,
plus 1 for the wrapper job managing it) — submitting every run's Index+Scale
job simultaneously can exceed a shared cluster allocation. `templates/
submit_cctbx_multirun.sh` batches submissions (`MAX_CONCURRENT_INDEXING`,
default 4), submitting the next batch only once the previous one's jobs have
left the queue — set this from the experiment's actual budget, not copied
from another experiment.

---

## 8. Starting spotfinding values — one verified-working config, not universal defaults

A good starting point when default spotfinding settings produce disappointing
spot/reflection counts — not something to apply blindly. Always ask the user
for detector type and check for an existing hand-tuned config for the
experiment first (§1):

```yaml
spotfinder_threshold_algorithm: "dispersion"        # vs. tool default dispersion_extended
spotfinder_threshold_dispersion_sigma_bkgnd: 25.0   # vs. field default 6
spotfinder_threshold_dispersion_global_threshold: 100  # vs. field default 0
spotfinder_filter_min_spot_size: 2                  # vs. field default 3
dispatch_hit_finder_minimum_number_of_reflections: 40  # vs. tool default 16
```

`spotfinder_threshold_algorithm` is worth calling out specifically: if left
unset, LUTE never emits an `algorithm =` line at all, so `dials.stills_process`
silently falls back to its own compiled-in default (`dispersion_extended`) —
more conservative near already-detected strong pixels, finding fewer spots
than plain `dispersion`, with nothing indicating the choice was never applied.

---

## 9. `radial_average` — a diagnostic, not a spotfinding/indexing parameter

`IndexCCTBXXFEL.phil_parameters.radial_average_*` (`enable`,
`two_theta_low`/`two_theta_high`, `verbose`, `output_bins`, `show_plots`,
`mask`) controls `dials.stills_process`'s top-level `radial_average` scope —
it computes a radial intensity average per image, independent of the
spotfinding/indexing/integration steps, typically used to sanity-check
detector distance calibration against known powder-ring positions. All seven
fields are optional and individually omitted from the rendered phil unless
explicitly set — enabling it does not by itself change indexing behavior.
Consult `ask-cctbx-xfel` for when this diagnostic is actually worth running.
