---
name: spec
description: Turn a spec written in any Markdown into kanban features under kanban/features/, asking only for the context that is missing, so /skift:run can build it.
disable-model-invocation: true
argument-hint: "[path to your spec .md, default spec/spec.md]"
---

# Spec

Spec: `$ARGUMENTS`, or spec/spec.md when empty. The user wrote it in any shape. You turn it into
features that fresh Claude sessions build one at a time. Each session sees one feature, the spec,
kanban/context.md and CLAUDE.md: what you write here is all they know of the intent.

## Steps

1. Read the spec in full. If it is missing or says nothing to build, print the comment block of
   ${CLAUDE_PLUGIN_ROOT}/templates/project/spec/spec.md, then end with this line, alone:
   `Next: write what you want in <spec path>, then /skift:spec <spec path>`
2. Read what exists: kanban/context.md, the files in kanban/features/, CLAUDE.md, progress.md, and
   the repo as far as the spec touches it: README, dependency manifests, configuration, schemas and
   migrations, the code the spec will change. Never open .env or print a secret; list only the keys
   it has: `grep -o '^[A-Za-z_][A-Za-z0-9_]*=' .env`.
3. Find the missing context: what a session needs to build and check this spec that neither the
   spec nor the repo gives. Ask about it only when a wrong guess would cost rework across features
   or touch something the user owns:
   - access to systems: which database, API or environment, how to reach it, which data is safe to
     read or write, and what must never change there;
   - secrets: never ask for their values; ask the user to put them in .env under the keys you name,
     and check that .env is in .gitignore;
   - what done looks like, where the spec leaves it open across features;
   - the stack, only when neither the spec nor the repo decides it and the user may care.
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
6. Write the features. A slice is a part of the spec a person can review as a whole: together its
   features give an outcome a user can use or a system can show. The first slice is the thinnest
   path end to end; every later one builds on what came before. Each slice is a file
   `kanban/features/NN-<slice>.json`, NN its place in the build order (01, 02, ...) and <slice> a
   short name in a-z, 0-9 and `-`, holding a JSON array of features:

       {"id": 1, "description": "<one sentence: what a user can do, or a system shows, once it is built>", "steps": ["..."], "passes": false}

   - A feature is one session's work: one statement of the spec. An answer or assumption that
     refines a statement becomes steps of its feature, never a feature of its own. Setup goes into
     the first feature that needs it, never a feature of its own.
   - steps: what a person does and sees, or what a system shows, each checkable; at most 8. They are
     also the checklist the user reviews the feature by.
   - Nothing the spec does not ask for. How a feature gets built is left to its session.
   - ids count up across every file, from one past the highest id kanban/features/ holds now or has
     ever held: `git log -p -- kanban/features | grep -o '"id": [0-9]*' | grep -o '[0-9]*$' | sort -n | tail -1`.
   - When features already exist: keep every feature that passes and whose part of the spec did not
     change; rewrite or remove the open features whose part changed or is gone; add features for
     what is new. A passing feature whose part changed goes back to `"passes": false`, and the
     summary says so. Never reuse an id. Renumber the files when the slice order changes.
7. Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/loop.py" --project-dir "$PWD" --mark-spec <spec path>`.
   It checks the features, records the spec and its hash in kanban/source.json, creates
   progress.md, and prints every feature by slice. Fix what it refuses and run it again.
8. Commit: `git add kanban progress.md <spec path> && git commit -m "skift: spec"`.
9. End with a summary in plain words about the product, never about files or code:
   - each slice in build order, with one line on what a user can do once it is built, and its
     number of features;
   - the assumptions you made;
   - the questions still open, if the user said "enough";
   - then this line, alone: `Next: /skift:run --until <first slice not yet built>`
