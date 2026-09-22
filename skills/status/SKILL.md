---
name: status
description: Show the skift kanban board, starting nothing - every feature under its slice in build order, passing or open, with its gaps, findings and deviations, the slices not detailed yet, and the features the spec changed under. Use before building a kanban feature, or when asked what is built or left.
---

# Status

Run this from the repo root and print its output verbatim:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py" --project-dir "$PWD" --status
```
