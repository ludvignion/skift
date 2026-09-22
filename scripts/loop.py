#!/usr/bin/env python3
"""skift driver: spec/spec.md -> features.json -> one fresh `claude -p` per feature until all pass.
Decomposes when features.json is absent or with --append, then builds; --until stops after one slice.
A feature named under ## Gaps in progress.md is skipped. A spec change under existing features stops
the run first. Ctrl+C stops after the current session; a second Ctrl+C stops now."""
import argparse, contextlib, itertools, json, os, re, signal, subprocess, sys, threading, time, unicodedata  # noqa: E401
from pathlib import Path

MODEL = "sonnet"
SPEC_CAP_TOKENS = 8000  # spec material per initializer session, counted as chars/4
MAX_TURNS = 200  # per session
MAX_STEPS = 8  # per feature
MAX_SESSIONS_PER_FEATURE = 3  # consecutive sessions on one feature without passing, then stop
SESSION_TIMEOUT = 3600  # seconds per session

PROMPTS = Path(__file__).resolve().parent.parent / "prompts"
SPEC, DECISIONS, FEATURES, PROGRESS = "spec/spec.md", "spec/decisions.md", "features.json", "progress.md"
COMMENT_RE, DECISION_RE = re.compile(r"<!--.*?-->", re.S), re.compile(r"^- \d{4}-\d{2}-\d{2} `?([^\s`:,]+(?:,\s*[^\s`:,]+)*)`?:")
MARK_RE, GAP_RE = re.compile(r"^skift: (initialize|reviewed) "), re.compile(r"\bfeature #?(\d+)\b", re.I)
TOOL_KEYS = ("command", "file_path", "path", "pattern")
STOP: list = []  # non-empty once Ctrl+C was pressed

# From here to parse_spec: copied unchanged from gates scripts/spec_intake.py.
_HEADING_RE = re.compile(r"^(?P<hashes>#{1,6})\s+(?P<text>.+?)\s*#*\s*$")
_FENCE_RE = re.compile(r"^\s*(```|~~~)")


class Unit:
    __slots__ = ("id", "title", "text")

    def __init__(self, uid: str, title: str, text: str) -> None:
        self.id, self.title, self.text = uid, title, text


def slug(text: str) -> str:
    """Lowercase ASCII with runs of anything else as ``-``. Accented Latin letters lose their
    marks first (å→a, ä→a, ö→o, é→e); a letter that does not decompose (ø, ß, non-Latin) raises."""
    plain = "".join(c for c in unicodedata.normalize("NFKD", text) if unicodedata.category(c) != "Mn")
    if any(ord(c) > 127 for c in plain):
        raise ValueError(f"heading {text!r} has letters that do not slug: add an id column (use the CSV shape)")
    return re.sub(r"[^a-z0-9]+", "-", plain.lower()).strip("-")


def markdown_units(text: str) -> list[Unit]:
    """Units from headings; raises ValueError on a duplicate path or a heading that slugs to nothing."""
    heads: list[tuple[int, str]] = []  # (level, text)
    bodies: list[list[str]] = []
    in_fence = False
    for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if _FENCE_RE.match(line):
            in_fence = not in_fence
        m = None if in_fence else _HEADING_RE.match(line)
        if m:
            heads.append((len(m.group("hashes")), m.group("text").strip()))
            bodies.append([])
        elif bodies:
            bodies[-1].append(line)
    if not heads:
        raise ValueError("no headings and no id column: the spec is markdown with headings or a CSV with an id column")
    if heads[0][0] == 1 and sum(1 for lvl, _ in heads if lvl == 1) == 1:  # the document title
        heads, bodies = heads[1:], bodies[1:]
    path: list[tuple[int, str]] = []
    units: list[Unit] = []
    seen: set[str] = set()
    for (level, title), body in zip(heads, bodies):
        seg = slug(title)
        if not seg:
            raise ValueError(f"heading {title!r} slugs to nothing: add an id column (use the CSV shape)")
        while path and path[-1][0] >= level:
            path.pop()
        path.append((level, seg))
        uid = "/".join(s for _, s in path)
        unit_text = "\n".join(body).strip()
        if not unit_text:
            continue  # a container: no unit, stays in the path
        if uid in seen:
            raise ValueError(f"duplicate id {uid}: the same heading path twice")
        seen.add(uid)
        units.append(Unit(uid, title, unit_text))
    return units

def parse_spec(text: str) -> tuple[str, dict[str, str]]:
    """(context, {id: text}): markdown_units over the `## Features` subtree, comments dropped. Everything
    outside that subtree is context, and so is the text directly under `## Features`."""
    lines, fence, start, end = COMMENT_RE.sub("", text).replace("\r\n", "\n").replace("\r", "\n").split("\n"), False, None, None
    for n, line in enumerate(lines):
        fence ^= bool(_FENCE_RE.match(line))
        if fence or not (m := _HEADING_RE.match(line)) or len(m["hashes"]) > 2:
            continue
        if start is None and len(m["hashes"]) == 2 and m["text"].strip().lower() == "features":
            start = n
        elif start is not None:
            end = n
            break
    if start is None: return "\n".join(lines).strip(), {}
    end = len(lines) if end is None else end
    units = markdown_units("\n".join(lines[start:end]))
    own = [lines[start], u.text] if (u := next((u for u in units if u.id == "features"), None)) else []
    return "\n".join(lines[:start] + own + lines[end:]).strip(), {u.id: u.text for u in units if u.id != "features"}

def until_ids(reqs: dict, until: str) -> set[str]:
    """Requirement IDs under the top-level Features heading `until` (its text or ID) or an earlier one in spec order."""
    tops, want = list(dict.fromkeys(r.split("/")[1] for r in reqs)), slug(until.removeprefix("features/"))
    if want not in tops: raise ValueError(f"--until {until}: no top-level heading under ## Features with requirements has that name ({', '.join(tops)})")
    return {r for r in reqs if r.split("/")[1] in tops[:tops.index(want) + 1]}

def section(root: Path, name: str) -> list[str]:
    """The lines under `## <name>` in progress.md."""
    out, on = [], False
    for line in (root / PROGRESS).read_text(encoding="utf-8").splitlines() if (root / PROGRESS).is_file() else []:
        if re.match(r"#{1,2}\s", line): on = line.strip().lower() == f"## {name.lower()}"
        elif on and line.strip(): out.append(line.strip())
    return out

def todo(feats: list[dict], scope: set | None, gap: list[str]) -> list[dict]:
    """Features to build, in features.json order: open, inside --until's slice, not named under ## Gaps."""
    skip = {int(x) for g in gap for x in GAP_RE.findall(g)}
    return [f for f in feats if not f.get("passes") and (scope is None or f.get("spec") in scope) and f.get("id") not in skip]

def material(spec: tuple, ids: list[str]) -> dict[str, str]:
    """Initializer input: context, requirement text, decisions citing `outline`, an id or a heading above one;
    a decision citing several ids counts for each."""
    ctx, reqs, decisions = spec
    cited = [d for d in decisions if (m := DECISION_RE.match(d)) and any(
             c == "outline" or any(i == c or i.startswith(c + "/") for i in ids) for c in re.split(r",\s*", m[1]))]
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

def status(root: Path, reqs: dict, feats: list[dict]) -> int:
    """Per top-level Features heading, in spec order: passing/total, and the gaps and findings naming its features."""
    top = {f.get("id"): str(f.get("spec")).split("/")[1] if "/" in str(f.get("spec")) else str(f.get("spec")) for f in feats}
    rows = {s: [0, 0, 0, 0] for s in dict.fromkeys([r.split("/")[1] for r in reqs] + list(top.values()))}
    loose = [0, 0]  # gaps and findings that name no feature
    for f in feats:
        rows[top[f.get("id")]][0] += bool(f.get("passes"))
        rows[top[f.get("id")]][1] += 1
    for col, name in ((2, "Gaps"), (3, "Findings")):
        for line in section(root, name):
            named = {top[i] for i in map(int, GAP_RE.findall(line)) if i in top}
            for s in named: rows[s][col] += 1
            loose[col - 2] += not named
    plural = lambda n, word: f"{n} {word}{'s' * (n != 1)}"  # noqa: E731
    width = max(map(len, rows), default=0)
    print(f"[skift] {sum(r[0] for r in rows.values())}/{len(feats)} features pass" + ("" if feats else f"; no {FEATURES} yet"))
    for s, (ok, n, g, fi) in rows.items():
        print(f"[skift] {s.ljust(width)}  {ok}/{n} passing · {plural(g, 'gap')} · {plural(fi, 'finding')}")
    if any(loose): print(f"[skift] naming no feature: {plural(loose[0], 'gap')} · {plural(loose[1], 'finding')}")
    return 0

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
    """Partition: every requirement cited by at least one feature. Exists: every cited id is a requirement. MAX_STEPS."""
    cited = {f.get("spec") for f in feats}
    out = [("partition", r, f"{r}: no feature cites it") for r in reqs if r not in cited]
    out += [("exists", f.get("id"), f"feature {f.get('id')}: cites {f.get('spec')}, not a requirement") for f in feats if f.get("spec") not in reqs]
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
            bad = {p[1] for p in mine if p[0] != "partition"}  # entries this run wrote: removed, then rewritten
            (root / FEATURES).write_text(json.dumps([f for f in load(root) or [] if f.get("id") not in bad], indent=2) + "\n")
            print(f"[skift] coverage: rerunning {' '.join(ids)} for {len(mine)} problem(s)")
            initialize(a, root, spec, ids, [p[2] for p in mine])
    for p in (problems := coverage(spec[1], load(root) or [], a.max_steps)):
        print(f"[skift] coverage: {p[2]}")
    return 1 if problems else 0

def build(a, root: Path, scope: set | None) -> int:
    streak, fid, totals = 0, None, {}
    for n in itertools.count():
        if STOP or (a.max_iterations and n >= a.max_iterations):
            print("[skift] stopped" if STOP else f"[skift] stopped after {a.max_iterations} iterations")
            return 0
        feats, gap = load(root) or [], section(root, "Gaps")
        if not todo(feats, scope, []):
            print(f"[skift] all {len(feats)} features pass" if scope is None else
                  f"[skift] all {sum(f.get('spec') in scope for f in feats)} features up to {a.until} pass")
            return 0
        if not (queue := todo(feats, scope, gap)):
            print(f"[skift] every feature left has a gap under ## Gaps in {PROGRESS}; answer each, delete its line, rerun:")
            print("\n".join(f"  {g}" for g in gap))
            return 1
        streak, fid = (streak + 1 if queue[0].get("id") == fid else 1), queue[0].get("id")
        print(f"[skift] feature {fid}, session {streak}: {queue[0].get('description', '')}")
        feature = json.dumps({k: queue[0].get(k) for k in ("id", "spec", "description", "steps")}, indent=2)
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
    p.add_argument("--until", metavar="HEADING", help="build only features under this top-level Features heading or an earlier one, then stop")
    p.add_argument("--bypass", action="store_true", help="sessions run with bypassPermissions instead of auto")
    p.add_argument("--status", action="store_true", help="per slice, in spec order: passing/total, gaps and findings; spawn no session")
    p.add_argument("--dry-run", action="store_true", help="print requirement IDs, workloads and, with --until, the features to build; spawn no session")
    a = p.parse_args()
    root = Path(a.project_dir).resolve()
    sys.stdout.reconfigure(line_buffering=True)
    signal.signal(signal.SIGINT, on_sigint)
    spec = (*parse_spec((root / SPEC).read_text(encoding="utf-8")),
            (root / DECISIONS).read_text(encoding="utf-8").splitlines() if (root / DECISIONS).is_file() else [])
    feats, reqs = load(root), spec[1]
    if a.status: return status(root, reqs, feats or [])
    scope = until_ids(reqs, a.until) if a.until else None
    uncited = [r for r in reqs if r not in {f.get("spec") for f in feats or []}]
    workloads = cut(spec, uncited if feats is None or a.append else [], a.spec_cap_tokens)
    changed = stale(root, reqs, feats) if feats is not None else []
    print(f"[skift] {len(reqs)} requirement(s), {len(uncited)} cited by no feature" + (" (--append adds them)" if feats and uncited and not a.append else ""))
    for r in reqs if a.dry_run else ():
        print(f"[skift] requirement {r}")
    for n, ids in enumerate(workloads, 1):
        print(f"[skift] workload {n}, ~{size(spec, ids):.0f} tokens: {' '.join(ids)}")
    for kind, _, msg in changed + (coverage(reqs, feats, a.max_steps) if a.dry_run and feats is not None else []):
        print(f"[skift] {kind}: {msg}")
    for f in todo(feats, scope, section(root, "Gaps")) if a.dry_run and scope is not None and feats is not None else ():
        print(f"[skift] would build feature {f.get('id')} ({f.get('spec')}): {f.get('description', '')}")
    if a.dry_run: return 0
    if changed:
        edited = " ".join(c[1] for c in changed if c[0] == "edited")
        print("[skift] review those features in features.json: edit them, or remove them and rerun with --append"
              + (f'\n[skift] then acknowledge the edits: git commit --allow-empty -am "skift: reviewed {edited}"' if edited else ""))
        return 1
    if workloads and ((rc := decompose(a, root, spec, workloads)) or STOP):
        return rc
    return build(a, root, scope)

if __name__ == "__main__":
    try:
        sys.exit(main())
    except json.JSONDecodeError as e:
        sys.exit(f"[skift] {FEATURES} is not valid JSON: {e}")
    except (OSError, ValueError) as e:  # a missing spec, a heading that does not slug, a requirement over the cap
        sys.exit(f"[skift] {e}")
    except KeyboardInterrupt:
        sys.exit("[skift] stopped")
