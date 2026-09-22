#!/usr/bin/env python3
"""skift driver: kanban/features/NN-<slice>.json -> one fresh `claude -p` per feature until all pass.
/skift:spec writes the features from your spec; this script only builds them, in build order, and
--until stops after one slice. A feature named under ## Gaps in progress.md is skipped, and a spec
changed since /skift:spec stops the run before it starts. Every run ends with a handoff in
.skift/handoff.md: what you can do now, how to open it, what to check, what was decided for you, what
is not built, and what to do next. Ctrl+C stops after the current session; a second Ctrl+C stops now."""
import argparse, contextlib, hashlib, itertools, json, os, re, signal, subprocess, sys, threading, time  # noqa: E401
from pathlib import Path

MODEL = "sonnet"
MAX_TURNS = 200  # per session
MAX_SESSIONS_PER_FEATURE = 3  # consecutive sessions on one feature without passing, then stop
SESSION_TIMEOUT = 3600  # seconds per session
INIT_TIMEOUT = 180  # seconds for ./init.sh when the run ends

PROMPTS = Path(__file__).resolve().parent.parent / "prompts"
FEATURES, SOURCE, PROGRESS, HANDOFF = "kanban/features", "kanban/source.json", "progress.md", ".skift/handoff.md"
LEGACY = "features.json"  # the single feature file of skift before 0.4
SECTIONS = ("Current", "Log", "Built", "Decided", "Gaps", "Findings")  # of progress.md
FILE_RE, NOTE_RE = re.compile(r"^(\d+)-[a-z0-9]+(?:-[a-z0-9]+)*$"), re.compile(r"\bfeature #?(\d+)\b", re.I)
TOOL_KEYS = ("command", "file_path", "path", "pattern")
STOP: list = []  # non-empty once Ctrl+C was pressed


def slices(root: Path) -> list[Path]:
    """The slice files in build order: kanban/features/NN-<slice>.json, by their number."""
    files = list((root / FEATURES).glob("*.json"))
    for p in files:
        if not FILE_RE.match(p.stem):
            raise ValueError(f"{FEATURES}/{p.name}: a slice file is named NN-<slice>.json, its number the build order; rerun /skift:spec")
    return sorted(files, key=lambda p: (int(p.stem.split("-")[0]), p.stem))

def load(root: Path) -> list[dict]:
    """Every feature in build order, its slice under "_slice"; refuses a malformed feature or an id used twice."""
    feats, seen = [], set()
    for p in slices(root):
        try:
            items = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise ValueError(f"{FEATURES}/{p.name} is not valid JSON: {e}") from e
        for f in items if isinstance(items, list) else [None]:
            if not (isinstance(f, dict) and isinstance(f.get("id"), int) and isinstance(f.get("description"), str)
                    and isinstance(f.get("steps"), list) and isinstance(f.get("passes"), bool)):
                raise ValueError(f"{FEATURES}/{p.name}: a slice file is a list of features, each with an int id, a description, a list of steps and passes")
            if f["id"] in seen: raise ValueError(f"{FEATURES}/{p.name}: feature id {f['id']} is used twice")
            seen.add(f["id"])
            feats.append({**f, "_slice": p.stem})
    return feats

def section(root: Path, name: str) -> list[str]:
    """The lines under `## <name>` in progress.md."""
    out, on = [], False
    for line in (root / PROGRESS).read_text(encoding="utf-8").splitlines() if (root / PROGRESS).is_file() else []:
        if re.match(r"#{1,2}\s", line): on = line.strip().lower() == f"## {name.lower()}"
        elif on and line.strip(): out.append(line.strip())
    return out

def notes(root: Path, name: str) -> dict[int, list[str]]:
    """The lines under `## <name>` in progress.md by the feature they name, without the `- feature N:` prefix."""
    out: dict[int, list[str]] = {}
    for line in section(root, name):
        text = re.sub(r"^-\s*(\d{4}-\d{2}-\d{2}\s+)?feature #?\d+\s*:\s*", "", line, flags=re.I)
        for i in NOTE_RE.findall(line): out.setdefault(int(i), []).append(text)
    return out

def ensure_progress(root: Path) -> None:
    """progress.md with every section, added at the end where one is missing."""
    path = root / PROGRESS
    text = path.read_text(encoding="utf-8") if path.is_file() else "# Progress\n"
    have = {m.lower() for m in re.findall(r"^## +(.+?)\s*$", text, re.M)}
    missing = [f"## {s}\n" for s in SECTIONS if s.lower() not in have]
    if missing: path.write_text(text.rstrip("\n") + "\n\n" + "\n".join(missing), encoding="utf-8")

def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def spec_state(root: Path) -> str:
    """Empty when the spec is unchanged since /skift:spec wrote the features; else why the run must not start."""
    if not (root / SOURCE).is_file(): return f"{SOURCE} is missing: run /skift:spec <your spec file>"
    src = json.loads((root / SOURCE).read_text(encoding="utf-8"))
    spec = root / str(src.get("spec", ""))
    if not spec.is_file(): return f"the spec {src.get('spec')} is gone: run /skift:spec <your spec file>"
    if digest(spec) != src.get("sha256"): return f"{src['spec']} changed since /skift:spec wrote the features: rerun /skift:spec {src['spec']}"
    return ""

def mark(root: Path, spec: str) -> int:
    """--mark-spec: check the features, record the spec they came from and its hash, then print the status."""
    path = (root / spec).resolve()
    if not path.is_file(): raise ValueError(f"{spec}: no such file")
    feats = load(root)
    if not feats: raise ValueError(f"{FEATURES}/ has no feature: write them first")
    ensure_progress(root)
    (root / SOURCE).write_text(json.dumps({"spec": os.path.relpath(path, root), "sha256": digest(path)}, indent=2) + "\n", encoding="utf-8")
    return status(root, feats)

def until_scope(feats: list[dict], until: str) -> set[str]:
    """The slices up to and including `until`: its file name (01-orders), its name (orders) or its number (1)."""
    order = list(dict.fromkeys(f["_slice"] for f in feats))
    hit = [s for s in order if until in (s, s.split("-", 1)[1]) or (until.isdigit() and int(until) == int(s.split("-")[0]))]
    if not hit: raise ValueError(f"--until {until}: no slice has that name ({', '.join(order)})")
    return set(order[:order.index(hit[0]) + 1])

def todo(feats: list[dict], scope: set | None, gapped: set) -> list[dict]:
    """Features to build, in build order: open, inside --until's slices, not named under ## Gaps."""
    return [f for f in feats if not f["passes"] and (scope is None or f["_slice"] in scope) and f["id"] not in gapped]

def plural(n: int, word: str) -> str:
    return f"{n} {word}{'s' * (n != 1)}"

def status(root: Path, feats: list[dict]) -> int:
    """Per slice, in build order: passing/total, gaps and findings, then each feature."""
    gaps, found = notes(root, "Gaps"), notes(root, "Findings")
    print(f"[skift] {sum(f['passes'] for f in feats)}/{len(feats)} features pass" + ("" if feats else f"; nothing in {FEATURES}/ yet: run /skift:spec"))
    for s in dict.fromkeys(f["_slice"] for f in feats):
        mine = [f for f in feats if f["_slice"] == s]
        g, fi = (sum(len(n.get(f["id"], [])) for f in mine) for n in (gaps, found))
        print(f"[skift] {s}  {sum(f['passes'] for f in mine)}/{len(mine)} passing · {plural(g, 'gap')} · {plural(fi, 'finding')}")
        for f in mine:
            print(f"[skift]   [{'x' if f['passes'] else ' '}] {f['id']}  {f['description']}" + ("  (gap)" if f["id"] in gaps else ""))
    if feats and (why := spec_state(root)): print(f"[skift] a run would not start: {why}")
    return 0

def dry_run(root: Path, a: argparse.Namespace, feats: list[dict]) -> int:
    scope, gapped = until_scope(feats, a.until) if a.until else None, set(notes(root, "Gaps"))
    for f in todo(feats, scope, set()):
        print(f"[skift] {'skip, gap' if f['id'] in gapped else 'would build'}: feature {f['id']} ({f['_slice']}): {f['description']}")
    if why := spec_state(root): print(f"[skift] a run would not start: {why}")
    return 0

def on_sigint(sig, frame) -> None:
    if STOP: raise KeyboardInterrupt
    STOP.append(sig)
    print("[skift] stopping after the current session; Ctrl+C again stops now")

def session(prompt: str, a: argparse.Namespace, root: Path) -> dict:
    """One fresh `claude -p`, streamed as in gates runner.py; returns the result event, {} if none."""
    cmd = ["claude", "-p", "--model", a.model, "--permission-mode", "bypassPermissions" if a.bypass else "auto",
           "--max-turns", str(a.max_turns), "--output-format", "stream-json", "--verbose"]
    proc = subprocess.Popen(cmd, cwd=root, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, start_new_session=True)
    kill = lambda: proc.poll() is None and os.killpg(proc.pid, signal.SIGTERM)  # noqa: E731  the session and its children
    timer, report = threading.Timer(a.session_timeout, kill), {}
    timer.start()
    try:
        with contextlib.suppress(BrokenPipeError):  # a session that exits before reading its prompt
            proc.stdin.write(prompt)
            proc.stdin.close()
        for raw in proc.stdout:
            try:
                ev = json.loads(raw)
            except json.JSONDecodeError:
                print(f"  {raw.rstrip()}")
                continue
            for b in (ev.get("message") or {}).get("content", []) if ev.get("type") == "assistant" else ():
                if b.get("type") == "text" and b.get("text", "").strip():
                    print("\n".join(f"  {t}" for t in b["text"].strip().splitlines()))
                elif b.get("type") == "tool_use":  # the command for Bash, the path for file tools
                    print(f"  {b.get('name')} {next((v for k, v in (b.get('input') or {}).items() if k in TOOL_KEYS), '')}")
            report = ev if ev.get("type") == "result" else report
    except KeyboardInterrupt:
        kill()
        raise
    finally:
        timer.cancel()
        proc.wait()
    if not report: print(f"  ! no result: the session failed or hit SESSION_TIMEOUT ({a.session_timeout}s)")
    return report

def usage(report: dict) -> tuple[int, int, str]:
    """(input tokens including cache writes and reads, output tokens, one printable line)."""
    u = report.get("usage") or {}
    tin, tout = sum(u.get(k) or 0 for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")), u.get("output_tokens") or 0
    return tin, tout, f"in {tin} out {tout} tokens, {report.get('num_turns', '?')} turns, {report.get('subtype', 'no result')}"

def fill(name: str, **kw) -> str:
    return re.sub(r"\{\{(\w+)\}\}", lambda m: str(kw.get(m[1], m[0])), (PROMPTS / name).read_text(encoding="utf-8"))


def build(a: argparse.Namespace, root: Path, run: dict) -> str:
    """One session per open feature until none is left; returns why it stopped: done, gaps, stuck, stopped or limit."""
    streak, fid = 0, None
    for n in itertools.count():
        if STOP: return "stopped"
        if a.max_iterations and n >= a.max_iterations: return "limit"
        feats, gapped = load(root), set(notes(root, "Gaps"))
        if not todo(feats, run["scope"], set()): return "done"
        if not (queue := todo(feats, run["scope"], gapped)): return "gaps"
        f = queue[0]
        streak, fid = (streak + 1 if f["id"] == fid else 1), f["id"]
        print(f"[skift] feature {fid} ({f['_slice']}), session {streak}: {f['description']}")
        prompt = fill("coding.md", FEATURE=json.dumps({k: f[k] for k in ("id", "description", "steps")}, indent=2, ensure_ascii=False),
                      ID=fid, MAX_TURNS=a.max_turns, FEATURE_FILE=f"{FEATURES}/{f['_slice']}.json", SPEC=run["spec"])
        line = usage(session(prompt, a, root))[2]
        feats = load(root)
        passed = any(g["id"] == fid and g["passes"] for g in feats)
        if passed: run["passed"].append(fid)
        print(f"[skift] {sum(g['passes'] for g in feats)}/{len(feats)} passing · feature {fid} {'passes' if passed else 'open'} · session {line}")
        if not passed and streak >= a.max_sessions_per_feature:
            run["stuck"] = (fid, streak)
            return "stuck"
        time.sleep(3)

def start(a: argparse.Namespace, root: Path, run: dict) -> tuple[str, str]:
    try:
        if (root / LEGACY).is_file(): raise ValueError(f"{LEGACY} is from skift before 0.4: rerun /skift:spec <your spec file>")
        if why := spec_state(root): raise ValueError(why)
        if not (feats := load(root)): raise ValueError(f"{FEATURES}/ has no feature: run /skift:spec <your spec file>")
        run["scope"] = until_scope(feats, a.until) if a.until else None
    except ValueError as e:
        return "refused", str(e)
    run["spec"] = json.loads((root / SOURCE).read_text(encoding="utf-8"))["spec"]
    ensure_progress(root)
    return build(a, root, run), ""

def open_it(root: Path) -> list[str]:
    """Run ./init.sh so the product is ready to use; the last lines it printed, which say where it is."""
    if not (root / "init.sh").is_file(): return []
    out = root / ".skift" / "init.out"
    try:
        with out.open("w", encoding="utf-8") as fh:  # a file, not a pipe: a server init.sh leaves running would hold a pipe open
            rc = subprocess.run(["./init.sh"], cwd=root, stdin=subprocess.DEVNULL, stdout=fh, stderr=subprocess.STDOUT,
                                timeout=INIT_TIMEOUT, start_new_session=True).returncode
    except (OSError, subprocess.TimeoutExpired) as e:
        return [f"./init.sh did not finish: {e}"]
    tail = [line for line in out.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip()][-5:]
    return tail if rc == 0 else [f"./init.sh failed with exit {rc}:", *tail]

def handoff(root: Path, a: argparse.Namespace, outcome: str, run: dict, detail: str) -> str:
    """What the run leaves you: what you can do now, how to open it, what to check, what was decided for you,
    what is not built, and what to do next. About the product, never about files or code."""
    try:
        feats = load(root)
    except ValueError:
        feats = []
    by_id, scope = {f["id"]: f for f in feats}, run["scope"]
    order = list(dict.fromkeys(f["_slice"] for f in feats))
    built, decided, gaps = notes(root, "Built"), notes(root, "Decided"), notes(root, "Gaps")
    passed = [by_id[i] for i in dict.fromkeys(run["passed"]) if i in by_id]
    wanted = [f for f in feats if scope is None or f["_slice"] in scope]
    last = max(scope, key=order.index) if scope else None
    head = {
        "done": f"skift: {'built up to ' + last if last else 'everything is built'} ({sum(f['passes'] for f in wanted)} of {len(wanted)} features pass)",
        "gaps": "skift: stopped: the features left need answers from you",
        "stuck": f"skift: stopped: feature {run['stuck'][0]} does not pass after {run['stuck'][1]} sessions" if run["stuck"] else "skift: stopped",
        "stopped": "skift: stopped by you",
        "limit": f"skift: stopped after {plural(a.max_iterations, 'session')} (--max-iterations)",
        "refused": f"skift: did not start: {detail}",
        "failed": f"skift: failed: {detail}",
    }[outcome]
    out = [head]
    if passed:
        out += ["", "What you can do now"] + [f"  - {(built.get(f['id']) or [f['description']])[-1]}" for f in passed]
        if lines := open_it(root):
            out += ["", "Open it"] + [f"  {line}" for line in lines]
        out += ["", "Check it"]
        for s in dict.fromkeys(f["_slice"] for f in passed):
            out.append(f"  {s}")
            for f in (f for f in passed if f["_slice"] == s):
                out += [f"    [ ] {f['id']}  {f['description']}"] + [f"          - {step}" for step in f["steps"]]
        if mine := [(f["id"], text) for f in passed for text in decided.get(f["id"], [])]:
            out += ["", "Decided for you, check these too"] + [f"  - {text} (feature {i})" for i, text in mine]
    elif outcome == "done":
        out += ["", "Nothing new was built: every feature in scope already passed."]
    if outcome not in ("refused", "done") and (left := [f for f in wanted if not f["passes"]]):
        out += ["", "Not built"]
        for f in left[:10]:
            why = (f"waiting for your answer: {gaps[f['id']][-1]}" if f["id"] in gaps else
                   "does not pass yet; where it stopped is under ## Current in progress.md" if run["stuck"] and f["id"] == run["stuck"][0] else "open")
            out.append(f"  - feature {f['id']}, {f['description']}: {why}")
        if len(left) > 10: out.append(f"  - and {len(left) - 10} more")
    again = "/skift:run" + (f" --until {a.until}" if a.until else "")
    later = [s for s in order[order.index(last) + 1:] if any(not f["passes"] for f in feats if f["_slice"] == s)] if last else []
    nxt = {
        "done": (f"Check the boxes above, then /skift:run --until {later[0]}" if later else
                 "Check the boxes above." + (" Everything is built." if all(f["passes"] for f in feats) else "")),
        "gaps": f"Answer each question in kanban/context.md, delete its line under ## Gaps in progress.md, then {again}",
        "stuck": f"Read ## Current in progress.md, clear up what blocks the feature (kanban/context.md or its steps), then {again}",
        "stopped": f"Continue with {again}",
        "limit": f"Continue with {again}",
        "refused": "Fix that, then /skift:run",
        "failed": f"Fix that, then {again}",
    }[outcome]
    return "\n".join(out + ["", "Next", f"  {nxt}"])

def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    for flag, default in (("model", MODEL), ("max-turns", MAX_TURNS), ("max-sessions-per-feature", MAX_SESSIONS_PER_FEATURE),
                          ("session-timeout", SESSION_TIMEOUT)):
        p.add_argument(f"--{flag}", type=type(default), default=default, help=f"default {default}")
    p.add_argument("--project-dir", default=".", help="the project repo (default: cwd)")
    p.add_argument("--max-iterations", type=int, default=0, help="coding sessions before stopping (default: no limit)")
    p.add_argument("--until", metavar="SLICE", help="build only up to this slice: its file name (01-orders), name (orders) or number (1)")
    p.add_argument("--bypass", action="store_true", help="sessions run with bypassPermissions instead of auto")
    p.add_argument("--status", action="store_true", help="per slice: passing/total, gaps and findings, then each feature; spawn no session")
    p.add_argument("--dry-run", action="store_true", help="print the features a run would build; spawn no session")
    p.add_argument("--mark-spec", metavar="SPEC", help="for /skift:spec: check the features, record the spec they came from, print the status")
    a = p.parse_args()
    root = Path(a.project_dir).resolve()
    sys.stdout.reconfigure(line_buffering=True)
    if a.status or a.dry_run or a.mark_spec:  # reports: they start nothing and leave the handoff alone
        try:
            if (root / LEGACY).is_file(): raise ValueError(f"{LEGACY} is from skift before 0.4: rerun /skift:spec <your spec file>")
            if a.mark_spec: return mark(root, a.mark_spec)
            return status(root, load(root)) if a.status else dry_run(root, a, load(root))
        except (OSError, ValueError) as e:
            print(f"[skift] {e}")
            return 1
    signal.signal(signal.SIGINT, on_sigint)
    run: dict = {"passed": [], "stuck": None, "scope": None, "spec": ""}
    try:
        outcome, detail = start(a, root, run)
    except KeyboardInterrupt:
        outcome, detail = "stopped", ""
    except (OSError, ValueError) as e:
        outcome, detail = "failed", str(e)
    text = handoff(root, a, outcome, run, detail)
    (root / HANDOFF).parent.mkdir(exist_ok=True)
    (root / HANDOFF).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if outcome == "done" else 1

if __name__ == "__main__":
    sys.exit(main())
