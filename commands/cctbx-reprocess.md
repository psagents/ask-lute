# /cctbx-reprocess — Reproducible CCTBX Index → Scale → Merge Setup

This command drives **ad hoc, offline reprocessing** of already-collected runs
through the CCTBX pipeline (`IndexCCTBXXFEL` → `ScaleCCTBXXFEL` → `MergeCCTBXXFEL`),
supporting one run or many merged together. This is not a live-beamline
operation — no DAQ, no eLog trigger registration, no experiment-state
tracking — just direct SLURM submission against an existing LUTE install, the
way a user reprocesses data they already collected to try different
parameters or add more statistics to a merge.

This is the one guided-setup exception to this skill's usual reference-only
role (see the top-level `SKILL.md`) — everywhere else, consult the reference
files directly rather than expecting an interactive flow.

**Phases 1–4 are pure planning — no files are written and no scripts are
run.** Execution happens only in Phase 5, after the user has reviewed and
approved the complete config set.

Read `references/cctbx-sfx-workflow.md` in full before starting — every phase
below points back into it. Templates used: `templates/IndexCCTBXXFEL.yaml`,
`templates/ScaleCCTBXXFEL.yaml`, `templates/MergeCCTBXXFEL.yaml`,
`templates/submit_cctbx_multirun.sh`, `templates/cctbx_index_scale_only.yaml`.
Consult the `ask-cctbx-xfel` skill for cctbx/psana parameter semantics
whenever a value's meaning (not just its YAML field name) is in question.

---

## Phase 1 — Gather basics

| Variable | How to obtain |
|---|---|
| `experiment` | Ask if not already known from context |
| `lute_path` | Ask for the LUTE install directory to use. If unsure, ask whether one already exists for this experiment (check under the experiment's `results/` area) before assuming a fresh install is needed |
| `work_dir` | Ask where this reprocessing attempt's output should live, e.g. `results/<name>`. This becomes the shared `work_dir` for every run in this attempt (see `cctbx-sfx-workflow.md` §7 for the per-run subfolder layout that goes under it) |

Confirm a Kerberos ticket is valid (`klist -s`); if not, show the `kinit`
command for the user to run themselves and wait for confirmation before Phase 5.

---

## Phase 2 — Crystal & processing parameters

Walk `cctbx-sfx-workflow.md` §1's required-information table explicitly — do
not guess or silently default any of these:

1. **Space group and unit cell.** If the user doesn't have these to hand, or
   isn't sure, that's a real signal to pause here rather than defaulting to a
   P1 pass without saying so (§1, §5 memory-pressure note).
2. **Reference detector geometry** — ask whether a refined `.expt` file
   already exists for this experiment (check a shared/common results
   directory first) before falling back to raw image-header geometry.
3. **Detector alias** (`data_spec.detector_address`) — confirm against
   `run.detnames`, never guess from a hutch reference table.
4. **Panel mask** — ask whether a bad/noisy-panel mask file exists. If yes,
   remember it needs to be set on *both* `spotfinder_lookup_mask` and
   `integration_lookup_mask` — these are independent fields; a mask on one
   does not apply to the other (a real, previously-hit gap).
5. **Reference PDB/MTZ for scaling** (`scaling_model`) — ask if one exists;
   OK to leave unset, but see the blank-string PHIL gotcha in §3 if so
   (never leave it `""`, use the literal string `"None"` if truly unset).
6. **Resolution cutoff** (`merging_d_min`) — required even in scaling-only
   mode; never invent a placeholder silently.
7. **Calibration `data_spec` fields** (optional) — `wavelength_offset`,
   `spectrum_eV_per_pixel`/`spectrum_eV_offset`, `<detector>.detz_offset`.
   Ask whether a prior direct `cctbx.xfel.process` config exists for this
   experiment (often under a shared results area) — these are normally
   constant across every run of one experiment, so if found, reuse them
   for every run's config rather than re-deriving them.
8. **Spotfinding starting values** — if the user reports few spots/reflections
   found with default settings, offer the verified starting point in §8
   (`spotfinder_threshold_algorithm: dispersion`, `sigma_bkgnd: 25`,
   `global_threshold: 100`, `min_spot_size: 2`,
   `dispatch_hit_finder_minimum_number_of_reflections: 40`) rather than the
   field defaults — but always check first whether an existing hand-tuned
   config for this experiment already specifies different values.

If a previous CCTBX config exists for this experiment (§1's guidance), read it
first and prefer reusing its values over re-deriving from scratch — confirm
with the user before copying them into the new config.

**Checkpoint.** Show the assembled crystal/processing parameter set. Correct?
(yes / adjust)

---

## Phase 3 — Run list and merge scope

Ask: **"Which run(s) should be processed? Just one, or several to be merged
together for better statistics?"**

- **Single run** — one `IndexCCTBXXFEL` + `ScaleCCTBXXFEL` + `MergeCCTBXXFEL`
  chain, all three in one DAG (matches the simple single-run pattern; no
  need for the multi-run layout below).
- **Multiple runs** — remind the user that a single run's merge statistics are
  typically too noisy to judge quality from (§7) if they weren't already
  planning to merge several. Record the full run list.

**Checkpoint.** Confirm the run list before generating configs.

---

## Phase 4 — Generate configs

**Still planning — nothing written to disk yet.**

### Single-run case
One YAML with all three tasks chained (`IndexCCTBXXFEL` → `ScaleCCTBXXFEL` →
`MergeCCTBXXFEL`), following the templates directly. Standard DAG (Index →
Scale → Merge, `!ALL_SUCCESS` chained).

### Multi-run case
Per `cctbx-sfx-workflow.md` §7:

1. **One YAML per run**, each with `IndexCCTBXXFEL` + `ScaleCCTBXXFEL` only
   (no per-run Merge) — `output_output_dir`/`input_path` pointed at that run's
   own `{work_dir}/r00XX/` subfolder, and **an explicit unique `phil_file`**
   for both tasks (e.g. `{{ work_dir }}/r0037/cctbx_index.phil`) — this is
   not optional for multi-run: omitting it causes a real race condition when
   runs are submitted in parallel (§7 failure signature: instant segfault,
   zero per-rank logs).
2. **One combined `MergeCCTBXXFEL` config**, `phil_parameters.input_path` set
   to the list of every run's `cctbx_scaled/` directory.
3. Use `templates/cctbx_index_scale_only.yaml` as the per-run workflow DAG
   (stops after Scale — no `next` entry for Merge).

Assemble every config block explicitly with the user — do not silently fill
in a value that wasn't confirmed in Phase 2/3.

**Checkpoint — full config review.** Show every config file that will be
written, in full, before proceeding. Correct? (yes / adjust)

---

## Phase 5 — Execute

The user has approved the parameters (Phase 2), run list (Phase 3), and full
config set (Phase 4).

1. `mkdir -p` every output directory the configs reference — LUTE does not
   create these itself (§4); every MPI rank crashes with `FileNotFoundError`
   on a missing directory.
2. Write the config file(s) and, for multi-run, the per-run workflow DAG and
   combined merge config.
3. Generate the submission script from `templates/submit_cctbx_multirun.sh`
   (multi-run) or a direct `submit_launch_slurm.sh` invocation (single-run,
   see §6's standard-submission snippet), filling in `LUTE_PATH`, `BASE_DIR`,
   `EXPERIMENT`, `RUNS`. Both **pin `PYTHONPATH` explicitly** after sourcing
   `activate_installation` (§6) — do not trust it alone, ambient shell
   `python3` resolution can silently point it at the wrong Python version.
4. Show the assembled script and ask for final confirmation before running
   it — submitting SLURM jobs is a real action on shared cluster resources,
   not something to do silently.
5. Run it. Report back job IDs and where to check output
   (`{work_dir}/r00XX/cctbx_scaled/`, `{work_dir}/cctbx_merged/`).

---

## Quick Reference — Phase Order

```
Phase 1  Gather basics        → experiment, LUTE install, work_dir
Phase 2  Crystal parameters   → space group, unit cell, geometry, mask, PDB, d_min, calibration ← user approves
Phase 3  Run list              → single run or multi-run merge scope       ← user approves
Phase 4  Generate configs     → per-run Index+Scale, combined Merge        ← user approves full review
Phase 5  Execute               → mkdir, write configs, generate + confirm + run submission script
```

Nothing touches the filesystem or SLURM before Phase 5, and Phase 5 itself
pauses for one final confirmation before actually submitting.
