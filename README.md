# skift

You write the spec, or as much of it as you can. skift checks what you wrote against the six
sections it builds from and asks only for what is missing: nothing when the spec holds up, a few
questions when it nearly does, a full grill when it is an idea, notes or an empty file. Then it cuts
the spec into tasks you rank, and writes each task's tickets with acceptance criteria. Then it stops:
skift builds nothing. You tell Claude, in your own session, what to build: one ticket, one task, or
every open ticket in order. Claude builds each the way it would on its own, for the whole spec, not
only its ticket. The criteria fix what must hold: nothing the spec does not ask for. How it gets
built is Claude's call, even where the spec or an assumption says otherwise: Claude takes the better
way and tells you where. Claude never calls a ticket done; it sets it to in review, and you decide.
Every change to skift is checked against this paragraph.

It works for new products and for regular work in existing repos: apps, commands, files, and work
against databases, APIs and other systems. Several workstreams live side by side, each its own task
with its own tickets, and a one-off task can be written by hand without any spec at all. And it
works for specs of any size: a large one, such as a client document of hundreds of pages, is indexed
rather than read whole, and never rewritten.

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
   `.gitignore`, `spec/spec.md`, an empty `kanban/`), adding only what is missing, and never
   overwrites a file.
2. Write what you want in `spec/spec.md`, in the six sections it already holds: Purpose, Done looks
   like, Systems, Built with (optional), Parts in build order, Out of scope. Fill in as much as you
   can and leave the rest; a line, rough notes or an empty file are fine too, and a document of your
   own can go in `spec/` instead, where it is never rewritten. Never put secrets in it: the `.env`
   key name goes under Systems, the value in `.env`.
3. `/skift:grill [path]`. It indexes the spec and checks it in two layers, printing both:
   - fixed checks: is there anything to build from, does a six-section spec carry every section and
     a bullet under every part, and where are the vague words and anything that looks like a secret;
   - a trial run: Claude drafts the tasks and their criteria without writing anything, and every
     place it would have to guess, where the guess would change what gets built, is a gap, with the
     line, the guess and the rule it breaks.

   Then it asks in proportion to what it found: nothing when there are no gaps, one round of at most
   five questions for a few narrow ones, and a full grill — round after round until the six sections
   hold up — for an idea, notes or an empty file. Your answers go into the spec, in your words, and
   what it settled itself into `kanban/context.md`, which every build reads.
4. `/skift:tasks`. Round 1 is one table — task, outcome, spec sections, what it comes after — plus
   the sections it would defer, each with a reason, and every section of the spec appears exactly
   once. Reply `go` for that order, or `go, order: C, A, B` for yours. Round 2 writes
   `kanban/tasks/<n>-<slug>.md` and `kanban/deferred.md`, and runs the coverage check until nothing
   is dropped, cited twice, or waiting on a task that does not exist.
5. `/skift:kanban <n>`, one task at a time (`--next N` for the next N that have none). It asks only
   the decisions a wrong guess would cost rework on, then writes
   `kanban/tickets/<n>.<m>-<slug>.md`: each a vertical slice, `<n>.1` the tracer bullet, each with
   acceptance criteria that a test can name or that are tagged `(human)`, and each criterion citing
   the spec sections it comes from.
6. Tell Claude what to build, in your own session, in your own words:
   - `build ticket 1.2`: that ticket, then it stops and reports;
   - `build task 1`: every open ticket of that task, in order;
   - `build everything open`: in build order, honouring `after` and `depends_on`, one commit per
     ticket, one report at the end.

   How Claude builds a ticket is in the `## Kanban` section of `CLAUDE.md`, which `/skift:init`
   adds. It sets a ticket to `in_review` when the criteria a test can name hold; you tick the
   `(human)` ones and set `status: done` yourself.
7. Optional: fill Verification in `CLAUDE.md` with a tool Claude uses from the shell to run a
   ticket's criteria as a user would (a Playwright for Python script, curl, a database query). Left
   empty, a ticket rests on its tests and you confirm the rest from its criteria.

## Commands

| Command | What it does |
| --- | --- |
| `/skift:init` | Copy the project template, adding only what is missing. |
| `/skift:grill [path]` | Check the spec, ask only for what is missing, write it into the spec, and write `kanban/context.md`. A spec that holds up gets no questions. |
| `/skift:tasks [first number]` | Cut the spec into tasks: one table you rank, then the task files and `kanban/deferred.md`. |
| `/skift:kanban <n>` or `--next [N]` | Write one task's tickets, with acceptance criteria. |
| `/skift:status` | The board: every task, its tickets and their status, the tasks with no tickets, the deferred sections, and what the spec changed under. Starts nothing. Claude runs it before it builds. |

## Tasks, tickets and criteria

- A **task** is one workstream: `kanban/tasks/<n>-<slug>.md`, with the spec sections it covers in
  `spec_refs`, the tasks it waits for in `after`, an outcome a tester could try, and what is not it.
  Tasks that wait on nothing are independent, so several can run side by side. A task you write by
  hand, with no `spec_refs`, is a one-off job that needs no spec.
- A **ticket** is one sitting's work: `kanban/tickets/<n>.<m>-<slug>.md`, with `status`,
  `depends_on`, the paths it may write, an outcome, acceptance criteria and what it leaves to
  another ticket.
- A **criterion** is `behavioral` (Given / When / Then), `property` (what always holds), `critical`
  (what must never happen) or `human` (what only a person can confirm). Everything but `human` is
  written so a test can name it. Each ends with the spec sections it comes from, in brackets, and a
  section that no criterion cites is refused: that is how the requirements stay tied to the spec.
- **Status** runs `ready` → `in_progress` → `in_review` → `done`. Claude never sets `done`.

## What a build ends with

When Claude has built what you asked, it tells you, about the product and never about files or code:

- **What you can do now**: one line per ticket built, in plain words.
- **Open it**: where the product is, from `./init.sh`, which the first ticket writes when the
  product must be started or built before it can be used.
- **Check it**: each ticket's `(human)` criteria as boxes to tick.
- **Built differently than the spec says**: where Claude took a better way than the spec, a
  criterion or an assumption said, why, and how the criteria it changed now read. Check these too.
- **Decided for you**: what Claude settled that the spec left open. Check these too.
- **Not built**: what is left, and why: waiting for your answer, stuck, or not started.
- **Next**: the one thing to do next.

Building one ticket, Claude asks you directly when only you can answer. Building several, it writes
the question under `## Gaps` in `progress.md`, goes on with the tickets that do not depend on it,
and asks at the end; your answer goes to `kanban/context.md`. A ticket it cannot finish is handed
over under `## Current` in `progress.md`, and the next build continues from there.

## Large specs and spec changes

`/skift:grill` indexes the spec by its headings into `kanban/index.md`: one line per section, with an
id (a requirement id such as `REQ-12` in the heading, else the heading path), its lines and its first
line. A long section with no subheadings is cut into parts. A large spec is never read whole: the
index is the map, and sections are opened one at a time. Every section with text of its own lands in
exactly one task or on one line of `kanban/deferred.md` with a reason, and the coverage check
refuses anything else, so nothing in the spec is dropped in silence.

Each section's hash is recorded when the tickets are written. After a spec edit, `/skift:status`
marks every task and ticket whose sections changed and lists sections new in the spec that no task
covers. Claude builds none of the marked tickets until you rerun `/skift:grill`, then `/skift:kanban`
for the tasks it named. When a client sends a new version, replace the files and start again from
`/skift:grill`.

## Files

- `spec/spec.md`, or your own path or folder: the spec, in six sections: Purpose, Done looks like,
  Systems, Built with, Parts in build order, Out of scope. Yours to write, and `/skift:grill` fills
  in what you left out. A document you brought is never edited; what it lacks is written beside it.
- `kanban/index.md`: the spec's sections, generated. `kanban/source.json`: which spec, and each
  section's hash when the tickets were written. `kanban/deferred.md`: the sections no task covers,
  each with a reason.
- `kanban/tasks/<n>-<slug>.md`, `kanban/tickets/<n>.<m>-<slug>.md`: the workstreams and their
  requirements. Reorder by renaming; the numbers are the build order.
- `kanban/context.md`: the purpose, what it is built with, the systems, your answers and skift's
  assumptions, each with its reason. Claude reads it for every ticket, and answers and assumptions
  bind: a ticket that needs one changed says so, and the line here changes first.
- `progress.md`: `## Current` (the handover), `## Log`, `## Decided`, `## Deviations`, `## Gaps` and
  `## Findings`.
- `CLAUDE.md`: Stack, Run commands and Conventions, filled when the first ticket is built;
  Verification, yours; Kanban, how Claude builds a ticket.
- `.env`: secrets, never committed.

From 0.9 or earlier: the slices in `kanban/map.md` and the features in `kanban/features/` are not
read any more. Rerun `/skift:init`, then `/skift:grill`, `/skift:tasks` and `/skift:kanban`, and
delete the old files once the board looks right.
