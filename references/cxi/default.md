# CXI — Coherent X-ray Imaging

> **Status:** Stub. Per-technique reference files have not yet been authored for CXI.
> Use this guide to walk technique identification and YAML construction from scratch.

---

## Step 1 — Identify the technique

Ask:

> "CXI runs SFX (serial crystallography with Cheetah/CCTBX), single-particle CDI,
> or ptychography. Which best describes your experiment?"

For SFX, the MFX SFX task chain applies with CXI-specific aliases:
- Primary detector at CXI: `jungfrau4M` — confirm via `run.detnames`
- Camera length PV: ask the instrument scientist
- Cheetah is the standard hit finder at CXI

---

## Step 2 — Hutch context

Read `references/hutches/cxi.md` for detector inventory, IPM aliases, and any
CXI-specific PVs not listed here.

---

## Step 3 — Walk empty templates

For SFX at CXI, use `templates/mfx/sfx.yaml` as a structural reference but
replace all MFX-specific aliases (`jungfrau`, `MFX:ROB:CONT:POS:Z`, etc.)
with CXI-specific values confirmed via `run.detnames` and the instrument scientist.

For non-SFX experiments, start from the appropriate per-task template:
- `templates/SubmitSMD.yaml` for SmallData production
- Downstream analyzer based on scientific output

---

## CXI Hutch Defaults (apply with caution — verify with instrument scientist)

| Field | Typical value | Note |
|---|---|---|
| SFX detector | `cspad` or `jungfrau` | Confirm via `run.detnames` |
| Hit finder | `RunCheetah` (Cheetah) | Standard at CXI for SFX |
| Indexer | `IndexCrystFEL` (xgandalf) or `IndexCCTBXXFEL` | Ask user preference |
| DAQ | check with user | Some CXI endstations still LCLS-I |
