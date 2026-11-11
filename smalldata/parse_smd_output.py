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
    "droplets": [["{det}/droplet_nDroplets"], ["{det}/var_droplet_sparse/data"]],
}


def parse_log(text: str) -> dict:
    text = re.sub(r"\x1b\[[\d;]*m", "", text)
    found = re.findall(r"^(\w+(?:Error|Exception)\b.*|.*(?:Task failed with return code|"
                       r"No azimuthal integration data found|ipm data not found|"
                       r"Scan variable .* not found|No XSS detname).*)$", text, re.M)
    # LCLS-II producer joins per-rank files; the LCLS-I producer writes one file and
    # prints no "Joining" line -- callers fall back to checking the .h5 exists.
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
    # LCLS-II files carry `timestamp`; LCLS-I files carry `event_time`.
    t = next((k for k in ("timestamp", "event_time") if k in f), None)
    n_events = len(f[t]) if t else None
    las = f["lightStatus/laser"][()] if "lightStatus/laser" in f else None
    out = {"n_events": n_events,
           "laser_on": int((las == 1).sum()) if las is not None else None,
           "laser_off": int((las == 0).sum()) if las is not None else None,
           "scan_var_present": (f"scan/{scan_var}" in f) if scan_var else None,
           "missing": [" | ".join(alts) for alts in missing]}
    if analysis == "droplets" and not missing:
        out.update(droplet_facts(f, det))
    return out


def droplet_facts(f, det: str, max_droplets: int = 5_000_000) -> dict:
    """Droplet occupancy, photon-peak position (calib units) and hot-pixel share."""
    import numpy as np
    nd = np.asarray(f[f"{det}/droplet_nDroplets"][()])
    g = f"{det}/var_droplet_sparse"
    n = min(int(nd.sum()), max_droplets)
    data = np.asarray(f[f"{g}/data"][:n])
    facts = {"droplets_per_event_median": float(np.median(nd)) if nd.size else None,
             "events_with_droplets": int((nd > 0).sum()),
             "droplets_read": int(n), "photon_peak": None, "top_repeat_fraction": None}
    if n:
        # Bin the bulk only: pile-up and hot clusters stretch the range and would
        # make the bins coarser than the photon peak.
        hi = float(np.percentile(data, 99.5))
        hist, edges = np.histogram(data, bins=400, range=(float(data.min()), hi))
        i = int(hist.argmax())
        facts["photon_peak"] = round(float((edges[i] + edges[i + 1]) / 2), 3)
        if f"{g}/row" in f and f"{g}/col" in f and f"{det}/var_droplet_sparse_len" in f:
            lens = np.asarray(f[f"{det}/var_droplet_sparse_len"][()])
            k = int(np.searchsorted(np.cumsum(lens), n, side="right"))  # whole events only
            m = int(lens[:k].sum())
            if k and m:
                rc = (np.round(f[f"{g}/row"][:m]).astype(np.int64) * 100000
                      + np.round(f[f"{g}/col"][:m]).astype(np.int64))
                ev = np.repeat(np.arange(k), lens[:k])
                pairs = np.unique(np.stack([rc, ev]), axis=1)[0]   # one per event
                _, counts = np.unique(pairs, return_counts=True)
                facts["top_repeat_fraction"] = round(float(counts.max()) / k, 3)
    return facts


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
    # droplets: 4 events; pixel (5, 5) fires in every event (hot), others peak at 10.5
    lens = np.array([3, 2, 3, 2])
    d = {"event_time": np.zeros(4), "epix/droplet_nDroplets": lens,
         "epix/var_droplet_sparse_len": lens,
         "epix/var_droplet_sparse/data": np.array([40, 10.5, 10.6, 40, 10.4, 40, 10.5, 21, 40, 10.5]),
         "epix/var_droplet_sparse/row": np.array([5, 1, 2, 5, 3, 5, 4, 6, 5, 7.]),
         "epix/var_droplet_sparse/col": np.array([5, 1, 2, 5, 3, 5, 4, 6, 5, 7.])}
    r = check_h5(d, "droplets", "epix", None, None)
    assert r["missing"] == [] and r["n_events"] == 4, r
    assert r["top_repeat_fraction"] == 1.0 and r["droplets_per_event_median"] == 2.5, r
    assert check_h5({"event_time": np.zeros(1)}, "droplets", "epix", None, None)["missing"] == [
        "epix/droplet_nDroplets", "epix/var_droplet_sparse/data"]


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
