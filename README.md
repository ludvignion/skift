# skift

A minimal Claude Code harness. A spec becomes a feature list; each feature is built and verified,
by using the running app, in its own fresh session. A driver opens every context window; agents never do.

1. `/skift:init` in an empty repo: copies the project template.
2. Fill Stack and Verification in `CLAUDE.md`; write `spec/spec.md`.
3. `/skift:grill`, then `/skift:grill <heading>` per section: answers land in `spec/decisions.md`.
4. `/skift:run`: cuts the spec into workloads, writes `features.json`, then builds one feature per session.
5. Follow `.skift/run.log`; answer `## Gaps` in `progress.md`; after adding spec headings, `/skift:run --append`.

Install:

    /plugin marketplace add ludvignion/skift
    /plugin install skift@skift

Priority is the order of `features.json`: the driver always builds the first feature that does not pass.
Reorder it to reprioritise.
