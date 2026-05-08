# LUTE Configuration

## Key source files

- **YAML parsing → TaskParameters** (variable substitution, dynamic class loading): `lute/io/config.py`
- **Base TaskParameters class** (Pydantic BaseSettings, `lute_config` field, validators): `lute/io/models/base.py`
- **Shared validators**: `lute/io/models/validators.py`
- **Parameter utilities**: `lute/io/parameters.py`
- **Reference config** (full working example): `config/test.yaml`

## Key website URL

- Task configuration (YAML): `https://slac-lcls.github.io/lute/v0.2.0/usage/configuration/`
- Running LUTE: `https://slac-lcls.github.io/lute/v0.2.0/usage/running_lute/`

---

## YAML file structure

LUTE config files are **two-document YAML** separated by `---`.

### Document 1 — experiment header

```yaml
title: My experiment run
experiment: myexp
run: 1
date: "2025/01/01"
lute_version: 0.2.0
task_timeout: 600       # seconds; default 10 min
work_dir: /path/to/work # required — DB and outputs land here
```

### Document 2 — per-task parameter blocks

```yaml
---
# Key must match the exact class name registered in managed_tasks.py
MyTask:
  param_a: 42
  param_b: "some_string"
  nested:
    sub_var: foo

AnotherTask:
  input_file: "/data/myfile.h5"
```

---

## Variable substitution

Substitutions use double-brace notation `{{ ... }}`:

| Syntax | Resolves to |
|---|---|
| `{{ experiment }}` | Header field |
| `{{ run:04d }}` | Header field with format spec |
| `{{ $SDF_DATA_DIR }}` | Shell environment variable |
| `{{ OtherTask.param }}` | Another task's parameter value |

Example:
```yaml
MyTask:
  output_dir: "{{ work_dir }}/results/{{ experiment }}_{{ run:04d }}"
  raw_dir: "{{ $SDF_DATA_DIR }}/{{ experiment }}"
  ref_geom: "{{ FindGeometry.output_file }}"
```

---

## TaskParameters model (Pydantic)

Each task has a corresponding `<Name>Parameters` class in `lute/io/models/<name>.py`:

```python
from lute.io.models.base import TaskParameters

class MyTaskParameters(TaskParameters):
    param_a: int               # required — must appear in YAML
    param_b: str = "default"   # optional — YAML can omit it
    nested: MySubModel = MySubModel()
```

- `lute_config` is a reserved field injected automatically — do **not** declare or set it.
- Pydantic validators in `lute/io/models/validators.py` are reusable across models.
- The config parser resolves the class via `globals()[f"{task_name}Parameters"]`, which
  requires the model to be exported from `lute/io/models/__init__.py`.

---

## Parameter model files by domain

| Domain | File |
|---|---|
| SmallData | `lute/io/models/smd.py` (~27 KB) |
| SFX peak finding | `lute/io/models/sfx_find_peaks.py` (~12 KB) |
| SFX indexing | `lute/io/models/sfx_index.py` (~30 KB) |
| SFX merging | `lute/io/models/sfx_merge.py` (~24 KB) |
| SFX solving | `lute/io/models/sfx_solve.py` |
| BayFAI | `lute/io/models/bayfai.py` |
| Geometry | `lute/io/models/geometry.py` |
| NeXus | `lute/io/models/nexus.py` |
| XTC | `lute/io/models/xtc.py` |
| Tests | `lute/io/models/tests.py` |
