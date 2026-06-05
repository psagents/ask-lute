# SLURM Submission Setup

## Key source files

- **Entry points** (submit_slurm, run_task): installed by `./build.sh -e` from `pyproject.toml`
- **Workflow launch helper**: `lute/execution/launch.py`
- **Build script**: `build.sh`

## Key website URLs

- Installing LUTE: `https://slac-lcls.github.io/lute/v0.2.0/usage/installation/`
- Running LUTE / SLURM submission: `https://slac-lcls.github.io/lute/v0.2.0/usage/running_lute/`
- Quick start: `https://slac-lcls.github.io/lute/v0.2.0/quick_start/`

---

## Overview

After creating a workflow DAG and YAML config, submitting to SLURM requires:
1. LUTE installed and its environment built
2. A compatible Python environment (psana1 or psana2) sourced
3. The LUTE virtual environment activated
4. A valid Kerberos ticket stored in a persistent file

The entry points `submit_slurm` (single task) and `launch_slurm` (full DAG) are installed by `./build.sh -e` and handle SLURM submission.

---

## CRITICAL: Kerberos Ticket Setup (do this first)

Claude's terminal session **cannot see** a Kerberos ticket you create in your own interactive shell. To make it accessible to both the `.sh` script and Claude when it executes it:

**User runs once per day (in their own terminal):**
```bash
kinit -c FILE:$HOME/krb5cc.ticket <username>@SLAC.STANFORD.EDU
```

This writes the ticket to `$HOME/krb5cc.ticket`. The `FILE:` prefix is required — it tells MIT Kerberos to use a file-based credential cache at that exact path.

**The `.sh` script then references it with:**
```bash
export KRB5CCNAME=FILE:${HOME}/krb5cc.ticket
```

The `FILE:` prefix must match between `kinit -c` and `KRB5CCNAME` so that `klist` and data-access tools read from the same cache file.

**Before creating or running the script**, the skill checks whether `$HOME/krb5cc.ticket` exists. If absent, it prompts:
> "No Kerberos ticket file found at `$HOME/krb5cc.ticket`. Please run the following in your terminal, then retry:
> `kinit -c FILE:$HOME/krb5cc.ticket <username>@SLAC.STANFORD.EDU`"

---

## Step 1 — Install / Locate LUTE

Check if LUTE is already available:
```bash
which submit_slurm 2>/dev/null || echo "LUTE not in PATH"
```

If not installed, clone to your home directory:
```bash
git clone https://github.com/slac-lcls/lute.git ~/lute
```

> If LUTE is available at a shared group path (e.g. `/sdf/group/lcls/...`), use that path instead of cloning.

---

## Step 2 — Build the LUTE Environment

Run the build script once (or after major LUTE updates):
```bash
cd ~/lute     # or the path where LUTE is installed
./build.sh -e
```

This installs the Python entry points (`submit_slurm`, `run_task`, `launch_slurm`, etc.) into a virtual environment.

---

## Step 3 — Source Python Environment (psana1 or psana2)

Check your current Python version first:
```bash
python --version
```

**psana2 (Python 3.9, recommended):**
```bash
source /sdf/group/lcls/ds/ana/sw/conda2/manage/bin/psconda.sh
```

**psana1 (Python 3.9):**
```bash
source /sdf/group/lcls/ds/ana/sw/conda1/manage/bin/psconda.sh
```

Source this **before** activating the LUTE environment.

---

## Step 4 — Activate LUTE Environment

After `./build.sh -e`, LUTE creates a virtual environment at:
```
~/.cache/lute_build_env_<MD5_OF_LUTE_DIR>_<PYVER>/bin/activate
```

The path is deterministic (MD5 hash of the LUTE installation directory + Python version). See `BUILD_ENV` in `build.sh` for the exact formula:
```
https://raw.githubusercontent.com/slac-lcls/lute/dev/build.sh
```

**Practical activation (if only one LUTE env exists):**
```bash
source $(ls ~/.cache/lute_build_env_*/bin/activate | head -1)
```

---

## Step 5 — Create and Execute the `.sh` Submission Script

The skill **creates the `.sh` file, makes it executable, and runs it**.

### Submitting a full workflow (DAG)

```bash
#!/bin/bash
#SBATCH --partition=milano
#SBATCH --account=lcls:<experiment>
#SBATCH --nodes=1
#SBATCH --ntasks=<N>
#SBATCH --time=<HH:MM:SS>
#SBATCH --output=<log_dir>/%j.log

# Kerberos ticket (must exist at $HOME/krb5cc.ticket — see CRITICAL section above)
export KRB5CCNAME=FILE:${HOME}/krb5cc.ticket
klist || { echo "ERROR: Kerberos ticket missing or expired. Run: kinit -c FILE:\$HOME/krb5cc.ticket <user>@SLAC.STANFORD.EDU"; exit 1; }

# Source Python environment (psana2 — Python 3.11)
source /sdf/group/lcls/ds/ana/sw/conda1/manage/bin/psconda.sh
# Alternative psana1 (Python 3.9): <command TBD>

# Activate LUTE environment
source $(ls ~/.cache/lute_build_env_*/bin/activate | head -1)

# Submit full workflow DAG
submit_launch_slurm.sh <LUTE_DIR>/bin/launch_slurm \
  -c <path/to/experiment_config.yaml> \
  -W <path/to/workflow.dag> \
  -e <EXPERIMENT> \
  -r <RUN>
```

### Submitting a single task

```bash
submit_slurm \
  -t <ManagedTaskName> \
  -c <path/to/experiment_config.yaml> \
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
3. Run with: `bash ~/submit_<workflow>.sh` (for dry-run/debug) or `sbatch ~/submit_<workflow>.sh`
