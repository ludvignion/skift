# skift

skift turns a spec into chunks of work that Claude builds, one per fresh session, in spec order.
`/skift:run` builds everything; `/skift:run --until <slice>` stops there so you can review. Nothing
gets built that the spec does not ask for, and nothing gets chosen that it does not name. Every
change to skift is checked against this paragraph.

The product is whatever the spec says the user gets: an app, a command, or files such as workbooks
and reports. A driver opens every context window; agents never do.

1. `/skift:init` in a new or existing repo: copies the project template, adding only what an existing
   `CLAUDE.md` or `.gitignore` lacks.
2. Write `spec/spec.md`, with Constraints saying what it is built with (`/skift:run` refuses empty
   Constraints). Verification in `CLAUDE.md` is optional: left empty, features pass on their tests.
3. `/skift:grill`, once for the whole spec: it asks only where a wrong guess would cost rework across
   features, and records each answer verbatim in `spec/decisions.md`. Reply "enough" to stop it.
4. `/skift:run`: cuts the spec into workloads, writes the features, then builds one feature per session.
5. Follow `.skift/run.log`. Answer `## Gaps` in `progress.md`, deleting each gap's line once answered
   (the driver skips a feature while its gap is there); after adding spec headings, `/skift:run --append`.

Install:

    /plugin marketplace add ludvignion/skift
    /plugin install skift@skift

Features live in `kanban/features/<slice-id>.json`, one file per top-level heading under `## Features`.
`/skift:run --status` lists every feature under its slice, passing or open, with gaps and findings.

Heading order in the spec is build order. `/skift:run --until <heading>` builds up to the end of that
slice and stops; the steps of each feature in it are your review checklist.

The driver always builds the first feature that does not pass, in spec order across slices and file
order inside a slice. Reorder a slice file, or move a heading in the spec, to reprioritise.

Tuning the grill: answers you accepted unchanged end in `(recommended)` in `spec/decisions.md`. If
most do, the grill asks too much; if you often change its recommendation, it asks too little.
