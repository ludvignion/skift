#!/usr/bin/env python3
"""skift driver. /skift:spec turns a spec of any size into kanban/map.md (every slice in build order, with
the spec sections it covers) and kanban/features/NN-<slice>.json (the features of the slices detailed so
far, each citing its sections); this script indexes the spec, checks that nothing in it is dropped, and
builds the features, one fresh `claude -p` each, until all pass or --until's slice is done. A feature
named under ## Gaps in progress.md is skipped. A spec edit stops only the features whose sections changed.
Every run ends with a handoff in .skift/handoff.md: what you can do now, how to open it, what to check,
what was decided for you, what is not built, and what to do next. Ctrl+C stops after the current
session; a second Ctrl+C stops now."""
import argparse, contextlib, hashlib, itertools, json, os, re, signal, subprocess, sys, threading, time, unicodedata  # noqa: E401
from pathlib import Path

MODEL = "sonnet"
MAX_TURNS = 200  # per session
MAX_SESSIONS_PER_FEATURE = 3  # consecutive sessions on one feature without passing, then stop
SESSION_TIMEOUT = 3600  # seconds per session
INIT_TIMEOUT = 180  # seconds for ./init.sh when the run ends
SMALL_SPEC_CHARS = 60000  # up to this, /skift:spec reads the spec whole and details every slice at once
CHUNK_LINES = 80  # own text longer than this is cited in parts, <id>~1, <id>~2, ...

PROMPTS = Path(__file__).resolve().parent.parent / "prompts"
FEATURES, MAP, INDEX, SOURCE = "kanban/features", "kanban/map.md", "kanban/index.md", "kanban/source.json"
PROGRESS, HANDOFF, LEGACY = "progress.md", ".skift/handoff.md", "features.json"  # LEGACY: the feature file before 0.4
SECTIONS = ("Current", "Log", "Built", "Decided", "Gaps", "Findings")  # of progress.md
FILE_RE, NOTE_RE = re.compile(r"^(\d+)-[a-z0-9]+(?:-[a-z0-9]+)*$"), re.compile(r"\bfeature #?(\d+)\b", re.I)
HEADING_RE, FENCE_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$"), re.compile(r"^\s*(```|~~~)")
EXPLICIT_ID = re.compile(r"\b(?:REQ|FR|NFR|US|UC|BR)-\d{1,6}\b")  # requirement ids a heading may carry
TRANSLIT = str.maketrans({"ø": "o", "Ø": "O", "æ": "ae", "Æ": "AE", "ß": "ss", "ł": "l", "Ł": "L", "đ": "d", "Đ": "D", "ð": "d", "þ": "th"})
SLICE_LINE_RE, SRC_RE = re.compile(r"^- (\d+-[a-z0-9]+(?:-[a-z0-9]+)*):\s*(.*?)\s*\[src:"), re.compile(r"\[src:\s*([^\]]*)\]\s*$")
TOOL_KEYS = ("command", "file_path", "path", "pattern")
STOP: list = []  # non-empty once Ctrl+C was pressed


# The spec index: sections by id, read straight from the spec each time, so line numbers never go stale.

def slug(text: str) -> str:
    """Lowercase a-z0-9 with runs of anything else as `-`: accents dropped (å→a, é→e), and ø→o, æ→ae, ß→ss."""
    plain = "".join(c for c in unicodedata.normalize("NFKD", text.translate(TRANSLIT)) if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "-", re.sub(r"[`*_\[\]()]", "", plain).lower()).strip("-")[:48] or "untitled"

def spec_files(root: Path, spec: str) -> list[Path]:
    path = root / spec
    if path.is_dir(): return sorted(p for p in path.rglob("*.md") if p.is_file())
    if path.is_file(): return [path]
    raise ValueError(f"{spec}: no such file or folder")

def chunks(lines: list[str], first: int) -> list[tuple[int, int]]:
    """Line ranges, 1-based and inclusive, of `lines` (which start at line `first`), cut at blank lines into
    parts of at least CHUNK_LINES // 2 lines."""
    out, a, count = [], None, 0
    for n, line in enumerate(lines, first):
        if line.strip():
            a, count = (n if a is None else a), count + 1
        elif a is not None and count >= CHUNK_LINES // 2:
            out.append((a, n - 1))
            a, count = None, 0
    if a is not None: out.append((a, first + len(lines) - 1))
    return out

def index(root: Path, spec: str) -> dict[str, dict]:
    """Every section of the spec, in document order, by id: parent, depth, file, start, end, title, own, hash.
    A section is a heading and its subtree (start-end); its own text is what stands before its first subheading.
    Its id is a requirement id in the heading (REQ-12, FR-3, ...), else the slug path of its headings. A file's
    single H1 is its title: it stays out of the paths, and citing it covers only its own text. With several
    files, each file is a section too, its id its path, holding everything in it. Own text over CHUNK_LINES
    lines is split into sections <id>~1, <id>~2, ... Two same-named siblings: <id>, <id>-2."""
    files, rows = spec_files(root, spec), {}
    for path in files:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        heads, fence = [], False
        for n, line in enumerate(lines, 1):
            if FENCE_RE.match(line):
                fence = not fence
            elif not fence and (m := HEADING_RE.match(line)):
                heads.append((n, len(m[1]), m[2].strip()))
        title_h1 = sum(level == 1 for _, level, _ in heads) == 1
        lead = [slug(p) for p in Path(os.path.relpath(path, root / spec)).with_suffix("").parts] if len(files) > 1 else []
        rel, stack = os.path.relpath(path, root), []  # stack: (level, slug, id) of the headings still open
        top = "/".join(lead) or None  # with several files, the file's own section
        if top:
            first = heads[0][0] - 1 if heads else len(lines)
            rows[top] = {"id": top, "parent": None, "depth": 0, "file": rel, "start": 1, "end": len(lines),
                         "title": rel, "own": "\n".join(lines[:first]).strip()}
        for k, (start, level, title) in enumerate(heads):
            body_end = heads[k + 1][0] - 1 if k + 1 < len(heads) else len(lines)
            end = next((h[0] - 1 for h in heads[k + 1:] if h[1] <= level), len(lines))
            while stack and stack[-1][0] >= level: stack.pop()
            path_ = [s for lv, s, _ in stack if not (title_h1 and lv == 1)]
            base = m[0] if (m := EXPLICIT_ID.search(title)) else "/".join(lead + path_ + [slug(title)])
            sid, n = base, 2
            while sid in rows: sid, n = f"{base}-{n}", n + 1
            parent = next((i for lv, _, i in reversed(stack) if not (title_h1 and lv == 1)), top)
            depth = len([1 for lv, _, _ in stack if not (title_h1 and lv == 1)]) + bool(top)
            stack.append((level, slug(title), sid))
            own = lines[start:body_end]
            rows[sid] = {"id": sid, "parent": parent, "depth": depth, "file": rel, "start": start, "end": end,
                         "title": title, "own": "\n".join(own).strip()}
            if sum(1 for line in own if line.strip()) > CHUNK_LINES:
                rows[sid]["own"] = ""
                for c, (a, b) in enumerate(chunks(own, start + 1), 1):
                    rows[f"{sid}~{c}"] = {"id": f"{sid}~{c}", "parent": sid, "depth": depth + 1, "file": rel, "start": a,
                                          "end": b, "title": f"{title}, part {c}", "own": "\n".join(lines[a - 1:b]).strip()}
    for r in rows.values():
        r["hash"] = hashlib.sha256(re.sub(r"\s+", " ", r["own"]).encode()).hexdigest()[:16]
    return rows

def summary(row: dict) -> str:
    first = next((line.strip() for line in row["own"].splitlines() if line.strip() and not line.lstrip().startswith(("|", "<", "!["))), "")
    first = re.sub(r"\s+", " ", first).replace("|", "/")
    return first[:110] + "..." if len(first) > 110 else first

def write_index(root: Path, spec: str, rows: dict) -> None:
    out = [f"# Spec index of {spec}", "", "Written by skift from the spec; do not edit. Read a section with",
           "`loop.py --show <id>`. Each line: id | file:lines | lines of own text | heading | first line.", ""]
    for r in rows.values():
        own = sum(1 for line in r["own"].splitlines() if line.strip())
        out.append(f"{'  ' * r['depth']}- {r['id']} | {r['file']}:{r['start']}-{r['end']} | own={own} | {r['title'].replace('|', '/')} | {summary(r)}")
    (root / INDEX).parent.mkdir(parents=True, exist_ok=True)
    (root / INDEX).write_text("\n".join(out) + "\n", encoding="utf-8")

def text_of(root: Path, row: dict, numbered: bool = False) -> str:
    lines = (root / row["file"]).read_text(encoding="utf-8", errors="replace").splitlines()[row["start"] - 1:row["end"]]
    body = [f"{n:>6}  {line}" if numbered else line for n, line in enumerate(lines, row["start"])]
    return "\n".join([f"## {row['id']}  ({row['file']}:{row['start']}-{row['end']})", *body])

def under(sid: str | None, anc: str, parents: dict) -> bool:
    """Whether section `sid` is `anc` or lies inside it."""
    seen = set()
    while sid is not None and sid not in seen:
        if sid == anc: return True
        seen.add(sid)
        sid = parents.get(sid)
    return False

def units(rows: dict) -> list[str]:
    """The sections with text of their own: what the map and the features must cover."""
    return [i for i, r in rows.items() if r["own"]]

def spec_path(root: Path) -> str:
    """The spec: from kanban/source.json once /skift:spec is done, else from the index's first line."""
    if (root / SOURCE).is_file(): return json.loads((root / SOURCE).read_text(encoding="utf-8"))["spec"]
    if (root / INDEX).is_file() and (m := re.match(r"# Spec index of (.+)", (root / INDEX).read_text(encoding="utf-8"))): return m[1].strip()
    raise ValueError(f"no spec yet: run --index <your spec> first")


# The map and the features.

def read_map(root: Path) -> dict | None:
    """kanban/map.md: the slices in build order (name, what, source), and the sections under ## Context and
    ## Out of scope. Each line ends in [src: <section id>, ...]."""
    if not (root / MAP).is_file(): return None
    mp, part = {"slices": [], "context": [], "out": []}, None
    for line in (root / MAP).read_text(encoding="utf-8").splitlines():
        if h := re.match(r"^##\s+(.+?)\s*$", line):
            part = {"slices": "slices", "context": "context", "out of scope": "out"}.get(h[1].lower())
        elif part and (s := SRC_RE.search(line)):
            ids = [x.strip() for x in s[1].split(",") if x.strip()]
            if part != "slices": mp[part] += ids
            elif m := SLICE_LINE_RE.match(line.strip()): mp["slices"].append({"name": m[1], "what": m[2], "source": ids})
    mp["slices"].sort(key=lambda s: (int(s["name"].split("-")[0]), s["name"]))
    return mp

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

def check(rows: dict, mp: dict, feats: list[dict], detailed: set) -> list[str]:
    """Why the map and the features do not fit the spec: sections that do not exist, features citing outside
    their slice, and sections with text that no slice, no feature of a detailed slice, Context or Out of scope covers."""
    parents, problems = {i: r["parent"] for i, r in rows.items()}, []
    names, numbers = [s["name"] for s in mp["slices"]], [s["name"].split("-")[0] for s in mp["slices"]]
    problems += [f"{MAP}: slice number {n} is used twice" for n in sorted({n for n in numbers if numbers.count(n) > 1})]
    for sid in dict.fromkeys([i for s in mp["slices"] for i in s["source"]] + mp["context"] + mp["out"]):
        if sid not in rows: problems.append(f"{MAP}: section {sid} is not in the spec")
    problems += [f"{FEATURES}/{s}.json: slice {s} is not in {MAP}" for s in sorted(detailed - set(names))]
    by_name = {s["name"]: s for s in mp["slices"]}
    for f in (f for f in feats if f["_slice"] in by_name):
        src = f.get("source")
        if not (isinstance(src, list) and src and all(isinstance(x, str) for x in src)):
            problems.append(f"feature {f['id']}: needs \"source\", the list of spec sections it comes from")
            continue
        for sid in src:
            if sid not in rows: problems.append(f"feature {f['id']}: section {sid} is not in the spec")
            elif not any(under(sid, a, parents) for a in by_name[f["_slice"]]["source"]):
                problems.append(f"feature {f['id']}: section {sid} lies outside its slice {f['_slice']}")
    inside = lambda sid, ancestors: any(under(sid, a, parents) for a in ancestors)  # noqa: E731
    for sid in units(rows):
        if inside(sid, mp["context"] + mp["out"]): continue
        homes = [s for s in mp["slices"] if inside(sid, s["source"])]
        if not homes: problems.append(f"section {sid} ({rows[sid]['title']}) is in no slice of {MAP}, nor under Context or Out of scope")
        for s in (s for s in homes if s["name"] in detailed):
            if not inside(sid, [x for f in feats if f["_slice"] == s["name"] for x in f.get("source") or []]):
                problems.append(f"slice {s['name']}: no feature cites section {sid} ({rows[sid]['title']})")
    return problems

def record(root: Path, spec: str, rows: dict) -> None:
    """kanban/source.json: the spec, and each section's hash and parent, as the features were written."""
    data = {"spec": spec, "sections": {i: r["hash"] for i, r in rows.items()}, "parents": {i: r["parent"] for i, r in rows.items()}}
    (root / SOURCE).write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")

def changes(root: Path, rows: dict) -> dict:
    """What changed in the spec since /skift:spec: sections edited, added and removed, and the old parents."""
    src = json.loads((root / SOURCE).read_text(encoding="utf-8")) if (root / SOURCE).is_file() else {}
    old = src.get("sections", {})
    return {"edited": {i for i in rows if i in old and rows[i]["hash"] != old[i]}, "added": set(rows) - set(old) if old else set(),
            "removed": set(old) - set(rows), "old_parents": src.get("parents", {})}

def affected(f: dict, ch: dict, rows: dict) -> list[str]:
    """The edited, added or removed sections inside what feature f cites."""
    new = {i: r["parent"] for i, r in rows.items()}
    cites = f.get("source") or []
    hit = [i for i in ch["edited"] | ch["added"] if any(under(i, a, new) for a in cites)]
    return sorted(hit + [i for i in ch["removed"] if any(under(i, a, ch["old_parents"]) for a in cites)])

def uncovered_new(rows: dict, mp: dict, ch: dict) -> list[str]:
    """Sections with text added to the spec since /skift:spec that no slice, Context or Out of scope covers."""
    parents = {i: r["parent"] for i, r in rows.items()}
    held = [i for s in mp["slices"] for i in s["source"]] + mp["context"] + mp["out"]
    return [i for i in units(rows) if i in ch["added"] and not any(under(i, a, parents) for a in held)]

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

def state(root: Path) -> dict:
    """What a run, --status and --dry-run look at: the spec, its sections, the map, the features, which slices
    are detailed, what changed in the spec, which features that touches, and new sections in no slice."""
    if (root / LEGACY).is_file(): raise ValueError(f"{LEGACY} is from skift before 0.4: rerun /skift:spec <your spec>")
    if not (root / SOURCE).is_file(): raise ValueError(f"{SOURCE} is missing: run /skift:spec <your spec>")
    spec = spec_path(root)
    if (mp := read_map(root)) is None: raise ValueError(f"{MAP} is missing: rerun /skift:spec {spec}")
    rows, feats = index(root, spec), load(root)
    ch = changes(root, rows)
    return {"spec": spec, "rows": rows, "map": mp, "feats": feats, "detailed": {p.stem for p in slices(root)}, "changes": ch,
            "affected": {f["id"]: affected(f, ch, rows) for f in feats}, "new": uncovered_new(rows, mp, ch)}

def until_scope(order: list[str], until: str) -> set[str]:
    """The slices up to and including `until`: its file name (01-orders), its name (orders) or its number (1)."""
    hit = [s for s in order if until in (s, s.split("-", 1)[1]) or (until.isdigit() and int(until) == int(s.split("-")[0]))]
    if not hit: raise ValueError(f"--until {until}: no slice has that name ({', '.join(order)})")
    return set(order[:order.index(hit[0]) + 1])

def todo(feats: list[dict], scope: set | None, gapped: set) -> list[dict]:
    """Features to build, in build order: open, inside --until's slices, not named under ## Gaps."""
    return [f for f in feats if not f["passes"] and (scope is None or f["_slice"] in scope) and f["id"] not in gapped]

def plural(n: int, word: str) -> str:
    return f"{n} {word}{'s' * (n != 1)}"

def build_index(root: Path, spec: str) -> int:
    """--index: write kanban/index.md, and say whether /skift:spec reads the spec whole or works from the index."""
    rows, files = index(root, spec), spec_files(root, spec)
    write_index(root, spec, rows)
    chars = sum(len(p.read_text(encoding="utf-8", errors="replace")) for p in files)
    print(f"[skift] {plural(len(rows), 'section')}, {len(units(rows))} with text, from {plural(len(files), 'file')}, {chars} characters: {INDEX}")
    print("[skift] small: read the spec whole, and write the features of every slice now" if chars <= SMALL_SPEC_CHARS else
          "[skift] large: work from the index, read sections with --show, and write the features of the first slice only")
    return 0

def show(root: Path, ids: list[str]) -> int:
    """--show: each section's text with its line numbers, read from the spec as it is now."""
    rows = index(root, spec_path(root))
    for sid in ids:
        print((text_of(root, rows[sid], numbered=True) if sid in rows else f"## {sid}: not in the spec") + "\n")
    return 0 if all(i in rows for i in ids) else 1

def grep(root: Path, pattern: str) -> int:
    """--grep: the sections whose heading or own text matches, with the first matching line."""
    rx, rows = re.compile(pattern, re.I), index(root, spec_path(root))
    for r in rows.values():
        line = summary(r) if rx.search(r["title"]) else next((x.strip() for x in r["own"].splitlines() if rx.search(x)), None)
        if line is not None: print(f"- {r['id']} | {r['file']}:{r['start']}-{r['end']} | {r['title']} | {line[:160]}")
    return 0

def mark(root: Path, spec: str) -> int:
    """--mark-spec: index the spec, check the map and the features against it, and when they fit, record each
    section's hash in kanban/source.json and print the status."""
    rows = index(root, spec)
    write_index(root, spec, rows)
    if (mp := read_map(root)) is None: raise ValueError(f"{MAP} is missing: write it first")
    problems = check(rows, mp, load(root), {p.stem for p in slices(root)})
    ensure_progress(root)
    for p in problems: print(f"[skift] problem: {p}")
    if problems:
        print(f"[skift] {plural(len(problems), 'problem')}: fix them, then run --mark-spec again")
        return 1
    record(root, spec, rows)
    return status(root)

def status(root: Path) -> int:
    """--status: per slice, in build order: passing/total, gaps and findings, then each feature; slices not
    detailed yet; and what changed in the spec."""
    st = state(root)
    feats, gaps, found = st["feats"], notes(root, "Gaps"), notes(root, "Findings")
    print(f"[skift] {sum(f['passes'] for f in feats)}/{len(feats)} features pass · {len(st['detailed'])} of {plural(len(st['map']['slices']), 'slice')} detailed")
    for s in st["map"]["slices"]:
        if s["name"] not in st["detailed"]:
            print(f"[skift] {s['name']}  not detailed yet: {s['what']}")
            continue
        mine = [f for f in feats if f["_slice"] == s["name"]]
        g, fi = (sum(len(n.get(f["id"], [])) for f in mine) for n in (gaps, found))
        print(f"[skift] {s['name']}  {sum(f['passes'] for f in mine)}/{len(mine)} passing · {plural(g, 'gap')} · {plural(fi, 'finding')}")
        for f in mine:
            marks = ("  (gap)" if f["id"] in gaps else "") + (("  (spec changed since it passed)" if f["passes"] else "  (spec changed)") if st["affected"][f["id"]] else "")
            print(f"[skift]   [{'x' if f['passes'] else ' '}] {f['id']}  {f['description']}{marks}")
    for i in st["new"]: print(f"[skift] new in the spec, in no slice: {i} ({st['rows'][i]['title']})")
    return 0

def dry_run(root: Path, a: argparse.Namespace) -> int:
    """--dry-run: what a run would build, skip or refuse."""
    st = state(root)
    order = [s["name"] for s in st["map"]["slices"]]
    scope, gapped = until_scope(order, a.until) if a.until else None, set(notes(root, "Gaps"))
    for f in todo(st["feats"], scope, set()):
        why = "blocked, spec changed" if st["affected"][f["id"]] else "skip, gap" if f["id"] in gapped else "would build"
        print(f"[skift] {why}: feature {f['id']} ({f['_slice']}): {f['description']}")
    for s in (s for s in order if (scope is None or s in scope) and s not in st["detailed"]):
        print(f"[skift] not detailed yet: {s}: /skift:spec --next writes its features")
    for i in st["new"]: print(f"[skift] new in the spec, in no slice: {i} ({st['rows'][i]['title']})")
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
    st, streak, fid = run["state"], 0, None
    for n in itertools.count():
        if STOP: return "stopped"
        if a.max_iterations and n >= a.max_iterations: return "limit"
        feats, gapped = load(root), set(notes(root, "Gaps"))
        if not todo(feats, run["scope"], set()): return "done"
        if not (queue := todo(feats, run["scope"], gapped)): return "gaps"
        f = queue[0]
        streak, fid = (streak + 1 if f["id"] == fid else 1), f["id"]
        print(f"[skift] feature {fid} ({f['_slice']}), session {streak}: {f['description']}")
        source = "\n\n".join(text_of(root, st["rows"][i]) for i in f.get("source") or [] if i in st["rows"])
        prompt = fill("coding.md", FEATURE=json.dumps({k: f[k] for k in ("id", "description", "steps")}, indent=2, ensure_ascii=False),
                      ID=fid, MAX_TURNS=a.max_turns, FEATURE_FILE=f"{FEATURES}/{f['_slice']}.json", SPEC=st["spec"],
                      SOURCE=source or "(the feature cites no section; its description and steps are all there is)")
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
        st = state(root)
        order = [s["name"] for s in st["map"]["slices"]]
        run.update(state=st, order=order, scope=until_scope(order, a.until) if a.until else None)
        if stray := sorted(st["detailed"] - set(order)):
            raise ValueError(f"{FEATURES}/{stray[0]}.json is a slice {MAP} does not list: rerun /skift:spec {st['spec']}")
        blocked = [f for f in st["feats"] if st["affected"][f["id"]] and not f["passes"] and (run["scope"] is None or f["_slice"] in run["scope"])]
        if blocked:
            raise ValueError("the spec changed under " + "; ".join(f"feature {f['id']} ({', '.join(st['affected'][f['id']][:3])})" for f in blocked[:5])
                             + f": rerun /skift:spec {st['spec']} to update those features")
    except ValueError as e:
        return "refused", str(e)
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
    what is not built, what changed in the spec, and what to do next. About the product, never files or code."""
    try:
        feats = load(root)
    except ValueError:
        feats = []
    st, scope = run.get("state") or {}, run.get("scope")
    order = run.get("order") or list(dict.fromkeys(f["_slice"] for f in feats))
    detailed = st.get("detailed") or {f["_slice"] for f in feats}
    by_id = {f["id"]: f for f in feats}
    built, decided, gaps = notes(root, "Built"), notes(root, "Decided"), notes(root, "Gaps")
    passed = [by_id[i] for i in dict.fromkeys(run["passed"]) if i in by_id]
    wanted = [f for f in feats if scope is None or f["_slice"] in scope]
    last = max(scope, key=order.index) if scope else None
    waiting = [s for s in order if (scope is None or s in scope) and s not in detailed]  # in scope, no features written yet
    tally = f"({sum(f['passes'] for f in wanted)} of {len(wanted)} features pass)"
    head = {
        "done": f"skift: built up to {last} {tally}" if last else
                f"skift: every detailed slice is built {tally}" if waiting else f"skift: everything is built {tally}",
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
    elif outcome == "done" and wanted:
        out += ["", "Nothing new was built: every feature in scope already passed."]
    if outcome not in ("refused", "done") and (left := [f for f in wanted if not f["passes"]]):
        out += ["", "Not built"]
        for f in left[:10]:
            why = (f"waiting for your answer: {gaps[f['id']][-1]}" if f["id"] in gaps else
                   "does not pass yet; where it stopped is under ## Current in progress.md" if run["stuck"] and f["id"] == run["stuck"][0] else "open")
            out.append(f"  - feature {f['id']}, {f['description']}: {why}")
        if len(left) > 10: out.append(f"  - and {len(left) - 10} more")
    moved = [f for f in feats if f["passes"] and (st.get("affected") or {}).get(f["id"])]
    if moved: out += ["", "The spec changed under these built features"] + [f"  - feature {f['id']}, {f['description']}" for f in moved]
    if st.get("new"): out += ["", "New in the spec, in no slice yet"] + [f"  - {st['rows'][i]['title']}" for i in st["new"][:10]]
    again = "/skift:run" + (f" --until {a.until}" if a.until else "")
    after = [s for s in (order[order.index(last) + 1:] if last else order) if s not in detailed or any(not f["passes"] for f in feats if f["_slice"] == s)]
    upcoming, check_ = (waiting or after or [None])[0], "Check the boxes above, then " if passed else ""
    stale = upcoming in detailed and any((st.get("affected") or {}).get(f["id"]) and not f["passes"] for f in feats if f["_slice"] == upcoming)
    nxt = {
        "done": (("Check the boxes above. " if passed else "") + "Everything is built." if upcoming is None else
                 f"{check_}/skift:spec --next to write the features of {upcoming}" if upcoming not in detailed else
                 f"{check_}/skift:spec {st.get('spec')} to update the features of {upcoming} the spec changed under, then /skift:run --until {upcoming}" if stale else
                 f"{check_}/skift:run --until {upcoming}"),
        "gaps": f"Answer each question in kanban/context.md, delete its line under ## Gaps in progress.md, then {again}",
        "stuck": f"Read ## Current in progress.md, clear up what blocks the feature (kanban/context.md or its steps), then {again}",
        "stopped": f"Continue with {again}",
        "limit": f"Continue with {again}",
        "refused": "Fix that, then /skift:run",
        "failed": f"Fix that, then {again}",
    }[outcome]
    if (moved or st.get("new")) and outcome != "refused" and "/skift:spec " not in nxt: nxt += f"\n  For the spec changes above: /skift:spec {st['spec']}"
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
    p.add_argument("--status", action="store_true", help="per slice: passing/total, gaps, findings and each feature; spec changes")
    p.add_argument("--dry-run", action="store_true", help="what a run would build, skip or refuse")
    p.add_argument("--index", metavar="SPEC", help="for /skift:spec: index the spec (a .md file or a folder) into kanban/index.md")
    p.add_argument("--show", metavar="ID", nargs="+", help="for /skift:spec: print these sections of the spec, with line numbers")
    p.add_argument("--grep", metavar="REGEX", help="for /skift:spec: the sections whose heading or text matches")
    p.add_argument("--mark-spec", metavar="SPEC", help="for /skift:spec: check the map and the features against the spec, and record it")
    a = p.parse_args()
    root = Path(a.project_dir).resolve()
    sys.stdout.reconfigure(line_buffering=True)
    reports = {"index": lambda: build_index(root, a.index), "show": lambda: show(root, a.show), "grep": lambda: grep(root, a.grep),
               "mark_spec": lambda: mark(root, a.mark_spec), "status": lambda: status(root), "dry_run": lambda: dry_run(root, a)}
    if chosen := [k for k in reports if getattr(a, k)]:  # reports start no session and leave the handoff alone
        try:
            return reports[chosen[0]]()
        except BrokenPipeError:  # piped into head: fine
            os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
            return 0
        except (OSError, ValueError, re.error) as e:
            print(f"[skift] {e}")
            return 1
    signal.signal(signal.SIGINT, on_sigint)
    run: dict = {"passed": [], "stuck": None, "scope": None}
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
