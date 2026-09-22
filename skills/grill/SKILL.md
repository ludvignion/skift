---
name: grill
description: Settle the user-visible behaviour of spec/spec.md in rounds of questions with recommended answers, recording each decision as a line in spec/decisions.md.
disable-model-invocation: true
argument-hint: "[heading]"
---

# Grill

Scope: `$ARGUMENTS`. Empty means the outline; otherwise one heading of spec/spec.md, by its text or
its requirement ID.

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
3. Load only what the scope needs.
   - No scope: read the context sections (every top-level section except `## Features`); of
     `## Features`, read only the headings. Every top-level heading under `## Features` must end
     in something a user can do in the app. Flag a heading that names a layer (data model, API,
     validation, refactor) and ask for a rewrite before anything else. The first heading is the
     tracer bullet. Settle cross-cutting behaviour: what holds across features. Cite each
     decision as `outline`.
   - A scope: read that heading's lines up to the next heading of the same or higher level, and
     the context sections (every top-level section except `## Features`). Never load the rest of
     the spec. Cite each decision with the most specific requirement ID it settles.
4. For every open point: search src/, tests/, features.json, progress.md and spec/decisions.md
   first; what the repo or the spec already answers is settled, never asked and never restated.
   Then apply one test: would the user notice the difference in the running app? No: decide it,
   record it as `[grill]`, never show it. Yes: ask.
5. Ask in numbered rounds of related questions, each with a recommended answer; "all
   recommended" is a valid reply. No cap, no floor. Never ask about naming, layout, technical
   choices, or anything under Out of scope. Print only the questions and the Next line.
6. Append each decision to spec/decisions.md as one line, in the user's meaning:
   `- YYYY-MM-DD <requirement ID or outline>: <decision>` with today's date. A decision you made
   yourself starts with `[grill] `: `- YYYY-MM-DD <requirement ID or outline>: [grill] <decision>`.
7. Stop when nothing in scope is open. If the scope had nothing open, so this run appended no
   line, append one line `- YYYY-MM-DD <requirement ID or outline>: [grill] nothing open` so the
   scope counts as covered. Commit:
   `git add spec/ && git commit -m "skift: grill <requirement ID or outline>"`.
8. End with a single line, alone. The next uncovered heading is the first heading under
   `## Features`, in document order, that no decision cites, neither by its ID nor by an ID under
   it:
   `Next: /skift:grill <next uncovered heading>`, or `Next: /skift:run` when all sections are covered.
