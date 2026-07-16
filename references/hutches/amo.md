# AMO — Atomic, Molecular & Optical

> **Usage note:** This file is a reference for consultation during the LUTE setup
> conversation. Read it to understand what is available at AMO. Do not use it to
> pre-fill YAML values — walk each parameter explicitly with the user and suggest
> values based on what this file says.

---

## Experimental Capacity

Soft X-ray AMO science at ~0.3–2 keV. Runs COLTRIMS/REMI (coincidence ion+electron
imaging via MCP delay-line), velocity map imaging (VMI), photoionization time-of-flight
(TOF), and XES/RIXS with Andor or Princeton spectrometers. Most AMO analysis is
waveform-dominated and highly custom (Roentdek hit-sorting, MBES spectroscopy). LUTE
is applicable at AMO but limited to SmallData production for standard use cases.

---

## Current LUTE Applicability

**LUTE is applicable but limited at AMO.** The primary analysis (COLTRIMS hit-sorting,
delay-line reconstruction, TOF peak analysis) is done with custom tools outside LUTE.
`SmallDataProducer` is the entry point for experiments that need per-shot HDF5
reduction (waveform ROIs, area detector images, scan variable storage).

No standard downstream LUTE analysis tasks (`SmallDataXSSAnalyzer`, etc.) are
applicable to typical AMO experiment types.

---

## DAQ Generation

**LCLS-I — psana1**
SmallData task: `SmallDataProducer` (YAML key `SubmitSMD`)
Raw data path: `/sdf/data/lcls/ds/amo/<exp>/xtc/`
SmallData output: `/sdf/data/lcls/ds/amo/<exp>/hdf5/smalldata/`

---

## Experiment Types

| Type | Description | LUTE scope |
|---|---|---|
| COLTRIMS / REMI | MCP delay-line coincidence; ion+electron 3D momentum | SmallData waveform reduction only |
| VMI | Velocity map imaging; 2D electron/ion momentum | SmallData area detector reduction |
| Ion / electron TOF | Time-of-flight spectroscopy | SmallData waveform ROIs |
| XES / RIXS | Dispersive spectrometer (Andor or Princeton) | SmallData + `SmallDataXESAnalyzer` |

---

## Detector Inventory

All aliases below must be confirmed with the user via `event_keys` on a representative
run before use in any LUTE configuration.

| Role | Typical psana alias / DetInfo source | Notes |
|---|---|---|
| Front pnCCD (CAMP) | `Camp.0:pnCCD.0` | 512×512 px; CAMP collaboration detector |
| Back pnCCD (CAMP) | `Camp.0:pnCCD.1` | 512×512 px; CAMP collaboration detector |
| Waveform digitizer (delay-line / TOF) | `AmoEndstation.0:Acqiris.1` | 8-channel Acqiris; channels carry delay-line anode signals |
| Waveform digitizer (MCP / spare) | `AmoEndstation.0:Acqiris.2` | 2-channel Acqiris; MCP total-yield or second spectrometer |
| Andor / Princeton spectrometer | `AmoEndstation.0:Princeton.0` | Andor or PI CCD; XES/RIXS |
| VMI / OPAL cameras | `AmoEndstation.0:Opal1000.N` | N is run-specific; VMI or beam-position screens |

**Acqiris.1 channel map (quad-anode COLTRIMS, typical):**

| Channel | Signal |
|---|---|
| 2 | X1 — delay-line layer U, wire 1 |
| 3 | X2 — delay-line layer U, wire 2 |
| 4 | Y1 — delay-line layer V, wire 1 |
| 5 | Y2 — delay-line layer V, wire 2 |
| 6 | MCP total signal (TOF reference) |

Hex-anode experiments add W1/W2 on remaining channels. Channel mapping is
experiment-specific — confirm with the user or the AMO logbook.

---

## LUTE-Relevant PVs

### Beam Intensity Monitors (`ipm_var`)

| smalldata field | Description | Notes |
|---|---|---|
| `gas_detector/f_11_ENRC` | FEE gas detector reading 1 | Upstream absolute pulse energy in mJ; always available |
| `gas_detector/f_12_ENRC` | FEE gas detector reading 2 | Average with f_11 for best estimate |
| (in-hutch IPIMB) | Ask IS for alias | `AmoEndstation.0:Ipimb.N`; run-specific; verify via `event_keys` |

### Scan Variables (`scan_var`)

| smalldata field | Description | Notes |
|---|---|---|
| `ebeam/ebeamL3Energy` | Electron beam energy per shot | Proxy for per-shot photon energy |
| `scan/<motor_alias>` | Any scan control PV | Appears under `scan/` in SmallData when DAQ runs a calibcycle scan |
| `epics/<pv_name>` | Beamline EPICS PVs | Slits, attenuators, grating positions |
| `epicsUser/<pv_name>` | User-added PVs | Laser energies, pressures, temperatures |

### Standard Shot Flags (always present in SmallData)

| smalldata field | Description |
|---|---|
| `lightStatus/xray` | X-ray present this shot (bool, from EVR) |
| `lightStatus/laser` | Laser present this shot (bool, from EVR) |
| `ebeam/ebeamL3Energy` | Electron beam L3 energy (MeV) per shot |

---

## LUTE Analysis Chains

| Technique | LUTE task chain |
|---|---|
| COLTRIMS / VMI / TOF | `SubmitSMD` (waveform ROIs via `getROIs`) — further analysis is custom (Roentdek, etc.) |
| XES / RIXS | `SubmitSMD` (`getROIs` + `writeArea=True`) → `SmallDataXESAnalyzer` |

---

## Special Notes

- **No standard downstream analysis:** For COLTRIMS/VMI/TOF, SmallData is the end of
  LUTE's role. The delay-line hit-sorting, momentum reconstruction, and coincidence
  filtering are done with custom tools outside LUTE.
- **Waveform ROIs:** `getROIs` in `producer_parameters` is used to extract time windows
  from the Acqiris waveforms per shot. The ROI definition depends on the signal timing,
  which the user must know from their setup.
- **Acqiris in SmallData:** Waveform data from Acqiris boards is saved as 1D arrays per
  channel per shot. If the user wants full waveforms, set `writeArea=True`.
