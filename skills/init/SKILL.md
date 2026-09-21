---
name: init
description: Copy the skift project template into the current repo without overwriting anything, and git init if needed.
disable-model-invocation: true
---

# Init

1. If `git rev-parse --is-inside-work-tree` fails, run `git init`.
2. From the repo root, copy the template, skipping every file that already exists:

```bash
T="${CLAUDE_PLUGIN_ROOT}/templates/project"
(cd "$T" && find . -type f) | while read -r f; do
  if [ -e "$f" ]; then echo "skipped $f"; else mkdir -p "$(dirname "$f")" && cp "$T/$f" "$f" && echo "copied $f"; fi
done
```

3. Show its output: the files copied and the files skipped.
4. End with this line, alone:

Next: fill Stack and Verification in CLAUDE.md, write spec/spec.md, then /skift:grill
