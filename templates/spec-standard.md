# What a spec must hold

skift builds nothing from a spec that leaves out what gets built. A spec meets this standard when
every item below holds. `/skift:spec` checks it, and where it fails, a grill writes what is missing.
An item fails only when a wrong reading would change what gets built or how it is checked.

- **S1 Purpose.** Who uses it, as roles, and what they can do once it is built that they cannot now.
  Fails: no user named, or a list of features with no reason under it.
- **S2 Parts, in build order.** Each part is one statement of what must work, as `<role> can <do X>`
  or `<system> shows <Y>`. Part 1 is the thinnest path end to end; each later part builds on the ones
  before. Fails: a capability only implied ("a CRM", "like Trello"), a part holding several
  capabilities, or a part that is a code property (a data model, validation, a refactor) rather than
  something a person can see.
- **S3 Done.** Every part carries at least one check a person can run by using the product or looking
  at a system: what they do, and what they see. A quality goal is measurable ("under 2 seconds", not
  "fast"). Fails: "works well", or a part with no check.
- **S4 Systems.** Every database, API, file or service it reads or writes, what it may do there, and
  what must never change. In an existing repo, which behaviour must stay. "None" is an answer.
  Fails: a system named with no limit on what may happen to it.
- **S5 Built with.** The stack, where the repo, the client or the user fixes it; otherwise "Claude
  chooses". It only has to be stated.
- **S6 Out of scope.** What is deliberately not built, and why. "Nothing" is an answer.

Every statement in the spec, whatever its shape:

- one reading only: no word that two readers would take differently;
- no two statements contradict, and each term is used one way;
- what, not how, unless the how is a constraint, with its reason;
- no secrets: name the key, and the value goes in `.env`.

## The shape skift writes

A spec skift's grill writes is one Markdown file in this shape. A spec the user brought, such as a
client document, keeps its own shape: the standard is about what it holds, not how it is laid out.

```markdown
# <product>

## Purpose
<who uses it, and what they can do once it is built that they cannot now>

## Parts in build order
### <role> can <do X>
<what must work, in a sentence or two>
Done:
- <what a person does, and what they see>

### <the next part>
Done:
- <...>

## Systems
- <system>: <what it may read or write; what must never change; the .env keys it needs>

## Built with
<the stack, or "Claude chooses">

## Out of scope
- <what, and why>
```
