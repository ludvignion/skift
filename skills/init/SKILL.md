---
name: init
description: Copy the skift project template into the current repo without overwriting anything, adding only what an existing CLAUDE.md or .gitignore lacks, and git init if needed.
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

3. Add to CLAUDE.md the template's `##` sections it lacks, and to .gitignore the template's lines
   it lacks. Nothing already there changes; a file just copied gets nothing:

```bash
T="${CLAUDE_PLUGIN_ROOT}/templates/project"
new=$(awk 'FILENAME == ARGV[1] { if (/^## /) have[$0] = 1; next } /^## / { keep = !($0 in have) } keep' CLAUDE.md "$T/CLAUDE.md")
if [ -n "$new" ]; then printf '\n%s\n' "$new" >> CLAUDE.md; echo "added to CLAUDE.md:"; echo "$new" | grep '^## '; fi
new=$(grep -vxFf .gitignore "$T/.gitignore")
if [ -n "$new" ]; then printf '\n%s\n' "$new" >> .gitignore; echo "added to .gitignore:"; echo "$new"; fi
```

4. Show both outputs: the files copied, the files skipped, and what was added to each.
5. End with this line, alone:

Next: write spec/spec.md (Constraints: what it is built with), optionally fill Verification in CLAUDE.md, then /skift:grill
