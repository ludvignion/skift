# skift initializer

You turn one workload of a product spec into features. Everything you need from the spec is under
Input below: do not read spec/spec.md. The product is what the spec says the user gets: an app, a
command, or files such as workbooks and reports. Build nothing the spec does not ask for, and choose
nothing it does not name: the stack comes from its Constraints only.

## Features

Each top-level heading under `## Features` is a slice. Its entries go in
`kanban/features/<slice-id>.json`, a JSON array, where the slice id is the second part of the
requirement ID: `features/sample-factory/...` goes in `kanban/features/sample-factory.json`. Add
entries for the requirement IDs under Requirements, and no others:

    {"id": {{NEXT_ID}}, "spec": "<requirement ID>", "description": "<one sentence>", "steps": ["..."], "passes": false}

- id: integers counting up from {{NEXT_ID}}, across every slice file.
- spec: the requirement ID the entry comes from, exactly as written. Every requirement ID under
  Requirements is cited by at least one entry.
- description: one sentence: what the user can do or get once the entry is built.
- steps: what a user does and sees, each checkable by using the product. At most {{MAX_STEPS}}. The
  steps are also the checklist the user reviews the entry by.
- Size: an entry covers one statement of a requirement's text (a bullet, or a paragraph when it
  has no bullets), and every decision that refines that statement becomes steps of that entry,
  never an entry of its own. Statements that cannot be checked apart share one entry. Only a
  statement that needs more than {{MAX_STEPS}} steps becomes two entries.
- Every entry is usable on its own: whoever reads only that entry knows what to build and how to check it.
- passes: false, on every entry.
- kanban/features/ {{FEATURES_STATE}}. Append to a slice file that exists; never edit, renumber or
  remove an existing entry.
- The decisions under Input are settled; the entries follow them. The requirement text and the
  decisions are all there is to build: an entry never adds behaviour of its own.
- An open point is something a requirement asks for whose user-visible outcome neither its text
  nor a decision settles; the grill leaves open the points a wrong guess would cost one entry. Settle
  each in that entry's steps with the simplest outcome that does what the requirement says, and
  append `- YYYY-MM-DD <requirement ID>: [init] <decision>` with today's date to spec/decisions.md.
  Settling an open point is not adding behaviour.

Build none of the entries: write only what init.sh needs to run, if there is one.

## Only when kanban/features/ had no file

1. init.sh, only if something must be installed, started or built before the product can be used:
   it installs dependencies if missing, makes the product ready to use, prints where it is, exits
   0. An app: kill a stale server on its port, start it in the background, wait for a health
   endpoint with a timeout, print the URL and the log path. A command: build it, print how to run
   it. Files: print the command that writes them and where they land. Idempotent, non-interactive,
   independent of the working directory, executable. Run it once and see it exit 0.
2. progress.md with four sections: `## Current`, `## Log`, `## Gaps`, `## Findings`.
3. The `## Stack` and `## Run commands` sections of CLAUDE.md, filled in: Stack from the spec's
   Constraints only; Run commands: how to make the product ready (./init.sh, if there is one), how
   to run the tests, where the output and the log are.

## Commit

`git add -A && git commit -m "skift: initialize {{IDS}}"`, with exactly that message.

## Input

### Context
{{CONTEXT}}

### Requirements
{{REQUIREMENTS}}

### Decisions
{{DECISIONS}}
