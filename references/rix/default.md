# RIX — Unknown or Non-Standard Experiment Type

> **When to use this file:** The user's experiment does not clearly match ChemRIXS or qRIXS.
> Use this guide to walk technique identification and YAML construction from scratch.

---

## Step 1 — Identify the technique

Ask:

> "RIX runs ChemRIXS (Andor VLS grating spectrometer), qRIXS (Archon CCD on Rowland circle),
> TR-XAS (absorption spectroscopy with CCM scan), or ePixHR scattering.
> Which best describes your experiment?
> (a) ChemRIXS — emission spectra with Andor VLS
> (b) qRIXS — high-resolution RIXS with Archon CCD
> (c) TR-XAS — absorption spectroscopy, pump-probe
> (d) ePixHR scattering or fast area detection
> (e) Something else — describe in one sentence"

If the answer matches (a) or (b), load `references/rix/rixs.md`.
If (c), use `templates/AnalyzeSmallDataXAS.yaml` with RIX-specific fields:
- CCM alias — confirm via `run.detnames`; typically monochromator grating energy
- Wave8 for `ipm_var` — run `detnames -e` to get exact alias

---

## Step 2 — Hutch context

Read `references/hutches/rix.md` for:
- Detector inventory and typical aliases
- Wave8/FIM unit locations
- Timetool PV (`RIX:QRIX:ALV:01:TT:TTALL`)
- Scan variable aliases (`lxt_ttc`, `step_value`, `step_docstring`)
- `integrating_detectors` rules (mandatory at RIX)

---

## Step 3 — Walk empty templates

Use the per-task templates from `templates/`. At RIX, always start with:
1. `templates/SubmitSMD.yaml` — walk all `producer_parameters` blocks
2. **CRITICAL first question in every RIX setup:** "Which detectors are integrating (Andor, Archon)?
   These must be listed in `integrating_detectors` before any other block."

For each block: enabling question → parameters → checkpoint.

---

## RIX Hutch Defaults (always apply)

| Field | Rule |
|---|---|
| `integrating_detectors` | MANDATORY for Andor or Archon — always set |
| `get_intg.intg_main` | slowest integrating detector in psana |
| `getPressioCompression` | qRIXS only; must appear **before** `getROIs` |
| `writeArea` | always `true` for RIXS |
| DAQ | LCLS-II — always `SmallDataProducer2` |
