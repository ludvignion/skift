# skift

A minimal Claude Code harness. A spec becomes a feature list; each feature is built and verified,
by using the running app, in its own fresh session. A driver opens every context window; agents never do.

1. `/skift:init` in a new or existing repo: copies the project template, adding only what an existing
   `CLAUDE.md` or `.gitignore` lacks.
2. Fill Verification in `CLAUDE.md`; write `spec/spec.md`. The initializer fills Stack from its Constraints.
3. `/skift:grill`, then `/skift:grill <heading>` per section: answers land in `spec/decisions.md`.
4. `/skift:run`: cuts the spec into workloads, writes `features.json`, then builds one feature per session.
5. Follow `.skift/run.log`; answer `## Gaps` in `progress.md`, deleting each gap's line once answered (the
   driver skips a feature while its gap is there); after adding spec headings, `/skift:run --append`.

Install:

    /plugin marketplace add ludvignion/skift
    /plugin install skift@skift

Heading order in the spec is build order: the initializer writes `features.json` in that order.
`/skift:run --until <heading>` builds up to the end of that slice and stops.

Priority is the order of `features.json`: the driver always builds the first feature that does not pass.
Reorder it to reprioritise.
