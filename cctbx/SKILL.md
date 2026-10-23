# cctbx — serial crystallography with cctbx.xfel (index → scale → merge)

Built from `psagents/setup-cctbx-pipeline` (`baa3a20`, templates and validation) and
`psagents/cctbx-sfx-workflow` (`fd1e468`, merge-log parsing), both from the
mfx101624926 lysozyme campaign. What a merge statistic *means*, and when to move
d_min: **`@ask-cctbx-xfel`** (`references/merge-assessment.md`), required.

## Not in production — needs the fork

The tasks and PHIL fields here (hit finder, `spotfinder_threshold_algorithm`,
`radial_average_*`, `integration_lookup_mask`, Merge `tag`/`sample`) exist only on
**`lcls-mlcv/lute@tag-sample-based-workflow`**, not on `slac-lcls/lute@dev` or in
`lute-lcls` from pip. Build it once per experiment area:

```bash
git clone -b tag-sample-based-workflow https://github.com/lcls-mlcv/lute.git <results>/lute
source /sdf/group/lcls/ds/ana/sw/conda2/manage/bin/psconda.sh
cd <results>/lute && bash build.sh -e -s /sdf/group/lcls/ds/ana/sw/conda2/manage/bin/psconda.sh
```

`-e` skips wrapdb, which compute nodes cannot reach. Build with the same Python the
batch jobs use (conda2, 3.9): a mismatch is `ModuleNotFoundError: No module named
'run_task'`. The usable entry points are then `<results>/lute/install/bin/`.

## Contract

| Field | Value |
|---|---|
| `template` | `cctbx/cctbx_pipeline.yaml.j2` |
| `dags` | `cctbx_index_scale.dag` — workflow `cctbx_index_scale`, trigger `END_OF_RUN`; `cctbx_merge.dag` — workflow `cctbx_merge`, trigger `MANUAL`; `cctbx_rescale.dag` — workflow `cctbx_rescale`, trigger `MANUAL` |
| `lute` | `source: lcls-mlcv/lute@tag-sample-based-workflow` |
| `validate` | `python3 cctbx/validate.py <rendered.yaml> "<unit cell from hutch-data cell>"` |
| `parse` | `python3 cctbx/parse_merge_log.py <work_dir>/merge_<tag>/<vNNN>/merge_<tag>_main.log` |

### How the three workflows fit

- **`cctbx_index_scale`** fires at the end of every run and indexes and scales that
  run into `{{ work_dir }}/r<run>/`. It does not look at tags. Every run is indexed,
  including non-sample ones — cheap compared with missing a run, and the merge below
  is what selects.
- **`cctbx_merge`** is fired by hand. `MergeCCTBXXFEL.phil_parameters.<tag|sample>`
  makes LUTE resolve `input_path` itself at parse time: every run carrying that eLog
  tag (or assigned to that sample) **whose `ScaleCCTBXXFEL` has a result in
  `lute.db`**; runs without one are skipped with a warning
  (`lute/io/models/sfx_merge.py`, `normalize_and_resolve_input_path`). So a merge
  covers exactly the tagged runs finished so far — fire it again as more land.
- **`cctbx_rescale`** re-scales and merges without re-indexing, for a new d_min.

The template's `merge_version` context puts each merge in
`{{ work_dir }}/merge_<tag>/<vNNN>/` so iterations never overwrite each other; that
directory must exist before the merge job starts.

## Walk the operator through

Required: every row marked *blocker: ask* below, in one message — `tag`/`selector`
(tag or sample?), `detector_address` (check `hutch-data detectors`), `pdb_file`,
`geometry_file`, `mask_file` (absolute paths that exist). Then show `d_min`,
`merge_version` and the spectrometer calibration with their defaults, once. No
`defaults/` file: the pipeline is per experiment.

| Variable | Source | If unknown |
|---|---|---|
| `experiment`, `work_dir`, `date` | caller | — |
| `tag`, `selector` | the eLog tag (`selector: tag`) or eLog sample (`selector: sample`) naming the dataset. If the operator names *what was in the beam*, it is a sample; never approximate a sample with a tag | blocker: ask |
| `detector_address` | `hutch-data detectors` on one run of the dataset, confirmed by the operator | blocker: ask |
| `pdb_file` | reference structure, absolute path | blocker: ask |
| `unit_cell`, `space_group` | `hutch-data cell <pdb_file>` — always from CRYST1, never typed in | — |
| `geometry_file` | refined `.expt` (e.g. from a geometry refinement) | blocker: ask |
| `mask_file` | bad-pixel mask, absolute path | blocker: ask |
| `d_min` | starting resolution, Å; start conservative | `2.5`, list as unreviewed |
| `merge_version` | `v001`, then the next free `vNNN` under `merge_<tag>/` | `v001` |
| `wavelength_offset`, `spectrum_eV_per_pixel`, `spectrum_eV_offset` | per-experiment spectrometer calibration; all three or none | omit — nominal wavelength, list as unreviewed |
| `select_min_ct`, `select_max_ct` | `200` / `300` only when all of a, b, c > 100 Å | omit |

`d_min` is written to both `ScaleCCTBXXFEL` and `MergeCCTBXXFEL`; never override one
without the other.

## Known traps

Config-time — caught by `validate.py`, so re-run it after any hand edit:

| Trap | Symptom |
|---|---|
| `parallel_a2a` set | `TypeError: hkl_group.distribute_reflection_table()` at `group_reflections.py:123` |
| `modify` in Merge `dispatch_step_list` | `KeyError: "Unknown column 's1'"` — Scale already applied polarization |
| no Merge `dispatch_step_list` | the default pipeline re-runs filter steps and hits the covariance crash |
| Merge suffixes not `.expt` / `.refl` | merge finds zero files (default is `_integrated.expt`) |
| shared `phil_file` across runs | parallel runs overwrite each other's phil: instant segfault, no per-rank logs |
| unit cell not the PDB's | indexing against the wrong lattice |

Setup and runtime — not caught:

| Trap | Fix |
|---|---|
| Output directories missing | `dials.stills_process` / `cctbx.xfel.merge` open per-rank logs without creating the directory — every rank dies with `FileNotFoundError`. Pre-create `r<run>/index/logs`, `r<run>/scale` per run (`hutch-lute` `ensure_run_dirs`) and `merge_<tag>/<vNNN>` per merge. |
| `filter_unit_cell_algorithm: cluster` | needs a covariance file, `TypeError` at `experiment_filter.py:195`; the template uses `unit_cell` |
| `statistics_cciso_mtz_file: "None"` | cctbx opens a file named `None`; leave it unset |
| Blank string PHIL value (`scaling_model: ""`, `output_prefix: ""`) | `RuntimeError: Missing value for <key>` — give a value; read the rendered `.phil` to see which line is blank |
| `preprocess_exception` on every event, or zero reflections at scale | wrong `detector_address` |
| Indexing in P1 | far more lattice candidates per still; ranks OOM at rank counts safe with known symmetry |
| Kerberos expired | eLog tag/sample resolution returns nothing: `kinit -c FILE:$HOME/krb5cc.ticket` |
| Explicit `--mem` in `slurm_params` | not needed; known-good runs use the default |
| `radial_average_two_theta_*` | 12.5–22.8° is calibrated for MFX Jungfrau; other detectors/energies need their own range |

## Reading the result

`parse_merge_log.py` prints, with no thresholds: `d_min`, the refined `unit_cell`,
`lattices`, `overall` (completeness, multiplicity, CC½), per-shell `shells`
(completeness, `asu_multi`, `obs_multi`, `n_meas`, I/σ, CC½, R_int, R_split),
`image_shells` (lattices accepted per shell), and `missing_sections` — a table
missing from a non-empty log means the format changed, not that the data are bad.

Whether those numbers are good, and which shell sets d_min:
`@ask-cctbx-xfel` `references/merge-assessment.md`. Compare two merges only at equal
d_min.
