# Task Versioning (new in v0.3.0)

## Overview

LUTE v0.3.0 introduces a **Task versioning system** that records which version of a
third-party tool (e.g. `smalldata_tools`) was used for each execution. This enables
**reproducible re-analysis**: given a LUTE database and a run number, you can restore
the codebase to exactly the state it was in when the analysis ran, then reconstruct
the full YAML configuration.

> Source: PR #127.
> Implementation files: `lute/io/version_utils.py`, `lute/io/_db/v2/api.py`.
> DB schema docs: `https://slac-lcls.github.io/lute/v0.3.0/design/database_v2/`

---

## VersionSpecifier Enum

`VersionSpecifier` (in `lute/io/version_utils.py`) is a bitmask enum representing the
kind of version information that has been captured:

| Member | Meaning |
|---|---|
| `GIT_COMMIT_HASH` | Full git commit hash of the task's code repository |
| `GIT_DIFF` | `git diff` patch capturing uncommitted local changes on top of the hash |
| `NONE` | No versioning available or applicable |

These can be OR-combined: `GIT_COMMIT_HASH | GIT_DIFF` represents "hash + local diff",
which together fully describe the exact state of a checked-out git repository.

**Which tasks currently store version information:**
- `SubmitSMD` — records the `smalldata_tools` git commit hash and diff. This is captured
  at parameter validation time and stored in the database alongside the execution record.

---

## Database Storage

Version information is stored in two new tables added to the DB v2 schema in v0.3.0:

### `version_info` table
Stores one row per unique versioned state:

| Column | Type | Description |
|---|---|---|
| `id` | INTEGER PK | Auto-increment identifier |
| `version_type` | INTEGER | Encoded `VersionSpecifier` bitmask |
| `version_data` | TEXT | Encoded version content (git hash, diff, or both) |
| `version_location` | TEXT | Path to the repository (needed to apply diffs) |

### `executions.version_id`
A new foreign key column added to the `executions` table that points to the corresponding
`version_info` row for each task execution. `NULL` if no versioning was recorded.

---

## `lute_cfg` Utility

`lute_cfg` is a CLI utility (installed as an entry point since v0.3.0) that uses the
stored version and parameter information to:

1. **Reconstruct a YAML config** for a specific run from the database — all parameters
   stored for that run, formatted as a valid LUTE two-document YAML.
2. **Restore code repositories** to their exact state during that run — applies the stored
   git hash checkout and diff patch where version information is available.

### Usage

```bash
# After sourcing LUTE (e.g. source lute_envs/lute_env_py39/bin/activate):
lute_cfg --help

lute_cfg -d /path/to/lute.db -r <RUN_NUMBER> -o /path/to/output_dir/
```

| Argument | Description |
|---|---|
| `-d / --database` | Path to the LUTE SQLite database (`lute.db`) |
| `-r / --run` | Run number to reconstruct config for |
| `-o / --output` | Directory or file path for the reconstructed YAML output |

### What it does step by step

For the given run number, `lute_cfg`:

1. Queries all `executions` rows for that run number.
2. For each execution, reads the stored parameters from the `parameters` table.
3. Reconstructs a valid two-document YAML (`---` header + per-task parameter blocks).
4. If a `version_id` exists for an execution (e.g., `SubmitSMD` with `smalldata_tools`
   versioning), it:
   - Checks out the stored git commit hash in the recorded `version_location` path.
   - Applies the stored diff patch to restore any uncommitted local changes.

The output YAML can then be passed directly to `launch_slurm` to reproduce the analysis
exactly.

### Source code

`utilities/lute_cfg/` in the LUTE repository. After building/installing LUTE, the
`lute_cfg` command is available in `PATH`.

---

## Limitations (v0.3.0)

- Only `SubmitSMD` currently captures and stores version information. Other tasks do not
  record versioning yet — the system is designed for incremental adoption.
- Repo restoration requires that the cloned `smalldata_tools` repository is still present
  at the path recorded in `version_location`.
- Nothing is modified automatically during normal LUTE runs. Calling `lute_cfg` is an
  explicit user action.
- The `VersionSpecifier` enum is extensible — additional tasks can opt in by adding
  version computation to their `TaskParameters` Pydantic validators.

---

## Further Reading

- Source: `lute/io/version_utils.py` (fetch via GitHub raw URL)
- DB API: `lute/io/_db/v2/api.py`
- DB schema: `https://slac-lcls.github.io/lute/v0.3.0/design/database_v2/`
- Source version_utils docs: `https://slac-lcls.github.io/lute/v0.3.0/source/io/version_utils/`
