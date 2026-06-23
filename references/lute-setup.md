# LUTE Setup

This reference guides the AI assistant through setting up a complete LUTE workspace for
an LCLS experiment. Follow the phases in order. Do not skip phases.

**Scripts referenced:**
- `scripts/install_lute.py` — workspace setup, DAG copying and SLURM patching
- `scripts/post_elog_workflows.py` — eLog workflow registration (separate step)
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
results_dir    = /sdf/data/lcls/ds/{hutch}/{experiment}/results[/{directory}]
lute_output_dir = {results_dir}/lute_output
config_path    = {lute_output_dir}/{hutch}_lute.yaml
```

---

## Phase 2 — LUTE Installation

Ask the user whether they want a **central install** (default, read-only) or a
**fresh install** (local clone, allows code modifications).

### Option A — Central install (recommended for most users)

No build step required. Paths are fixed:
```
lute_path         = /sdf/group/lcls/ds/tools/lute/{version}/lute
arp_executable    = {lute_path}/install/bin/submit_launch_slurm.sh
launch_executable = {lute_path}/install/bin/launch_slurm
hutch_config      = {lute_path}/config/{hutch}.yaml
test_config       = {lute_path}/config/test.yaml
```

### Option B — Fresh install (for local code modifications)

Clone and build. Use the `-f` flag in both install scripts:
```bash
git clone https://github.com/slac-lcls/lute.git {results_dir}/lute
cd {results_dir}/lute && git checkout {version}
./build.sh -e
chmod -R 765 {results_dir}/lute
```

> IMPORTANT: Clone directly to `{results_dir}/lute`. The target directory must not
> pre-exist. The build step (`./build.sh -e`) installs entry points and takes
> several minutes.
> If not working, might need to `source /sdf/group/lcls/ds/ana/sw/conda2/manage/bin/psconda.sh`

Fresh-install paths:
```
lute_path         = {results_dir}/lute
arp_executable    = {lute_path}/install/bin/submit_launch_slurm.sh
launch_executable = {lute_path}/install/bin/launch_slurm
hutch_config      = {lute_path}/install/lib/python{X.Y}/site-packages/config/{hutch}.yaml
test_config       = {lute_path}/install/lib/python{X.Y}/site-packages/config/test.yaml
```
(`python{X.Y}` = the Python version in the active environment, e.g. `python3.9`)

---

## Phase 3 — Workspace Setup

Run `install_lute.py` (or replicate its steps manually):

```bash
python install_lute.py \
  -e {experiment} \
  -v {version} \
  [-f]            \   # if fresh install
  [-D {directory}] \  # if subdirectory specified
  -W {wf1} {wf2} ...  # workflow names determined in Phase 5
  [--partition {partition}] \
  [--account {account}]    \
  [--nodes {N}]            \
  [--ntasks-per-node {N}]
```

What the script does:
1. Creates `{lute_output_dir}` (mode 777)
2. Touches `{lute_output_dir}/lute.db` and sets permissions 664
3. Copies `{hutch}.yaml` (or `test.yaml` if hutch config absent) to `{config_path}`
4. Sets `chmod 666` on the config YAML
5. Patches `work_dir` in the YAML via sed: `s|work_dir:.*|work_dir: "{lute_output_dir}"|g`
6. For each workflow: copies `.dag` from `{lute_path}/workflows/common/` and patches `slurm_params`

---

## Phase 4 — Analysis Inference (Tiered)

This is the core intelligence phase. Determine which LUTE tasks and workflows to run.
Use the three tiers below in order.

### Step 4.1 — Ask for a free-form experiment description

Prompt:
> "Briefly describe your experiment: what technique (e.g. SAXS, XES, SFX, XAS),
> what detector(s), is there a pump laser, and what scientific output do you need?"

### Step 4.2 — Tier 1: Match against the embedded LUTE task catalog

Use the catalog below to map the user's description to candidate workflows and tasks.
If a clear match is found and all required parameters can be determined → proceed to Phase 5.

#### LUTE Task Catalog (for inference)

```
SmallData production
  SmallDataProducer            LCLS1 raw XTC → reduced HDF5 (psana1 environment)
  SmallDataProducer2           LCLS2 raw XTC2 → reduced HDF5 (psana2 environment)
  → Required for: any per-shot analysis; all SMD downstream workflows

Scattering / spectroscopy  (all require SmallData first)
  SmallDataXSSAnalyzer         Difference X-ray scattering signal (SAXS/WAXS/TR-XSS)
  SmallDataXASAnalyzer         X-ray absorption spectroscopy (XAS/XANES/EXAFS)
  SmallDataXESAnalyzer         X-ray emission spectroscopy (XES/RIXS)

SFX / serial crystallography
  PeakFinderSFX                Bragg peak finding (Peakfinder8 or PyAlgos)
  CrystFELIndexer              CrystFEL indexamajig (xgandalf, mosflm, asdf, ...)
  CCTBXIndexer                 CCTBX.XFEL indexing
  PartialatorMerger            CrystFEL partialator merging
  CCTBXMerger                  CCTBX.XFEL merging
  HKLComparer                  Merge statistics (CompareHKL)
  SHELXRunner                  Phasing (SHELXC/D/E)
  DimpleSolver                 Molecular replacement (DIMPLE)

Geometry calibration       (all require SmallData first)
  BayFAIOptimizer              Bayesian PyFAI geometry optimization (LCLS1; needs calibrant run)
  BayFAIOptimizer2             Same for LCLS2
  GeometryOptimizer            Exhaustive AgBh geometry search

Data format conversion
  XtcConverter                 XTC1 → XTC2 format conversion
  NeXusConverter               SmallData HDF5 → NeXus
```

#### Workflow → science mapping

| Workflow name | Science type | Requires |
|---|---|---|
| `smd` | General online monitoring / data reduction | — |
| `smd_xss` | TR-SAXS / WAXS / XSS difference scattering | `smd` done first |
| `smd_xas` | XAS / XANES / pump-probe absorption | `smd` done first |
| `smd_xes` | XES / RIXS emission spectroscopy | `smd` done first |
| `sfx` | SFX: peak finding → CrystFEL indexing → merging | — |
| `sfx_cctbx` | SFX: peak finding → CCTBX indexing → merging | — |
| `bayfai` | Detector geometry calibration via Bayesian optimization | calibrant data | `smd` done first |
| `xtc_convert` | XTC1 → XTC2 format conversion | — |

### Step 4.3 — Tier 2: Consult specialist skills

When Tier 1 identifies a workflow but **optional parameter configuration is ambiguous**,
delegate using the Task tool to the appropriate specialist skill.

| Condition | Specialist skill | Example trigger |
|---|---|---|
| SmallData optional blocks unclear (detector algorithm, azimuthal integration type, photon counting strategy, ROI design, waveform fitting) | `ask-smalldata` | "I have an ePix10k2M — should I use droplet finding or photon counting?" |
| SFX indexing/merging/solving strategy unclear (CrystFEL vs CCTBX, post-merge pipeline, phasing) | `ask-cctbx-xfel` *(skill in development — use Tier 3 if unavailable)* | "Should I use CrystFEL or CCTBX for indexing? What does post-merge look like?" |

When calling a specialist skill, pass:
- The user's experiment description
- The candidate task list identified in Tier 1
- The specific question that needs answering

Incorporate the answer into the analysis plan before continuing.

### Step 4.4 — Tier 3: Direct user prompt

If Tier 2 cannot resolve an ambiguity (specialist skill unavailable or inconclusive),
ask the user a **targeted, specific question** — not open-ended. Examples:
- "Are you using CrystFEL or CCTBX.XFEL for indexing?"
- "Does a `.poni` calibration file already exist for this detector configuration?"
- "What is the ADU-per-photon for your ePix detector at this gain setting?"
- "Is this LCLS1 (psana1) or LCLS2 (psana2) data?"

### Step 4.5 — Optional parameter activation

Based on the answers from Tiers 1–3, determine which optional `producer_parameters`
blocks to enable in `SubmitSMD`. Use the table below.

#### SmallData optional parameter activation table

| Experiment type | `producer_parameters` blocks to enable | Key required fields | Notes |
|---|---|---|---|
| SAXS / WAXS / XSS — `.poni` file exists | `getAzIntPyFAIParams` + `detSumAlgos` | `poni_file` path, `npts` | PyFAI path; prefer when calibration file available |
| SAXS / WAXS / XSS — no `.poni` file | `getAzIntParams` + `detSumAlgos` | `eBeam` (keV), `center` ([x,y] µm), `dis_to_sam` (mm) | Native numpy path; no prerequisites |
| SAXS / WAXS with azimuthal sectors | `getAzIntParams` + `detSumAlgos` | `phiBins` > 1 | PyFAI `return2d=True` also works |
| XES / RIXS — integrating det (Andor, Archon) | `get_intg` + `getROIs` (`writeArea=True, ROI=null`) | `intg_main` (slowest det name) | Sub-Hz detectors need `get_intg` |
| XES / RIXS — fast area det (ePix, piranha, AXIS) | `getROIs` (`writeArea=True`) + `getDroplet2Photons` | `aduspphot` (ADU/photon from det characterization) | Modern standard for sparse photon detectors |
| XES / RIXS — curved spectrometer (Rowland circle) | + `getPressioCompression` before other funcs | — | Only for Rowland circle geometries (cRIXS) |
| Beam monitors (FIM / Wave8 / diode) | `getROIs` for waveform traces | `sig_roi`, `bkg_roi`, `negative_signal` | Nearly universal; enables intensity normalization |
| Multi-bunch / multi-pulse per shot | `getSvdParams` | `basis_file` (must pre-exist from calibration) | Requires SVD basis file — ask user if it exists |
| Waveform diode, single pulse | `getROIs` (1D window slice) | `sig_roi`, `bkg_roi` | Simpler than SVD when one pulse per shot |
| Any experiment (universal) | `detSumAlgos` | at minimum `"calib"` | Controls what accumulated images are saved |

**Dependency checks before enabling a block:**
- `getAzIntPyFAIParams` → verify `.poni` file path exists; if not, fall back to `getAzIntParams`
- `getSvdParams` → verify `basis_file` exists; if not, disable and warn: *"SVD basis file not found. Run the basis-file creation step first."*
- `getDroplet2Photons` → `aduspphot` is detector/gain specific; if unknown, prompt the user or ask `ask-smalldata`
- `get_intg` → requires knowing `intg_main` (slowest integrating detector name)

### Step 4.6 — Confirm analysis plan with user

Before proceeding, display a summary and ask for confirmation:

```
Analysis plan
  Workflows   : smd, smd_xss
  Tasks       : SmallDataProducer2 → SmallDataXSSAnalyzer
  YAML blocks : SubmitSMD (header + getAzIntParams + detSumAlgos)
                AnalyzeSmallDataXSS

Proceed? (yes / adjust)
```

---

## Phase 5 — DAG Setup & SLURM Parameters

For each workflow in the confirmed analysis plan:

1. Check if `{lute_output_dir}/{wf_name}.dag` already exists
2. If not, copy from `{lute_path}/workflows/common/{wf_name}.dag`
   - If that source also does not exist, log an error and skip the workflow
3. `chmod 666 {wf_name}.dag`
4. Patch `slurm_params` in-place using task-specific defaults (see below)

### DEFAULT_CONFIG — task-specific SLURM overrides

These override user-provided `--nodes`/`--ntasks-per-node` for specific tasks:

| Managed Task Name | Nodes | ntasks-per-node | Extra flags |
|---|---|---|---|
| `SmallDataProducer` | 4 | 50 | `--exclusive` |
| `SmallDataProducer2` | 4 | 50 | `--exclusive` |
| `BayFAIOptimizer` | 1 | 120 | — |
| `BayFAIOptimizer2` | 1 | 120 | — |
| All other tasks | user `--nodes` (default 1) | user `--ntasks-per-node` (default 1) | — |

### Default SLURM parameters

Use without prompting — only ask for overrides:
- `--partition=milano`
- `--account=lcls:{experiment}`

If the user provides non-default values, pass them as extra args to `install_lute.py`.

---

## Phase 6 — YAML Configuration Assembly

### 6.1 Assemble the YAML

Combine templates from the `templates/` directory into a single config file:
- Start with the **header block** from any template (the `%YAML 1.3 / ---` section)
- Append each task's parameter block, **stripping** the `%YAML 1.3` line and first `---`
  from the 2nd+ template so the file remains a valid two-document YAML

The final structure:
```yaml
%YAML 1.3
---
title: ""
experiment: "{experiment}"
run: ""
date: "{YYYY/MM/DD}"
lute_version: 0.2.0
task_timeout: 600
work_dir: "{lute_output_dir}"
---
SubmitSMD:
  directory: ""
  ...

AnalyzeSmallDataXSS:
  smd_path: ""
  ...
```

### 6.2 Walk required fields

Required fields are those that are **non-commented** and have an empty string value `""`.
Walk through them task by task, asking the user for values. Do not ask about commented-out
fields unless they were activated in Phase 4.

Common required fields across all tasks (in the header):
- `title` — free-form description (not important)
- `experiment` — already known from Phase 1
- `run` — DAQ run number (can be left empty if submitting via eLog trigger)
- `date` — start date of analysis `YYYY/MM/DD` (not important)
- `work_dir` — already set by `install_lute.py`; verify it is correct

### 6.3 Walk enabled optional blocks

For each optional `producer_parameters` block activated in Phase 4, uncomment it and
fill its required sub-fields. Use the answers gathered during inference. If a value is
unknown, note it prominently as `# FILL IN` in the YAML.

### 6.4 Variable substitution reminder

Remind the user that the following substitutions are available in any path field:
- `{{ work_dir }}` — resolves to `work_dir` from the header
- `{{ experiment }}` — LCLS experiment name
- `{{ run:04d }}` — zero-padded run number
- `{{ $ENV_VAR }}` — any shell environment variable

Example:
```yaml
SubmitSMD:
  directory: "{{ work_dir }}/smalldata"
```

### 6.5 Write the final YAML

Write to `{lute_output_dir}/{hutch}_lute.yaml` (already created by `install_lute.py`).
Set permissions: `chmod 666`.

---

## Phase 7 — eLog Workflow Registration

### Step 7.1 — Check Kerberos ticket

Run:
```bash
klist -c FILE:$HOME/krb5cc.ticket
```

**Case A — ticket is valid:** proceed to Step 7.2.

**Case B — ticket missing or expired:**
1. Ask the user for their SLAC username (if not already known from the session)
2. Display the exact command to run **in their own terminal**:
   ```
   kinit -c FILE:$HOME/krb5cc.ticket <username>@SLAC.STANFORD.EDU
   ```
   Note: the AI never asks for the password. The user runs this in their terminal.
   The `FILE:` prefix is required — it writes the ticket to a file that both this
   script and the LUTE submission scripts can read.
3. Ask the user to confirm once they have run it
4. Re-run `klist -c FILE:$HOME/krb5cc.ticket` to verify
5. If still invalid, repeat the prompt once, then abort with a clear error message

### Step 7.2 — Run post_elog_workflows.py

```bash
python scripts/post_elog_workflows.py \
  -e {experiment} \
  -v {version} \
  [-f]                     \   # if fresh install
  [-D {directory}]         \   # if subdirectory was specified
  -W {wf1} {wf2} ...       \
  [--partition {partition}] \
  [--account {account}]    \
  [--test]                      # if using the test Airflow instance
```

The script will:
- Re-validate the Kerberos ticket before posting
- Set `KRB5CCNAME=FILE:$HOME/krb5cc.ticket` so `krtc` uses the correct cache
- Check that each `.dag` file exists (skip with error if not)
- POST each workflow definition to the eLog API
- Log success or failure per workflow

### Step 7.3 — Verify registration

Confirm with the user that workflows appear in the eLog:
```
https://pswww.slac.stanford.edu/lgbk/lgbk/{experiment}/
→ Workflow Definitions tab
```

### Trigger reference (for the skill's own reasoning)

Use this to explain to the user when each workflow will fire:

| Workflow | Trigger type | Fires when |
|---|---|---|
| `smd` | `END_OF_RUN` | Automatically at end of each DAQ run |
| `smd_xss` | `RUN_PARAM_IS_VALUE` | After SmallData run param is set to `"done"` |
| `smd_xas` | `RUN_PARAM_IS_VALUE` | After SmallData run param is set to `"done"` |
| `smd_xes` | `RUN_PARAM_IS_VALUE` | After SmallData run param is set to `"done"` |
| `smd_summaries` | `RUN_PARAM_IS_VALUE` | After SmallData run param is set to `"done"` |
| `bayfai` | `MANUAL` | Only when user manually triggers from eLog |
| All others | `END_OF_RUN` | Automatically at end of each DAQ run |

---

## Quick Reference — Full Command Sequence

For a typical SMD + XSS experiment with central install:

```bash
# 1. Workspace setup
python scripts/install_lute.py \
  -e mfxl1013621 \
  -v dev \
  -W smd smd_xss

# 2. Edit the assembled YAML
#    (fill required fields, configure producer_parameters)
vim /sdf/data/lcls/ds/mfx/mfxl1013621/results/lute_output/mfx_lute.yaml

# 3. Register workflows in the eLog
#    (requires valid Kerberos ticket at $HOME/krb5cc.ticket)
python scripts/post_elog_workflows.py \
  -e mfxl1013621 \
  -v dev \
  -W smd smd_xss
```

For a fresh install, add `-f` to both commands.
