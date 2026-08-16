# Result Passing Between Tasks

## Overview

LUTE uses a **database-based result passing mechanism** to automatically chain tasks in workflows. Understanding this system is critical for creating correct workflow configurations.

---

## The Two-Phase Configuration System

LUTE processes configurations in two distinct phases:

### Phase 1: Config Parse Time (YAML Variable Substitution)
- Happens when `lute` reads the YAML file
- `{{ variable }}` substitutions are resolved
- **Only static values are available**: `experiment`, `run`, `work_dir`, environment variables, and other YAML parameters
- **Task results do NOT exist yet** - tasks haven't run!

### Phase 2: Runtime (Pydantic Validators)
- Happens when a Task is about to execute
- Pydantic validators run to validate/transform parameters
- **Previous task results ARE available** via database queries
- This is where automatic result chaining happens

---

## How LUTE Stores and Retrieves Results

### Database Schema (v0.2)

When a Task completes:
1. **Executor** receives the result via IPC
2. **Result** is stored in `lute.db` (SQLite database in `work_dir`)
3. **Database tables** store:
   - `executions` table: links Task runs to results
   - `results` table: stores `payload` (file path or actual result)
   - `parameters` table: stores all input parameters for the execution

### Automatic Retrieval Function

Tasks use `read_latest_db_entry()` (from `lute/io/_db/v2/api.py`) to query previous results:

```python
def read_latest_db_entry(
    db_dir: str,           # Work directory (contains lute.db)
    task_name: str,        # Task CLASS name (e.g., "FindPeaksSFX")
    param: str,            # Parameter to retrieve (e.g., "out_file")
    valid_only: bool = True,  # Only valid results
    for_run: Optional[Union[str, int]] = None,  # Filter by run number
) -> Optional[Any]:
```

**Important:** Uses **Task class names** (same as YAML section headers), not Managed Task names!

---

## The Three Valid Patterns for in_file/out_file

### Pattern 1: Omit Parameters (RECOMMENDED - Automatic Chaining)

**When to use:** Standard workflow where Task B processes Task A's output

**How it works:**
- Leave `in_file` empty or omit it entirely from YAML
- Task's Pydantic validator automatically calls `read_latest_db_entry()`
- Retrieves most recent valid result from the prerequisite Task
- Uses that as the input

**Example workflow config:**

```yaml
FindPeaksSFX:
  algorithm: "Peakfinder8"
  outdir: "{{ work_dir }}/peaks"
  det_name: "jungfrau4M"
  min_peaks: 10
  # out_file will be auto-generated based on outdir/experiment/run/tag
  # Result stored in database automatically

IndexCrystFEL:
  # ✓ in_file OMITTED - validator retrieves it from database
  geometry: "/path/to/geometry.geom"
  indexing: "xgandalf"
  # out_file will be auto-generated
  # Result stored in database automatically

MergePartialator:
  # ✓ in_file OMITTED - validator retrieves from IndexCrystFEL result
  symmetry: "mmm"
  # Result stored in database automatically
```

**What happens internally (IndexCrystFEL example):**

```python
# From lute/io/models/sfx_index.py
@validator("in_file", always=True)
def validate_in_file(cls, in_file: str, values: Dict[str, Any]) -> str:
    if in_file == "":
        # Query database for most recent FindPeaksSFX output
        filename = read_latest_db_entry(
            f"{values['lute_config'].work_dir}", 
            "FindPeaksSFX",  # Task class name
            "out_file"       # Parameter that contains the result path
        )
        if filename is not None:
            return filename
        # Falls back to checking other peak finders...
```

**Advantages:**
- ✓ Most robust - works even if paths change
- ✓ Automatically uses the correct result
- ✓ Handles workflow re-execution correctly
- ✓ Less verbose YAML

**When it works:**
- Task parameter model must have an `@validator` that implements this logic
- Most LUTE tasks for SFX, smalldata, etc. have these validators
- Check the source code in `lute/io/models/<task_type>.py` to confirm

---

### Pattern 2: Explicit File Paths

**When to use:** 
- Debugging specific files
- Rerunning analysis on old data
- Using files from outside the workflow
- Task doesn't have automatic validators

**Example:**

```yaml
IndexCrystFEL:
  in_file: "/sdf/data/lcls/ds/mfx/mfx101555026/scratch/peaks/mfx101555026_0313_pf8.list"
  out_file: "/sdf/data/lcls/ds/mfx/mfx101555026/scratch/indexed/output.stream"
  geometry: "/path/to/geometry.geom"
```

**Advantages:**
- ✓ Explicit and clear
- ✓ Works for any task
- ✓ Useful for testing/debugging

**Disadvantages:**
- ✗ Hardcoded paths - not portable
- ✗ Must update if files move
- ✗ Requires knowing exact paths in advance

---

### Pattern 3: YAML Substitution for STATIC Parameters Only

**When to use:** Referencing experiment metadata, environment variables, or other YAML parameters that are known at parse time

**Example of CORRECT usage:**

```yaml
FindPeaksSFX:
  # ✓ Substitute experiment header values
  outdir: "{{ work_dir }}/peaks/{{ experiment }}_{{ run:04d }}"
  
  # ✓ Reference environment variables
  mask_file: "{{ $CALIB_DIR }}/mask.npy"

IndexCrystFEL:
  # ✓ Reference environment variables
  geometry: "{{ $GEOM_DIR }}/detector.geom"
  
  # ✓ Reference static path parameters from other tasks
  pdb_file: "{{ DimpleSolve.pdb }}"  # Only if pdb is a static input path
```

**Example of INCORRECT usage:**

```yaml
IndexCrystFEL:
  # ❌ WRONG - trying to substitute a task result
  in_file: "{{ FindPeaksSFX.out_file }}"
  
  # ❌ WRONG - out_file doesn't exist at parse time
  in_file: "{{ PreviousTask.out_file }}"
```

**Why these fail:**
1. YAML substitution happens **at parse time**
2. At parse time, `FindPeaksSFX` hasn't run yet
3. `out_file` is just a parameter definition (often `""` or auto-generated)
4. Substitution gets an empty string or a template, not the actual result path

**What you might get:**
```yaml
# After substitution, you might end up with:
IndexCrystFEL:
  in_file: ""  # Empty string from FindPeaksSFX.out_file default
```

---

## Task-Specific Automatic Validators

### Tasks with Automatic in_file Retrieval

These tasks have validators that auto-retrieve previous results:

| Task | Auto-retrieves from | Parameter queried |
|------|---------------------|-------------------|
| `IndexCrystFEL` | `FindPeaksSFX`, `RunCheetah`, `FindPeaksPsocake` | `out_file` or `result.payload` |
| `ConcatenateStreamFiles` | `IndexCrystFEL` | `out_file` |
| `MergePartialator` | `IndexCrystFEL` | `out_file` (retrieves directory) |
| `CompareHKL` | `MergePartialator` | `out_file` |
| `AnalyzeSmallDataXSS` | `SubmitSMD` | `result.payload` |
| `AnalyzeSmallDataXAS` | `SubmitSMD` | `result.payload` |
| `MergeCCTBXXFEL` | `ScaleCCTBXXFEL` | `result.payload` (output directory) |

**To verify if a task has auto-retrieval:**
```bash
# Fetch the parameter model file
curl https://raw.githubusercontent.com/slac-lcls/lute/dev/lute/io/models/sfx_index.py | grep -A 20 "@validator.*in_file"
```

Look for patterns like:
```python
@validator("in_file", always=True)
def validate_in_file(cls, in_file: str, values: Dict[str, Any]) -> str:
    if in_file == "":
        filename = read_latest_db_entry(...)
```

---

## Common Mistakes and How to Fix Them

### Mistake 1: Using {{ TaskName.out_file }} for Result Chaining

**Wrong:**
```yaml
FindPeaksSFX:
  outdir: "{{ work_dir }}/peaks"
  # out_file: ""  (default, auto-generated)

IndexCrystFEL:
  in_file: "{{ FindPeaksSFX.out_file }}"  # ❌ Gets empty string!
```

**Right:**
```yaml
FindPeaksSFX:
  outdir: "{{ work_dir }}/peaks"
  # Result stored in database

IndexCrystFEL:
  # in_file omitted - validator queries database ✓
  geometry: "/path/to/geometry.geom"
```

---

### Mistake 2: Confusing Task Class Names with Managed Task Names

**Wrong:**
```python
# In validator code
filename = read_latest_db_entry(
    work_dir,
    "PeakFinderSFX",  # ❌ This is the MANAGED task name
    "out_file"
)
```

**Right:**
```python
# In validator code
filename = read_latest_db_entry(
    work_dir,
    "FindPeaksSFX",  # ✓ This is the TASK CLASS name
    "out_file"
)
```

**Remember:** Database queries use **Task class names** (same as YAML section headers)!

---

### Mistake 3: Over-specifying Parameters

**Over-specified:**
```yaml
FindPeaksSFX:
  outdir: "{{ work_dir }}/peaks"
  out_file: "{{ outdir }}/{{ experiment }}_{{ run:04d }}_pf8.list"  # Unnecessary

IndexCrystFEL:
  in_file: "{{ work_dir }}/peaks/{{ experiment }}_{{ run:04d }}_pf8.list"  # Brittle
```

**Better - let LUTE handle it:**
```yaml
FindPeaksSFX:
  outdir: "{{ work_dir }}/peaks"
  tag: "pf8"
  # out_file auto-generated from outdir/experiment/run/tag

IndexCrystFEL:
  # in_file auto-retrieved from database
```

---

## Decision Tree: What Should I Do?

```
Do I need to specify in_file or out_file?
│
├─ Is this a standard workflow with task chaining?
│  └─ NO → Omit in_file, let validator auto-retrieve ✓
│
├─ Am I debugging or using specific existing files?
│  └─ YES → Use explicit file paths ✓
│
├─ Do I need to customize output location?
│  └─ YES → Set outdir/tag, let out_file auto-generate ✓
│
└─ Do I want to reference static metadata?
   └─ YES → Use {{ experiment }}, {{ run }}, {{ work_dir }}, {{ $ENV_VAR }} ✓
```

---

## Inspecting What Values Will Be Used

If you're unsure what values will be used, you can inspect the database:

```bash
# After running tasks, check the database
sqlite3 /path/to/work_dir/lute.db

# Query recent results
SELECT task_name, param_key, param_value 
FROM parameters 
JOIN tasks ON parameters.task_id = tasks.id 
WHERE param_key IN ('in_file', 'out_file') 
ORDER BY timestamp DESC 
LIMIT 10;
```

Or use LUTE's database reading functions:

```python
from lute.io.db import read_latest_db_entry

# Check what IndexCrystFEL will retrieve
result = read_latest_db_entry(
    db_dir="/path/to/work_dir",
    task_name="FindPeaksSFX",
    param="out_file"
)
print(f"IndexCrystFEL will use: {result}")
```

---

## Summary: Best Practices

1. **Default approach:** Omit `in_file` and let validators handle automatic chaining
2. **Check validators:** Verify the task has an `@validator` for `in_file` in its parameter model
3. **YAML substitution:** Only use `{{ }}` for static values (experiment, run, work_dir, env vars)
4. **Never use:** `{{ TaskName.out_file }}` for result chaining - it won't work
5. **Explicit paths:** Only when debugging, testing, or using external files
6. **Query by Task class name:** Database queries use Task class names (YAML section headers), not Managed Task names

---

## Reference: Database Query Function Signature

```python
from lute.io.db import read_latest_db_entry

def read_latest_db_entry(
    db_dir: str,                              # Work directory containing lute.db
    task_name: str,                           # Task CLASS name (e.g., "FindPeaksSFX")
    param: str,                               # Parameter name (e.g., "out_file")
    valid_only: bool = True,                  # Only retrieve valid results
    for_run: Optional[Union[str, int]] = None # Filter by run number
) -> Optional[Any]:
    """
    Read the most recent entry for a specific parameter from a specific Task.
    
    Special param values:
    - "result.payload" : Query the result's payload field
    - "result.summary" : Query the result's summary field
    - Any other string  : Query that parameter name
    """
```

---

## Further Reading

- **Database v2 API**: `https://slac-lcls.github.io/lute/v0.3.0/design/database_v2/`
- **YAML Configuration**: `https://slac-lcls.github.io/lute/v0.3.0/usage/configuration/`
- **Source code**: `lute/io/_db/v2/api.py` - `read_latest_db_entry` function
- **Validators**: `lute/io/models/validators.py` - common validator patterns
- **Task models**: `lute/io/models/sfx_*.py` - SFX task parameter validators
