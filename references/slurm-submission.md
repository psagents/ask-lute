# SLURM Submission Setup

## Key source files

- **`setup_lute` utility** (primary experiment setup tool): `utilities/setup/setup_lute.py`
- **Entry points** (submit_slurm, run_task, launch_slurm, setup_lute): installed via `pyproject.toml`
- **Workflow launch helper**: `lute/execution/launch.py`
- **Build script**: `build.sh`
- **Submission shell scripts**: `launch_scripts/submit_slurm.sh`, `launch_scripts/submit_launch_slurm.sh`

## Key website URLs

- Installing LUTE: `https://slac-lcls.github.io/lute/v0.2.0/usage/installation/`
- Running LUTE / SLURM submission: `https://slac-lcls.github.io/lute/v0.2.0/usage/running_lute/`
- Quick start: `https://slac-lcls.github.io/lute/v0.2.0/quick_start/`

---

## Overview

The recommended way to set up LUTE for an experiment is the **`setup_lute` command**. It
handles creating environments, copying configs, and registering eLog workflows in one step.
Manual SLURM script creation is only needed for advanced or non-standard use cases.

---

## CRITICAL: Kerberos Ticket Setup (do this first)

Claude's terminal session **cannot see** a Kerberos ticket you create in your own interactive shell. To make it accessible to both the `.sh` script and Claude when it executes it:

**User runs once per day (in their own terminal):**
```bash
kinit -c FILE:$HOME/krb5cc.ticket <username>@SLAC.STANFORD.EDU
```

This writes the ticket to `$HOME/krb5cc.ticket`. The `FILE:` prefix is required.

**The `.sh` script then references it with:**
```bash
export KRB5CCNAME=FILE:${HOME}/krb5cc.ticket
```

**Before creating or running the script**, check whether `$HOME/krb5cc.ticket` exists. If absent, prompt:
> "No Kerberos ticket file found at `$HOME/krb5cc.ticket`. Please run the following in your terminal, then retry:
> `kinit -c FILE:$HOME/krb5cc.ticket <username>@SLAC.STANFORD.EDU`"

---

## Recommended: `setup_lute` Command

`setup_lute` is the primary tool for setting up LUTE for an experiment. It:
1. Creates virtual environments (or clones/uses a shared installation)
2. Copies the hutch-specific YAML config and populates `work_dir`
3. Copies workflow DAG files and updates their SLURM parameters
4. Registers eLog workflows via the LCLS REST API

### Prerequisites

`setup_lute` itself must be available. Activate a LUTE installation that provides it:

```bash
# Option A: use the central shared installation
source /sdf/group/lcls/ds/tools/lute/dev/lute/install/bin/activate_installation

# Option B: activate a local build (after ./build.sh -e)
source /path/to/lute/install/bin/activate_installation
```

### Running `setup_lute`

```bash
setup_lute -e <EXPERIMENT> [MODE] [-W WORKFLOW...] [SLURM OPTS]
```

**Arguments:**

| Argument | Description |
|---|---|
| `-e <EXP>` | Experiment name, e.g. `mfxl1013621` (required) |
| `-fi` / `--fresh_install` | **Recommended.** Create isolated virtual envs via `pip install lute-lcls` |
| `-fb` / `--fresh_build` | Clone repo + run `./build.sh -e -r` (for code modifications) |
| *(no mode flag)* | Use central installation at `/sdf/group/lcls/ds/tools/lute/{version}/lute` |
| `-D <subdir>` | Subdirectory under `{exp}/results/` for LUTE output (optional) |
| `-v <version>` | LUTE version tag or `dev` (default: `dev`) |
| `-W <wf1> [wf2...]` | Workflow names to set up (default: `smd`). E.g. `-W smd bayfai` |
| `--partition=<P>` | SLURM partition (default: `milano`) |
| `--account=<A>` | SLURM account (default: `lcls:<experiment>`) |
| `--nodes=<N>` | SLURM nodes (default: 1) |
| `--ntasks=<N>` | SLURM ntasks (default: 1) |

**Example — fresh virtual env install, SMD + BayFAI workflows:**
```bash
source /sdf/group/lcls/ds/tools/lute/dev/lute/install/bin/activate_installation
setup_lute -e mfxl1013621 -fi -W smd bayfai \
  --partition=milano --account=lcls:mfxl1013621 \
  --nodes=4 --ntasks-per-node=50
```

### What `setup_lute` creates

Given `-fi` (fresh_install) and `-D lute_output`, `setup_lute` creates:

```
/sdf/data/lcls/ds/<hutch>/<exp>/results/
├── lute_envs/
│   ├── lute_env_py39/      ← Python 3.9 virtual env with lute-lcls installed
│   └── lute_env_py311/     ← Python 3.11 virtual env with lute-lcls installed
└── lute_output/
    ├── <hutch>_lute.yaml   ← LUTE config (work_dir pre-populated)
    ├── lute.db             ← SQLite database (created empty)
    ├── smd.dag             ← Workflow DAG (slurm_params pre-populated)
    └── bayfai.dag          ← (if -W bayfai specified)
```

---

## Installation Modes

### Mode 1: Fresh Virtual Env Install (`-fi`) — Recommended

Creates isolated Python virtual environments via `pip install lute-lcls`. Resolves
environment leakage and permissions issues.

**Python interpreters used:**

| Version | Interpreter path |
|---|---|
| Python 3.9 | `/sdf/group/lcls/ds/ana/sw/conda2/inst/bin/python3.9` |
| Python 3.11 | `/sdf/group/lcls/ds/ana/sw/conda2-v3/inst/bin/python3.11` |

**Virtual env naming convention:** `lute_env_py{MAJORMINOR}` (e.g. `lute_env_py39`, `lute_env_py311`).

**Environment variables set by submission scripts** when `bin/activate` is detected:

| Variable | Value |
|---|---|
| `LUTE_VIRTUAL_ENV` | Path to primary lute venv (e.g. `.../lute_env_py39`) |
| `LUTE_VIRTUAL_ENV_PY39` | Path to Python 3.9 executable in the venv |
| `LUTE_VIRTUAL_ENV_PY311` | Path to Python 3.11 executable in the venv |

The executor uses `LUTE_VIRTUAL_ENV_PY{VERSION}` to switch Python interpreters when a
task declares `LUTE_NEW_PYVER` (e.g. a task requiring Python 3.11 for compressed data).

**Important:** In virtual env mode, `psana` is **not** installed in the venv. Tasks that
need psana are sourced separately via `managed_tasks.py` `shell_source()` calls. For
`SubmitSMD`, this means `producer` and `lute_template_cfg` must be specified explicitly
in the YAML config — see `references/lute-configuration.md`.

### Mode 2: Fresh Build (`-fb`)

Clones the repo to `{results}/lute/` and runs `./build.sh -e -r`. Use when local code
modifications are needed.

```bash
setup_lute -e mfxl1013621 -fb -W smd
```

Produces a meson/prefix installation at `{results}/lute/install/`.

### Mode 3: Central Install (no mode flag)

Uses the shared installation at `/sdf/group/lcls/ds/tools/lute/{version}/lute`.
No cloning or pip install is done. Suitable when no customization is needed.

---

## Manual SLURM Submission (Advanced)

For cases where `setup_lute` cannot be used, you can manually create and execute
a submission script.

### Step 1 — Activate LUTE environment

**Virtual env install:**
```bash
# Source the primary venv
source /path/to/lute_envs/lute_env_py39/bin/activate
export LUTE_VIRTUAL_ENV="/path/to/lute_envs/lute_env_py39"
export LUTE_VIRTUAL_ENV_PY39="/path/to/lute_envs/lute_env_py39/bin/python"
export LUTE_VIRTUAL_ENV_PY311="/path/to/lute_envs/lute_env_py311/bin/python"
```

**Meson/prefix install (build.sh):**
```bash
source /path/to/lute/install/bin/activate_installation
```

`activate_installation` sets `PYTHONPATH` and `PATH` to include the LUTE `install/` prefix.

### Step 2 — Source Python environment (psana)

Tasks that need psana source it automatically via `managed_tasks.py` `shell_source()`.
However, `submit_slurm` itself needs to be callable:

```bash
# psana2 (Python 3.9 — default for most tasks)
source /sdf/group/lcls/ds/ana/sw/conda2/manage/bin/psconda.sh

# psana1 (Python 3.9 — for LCLS-I data)
source /sdf/group/lcls/ds/ana/sw/conda1/manage/bin/psconda.sh
```

### Step 3 — Submission script template

#### Submitting a full workflow (DAG)

```bash
#!/bin/bash
export KRB5CCNAME=FILE:${HOME}/krb5cc.ticket
klist || { echo "ERROR: Kerberos ticket missing or expired."; exit 1; }

# Activate environment (choose one)
source /path/to/lute_envs/lute_env_py39/bin/activate   # virtual env
# OR: source /path/to/lute/install/bin/activate_installation  # meson/prefix

submit_launch_slurm.sh launch_slurm \
  -c /path/to/<hutch>_lute.yaml \
  -W /path/to/workflow.dag \
  -e <EXPERIMENT> \
  -r <RUN>
```

#### Submitting a single task

```bash
submit_slurm \
  -t <ManagedTaskName> \
  -c /path/to/<hutch>_lute.yaml \
  -e <EXPERIMENT> \
  -r <RUN> \
  --partition=milano \
  --account=lcls:<experiment> \
  --ntasks=<N>
```

### Skill execution steps

After generating the script content:
1. Write to file: e.g. `~/submit_<workflow>.sh`
2. Make executable: `chmod +x ~/submit_<workflow>.sh`
3. Run with: `bash ~/submit_<workflow>.sh` (dry-run/debug) or `sbatch ~/submit_<workflow>.sh`
