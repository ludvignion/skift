---
name: grill
description: Settle the user-visible behaviour of spec/spec.md, one functional question at a time, recording each answer as a line in spec/decisions.md.
disable-model-invocation: true
argument-hint: "[heading]"
---

# Grill

Scope: `$ARGUMENTS`. Empty means the outline; otherwise one heading of spec/spec.md, by its text or
its requirement ID.

**Requirement ID.** The heading path below the `#` title, each heading lowercased with every run of
characters other than a-z and 0-9 turned into `-`, joined with `/`: `## Features` › `### Accounts`
› `#### Log in` is `features/accounts/log-in`.

## Steps

1. Read spec/decisions.md; if it is absent, create it containing `# Decisions`. What it already
   records is settled: never ask it again.
2. Load only what the scope needs. Run `grep -n '^#' spec/spec.md` for the headings and their
   line numbers.
   - No scope: the headings are all you read. Settle cross-cutting behaviour: what holds across
     features. Cite each decision as `outline`.
   - A scope: read that heading's lines up to the next heading of the same or higher level, and
     the context sections (every top-level section except `## Features`). Never load the rest of
     the spec. Cite each decision with the most specific requirement ID it settles.
3. For every user-visible behaviour in scope: where the spec already answers it, record that
   answer without asking. Ask only where it does not.
4. Ask one question at a time and wait for the answer. Functional only: what a user does, sees
   or gets. If a user would not notice the difference, it is technical: never ask it and never
   record it. No options menus; you may say which answer you would give.
5. Append each answer to spec/decisions.md as one line, in the user's meaning:
   `- YYYY-MM-DD <requirement ID or outline>: <decision>` with today's date.
6. Stop when no user-visible behaviour in scope is ambiguous, and say so in one line. Commit:
   `git add spec/ && git commit -m "skift: grill <requirement ID or outline>"`.
7. End with a single line, alone. The next uncovered heading is the first heading under
   `## Features`, in document order, that no decision cites, neither by its ID nor by an ID under
   it:
   `Next: /skift:grill <next uncovered heading>`, or `Next: /skift:run` when all sections are covered.
