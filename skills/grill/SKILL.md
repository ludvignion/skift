---
name: grill
description: Read the spec the user filled in, check it against the six sections skift builds from, and ask for exactly what is missing - nothing when the spec holds up, a few questions when it nearly does, a full grill when it is an idea, notes or empty. Writes the spec and kanban/context.md, then hands over to /skift:tasks. Never writes tasks or tickets, and never builds.
disable-model-invocation: true
argument-hint: "[spec .md file or folder, default spec/spec.md]"
---

# Grill

Arguments: `$ARGUMENTS`. The spec is the path given, or spec/spec.md. The user brought what they
have: a filled-in spec, notes, a client document of any size, or nothing. You ask only for what is
missing, in proportion to what is missing, and the spec is what you leave behind. A well-written spec
gets no grill: you check it, ask nothing or almost nothing, and hand over.

`L` below stands for `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/kanban.py" --project-dir "$PWD"`.

## The spec

One Markdown file in six sections, in this order and no others. `Built with` is the only one that may
be left out. Where the user brought a document of their own, it keeps its shape and is never
rewritten: what it lacks is written beside it, as `spec/<name>-additions.md`, in these same sections.

    # <what you want, in a few words>

    ## Purpose
    One paragraph: what it is for, who uses it, in what situation.

    ## Done looks like
    3 to 5 outcomes to check at the end, each observable by a user or a system.

    ## Systems
    Each database, API, file source or service it touches: what it is and where it runs, read-only
    or writable and which data is safe for tests, what must never change there, and the .env key
    names it needs (never the values).

    ## Built with
    Only what the user cares about: language, framework, hosting, look and feel. Left out, the build
    chooses.

    ## Parts, in build order
    ### <Part 1: the thinnest path end to end>
    - one checkable statement per bullet: what a user does and sees, or what a system shows
    ### <Part 2>
    - ...

    ## Out of scope
    - what must not be built.

What makes it buildable, and what you check against:

- A bullet is one checkable statement. Test: could a person confirm it in the running product in
  under a minute? If not, it is either how it is built, which is left out, or several bullets.
- A part ends in something a user can do. A part that only adds a data model, a layer, validation or
  a refactor gives nobody anything to try: name the behaviour it serves instead.
- Part 1 is the tracer bullet, the thinnest path end to end. What follows is ordered by what the
  user wants to try next, never by architecture.
- Systems is what real work most often lacks. Ask for it even when everything else is clear.
- Out of scope binds: nothing on it gets built, however natural it looks later.
- Every statement has one reading, no two contradict, and what is written is what must work, never
  how. A quality goal is measurable: "under 2 seconds", never "fast".
- Never a secret in the spec: the key name belongs there, the value in .env.

## Steps

1. Read the spec as it stands. If it exists and holds text, run `L --index <spec>`; it says whether
   the spec is small or large:
   - small: read it whole;
   - large: never read it whole. Read kanban/index.md, open sections with `L --show <id> ...` and
     find them with `L --grep <regex>`.
   Read what else exists: kanban/context.md, spec/decisions.md if an older grill left one,
   kanban/tasks/, CLAUDE.md, and the repo as far as the spec touches it: README, dependency
   manifests, configuration, schemas and migrations, the code the spec will change. Never open .env
   or print a secret; list only the keys it has: `grep -o '^[A-Za-z_][A-Za-z0-9_]*=' .env`.
2. Check it, in two layers.
   - `L --check-spec <spec>`: the checks that come out the same every run. It refuses a spec with
     nothing to build from, checks every section and a bullet under every part for a spec in the six
     sections, and lists vague words and anything that looks like a secret, with their lines.
   - The trial run, which you do in your head and write nothing for: draft the tasks the spec would
     cut into, and for each the acceptance criteria its tickets would carry. Every place you would
     have to guess, where the guess would change what gets built or how it is checked, is a gap.
     Note the section id or line, the guess, and which of the rules above it breaks. What the repo
     already settles is not a gap.
3. Print the verdict, and nothing else about it:

       Spec check: 3 gaps
       - Systems: no environment named — dev only, or prod too?
       - parts/orders: "manage orders" — create and cancel, or edit and refund too?
       - vague: spec.md:14 "fast"

4. Ask in proportion to what you found, and never for what the spec, the repo or a decision already
   settles:
   - **No gaps**: ask nothing. Go to step 6.
   - **A few narrow gaps**: one round of questions, at most 5, each naming the gap it closes.
   - **An idea, notes, an empty file, or gaps across the sections**: the full grill. Rounds of at
     most 5 questions, costliest to get wrong first, each round narrowing the next: what it is for
     and who uses it, what done looks like, the systems and what must never change there, the parts
     in build order and the bullets under each, what is out of scope. Stop when the six sections
     hold up, not at a question count.
   In every round, give a recommended answer only where the spec, the repo or common practice makes
   one clearly better; where the choice is the user's alone, give the options and recommend none.
   Valid replies: an answer, "all recommended" (each question that has one takes it), or "decide it"
   (you decide, and it becomes an assumption). Print only the questions. Quote an answer verbatim
   when you write it down; misattributing an answer is the mistake that costs most.
5. Write the spec: the user's answers into the six sections, in their words where they gave them.
   A document the user brought is never rewritten; its additions go beside it as
   `spec/<name>-additions.md`, and from then on the spec is the folder holding both. Then run
   `L --index <spec>` and `L --check-spec <spec>` again, and redo the trial run. One pass only: if
   gaps are left, print them and stop, rather than grilling a second time.
6. Write kanban/context.md, the one file every build reads. Five sections. The first two are copied
   from the spec on every run; the other three keep what is there and add to it:
   - `## Purpose`: the spec's Purpose, word for word, ending with its section id in brackets;
   - `## Built with`: the spec's Built with, word for word, or the one line
     `nothing named: the build chooses`;
   - `## Systems`: each system, how to reach it, the .env keys it needs (never their values), and
     what must never change there;
   - `## Answers`: each answer as `- YYYY-MM-DD Q: <question as asked> A: <answer as given>`; for
     "all recommended", A is the recommended answer followed by ` (recommended)`;
   - `## Assumptions`: each thing you decided, as `- YYYY-MM-DD <assumption>, because <reason>`.
   Answers and assumptions bind every ticket built; a build that needs one changed says so in its
   ticket, and the line changes here first. If an older grill left `spec/decisions.md`, fold it into
   Answers and Assumptions and delete it. skift keeps no other decisions file.
7. Commit: `git add kanban <spec> && git commit -m "skift: spec"`.
8. End with, in plain words about the product and never about files or code: what it is for and who
   uses it, in one line; each part in build order, one line each; the assumptions you made; then
   this line, alone:
   `Next: /skift:tasks`
