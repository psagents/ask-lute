# Reference — Full Topic & URL Maps

## How to fetch files from GitHub

- **List a directory**: `https://api.github.com/repos/slac-lcls/lute/contents/<PATH>`
- **Read a file**: fetch the `download_url` returned above
  (format: `https://raw.githubusercontent.com/slac-lcls/lute/dev/<PATH>`)
- Or fetch raw files directly if the path is known:
  `https://raw.githubusercontent.com/slac-lcls/lute/dev/<PATH>`

> If a website URL returns 404, fall back to reading the raw file from GitHub directly.

---

## Topic to File Map

### Architecture & high-level design
- **Overview / README**: `README.md`
- **Entry point for running a task**: `run_task.py`
- **Subprocess task handler**: `subprocess_task.py`

### Tasks (analysis units)
- **Abstract Task base class** (lifecycle, IPC hooks, `_run()` pattern): `lute/tasks/task.py`
- **TaskResult, TaskStatus dataclasses**: `lute/tasks/dataclasses.py`
- **Tasklets** (lightweight pre/post hooks attached to Executors): `lute/tasks/tasklets.py`
- **SmallData task** (first-party example): `lute/tasks/smalldata.py`
- **SFX peak finding**: `lute/tasks/sfx_find_peaks.py`
- **SFX indexing**: `lute/tasks/sfx_index.py`
- **BayFAI**: `lute/tasks/bayfai.py`
- **Geometry**: `lute/tasks/geometry.py`
- **XTC conversion** (ReadXtc1 / WriteXtc2 parallel tasks — replaces old ConvertXtc1to2): `lute/tasks/xtc1.py`, `lute/tasks/xtc2.py`
- **SFX scaling** (ScaleCCTBXXFEL — new in v0.3.0): `lute/io/models/sfx_merge.py`
- **Math utilities**: `lute/tasks/math.py`
- **Test tasks**: `lute/tasks/test.py`
- **MPI test tasks**: `lute/tasks/mpi_test.py`

### Executors (process management)
- **All executor classes** (BaseExecutor / Executor / MPIExecutor, process spawning,
  CPU affinity, result hooks): `lute/execution/executor.py` (~68 KB, large file)
- **IPC system** (PipeCommunicator, SocketCommunicator, signals, message types):
  `lute/execution/ipc.py` (~42 KB)
- **Launch helpers** (Airflow/Maestro submission): `lute/execution/launch.py`
- **Logging setup**: `lute/execution/logging.py`
- **Subprocess utilities**: `lute/execution/subprocess_utils.py`
- **Debug utilities**: `lute/execution/debug_utils.py`

### Managed Tasks
- **Full catalog**: `lute/managed_tasks.py`

### Configuration & Parameters
- **YAML parsing** (incl. `!branch_daq2` and `!run_type` branching logic): `lute/io/config.py`
- **Parameter utilities**: `lute/io/parameters.py`
- **Base TaskParameters class**: `lute/io/models/base.py`
- **Shared validators**: `lute/io/models/validators.py`

### Database & Results
- **Version-agnostic DB API**: `lute/io/db.py`
- **DB API v2**: `lute/io/_db/v2/api.py`
- **DB API v1** (legacy): `lute/io/_db/v1/api.py`
- **eLog posting**: `lute/io/elog.py` (~18 KB)
- **Calibration I/O**: `lute/io/calib.py` in v0.3.0; removed on `dev` (calibration mapping now done inside LCLSGeom)
- **Custom exceptions**: `lute/io/exceptions.py`

### Task Versioning (new in v0.3.0)
- **Version utilities** (VersionSpecifier enum, git hash/diff, encode/decode): `lute/io/version_utils.py`
- **DB version tables**: see `lute/io/_db/v2/api.py`
- **`lute_cfg` utility** (reconstruct YAML from DB, restore repos): `utilities/lute_cfg/`
- For full documentation see `references/lute-versioning.md`

### Workflows & Orchestration
- **Workflow DAG definitions**: `workflows/` directory
  (list: `https://api.github.com/repos/slac-lcls/lute/contents/workflows`)

### Build & Extensions
- **Build script**: `build.sh`
- **`setup_lute` experiment setup utility** (creates venvs, copies config, registers eLog workflows): `utilities/setup/setup_lute.py`
- **Installation activation script** (sets PATH/PYTHONPATH for meson/prefix installs): `utilities/activate_installation`
- **Extensions**: `extensions/` directory
- **Subprojects**: `subprojects/` directory

> **Package name:** The pip-installable package is `lute-lcls` (not `lute`).
> Install with: `pip install lute-lcls`
> Nightly builds: `pip install lute-lcls --extra-index-url https://slac-lcls.github.io/lute/wheels --pre`

---

## What changed on `dev` since v0.3.0 (0.4.0+dev — unreleased)

The latest release is **v0.3.0** (2026-08-12); `dev` reports version 0.4.0 and
is published as the `v0.4.0+dev` nightly pre-release. Docs for it live under
`https://slac-lcls.github.io/lute/dev/` (there is no `v0.4.0` docs site yet).
Installs that run `dev` include the central `dev` build and the
`lcls-mlcv/lute` `tag-sample-based-workflow` branch used by the CCTBX skills.

| Change | Where | Notes |
|---|---|---|
| `RUN_GROUPS`: per-run parameter policies, DB lookup (`@db:current`, `@db:run:NNN`, `@literal`) | `lute/io/config.py`; `lute-configuration.md` §`RUN_GROUPS` | #145, #150 |
| BayFAI rework: one Task for psana/psana2 (LCLSGeom), `bo_params` → `bayfai_params`, `powder`/`in_file`/`preprocess` removed, new hyperparameters, zip mapping of configurations, MEC DAG | `lute/io/models/bayfai.py`, `workflows/common/bayfai_mec.dag` | #143; see the `bayfai/` sub-skill — `templates/BayFAI.yaml` is still the v0.3.0 shape |
| `lute/io/calib.py` removed — calibration mapping moved into LCLSGeom | `lute/io/` | |
| `PS_PARALLEL=mpi` forced for psana2 Tasks (SmallData XSS/XAS/XES analyzers, PeakFinderSFX*, Xtc2Writer) | `lute/managed_tasks.py`, `lute/tasks/util/environment.py` | `206eed1` |
| `--constraint=OS_VER:9.6` for mixed RHEL 8.10/9.6 nodes breaking MPI | tests + `launch_scripts/submit_launch_airflow.sh` **only** | `c1a1a14`; `launch_slurm` DAGs need their own `slurm_params` constraint — see `slurm-submission.md` |
| Per-hutch default SLURM params; LCLSGeom azimuthal-integration docs | `utilities/setup/setup_lute.py`; SMD DAGs | #149 |

## Website URL Map

Base: `https://slac-lcls.github.io/lute/v0.3.0`

| Topic | URL |
|---|---|
| Home / overview | `https://slac-lcls.github.io/lute/v0.3.0` |
| Quick start | `https://slac-lcls.github.io/lute/v0.3.0/quick_start/` |
| Task configuration (YAML) | `https://slac-lcls.github.io/lute/v0.3.0/usage/configuration/` |
| Installing LUTE | `https://slac-lcls.github.io/lute/v0.3.0/usage/installation/` |
| Running LUTE | `https://slac-lcls.github.io/lute/v0.3.0/usage/running_lute/` |
| Complete simple example | `https://slac-lcls.github.io/lute/v0.3.0/usage/hello_world/` |
| Using smalldata_tools | `https://slac-lcls.github.io/lute/v0.3.0/usage/tasks/smalldata_tools/` |
| Converting XTC1 to XTC2 (parallel Xtc1Reader + Xtc2Writer) | `https://slac-lcls.github.io/lute/v0.3.0/usage/tasks/xtc1_to_xtc2_conversion/` |
| Creating a new Task (overview) | `https://slac-lcls.github.io/lute/v0.3.0/development/new_task/overview/` |
| Creating a first-party Task | `https://slac-lcls.github.io/lute/v0.3.0/development/new_task/first_party/` |
| Creating a third-party Task | `https://slac-lcls.github.io/lute/v0.3.0/development/new_task/third_party/` |
| Creating a new workflow | `https://slac-lcls.github.io/lute/v0.3.0/development/creating_workflows/` |
| Airflow workflows | `https://slac-lcls.github.io/lute/v0.3.0/development/creating_workflows_airflow/` |
| Maestro workflows | `https://slac-lcls.github.io/lute/v0.3.0/development/creating_workflows_maestro/` |
| Dynamic run-time workflows (incl. run_type branching) | `https://slac-lcls.github.io/lute/v0.3.0/development/dynamic_workflows/` |
| Database spec v2 | `https://slac-lcls.github.io/lute/v0.3.0/design/database_v2/` |
| Database spec v1 | `https://slac-lcls.github.io/lute/v0.3.0/design/database/` |
| Source: managed_tasks | `https://slac-lcls.github.io/lute/v0.3.0/source/managed_tasks/` |
| Source: executor | `https://slac-lcls.github.io/lute/v0.3.0/source/execution/executor/` |
| Source: ipc | `https://slac-lcls.github.io/lute/v0.3.0/source/execution/ipc/` |
| Source: task | `https://slac-lcls.github.io/lute/v0.3.0/source/tasks/task/` |
| Source: version_utils | `https://slac-lcls.github.io/lute/v0.3.0/source/io/version_utils/` |

---

## Quick Reference

| Question | GitHub file | Website URL |
|---|---|---|
| How do I install lute? | `README.md` | `/quick_start/` |
| How do I set up lute for an experiment? | `utilities/setup/setup_lute.py` | `/usage/installation/` |
| How do I write a new Task? | `lute/tasks/task.py` | `/development/new_task/first_party/` |
| How does IPC work? | `lute/execution/ipc.py` | `/source/execution/ipc/` |
| How do I configure parameters? | `lute/io/config.py`, `lute/io/models/base.py` | `/usage/configuration/` |
| What managed tasks exist? | `lute/managed_tasks.py` | `/source/managed_tasks/` |
| How are results stored? | `lute/io/db.py`, `lute/io/_db/v2/api.py` | `/design/database_v2/` |
| How do I add a tasklet? | `lute/tasks/tasklets.py`, `lute/managed_tasks.py` | `/development/new_task/third_party/` |
| How does Airflow integration work? | `lute/execution/launch.py` | `/development/creating_workflows_airflow/` |
| How does the Executor spawn Tasks? | `lute/execution/executor.py` | `/source/execution/executor/` |
| How does run_type branching work? | `lute/io/config.py` (parser logic) | `/development/dynamic_workflows/` |
| How do I reconstruct a YAML from the DB? | `utilities/lute_cfg/` | see `references/lute-versioning.md` |
| How do I convert XTC1 → XTC2? | `lute/tasks/xtc1.py`, `lute/tasks/xtc2.py` | `/usage/tasks/xtc1_to_xtc2_conversion/` |

---

## Entry Points (installed by `pyproject.toml`)

| Command | Module | Description |
|---|---|---|
| `run_task` | `run_task:main` | Execute a single task subprocess |
| `subprocess_task` | `subprocess_task:main` | Task subprocess entry point |
| `launch_slurm` | `launch_scripts.launch_maestro:main` | Launch a full workflow DAG via Maestro |
| `launch_prefect` | `launch_scripts.launch_prefect:main` | Launch a workflow via the Prefect backend (`workflows/prefect/`) |
| `launch_airflow` | `launch_scripts.launch_airflow:main` | Launch a full workflow DAG via Airflow |
| `submit_slurm` | `launch_scripts.submit_slurm:main` | Submit a single managed task to SLURM |
| `setup_lute` | `lute_utilities.setup.setup_lute:main` | Set up LUTE for an experiment (venvs, config, eLog) |
| `lute_cfg` | `lute_utilities.lute_cfg.lute_cfg:main` | Reconstruct a YAML from the DB and restore repos to their versioned state (new in v0.3.0) |
| `lute_help` | `lute_utilities.help.task_parameters:main` | Show task parameter help |
| `dbview` | `lute_utilities.dbview.dbview:main` | View the LUTE SQLite database |
