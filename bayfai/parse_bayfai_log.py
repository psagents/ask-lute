#!/usr/bin/env python3
"""Facts from a BayFAIOptimizer[2] log, as JSON. No verdict."""
import json
import re
import sys

PATTERNS = {
    "distance_m": r"Detector Distance to Sample: (\S+)",
    "beam_center_m": r"Beam center \((\S+), (\S+)\)",
    "rotations_rad": r"Rotations: \S+ = \((\S+), \S+ = (\S+), \S+ = (\S+)\)",
    "best_score": r"Best Score: (\S+)",
    "elapsed_s": r"Elapsed time: (\S+) s",
    "lowest_q": r">>> Lowest q : (.+)$",
    "highest_q": r">>> Highest q : (.+)$",
    "out_file": r"TaskResult specified as (\S+?)\.?$",
}


def parse(text: str) -> dict:
    text = re.sub(r"\x1b\[[\d;]*m", "", text)
    facts = {"task_completed": "Exiting after Task completion." in text,
             "task_failed": "Exiting after Task failure." in text}
    for key, pat in PATTERNS.items():
        m = re.search(pat, text, re.M)
        if not m:
            facts[key] = None
        elif key.endswith("_q") or key == "out_file":
            facts[key] = m.group(1).strip()
        else:
            nums = [float(g) for g in m.groups()]
            facts[key] = nums[0] if len(nums) == 1 else nums
    # The exception line ending each traceback, once per distinct message: MPI ranks
    # repeat the same one.
    found = re.findall(r"^(\w+(?:Error|Exception)\b.*|.*Task failed with return code.*)$",
                       text, re.M)
    facts["errors"] = list(dict.fromkeys(e.strip() for e in found))[:5]
    return facts


def _selfcheck() -> None:
    log = """INFO:lute.execution.executor:TaskResult specified as /x/geom/22-end.data.
TASK_LOG -- INFO:lute.tasks.bayfai: Elapsed time: 412.21 s
TASK_LOG -- INFO:lute.tasks.bayfai: Detector Distance to Sample: 0.098072
TASK_LOG -- INFO:lute.tasks.bayfai: Beam center (-0.000800, -0.000500)
TASK_LOG -- INFO:lute.tasks.bayfai: Rotations: θx = (-5.26e-03, θy = 5.34e-03, θz = 0.00e+00)
TASK_LOG -- INFO:lute.tasks.bayfai: Best Score: 1.19e+01
TASK_LOG -- INFO:lute.tasks.bayfai: >>> Lowest q : 0.148 Å-1 | 42.379 Å
INFO:lute.execution.executor:Exiting after Task completion.
"""
    f = parse(log)
    assert f["task_completed"] and not f["task_failed"]
    assert f["distance_m"] == 0.098072 and f["beam_center_m"] == [-0.0008, -0.0005]
    assert f["rotations_rad"] == [-5.26e-03, 5.34e-03, 0.0] and f["best_score"] == 11.9
    assert f["out_file"] == "/x/geom/22-end.data" and f["highest_q"] is None
    failed = parse("ModuleNotFoundError: No module named 'x'\nModuleNotFoundError: No module named 'x'\n"
                   "WARNING:lute: Task failed with return code: 1\nExiting after Task failure.")
    assert failed["task_failed"] and len(failed["errors"]) == 2


if __name__ == "__main__":
    if sys.argv[1:] == ["--selfcheck"]:
        _selfcheck()
        sys.exit(print("ok"))
    if len(sys.argv) != 2:
        sys.exit("usage: parse_bayfai_log.py <BayFAIOptimizer*.out> | --selfcheck")
    print(json.dumps({"log": sys.argv[1], **parse(open(sys.argv[1], errors="replace").read())},
                     indent=2, ensure_ascii=False))
