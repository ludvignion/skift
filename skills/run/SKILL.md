---
name: run
description: Build the features in kanban/features/ with the skift driver (scripts/loop.py), one fresh session each, and report back with a handoff when the run ends.
disable-model-invocation: true
argument-hint: "[--until <slice>] [--status] [--dry-run] [--max-iterations N] [--bypass]"
---

# Run

If the arguments include `--status` or `--dry-run`, nothing is started: run this from the repo root,
print its output verbatim, and stop:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/loop.py" --project-dir "$PWD" $ARGUMENTS
```

Otherwise:

1. Start the driver, from the repo root, exactly as written (one Bash call). It runs detached, so it
   keeps going if this session ends:

```bash
mkdir -p .skift && rm -f .skift/handoff.md
nohup python3 "${CLAUDE_PLUGIN_ROOT}/scripts/loop.py" --project-dir "$PWD" $ARGUMENTS > .skift/run.log 2>&1 &
echo $! > .skift/run.pid
```

2. Start this watcher as a background task (Bash with `run_in_background: true`), exactly as written.
   It ends when the driver ends:

```bash
while kill -0 "$(cat .skift/run.pid)" 2>/dev/null; do sleep 20; done; cat .skift/handoff.md 2>/dev/null || tail -n 30 .skift/run.log
```

3. Print these two lines and stop:

Follow: `tail -f .skift/run.log`
Stop: `kill -INT $(cat .skift/run.pid)` stops after the current session; send it again to stop at once.

When the watcher finishes, print its output verbatim and nothing else: it is the handoff.
