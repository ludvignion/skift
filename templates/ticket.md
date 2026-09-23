---
id: <n>.<m>
parent: <n>              # the task it belongs to
status: ready            # ready | in_progress | in_review | done — only you set done
depends_on: []           # the tickets that must be built first: [1.1]
writes: []               # the paths the build may touch; empty means no limit
---

# <n>.<m> <title>

## Outcome
<What a user can do, or a system shows, once this ticket is built: one sentence.>

## Acceptance criteria
- AC-1 (behavioral): Given <state>, When <action>, Then <what is observable> [<spec section id>]
- AC-2 (property): For all <inputs>, <what always holds> [<spec section id>]
- AC-3 (critical): <what must never happen, and what happens instead> [<spec section id>]
- AC-4 (human): Given <state>, a person confirms <outcome> [<spec section id>]  # no test names it

## Out of scope
- <what this ticket does not do, and which ticket does>

## Notes
<Optional: what the build should know, such as an earlier decision it must follow.>
