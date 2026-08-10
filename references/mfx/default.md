# MFX — Unknown or Non-Standard Experiment Type

> **When to use this file:** The user's experiment does not clearly match SFX, TR-SAXS/WAXS,
> or XES. Use this guide to walk the technique identification and YAML construction from scratch.
> Do **not** use a pre-filled template — start from the empty per-task templates instead.

---

## Step 1 — Identify the technique

Ask a single framing question:

> "MFX typically runs SFX (serial crystallography), TR-SAXS/WAXS (solution scattering + pump-probe),
> or XES (emission spectroscopy with the Von Hamos or Andor spectrometer).
> Which best describes your experiment?
> (a) SFX / serial crystallography
> (b) Solution scattering (SAXS/WAXS), possibly pump-probe
> (c) X-ray emission spectroscopy (XES)
> (d) XAS / absorption spectroscopy with the CCM
> (e) Something else — describe in one sentence"

If the answer matches (a)–(d), load the corresponding reference:
- (a) → `references/mfx/sfx.md`
- (b) → `references/mfx/saxs.md`
- (c) → `references/mfx/xes.md`
- (d) → build from `templates/AnalyzeSmallDataXAS.yaml`; use `references/hutches/mfx.md` §CCM PVs

---

## Step 2 — Hutch context (if technique is unknown after Step 1)

Read `references/hutches/mfx.md` for:
- Detector inventory and typical aliases
- Available IPM / beam monitor fields
- Available scan variable fields
- Full LUTE analysis chain table

---

## Step 3 — Build the task chain from scratch

Ask the user the minimal set of technique-determining questions:
1. "Is there a pump laser?" → determines timetool block, scan_var, and SmallDataXSS vs XES vs XAS
2. "Is the output diffraction peaks, a scattering profile, or an emission/absorption spectrum?"
3. "What detector(s) are you recording?" → run `run.detnames` to get aliases

Match answers to LUTE task chain using `references/workflow-creation.md` task catalog.

---

## Step 4 — Walk empty templates one block at a time

Use the per-task templates from `templates/` as structured checklists:
- `templates/SubmitSMD.yaml` — walk all `producer_parameters` blocks; skip those clearly inapplicable
- Select the appropriate downstream analyzer: `AnalyzeSmallDataXES.yaml`, `AnalyzeSmallDataXSS.yaml`, or `AnalyzeSmallDataXAS.yaml`

For each block:
1. Ask whether it applies to this experiment
2. If yes, ask each uncommented parameter one at a time
3. Show the assembled block and get confirmation before moving on

---

## MFX Hutch Defaults (always apply regardless of technique)

| Field | Default | Notes |
|---|---|---|
| `ipm_var` | `ipm_dg2/sum` | Primary I₀; confirm alias via `run.detnames` |
| `lightStatus/xray` | always present | X-ray shot flag |
| `lightStatus/laser` | always present | Laser shot flag |
| `ebeam/ebeamL3Energy` | always present | Per-shot electron beam energy |
| DAQ generation | LCLS-II since Jul 2025 | Use `SmallDataProducer2`; confirm `.xtc2` |
