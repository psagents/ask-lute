#!/usr/bin/env python3
"""Check the ask-lute skill against upstream LUTE and report drift.

Read-only with respect to the skill: fetches LUTE from GitHub and the docs
site, scans the skill's own files, and prints a Markdown report. The only
write is `--record`, which stores the upstream commit just checked in
`.upstream-state.json` so the next run can list what changed since.

Usage:
    python3 -I scripts/check_upstream.py            # full report vs slac-lcls/lute@dev
    python3 -I scripts/check_upstream.py --record   # report, then save baseline
    python3 -I scripts/check_upstream.py --quiet    # print only if drift found
    python3 -I scripts/check_upstream.py --repo lcls-mlcv/lute \
        --ref tag-sample-based-workflow             # check against a fork/branch

The CCTBX templates track the lcls-mlcv fork, so check them with --repo as above;
expect CCTBX "drift" when checking against slac-lcls/lute@dev.

Set GITHUB_TOKEN (or have `gh` logged in) to lift the anonymous API limit.

Exit codes: 0 no drift, 1 drift found, 2 upstream unreachable.
"""

import argparse
import ast
import datetime
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_REPO = "slac-lcls/lute"
DOCS = "https://slac-lcls.github.io/lute"

SKILL_DIR = Path(__file__).resolve().parent.parent
STATE_FILE = SKILL_DIR / ".upstream-state.json"
SCAN_SUFFIXES = {".md", ".yaml", ".yml", ".sh", ".dag", ".j2"}

# Top-level repo directories whose paths the skill cites.
PATH_RE = re.compile(
    r"(?<![\w/.$-])((?:lute|launch_scripts|utilities|config|workflows|extensions"
    r"|subprojects)/[A-Za-z0-9_./-]*[A-Za-z0-9_])"
)
# Upstream areas worth flagging in the "changed since last check" section.
WATCHED_PREFIXES = (
    "lute/managed_tasks.py",
    "lute/io/models/",
    "lute/io/config.py",
    "lute/execution/",
    "launch_scripts/",
    "workflows/",
    "config/templates/",
    "utilities/setup/",
    "pyproject.toml",
    "build.sh",
)
# Template keys whose children are free-form (no model fields to check).
OPEN_DICT_KEYS = {"data_spec"}


class Unreachable(Exception):
    pass


# --------------------------------------------------------------------------- fetch


def _token():
    for var in ("GITHUB_TOKEN", "GH_TOKEN"):
        if os.environ.get(var):
            return os.environ[var]
    try:
        out = subprocess.run(
            ["gh", "auth", "token"], capture_output=True, text=True, timeout=5
        )
        return out.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


TOKEN = _token()


def fetch(url, api=False):
    headers = {"User-Agent": "ask-lute-drift-check"}
    if api:
        headers["Accept"] = "application/vnd.github+json"
        if TOKEN:
            headers["Authorization"] = f"Bearer {TOKEN}"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        hint = " (rate-limited? set GITHUB_TOKEN)" if e.code == 403 else ""
        raise Unreachable(f"{url}: HTTP {e.code}{hint}") from e
    except (urllib.error.URLError, TimeoutError) as e:
        raise Unreachable(f"{url}: {e}") from e
    return json.loads(body) if api else body


# ------------------------------------------------------------------------ upstream


def load_upstream(repo, ref):
    api = f"https://api.github.com/repos/{repo}"
    head = fetch(f"{api}/commits/{ref}", api=True)
    if head is None:
        raise Unreachable(f"ref '{ref}' not found in {repo}")
    sha = head["sha"]
    tree = fetch(f"{api}/git/trees/{sha}?recursive=1", api=True)
    paths = {t["path"] for t in tree["tree"]}

    def raw(path):
        return fetch(f"https://raw.githubusercontent.com/{repo}/{sha}/{path}") or ""

    models = {
        p: raw(p)
        for p in sorted(paths)
        if p.startswith("lute/io/models/") and p.endswith(".py")
    }
    return {
        "repo": repo,
        "api": api,
        "ref": ref,
        "sha": sha,
        "date": head["commit"]["committer"]["date"],
        "paths": paths,
        "managed_tasks": raw("lute/managed_tasks.py"),
        "pyproject": raw("pyproject.toml"),
        "models": models,
        "tags": [t["name"] for t in fetch(f"{api}/tags?per_page=100", api=True)],
    }


def parse_managed_tasks(src):
    """Managed Task name -> Task class name."""
    pat = re.compile(r'^(\w+)\s*:\s*\w+\s*=\s*\w+\(\s*"(\w+)"', re.M)
    return dict(pat.findall(src))


def parse_entry_points(pyproject):
    m = re.search(r"^\[project\.scripts\]\n(.*?)(?=^\[)", pyproject, re.M | re.S)
    if not m:
        return {}
    return dict(re.findall(r'^(\w+)\s*=\s*"([\w.:]+)"', m.group(1), re.M))


def entry_point_file(target):
    module = target.split(":")[0].replace(".", "/") + ".py"
    # Installed `lute_utilities` is the repo's `utilities` directory.
    return re.sub(r"^lute_utilities/", "utilities/", module)


def _class_fields(cls, dict_fields=None):
    """Annotated fields of a class and its nested classes (except Config).

    Names of fields typed as a dict are added to `dict_fields` when given:
    their YAML children are free-form keys, not model fields.
    """
    fields = set()
    for node in cls.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            fields.add(node.target.id)
            if dict_fields is not None and re.search(r"\b[Dd]ict\b", ast.unparse(node.annotation)):
                dict_fields.add(node.target.id)
        elif isinstance(node, ast.ClassDef) and node.name != "Config":
            fields |= _class_fields(node, dict_fields)
    return fields


def parse_models(models):
    """-> ({Task: (its Parameters fields, model path)},
           {model path: every class field in that file},
           {model path: dict-typed field names in that file}).

    Source is parsed with `ast`, never imported or executed.
    """
    per_task, per_file, dict_fields = {}, {}, {}
    for path, src in models.items():
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue
        classes = [n for n in tree.body if isinstance(n, ast.ClassDef)]
        dict_fields[path] = set()
        per_file[path] = set()
        for c in classes:
            per_file[path] |= _class_fields(c, dict_fields[path])
            if c.name.endswith("Parameters") and c.name != "Parameters":
                per_task[c.name[: -len("Parameters")]] = (_class_fields(c), path)
    return per_task, per_file, dict_fields


def release_key(tag):
    m = re.fullmatch(r"v?(\d+)\.(\d+)(?:\.(\d+))?", tag)
    return tuple(int(x or 0) for x in m.groups()) if m else None


# --------------------------------------------------------------------------- skill


def skill_files():
    for p in sorted(SKILL_DIR.rglob("*")):
        rel = p.relative_to(SKILL_DIR)
        if p.is_file() and p.suffix in SCAN_SUFFIXES and rel.parts[0] not in (".git", "scripts"):
            yield rel, p.read_text(errors="replace").splitlines()


def where(hits, limit=4):
    shown = ", ".join(f"`{f}:{n}`" for f, n in hits[:limit])
    return shown + (f" (+{len(hits) - limit} more)" if len(hits) > limit else "")


def template_keys(lines, task, open_dicts=OPEN_DICT_KEYS):
    """Keys (active and commented-out) under a task block in a YAML template.

    Children of keys in `open_dicts` are skipped.
    """
    keys, stack, inside = [], [], False
    for n, line in enumerate(lines, 1):
        if re.match(rf"^{task}:\s*$", line):
            inside = True
            continue
        if not inside:
            continue
        if re.match(r"^\S", line) and not line.startswith("#"):
            break  # next top-level key
        active = re.match(r"^(\s+)([a-z_]\w*)\s*:", line)
        commented = re.match(r"^(\s*)#\s?\s*([a-z_]\w*):(\s|$)", line)
        m = active or commented
        if not m:
            continue
        indent = len(m.group(1))
        if not active:
            # Read `  #   dist:` as if uncommented: the `# ` stands in for indentation,
            # so it nests under `  # resolutions:` but not under an active `  bounds:`.
            key_col = len(line) - len(line.lstrip(" #"))
            indent = max(indent, key_col - 2)
        while stack and stack[-1][0] >= indent:
            stack.pop()
        if not any(k in open_dicts for _, k in stack):
            keys.append((m.group(2), n))
        stack.append((indent, m.group(2)))
    return keys


# -------------------------------------------------------------------------- checks


class Report:
    def __init__(self):
        self.sections = []
        self.drift = 0

    def add(self, title, drift_items, info_items=()):
        self.drift += len(drift_items)
        self.sections.append((title, list(drift_items), list(info_items)))

    def render(self, up, since):
        out = [
            "# ask-lute upstream drift report",
            "",
            f"Checked against `{up['repo']}@{up['ref']}` = `{up['sha'][:10]}` "
            f"(committed {up['date']}), {datetime.date.today()}.",
            "",
            f"**{self.drift} drift item(s)** — things in the skill that no longer "
            "match upstream. Info items are worth a look but are not errors.",
        ]
        if since:
            out += ["", since]
        for title, drift, info in self.sections:
            status = "DRIFT" if drift else "OK"
            out += ["", f"## {title} — {status}"]
            out += [f"- ✗ {d}" for d in drift]
            out += [f"- ℹ {i}" for i in info]
            if not drift and not info:
                out.append("- nothing to report")
        return "\n".join(out) + "\n"


def check_paths(up, files, report):
    missing = {}
    for rel, lines in files:
        for n, line in enumerate(lines, 1):
            for m in PATH_RE.finditer(line):
                if line[m.end() : m.end() + 1] in ("*", "<", "{"):
                    continue  # glob or placeholder, e.g. `sfx_*.py`, `<name>.py`
                p = m.group(1).rstrip("/.")
                if p not in up["paths"]:
                    missing.setdefault(p, []).append((rel, n))
    report.add(
        "Repository paths cited by the skill",
        [f"`{p}` not in upstream — cited at {where(h)}" for p, h in sorted(missing.items())],
    )


def check_task_names(up, files, report):
    mt = parse_managed_tasks(up["managed_tasks"])
    classes = set(mt.values()) | set(parse_models(up["models"])[0])
    drift = {}

    def flag(msg, rel, n):
        drift.setdefault(msg, []).append((rel, n))

    pair_res = [
        re.compile(r"\|\s*`(\w+)`\s*\|\s*`(\w+)`\s*\|"),  # | `Managed` | `Class` |
        re.compile(r'(\w+)\s*:\s*\w*Executor\s*=\s*\w*Executor\(\s*"(\w+)"'),
    ]
    class_paren = re.compile(r"\b([A-Z]\w+) \(([A-Z]\w+)\)")  # Class (Managed)
    for rel, lines in files:
        is_template = rel.parts[0] == "templates"
        second_doc = False
        for n, line in enumerate(lines, 1):
            for name in re.findall(r'task_name:\s*"?([A-Z]\w*)', line):
                if name not in mt:
                    flag(f"managed task `{name}` not in managed_tasks.py", rel, n)
            pairs = [m for r in pair_res for m in r.findall(line)]
            pairs += [(b, a) for a, b in class_paren.findall(line)]
            for managed, cls in pairs:
                if managed in mt and mt[managed] != cls:
                    flag(f"`{managed}` runs `{mt[managed]}` upstream, skill says `{cls}`", rel, n)
                elif (
                    managed not in mt
                    and managed not in classes  # e.g. a `| Task | depends on |` table
                    and cls in classes
                    and managed[0].isupper()
                ):
                    owners = [k for k, v in mt.items() if v == cls]
                    if owners:
                        flag(
                            f"`{managed}` not a managed task; `{cls}` is run by "
                            f"{', '.join(f'`{o}`' for o in owners)}",
                            rel,
                            n,
                        )
            if is_template and line.strip() == "---":
                second_doc = True
            elif is_template and second_doc:
                m = re.match(r"^([A-Z]\w+):\s*$", line)
                if m and m.group(1) not in classes:
                    flag(f"YAML task key `{m.group(1)}` has no Task/Parameters class upstream", rel, n)
    report.add(
        "Managed Task / Task class names",
        [f"{msg} — {where(h)}" for msg, h in sorted(drift.items())],
        [f"{len(mt)} managed tasks upstream"],
    )


def check_entry_points(up, report):
    eps = parse_entry_points(up["pyproject"])
    ref_md = (SKILL_DIR / "references/reference.md").read_text()
    skill_eps = dict(re.findall(r"^\|\s*`(\w+)`\s*\|\s*`([\w.:]+)`\s*\|", ref_md, re.M))
    drift, info = [], []
    for name, target in sorted(eps.items()):
        if name not in skill_eps:
            drift.append(f"entry point `{name}` → `{target}` missing from reference.md")
        elif skill_eps[name] != target:
            drift.append(f"`{name}` is `{target}` upstream, reference.md says `{skill_eps[name]}`")
        if entry_point_file(target) not in up["paths"]:
            info.append(
                f"upstream inconsistency: `{name}` → `{target}` but "
                f"`{entry_point_file(target)}` does not exist in the repo"
            )
    for name in sorted(set(skill_eps) - set(eps)):
        drift.append(f"reference.md lists `{name}`, which is no longer an entry point")
    report.add("Entry points (pyproject.toml)", drift, info)


def check_backends(up, report):
    backends = sorted(
        p.split("/")[1]
        for p in up["paths"]
        if p.count("/") == 1 and p.startswith("workflows/") and "." not in p
    )
    text = (SKILL_DIR / "references/workflow-creation.md").read_text().lower()
    report.add(
        "Workflow backends",
        [
            f"`workflows/{b}/` exists upstream but workflow-creation.md never mentions {b}"
            for b in backends
            if b != "common" and b not in text
        ],
        [f"upstream backends: {', '.join(backends)}"],
    )


def check_versions(up, files, report):
    releases = sorted((t for t in up["tags"] if release_key(t)), key=release_key)
    latest = releases[-1] if releases else None
    info = [f"latest release tag: `{latest}`; newest tags: {', '.join(up['tags'][:3])}"]
    drift = []
    try:
        versions = json.loads(fetch(f"{DOCS}/versions.json") or "[]")
        docs_latest = next((v["version"] for v in versions if "latest" in v["aliases"]), None)
        info.append(f"docs `latest` alias → `{docs_latest}`")
    except (Unreachable, ValueError):
        info.append("could not read docs versions.json")

    pinned, lute_versions = {}, {}
    for rel, lines in files:
        for n, line in enumerate(lines, 1):
            for v in re.findall(r"slac-lcls\.github\.io/lute/(v[\d.]+)/", line):
                pinned.setdefault(v, []).append((rel, n))
            m = re.match(r"^lute_version:\s*([\w.]+)", line)
            if m:
                lute_versions.setdefault(m.group(1), []).append((rel, n))
    for v, hits in sorted(pinned.items()):
        info.append(f"docs URLs pinned to `{v}`: {where(hits)} (fine only for pages removed later)")
    if latest:
        for v, hits in sorted(lute_versions.items()):
            if release_key(v) and release_key(v) < release_key(latest):
                info.append(
                    f"templates say `lute_version: {v}` ({len(hits)} files), latest is "
                    f"`{latest}` — metadata only, LUTE does not validate it"
                )

    # Docs pages that exist now but the skill never links to.
    try:
        html = fetch(f"{DOCS}/latest/") or ""
        pages = set(re.findall(r'href="((?:usage|development|design)/[\w/]+/)"', html))
        alltext = "\n".join("\n".join(lines) for _, lines in files)
        new = sorted(p for p in pages if p not in alltext)
        if new:
            info.append("docs pages not linked anywhere in the skill: " + ", ".join(f"`{p}`" for p in new))
    except Unreachable:
        pass
    report.add("Versions and documentation", drift, info)


def check_template_fields(up, report):
    per_task, per_file, dict_fields = parse_models(up["models"])
    base_fields = per_file.get("lute/io/models/base.py", set())
    drift, info = [], []
    for path in sorted((SKILL_DIR / "templates").glob("*.yaml")):
        task = path.stem
        if task not in per_task:
            continue
        lines = path.read_text(errors="replace").splitlines()
        own, model_path = per_task[task]
        # Nested models are often separate classes in the same file.
        known = per_file[model_path] | base_fields
        keys = template_keys(lines, task, OPEN_DICT_KEYS | dict_fields[model_path])
        unknown = [(k, n) for k, n in keys if k not in known]
        for k, n in unknown:
            drift.append(
                f"`templates/{path.name}:{n}` field `{k}` is not in `{model_path}` "
                "(renamed/removed? models that allow extra keys pass it through silently)"
            )
        new = sorted(own - {k for k, _ in keys})
        if new:
            shown = ", ".join(f"`{f}`" for f in new[:12])
            more = f" (+{len(new) - 12} more)" if len(new) > 12 else ""
            info.append(f"`{task}`: {len(new)} upstream field(s) not in template: {shown}{more}")
    report.add("Template fields vs Parameters models", drift, info)


def state_key(up):
    return f"{up['repo']}@{up['ref']}"


def since_last_check(up):
    states = json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {}
    state = states.get(state_key(up))
    if not state:
        return "_No baseline yet — run with `--record` to track changes from this commit on._"
    old = state["sha"]
    if old == up["sha"]:
        return f"No upstream commits since the last recorded check ({state['checked']})."
    cmp = fetch(f"{up['api']}/compare/{old}...{up['sha']}", api=True)
    if cmp is None:
        return f"Last recorded commit `{old[:10]}` is no longer reachable from `{up['ref']}`."
    commits = cmp.get("commits", [])
    touched = sorted(
        f["filename"] for f in cmp.get("files", []) if f["filename"].startswith(WATCHED_PREFIXES)
    )
    lines = [
        f"## Upstream changes since last check ({state['checked']}, `{old[:10]}`)",
        f"{cmp.get('total_commits', len(commits))} commit(s); "
        f"{len(touched)} file(s) in areas this skill documents:",
    ]
    lines += [f"- `{f}`" for f in touched[:40]]
    lines += ["", "Commits:"]
    lines += [
        f"- `{c['sha'][:8]}` {c['commit']['message'].splitlines()[0]}" for c in commits[-30:]
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------- main


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--repo", default=DEFAULT_REPO, help=f"GitHub owner/name (default: {DEFAULT_REPO})")
    ap.add_argument("--ref", default="dev", help="upstream branch or tag (default: dev)")
    ap.add_argument("--record", action="store_true", help="save this upstream commit as the baseline")
    ap.add_argument("--quiet", action="store_true", help="print nothing when there is no drift")
    args = ap.parse_args()

    try:
        up = load_upstream(args.repo, args.ref)
        since = since_last_check(up)
    except Unreachable as e:
        print(f"ask-lute drift check: could not reach upstream: {e}", file=sys.stderr)
        return 2

    files = list(skill_files())
    report = Report()
    check_paths(up, files, report)
    check_task_names(up, files, report)
    check_entry_points(up, report)
    check_backends(up, report)
    check_versions(up, files, report)
    check_template_fields(up, report)

    if not (args.quiet and report.drift == 0):
        sys.stdout.write(report.render(up, since))
    if args.record:
        states = json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {}
        states[state_key(up)] = {"sha": up["sha"], "checked": str(datetime.date.today())}
        STATE_FILE.write_text(json.dumps(states, indent=2) + "\n")
    return 1 if report.drift else 0


if __name__ == "__main__":
    sys.exit(main())
