#!/usr/bin/env python3
"""skift kanban. skift turns a spec into requirements and stops: /skift:spec indexes the spec and has it
grilled where it is too thin, /skift:tasks cuts it into tasks under kanban/tasks/ (one workstream each,
citing the spec sections it covers), and /skift:kanban writes a task's tickets under kanban/tickets/, each
with acceptance criteria. This script indexes the spec, shows its sections, checks the spec's shape, checks
that the tasks and tickets drop nothing and contradict nothing, records each section's hash, and prints the
board. It builds nothing: you tell Claude what to build, in your own session."""
import argparse, hashlib, json, os, re, sys, unicodedata  # noqa: E401
from pathlib import Path

SMALL_SPEC_CHARS = 60000  # up to this, the spec is read whole and every task is written at once
CHUNK_LINES = 80  # own text longer than this is cited in parts, <id>~1, <id>~2, ...

TASKS, TICKETS, DEFERRED = "kanban/tasks", "kanban/tickets", "kanban/deferred.md"
INDEX, SOURCE, PROGRESS = "kanban/index.md", "kanban/source.json", "progress.md"
LEGACY = ("features.json", "kanban/features", "kanban/map.md")  # skift before 1.0
SECTIONS = ("Current", "Log", "Decided", "Deviations", "Gaps", "Findings")  # of progress.md
STATUSES = ("ready", "in_progress", "in_review", "done")  # of a ticket; only a person sets done
AC_TAGS = ("behavioral", "property", "critical", "human")  # human: no test names it, a person confirms it
NOTE_RE = re.compile(r"\bticket #?(\d+\.\d+)\b", re.I)
HEADING_RE, FENCE_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$"), re.compile(r"^\s*(```|~~~)")
EXPLICIT_ID = re.compile(r"\b(?:REQ|FR|NFR|US|UC|BR)-\d{1,6}\b")  # requirement ids a heading may carry
TRANSLIT = str.maketrans({"ø": "o", "Ø": "O", "æ": "ae", "Æ": "AE", "ß": "ss", "ł": "l", "Ł": "L", "đ": "d", "Đ": "D", "ð": "d", "þ": "th"})
FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.S)
TASK_RE = re.compile(r"^(\d+)-([a-z0-9]+(?:-[a-z0-9]+)*)$")
TICKET_RE = re.compile(r"^(\d+)\.(\d+)-([a-z0-9]+(?:-[a-z0-9]+)*)$")
AC_RE = re.compile(r"^-\s*AC-(\d+)\s*(?:\(([a-z]+)\))?\s*:\s*(.+)$")
CITE_RE = re.compile(r"\[([^\]]+)\]")
DEFER_RE = re.compile(r"^-\s*`?([^\s`]+)`?\s*(?:—|–|--|-)\s*(\S.*)$")
COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
SPEC_HEADS = ("Purpose", "Parts in build order", "Systems", "Built with", "Out of scope")  # skift's own spec shape
VAGUE = ("fast", "quick", "easy", "simple", "user-friendly", "intuitive", "robust", "scalable", "flexible",
         "seamless", "modern", "clean", "efficient", "as needed", "and/or", "etc.", "tbd", "if needed")
SECRET_RE = re.compile(r"(?i)\b(api[_-]?key|secret|token|password|passwd|bearer)\b\s*[:=]\s*\S")


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
    out = [f"# Spec index of {spec}", "", "Written by skift from the spec; do not edit. Read a section at its file:lines.",
           "Each line: id | file:lines | lines of own text | heading | first line.", ""]
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
    """The sections with text of their own: what the tasks and the deferred list must cover."""
    return [i for i, r in rows.items() if r["own"]]

def spec_path(root: Path) -> str:
    """The spec: from kanban/source.json once /skift:spec is done, else from the index's first line."""
    if (root / SOURCE).is_file(): return json.loads((root / SOURCE).read_text(encoding="utf-8"))["spec"]
    if (root / INDEX).is_file() and (m := re.match(r"# Spec index of (.+)", (root / INDEX).read_text(encoding="utf-8"))): return m[1].strip()
    raise ValueError(f"no spec yet: run --index <your spec> first")


# What the spec looked like when the tickets were written.

def record(root: Path, spec: str, rows: dict) -> None:
    """kanban/source.json: the spec, and each section's hash and parent, as the tickets were written."""
    data = {"spec": spec, "sections": {i: r["hash"] for i, r in rows.items()}, "parents": {i: r["parent"] for i, r in rows.items()}}
    (root / SOURCE).write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")

def changes(root: Path, rows: dict) -> dict:
    """What changed in the spec since the tickets were written: sections edited, added and removed, and the old parents."""
    src = json.loads((root / SOURCE).read_text(encoding="utf-8")) if (root / SOURCE).is_file() else {}
    old = src.get("sections", {})
    return {"edited": {i for i in rows if i in old and rows[i]["hash"] != old[i]}, "added": set(rows) - set(old) if old else set(),
            "removed": set(old) - set(rows), "old_parents": src.get("parents", {})}

def section(root: Path, name: str) -> list[str]:
    """The items under `## <name>` in progress.md, one per bullet, its wrapped lines joined."""
    out, on = [], False
    for line in (root / PROGRESS).read_text(encoding="utf-8").splitlines() if (root / PROGRESS).is_file() else []:
        if re.match(r"#{1,2}\s", line): on = line.strip().lower() == f"## {name.lower()}"
        elif on and line.strip():
            if out and not re.match(r"\s*[-*]\s", line): out[-1] += " " + line.strip()
            else: out.append(line.strip())
    return out

def notes(root: Path, name: str) -> dict[str, list[str]]:
    """The items under `## <name>` in progress.md by the ticket they start with (`- ticket N.M:`), else by every
    ticket they name, without that prefix."""
    out: dict[str, list[str]] = {}
    for line in section(root, name):
        lead = re.match(r"^-\s*(\d{4}-\d{2}-\d{2}\s+)?ticket #?(\d+\.\d+)\s*:\s*", line, re.I)
        text = line[lead.end():] if lead else line
        for i in [lead[2]] if lead else NOTE_RE.findall(line): out.setdefault(i, []).append(text)
    return out

def ensure_progress(root: Path) -> None:
    """progress.md with every section, added at the end where one is missing."""
    path = root / PROGRESS
    text = path.read_text(encoding="utf-8") if path.is_file() else "# Progress\n"
    have = {m.lower() for m in re.findall(r"^## +(.+?)\s*$", text, re.M)}
    missing = [f"## {s}\n" for s in SECTIONS if s.lower() not in have]
    if missing: path.write_text(text.rstrip("\n") + "\n\n" + "\n".join(missing), encoding="utf-8")

def plural(n: int, word: str) -> str:
    return f"{n} {word}{'s' * (n != 1)}"

def spec_chars(root: Path, spec: str) -> int:
    return sum(len(p.read_text(encoding="utf-8", errors="replace")) for p in spec_files(root, spec))

def build_index(root: Path, spec: str) -> int:
    """--index: write kanban/index.md, and say whether /skift:spec reads the spec whole or works from the index."""
    rows, files, chars = index(root, spec), spec_files(root, spec), spec_chars(root, spec)
    write_index(root, spec, rows)
    print(f"[skift] {plural(len(rows), 'section')}, {len(units(rows))} with text, from {plural(len(files), 'file')}, {chars} characters: {INDEX}")
    print("[skift] small: read the spec whole" if chars <= SMALL_SPEC_CHARS else
          "[skift] large: never read it whole; work from the index and read sections with --show")
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



# The tasks, their tickets and the deferred sections.

def front(text: str) -> tuple[dict, str]:
    """A markdown file's frontmatter as {key: str or list of str}, and the body under it."""
    if not (m := FM_RE.match(text)): return {}, text
    data: dict = {}
    for line in m[1].splitlines():
        if kv := re.match(r"^([A-Za-z_][\w-]*):\s*(.*?)\s*(?:\s#.*)?$", line):
            v = kv[2].strip()
            data[kv[1]] = ([x.strip().strip("`\"'") for x in v[1:-1].split(",") if x.strip()]
                           if v.startswith("[") and v.endswith("]") else v.strip("`\"'"))
    return data, text[m.end():]

def part_of(body: str, name: str) -> str:
    """The text under `## <name>`, up to the next heading of the same level or higher, so its `###` parts stay."""
    m = re.search(rf"^##\s+{re.escape(name)}\s*$\n(.*?)(?=^#{{1,2}}\s|\Z)", body, re.S | re.M | re.I)
    return m[1].strip() if m else ""

def title_of(body: str, fallback: str, lead: str = "") -> str:
    """The `# ` heading of a task or ticket file, without the number it repeats."""
    title = next((line[2:].strip() for line in body.splitlines() if line.startswith("# ")), fallback)
    return re.sub(lead, "", title, count=1).strip() if lead else title

def tasks(root: Path) -> list[dict]:
    """kanban/tasks/<n>-<slug>.md in number order: n, name, path, title, outcome, spec_refs, after."""
    out = []
    for p in sorted((root / TASKS).glob("*.md")):
        if not (m := TASK_RE.match(p.stem)):
            raise ValueError(f"{TASKS}/{p.name}: a task file is named <n>-<slug>.md, such as 1-orders.md")
        fm, body = front(p.read_text(encoding="utf-8"))
        out.append({"n": int(m[1]), "name": p.stem, "path": f"{TASKS}/{p.name}", "title": title_of(body, p.stem, r"^Task\s+\d+\s*[:.]?\s*"),
                    "outcome": " ".join(part_of(body, "Outcome").split()),
                    "spec_refs": list(fm.get("spec_refs") or []),
                    "after": [int(x) for x in fm.get("after") or [] if str(x).strip().isdigit()]})
    numbers = [t["n"] for t in out]
    if twice := sorted({n for n in numbers if numbers.count(n) > 1}):
        raise ValueError(f"{TASKS}: task number {twice[0]} is used twice")
    return sorted(out, key=lambda t: t["n"])

def tickets(root: Path) -> list[dict]:
    """kanban/tickets/<n>.<m>-<slug>.md: id, parent, status, depends_on, writes, title, acs and the sections
    its acceptance criteria cite, in `[<section id>]` at the end of the line."""
    out = []
    for p in sorted((root / TICKETS).glob("*.md")):
        if not (m := TICKET_RE.match(p.stem)):
            raise ValueError(f"{TICKETS}/{p.name}: a ticket file is named <n>.<m>-<slug>.md, such as 1.2-place-an-order.md")
        fm, body = front(p.read_text(encoding="utf-8"))
        acs = [{"n": int(a[1]), "tag": (a[2] or ""), "text": a[3],
                "cites": [x.strip() for c in CITE_RE.findall(a[3]) for x in c.split(",") if x.strip()]}
               for line in part_of(body, "Acceptance criteria").splitlines() if (a := AC_RE.match(line.strip()))]
        out.append({"id": f"{int(m[1])}.{int(m[2])}", "parent": int(m[1]), "m": int(m[2]), "path": f"{TICKETS}/{p.name}",
                    "title": title_of(body, p.stem, r"^\d+\.\d+\s*[:.]?\s*"), "status": str(fm.get("status") or "ready").strip(),
                    "depends_on": [str(x) for x in fm.get("depends_on") or []], "writes": list(fm.get("writes") or []),
                    "acs": acs, "cites": sorted({c for a in acs for c in a["cites"]})})
    ids = [t["id"] for t in out]
    if twice := sorted({i for i in ids if ids.count(i) > 1}):
        raise ValueError(f"{TICKETS}: ticket {twice[0]} is written twice")
    return sorted(out, key=lambda t: (t["parent"], t["m"]))

def deferred(root: Path) -> list[dict]:
    """kanban/deferred.md: one `- <section id> — <reason>` line per section no task covers."""
    out = []
    for line in (root / DEFERRED).read_text(encoding="utf-8").splitlines() if (root / DEFERRED).is_file() else []:
        if not line.strip().startswith("-"): continue
        if d := DEFER_RE.match(line.strip()): out.append({"id": d[1], "reason": d[2]})
        else: out.append({"id": line.strip().lstrip("-").strip().strip("`"), "reason": ""})
    return out

def a_cycle(edges: dict) -> list | None:
    """One cycle in a graph of node -> nodes it waits for, as the nodes around it, or None."""
    state, stack = {}, []
    def walk(u):
        state[u], _ = 1, stack.append(u)
        for v in edges.get(u, []):
            if state.get(v) == 1: return stack[stack.index(v):] + [v]
            if not state.get(v) and (found := walk(v)): return found
        state[u] = 2
        stack.pop()
        return None
    for u in list(edges):
        if not state.get(u) and (found := walk(u)): return found
    return None

def spec_rows(root: Path) -> tuple[str | None, dict]:
    """The spec and its sections, or (None, {}) when the project has no spec: tasks may be written by hand."""
    try:
        spec = spec_path(root)
    except ValueError:
        return None, {}
    return spec, index(root, spec)

def coverage(root: Path) -> list[str]:
    """Why the tasks and tickets do not fit the spec, as `<path>: <what is wrong>` lines: a section in no task
    and not deferred, or in two; a cited section that is not in the spec; a deferred line without a reason; an
    `after` or `depends_on` that does not exist or runs in a circle; a ticket without sound acceptance
    criteria; and, once a task has tickets, a section of it no acceptance criterion cites."""
    spec, rows = spec_rows(root)
    ts, tk, df, out = tasks(root), tickets(root), deferred(root), []
    parents = {i: r["parent"] for i, r in rows.items()}
    covers = lambda sid, cited: [a for a in cited if under(sid, a, parents)]  # noqa: E731
    by_n = {t["n"]: t for t in ts}
    for t in ts:
        for sid in t["spec_refs"]:
            if rows and sid not in rows: out.append(f"{t['path']}: section {sid} is not in the spec (rerun /skift:spec after a spec edit)")
        for n in t["after"]:
            if n not in by_n: out.append(f"{t['path']}: after {n} is not a task")
    for d in df:
        if rows and d["id"] not in rows: out.append(f"{DEFERRED}: section {d['id']} is not in the spec")
        if not d["reason"]: out.append(f"{DEFERRED}: {d['id']} is deferred without a reason: write `- {d['id']} — <why>`")
    if found := a_cycle({t["n"]: t["after"] for t in ts}):
        out.append(f"{TASKS}: after runs in a circle: {' after '.join(str(n) for n in found)}")
    for sid in units(rows):
        homes = [t for t in ts if covers(sid, t["spec_refs"])]
        away = [d for d in df if covers(sid, [d["id"]])]
        where = [t["name"] for t in homes] + [f"deferred ({d['id']})" for d in away]
        if not where: out.append(f"{INDEX}: section {sid} ({rows[sid]['title']}) is in no task and not deferred")
        elif len(where) > 1: out.append(f"{INDEX}: section {sid} ({rows[sid]['title']}) is in {' and '.join(where)}: it belongs in one")
    for k in tk:
        if k["parent"] not in by_n: out.append(f"{k['path']}: task {k['parent']} is not in {TASKS}")
        if k["status"] not in STATUSES: out.append(f"{k['path']}: status {k['status']} is not one of {', '.join(STATUSES)}")
        if not k["acs"]: out.append(f"{k['path']}: no acceptance criteria: each is `- AC-1 (behavioral): Given ..., When ..., Then ...`")
        for a in k["acs"]:
            if a["tag"] not in AC_TAGS:
                out.append(f"{k['path']}: AC-{a['n']} is tagged {a['tag'] or '(nothing)'}: every criterion is {', '.join(AC_TAGS[:-1])} or human")
            for sid in a["cites"]:
                if rows and sid not in rows: out.append(f"{k['path']}: AC-{a['n']} cites {sid}, which is not in the spec")
                elif k["parent"] in by_n and rows and not covers(sid, by_n[k["parent"]]["spec_refs"]):
                    out.append(f"{k['path']}: AC-{a['n']} cites {sid}, which lies outside task {k['parent']}")
        for dep in k["depends_on"]:
            if dep not in {x["id"] for x in tk}: out.append(f"{k['path']}: depends_on {dep} is not a ticket")
    if found := a_cycle({k["id"]: k["depends_on"] for k in tk}):
        out.append(f"{TICKETS}: depends_on runs in a circle: {' needs '.join(found)}")
    for t in ts:
        mine = [k for k in tk if k["parent"] == t["n"]]
        cited = [c for k in mine for c in k["cites"]]
        for sid in (units(rows) if mine else []):
            if covers(sid, t["spec_refs"]) and not covers(sid, cited):
                out.append(f"{t['path']}: section {sid} ({rows[sid]['title']}) is in task {t['n']} but no acceptance criterion cites it")
    return out

def drift(root: Path, rows: dict) -> dict:
    """Sections that changed since the tickets were written, by what cites them: {task number or ticket id: ids}."""
    ch, marks = changes(root, rows), {}
    parents, old = {i: r["parent"] for i, r in rows.items()}, ch["old_parents"]
    for key, cites in [(t["n"], t["spec_refs"]) for t in tasks(root)] + [(k["id"], k["cites"]) for k in tickets(root)]:
        hit = [i for i in ch["edited"] | ch["added"] if any(under(i, a, parents) for a in cites)]
        hit += [i for i in ch["removed"] if any(under(i, a, old) for a in cites)]
        if hit: marks[key] = sorted(hit)
    return marks

def new_sections(root: Path, rows: dict) -> list[str]:
    """Sections with text that the spec gained since the tickets were written, in no task and not deferred."""
    ch, parents = changes(root, rows), {i: r["parent"] for i, r in rows.items()}
    held = [i for t in tasks(root) for i in t["spec_refs"]] + [d["id"] for d in deferred(root)]
    return [i for i in units(rows) if i in ch["added"] and not any(under(i, a, parents) for a in held)]


# The reports: the spec's shape, the coverage, and the board.

def check_spec(root: Path, spec: str) -> int:
    """--check-spec: the fixed checks on the spec, the ones that are the same every run. Whether the spec says
    enough to build from is judged by /skift:spec, not here."""
    files = spec_files(root, spec)
    text = COMMENT_RE.sub("", "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in files)).strip()
    out = []
    said = [line.strip() for line in text.splitlines()
            if line.strip() and not line.strip().startswith("#") and not re.fullmatch(r"[-*]?\s*<[^>]*>", line.strip())]
    if not said:
        print(f"[skift] spec check: {spec} says nothing to build from: it needs a grill")
        return 1
    bodies = {p: COMMENT_RE.sub("", p.read_text(encoding="utf-8", errors="replace")) for p in files}
    shaped = [p for p, b in bodies.items() if re.search(r"^##\s+Parts in build order\s*$", b, re.M | re.I)]
    for p in shaped:  # skift's own shape: the grill writes it, so it must hold up
        rel = os.path.relpath(p, root)
        for head in SPEC_HEADS:
            if not part_of(bodies[p], head): out.append(f"{rel}: ## {head} is missing or empty")
        parts = re.split(r"^###\s+(.+?)\s*$", part_of(bodies[p], "Parts in build order"), flags=re.M)[1:]
        if not parts: out.append(f"{rel}: Parts in build order holds no part: each is `### <what must work>`")
        for name, body in zip(parts[::2], parts[1::2]):
            if not re.search(r"^\s*Done:\s*$", body, re.M) or not re.search(r"^\s*-\s+\S", body, re.M):
                out.append(f"{rel}: part {name}: no `Done:` line with at least one check under it")
    for p, body in bodies.items():
        rel = os.path.relpath(p, root)
        for n, line in enumerate(body.splitlines(), 1):
            low = line.lower()
            for word in VAGUE:
                if re.search(rf"(?<![\w-]){re.escape(word)}(?:ly|er|est|ness)?(?![\w-])", low):
                    out.append(f"{rel}:{n}: \"{word}\" says nothing checkable: give what a person does and sees")
            if SECRET_RE.search(line): out.append(f"{rel}:{n}: this looks like a secret: put it in .env and name the key here")
    for line in out: print(f"[skift] {line}")
    shape = "in skift's shape" if shaped else "in its own shape, as it was brought"
    print(f"[skift] spec check: {plural(len(out), 'problem')} in {spec}" if out else
          f"[skift] spec check: no fixed check failed; {spec} is {shape}. Whether it says enough is the trial run's call")
    return 1 if out else 0

def check(root: Path, record_it: bool, spec: str | None = None) -> int:
    """--coverage, and with --record the same checks before each section's hash goes into kanban/source.json."""
    spec = spec or (spec_path(root) if (root / SOURCE).is_file() or (root / INDEX).is_file() else None)
    rows = index(root, spec) if spec else {}
    if spec: write_index(root, spec, rows)
    problems = coverage(root)
    for p in problems: print(f"[skift] {p}")
    print(f"[skift] coverage: {plural(len(problems), 'problem')} over {plural(len(units(rows)), 'section')}, "
          f"{plural(len(tasks(root)), 'task')}, {plural(len(tickets(root)), 'ticket')}")
    if problems: return 1
    if record_it:
        if spec: record(root, spec, rows)
        ensure_progress(root)
        return status(root)
    return 0

def status(root: Path) -> int:
    """--status: every task in build order with its tickets and their status, what the spec changed under, and
    the tasks with no tickets yet."""
    for old in LEGACY:
        if (root / old).exists(): print(f"[skift] {old} is from skift before 1.0: rerun /skift:spec, then /skift:tasks")
    spec, rows = spec_rows(root)
    ts, tk = tasks(root), tickets(root)
    marks = drift(root, rows) if rows and (root / SOURCE).is_file() else {}
    done = sum(k["status"] == "done" for k in tk)
    print(f"[skift] {plural(len(ts), 'task')} · {plural(len(tk), 'ticket')} · {done} done · "
          f"{sum(k['status'] == 'in_review' for k in tk)} in review · spec: {spec or 'none'}")
    for t in ts:
        mine = [k for k in tk if k["parent"] == t["n"]]
        waits = f" · after {', '.join(str(n) for n in t['after'])}" if t["after"] else ""
        mark = "  (spec changed)" if t["n"] in marks else ""
        print(f"[skift] task {t['n']} {t['title']}{waits}{mark}")
        if not mine:
            print(f"[skift]   no tickets yet: /skift:kanban {t['n']}")
        for k in mine:
            human = sum(a["tag"] == "human" for a in k["acs"])
            print(f"[skift]   [{k['status']}] {k['id']}  {k['title']}  ({plural(len(k['acs']), 'AC')}"
                  f"{f', {human} for you' if human else ''}){'  (spec changed)' if k['id'] in marks else ''}")
    if df := deferred(root): print(f"[skift] deferred: {plural(len(df), 'section')} no task covers")
    for i in (new_sections(root, rows) if rows and (root / SOURCE).is_file() else []):
        print(f"[skift] new in the spec, in no task: {i} ({rows[i]['title']})")
    if marks: print(f"[skift] the spec changed: rerun /skift:spec, then /skift:kanban for each task marked above")
    return 0

def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--project-dir", default=".", help="the project repo (default: cwd)")
    p.add_argument("--status", action="store_true", help="the board: every task, its tickets and their status")
    p.add_argument("--index", metavar="SPEC", help="for /skift:spec: index the spec (a .md file or a folder) into kanban/index.md")
    p.add_argument("--show", metavar="ID", nargs="+", help="for /skift:spec: print these sections of the spec, with line numbers")
    p.add_argument("--grep", metavar="REGEX", help="for /skift:spec: the sections whose heading or text matches")
    p.add_argument("--check-spec", metavar="SPEC", help="for /skift:spec: the fixed checks on the spec's shape and wording")
    p.add_argument("--coverage", action="store_true", help="for /skift:tasks and /skift:kanban: check the tasks and tickets against the spec")
    p.add_argument("--record", action="store_true", help="for /skift:kanban: --coverage, then record each section's hash and print the board")
    a = p.parse_args()
    root = Path(a.project_dir).resolve()
    reports = {"index": lambda: build_index(root, a.index), "show": lambda: show(root, a.show), "grep": lambda: grep(root, a.grep),
               "check_spec": lambda: check_spec(root, a.check_spec), "record": lambda: check(root, True),
               "coverage": lambda: check(root, False), "status": lambda: status(root)}
    if not (chosen := [k for k in reports if getattr(a, k)]):
        p.print_usage()
        return 2
    try:
        return reports[chosen[0]]()
    except BrokenPipeError:  # piped into head: fine
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        return 0
    except (OSError, ValueError, re.error) as e:
        print(f"[skift] {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
