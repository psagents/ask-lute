#!/usr/bin/env python3
"""Per-shell statistics from a cctbx.xfel.merge *_main.log, as JSON. No verdict, no thresholds."""
import json
import re
import sys

BIN = r"^\s*(\d+)\s+(-?[\d.]+)\s+-\s+([\d.]+)\s+"


def section(text: str, title: str) -> str:
    start = text.find(title)
    if start < 0:
        return ""
    end = text.find("\nAll ", start)
    return text[start:text.find("\n", end + 1) if end >= 0 else len(text)]


def parse(text: str) -> dict:
    d_min = re.search(r"^\s*d_min\s*=\s*([\d.]+)", text, re.M)
    images = [{"bin": int(m[1]), "d_max": float(m[2]), "d_min": float(m[3]),
               "lattices": int(m[4]), "accepted_pct": float(m[5])}
              for m in re.finditer(BIN + r"(\d+)\s+([\d.]+)\s*$", section(text, "Image Statistics"), re.M)]
    intens = section(text, "Intensity Statistics (all accepted experiments)")
    shells = [{"bin": int(m[1]), "d_max": float(m[2]), "d_min": float(m[3]),
               "completeness_pct": float(m[4]), "asu_multi": float(m[5]),
               "obs_multi": float(m[6]), "n_meas": int(m[7]), "i_over_sigma": float(m[9])}
              for m in re.finditer(BIN + r"\[\d+/\d+\]\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+(\d+)\s+(\d+)"
                                   r"\s+\S+\s+([\d.]+)", intens, re.M)]
    scaling = section(text, "Table of Scaling Results")
    for m in re.finditer(BIN + r"\[\d+/\d+\]\s+([\d.]+)%\s+\d+\s+\S+\s+\S+\s+([\d.]+)%\s+([\d.]+)%",
                         scaling, re.M):
        for s in shells:
            if s["bin"] == int(m[1]):
                s.update(cc_half_pct=float(m[4]), r_int_pct=float(m[5]), r_split_pct=float(m[6]))
    overall = re.search(r"^All\s+\[\d+/\d+\]\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)", intens, re.M)
    cc = re.search(r"C\.C\. int is ([\d.]+)% on (\d+) indices", text)
    # The first "Unit cell:" is the target from the phil; the last is the refined average.
    cells = re.findall(r"^Unit cell: \(([^)]+)\)", text, re.M)
    lattices = re.search(r"^All\s+(\d+)\s*$", section(text, "Image Statistics"), re.M)
    return {
        "d_min": float(d_min[1]) if d_min else None,
        "unit_cell": [float(x) for x in cells[-1].split(",")] if cells else None,
        "lattices": int(lattices[1]) if lattices else None,
        "overall": {"completeness_pct": float(overall[1]), "asu_multi": float(overall[2]),
                    "obs_multi": float(overall[3]),
                    "cc_half_pct": float(cc[1]) if cc else None} if overall else None,
        "shells": shells,
        "image_shells": images,
        # An empty table on a non-empty log means the format moved, not that the data are bad.
        "missing_sections": [t for t, v in (("intensity", shells), ("images", images),
                                            ("cc_half", cc)) if not v] if text else [],
    }


def _selfcheck() -> None:
    log = """  d_min = 1.8
          Image Statistics
Bin  Resolution Range Lattices Accepted (%)
  1 -1.0000 -  4.8859     1287    96.77
  2  4.8859 -  3.8780     1235    92.86

All                       1330
Unit cell: (77.05, 77.05, 37.21, 90.0, 90.0, 90.0)
Unit cell: (79.012299, 79.012299, 38.340599, 90.000, 90.000, 90.000)
                     Intensity Statistics (all accepted experiments)
  1 -1.0000 -  4.8859     [661/668] 98.95  11.62  11.74   7763      661     181692     4.769       43.325          48.126           1.792
  2  4.8859 -  3.8780     [603/617] 97.73   8.31   8.50   5126      603     273111     3.952       58.140          48.988           1.302
All                   [10439/11740] 88.92   5.00   5.62  58711    10439      66927     2.774        0.000           0.000           0.000
C.C. int is 76.3% on 5284 indices
Table of Scaling Results:
  1 -1.0000 -  4.8859     [578/668] 70.8%     578  --  -- 47.5% 34.1%  -- 0.807   --  1.6638
  2  4.8859 -  3.8780     [465/617] 69.2%     465  --  -- 39.7% 28.9%  -- 0.912   --  1.2412
All                    [5284/11739] 76.3%    5284  --  -- 47.3% 34.5%  -- 0.806   --   1.4
"""
    r = parse(log)
    assert r["d_min"] == 1.8 and r["lattices"] == 1330 and r["unit_cell"][2] == 38.340599
    assert r["overall"] == {"completeness_pct": 88.92, "asu_multi": 5.0, "obs_multi": 5.62,
                            "cc_half_pct": 76.3}
    assert r["shells"][1] == {"bin": 2, "d_max": 4.8859, "d_min": 3.878, "completeness_pct": 97.73,
                              "asu_multi": 8.31, "obs_multi": 8.5, "n_meas": 5126,
                              "i_over_sigma": 3.952, "cc_half_pct": 69.2, "r_int_pct": 39.7,
                              "r_split_pct": 28.9}, r["shells"][1]
    assert r["image_shells"][0]["accepted_pct"] == 96.77 and r["missing_sections"] == []
    assert parse("garbage")["missing_sections"] == ["intensity", "images", "cc_half"]


if __name__ == "__main__":
    if sys.argv[1:] == ["--selfcheck"]:
        _selfcheck()
        sys.exit(print("ok"))
    if len(sys.argv) != 2:
        sys.exit("usage: parse_merge_log.py <merge_*_main.log> | --selfcheck")
    print(json.dumps({"log": sys.argv[1], **parse(open(sys.argv[1], errors="replace").read())}, indent=2))
