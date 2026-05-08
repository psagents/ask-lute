# Workflow Creation

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

## Adding a task to an existing workflow

1. Make sure the task is registered in `lute/managed_tasks.py`.
2. In the workflow DAG file (under `workflows/`), import or reference the managed task by name.
3. Wire up dependencies (upstream/downstream) using the orchestrator's API.
4. Add the task's parameter block to the experiment YAML config
   (see `task-creation.md` — Step 5).

## Tasklets

Tasklets are lightweight callables attached to an Executor that run before or after the
main Task without spawning a new process. To add one:

1. Define the callable in `lute/tasks/tasklets.py`.
2. Attach it in `lute/managed_tasks.py` via `ManagedTask(..., tasklets=[...])`.
