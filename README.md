# skift

You write what you want in a Markdown file. `/skift:spec` reads it and your repo, asks only for the
context that is missing, and turns it into kanban features, then stops: skift builds nothing. You
tell Claude, in your own session, what to build: one feature, one slice, or every open feature in
order. Claude builds each the way it would on its own, for the whole spec, not only its feature. The
spec fixes what gets built: nothing it does not ask for. How it gets built is Claude's call, even
where the spec or an assumption says otherwise: Claude takes the better way and tells you where.
Every build ends with what you can now do and what to check. Every change to skift is checked
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
   and ends with each slice in plain words. Review them; nothing is built yet.
4. Tell Claude what to build, in your own session, in your own words:
   - `build feature 3`: that feature, then it stops and reports;
   - `build slice 01-orders`: every open feature of that slice;
   - `build every open feature up to slice 02`, or `build everything`: in build order, one commit
     per feature, and one report at the end.
   How Claude builds a feature is in the `## Kanban` section of `CLAUDE.md`, which `/skift:init`
   adds. When the next slice has no features yet, run `/skift:spec --next`, which writes them.
5. Optional: fill Verification in `CLAUDE.md` with a tool Claude uses from the shell to do a
   feature's steps as a user would (a Playwright for Python script, curl, a database query). Left
   empty, a feature passes on its tests and you check it yourself from its steps.

## Commands

| Command | What it does |
| --- | --- |
| `/skift:init` | Copy the project template, adding only what is missing. |
| `/skift:spec [path]` | Turn the spec into the map and the features, asking only for what is missing. |
| `/skift:spec --next [N]` | Write the features of the next N slices that have none yet (default 1). |
| `/skift:status` | List every feature under its slice: passing or open, gaps, findings, deviations, and the features the spec changed under. Starts nothing. Claude runs it before it builds. |

## What a build ends with

When Claude has built what you asked, it tells you, about the product and never about files or code:

- **What you can do now**: one line per feature built, in plain words.
- **Open it**: where the product is, from `./init.sh`, which the first feature writes when the
  product must be started or built before it can be used.
- **Check it**: each feature built, with its steps as boxes to tick.
- **Built differently than the spec says**: where Claude took a better way than the spec, a step or
  an assumption said, why, and how the steps it changed now read. Check these too.
- **Decided for you**: what Claude settled that the spec left open. Check these too.
- **Not built**: what is left, and why: waiting for your answer, stuck, or not started.
- **Next**: the one thing to do next.

Building one feature, Claude asks you directly when only you can answer. Building several, it writes
the question under `## Gaps` in `progress.md`, goes on with the features that do not depend on it,
and asks at the end; your answer goes to `kanban/context.md`. A feature it cannot finish is handed
over under `## Current` in `progress.md`, and the next build continues from there.

## Large specs and spec changes

`/skift:spec` indexes the spec by its headings into `kanban/index.md`: one line per section, with an
id (a requirement id such as `REQ-12` in the heading, else the heading path), its lines and its first
line. A long section with no subheadings is cut into parts. A large spec is never read whole: the
index is the map, and sections are opened one at a time. `kanban/map.md` places every section with
text in a slice, in Context or in Out of scope; `/skift:spec` refuses a map or features that drop a
section. Building a feature, Claude reads the sections it cites and the rest of the spec, so it
builds for the whole product: a small spec whole, a large one through the index.

Each section's hash is recorded when the features are written. After a spec edit, `/skift:status`
marks the features whose cited sections changed and lists sections new in the spec that no slice
covers, and Claude builds none of those features until you rerun `/skift:spec`, which updates
exactly them. When a client sends a new version, replace the files and rerun `/skift:spec`.

## Files

- `spec/spec.md` (or your own path): what you want, in your words. skift never edits it.
- `kanban/context.md`: systems, your answers, assumptions. Claude reads it for every feature: your
  answers and the systems bind it, the assumptions are defaults it may build differently, saying why.
- `kanban/map.md`: every slice in build order with the sections it covers, plus Context and Out of
  scope.
- `kanban/features/NN-<slice>.json`: the features of the detailed slices, each with an id, a
  description, steps (your review checklist), the sections it cites, and `passes`. Reorder slices by
  renaming, features by moving them in a file.
- `kanban/index.md`: the spec's sections, generated; `kanban/source.json`: which spec, and each
  section's hash when the features were written.
- `progress.md`: `## Current` (the handover), `## Log`, `## Decided`, `## Deviations`, `## Gaps` and
  `## Findings`.
- `CLAUDE.md`: Stack, Run commands and Conventions, filled when the first feature is built;
  Verification, yours; Kanban, how Claude builds a feature.
- `.env`: secrets, never committed.

From 0.7 or earlier: rerun `/skift:init` to add the `## Kanban` section to `CLAUDE.md`, then delete
its old `## Rule` section and the `.skift/` folder.
