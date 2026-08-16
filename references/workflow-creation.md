# Workflow Creation

**Sections:** [Task vs Managed Task Names](#critical-understanding-task-names-vs-managed-task-names) · [Common Managed Tasks](#common-lute-managed-tasks) · [Result Passing](#critical-result-passing-between-tasks) · [DAG Branching](#dag-branching) · [Workflow Checklist](#workflow-creation-checklist) · [Adding a Task](#adding-a-task-to-an-existing-workflow) · [SLURM Submission](#slurm-submission) · [Tasklets](#tasklets)

---

## Key source files

- **Workflow DAG definitions**: `workflows/` directory
  List contents: `https://api.github.com/repos/slac-lcls/lute/contents/workflows`
- **Launch helpers** (Airflow/Maestro submission): `lute/execution/launch.py`
- **Managed task catalog** (tasks available to wire into workflows): `lute/managed_tasks.py`
- **Tasklets** (lightweight pre/post hooks attached to Executors): `lute/tasks/tasklets.py`
- **DAG parser** (incl. `!branch_daq2` and `!run_type` branching logic): `lute/io/config.py`

## Key website URLs

- Creating a new workflow (overview): `https://slac-lcls.github.io/lute/v0.3.0/development/creating_workflows/`
- Airflow workflows: `https://slac-lcls.github.io/lute/v0.3.0/development/creating_workflows_airflow/`
- Maestro workflows: `https://slac-lcls.github.io/lute/v0.3.0/development/creating_workflows_maestro/`
- Dynamic run-time workflows (run_type branching): `https://slac-lcls.github.io/lute/v0.3.0/development/dynamic_workflows/`

---

## Overview

LUTE workflows are DAGs that chain ManagedTasks together. Two orchestration backends
are supported:

- **Airflow** — tasks become Airflow operators; the DAG is defined in Python
- **Maestro** — tasks are described in a Maestro step file (YAML-based)

Both backends rely on `lute/execution/launch.py` to submit tasks to the batch system.

---

## CRITICAL: Understanding Task Names vs Managed Task Names

**LUTE has two different naming systems** that must be used correctly:

### 1. Task Class Name (used in YAML config)
- Defined in `lute/tasks/<name>.py` 
- Example: `FindPeaksSFX` (the Python class name)
- This is what you use as the **top-level key** in the YAML config file
- Example in YAML: `FindPeaksSFX:` followed by parameters

### 2. Managed Task Name (used in workflow DAG files)
- Defined in `lute/managed_tasks.py`
- Example: `PeakFinderSFX` (the variable name assigned to the Executor)
- This is what you use in the **workflow DAG** `task_name` field
- Example in DAG: `task_name: "PeakFinderSFX"`

### How to Find the Correct Names

**ALWAYS fetch and read `lute/managed_tasks.py` from the LUTE repository** to get the authoritative mapping:

```python
# Example from managed_tasks.py:
PeakFinderSFX: MPIExecutor = MPIExecutor("FindPeaksSFX")
#              └─────────┘                └──────────┘
#              Managed Task Name          Task Class Name
#              (use in DAG file)          (use in YAML config)
```

**Common mistakes to avoid:**
- ❌ Using `FindPeaksPyAlgos` - this doesn't exist
- ❌ Using Task class names in the DAG file
- ❌ Using Managed Task names in the YAML config
- ❌ Guessing names without checking `managed_tasks.py`

### Complete Example of Correct Naming

**In workflow DAG file (e.g., `sfx_workflow.dag`):**
```yaml
!LUTE_DAG
task_name: "PeakFinderSFX"  # ← Managed Task name from managed_tasks.py
slurm_params: "--ntasks=2 --cpus-per-task=4"
next:
  - task_name: "CrystFELIndexer"  # ← Another Managed Task name
    next: []
```

**In YAML config file (e.g., `experiment_config.yaml`):**
```yaml
---
FindPeaksSFX:  # ← Task class name (what FindPeaksSFX class is called in lute/tasks/)
  algorithm: "Peakfinder8"
  outdir: "/path/to/output"
  # ... other parameters

IndexCrystFEL:  # ← Task class name (what IndexCrystFEL class is called)
  in_file: "{{ FindPeaksSFX.out_file }}"  # ← Reference Task class name
  geometry: "/path/to/geometry.geom"
```

**Variable substitution in YAML** also uses Task class names:
```yaml
IndexCrystFEL:
  in_file: "{{ FindPeaksSFX.out_file }}"  # ← Use Task class name, not Managed Task name
```

---

## Common LUTE Managed Tasks

When creating workflows, **always verify names in `managed_tasks.py`**, but here are common examples:

| Managed Task Name | Task Class Name | Purpose |
|-------------------|-----------------|---------|
| `PeakFinderSFX` | `FindPeaksSFX` | Bragg peak finding (PyAlgos/Peakfinder8) |
| `CrystFELIndexer` | `IndexCrystFEL` | CrystFEL indexing |
| `PartialatorMerger` | `MergePartialator` | CrystFEL merging |
| `HKLComparer` | `CompareHKL` | Merge statistics |
| `CCTBXIndexer` | `IndexCCTBXXFEL` | CCTBX indexing |
| `CCTBXScaler` | `ScaleCCTBXXFEL` | CCTBX scaling-only step (new in v0.3.0) |
| `CCTBXMerger` | `MergeCCTBXXFEL` | CCTBX merging |
| `SmallDataProducer` | `SubmitSMD` | LCLS-I smalldata production |
| `SmallDataProducer2` | `SubmitSMD` | LCLS-II smalldata production (psana2) |
| `BayFAIOptimizer` | `OptimizeBayFAI` | BayFAI geometry optimization (psana1) |
| `BayFAIOptimizer2` | `OptimizeBayFAI` | BayFAI geometry optimization (psana2) |
| `Xtc1Reader` | `ReadXtc1` | XTC1→XTC2 conversion reader (new in v0.3.0) |
| `Xtc2Writer` | `WriteXtc2` | XTC1→XTC2 conversion writer (new in v0.3.0) |

**This table is for reference only. Always fetch the current `managed_tasks.py` to get up-to-date names.**

---

## CRITICAL: Result Passing Between Tasks

**Most workflow parameters do NOT need explicit `in_file` specifications!**

LUTE uses **automatic database-based result chaining**. When a task completes, its results are stored in the database. Subsequent tasks automatically retrieve the most recent valid result via Pydantic validators.

### The Golden Rule for in_file/out_file

**DON'T specify `in_file` in YAML configs for standard workflows** - let the validators handle it automatically!

**Example - CORRECT approach:**
```yaml
FindPeaksSFX:
  algorithm: "Peakfinder8"
  outdir: "{{ work_dir }}/peaks"
  # out_file auto-generated and stored in database

IndexCrystFEL:
  # ✓ in_file OMITTED - validator queries database automatically
  geometry: "/path/to/geometry.geom"

MergePartialator:
  # ✓ in_file OMITTED - validator queries database automatically
  symmetry: "mmm"
```

**Example - WRONG approach:**
```yaml
FindPeaksSFX:
  outdir: "{{ work_dir }}/peaks"

IndexCrystFEL:
  in_file: "{{ FindPeaksSFX.out_file }}"  # ❌ WRONG! This won't work!
```

**Why this fails:**
- `{{ }}` substitution happens at YAML parse time
- At parse time, `FindPeaksSFX.out_file` is just a parameter (often `""`)
- The task hasn't run yet, so no actual file path exists
- You end up with `in_file: ""` (empty string)

**For complete details, see:** [references/result-passing.md](references/result-passing.md)

---

## DAG Branching

LUTE supports two kinds of run-time branching inside a single workflow DAG.
Both are triggered by special YAML tags in the DAG file.

### Type 1 — `!branch_<key>` (DAQ generation / arbitrary condition)

The `!branch_<key>` YAML tag splits the DAG based on a key that is resolved at
launch time (typically `daq2` vs `daq1`, determined by whether `.xtc2` or `.xtc` files
are present). **Only the matching branch runs.** This branching is mutually exclusive.

```yaml
!LUTE_DAG
- !branch_daq2
  daq2:
    task_name: SmallDataProducer2
    slurm_params: "--nodes=2 --ntasks-per-node=50 --partition=milano --account=lcls:..."
    next: []
  daq1:
    task_name: SmallDataProducer
    slurm_params: "--nodes=2 --ntasks-per-node=50 --partition=milano --account=lcls:..."
    next: []
```

### Type 2 — `!run_type` (new in v0.3.0)

The `!run_type` tag branches based on the `run_type` field read from the eLog for the
current run. This is **additive** — all matching branches run in parallel.

**Match rules:**
- **Exact match**: key `DATA` runs only when `run_type == "DATA"`
- **Negative match**: key `NOT_DARK` runs whenever `run_type != "DARK"`
- **No match**: the `!run_type` node is skipped (nothing downstream runs from it)
- An unknown key that never exactly matches is still tested for `NOT_*` negative patterns

**CLI override (for testing):**
```bash
submit_launch_slurm.sh launch_slurm -c config.yaml -W workflow.dag \
  --type GEOM -e mfx100852324 -r 298 --partition=milano --account=lcls:...
```
Pass `--type <VALUE>` to override the eLog `run_type` without writing to the log.

**Full example — combining `!branch_daq2` and `!run_type`:**

```yaml
!LUTE_DAG
- !branch_daq2
  daq2:
    task_name: SmallDataProducer2
    slurm_params: "--nodes=2 --ntasks-per-node=50 --partition=milano --account=lcls:..."
    next:
      - !run_type
        DATA:
          task_name: SmallDataXSSAnalyzer
          slurm_params: "--partition=milano --account=lcls:..."
          next: []
        GEOM:
          task_name: BayFAIOptimizer2
          slurm_params: "--nodes=2 --ntasks-per-node=50 --partition=milano --account=lcls:..."
          next: []
        NOT_DARK:
          task_name: SmallDataXESAnalyzer
          slurm_params: "--partition=milano --account=lcls:..."
          next: []
  daq1:
    task_name: SmallDataProducer
    slurm_params: "--nodes=2 --ntasks-per-node=50 --partition=milano --account=lcls:..."
    next:
      - !run_type
        DATA:
          task_name: SmallDataXSSAnalyzer
          slurm_params: "--partition=milano --account=lcls:..."
          next: []
        GEOM:
          task_name: BayFAIOptimizer
          slurm_params: "--nodes=2 --ntasks-per-node=50 --partition=milano --account=lcls:..."
          next: []
        NOT_DARK:
          task_name: SmallDataXESAnalyzer
          slurm_params: "--partition=milano --account=lcls:..."
          next: []
```

**Behaviour table for the `!run_type` block above:**

| `run_type` value | GEOM branch | DATA branch | NOT_DARK branch |
|---|---|---|---|
| `GEOM` | runs | skipped | runs (not DARK) |
| `DATA` | skipped | runs | runs (not DARK) |
| `DARK` | skipped | skipped | skipped |
| `FAKE` (unknown) | skipped | skipped | runs (not DARK) |

> Source: PR #134. Implementation: `lute/io/config.py` (parser logic).
> Full docs: `https://slac-lcls.github.io/lute/v0.3.0/development/dynamic_workflows/`

---

## Parallel tasks in a DAG

The `next` field is a list — all tasks in the list are submitted in parallel.
This also applies when two tasks must run simultaneously (e.g., XTC1→XTC2 conversion):

```yaml
!LUTE_DAG
- task_name: "Xtc1Reader"
  slurm_params: "--nodes=1 --tasks-per-node=11 --partition=milano --account=lcls:<EXP>"
  next: []
- task_name: "Xtc2Writer"
  slurm_params: "--nodes=1 --tasks-per-node=11 --partition=milano --account=lcls:<EXP>"
  next: []
```

> **XTC1→XTC2 note:** `Xtc1Reader` and `Xtc2Writer` **must** have identical `ntasks-per-node`.
> They coordinate peer-to-peer via ZMQ — see `references/reference.md` for the XTC conversion doc URL.

---

## Workflow Creation Checklist

When creating a new workflow:

1. **Fetch `managed_tasks.py`** from GitHub:
   ```
   https://raw.githubusercontent.com/slac-lcls/lute/dev/lute/managed_tasks.py
   ```

2. **Identify Managed Task names** for your workflow DAG:
   - Look for variable assignments like `TaskName: Executor = Executor("...")`
   - The variable name (left side) is the Managed Task name
   - Use these in your DAG file's `task_name:` fields

3. **Identify Task class names** for your YAML config:
   - Look at the string argument to `Executor(...)` or `MPIExecutor(...)`
   - This is the Task class name
   - Use these as top-level keys in your YAML config

4. **Create the workflow DAG** with correct Managed Task names

5. **Create the YAML config** with correct Task class names:
   - **OMIT `in_file` parameters** - let validators auto-retrieve from database
   - Only specify `in_file` if debugging or using external files
   - Use `{{ }}` substitution ONLY for static values (experiment, run, work_dir)
   - **NEVER use `{{ TaskName.out_file }}`** for result chaining

6. **Understand result passing** - read [result-passing.md](result-passing.md)

7. **Create and submit the SLURM submission script** — see [slurm-submission.md](slurm-submission.md) for the full environment setup (LUTE install, build, psana sourcing, Kerberos ticket) and the `.sh` template

---

## SLURM Submission

For the complete guide to creating and executing the `.sh` submission script, see **[slurm-submission.md](slurm-submission.md)**. It covers:
- Installing/locating LUTE
- Running `./build.sh -e` to install entry points
- Sourcing psana1/psana2 Python environments
- Storing a Kerberos ticket to a persistent file so Claude can access it
- The full `.sh` template for single-task and full-DAG submission

---

## Adding a task to an existing workflow

1. **Fetch `managed_tasks.py`** to verify the task is registered and get its names
2. In the workflow DAG file (under `workflows/`), reference the **Managed Task name**
3. Wire up dependencies (upstream/downstream) using the orchestrator's API
4. Add the task's parameter block to the experiment YAML config using the **Task class name**

## Tasklets

Tasklets are lightweight callables attached to an Executor that run before or after the
main Task without spawning a new process. To add one:

1. Define the callable in `lute/tasks/tasklets.py`.
2. Attach it in `lute/managed_tasks.py` via `ManagedTask(..., tasklets=[...])`.

---

## Managed Task Environment Sourcing

All managed tasks in `lute/managed_tasks.py` now have **explicit `shell_source()` calls**
that source the correct psana environment before the task subprocess runs. This is required
when using the virtual-env installation (`setup_lute -fi`), where psana is not in the LUTE
venv and must be injected from the LCLS conda stacks.

**Per-task sourcing rules (as of PR #132):**

| Managed Task(s) | Sourced environment | Notes |
|---|---|---|
| `SmallDataProducer` | `conda1/manage/bin/psconda.sh` | LCLS-I (psana1, Python 3.9) |
| `AgBhGeometryOptimizer` | `conda1/manage/bin/psconda.sh` | LCLS-I (psana1, Python 3.9) |
| `BayFAIOptimizer` | `conda1/manage/bin/psconda.sh` | LCLS-I (psana1, Python 3.9) |
| `PeakFinderPsocake` | `conda1/manage/bin/psconda.sh` | LCLS-I (deprecated, psana1) |
| `Xtc1Reader` | `conda1/manage/bin/psconda.sh` | LCLS-I (psana1, Python 3.9) |
| All other managed tasks | `conda2/manage/bin/psconda.sh` | LCLS-II (psana2, Python 3.9) |

**Why this matters for workflow creation:**
- Always fetch the current `managed_tasks.py` to verify which environment a task sources.
- When adding a new managed task, add an explicit `shell_source()` call pointing to the
  appropriate conda environment.
- The executor uses `LUTE_NEW_PYVER` set in the venv activate script to switch Python
  interpreter versions for tasks that need Python 3.11 (e.g. `PeakFinderSFXXpp`).
