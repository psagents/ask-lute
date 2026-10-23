#!/usr/bin/env python3
"""Exit non-zero if a rendered CCTBX config contains a known config-time trap."""
from __future__ import annotations

import re
import sys


def block(text: str, task: str) -> str:
    m = re.search(rf"^{task}:\n(.*?)(?=^\S|\Z)", text, re.M | re.S)
    return m.group(1) if m else ""


def check(text: str, pdb_cell: str | None) -> list[str]:
    live = "\n".join(l for l in text.splitlines() if not l.lstrip().startswith("#"))
    merge = block(live, "MergeCCTBXXFEL")
    errors = []
    if "parallel_a2a" in live:
        errors.append("parallel_a2a is set: TypeError in group_reflections.py:123")
    steps = re.search(r"dispatch_step_list:\s*>-?\s*\n((?:\s{6,}.*\n?)+)", merge)
    if not steps:
        errors.append("MergeCCTBXXFEL has no dispatch_step_list: the default pipeline "
                      "re-runs modify/filter and hits the covariance crash")
    elif re.search(r"\bmodify\b", steps.group(1)):
        errors.append("MergeCCTBXXFEL dispatch_step_list contains modify: scale output "
                      "has no s1 column, KeyError on polarization re-correction")
    for key, val in (("input_experiments_suffix", ".expt"), ("input_reflections_suffix", ".refl")):
        if f'{key}: "{val}"' not in merge:
            errors.append(f'MergeCCTBXXFEL needs {key}: "{val}" or it finds zero files')
    for task in ("IndexCCTBXXFEL", "ScaleCCTBXXFEL"):
        pf = re.search(r'^\s*phil_file:\s*"([^"]+)"', block(live, task), re.M)
        if not pf or "{{ run" not in pf.group(1):
            errors.append(f"{task}.phil_file is not per-run: parallel runs overwrite it")
    if pdb_cell and pdb_cell not in live:
        errors.append(f"unit cell {pdb_cell!r} from the PDB CRYST1 record is not in the config")
    return errors


def _selfcheck() -> None:
    good = '''IndexCCTBXXFEL:
  phil_file: "{{ work_dir }}/r{{ run:04d }}/cctbx_index.phil"
  phil_parameters:
    indexing_known_symmetry_unit_cell: "77.05 77.05 37.21 90.0 90.0 90.0"
ScaleCCTBXXFEL:
  phil_file: "{{ work_dir }}/r{{ run:04d }}/cctbx_scale.phil"
MergeCCTBXXFEL:
  phil_parameters:
    input_experiments_suffix: ".expt"
    input_reflections_suffix: ".refl"
    dispatch_step_list: >-
      input model_scaling statistics_unitcell
      merge statistics_intensity_cxi
    merging_d_min: 2.0
'''
    assert check(good, "77.05 77.05 37.21 90.0 90.0 90.0") == []
    bad = good.replace("statistics_unitcell", "modify statistics_unitcell").replace(
        "r{{ run:04d }}/cctbx_scale", "cctbx_scale") + "    parallel_a2a: 64\n"
    assert len(check(bad, "1 2 3 90 90 90")) == 4, check(bad, "1 2 3 90 90 90")


if __name__ == "__main__":
    if sys.argv[1:] == ["--selfcheck"]:
        _selfcheck()
        sys.exit(print("ok"))
    if len(sys.argv) not in (2, 3):
        sys.exit("usage: validate.py <rendered.yaml> [\"<a b c al be ga>\" from hutch-data cell]")
    errors = check(open(sys.argv[1]).read(), sys.argv[2] if len(sys.argv) == 3 else None)
    for e in errors:
        print(f"FAIL  {e}", file=sys.stderr)
    sys.exit(1 if errors else print("ok: no known config-time traps"))
