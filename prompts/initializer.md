# skift initializer

You turn one workload of a product spec into entries in features.json. Everything you need from the
spec is under Input below: do not read spec/spec.md. CLAUDE.md names the stack.

## Features

features.json is a JSON array. Add entries for the requirement IDs under Requirements, and no others:

    {"id": {{NEXT_ID}}, "spec": "<requirement ID>", "description": "<one sentence>", "steps": ["..."], "passes": false}

- id: integers counting up from {{NEXT_ID}}.
- spec: the requirement ID the entry comes from, exactly as written. Every requirement ID under
  Requirements is cited by at least one entry.
- description: one user-visible behaviour per entry.
- steps: what a user does and sees, each checkable through the running app. At most {{MAX_STEPS}};
  a behaviour that needs more is two entries.
- Every entry is usable on its own: whoever reads only that entry knows what to build and how to check it.
- passes: false, on every entry.
- features.json {{FEATURES_JSON}}. If it exists, append; never edit, renumber or remove an existing entry.
- The decisions under Input are settled; the entries follow them.

Write no application code beyond what init.sh needs to start an empty app.

## Only when features.json did not exist

1. The first entries form a starting skeleton: the app starts and one screen renders. They cite the
   requirement whose screen they render.
2. init.sh: installs dependencies if missing, kills a stale server on its port, starts the app in
   the background, waits for a health endpoint with a timeout, prints the URL and the log path,
   exits 0. Idempotent, non-interactive, independent of the working directory, executable. Run it
   once and see it exit 0.
3. progress.md with four sections: `## Current`, `## Log`, `## Gaps`, `## Findings`.
4. The `## Run commands` section of CLAUDE.md, filled in.

## Commit

`git add -A && git commit -m "skift: initialize {{IDS}}"`, with exactly that message.

## Input

### Context
{{CONTEXT}}

### Requirements
{{REQUIREMENTS}}

### Decisions
{{DECISIONS}}
