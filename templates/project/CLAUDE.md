## Stack
<!-- Filled when the first ticket is built, from the spec and kanban/context.md: language, framework, package manager, versions. -->

## Run commands
<!-- Filled when the first ticket is built: how to make the product ready (./init.sh, if there is one), how to run the tests, where the output and the log are. -->

## Conventions
<!-- Filled when the first ticket is built: what every later ticket follows, such as the code structure, and for a UI the design direction and the one shared stylesheet every screen uses. -->

## Verification
<!-- Optional, yours to fill: a tool used from the shell to do a ticket's acceptance criteria as a user would, e.g. a Playwright for Python script for an app, curl for an API, a query for a database, running the command. Name the tool here and nowhere else. Left empty, a ticket rests on its tests, and you confirm the rest yourself. -->

## Kanban
skift turned the spec into tasks in kanban/tasks/<n>-<slug>.md, each citing the spec sections it
covers, and tickets in kanban/tickets/<n>.<m>-<slug>.md, each with acceptance criteria. Nothing is
built until the user says what: one ticket, one task, or every open ticket in order. Build exactly
that, one ticket at a time, each as below.

What binds you, and what is yours:
- The ticket's acceptance criteria say what must hold. The task's Outcome and Not this say what it
  is for. The spec is the brief behind both: read it whole, or, if it is over 60,000 characters,
  read kanban/index.md (every section with its file and lines) and open the sections the ticket's
  criteria cite in brackets, plus what bears on how it should be built.
- Binding: the acceptance criteria, the spec's purpose and Out of scope, a stack or system the spec
  names, `writes:` on the ticket where it is set, and in kanban/context.md the `## Answers` (the
  user's own words) and `## Systems` (what you may reach, and what must never change there). To go
  against one of these, ask.
- Yours: everything else. How the product works, its structure, data, look and quality. Where the
  spec, a criterion or an assumption says how something works and you see a better way to give the
  user what it is for, build the better way and record it under `## Deviations`. The
  `## Assumptions` in kanban/context.md were made before any code existed: defaults, not orders.
- Nothing the spec does not ask for; whatever makes the criteria hold well is part of building them.
  Design for the tickets after this one, and leave them unbuilt.
- Secrets are in .env: never print them, never commit them.

Before the first ticket:
1. Run /skift:status. A ticket marked `(spec changed)` is not built until /skift:grill and
   /skift:kanban update it; a task with no tickets yet needs /skift:kanban <n>. Say which.
2. Read kanban/context.md, and in progress.md `## Current`, `## Deviations` and the last 20 lines of
   `## Log`, and `git log --oneline -20`. Earlier deviations are the design as built: build on them.
3. Run `./init.sh` if it exists, and the tests. If Verification names a tool, also run the criteria
   of a ticket that is done through it. Fix whatever fails first, and note it in `## Log`.
4. If Stack, Run commands or Conventions above is still empty, set the project up as you would, with
   the stack the spec and kanban/context.md name, and fill them. Conventions hold what every later
   ticket follows. If the product must be started or built before it can be used, write `./init.sh`:
   it installs what is missing, makes the product ready, prints where it is (a URL, a command or an
   output path), and exits 0; idempotent, non-interactive, from any directory.

Each ticket, in the order the user asked for (a ticket waits for the ones in its `depends_on`, and a
task for the ones in its `after`):
1. Set `status: in_progress` in the ticket. If `## Current` in progress.md names it, continue from
   its next step.
2. Build it fully and well, as you would if the product were yours, following Conventions. Write
   tests that name each criterion that is not tagged `(human)`.
3. Set `status: in_review` only when every criterion but the `(human)` ones is built and its test
   passes, and, if Verification names a tool, you did them through it and saw them hold. You never
   set `done`: the user does that after checking the `(human)` criteria. The ticket's status is the
   only edit you make under kanban/.
4. Wherever you build differently than the spec, a criterion or an assumption says, append
   `- ticket <n>.<m>: <what they said>; built instead: <what you built>; why: <why it serves the
   user better>` to `## Deviations` in progress.md, naming each criterion it changes and how it now
   reads. Changing Conventions is a deviation too.
5. Something a user would notice that neither the spec nor kanban/context.md settles: decide it as a
   good product would and append `- ticket <n>.<m>: <the decision, in plain words>` to `## Decided`.
   Ask only when a wrong guess would cost rework beyond this ticket and the answer turns on
   something only the user knows, or the better way goes against what binds you. Building one
   ticket, ask now. Building several, append `- ticket <n>.<m>: <question>` to `## Gaps`, leave the
   status as it was, go on with the next ticket that does not depend on it, and ask at the end. Each
   answer goes to `## Answers` in kanban/context.md, and its line under `## Gaps` is deleted.
6. Anything you notice outside this ticket goes to `## Findings` as `- ticket <n>.<m>: <finding>`,
   not into the diff.
7. Overwrite `## Current` (ticket id, done, left, next step), append
   `- YYYY-MM-DD ticket <n>.<m>: <done, verified, left>` to `## Log`, and commit everything with a
   message naming the ticket.
8. If a ticket cannot be finished (stuck, or out of room), hand over as in 7, set the status back to
   `ready`, and stop there, saying why.

## Decisions
kanban/context.md holds the purpose, what it is built with, the systems, the answers the user
gave and the assumptions skift made. Read it before building any ticket. Answers and assumptions
bind: a ticket that needs one changed says so under its `## Notes` when set to in_review, and the
line in context.md changes before the ticket does. Any skill that keeps a decisions file uses
kanban/context.md. Never create spec/decisions.md.

When done, tell the user about the product, never files or code: for each ticket built, what they
can now do; how to open it (what `./init.sh` prints); its `(human)` criteria as boxes to tick; and
its deviations and decisions, to check too. Then what is not built and why, and the one thing to do
next. Say that a ticket they are happy with becomes `status: done`.
