# TXI — Time-resolved X-ray Imaging

> **Usage note:** This file is a reference for consultation during the LUTE setup
> conversation. Read it to understand what is available at TXI. Do not use it to
> pre-fill YAML values — walk each parameter explicitly with the user and suggest
> values based on what this file says.

---

## Experimental Capacity

LCLS-II NEH time-resolved X-ray imaging and scattering station at ~1.3–7 keV. Designed
for TR-SAXS/WAXS at 10 kHz using the ePixHR 2M, single-particle imaging (SPI), and
X-ray imaging experiments. vonHamos spectrometer available for XES. Two Wave8 units
for I₀ normalization. TXI is the least-documented LCLS-II hutch — alias verification
via `detnames` is especially important before configuring anything.

---

## DAQ Generation

**LCLS-II — psana2**
SmallData task: `SmallDataProducer2` (YAML key `SubmitSMD`)
Raw data path: `/sdf/data/lcls/ds/txi/<exp>/xtc2/`
FFB (live): `/sdf/data/lcls/drpsrcf/ffb/txi/<exp>/xtc2/`
SmallData output: `/sdf/data/lcls/ds/txi/<exp>/hdf5/smalldata/`

---

## Experiment Types

| Type | Description |
|---|---|
| TR-SAXS / TR-WAXS | Time-resolved solution scattering at up to 10 kHz; azimuthal integration |
| SPI (single-particle imaging) | Sparse hit triggering; radial integration + background subtraction |
| XES (vonHamos) | X-ray emission via vonHamos bent-crystal spectrometer |
| X-ray imaging | Direct imaging with pump-probe capability |

---

## Detector Inventory

**TXI detector aliases are not fully documented.** Always run `run.detnames` first
and present the full list to the user before configuring any detector field.

```python
ds = DataSource(exp='<exp>', run=<N>)
run = next(ds.runs())
print(run.detnames)
```

| Role | Likely psana alias | Notes |
|---|---|---|
| Main area detector (SAXS / SPI) | `epixhr` or `epixuhr` | ePixHR 2M; larger format than RIX ePixHR2x2; exact alias — verify via `run.detnames` |
| vonHamos spectrometer | unknown | Alias not documented; verify with TXI IS or `run.detnames` |
| Beam monitor 1 | unknown | Wave8; IOC `ioc-txi-pgpw8-01`; exact psana alias — verify via `detnames -e` |
| Beam monitor 2 | unknown | Second Wave8; verify via `detnames -e` |

---

## LUTE-Relevant PVs

### Beam Intensity Monitors (`ipm_var`)

TXI has one confirmed Wave8 IOC (`ioc-txi-pgpw8-01`). The exact psana alias is not
documented. Always enumerate via:

```bash
detnames -e exp=<exp>,run=<N>
```

### Scan Variables (`scan_var`)

No TXI-specific scan variable PV names are documented. Expected pattern (inferred from
TMO/RIX conventions):

| Expected field | Description | Notes |
|---|---|---|
| `lxt_ttc` | ATM timing delay stage | Pump-probe delay; confirm alias |
| mono energy | Monochromator grating | Confirm alias via `detnames -s` |
| `step_value` | Step counter | Auto-generated in Bluesky scans |

To enumerate all scan variables:
```bash
detnames -s exp=<exp>,run=<N>
```

### Standard Shot Flags (psana2)

| psana field | Description |
|---|---|
| `timing.raw.eventcodes(evt)` | EVR event codes fired this shot |
| `timing.raw.pulseId(evt)` | Pulse ID |
| `ebeam.raw.ebeamPhotonEnergy(evt)` | Per-shot photon energy |

---

## LUTE Analysis Chains

| Technique | LUTE task chain |
|---|---|
| TR-SAXS / TR-WAXS | `SubmitSMD` (`getAzIntPyFAIParams` or `getAzIntParams`) → `SmallDataXSSAnalyzer` |
| XES (vonHamos) | `SubmitSMD` (`getROIs` + `writeArea=True`) → `SmallDataXESAnalyzer` |
| SPI | `SubmitSMD` (radial integration + rebinning) — no standard downstream LUTE task |

---

## Special Notes

- **Alias verification is mandatory at TXI.** Do not pre-fill any detector alias or
  beam monitor field without running `run.detnames` and `detnames -e` first and
  confirming with the user.
- **ePixHR 2M:** The ePixHR at TXI is a larger-format detector than the ePixHR2x2 at
  RIX. The psana alias and detector type string should be confirmed with the TXI
  instrument scientist before configuring any processing function.
- **Shared memory (live):** `DataSource(shmem='txi')` (inferred from TMO/RIX pattern;
  confirm with TXI IS).
- **ARP trigger:** Use `END_OF_RUN` for SmallData; downstream analyzers use
  `RUN_PARAM_IS_VALUE:SmallData:done`.
