# skift

skift turns a spec into chunks of work that Claude builds, one per fresh session, in spec order.
The first `/skift:run` writes the features and stops so you can review them; after that
`/skift:run` builds everything, and `/skift:run --until <slice>` stops there so you can review. Nothing
gets built that the spec does not ask for, and nothing gets chosen that it does not name. Every
change to skift is checked against this paragraph.

The product is whatever the spec says the user gets: an app, a command, or files such as workbooks
and reports. A driver script opens every context window; agents never do.

## Install

    /plugin marketplace add ludvignion/skift
    /plugin install skift@skift

To update, then restart the Claude session:

    claude plugin marketplace update skift
    claude plugin update skift@skift
    claude plugin list | grep -A2 skift

The list should show one skift entry at the latest version. An older entry with `Scope: project`
wins inside that project: remove it with `claude plugin uninstall skift@skift --scope project`.

## Use it

1. `/skift:init` in a new or existing repo. It copies the project template, adding only what an
   existing `CLAUDE.md` or `.gitignore` lacks, and never overwrites a file.
2. Write `spec/spec.md`:
   - Purpose: what the user gets (an app, a command, files).
   - Constraints: what it is built with (language, framework, libraries). Required: `/skift:run`
     refuses a spec whose Constraints are empty, and nothing is chosen for you.
   - Features: every heading with text of its own is one requirement, and that text says what a
     user does and sees. Each top-level heading is a slice; heading order is build order.
   - Out of scope: what must not be built.
3. Optional: fill Verification in `CLAUDE.md` with a tool a session uses from the shell to do a
   feature's steps as a user would (a Playwright for Python script, curl, running the command).
   Left empty, a feature passes on its tests and you check it yourself.
4. `/skift:grill`, once for the whole spec. It asks only where a wrong guess would cost rework across
   features, costliest first, each question with a recommended answer. Reply with an answer, "all
   recommended", "decide it", or "enough" to stop. Answers land verbatim in `spec/decisions.md`.
5. `/skift:run`: writes the features for the whole spec into `kanban/features/` and stops. Review
   them with `/skift:run --status` and the slice files; edit or reorder them if needed.
6. `/skift:run --until <first slice>`: builds that slice and stops. Check it against the steps of
   its features, then run `--until` the next slice, or plain `/skift:run` for the rest.

## Running

`/skift:run` starts the driver in the background and returns at once. When there are no features
yet, it writes them and stops. When there are, it builds every feature that does not pass, one fresh
session each.

| Command | What it does |
| --- | --- |
| `/skift:run` | No features yet: write them, then stop for review. Otherwise: build all that do not pass. |
| `/skift:run --until <slice>` | Build up to the end of that slice (heading text or ID), then stop. |
| `/skift:run --status` | List every feature under its slice: passing or open, gaps, findings. Starts nothing. |
| `/skift:run --dry-run` | Print the requirement IDs and workloads; with `--until`, the features it would build. Starts nothing. |
| `/skift:run --append` | After adding headings to the spec: write features for the new ones, then stop for review. |
| `tail -f .skift/run.log` | Follow the running driver. |
| `kill -INT $(cat .skift/run.pid)` | Stop after the current session; send it again to stop at once. |

To continue after a stop, run `/skift:run` again: passing features are skipped, and a feature left
half-done resumes from `## Current` in `progress.md`.

More flags, with their defaults: `--max-iterations N` (coding sessions before stopping; no limit),
`--bypass` (sessions run with bypassPermissions instead of auto), `--model` (sonnet), `--max-turns`
(200 per session), `--max-steps` (8 per feature), `--max-sessions-per-feature` (3),
`--session-timeout` (3600 seconds), `--spec-cap-tokens` (8000 of spec per initializer session).

## When it stops

- **Features written**: the log lists them per slice. Review `kanban/features/`, then run again to build.
- **All features pass**, or all up to `--until`: review, then run the next slice.
- **Gaps**: a session found the spec silent on something the user would see. It wrote the question
  under `## Gaps` in `progress.md` and the driver skips that feature. Answer it (in the spec or in
  `spec/decisions.md`), delete the gap's line, and rerun.
- **Stuck**: one feature ran 3 sessions in a row without passing. Read `## Current` and `## Log` in
  `progress.md`, fix the cause or the feature, and rerun.
- **Spec edited under existing features**: the driver lists the affected features. Edit them in
  their slice file, or remove them and rerun with `--append`; then acknowledge with
  `git commit --allow-empty -am "skift: reviewed <requirement IDs>"`.

## Files

- `spec/spec.md`: your spec. `spec/decisions.md`: grill answers, plus `[init]` lines for small open
  points the initializer settled.
- `kanban/features/<slice-id>.json`: the features of one slice, each with its requirement ID,
  description, steps and `passes`. The steps are your review checklist.
- `progress.md`: `## Current` (the handover), `## Log`, `## Gaps` and `## Findings`.
- `CLAUDE.md`: Stack and Run commands, filled by the initializer; Verification, yours; the Rule.
- `init.sh`: only when something must be installed, started or built before the product can be used.
- `.skift/`: the driver's log and pid, ignored by git.

## Order and priority

The driver always builds the first feature that does not pass, in spec order across slices and file
order inside a slice. Reorder a slice file, or move a heading in the spec, to reprioritise.

## Tuning the grill

Answers you accepted unchanged end in `(recommended)` in `spec/decisions.md`. If most do, the grill
asks too much; if you often change its recommendation, it asks too little.
