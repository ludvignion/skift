## Stack
<!-- Filled by the first skift session, from the spec and kanban/context.md: language, framework, package manager, versions. -->

## Run commands
<!-- Filled by the first skift session: how to make the product ready (./init.sh, if there is one), how to run the tests, where the output and the log are. -->

## Conventions
<!-- Filled by the first skift session: what every later session follows, such as the code structure, and for a UI the design direction and the one shared stylesheet every screen uses. -->

## Verification
<!-- Optional, yours to fill: a tool a session uses from the shell to do a feature's steps as a user would, e.g. a Playwright for Python script for an app, curl for an API, a query for a database, running the command. Name the tool here and nowhere else. Left empty, a feature passes on its tests, and you check it yourself at each /skift:run --until stop. -->

## Rule
One feature per session. A feature passes when every step is built and its tests pass, and, if Verification names a tool, every step was done through it.
