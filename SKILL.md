---
name: ask-lute
description: >
  How to set up a LUTE (LCLS Unified Task Executor) workflow, and the LUTE
  reference behind it. Dispatches to a sub-skill per analysis — BayFAI geometry
  calibration, SmallData (XSS / XAS / XES), CCTBX SFX — each of which returns
  the template, DAGs, trigger, LUTE install and output-log parser a caller needs.
  Triggers on: set up lute, lute config, lute yaml, lute dag, workflow, trigger,
  managed task, executor, result passing, in_file out_file, lute database, task
  creation, lute slurm, run_type branching, lute versioning, bayfai, geometry
  calibration, AgBh, smalldata, SubmitSMD, XSS, XAS, XES, azimuthal integration,
  cctbx, cctbx.xfel, IndexCCTBXXFEL, ScaleCCTBXXFEL, MergeCCTBXXFEL, SFX
  pipeline, d_min, Xtc1Reader, Xtc2Writer, XTC conversion.
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

Every sub-skill answers "set up X for experiment E" with these fields, so a caller
can feed them straight to `hutch-lute render / plan / all`:

| Field | Meaning |
|---|---|
| `template` | Path to one config template. `${{ var }}` is filled at render time; LUTE's own `{{ work_dir }}` / `{{ run:04d }}` pass through untouched. |
| `context` | The `${{ }}` variables the template needs: the sub-skill's `defaults` file (`--context`) plus the operator's answers and resolved values (`--set-context`). |
| `defaults` | `<sub-skill>/defaults/<hutch>.yaml`, else `default.yaml` where the sub-skill has one: the per-hutch knowledge as data, each value with its reason. |
| `sets` | `TASK.BLOCK.KEY=value` overrides on top of the template. |
| `dags` | Each DAG with its workflow name and eLog trigger (`START_OF_RUN`, `END_OF_RUN`, `MANUAL`, `RUN_PARAM_IS_VALUE:<name>:<value>`). A `.dag.j2` is rendered with the same context (`hutch-lute render --no-whitelist`); a `.dag` is copied. |
| `lute` | `release: <version>` — in production; runs from the central build `/sdf/group/lcls/ds/tools/lute/<version>` (`dev` = lute-lcls 0.4.0+dev), pip venvs only if there is none. Or `source: <repo>@<branch>` — not in production, clone and build that branch (needs internet: not from a hutch host). |
| `validate` | Optional command; non-zero exit means the rendered config must not be installed. |
| `unreviewed` | Every parameter left at a default, with the default used. |
| `parse` | Command per output log. Prints JSON facts, never a verdict. |

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

If a fetched source disagrees with a reference file, trust the source, tell the user,
and suggest running `python3 -I scripts/check_upstream.py` to see what else
has drifted.

---

## Reference Navigation

| Topic | Reference file |
|---|---|
| **YAML config** — parameter models, variable substitution, two-document structure | `references/lute-configuration.md` |
| **Result passing** — in_file/out_file, database chaining, `smd_path` auto-population | `references/result-passing.md` |
| **Workflow / DAG** — DAG YAML syntax, `!branch_daq2`, `!run_type` branching, Airflow, Maestro, tasklets | `references/workflow-creation.md` |
| **SLURM submission** — environment setup, psana, Kerberos, running LUTE | `references/slurm-submission.md` |
| **Task creation** — implementation checklist, gotchas, new task walkthrough | `references/task-creation.md` |
| **Task versioning** — VersionSpecifier, lute_cfg utility, DB version tables, reproducibility | `references/lute-versioning.md` |
| **Everything else** — executors, IPC, DB, installation, GitHub URLs | `references/reference.md` |

When in doubt, read `references/reference.md` — it contains the full Topic to File Map
and Website URL Map.
