# Workflow Creation

**Sections:** [Task vs Managed Task Names](#critical-understanding-task-names-vs-managed-task-names) · [Common Managed Tasks](#common-lute-managed-tasks) · [Result Passing](#critical-result-passing-between-tasks) · [Workflow Checklist](#workflow-creation-checklist) · [Adding a Task](#adding-a-task-to-an-existing-workflow) · [SLURM Submission](#slurm-submission) · [Tasklets](#tasklets)

---

## Key source files

- **Workflow DAG definitions**: `workflows/` directory
  List contents: `https://api.github.com/repos/slac-lcls/lute/contents/workflows`
- **Launch helpers** (Airflow/Maestro submission): `lute/execution/launch.py`
- **Managed task catalog** (tasks available to wire into workflows): `lute/managed_tasks.py`
- **Tasklets** (lightweight pre/post hooks attached to Executors): `lute/tasks/tasklets.py`

## Key website URLs

- Creating a new workflow (overview): `https://slac-lcls.github.io/lute/v0.2.0/development/creating_workflows/`
- Airflow workflows: `https://slac-lcls.github.io/lute/v0.2.0/development/creating_workflows_airflow/`
- Maestro workflows: `https://slac-lcls.github.io/lute/v0.2.0/development/creating_workflows_maestro/`

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
| `SmallDataProducer` | `SubmitSMD` | LCLS smalldata production |

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
