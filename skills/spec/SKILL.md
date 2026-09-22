---
name: spec
description: Turn a spec of any size, in any Markdown (one file or a folder), into kanban/map.md and kanban features under kanban/features/, asking only for the context that is missing. A large spec is indexed, never read whole, and detailed one slice at a time.
disable-model-invocation: true
argument-hint: "[spec .md file or folder, default spec/spec.md] [--next [N]]"
---

# Spec

Arguments: `$ARGUMENTS`. The spec is the path given, or spec/spec.md. With `--next [N]` (N is 1 when
left out), the spec is the one kanban/source.json names, and only the next N slices without features
get them. The user wrote the spec in any shape and any size. You turn it into features that fresh
Claude sessions build one at a time. Each session sees one feature, the text of the spec sections it
cites, kanban/context.md and CLAUDE.md: what you write is all they know of the intent.

`L` below stands for `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/loop.py" --project-dir "$PWD"`.

## Steps

1. Run `L --index <spec>`. If the spec is missing or says nothing to build, print the comment block
   of ${CLAUDE_PLUGIN_ROOT}/templates/project/spec/spec.md, then end with this line, alone:
   `Next: write what you want in <spec>, then /skift:spec <spec>`
   The index says whether the spec is small or large:
   - small: read the spec whole. Every slice gets its features now.
   - large: never read it whole. Read kanban/index.md, open sections with `L --show <id> ...`, find
     them with `L --grep <regex>`. Only the first slice without features gets them now; with
     `--next N`, the next N.
2. Read what exists: kanban/context.md, kanban/map.md, kanban/features/, CLAUDE.md, progress.md, and
   the repo as far as the spec touches it: README, dependency manifests, configuration, schemas and
   migrations, the code the spec will change. When features exist, run `L --status`: it marks the
   features the spec changed under and lists sections new in the spec. Never open .env or print a
   secret; list only the keys it has: `grep -o '^[A-Za-z_][A-Za-z0-9_]*=' .env`.
3. Find the missing context: what a session needs to build and check the slices you detail now, that
   neither the spec nor the repo gives. On a first run, also what the whole map depends on. Ask
   only when a wrong guess would cost rework across features or touch something the user owns:
   - access to systems: which database, API or environment, how to reach it, which data is safe to
     read or write, and what must never change there;
   - secrets: never ask for their values; ask the user to put them in .env under the keys you name,
     and check that .env is in .gitignore;
   - what done looks like, where the spec leaves it open across features;
   - the stack, only when neither the spec nor the repo decides it and the user may care;
   - contradictions in the spec: quote both sections by id and recommend one.
   Everything else you decide as a good engineer would, and record as an assumption.
4. Ask in numbered rounds of related questions, costliest to get wrong first, each with a
   recommended answer. Valid replies: an answer, "all recommended", "decide it" (the recommended
   answer becomes an assumption), or "enough" (stop asking; the recommended answer of every
   question still open becomes an assumption). Print only the questions.
5. Write kanban/context.md with three sections, keeping what is already there:
   - `## Systems`: each system the work touches, how to reach it, the .env keys it needs (never
     their values), and what must never change there;
   - `## Answers`: each answer as `- YYYY-MM-DD Q: <question as asked> A: <answer as given>`; for
     "all recommended", A is the recommended answer followed by ` (recommended)`;
   - `## Assumptions`: each thing you decided, as `- YYYY-MM-DD <assumption>`.
6. Write kanban/map.md: every slice of the whole spec, in build order, and what is not built.

       # Map

       ## Slices
       - 01-<slice>: <what a user can do, or a system shows, once it is built> [src: <section id>, ...]

       ## Context
       - <what these sections hold, such as purpose, users or systems> [src: <section id>, ...]

       ## Out of scope
       - <what, and why> [src: <section id>, ...]

   - Section ids are the ones in kanban/index.md. Citing a section covers everything under it.
   - Every section with text of its own (own above 0 in the index) lies inside some line's
     [src: ...]: a slice's, Context's, or Out of scope's. Nothing is dropped silently.
   - A slice is a part a person can review as a whole: together its features give an outcome a
     user can use or a system can show. 01 is the thinnest path end to end; every later slice
     builds on what came before. A slice is named NN-<slice>, NN its place in the build order and
     <slice> a short name in a-z, 0-9 and `-`.
   - On a rerun keep the slices and their numbers, and add slices for new sections. Renumber only
     when the order changes, and rename the slice files with it.
7. Write the features of the slices detailed now. Each is a file `kanban/features/NN-<slice>.json`,
   named as in the map, holding a JSON array of features:

       {"id": 1, "description": "<one sentence: what a user can do, or a system shows, once it is built>", "steps": ["..."], "source": ["<section id>", "..."], "passes": false}

   - source: the most specific sections the feature comes from, each inside its slice's [src: ...];
     a feature citing a whole chapter is flagged by every edit in it. Together, the features of a
     slice cite every section with text in the slice that Context and Out of scope do not hold.
   - A feature is one session's work: one statement of the spec. An answer or assumption that
     refines a statement becomes steps of its feature, never a feature of its own. Setup goes into
     the first feature that needs it, never a feature of its own.
   - steps: what a person does and sees, or what a system shows, each checkable; at most 8. They are
     also the checklist the user reviews the feature by.
   - Nothing the spec does not ask for. How a feature gets built is left to its session.
   - ids count up across every file, from one past the highest id kanban/features/ holds now or has
     ever held: `git log -p -- kanban/features | grep -o '"id": [0-9]*' | grep -o '[0-9]*$' | sort -n | tail -1`.
   - When features already exist, on every run, `--next` included: keep every feature whose
     sections did not change. Rewrite the ones `L --status` marks `(spec changed)` from their
     sections as they are now. For one marked `(spec changed since it passed)`: if the change alters
     what it does, set `"passes": false` and say so in the summary; if not, leave it. Remove
     features whose sections are gone. Never reuse an id.
8. Run `L --mark-spec <spec>`. It indexes the spec again, checks the map and the features against it
   (every section covered, every cited section exists and lies inside its slice), records each
   section's hash in kanban/source.json, creates progress.md, and prints the status. Fix every
   problem it lists and run it again, until it prints the status.
9. Commit: `git add kanban progress.md <spec> && git commit -m "skift: spec"`.
10. End with a summary in plain words about the product, never about files or code:
    - each slice detailed now, in build order: one line on what a user can do once it is built, and
      its number of features;
    - the slices not detailed yet, one line each;
    - the assumptions you made, and the questions still open if the user said "enough";
    - then this line, alone: `Next: /skift:run --until <the last slice detailed now>`
