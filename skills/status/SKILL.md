---
name: status
description: Show the skift board, starting nothing - every task in build order with its tickets and their status (ready, in progress, in review, done), the tasks with no tickets yet, the deferred sections, and what the spec changed under. Use before building a ticket, or when asked what is built and what is left.
---

# Status

Run this from the repo root and print its output verbatim:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py" --project-dir "$PWD" --status
```
