# skift coding session

You work on one feature of this project, then hand over. Your budget is {{MAX_TURNS}} turns.

## Feature

{{FEATURE}}

## Session

0. Whenever the feature will not be finished within the budget: overwrite `## Current` in
   progress.md with the handover, append a dated line to `## Log`, commit what is done (tests may
   be red), and stop. Do not flip `passes`. The next session continues this feature.
1. Run `pwd`. Read CLAUDE.md, `## Current` and the last 20 lines of `## Log` in progress.md, and
   `git log --oneline -20`. Run `./init.sh`. If any feature in features.json already passes, do the
   steps of one of them end to end with the Verification method in CLAUDE.md; if it fails, fix
   that first and note it in `## Log`.
2. If `## Current` names this feature, continue from its next step.
3. Implement only this feature. Write tests as you see fit; tests do not decide `passes`.
4. Do this feature's steps by using the product as its user would, with the Verification method
   in CLAUDE.md. Set this feature's `passes` to true only if every step was observed. That flip is
   the only edit ever made to features.json.
5. If a step cannot be done because the spec is silent on user-visible behaviour, do not guess:
   append `- feature {{ID}}: <question>` to `## Gaps` in progress.md, leave `passes` false, hand over
   as in 7, and stop. The driver skips this feature while that line is there.
6. Anything you notice outside this feature goes to `## Findings` in progress.md, not into the diff.
7. Overwrite `## Current` (feature id, done, left, next step), append a dated line to `## Log`
   (done, verified, left), and commit everything with a message naming feature {{ID}}. Stop.
