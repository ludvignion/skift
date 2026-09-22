## Stack
<!-- Filled when the first feature is built, from the spec and kanban/context.md: language, framework, package manager, versions. -->

## Run commands
<!-- Filled when the first feature is built: how to make the product ready (./init.sh, if there is one), how to run the tests, where the output and the log are. -->

## Conventions
<!-- Filled when the first feature is built: what every later feature follows, such as the code structure, and for a UI the design direction and the one shared stylesheet every screen uses. -->

## Verification
<!-- Optional, yours to fill: a tool used from the shell to do a feature's steps as a user would, e.g. a Playwright for Python script for an app, curl for an API, a query for a database, running the command. Name the tool here and nowhere else. Left empty, a feature passes on its tests, and you check it yourself from its steps. -->

## Kanban
/skift:spec turns the spec (named in kanban/source.json) into kanban/map.md, every slice in build order,
and kanban/features/NN-<slice>.json, the features of the slices detailed so far. Nothing is built until
the user says what: one feature, one slice, or every open feature in build order, up to a slice if
they name one. Build exactly that, one feature at a time, each as below.

What binds you, and what is yours:
- The spec is the user's brief: what the product is for and what it must do. Read it whole; if it is
  over 60,000 characters, read kanban/map.md and kanban/index.md (every section with its file and
  lines) instead, then the sections the feature cites and those that bear on how it should be built,
  including those of the features that build on it. Build the feature the way the whole product
  needs it, not only the way its steps read.
- Binding: the spec's purpose and Out of scope, a stack or system the spec names, and in
  kanban/context.md the `## Answers` (the user's own words) and `## Systems` (what you may reach, and
  what must never change there). To go against one of these, ask.
- Yours: everything else. How the product works, its structure, data, look and quality. Where the
  spec, a feature's steps or an assumption says how something works and you see a better way to give
  the user what it is for, build the better way and record it under `## Deviations`. The
  `## Assumptions` in kanban/context.md were made before any code existed: defaults, not orders.
- No features the spec does not ask for; whatever makes the ones it asks for work well is part of
  building them. Design for the features after this one in kanban/map.md, and leave them unbuilt.
- Secrets are in .env: never print them, never commit them.

Before the first feature:
1. Run /skift:status. A feature marked `(spec changed)` is not built until /skift:spec updates it; a
   slice not detailed yet has no features until /skift:spec --next writes them. Tell the user which.
2. Read kanban/context.md, and in progress.md `## Current`, `## Deviations` and the last 20 lines of
   `## Log`, and `git log --oneline -20`. Earlier deviations are the design as built: build on them.
3. Run `./init.sh` if it exists, and the tests; if Verification names a tool, also do the steps of a
   feature that passes through it. Fix whatever fails first, and note it in `## Log`.
4. If Stack, Run commands or Conventions above is still empty, set the project up as you would, with
   the stack the spec and kanban/context.md name, and fill them. Conventions hold what every later
   feature follows. If the product must be started or built before it can be used, write
   `./init.sh`: it installs what is missing, makes the product ready, prints where it is (a URL, a
   command or an output path), and exits 0; idempotent, non-interactive, from any directory.

Each feature:
1. If `## Current` in progress.md names it, continue from its next step.
2. Build it fully and well, as you would if the product were yours, following Conventions. Write
   tests that check its steps.
3. Set its `passes` to true only when every step is built and the tests pass, and, if Verification
   names a tool, every step was done through it and observed. A step a deviation changed must hold as
   the deviation restates it. That flip is the only edit you make under kanban/.
4. Wherever you build differently than the spec, a feature's steps or an assumption says, append
   `- feature N: <what they said>; built instead: <what you built>; why: <why it serves the user
   better>` to `## Deviations` in progress.md, naming each step it changes and how it now reads.
   Changing Conventions is a deviation too.
5. Something a user would notice that neither the spec nor kanban/context.md settles: decide it as a
   good product would and append `- feature N: <the decision, in plain words>` to `## Decided`. Ask
   only when a wrong guess would cost rework beyond this feature and the answer turns on something
   only the user knows, or the better way goes against what binds you. Building one feature, ask the
   user now. Building several, append `- feature N: <question>` to `## Gaps`, leave `passes` false,
   and go on with the next feature that does not depend on it; ask at the end. Each answer goes to
   `## Answers` in kanban/context.md, and its line under `## Gaps` is deleted.
6. Anything you notice outside this feature goes to `## Findings` as `- feature N: <finding>`, not
   into the diff.
7. Overwrite `## Current` (feature id, done, left, next step), append
   `- YYYY-MM-DD feature N: <done, verified, left>` to `## Log`, and commit everything with a message
   naming feature N.
8. If a feature cannot be finished (stuck, or out of room), hand over as in 7 with `passes` false and
   stop there, saying why.

When done, tell the user about the product, never files or code: for each feature built, what they
can now do; how to open it (what `./init.sh` prints); its steps as boxes to tick; and its deviations
and decisions, to check too. Then what is not built and why, and the one thing to do next.
