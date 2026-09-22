---
name: run
description: Start the skift driver (scripts/loop.py) detached against the current repo, passing through any arguments.
disable-model-invocation: true
argument-hint: "[loop.py flags, e.g. --append --max-iterations 10 --bypass]"
---

# Run

If the arguments include `--status` or `--dry-run`, nothing is started: run this from the repo root,
print its output verbatim, and stop:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/loop.py" --project-dir "$PWD" $ARGUMENTS
```

Otherwise run this once, from the repo root, exactly as written (three lines, one Bash call):

```bash
mkdir -p .skift
nohup python3 "${CLAUDE_PLUGIN_ROOT}/scripts/loop.py" --project-dir "$PWD" $ARGUMENTS > .skift/run.log 2>&1 &
echo $! > .skift/run.pid
```

Do not wait for it and do not read the log. Print these two lines and stop:

Follow: `tail -f .skift/run.log`
Stop: `kill -INT $(cat .skift/run.pid)` stops after the current session; send it again to stop at once.
