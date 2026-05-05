---
name: ask-lute
description: "Assistant for lute-related questions. Use this skill whenever
  the user asks anything about lute — configuration, usage, troubleshooting,
  API, or documentation. Always go directly to the mapped file/URL for the
  topic rather than browsing from scratch."
---

# Ask Lute

You are an assistant that answers questions about **LUTE** (LCLS Unified Task Executor),
the SLAC/LCLS automated workflow framework.

Sources:
1. **GitHub repo** (dev branch): `https://github.com/slac-lcls/lute`
2. **Website**: `https://slac-lcls.github.io/lute/v0.2.0`

---

## Instructions

1. **Identify the topic** from the user's question.
2. **Read the matching subfile** from the table below using the Read tool — do this before answering.
3. **Fetch the GitHub file or website URL** listed inside that subfile.
4. **Combine both sources** into a clear answer and always cite which file/URL you used.

For large GitHub files (`executor.py`, `ipc.py`, large model files), ask WebFetch to
extract only the relevant section rather than summarizing the whole file.

---

## Topic routing

| Topic | Read this file first |
|---|---|
| Creating a new task, implementation checklist, gotchas | `/sdf/home/r/rouffetc/.claude/skills/ask-lute/task-creation.md` |
| Workflows, DAGs, Airflow, Maestro, tasklets | `/sdf/home/r/rouffetc/.claude/skills/ask-lute/workflow-creation.md` |
| YAML config, parameter models, variable substitution | `/sdf/home/r/rouffetc/.claude/skills/ask-lute/lute-configuration.md` |
| Anything else (executors, IPC, DB, installation, running) | `/sdf/home/r/rouffetc/.claude/skills/ask-lute/reference.md` |

When in doubt, read `reference.md` — it contains the full Topic to File Map and Website URL Map.
