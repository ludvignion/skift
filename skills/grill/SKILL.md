---
name: grill
description: Settle what spec/spec.md leaves open, in rounds of questions with recommended answers, asking only where two or more requirements depend on the answer and recording each answer verbatim in spec/decisions.md.
disable-model-invocation: true
---

# Grill

One run covers the whole spec. Rerun after a spec edit: what is already settled is never asked
again, so only what is newly open gets asked.

**Requirement ID.** The heading path below the `#` title, each heading with accented Latin letters
stripped to their base letter (å→a, ä→a, ö→o, é→e), lowercased, with every run of characters other
than a-z and 0-9 turned into `-` and `-` dropped at either end, joined with `/`: `## Features` ›
`### Accounts` › `#### Log in?` is `features/accounts/log-in`. A heading with a letter that has no
base letter (ø, ß, non-Latin) has no ID: scripts/loop.py refuses the spec until it is renamed.

## Steps

1. Run `grep -n '^#' spec/spec.md` for the headings and their line numbers. If the file is
   missing or no heading sits under `## Features`, there is nothing to grill: create nothing,
   commit nothing. Print the comment block from
   ${CLAUDE_PLUGIN_ROOT}/templates/project/spec/spec.md, then end with this line, alone:
   `Next: write requirements under ## Features in spec/spec.md, then /skift:grill`
2. Read spec/decisions.md; if it is absent, create it containing `# Decisions`. What it already
   records is settled: never ask it again.
3. Read the context sections (every top-level section except `## Features`) and the whole
   `## Features` subtree. If spec/spec.md is over 32000 characters (`wc -c`), read the Features
   text one top-level heading at a time, in spec order, keeping every heading in view. Every
   top-level heading under `## Features` must end in something the user does with or gets from the
   product. Flag a heading that names a layer (data model, API, validation, refactor) and ask for a
   rewrite before anything else. The first heading is the tracer bullet.
4. An open point is something the spec asks for whose user-visible outcome it leaves undecided.
   What the spec does not ask for is never an open point: never propose it, not even as a
   recommended answer. For each open point, first look for the line in the spec or the repo
   (src/, tests/, features.json, progress.md) that answers it; if one exists it is settled, never
   asked and never restated. Then count the requirements whose build depends on the answer. Fewer
   than two: not asked and not recorded; the initializer settles it. Two or more: ask.
5. Ask in numbered rounds of related questions, in descending order of that count. Each question
   stands on its own (never "as above"), lists the requirement IDs it affects, and carries a
   recommended answer: the simplest outcome that does what the spec says, adding nothing it does
   not ask for. Valid replies: an answer, "all recommended", or "decide it" (the recommended answer
   is recorded as `[grill]`). Never ask about naming, screen layout, technical choices, or
   anything under Out of scope. Print only the questions and, after each round, the lines just
   written to spec/decisions.md, verbatim.
6. Record each answer as one line with today's date, citing the most specific requirement IDs it
   settles, comma-separated, or `outline` when it holds across every requirement:
   `- YYYY-MM-DD <id>[,<id>...]: Q: <question as asked> A: <answer as given>`. Never reword it,
   never merge it with another line. For "all recommended", A is the recommended answer followed
   by ` (recommended)`. For "decide it":
   `- YYYY-MM-DD <id>[,<id>...]: [grill] <recommended answer>`.
7. Stop when nothing with a count of two or more is open. Commit:
   `git add spec/ && git commit -m "skift: grill"`. If nothing was open, commit nothing.
8. End with this line, alone: `Next: /skift:run`
