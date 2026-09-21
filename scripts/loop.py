#!/usr/bin/env python3
"""skift driver: spec/spec.md -> features.json -> one fresh `claude -p` per feature until all pass.
Decomposes when features.json is absent or with --append, then builds. A spec change under existing
features stops the run first. Ctrl+C stops after the current session; a second Ctrl+C stops now."""
import argparse, contextlib, itertools, json, os, re, signal, subprocess, sys, threading, time, unicodedata  # noqa: E401
from pathlib import Path

MODEL = "sonnet"
SPEC_CAP_TOKENS = 8000  # spec material per initializer session, counted as chars/4
MAX_TURNS = 200  # per session
MAX_STEPS = 8  # per feature
MAX_SESSIONS_PER_FEATURE = 3  # consecutive sessions on one feature without passing, then stop
SESSION_TIMEOUT = 3600  # seconds per session

PROMPTS = Path(__file__).resolve().parent.parent / "prompts"
SPEC, DECISIONS, FEATURES = "spec/spec.md", "spec/decisions.md", "features.json"
HEAD_RE, FENCE_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$"), re.compile(r"^\s*(```|~~~)")
COMMENT_RE, DECISION_RE = re.compile(r"<!--.*?-->", re.S), re.compile(r"^- \d{4}-\d{2}-\d{2} `?([^\s`:]+)`?:")
MARK_RE = re.compile(r"^skift: (initialize|reviewed) ")
TOOL_KEYS = ("command", "file_path", "path", "pattern")
STOP: list = []  # non-empty once Ctrl+C was pressed

def slug(text: str) -> str:
    """gates spec_intake.py: marks dropped, lowercase, runs of anything but a-z0-9 become `-`."""
    plain = "".join(c for c in unicodedata.normalize("NFKD", text) if unicodedata.category(c) != "Mn")
    seg = re.sub(r"[^a-z0-9]+", "-", plain.lower()).strip("-")
    if not seg or any(ord(c) > 127 for c in plain): raise ValueError(f"heading {text!r} does not slug to an id: use a-z and digits")
    return seg

def parse_spec(text: str) -> tuple[str, dict[str, str]]:
    """(context, {id: text}): requirements are headings under Features with text, id'd by path; the rest is context."""
    heads, fence = [], False
    for line in text.replace("\r\n", "\n").split("\n"):
        fence ^= bool(FENCE_RE.match(line))
        if not fence and (m := HEAD_RE.match(line)):
            heads.append((len(m[1]), m[2].strip(), line, []))
        elif heads:
            heads[-1][3].append(line)
    context, reqs, path = [], {}, []
    if heads and heads[0][0] == 1 and sum(h[0] == 1 for h in heads) == 1:
        context.append((heads[0][2] + "\n" + "\n".join(heads.pop(0)[3])).strip())
    for level, title, line, body in heads:
        path = [x for x in path if x[0] < level] + [(level, slug(title))]
        uid, body_text = "/".join(s for _, s in path), COMMENT_RE.sub("", "\n".join(body)).strip()
        if uid.split("/")[0] != "features" or (uid == "features" and body_text):
            context.append((line + "\n" + body_text).strip())
        elif uid != "features" and body_text:
            if uid in reqs: raise ValueError(f"duplicate id {uid}: the same heading path twice")
            reqs[uid] = body_text
    return "\n\n".join(context), reqs

def material(spec: tuple, ids: list[str]) -> dict[str, str]:
    """Initializer input: context, requirement text, decisions citing `outline`, an id or a heading above one."""
    ctx, reqs, decisions = spec
    cited = [d for d in decisions if (m := DECISION_RE.match(d)) and
             (m[1] == "outline" or any(i == m[1] or i.startswith(m[1] + "/") for i in ids))]
    return {"CONTEXT": ctx or "(none)", "REQUIREMENTS": "\n\n".join(f"#### {i}\n{reqs[i]}" for i in ids),
            "DECISIONS": "\n".join(cited) or "(none)"}

def size(spec: tuple, ids: list[str]) -> float:
    return sum(len(v) for v in material(spec, ids).values()) / 4

def cut(spec: tuple, ids: list[str], cap: int) -> list[list[str]]:
    """Workloads: consecutive ids in document order whose material totals at most `cap` tokens."""
    out = []
    for i in ids:
        if size(spec, [i]) > cap: raise ValueError(f"{i} is over SPEC_CAP_TOKENS ({cap}) with its context: split it or raise --spec-cap-tokens")
        if out and size(spec, out[-1] + [i]) <= cap:
            out[-1].append(i)
        else:
            out.append([i])
    return out

def git(root: Path, *args: str) -> str | None:
    r = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else None

def load(root: Path) -> list[dict] | None:
    return json.loads((root / FEATURES).read_text(encoding="utf-8")) if (root / FEATURES).is_file() else None

def next_id(root: Path, feats: list[dict]) -> int:
    """One past every id features.json has ever held, so a removed id is never reused."""
    hist = git(root, "log", "-p", "--format=", "--", FEATURES) or ""
    ids = [int(x) for x in re.findall(r'"id"\s*:\s*(\d+)', hist)] + [f["id"] for f in feats if isinstance(f.get("id"), int)]
    return max(ids, default=0) + 1

def coverage(reqs: dict, feats: list[dict], max_steps: int) -> list[tuple]:
    """Partition: every requirement cited by at least one feature. Drift: every cited id exists. Steps."""
    cited = {f.get("spec") for f in feats}
    out = [("uncited", r, f"{r}: no feature cites it") for r in reqs if r not in cited]
    out += [("drift", f.get("id"), f"feature {f.get('id')}: cites {f.get('spec')}, not a requirement") for f in feats if f.get("spec") not in reqs]
    return out + [("steps", f.get("id"), f"feature {f.get('id')}: over {max_steps} steps") for f in feats if len(f.get("steps") or []) > max_steps]

def stale(root: Path, reqs: dict, feats: list[dict]) -> list[tuple[str, str, str]]:
    """Cited headings deleted, or edited since the last `skift: initialize|reviewed` commit naming them."""
    log = (line.partition(" ") for line in (git(root, "log", "--format=%H %s") or "").splitlines())
    marks = [(h, s.replace(",", " ").split()[2:]) for h, _, s in log if MARK_RE.match(s)]
    old, out = {}, []
    for sid in dict.fromkeys(f.get("spec") for f in feats):
        users = ", ".join(str(f.get("id")) for f in feats if f.get("spec") == sid)
        if sid not in reqs:
            out.append(("deleted", sid, f"{sid}: heading deleted or renamed (features {users})"))
        elif h := next((h for h, ids in marks if sid in ids), None):
            old[h] = old[h] if h in old else parse_spec(git(root, "show", f"{h}:{SPEC}") or "")[1]
            if sid in old[h] and old[h][sid] != reqs[sid]:
                out.append(("edited", sid, f"{sid}: edited since {h[:7]} (features {users})"))
    return out

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

def initialize(a, root: Path, spec: tuple, ids: list[str], problems=()) -> set:
    """One initializer session for the workload `ids`; returns the feature ids it added."""
    feats = load(root)
    before = {f.get("id") for f in feats or []}
    prompt = fill("initializer.md", **material(spec, ids), IDS=" ".join(ids), MAX_STEPS=a.max_steps,
                  NEXT_ID=next_id(root, feats or []), FEATURES_JSON="exists" if feats is not None else "does not exist")
    if problems: prompt += "\n\n## Coverage problems in the previous attempt\n\n" + "\n".join(f"- {p}" for p in problems)
    print(f"[skift] initializer: {usage(session(prompt, a, root))[2]}")
    return {f.get("id") for f in load(root) or []} - before

def decompose(a, root: Path, spec: tuple, workloads: list[list[str]]) -> int:
    added = []
    for n, ids in enumerate(workloads, 1):
        print(f"[skift] initializer {n}/{len(workloads)}: {' '.join(ids)}")
        added.append(initialize(a, root, spec, ids))
        if STOP: return 0
    problems = coverage(spec[1], load(root) or [], a.max_steps)
    for ids, new in zip(workloads, added) if problems else ():
        if mine := [p for p in problems if p[1] in ids or p[1] in new]:
            bad = {p[1] for p in mine if p[0] != "uncited"}  # entries this run wrote: removed, then rewritten
            (root / FEATURES).write_text(json.dumps([f for f in load(root) or [] if f.get("id") not in bad], indent=2) + "\n")
            print(f"[skift] coverage: rerunning {' '.join(ids)} for {len(mine)} problem(s)")
            initialize(a, root, spec, ids, [p[2] for p in mine])
    for p in (problems := coverage(spec[1], load(root) or [], a.max_steps)):
        print(f"[skift] coverage: {p[2]}")
    return 1 if problems else 0

def build(a, root: Path) -> int:
    streak, fid, totals = 0, None, {}
    for n in itertools.count():
        if STOP or (a.max_iterations and n >= a.max_iterations):
            print("[skift] stopped" if STOP else f"[skift] stopped after {a.max_iterations} iterations")
            return 0
        if (todo := next((f for f in load(root) or [] if not f.get("passes")), None)) is None:
            print(f"[skift] all {len(load(root) or [])} features pass")
            return 0
        streak, fid = (streak + 1 if todo.get("id") == fid else 1), todo.get("id")
        print(f"[skift] feature {fid}, session {streak}: {todo.get('description', '')}")
        feature = json.dumps({k: todo.get(k) for k in ("id", "spec", "description", "steps")}, indent=2)
        tin, tout, line = usage(session(fill("coding.md", FEATURE=feature, ID=fid, MAX_TURNS=a.max_turns), a, root))
        feats = load(root) or []
        passed = any(f.get("id") == fid and f.get("passes") for f in feats)
        total = totals[fid] = [x + y for x, y in zip(totals.get(fid, (0, 0)), (tin, tout))]
        print(f"[skift] {sum(bool(f.get('passes')) for f in feats)}/{len(feats)} passing · feature {fid} "
              f"{'passes' if passed else 'open'} · session {line} · feature total in {total[0]} out {total[1]}")
        if not passed and streak >= a.max_sessions_per_feature:
            print(f"[skift] stuck: feature {fid} ran {streak} sessions without passing")
            return 1
        time.sleep(3)

def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    for flag, default in (("model", MODEL), ("spec-cap-tokens", SPEC_CAP_TOKENS), ("max-turns", MAX_TURNS), ("max-steps", MAX_STEPS),
                          ("max-sessions-per-feature", MAX_SESSIONS_PER_FEATURE), ("session-timeout", SESSION_TIMEOUT)):
        p.add_argument(f"--{flag}", type=type(default), default=default, help=f"default {default}")
    p.add_argument("--project-dir", default=".", help="the project repo (default: cwd)")
    p.add_argument("--max-iterations", type=int, default=0, help="coding sessions before stopping (default: no limit)")
    p.add_argument("--append", action="store_true", help="decompose the requirements no feature cites yet, then build")
    p.add_argument("--bypass", action="store_true", help="sessions run with bypassPermissions instead of auto")
    p.add_argument("--dry-run", action="store_true", help="parse, cut and check coverage; spawn no session")
    a = p.parse_args()
    root = Path(a.project_dir).resolve()
    sys.stdout.reconfigure(line_buffering=True)
    signal.signal(signal.SIGINT, on_sigint)
    spec = (*parse_spec((root / SPEC).read_text(encoding="utf-8")),
            (root / DECISIONS).read_text(encoding="utf-8").splitlines() if (root / DECISIONS).is_file() else [])
    feats, reqs = load(root), spec[1]
    uncited = [r for r in reqs if r not in {f.get("spec") for f in feats or []}]
    workloads = cut(spec, uncited if feats is None or a.append else [], a.spec_cap_tokens)
    changed = stale(root, reqs, feats) if feats is not None else []
    print(f"[skift] {len(reqs)} requirement(s), {len(uncited)} cited by no feature" + (" (--append adds them)" if feats and uncited and not a.append else ""))
    for n, ids in enumerate(workloads, 1):
        print(f"[skift] workload {n}, ~{size(spec, ids):.0f} tokens: {' '.join(ids)}")
    for kind, _, msg in changed + (coverage(reqs, feats or [], a.max_steps) if a.dry_run else []):
        print(f"[skift] {kind}: {msg}")
    if a.dry_run: return 0
    if changed:
        edited = " ".join(c[1] for c in changed if c[0] == "edited")
        print("[skift] review those features in features.json: edit them, or remove them and rerun with --append"
              + (f'\n[skift] then acknowledge the edits: git commit --allow-empty -am "skift: reviewed {edited}"' if edited else ""))
        return 1
    if workloads and ((rc := decompose(a, root, spec, workloads)) or STOP):
        return rc
    return build(a, root)

if __name__ == "__main__":
    try:
        sys.exit(main())
    except json.JSONDecodeError as e:
        sys.exit(f"[skift] {FEATURES} is not valid JSON: {e}")
    except (OSError, ValueError) as e:  # a missing spec, a heading that does not slug, a requirement over the cap
        sys.exit(f"[skift] {e}")
    except KeyboardInterrupt:
        sys.exit("[skift] stopped")
