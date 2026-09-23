---
name: spec
description: Check a spec of any size, in any Markdown (one file or a folder), against what skift needs to build from, have a grill write whatever is missing, index it, and record the systems and answers in kanban/context.md. It writes no tasks and no tickets; /skift:tasks does that next.
disable-model-invocation: true
argument-hint: "[spec .md file or folder, default spec/spec.md]"
---

# Spec

Arguments: `$ARGUMENTS`. The spec is the path given, or spec/spec.md. The user never writes the spec:
they bring what they have, from nothing or a one-line idea to a client document of any size, and you
have the grill write what is missing. This skill stops at a spec that holds enough to build from;
`/skift:tasks` cuts it into tasks and `/skift:kanban` writes a task's tickets.

`L` below stands for `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py" --project-dir "$PWD"`.

## Steps

1. Read `${CLAUDE_PLUGIN_ROOT}/templates/spec-standard.md`: S1-S6 and the rules for every statement
   are what you check against, and the shape the grill writes in.
2. If the spec exists and holds text, run `L --index <spec>`. It says whether the spec is small or
   large:
   - small: read the spec whole.
   - large: never read it whole. Read kanban/index.md, open sections with `L --show <id> ...`, find
     them with `L --grep <regex>`.
3. Read what exists: kanban/context.md, kanban/tasks/, kanban/tickets/, CLAUDE.md, progress.md, and
   the repo as far as the spec touches it: README, dependency manifests, configuration, schemas and
   migrations, the code the spec will change. When tasks exist, run `L --status`. Never open .env or
   print a secret; list only the keys it has: `grep -o '^[A-Za-z_][A-Za-z0-9_]*=' .env`.
4. Check the spec, in two layers.
   - Run `L --check-spec <spec>`: the checks that come out the same every run. It refuses a spec
     with nothing to build from, and for a spec in skift's shape it checks that each heading is
     there and that each part carries a `Done:` check. It also lists vague words and anything that
     looks like a secret, with their lines.
   - Then the trial run, which you do in your head and write nothing for: draft the tasks the spec
     would cut into, and for each task the acceptance criteria its tickets would carry. Every place
     you would have to guess, where the guess would change what gets built or how it is checked, is
     a gap: write down the spec line or section id, the guess, and the item it breaks (S1-S6 or a
     rule). What the repo already settles is not a gap.
5. Print the verdict, and nothing else about it:

       Spec check: grill needed (3 gaps)
       - S2 parts/orders: "manage orders" — create and cancel, or edit and refund too?
       - S3 parts/reports: no check — which columns, and what a correct total looks like
       - vague: spec.md:14 "fast"

   With no gaps, print `Spec check: clean` and go to step 7.
6. Have the missing parts written. The user never fills them in themselves.
   - Invoke the `grill` skill on the spec, and give it the standard, the gaps above, and what the
     repo already settles, so it does not ask about that.
   - Without a grill skill, do it yourself: ask in numbered rounds of related questions, costliest
     to get wrong first, at most 5 a round. Give a recommended answer only where the spec, the repo
     or common practice makes one clearly better; where the choice is the user's alone, give the
     options and recommend none. Valid replies: an answer, "all recommended" (each question that has
     one takes it), or "decide it" (you decide, and it becomes an assumption in step 8).
   - Where it lands: in the spec itself when skift wrote it, or when it is small enough to rewrite
     whole. A document the user brought is never rewritten: write what is missing beside it as
     `spec/<name>-additions.md`, citing the sections it completes, and from then on the spec is the
     folder that holds both.
   - Then run `L --index <spec>` and `L --check-spec <spec>` again and redo the trial run, until the
     verdict is clean. Never grill twice in one run: if gaps are left after one pass, print them and
     stop.
7. Ask what the spec cannot hold, in rounds as in step 6: how to reach each system it names, which
   data is safe to read or write, and which `.env` keys hold its secrets. Never ask for a secret's
   value; ask the user to put it in .env under the keys you name, and check that .env is in
   .gitignore.
8. Write kanban/context.md, keeping what is already there:
   - `## Systems`: each system the work touches, how to reach it, the .env keys it needs (never
     their values), and what must never change there;
   - `## Answers`: each answer as `- YYYY-MM-DD Q: <question as asked> A: <answer as given>`; for
     "all recommended", A is the recommended answer followed by ` (recommended)`. Answers bind every
     ticket built;
   - `## Assumptions`: each thing you decided, as `- YYYY-MM-DD <assumption>`. Assumptions are
     defaults: whoever builds a ticket takes a better way where they see one, and records why.
9. Commit: `git add kanban <spec> && git commit -m "skift: spec"`.
10. End with, in plain words about the product and never about files or code: what it is for and who
    uses it, in one line; the parts the spec now holds, one line each; the assumptions you made;
    then this line, alone:
    `Next: /skift:tasks`
