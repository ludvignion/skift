---
name: kanban
description: Turn one task into its tickets under kanban/tickets/, each a vertical slice with acceptance criteria that are machine-verifiable or tagged (human), citing the spec sections they come from. Asks only the decisions a wrong guess would cost rework on, and builds nothing.
disable-model-invocation: true
argument-hint: "<task number> | --next [N]"
---

# Kanban

Arguments: `$ARGUMENTS`. A task number writes that task's tickets; `--next [N]` (N is 1 when left
out) takes the next N tasks that have no tickets yet, in build order. Input:
kanban/tasks/<n>-<slug>.md and the spec sections it cites. Output: kanban/tickets/<n>.<m>-<slug>.md
and a green `L --record`. You write requirements here, never code: what must hold, never how.

`L` below stands for `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py" --project-dir "$PWD"`.

## Steps

1. Run `L --status`. Read the task file, kanban/context.md, CLAUDE.md, the tickets of the tasks it
   comes after, and the repo as far as the task touches it. Read every section the task cites, with
   `L --show <id> ...`, and enough of the rest of the spec to know what the tickets after this one
   will need. A task marked `(spec changed)`: rerun `/skift:grill` first and say so.
2. Settle what the tickets rest on, evidence first: the repo and the spec answer most of it. Ask the
   user only where a wrong guess would cost rework beyond one ticket and the answer turns on
   something only they know: what the user of this task sees, which of two behaviours is meant,
   where the task's edge lies. Never ask how to build it. Ask in numbered rounds of related
   questions, at most 5 a round and at most 2 rounds; past that, say the task is too big and propose
   where to split it. Give a recommended answer only where the spec, the repo or common practice
   makes one clearly better; where the choice is the user's alone, give the options and recommend
   none. Everything you settle yourself that a user would notice goes into kanban/context.md under
   `## Assumptions`, and every answer they give under `## Answers`, dated.
3. Cut the task into tickets, each a vertical slice: it crosses every layer it touches and can be
   shown working on its own. Ticket `<n>.1` is the tracer bullet, the thinnest slice that proves the
   whole path. A ticket is one sitting's work. Never a ticket for setup, a data model, a refactor or
   "tests": that work belongs inside the first ticket that needs it.
4. Write each one from `${CLAUDE_PLUGIN_ROOT}/templates/ticket.md` at
   `kanban/tickets/<n>.<m>-<slug>.md`, `<m>` counting from 1 within the task, in build order:
   - `status: ready`, `depends_on` naming the tickets inside or before this task it needs, `writes`
     naming the paths a build may touch where the repo makes that clear, else empty.
   - `## Outcome`: what a user can do, or a system shows, once it is built.
   - `## Acceptance criteria`: each one `- AC-<k> (behavioral|property|critical|human): ...`, and
     each ending in the spec sections it comes from, in brackets: `[parts/orders]`.
     - behavioral: Given a state, When an action, Then what is observable.
     - property: for all inputs of a kind, what always holds.
     - critical: what must never happen, and what happens instead.
     - human: what only a person can confirm — how a page looks, whether the tone fits, a call to a
       live system. Tag it, and nobody writes a test for it.
     - Every criterion but a `(human)` one is one a test can name. Where you cannot write it that
       way, either sharpen it or tag it `(human)`.
     - Together, the task's tickets cite every section the task's `spec_refs` hold. `L --record`
       refuses a section no criterion cites.
   - `## Out of scope`: what this ticket does not do, and which ticket does.
   - `## Notes`: only what the build must know, such as a decision from step 2.
5. Run `L --record`. It checks the tickets against the spec, records each section's hash, makes sure
   progress.md exists and prints the board. Fix every line it prints and run it again until it is
   green. On a rerun for a task whose sections changed, rewrite the tickets those sections feed;
   leave a ticket that is `done` alone unless the change alters what it does, and say so if it does.
6. Commit: `git add kanban progress.md && git commit -m "skift: tickets for task <n>"`.
7. End with, in plain words about the product, never about files or code: one line per ticket in
   build order, what the user will be able to do; which criteria only a person can confirm; what you
   decided for them. Then this line, alone:
   `Next: tell Claude what to build, such as "build ticket <n>.1" or "build every open ticket of task <n>"`
