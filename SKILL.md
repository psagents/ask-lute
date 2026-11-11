---
name: ask-lute
description: >
  How to set up a LUTE (LCLS Unified Task Executor) workflow, and the LUTE
  reference behind it. Dispatches to a sub-skill per analysis — BayFAI geometry
  calibration, SmallData production, CCTBX SFX — each of which returns
  the template, DAGs, trigger, LUTE install and output-log parser a caller needs.
  Triggers on: set up lute, lute config, lute yaml, lute dag, lute workflow, 
  lute install.
---

# ask-lute — setting up LUTE workflows

You hold **setup knowledge**: what a workflow needs in its config and DAG to run,
and how to read what it writes. You hold no hutch-specific inventories, and no
verdict on whether a result is scientifically good — that belongs to whoever
called you (`hutch-copilot/assess-analysis`) and, for SFX, to `ask-cctbx-xfel`.

## Dispatch

Identify the analysis, then read that sub-skill's `SKILL.md` and follow it.

| Analysis | Sub-skill |
|---|---|
| Detector geometry calibration on a powder run — BayFAI, AgBh / LaB6 / CeO2 | [`bayfai/SKILL.md`](bayfai/SKILL.md) |
| SmallData production and its analyzers — XSS, XAS, XES, azav, difference signal | [`smalldata/SKILL.md`](smalldata/SKILL.md) |
| Serial crystallography with cctbx.xfel — index / scale / merge, d_min | [`cctbx/SKILL.md`](cctbx/SKILL.md) |

Anything else (CrystFEL, XTC conversion, a new task): answer from the references
below and the per-task templates in `templates/`.

## The setup contract

Every sub-skill answers "set up X for experiment E" with these fields. They are data —
files, variables, facts — never a caller's command: the caller maps each field onto its
own tools.

| Field | Meaning |
|---|---|
| `template` | Path to one config template. `${{ var }}` is filled at render time; LUTE's own `{{ work_dir }}` / `{{ run:04d }}` pass through untouched. |
| `context` | The `${{ }}` variables the template needs: the sub-skill's `defaults` file (`--context`) plus the operator's answers and resolved values (`--set-context`). |
| `defaults` | `<sub-skill>/defaults/<hutch>.yaml`, else `default.yaml` where the sub-skill has one: the per-hutch knowledge as data, each value with its reason. |
| `sets` | `TASK.BLOCK.KEY=value` overrides on top of the template. |
| `dags` | Each DAG with its workflow name and eLog trigger (`START_OF_RUN`, `END_OF_RUN`, `MANUAL`, `RUN_PARAM_IS_VALUE:<name>:<value>`). A `.dag.j2` is rendered with the same context and delimiters, without the LUTE template whitelist; a `.dag` is copied. The caller adds account, partition and reservation. |
| `lute` | `release: <version>` — in production; runs from the central build `/sdf/group/lcls/ds/tools/lute/<version>` (`dev` = lute-lcls 0.4.0+dev), pip venvs only if there is none. Or `source: <repo>@<branch>` — not in production, clone and build that branch (needs internet: not from a hutch host). |
| `validate` | Optional command; non-zero exit means the rendered config must not be installed. |
| `smoke` | Optional. The same template rendered with `nevents` small (100) and its output directory in scratch, submitted as one Task on a run the operator names, then read with `parse` — **before** registering. It catches what only shows at run time (wrong units, a config that fails to import) in minutes, without writing into the experiment's real output. |
| `resolve` | Facts the caller reads off the experiment, and what each fills or checks: `daq` → `daq`; `detnames` (a run) → checks every detector variable; `unit_cell` (`pdb_file`) → `unit_cell`, `space_group` from CRYST1; `run_dirs` → directories to create before a Task starts. |
| `unreviewed` | Every parameter left at a default, with the default used. |
| `parse` | Command per output log. Prints JSON facts, never a verdict. |

### `daq` — resolve it first

Every sub-skill branches on `daq`, and LCLS-I and LCLS-II differ in almost every path.
Resolve it from the run's files before anything else, and pass it to the caller:

- `.xtc2` in `xtc/` → `lcls2`
- `.xtc` only → `lcls1`
- neither (no run yet) → ask

| | `lcls2` | `lcls1` |
|---|---|---|
| SmallData producer Task | `SmallDataProducer2` | `SmallDataProducer` |
| producer, templates | `lcls2_producers/`, `smd2_prod_config_template.py` | `lcls1_producers/`, `smd1_prod_config_template.py` |
| `submit_slurm` | `--psana2` | `--psana1` |
| psconda | `conda2/manage/bin/psconda.sh` | `conda1/manage/bin/psconda.sh` |
| detector names | `psana2` `run.detnames` | `detnames exp=<E>:run=<R>` (psana1) |
| SmallData `detnames` | optional | **required** (else the rendered config does not import) |

A DAG with `!branch_daq2` takes the right branch at run time on its own; the config
template does not, so `daq` must be known to render it.

### Walk the operator through — every sub-skill, before rendering

Each sub-skill's *Walk the operator through* section lists what to ask. Do it as **one
exchange**, not an interview:

1. **Required.** Ask every required value in one message, each with the check beside
   it (run it before rendering). Render nothing until they are answered.
2. **Defaults.** Show the `defaults` file's values in one table, each with its comment,
   and ask once: keep, or change which?
3. **Unreviewed.** Whatever the operator did not look at — optional values left out,
   defaults on a hutch that has only `default.yaml` — goes in `unreviewed`.

That one exchange is the whole review: it is not a reason to resolve more facts before
submitting. A value the operator does not know is listed as unreviewed, not chased.

---

## Core Concepts

- **Task** — a unit of analysis; implements `_run()` in `lute/tasks/<name>.py`
- **TaskParameters** — Pydantic model that validates the Task's inputs
- **ManagedTask** — pairs a Task with an Executor; registered in `lute/managed_tasks.py`
- **Executor** — spawns the Task subprocess, handles IPC, reads results
- **YAML config** — two-document file: experiment header + one parameter block per Task,
  keyed by the **Task class name** (not the ManagedTask name)
- **Workflow** — a DAG of ManagedTasks orchestrated by Airflow or Maestro

The flow: `YAML → config.py → TaskParameters → ManagedTask → Executor → Task._run()`

---

## How to Answer Questions

1. **Identify the topic** from the user's question.
2. **Read the matching reference file** from the table below.
3. **Fetch the GitHub file or URL** listed inside that reference if needed.
4. **Return a clear answer** and cite which file/URL you used.

For GitHub/website sources, read [references/reference.md](references/reference.md).
For large GitHub files, fetch the raw file (WebFetch, or `curl` on the
`raw.githubusercontent.com` URL when WebFetch isn't available) and extract only the
relevant section.

### Facts to fetch live, not trust from these references

LUTE changes often. The reference files are a map and a store of hard-won
experience, not a copy of the source. For anything below, fetch the current
file from the LUTE the user actually runs before giving a definitive answer:

- `slac-lcls/lute`, `dev` branch, unless the user's install
  (`git -C <lute_path> remote -v; git -C <lute_path> branch`) says otherwise.

| Fact | Authoritative source |
|---|---|
| Managed Task names ↔ Task class names, `shell_source()` environments | `lute/managed_tasks.py` |
| A Task's parameter fields, defaults, validators | the `class <Task>Parameters` in `lute/io/models/*.py` |
| Command-line entry points | `[project.scripts]` in `pyproject.toml` |
| Workflow backends and shipped DAGs | `workflows/` directory listing |
| Rendered PHIL templates (CCTBX) | `config/templates/cctbx_*.phil` |
| Released versions | `https://api.github.com/repos/slac-lcls/lute/tags` |
| SmallData producer hooks (`get_droplet`, `getROIs`, …) and per-detector common mode | `slac-lcls/smalldata_tools`: `lcls1_producers/smd_producer.py`, `lcls2_producers/smd_producer.py` — a separate repo; the copy that runs is the one cloned into `{{ work_dir }}/smalldata_tools` |
| A SmallData analysis function's kwargs | `smalldata_tools/ana_funcs/*.py` (e.g. `droplet.py`) |

If a fetched source disagrees with a reference file, trust the source, tell the user,
and suggest running `python3 -I scripts/check_upstream.py` to see what else
has drifted.

---

## Reference Navigation

| Topic | Reference file |
|---|---|
| **YAML config** — parameter models, variable substitution, two-document structure, `RUN_GROUPS` per-run policies (0.4.0+dev) | `references/lute-configuration.md` |
| **Result passing** — in_file/out_file, database chaining, `smd_path` auto-population | `references/result-passing.md` |
| **Workflow / DAG** — DAG YAML syntax, `!branch_daq2`, `!run_type` branching, Airflow, Maestro, tasklets | `references/workflow-creation.md` |
| **SLURM submission** — environment setup, psana, Kerberos, running LUTE | `references/slurm-submission.md` |
| **Task creation** — implementation checklist, gotchas, new task walkthrough | `references/task-creation.md` |
| **Task versioning** — VersionSpecifier, lute_cfg utility, DB version tables, reproducibility | `references/lute-versioning.md` |
| **Everything else** — executors, IPC, DB, installation, GitHub URLs | `references/reference.md` |

When in doubt, read `references/reference.md` — it contains the full Topic to File Map
and Website URL Map.
