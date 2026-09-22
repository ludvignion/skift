# skift

You write what you want in a Markdown file. `/skift:spec` reads it and your repo, asks only for the
context that is missing, and turns it into kanban features. `/skift:run` builds them, one fresh
Claude session per feature, and Claude builds each the way it would on its own, for the whole spec,
not only its feature. The spec fixes what gets built: nothing it does not ask for. How it gets built
is Claude's call, even where the spec or an assumption says otherwise: Claude takes the better way
and the handoff tells you where. `--until` stops after a slice so you can review, and every run ends
with a handoff that says what you can now do and what to check. Every change to skift is checked
against this paragraph.

It works for new products and for regular work in existing repos: apps, commands, files, and work
against databases, APIs and other systems. And it works for specs of any size: a large one, such as a
client document of hundreds of pages, is indexed rather than read whole, mapped into slices at once,
and detailed into features one slice at a time.

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

1. `/skift:init` in a new or existing repo. It copies the project template (`CLAUDE.md`,
   `.gitignore`, `spec/spec.md`), adding only what is missing, and never overwrites a file.
2. Write what you want in `spec/spec.md`, or any `.md` file, in any shape. It helps to say what it
   is for, what done looks like, the systems it touches and what must never change there, what it
   is built with if you care, and what is out of scope. Never put secrets in it.
3. `/skift:spec [path]`, where the path is a `.md` file or a folder of them. It indexes the spec,
   reads it and the repo, then asks, in rounds with a recommended answer each, only what a wrong
   guess would make costly: access to databases and APIs, what must not change, what done looks
   like. Reply with an answer, "all recommended", "decide it", or "enough". Secrets go in `.env`
   under the keys it names. It writes:
   - `kanban/context.md`: the systems, your answers and its assumptions;
   - `kanban/map.md`: every slice of the whole spec in build order, each citing the spec sections it
     covers, plus what is context and what is out of scope;
   - `kanban/features/NN-<slice>.json`: the features of the slices detailed so far, each citing its
     sections. A small spec gets every slice detailed at once; a large one only the first.
   and ends with each slice in plain words and `Next: /skift:run --until <slice>`.
4. `/skift:run --until <first slice>`: builds that slice. When the run ends, your session prints the
   handoff. Check it, then run `--until` the next slice, or plain `/skift:run` for the rest. When the
   next slice has no features yet, the handoff says `/skift:spec --next`, which writes them.
5. Optional: fill Verification in `CLAUDE.md` with a tool a session uses from the shell to do a
   feature's steps as a user would (a Playwright for Python script, curl, a database query). Left
   empty, a feature passes on its tests and you check it yourself from the handoff.

## Running

| Command | What it does |
| --- | --- |
| `/skift:run` | Build every feature that does not pass, one fresh session each. |
| `/skift:run --until <slice>` | Build up to the end of that slice, then stop. The slice by file name (`01-orders`), name (`orders`) or number (`1`). |
| `/skift:run --status` | List every feature under its slice: passing or open, gaps, findings, deviations. Starts nothing. |
| `/skift:run --dry-run` | List the features a run would build, skip or refuse, and the slices not detailed yet. Starts nothing. |
| `/skift:spec --next [N]` | Write the features of the next N slices that have none yet (default 1). |
| `tail -f .skift/run.log` | Follow the running driver. |
| `kill -INT $(cat .skift/run.pid)` | Stop after the current session; send it again to stop at once. |

`/skift:run` starts the driver detached, so it keeps going if you close the session, plus a watcher
in your session that prints the handoff when the driver ends. If you closed the session, the handoff
waits in `.skift/handoff.md`. To continue after a stop, run `/skift:run` again: passing features are
skipped, and a feature left half-done resumes from `## Current` in `progress.md`.

More flags, with their defaults: `--max-iterations N` (sessions before stopping; no limit),
`--bypass` (sessions run with bypassPermissions instead of auto), `--model` (sonnet), `--max-turns`
(200 per session), `--max-sessions-per-feature` (3), `--session-timeout` (3600 seconds).

## The handoff

Every run ends with one, about the product, never about files or code:

- **What you can do now**: one line per feature built in this run, in plain words.
- **Open it**: where the product is, from `./init.sh`, which the driver runs when the run ends.
- **Check it**: each feature built, with its steps as boxes to tick.
- **Built differently than the spec says**: where a session took a better way than the spec, a
  step or an assumption said, why, and how the steps it changed now read. Check these too.
- **Decided for you**: what the sessions settled that the spec left open. Check these too.
- **Not built**: what is left, and why: waiting for your answer, stuck, or not started.
- **The spec changed**: built features whose sections changed, and sections new in the spec.
- **Next**: the one thing to do next.

A run stops when everything in scope passes; when every feature left waits for an answer (it asked
under `## Gaps` in `progress.md`: answer in `kanban/context.md`, delete the line, rerun); when one
feature fails 3 sessions in a row; or when you stop it.

## Large specs and spec changes

`/skift:spec` indexes the spec by its headings into `kanban/index.md`: one line per section, with an
id (a requirement id such as `REQ-12` in the heading, else the heading path), its lines and its first
line. A long section with no subheadings is cut into parts. A large spec is never read whole: the
index is the map, and sections are opened one at a time. `kanban/map.md` places every section with
text in a slice, in Context or in Out of scope; `--mark-spec` refuses a map or features that drop a
section. Each coding session gets the text of the sections its feature cites, and reads the rest so
it builds for the whole product: a small spec whole, a large one through the index.

Each section's hash is recorded when the features are written. After a spec edit, a run refuses
only the features whose cited sections changed, and says which; the rest build on. `--status` marks
them, and lists sections new in the spec that no slice covers. Rerun `/skift:spec` to update exactly
those. When a client sends a new version, replace the files and rerun `/skift:spec`.

## Files

- `spec/spec.md` (or your own path): what you want, in your words. skift never edits it.
- `kanban/context.md`: systems, your answers, assumptions. Every session reads it: your answers and
  the systems bind it, the assumptions are defaults it may build differently, saying why.
- `kanban/map.md`: every slice in build order with the sections it covers, plus Context and Out of
  scope.
- `kanban/features/NN-<slice>.json`: the features of the detailed slices, each with an id, a
  description, steps (your review checklist), the sections it cites, and `passes`. Reorder slices by
  renaming, features by moving them in a file.
- `kanban/index.md`: the spec's sections, generated; `kanban/source.json`: which spec, and each
  section's hash when the features were written.
- `progress.md`: `## Current` (the handover), `## Log`, `## Built`, `## Decided`, `## Deviations`,
  `## Gaps` and `## Findings`.
- `CLAUDE.md`: Stack, Run commands and Conventions, filled by the first session; Verification, yours.
- `.env`: secrets, never committed. `.skift/`: the driver's log, pid and handoff, ignored by git.
