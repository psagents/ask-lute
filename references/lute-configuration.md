# LUTE Configuration

## Key source files

- **YAML parsing → TaskParameters** (variable substitution, dynamic class loading): `lute/io/config.py`
- **Base TaskParameters class** (Pydantic BaseSettings, `lute_config` field, validators): `lute/io/models/base.py`
- **Shared validators**: `lute/io/models/validators.py`
- **Parameter utilities**: `lute/io/parameters.py`
- **Reference config** (full working example): `config/test.yaml`

## Key website URL

- Task configuration (YAML): `https://slac-lcls.github.io/lute/v0.3.0/usage/configuration/`
- Running LUTE: `https://slac-lcls.github.io/lute/v0.3.0/usage/running_lute/`

---

## YAML file structure

LUTE config files are **two-document YAML** separated by `---`.

### Document 1 — experiment header

```yaml
title: My experiment run
experiment: myexp
run: 1
date: "2025/01/01"
lute_version: 0.3.0
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
| `{{ OtherTask.param }}` | Another task's parameter value **as written in this YAML** |

Example:
```yaml
MyTask:
  output_dir: "{{ work_dir }}/results/{{ experiment }}_{{ run:04d }}"
  raw_dir: "{{ $SDF_DATA_DIR }}/{{ experiment }}"
  peaks_dir: "{{ FindPeaksSFX.outdir }}"   # OK: a static value set in the YAML
```

> **Substitution happens at parse time, before any task runs.** `{{ OtherTask.param }}`
> is only correct for values that are literally set in the YAML (directories, static
> paths). It cannot pass a task's *runtime result* (e.g. `{{ FindPeaksSFX.out_file }}`
> resolves to `""`). For results, omit the field and let database chaining fill it —
> see `result-passing.md`.

---

## `RUN_GROUPS` — per-run parameter policies (0.4.0+dev, not in v0.3.0)

Only on `dev` / the `v0.4.0+dev` nightly (PRs #145, #150). Docs:
`https://slac-lcls.github.io/lute/dev/usage/configuration/` (§`RUN_GROUPS`).
Parser: `resolve_run_group_directives()` in `lute/io/config.py`.

Label sets of runs **globally** (header document), then set **per-Task
policies** for each label:

```yaml
%YAML 1.3
---
experiment: "MYEXP123"
run: "{{ $RUN }}"
work_dir: "/path/to/work_dir"
RUN_GROUPS:
  SAMPLE1:
    applies_to:
      range: [0, 40]          # inclusive
  SAMPLE2:
    applies_to:
      runs: [4, 13, 50]       # explicit list
...
---
SubmitSMD:
  RUN_GROUPS:
    SAMPLE1:
      default: @db:current                          # all params of this Task
      producer_parameters.getROIs.jungfrau: @db:run:10   # dot path into nesting
    SAMPLE2:
      producer_parameters: @literal
  producer_parameters: { ... }   # literal values = final fallback
...
```

| Directive | Value used |
|---|---|
| `@db:current` | Latest value stored in `lute.db` **for the run being processed** (reprocess with the old parameters) |
| `@db:run:NNN` | Latest value stored for **run NNN**, whatever run is being processed |
| `@literal` | The YAML value as written — also the fallback when no DB entry exists |

Conflict rules: a Task sees the union of global and Task-level groups (a group
defined only under one Task is invisible to others — define ranges globally);
Task-level ranges and default policies override global ones; for a run in
several groups the more specific wins (list beats range, narrower range beats
wider). Dot paths reach nested dicts but **not list items** — a list is
replaced whole. Directives may be unquoted (custom SafeLoader). Parameter
sweeps also go through `RUN_GROUPS` resolution (#150).

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
| SmallData | `lute/io/models/smd.py` (~30 KB) |
| SFX peak finding | `lute/io/models/sfx_find_peaks.py` (~12 KB) |
| SFX indexing | `lute/io/models/sfx_index.py` (~30 KB) |
| SFX merging | `lute/io/models/sfx_merge.py` (~24 KB) |
| SFX solving | `lute/io/models/sfx_solve.py` (~8 KB) |
| BayFAI | `lute/io/models/bayfai.py` (~6 KB) |
| Cheetah | `lute/io/models/cheetah.py` (~29 KB) |
| Geometry | `lute/io/models/geometry.py` |
| NeXus | `lute/io/models/nexus.py` |
| XTC | `lute/io/models/xtc.py` |
| MPI tests | `lute/io/models/mpi_tests.py` |
| Tests | `lute/io/models/tests.py` |

---

## SubmitSMD — Producer Parameters and Template Config

`SubmitSMD` uses a **two-layer configuration**: command-line arguments (top-level fields)
and a rendered producer config file (template-based).

### 1. All detector/algorithm config goes under `producer_parameters:`

Every field from `ProducerParameters` (detnames, getROIs, getAzIntPyFAIParams, etc.)
**must** be nested under the `producer_parameters:` key — **not** placed directly under
`SubmitSMD:`. Direct/flat placement bypasses Pydantic validation.

```yaml
SubmitSMD:
  directory: "{{ work_dir }}"
  producer_parameters:           # ← required nesting level
    detnames: ["epix10k2M"]
    getAzIntPyFAIParams:
      epix10k2M:
        poni_file: "/path/to/detector.poni"
        npts: 512
        int_units: "q_A^-1"
```

### 2. `lute_template_cfg` — auto-detected vs explicit

`lute_template_cfg` controls which Jinja2 template is used to render the producer config
file and where it is written:

```python
class TemplateConfig(BaseModel):
    template_name: str   # "smd1_prod_config_template.py" or "smd2_prod_config_template.py"
    output_path: str     # Full path where the rendered config file is written
```

**When psana is available** (standard conda install): both `template_name` and `output_path`
are auto-populated by the `use_producer` validator based on whether psana1 or psana2 is
detected.

**When psana is NOT available** (virtual env install via `setup_lute -fi`): the validator
raises `ValueError`. Both `producer` **and** `lute_template_cfg` **must** be set explicitly:

```yaml
SubmitSMD:
  # Required in virtual env mode (psana not available)
  producer: "{{ work_dir }}/smalldata_tools/lcls2_producers/smd_producer.py"
  lute_template_cfg:
    template_name: "smd2_prod_config_template.py"   # psana2 / LCLS-II
    # template_name: "smd1_prod_config_template.py" # psana1 / LCLS-I
    output_path: "{{ work_dir }}/smalldata_tools/lcls2_producers/prod_config_mfx.py"
  producer_parameters:
    detnames: ["jungfrau"]
    ...
```

**Template names:**
- `smd1_prod_config_template.py` — LCLS-I / psana1 (xtc files)
- `smd2_prod_config_template.py` — LCLS-II / psana2 (xtc2 files)
