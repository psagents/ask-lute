# LUTE Setup

This reference guides the AI assistant through setting up a complete LUTE workspace for
an LCLS experiment. **Phases 1–4 are pure planning — no files are written and no scripts
are run.** Execution happens only in Phase 5, after the user has reviewed and approved
the complete plan.

**Scripts referenced:**
- `scripts/install_lute.py` — workspace setup, DAG patching, and eLog registration (all-in-one)
- Templates: `templates/` directory — one YAML block per task

---

## Phase 1 — Gather Experiment Info

Ask the user for the following. Derive what can be derived; only ask for what cannot.

| Variable | How to obtain |
|---|---|
| `experiment` | Ask the user (e.g. `mfxl1013621`) |
| `hutch` | Derived: first 3 characters of `experiment` |
| `version` | Ask — default `dev` |
| `directory` | Ask — optional subdirectory under `results/`; default empty |

Derived paths:
```
results_dir     = /sdf/data/lcls/ds/{hutch}/{experiment}/results[/{directory}]
lute_output_dir = {results_dir}/lute_output
config_path     = {lute_output_dir}/{hutch}_lute.yaml
```

---

## Phase 2 — LUTE Install Type Decision

**Decision only — nothing is installed or executed yet.**

Ask the user whether they want a **central install** (default, read-only) or a
**fresh install** (local clone, allows code modifications).

### Option A — Central install (recommended for most users)

No build step required. Record these paths for Phase 5:
```
lute_path         = /sdf/group/lcls/ds/tools/lute/{version}/lute
arp_executable    = {lute_path}/install/bin/submit_launch_slurm.sh
launch_executable = {lute_path}/install/bin/launch_slurm
hutch_config      = {lute_path}/config/{hutch}.yaml
test_config       = {lute_path}/config/test.yaml
```

### Option B — Fresh install (for local code modifications)

Record the commands to run in Phase 5:
```bash
git clone https://github.com/slac-lcls/lute.git {results_dir}/lute
cd {results_dir}/lute && git checkout {version}
./build.sh -e
chmod -R 765 {results_dir}/lute
```

> IMPORTANT: Clone directly to `{results_dir}/lute`. Target directory must not pre-exist.
> `./build.sh -e` installs entry points and takes several minutes.
> If not working: `source /sdf/group/lcls/ds/ana/sw/conda2/manage/bin/psconda.sh`

Fresh-install paths to record:
```
lute_path         = {results_dir}/lute
arp_executable    = {lute_path}/install/bin/submit_launch_slurm.sh
launch_executable = {lute_path}/install/bin/launch_slurm
hutch_config      = {lute_path}/install/lib/python{X.Y}/site-packages/config/{hutch}.yaml
test_config       = {lute_path}/install/lib/python{X.Y}/site-packages/config/test.yaml
```
(`python{X.Y}` = Python version in the active environment, e.g. `python3.9`)

> **Development vs. production note:** Currently LUTE is deployed as a managed
> git + conda installation at S3DF. In the future, LUTE will be a standard pip or conda
> package — the install phase will be unnecessary for experiment data analysis.
> Phase 2 Option B will remain relevant for **developers** modifying LUTE source code.

---

## Phase 3 — Analysis & DAG Planning

**Still planning — no execution.** This phase produces two artefacts for the user to
approve before Phase 4: (1) the confirmed analysis chain, (2) the complete DAG YAML.

### Step 3.1 — Pre-inference: use hutch context

Read [lcls-techniques.md](lcls-techniques.md) and use the hutch from Phase 1 to form
a prior hypothesis before asking the user anything:

- Look up the hutch in the Hutch × Technique Reference table
- Determine DAQ generation (LCLS-I/psana1 or LCLS-II/psana2)
- Identify the 1–3 most likely technique types for that hutch
- Frame the next question as a **confirmation**, not open-ended

Example for hutch `mfx`:
> "MFX typically runs SFX, XES, or XAS experiments. Which best describes yours?
> (a) Serial femtosecond crystallography (SFX), (b) X-ray emission spectroscopy (XES),
> (c) X-ray absorption spectroscopy (XAS), or (d) something else?"

### Step 3.2 — Experiment description

Prompt (frame as confirmation if hutch context already narrows the options):
> "Briefly describe your experiment: technique, detector(s), pump laser (yes/no),
> and what scientific output you need."

### Step 3.3 — Tier 1: Match against the LUTE task catalog

Identify which LUTE tasks are needed and how they chain. Output: an **ordered task list**.

#### LUTE Task Catalog

Two different names exist for each task and they are used in different places:
- **YAML key** (Task class name) — the key used in the YAML config file
- **ManagedTask name** — the name used in `.dag` files and eLog workflow registration

These are NOT interchangeable. Using the wrong name in either place causes silent
misconfiguration or a validation error.

```
SmallData production  (entry point for all per-shot analysis)
  YAML key             ManagedTask name (DAG)     Notes
  SubmitSMD            SmallDataProducer           LCLS-I; psana1; raw XTC → HDF5
  SubmitSMD            SmallDataProducer2          LCLS-II; psana2; raw XTC2 → HDF5
  (same YAML key for both — DAG selects the right producer via !branch_daq2)
  Required for: any downstream per-shot analysis.

Downstream analysis  (each requires SmallData to complete first)
  YAML key                   ManagedTask name (DAG)
  AnalyzeSmallDataXSS        SmallDataXSSAnalyzer   Difference scattering (SAXS/WAXS/TR-XSS)
  AnalyzeSmallDataXAS        SmallDataXASAnalyzer   X-ray absorption (XAS/XANES/EXAFS)
  AnalyzeSmallDataXES        SmallDataXESAnalyzer   X-ray emission (XES/RIXS)

SFX / serial crystallography  (operates on XTC directly; no SmallData prerequisite)
  YAML key                   ManagedTask name (DAG)
  Peak finding — choose one backend:
    RunCheetah                 CheetahRunner          Cheetah; XTC → .cxi/stream (MFX/CXI standard)
    FindPeaksSFX               PeakFinderSFX          psana-native Peakfinder8/PyAlgos

  Indexing — choose one backend:
    IndexCrystFEL              CrystFELIndexer        CrystFEL indexamajig (xgandalf, mosflm, ...)
    IndexCCTBXXFEL             CCTBXIndexer           CCTBX.XFEL indexing

  Post-indexing (CrystFEL path):
    ConcatenateStreamFiles     StreamFileConcatenator Merge per-node .stream files
    MergePartialator           PartialatorMerger      CrystFEL partialator merging
    CompareHKL                 HKLComparer            Merge statistics
    ManipulateHKL              HKLManipulator         HKL scaling / format conversion
    DimpleSolve                DimpleSolver           Molecular replacement (DIMPLE)
    RunSHELXC                  SHELXRunner            Ab initio phasing (SHELXC/D/E)

  Post-indexing (CCTBX path):
    MergeCCTBXXFEL             CCTBXMerger            CCTBX.XFEL merging

Geometry calibration  (separate calibrant run, e.g. AgBh powder)
  YAML key              ManagedTask name (DAG)
  BayFAIOptimizer       BayFAIOptimizer        Bayesian PyFAI optimization (LCLS-I)
  BayFAIOptimizer2      BayFAIOptimizer2       Same for LCLS-II
  GeometryOptimizer     GeometryOptimizer      Exhaustive AgBh geometry search

Data format conversion
  ConvertXtc1to2        Xtc1to2Converter       XTC1 → XTC2 format conversion
  ConvertSMDToNexus     SMDtoNeXusConverter    SmallData HDF5 → NeXus
```

### Step 3.4 — Disambiguation (Tiers 2 and 3)

**Tier 2 — Consult specialist skills** when optional parameter configuration is ambiguous:

| Condition | Specialist skill | Example trigger |
|---|---|---|
| SmallData optional blocks unclear (detector algorithm, azimuthal integration type, photon counting strategy, ROI design) | `ask-smalldata` | "I have an ePix10k2M — droplet finding or photon counting?" |
| SFX indexing/merging strategy unclear (CrystFEL vs CCTBX, post-merge pipeline) | `ask-cctbx-xfel` *(in development — use Tier 3 if unavailable)* | "CrystFEL or CCTBX for indexing?" |

Pass to the specialist: user's experiment description, candidate task list, specific question.

**Tier 3 — Targeted user prompt** when Tier 2 cannot resolve. Ask one specific question at a time:
- "Are you using CrystFEL or CCTBX.XFEL for indexing?"
- "Does a `.poni` calibration file already exist for this detector?"
- "What is the ADU-per-photon for your ePix detector at this gain setting?"
- "Are your raw files `.xtc` (LCLS-I/psana1) or `.xtc2` (LCLS-II/psana2)?"

### Step 3.5 — Design the custom DAG

Build the DAG YAML from the confirmed analysis chain. **Always build a custom minimal
DAG** — it contains exactly the tasks needed, nothing more.

**DAG YAML syntax:**

```yaml
!LUTE_DAG
task_name: "FirstManagedTaskName"
slurm_params: "--nodes=1 --ntasks=1"
next:
- task_name: "NextManagedTaskName"
  slurm_params: "--nodes=1 --ntasks=1"
  next: []
```

For parallel downstream tasks:
```yaml
next:
- task_name: "AnalyzerA"
  slurm_params: "--nodes=1 --ntasks=1"
  next: []
- task_name: "AnalyzerB"
  slurm_params: "--nodes=1 --ntasks=1"
  next: []
```

For SmallData chains, include `!branch_daq2` — the runtime picks `SmallDataProducer`
or `SmallDataProducer2` transparently based on the DAQ `is_daq2` flag:
```yaml
!LUTE_DAG
!branch_daq2
daq2:
  task_name: "SmallDataProducer2"
  slurm_params: "--nodes=4 --ntasks=50 --exclusive"
  next:
  - task_name: "SmallDataXSSAnalyzer"
    slurm_params: "--nodes=1 --ntasks=1"
    next: []
daq1:
  task_name: "SmallDataProducer"
  slurm_params: "--nodes=4 --ntasks=50 --exclusive"
  next:
  - task_name: "SmallDataXSSAnalyzer"
    slurm_params: "--nodes=1 --ntasks=1"
    next: []
```

**`slurm_params` defaults per task:**

| Managed Task Name | Nodes | ntasks-per-node | Extra flags |
|---|---|---|---|
| `SmallDataProducer` | 4 | 50 | `--exclusive` |
| `SmallDataProducer2` | 4 | 50 | `--exclusive` |
| `BayFAIOptimizer` | 1 | 120 | — |
| `BayFAIOptimizer2` | 1 | 120 | — |
| All other tasks | 1 (or user override) | 1 (or user override) | — |

Default SLURM globals (ask only if user wants to override):
- `--partition=milano`
- `--account=lcls:{experiment}`

**Choose a meaningful workflow name** (e.g., `xss_analysis`, `sfx_crystfel`,
`rix_rixs`). This becomes the DAG filename and the eLog workflow registration name
(the eLog entry will be `lute_{wf_name}` — see Phase 6).

**Note on DAG file syntax:** `!LUTE_DAG` and `!branch_daq2` are LUTE-specific custom
YAML tags parsed by LUTE's DAG loader at runtime. When branching, each condition should be
preceded by a `-`. Standard YAML validators (`yaml.safe_load`, linters) will reject these
tags with an error — this is expected. `install_lute.py`'s `patch_dag_slurm_params` reads 
the file as plain text and is unaffected by the tags.

### Step 3.6 — Confirm analysis plan

Show the complete plan and get explicit user approval before proceeding to Phase 4:

```
Analysis plan
──────────────────────────────────────────
Hutch    : {hutch}  ({LCLS-I/psana1 or LCLS-II/psana2})
Chain    : {Task1} → {Task2} → ...

Workflows:
  {wf_name}
    DAG    : {lute_output_dir}/{wf_name}.dag
    Trigger: {END_OF_RUN | MANUAL | RUN_PARAM_IS_VALUE:SmallData:done}
  (repeat for each workflow)

DAG YAML:
{full DAG YAML content}

install_lute.py (will be run at end of Phase 5):
  python scripts/install_lute.py -e {experiment} -v {version} \
    -W {wf1} [{wf2}] --trigger {spec1} [{spec2}]
──────────────────────────────────────────
Proceed to YAML configuration? (yes / adjust)
```

Do not advance to Phase 4 until the user approves this plan.

---

## Phase 4 — YAML Configuration

**Still planning — no files written yet.** Walk every parameter explicitly with the
user. Never guess a value and present it for approval — ask first, then assemble.

The protocol for every block is:
1. Ask the **enabling question** ("Do you need X?")
2. If yes, ask **each parameter** in the block one at a time
3. Show the **assembled block** as a checkpoint — "Here is the `{block}` section:"
4. Get confirmation before moving to the next block

---

### Step 4.0 — Detector alias pre-flight (hard gate)

Collect every detector alias that will appear anywhere in the YAML **before** filling
in any field. A wrong alias produces no error — just silently missing data.

Ask the user to run the appropriate command for a representative run:

> "Before we start, I need to confirm the psana detector aliases for each detector
> in this experiment. Please run:
>
> **psana1:** `ds = psana.DataSource('exp={experiment}:run={run}:smd'); print(next(ds.events()).keys())`
>
> **psana2:** `ds = DataSource(exp='{experiment}', run={run}); print(next(ds.runs()).detnames)`
>
> What alias do you see for: {each detector mentioned in the experiment description}?"

Record all confirmed aliases. Never write a detector name that the user has not
confirmed. If uncertain, write `"# VERIFY ALIAS"` as a placeholder.

---

### Step 4.1 — YAML header

Ask each field explicitly:

1. **title** — "Brief description of this experiment config (for your own reference)?"
2. **experiment** — already known from Phase 1; confirm with user
3. **run** — leave empty (`""`); filled automatically by the eLog trigger at runtime
4. **date** — today's date; confirm with user (`YYYY/MM/DD`)
5. **task_timeout** — "Maximum runtime per task in seconds? [600]"
6. **work_dir** — already known (`{lute_output_dir}`); show to user, confirm

**Variable substitution available in any path field:**
- `{{ work_dir }}` → `work_dir` from the header
- `{{ experiment }}` → experiment name
- `{{ run:04d }}` → zero-padded run number
- `{{ $ENV_VAR }}` → any shell environment variable

> **Checkpoint — header block:**
> ```yaml
> %YAML 1.3
> ---
> title: "..."
> experiment: "..."
> run: ""
> date: "YYYY/MM/DD"
> lute_version: 0.2.0
> task_timeout: 600
> work_dir: "..."
> ```
> Correct? (yes / adjust)

---

### Step 4.2 — SubmitSMD: output directory

Ask: "Where should SmallData HDF5 files be written? Default:
`/sdf/data/lcls/ds/{hutch}/{experiment}/hdf5/smalldata`"

→ `SubmitSMD.directory`

> **Checkpoint — directory field.** Correct? (yes / adjust)

---

### Step 4.3 — SubmitSMD: producer_parameters

Work through each category in order. For each: ask the enabling question; if the
answer is yes, ask every parameter in that block; then checkpoint.

#### A — X-ray scattering (SAXS / WAXS / XSS)

**Enabling question:** "Are you measuring azimuthally-integrated X-ray scattering
(SAXS, WAXS, TR-XSS, diffuse scattering)?"

If **yes**, ask: "Do you have a `.poni` PyFAI calibration file for the detector geometry?"

→ **If `.poni` exists** (`getAzIntPyFAIParams`):
  1. "Full path to the `.poni` file?" → `poni_file`
  2. "Number of radial (Q) bins? [512]" → `npts`
  3. "Number of azimuthal sectors? Enter 1 for isotropic SAXS (scalar I(Q) per shot),
     or higher for sector-resolved analysis. [1]" → `npts_az`
  4. "Integration units? Use `q_A^-1` for SAXS/WAXS (Å⁻¹), `2th_deg` for powder
     diffraction. [q_A^-1]" → `int_units`
  5. "Return the full 2D Q/φ map per shot (large output)? [no]" → `return2d`

→ **If no `.poni`** (`getAzIntParams`):
  1. "X-ray beam energy in keV?" → `eBeam`
  2. "Beam center on detector — [x, y] in pixels?" → `center`
  3. "Sample-to-detector distance in mm?" → `dis_to_sam`
  4. "Number of radial (Q) bins? [512]" → `npts`
  5. "Integration units? [q_A^-1]" → `int_units`
  6. "Number of azimuthal sectors? [1]" → `phiBins`

> **Checkpoint — scattering block.** Show assembled `getAzIntPyFAIParams` or
> `getAzIntParams` section. Correct? (yes / adjust)

#### B — Beam intensity monitors (FIM / Wave8 / diodes)

**Enabling question:** "Do you have beam intensity monitors to record for shot-by-shot
normalization? (e.g. FIM, Wave8, photodiodes)"

If **yes**, for each monitor detector (use confirmed aliases from Step 4.0):
  1. "Signal ROI: row range [start, end] and col range [start, end]?" → `sig_roi`
  2. "Background ROI (or none if not needed)?" → `bkg_roi`
  3. "Is the signal inverted (negative-going pulse)? [no]" → `negative_signal`
  4. "Should a waveform fit be applied? [no]" → `calcPars`

> **Checkpoint — beam monitors block.** Show assembled `getROIs` section. Correct?

#### C — Integrating detectors (Archon CCD, Andor Newton, etc.)

**Enabling question:** "Do you have sub-Hz integrating detectors (Archon, Andor, CCD
cameras that read out slower than the DAQ event rate)?"

If **yes**:
  1. "Which detector is the primary (slowest) integrating detector?" → `intg_main`
     (use alias confirmed in Step 4.0)
  2. "Are there additional integrating detectors? If yes, list their aliases; if no,
     leave empty." → `intg_addl`
  3. Confirm: "`integrating_detectors` for psana2 will be set to [{intg_main} + intg_addl].
     This is required for correct event alignment in psana2 — does that list look right?"

> **Checkpoint — integrating detector block.** Show `integrating_detectors` list and
> `get_intg` section. Correct?

#### D — Area detector images (XES spectrometer, RIXS, full-frame saves)

**Enabling question:** "Do you need to save full detector images per shot? (e.g.
for a dispersive XES or RIXS spectrometer, or any detector where you want the 2D frame)"

If **yes**, for each such detector:
  1. "Detector alias?" (from Step 4.0)
  2. "ROI to save — rows [start, end], cols [start, end]? Leave null for the full chip." → `ROI`
  3. "ADU threshold for pixel masking (thresADU)? Leave null for no masking." → `thresADU`
  4. "Calculate geometric parameters (beam center, pixel solid angles)? [no]" → `calcPars`

> **Checkpoint — area detector save block.** Show `getROIs` (with `writeArea: true`).
> Correct?

#### E — Sparse photon counting (ePix, AXIS, sparse area detectors)

**Enabling question:** "Are any of your area detectors operating in a sparse photon
regime (average occupancy below ~0.1 photons/pixel)?"

If **yes**, for each sparse detector:
  1. "Detector alias?" (from Step 4.0)
  2. "ADU-per-photon (`aduspphot`) — from your detector characterization at this gain?"
     If unknown: pause and explain how to determine it, or mark `# FILL IN`.
  3. "Minimum ADU to count as a droplet candidate? [typically 0.5× aduspphot]" → `threshold`
  4. "Is this a 2-photon finder or single-photon droplet? [single-photon droplet]"
     → selects `getDroplet2Photons` vs `getDropletParams`

> **Checkpoint — photon counting block.** Correct?

#### F — XPCS / speckle autocorrelation

**Enabling question:** "Are you measuring X-ray photon correlation spectroscopy (XPCS)
or speckle dynamics?"

If **yes**, walk the `getAutocorrParams` fields from the template.

> **Checkpoint — autocorrelation block.** Correct?

#### G — SVD multi-bunch decomposition

**Enabling question:** "Does your experiment have multi-bunch or multi-pulse shots
that require SVD basis decomposition?"

If **yes**:
  1. "Path to the pre-computed SVD basis file?" → `basis_file`
     Check it exists before accepting: if not found, warn and halt.

> **Checkpoint — SVD block.** Correct?

#### H — cRIXS / Pressio compression (Rowland circle spectrometer)

**Enabling question:** "Are you using a curved Rowland-circle RIXS spectrometer
(e.g. cRIXS at TMO) that requires data compression before ROI extraction?"

If **yes**, walk `getPressioCompression` fields from the template.
Note: this block must appear **before** `getROIs` in the YAML.

> **Checkpoint — compression block.** Correct?

#### I — Timing tool (pump-probe timetool)

**Enabling question:** "Is there a pump-probe timing tool running to correct
laser–X-ray timing jitter?"

If **yes**, walk `ttCalib` fields from the template.

> **Checkpoint — timetool block.** Correct?

#### J — Detector accumulation types (always asked)

Ask regardless of experiment type:

"What data types should be accumulated per run for each detector? Options:
- `calib` — calibrated ADU array (always recommended)
- `image` — assembled 2D image (with geometry applied)
- `raw` — raw uncalibrated array

Enter as a list, minimum [`calib`]." → `detSumAlgos.all`

> **Checkpoint — detSumAlgos block.** Correct?

---

### Step 4.4 — Downstream task parameters

For each downstream task in the analysis chain (e.g. `AnalyzeSmallDataXSS`,
`AnalyzeSmallDataXES`, `AnalyzeSmallDataXAS`), walk every non-commented field in the
corresponding template, asking the user for each value explicitly.

Common fields across downstream tasks:
- `smd_path` — leave empty (`""`); auto-populated from `SubmitSMD` result via LUTE DB
- `ipm_var` — "Which IPM alias for X-ray intensity filtering? (e.g. `ipm5/sum`)"
- `scan_var` — "Is there a scan variable (delay stage, monochromator energy, motor)?
  If yes, what is its DAQ alias? If no, leave empty."
- `xes_detname` / `xss_detname` — use confirmed aliases from Step 4.0

> **Checkpoint after each downstream task block.** Correct?

---

### Step 4.5 — Full YAML review

Assemble the complete two-document YAML (header + all task blocks) and present it in
full:

```
Here is the complete YAML that will be written to:
  {config_path}

{full two-document YAML}

Please review carefully before I write anything to disk.
Shall I proceed to Phase 5 (execution)? (yes / adjust)
```

Do not advance to Phase 5 until the user gives explicit approval.

---

## Phase 5 — Execute

The user has approved the plan (Phase 3) and the YAML (Phase 4). Now execute everything
in order. Each step is concrete and verifiable.

### Step 5.0 — Kerberos ticket (get it now to avoid interruption later)

`install_lute.py` checks `$HOME/krb5cc.ticket` before posting to the eLog.
Obtain a ticket before writing any files so the final script call is uninterrupted:

```bash
klist -c FILE:$HOME/krb5cc.ticket
```

**Valid:** proceed. **Missing or expired** — ask the user for their SLAC username and
show the command to run **in their own terminal** (the AI never asks for the password):
```
kinit -c FILE:$HOME/krb5cc.ticket <username>@SLAC.STANFORD.EDU
```
Ask the user to confirm once done, then re-run `klist` to verify.

### Step 5.1 — Fresh install build (Option B only)

If the user chose Option B in Phase 2, run the clone and build now:
```bash
git clone https://github.com/slac-lcls/lute.git {results_dir}/lute
cd {results_dir}/lute && git checkout {version}
./build.sh -e
chmod -R 765 {results_dir}/lute
```

Skip this step for central install (Option A).

### Step 5.2 — Create output directory

`install_lute.py` will also create this directory, but the DAG and YAML files must
be written into it first, so create it now:

```bash
mkdir -p {lute_output_dir}
chmod 777 {lute_output_dir}
```

### Step 5.3 — Write DAG file(s)

For each workflow from Phase 3, write the DAG YAML:

```bash
cat > {lute_output_dir}/{wf_name}.dag << 'EOF'
{full DAG YAML from Phase 3}
EOF
chmod 666 {lute_output_dir}/{wf_name}.dag
```

Repeat for each workflow in the analysis plan.

### Step 5.4 — Write YAML configuration

Write the complete YAML assembled in Phase 4:

```bash
cat > {config_path} << 'EOF'
{full two-document YAML from Phase 4}
EOF
chmod 666 {config_path}
```

### Step 5.5 — Run install_lute.py

All files are now in place. Run the script once to finalize the workspace, patch
`slurm_params` in the DAGs, and register workflows in the eLog:

```bash
python scripts/install_lute.py \
  -e {experiment} \
  -v {version}    \
  -W {wf1} {wf2} ...                              \
  --trigger {spec1} {spec2} ...                   \
  [--partition {partition}]                       \
  [--account {account}]                           \
  [--nodes {N}] [--ntasks-per-node {N}]           \
  [-f] [-D {directory}] [--test]
```

`--trigger` specs (one per `-W` workflow, in matching order):

| Spec | When to use |
|---|---|
| `END_OF_RUN` | Workflow processes raw data; no upstream dependency |
| `MANUAL` | Calibration or one-time computation; should not auto-run |
| `RUN_PARAM_IS_VALUE:SmallData:done` | Workflow depends on SmallData production completing |

The trigger for each workflow is determined in Phase 3 (Step 3.7) as part of the
analysis plan — it reflects the workflow's role, not its name.

What the script does in order:
1. **Fresh install** (only if `-f`): git clone, `build.sh -e`, set permissions
2. **Workspace**: creates `lute.db` (mode 664); sets final permissions on directory
3. **DAG patching**: verifies each DAG exists, patches `slurm_params` in-place
4. **Kerberos check**: verifies `$HOME/krb5cc.ticket`; exits with instructions if invalid
5. **eLog registration**: POSTs each workflow with the trigger type from `--trigger`

### Step 5.6 — Verify

```bash
ls -la {lute_output_dir}/
# Expected: lute.db (664), {hutch}_lute.yaml (666), {wf_name}.dag (666) for each workflow
```

---

## Phase 6 — Verify

`install_lute.py` handles eLog registration at the end of Step 5.5. Once it completes
successfully, confirm that the workflows appear in the eLog:

```
https://pswww.slac.stanford.edu/lgbk/lgbk/{experiment}/
→ Workflow Definitions tab
```

**Name prefix:** `install_lute.py` registers each workflow as `lute_{wf_name}`. A
workflow named `rix_smalldata` appears in the eLog as `lute_rix_smalldata`. This is
expected — look for the `lute_` prefix when verifying.

If you need to re-register (e.g. after changing a DAG or trigger type) without redoing
the full workspace setup, re-run `install_lute.py` with the same `-W` arguments. The
workspace and DAG patching steps are idempotent.

**Kerberos ticket:** `install_lute.py` checks `$HOME/krb5cc.ticket` before posting.
If it is missing or expired the script exits with the exact `kinit` command to run.
The AI never requests the password — the user runs `kinit` in their own terminal.

### Trigger types — determined in Phase 3, passed explicitly to the script

Triggers are decided during Phase 3 (Step 3.7) based on each workflow's role in the
analysis chain. They are passed to `install_lute.py` via `--trigger` at execution time.
No name-based lookup is performed — the skill determines the right trigger live.

| Workflow role | `--trigger` spec to pass |
|---|---|
| Produces data from raw XTC (SmallData, SFX peak finding, XTC conversion) | `END_OF_RUN` |
| Analyzes SmallData output (XSS, XAS, XES) — depends on SmallData completing | `RUN_PARAM_IS_VALUE:SmallData:done` |
| Geometry calibration, phasing, or one-time computation | `MANUAL` |

---

## Quick Reference — Phase Order

```
Phase 1  Gather info          → experiment name, hutch, paths
Phase 2  Install type         → central or fresh (decide only)
Phase 3  Analysis & DAG plan  → task chain, DAG YAML, triggers        ← user approves
Phase 4  YAML configuration   → alias pre-flight, then ask every param ← user approves each block + full review
Phase 5  Execute              → mkdir, write DAGs, write YAML,
                                then install_lute.py  (workspace + DAG patch + eLog)
Phase 6  Verify               → confirm workflows appear in eLog UI
```

Nothing touches the filesystem before Phase 5. The user approves the full plan at the
end of Phase 3 and the complete YAML at the end of Phase 4.

One script (`install_lute.py`) handles workspace creation, optional fresh install,
DAG patching, Kerberos check, and eLog registration end-to-end.
