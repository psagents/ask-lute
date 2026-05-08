# Task Creation

## New Task Implementation Checklist

When implementing a new first-party Task, **five steps** must all be completed or the task
will fail at runtime. Missing any one of them produces a specific error:

| Step | File | What to do | Error if missing |
|---|---|---|---|
| 1 | `lute/tasks/<name>.py` | Create the Task class inheriting from `Task`, implement `_run()` | `AttributeError` / import error |
| 2 | `lute/io/models/<name>.py` | Create the `<Name>Parameters` class inheriting from `TaskParameters` | `KeyError: '<Name>Parameters'` |
| 3 | `lute/io/models/__init__.py` | Add `from .<name> import *` | **`KeyError: '<Name>Parameters'`** ← most common gotcha |
| 4 | `lute/managed_tasks.py` | Add `<Name> : Executor = Executor("<Name>")` | Task not found by `run_task.py` |
| 5 | `config/<name>.yaml` (or your experiment YAML) | Add the header block + `<Name>:` parameter block | `ValidationError` / missing required fields at parse time |

## Key source files

- **Abstract Task base class** (`_run()` pattern, lifecycle, IPC hooks): `lute/tasks/task.py`
- **TaskResult, TaskStatus**: `lute/tasks/dataclasses.py`
- **Base TaskParameters** (Pydantic BaseSettings, `lute_config` field, validators): `lute/io/models/base.py`
- **Managed task catalog**: `lute/managed_tasks.py`
- **SmallData task** (first-party example to copy from): `lute/tasks/smalldata.py`

## Key website URLs

- Overview: `https://slac-lcls.github.io/lute/v0.2.0/development/new_task/overview/`
- First-party task: `https://slac-lcls.github.io/lute/v0.2.0/development/new_task/first_party/`
- Third-party task: `https://slac-lcls.github.io/lute/v0.2.0/development/new_task/third_party/`

---

## Step 3 — most common gotcha

`lute/io/config.py` resolves the parameter class at runtime using `globals()`:
```python
parsed_parameters = globals()[f"{task_name}Parameters"](**lute_config)
```
`globals()` is populated by `from lute.io.models import *`, which runs `lute/io/models/__init__.py`.
If your model file is not listed there, the class is invisible to the config parser:
```
KeyError: 'YourTaskParameters'
```
**Fix:** add `from .yourmodel import *` to `lute/io/models/__init__.py`.

---

## Step 5 — YAML configuration file

LUTE config files are **two-document YAML** (separated by `---`). The first document is the
shared experiment header; the second contains one block per task, keyed by the exact task name.

```yaml
title: My experiment run
experiment: myexp
run: 1
date: "2025/01/01"
lute_version: 0.2.0
task_timeout: 600          # seconds; default 10 min
work_dir: /path/to/work    # required — DB and outputs land here

---

# One block per task; key must match the class name in managed_tasks.py
MyNewTask:
  param_a: 42
  param_b: "some_string"
  # nested sub-parameters
  param_c:
    sub_var: foo
    sub_var2: bar
  # variable substitution — reference header fields or env vars
  output_dir: "{{ work_dir }}/results/{{ experiment }}_{{ run:04d }}"
  raw_dir: "{{ $SDF_DATA_DIR }}/{{ experiment }}"
```

**Key rules:**
- `lute_config` is injected automatically — do **not** add it to the YAML block.
- Use `{{ field }}` for header fields, `{{ $ENV_VAR }}` for shell env vars,
  `{{ OtherTask.param }}` to reference another task's parameter.
- All parameters declared in `<Name>Parameters` with no default are **required** here;
  parameters with defaults can be omitted.
- The reference config is `config/test.yaml` in the repo — use it as a template.

---

## Expected non-fatal errors when running outside LCLS infrastructure

These appear in the log but do **not** affect task results:
- `ERROR: eLog Update Failed! JID_UPDATE_COUNTERS is not defined!` — eLog posting requires
  the LCLS online environment; safe to ignore locally.
- `CRITICAL: Unable to store configuration! … type 'dict' is not supported` — the LUTE
  SQLite DB cannot serialize numpy arrays in the result payload; output `.npy` files are unaffected.
