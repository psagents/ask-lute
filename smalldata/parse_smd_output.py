#!/usr/bin/env python3
"""Facts about a SmallData run: task outcome from the log, analyzer inputs present in the HDF5. No verdict."""
from __future__ import annotations

import argparse
import json
import re
import sys

# Datasets each analyzer reads (lute/tasks/_smalldata.py); {det} is the detector alias.
NEEDS = {
    "xss": [["{det}/azav_azav", "{det}/pyfai_azav"], ["lightStatus/xray"], ["lightStatus/laser"]],
    "xas": [["{det}/ROI_0_sum"], ["lightStatus/xray"], ["lightStatus/laser"]],
    "xes": [["{det}/ROI_0_area"], ["lightStatus/xray"], ["lightStatus/laser"]],
}


def parse_log(text: str) -> dict:
    text = re.sub(r"\x1b\[[\d;]*m", "", text)
    found = re.findall(r"^(\w+(?:Error|Exception)\b.*|.*(?:Task failed with return code|"
                       r"No azimuthal integration data found|ipm data not found|"
                       r"Scan variable .* not found|No XSS detname).*)$", text, re.M)
    h5 = re.findall(r"Joining: \d+ files --> (\S+)", text)
    return {"task_completed": "Exiting after Task completion." in text,
            "task_failed": "Exiting after Task failure." in text,
            "h5_written": h5[-1] if h5 else None,
            "errors": list(dict.fromkeys(e.strip() for e in found))[:5]}


def check_h5(f, analysis: str, det: str, ipm_var: str | None, scan_var: str | None) -> dict:
    """`f` is an open h5py.File (or any mapping with `in` and `[...]`)."""
    needs = [[p.format(det=det) for p in alts] for alts in NEEDS[analysis]]
    if ipm_var:
        needs.append([ipm_var])
    missing = [alts for alts in needs if not any(p in f for p in alts)]
    n_events = len(f["timestamp"]) if "timestamp" in f else None
    las = f["lightStatus/laser"][()] if "lightStatus/laser" in f else None
    return {"n_events": n_events,
            "laser_on": int((las == 1).sum()) if las is not None else None,
            "laser_off": int((las == 0).sum()) if las is not None else None,
            "scan_var_present": (f"scan/{scan_var}" in f) if scan_var else None,
            "missing": [" | ".join(alts) for alts in missing]}


def _selfcheck() -> None:
    import numpy as np
    f = {"timestamp": np.zeros(4), "lightStatus/xray": np.ones(4),
         "lightStatus/laser": np.array([1, 0, 1, 1]), "jungfrau/pyfai_azav": np.zeros(4),
         "ipm/sum": np.zeros(4)}
    r = check_h5(f, "xss", "jungfrau", "ipm/sum", "lxt")
    assert r == {"n_events": 4, "laser_on": 3, "laser_off": 1,
                 "scan_var_present": False, "missing": []}, r
    assert check_h5(f, "xes", "epix", None, None)["missing"] == ["epix/ROI_0_area"]
    log = "Joining: 4 files --> mfxl1044925_Run0042.h5\nExiting after Task completion."
    assert parse_log(log)["h5_written"] == "mfxl1044925_Run0042.h5"


if __name__ == "__main__":
    if sys.argv[1:] == ["--selfcheck"]:
        _selfcheck()
        sys.exit(print("ok"))
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--log", help="SmallDataProducer* or SmallData*Analyzer .out")
    ap.add_argument("--h5", help="SmallData HDF5 for the run")
    ap.add_argument("--analysis", choices=sorted(NEEDS))
    ap.add_argument("--det", help="detector alias the analyzer reads")
    ap.add_argument("--ipm-var")
    ap.add_argument("--scan-var")
    a = ap.parse_args()
    result = {}
    if a.log:
        result["log"] = {"path": a.log, **parse_log(open(a.log, errors="replace").read())}
    if a.h5:
        if not (a.analysis and a.det):
            ap.error("--h5 needs --analysis and --det")
        import h5py
        with h5py.File(a.h5, "r") as f:
            result["h5"] = {"path": a.h5, **check_h5(f, a.analysis, a.det, a.ipm_var, a.scan_var)}
    if not result:
        ap.error("give --log and/or --h5")
    print(json.dumps(result, indent=2))
