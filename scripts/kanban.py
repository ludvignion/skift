#!/usr/bin/env python3
"""skift kanban. /skift:spec turns a spec of any size into kanban/map.md (every slice in build order, with
the spec sections it covers) and kanban/features/NN-<slice>.json (the features of the slices detailed so
far, each citing its sections); this script indexes the spec, shows its sections, checks that the map and
the features drop nothing, records each section's hash, and prints the board: every feature under its
slice, passing or open, and the features a spec edit changed under. It builds nothing: you tell Claude
what to build, in your own session."""
import argparse, hashlib, json, os, re, sys, unicodedata  # noqa: E401
from pathlib import Path

SMALL_SPEC_CHARS = 60000  # up to this, the spec is read whole and every slice is detailed at once
CHUNK_LINES = 80  # own text longer than this is cited in parts, <id>~1, <id>~2, ...

FEATURES, MAP, INDEX, SOURCE = "kanban/features", "kanban/map.md", "kanban/index.md", "kanban/source.json"
PROGRESS, LEGACY = "progress.md", "features.json"  # LEGACY: the feature file before 0.4
SECTIONS = ("Current", "Log", "Decided", "Deviations", "Gaps", "Findings")  # of progress.md
FILE_RE, NOTE_RE = re.compile(r"^(\d+)-[a-z0-9]+(?:-[a-z0-9]+)*$"), re.compile(r"\bfeature #?(\d+)\b", re.I)
HEADING_RE, FENCE_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$"), re.compile(r"^\s*(```|~~~)")
EXPLICIT_ID = re.compile(r"\b(?:REQ|FR|NFR|US|UC|BR)-\d{1,6}\b")  # requirement ids a heading may carry
TRANSLIT = str.maketrans({"ø": "o", "Ø": "O", "æ": "ae", "Æ": "AE", "ß": "ss", "ł": "l", "Ł": "L", "đ": "d", "Đ": "D", "ð": "d", "þ": "th"})
SLICE_LINE_RE, SRC_RE = re.compile(r"^- (\d+-[a-z0-9]+(?:-[a-z0-9]+)*):\s*(.*?)\s*\[src:"), re.compile(r"\[src:\s*([^\]]*)\]\s*$")


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
    """The items under `## <name>` in progress.md, one per bullet, its wrapped lines joined."""
    out, on = [], False
    for line in (root / PROGRESS).read_text(encoding="utf-8").splitlines() if (root / PROGRESS).is_file() else []:
        if re.match(r"#{1,2}\s", line): on = line.strip().lower() == f"## {name.lower()}"
        elif on and line.strip():
            if out and not re.match(r"\s*[-*]\s", line): out[-1] += " " + line.strip()
            else: out.append(line.strip())
    return out

def notes(root: Path, name: str) -> dict[int, list[str]]:
    """The items under `## <name>` in progress.md by the feature they start with (`- feature N:`), else by every
    feature they name, without that prefix."""
    out: dict[int, list[str]] = {}
    for line in section(root, name):
        lead = re.match(r"^-\s*(\d{4}-\d{2}-\d{2}\s+)?feature #?(\d+)\s*:\s*", line, re.I)
        text = line[lead.end():] if lead else line
        for i in [lead[2]] if lead else NOTE_RE.findall(line): out.setdefault(int(i), []).append(text)
    return out

def ensure_progress(root: Path) -> None:
    """progress.md with every section, added at the end where one is missing."""
    path = root / PROGRESS
    text = path.read_text(encoding="utf-8") if path.is_file() else "# Progress\n"
    have = {m.lower() for m in re.findall(r"^## +(.+?)\s*$", text, re.M)}
    missing = [f"## {s}\n" for s in SECTIONS if s.lower() not in have]
    if missing: path.write_text(text.rstrip("\n") + "\n\n" + "\n".join(missing), encoding="utf-8")

def state(root: Path) -> dict:
    """What --status looks at: the spec, its sections, the map, the features, which slices are detailed, what
    changed in the spec, which features that touches, and new sections in no slice."""
    if (root / LEGACY).is_file(): raise ValueError(f"{LEGACY} is from skift before 0.4: rerun /skift:spec <your spec>")
    if not (root / SOURCE).is_file(): raise ValueError(f"{SOURCE} is missing: run /skift:spec <your spec>")
    spec = spec_path(root)
    if (mp := read_map(root)) is None: raise ValueError(f"{MAP} is missing: rerun /skift:spec {spec}")
    rows, feats = index(root, spec), load(root)
    ch = changes(root, rows)
    return {"spec": spec, "rows": rows, "map": mp, "feats": feats, "detailed": {p.stem for p in slices(root)}, "changes": ch,
            "affected": {f["id"]: affected(f, ch, rows) for f in feats}, "new": uncovered_new(rows, mp, ch)}

def plural(n: int, word: str) -> str:
    return f"{n} {word}{'s' * (n != 1)}"

def spec_chars(root: Path, spec: str) -> int:
    return sum(len(p.read_text(encoding="utf-8", errors="replace")) for p in spec_files(root, spec))

def build_index(root: Path, spec: str) -> int:
    """--index: write kanban/index.md, and say whether /skift:spec reads the spec whole or works from the index."""
    rows, files, chars = index(root, spec), spec_files(root, spec), spec_chars(root, spec)
    write_index(root, spec, rows)
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
    feats, gaps, found, dev = st["feats"], notes(root, "Gaps"), notes(root, "Findings"), notes(root, "Deviations")
    print(f"[skift] {sum(f['passes'] for f in feats)}/{len(feats)} features pass · {len(st['detailed'])} of {plural(len(st['map']['slices']), 'slice')} detailed")
    for s in st["map"]["slices"]:
        if s["name"] not in st["detailed"]:
            print(f"[skift] {s['name']}  not detailed yet: {s['what']}")
            continue
        mine = [f for f in feats if f["_slice"] == s["name"]]
        g, fi, dv = (sum(len(n.get(f["id"], [])) for f in mine) for n in (gaps, found, dev))
        print(f"[skift] {s['name']}  {sum(f['passes'] for f in mine)}/{len(mine)} passing · {plural(g, 'gap')} · "
              f"{plural(fi, 'finding')} · {plural(dv, 'deviation')}")
        for f in mine:
            marks = ("  (gap)" if f["id"] in gaps else "") + (("  (spec changed since it passed)" if f["passes"] else "  (spec changed)") if st["affected"][f["id"]] else "")
            print(f"[skift]   [{'x' if f['passes'] else ' '}] {f['id']}  {f['description']}{marks}")
    for i in st["new"]: print(f"[skift] new in the spec, in no slice: {i} ({st['rows'][i]['title']})")
    if st["new"] or any(st["affected"].values()):
        print(f"[skift] the spec changed: /skift:spec {st['spec']} updates the features first; build none marked (spec changed) before it")
    return 0

def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--project-dir", default=".", help="the project repo (default: cwd)")
    p.add_argument("--status", action="store_true", help="per slice: passing/total, gaps, findings and each feature; spec changes")
    p.add_argument("--index", metavar="SPEC", help="for /skift:spec: index the spec (a .md file or a folder) into kanban/index.md")
    p.add_argument("--show", metavar="ID", nargs="+", help="for /skift:spec: print these sections of the spec, with line numbers")
    p.add_argument("--grep", metavar="REGEX", help="for /skift:spec: the sections whose heading or text matches")
    p.add_argument("--mark-spec", metavar="SPEC", help="for /skift:spec: check the map and the features against the spec, and record it")
    a = p.parse_args()
    root = Path(a.project_dir).resolve()
    reports = {"index": lambda: build_index(root, a.index), "show": lambda: show(root, a.show), "grep": lambda: grep(root, a.grep),
               "mark_spec": lambda: mark(root, a.mark_spec), "status": lambda: status(root)}
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
