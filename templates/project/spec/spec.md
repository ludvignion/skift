# <what you want, in a few words>

<!--
Fill this in yourself, or leave it as it is and run /skift:grill: it asks for what is missing, in
proportion to what is missing, and writes it here. A spec that holds up gets no grill at all.
You can also drop a document of your own in spec/ instead; it is never rewritten.
Never put a secret here: the .env key name belongs in Systems, the value in .env.
Then: /skift:tasks, then /skift:kanban 1, then tell Claude what to build.
-->

## Purpose
<One paragraph: what it is for, who uses it, in what situation.>

## Done looks like
<3 to 5 outcomes you would check at the end, each one a user or a system can show.>

## Systems
<Each database, API, file source or service it touches:>
- <what it is and where it runs (dev/test/prod)>
- <read-only or writable, and which data is safe to use for tests>
- <what must never change there>
- <the .env key names it needs, never the values>

## Built with
<Only what you care about: language, framework, hosting, look and feel. Leave it out and the build
chooses.>

## Parts, in build order
### <Part 1: the thinnest path end to end>
- <one checkable statement per bullet: what a user does and sees, or what a system shows>

### <Part 2>
- <...>

## Out of scope
- <what must not be built>
