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
- **XTC conversion**: `lute/tasks/xtc.py`
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
- **YAML parsing**: `lute/io/config.py`
- **Parameter utilities**: `lute/io/parameters.py`
- **Base TaskParameters class**: `lute/io/models/base.py`
- **Shared validators**: `lute/io/models/validators.py`

### Database & Results
- **Version-agnostic DB API**: `lute/io/db.py`
- **DB API v2**: `lute/io/_db/v2/api.py`
- **DB API v1** (legacy): `lute/io/_db/v1/api.py`
- **eLog posting**: `lute/io/elog.py` (~18 KB)
- **Calibration I/O**: `lute/io/calib.py`
- **Custom exceptions**: `lute/io/exceptions.py`

### Workflows & Orchestration
- **Workflow DAG definitions**: `workflows/` directory
  (list: `https://api.github.com/repos/slac-lcls/lute/contents/workflows`)

### Build & Extensions
- **Build script**: `build.sh`
- **Extensions**: `extensions/` directory
- **Subprojects**: `subprojects/` directory

---

## Website URL Map

Base: `https://slac-lcls.github.io/lute/v0.2.0`

| Topic | URL |
|---|---|
| Home / overview | `https://slac-lcls.github.io/lute/v0.2.0` |
| Quick start | `https://slac-lcls.github.io/lute/v0.2.0/quick_start/` |
| Task configuration (YAML) | `https://slac-lcls.github.io/lute/v0.2.0/usage/configuration/` |
| Installing LUTE | `https://slac-lcls.github.io/lute/v0.2.0/usage/installation/` |
| Running LUTE | `https://slac-lcls.github.io/lute/v0.2.0/usage/running_lute/` |
| Complete simple example | `https://slac-lcls.github.io/lute/v0.2.0/usage/complete_example/` |
| Creating a new Task (overview) | `https://slac-lcls.github.io/lute/v0.2.0/development/new_task/overview/` |
| Creating a first-party Task | `https://slac-lcls.github.io/lute/v0.2.0/development/new_task/first_party/` |
| Creating a third-party Task | `https://slac-lcls.github.io/lute/v0.2.0/development/new_task/third_party/` |
| Creating a new workflow | `https://slac-lcls.github.io/lute/v0.2.0/development/creating_workflows/` |
| Airflow workflows | `https://slac-lcls.github.io/lute/v0.2.0/development/creating_workflows_airflow/` |
| Maestro workflows | `https://slac-lcls.github.io/lute/v0.2.0/development/creating_workflows_maestro/` |
| Database spec v2 | `https://slac-lcls.github.io/lute/v0.2.0/design/database_v2/` |
| Database spec v1 | `https://slac-lcls.github.io/lute/v0.2.0/design/database_v1/` |
| Source: managed_tasks | `https://slac-lcls.github.io/lute/v0.2.0/source/managed_tasks/` |
| Source: executor | `https://slac-lcls.github.io/lute/v0.2.0/source/execution/executor/` |
| Source: ipc | `https://slac-lcls.github.io/lute/v0.2.0/source/execution/ipc/` |
| Source: task | `https://slac-lcls.github.io/lute/v0.2.0/source/tasks/task/` |

---

## Quick Reference

| Question | GitHub file | Website URL |
|---|---|---|
| How do I install lute? | `README.md` | `/quick_start/` |
| How do I write a new Task? | `lute/tasks/task.py` | `/development/new_task/first_party/` |
| How does IPC work? | `lute/execution/ipc.py` | `/source/execution/ipc/` |
| How do I configure parameters? | `lute/io/config.py`, `lute/io/models/base.py` | `/usage/configuration/` |
| What managed tasks exist? | `lute/managed_tasks.py` | `/source/managed_tasks/` |
| How are results stored? | `lute/io/db.py`, `lute/io/_db/v2/api.py` | `/design/database_v2/` |
| How do I add a tasklet? | `lute/tasks/tasklets.py`, `lute/managed_tasks.py` | `/development/new_task/third_party/` |
| How does Airflow integration work? | `lute/execution/launch.py` | `/development/creating_workflows_airflow/` |
| How does the Executor spawn Tasks? | `lute/execution/executor.py` | `/source/execution/executor/` |
