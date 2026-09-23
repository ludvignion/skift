---
name: tasks
description: Cut the indexed spec into tasks under kanban/tasks/, one workstream each: round 1 is one table (task, outcome, spec_refs, after) plus the sections to defer, every section exactly once, and you rank it; round 2 writes the task files and kanban/deferred.md and makes the coverage check green. It never edits the spec and never renumbers a task.
disable-model-invocation: true
argument-hint: "[first task number]"
---

# Tasks

Arguments: `$ARGUMENTS`, the number to start at; otherwise the next free number in kanban/tasks/.
Input: kanban/index.md and the spec it names, after `/skift:spec`. Output: one file per row under
kanban/tasks/, kanban/deferred.md, and `L --coverage` printing `0 problems`. A task is a workstream:
its own outcome, its own tickets, and `after` for the tasks it waits on. Tasks that wait on nothing
can be built in any order, or by different people.

`L` below stands for `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py" --project-dir "$PWD"`.

## Steps

1. Read kanban/index.md, then the spec: whole if `L --index` called it small, else section by
   section with `L --show` and `L --grep`. No index: print `Next: /skift:spec <your spec>` and stop.
   Read kanban/context.md and any task that already exists.
2. Round 1: print the two tables, letter the rows, and nothing else. End the turn there.

       | task | outcome | spec_refs | after |
       |---|---|---|---|
       | A | a customer places an order and the shopkeeper sees it | parts/orders, parts/cart | |
       | B | the shopkeeper refunds an order | parts/refunds | A |

       | deferred | reason | sections |
       |---|---|---|
       | purpose | why the product exists; no behaviour of its own | purpose |

   - Every section with text in the index (own above 0) appears exactly once, in one task's
     `spec_refs` or in one deferred row. Never twice, never missing. Count them before you answer.
     Citing a section covers everything under it, so a parent covers its children.
   - `outcome` is what a user can do, or a system shows, once the task is built: one sentence a
     tester could try. Never a code property: no "set up the data model", no "add validation", no
     "refactor X". Name the behaviour those would serve instead.
   - Row A is the tracer bullet: the thinnest task that crosses every layer the product touches and
     leaves something a user can see.
   - `after` names every task that must be built first. Where you are unsure, list the candidates;
     the user strikes the ones that are not real when they rank.
   - Defer a section only when no outcome a user can see could cite it: narrative, definitions,
     figures, strategy, roadmap, or context such as Purpose, Systems and Built with, which
     kanban/context.md already carries. The reason says which.
   - Do not number the tasks yet.
3. The user ranks: `go` keeps the table's order, `go, order: C, A, B` sets theirs. Answer anything
   else they say and print the table again.
4. Round 2: write one file per row, from `${CLAUDE_PLUGIN_ROOT}/templates/task.md`, at
   `kanban/tasks/<n>-<slug>.md`, numbered from the argument or the next free number, in the ranked
   order. `<slug>` is a short name in a-z, 0-9 and `-`. Frontmatter carries `spec_refs` and `after`
   from the table, with `after` naming task numbers. Fill Outcome, Why it matters, What is already
   decided (quoting the sections it cites), Open questions and Not this from the spec. Tasks that
   already exist keep their numbers and their files. Write kanban/deferred.md with one
   `- <section id> — <reason>` line per deferred section. The spec is never edited.
5. Run `L --coverage`. Every line it prints names a file and what is wrong: fix the task files or
   kanban/deferred.md, never the spec or the index, and run it again until it prints `0 problems`.
6. Commit: `git add kanban && git commit -m "skift: tasks"`.
7. End with one line per task, in build order, in plain words about the product: its number, its
   outcome, and what it waits for. Then this line, alone, with the first task's number:
   `Next: /skift:kanban <n>`
