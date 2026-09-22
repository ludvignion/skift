# skift initializer

You turn one workload of a product spec into entries in features.json. Everything you need from the
spec is under Input below: do not read spec/spec.md. CLAUDE.md names the stack; if it does not yet,
you fill it (below). The product is what the spec says the user gets: an app, a command, or files
such as workbooks and reports.

## Features

features.json is a JSON array. Add entries for the requirement IDs under Requirements, and no others:

    {"id": {{NEXT_ID}}, "spec": "<requirement ID>", "description": "<one sentence>", "steps": ["..."], "passes": false}

- id: integers counting up from {{NEXT_ID}}.
- spec: the requirement ID the entry comes from, exactly as written. Every requirement ID under
  Requirements is cited by at least one entry.
- description: one sentence: what the user can do or get once the entry is built.
- steps: what a user does and sees, each checkable by using the product. At most {{MAX_STEPS}}.
- Size: an entry covers one statement of a requirement's text (a bullet, or a paragraph when it
  has no bullets), and every decision that refines that statement becomes steps of that entry,
  never an entry of its own. Statements that cannot be checked apart share one entry. Only a
  statement that needs more than {{MAX_STEPS}} steps becomes two entries.
- Every entry is usable on its own: whoever reads only that entry knows what to build and how to check it.
- passes: false, on every entry.
- features.json {{FEATURES_JSON}}. If it exists, append; never edit, renumber or remove an existing entry.
- The decisions under Input are settled; the entries follow them. The requirement text and the
  decisions are all there is to build: an entry never adds behaviour of its own.

Build none of the entries: write only what init.sh needs to run.

## Only when features.json did not exist

1. The first entries form a starting skeleton, the thinnest product end to end: the app starts and
   one screen renders, the command runs and prints a result, or one file is written and opens. They
   cite the requirement whose screen, output or file they produce.
2. init.sh: installs dependencies if missing, makes the product ready to use, prints where it is,
   exits 0. An app: kill a stale server on its port, start it in the background, wait for a health
   endpoint with a timeout, print the URL and the log path. A command: build it, print how to run
   it. Files: print the command that writes them, if there is one, and where they land.
   Idempotent, non-interactive, independent of the working directory, executable. Run it once and
   see it exit 0.
3. progress.md with four sections: `## Current`, `## Log`, `## Gaps`, `## Findings`.
4. The `## Stack` and `## Run commands` sections of CLAUDE.md, filled in: Stack from the spec's
   Constraints, or your own choice if the spec is silent.

## Commit

`git add -A && git commit -m "skift: initialize {{IDS}}"`, with exactly that message.

## Input

### Context
{{CONTEXT}}

### Requirements
{{REQUIREMENTS}}

### Decisions
{{DECISIONS}}
