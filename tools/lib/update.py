"""Update workflow: propose NEW/CHANGED/GONE/RELINK from sources, then apply decisions."""

import hashlib
import json
import re

from lib import classify, data, paths, wiki
from lib.fsio import atomic_write, dump_json

ROW_FIELDS = ("sku", "section", "released", "steel", "handle", "type", "qty")
RULE_FIELDS = ("handle", "sku", "wiki_table")


class StaleProposal(Exception):
    pass


def _family_sha1(id_):
    return hashlib.sha1((paths.FAMILIES / f"{id_}.json").read_bytes()).hexdigest()


def _proposal_path(id_):
    return paths.CACHE / "proposals" / f"{id_}.json"


def classify_record(fam, record, key):
    full = {k: record.get(k, "") for k in ("table", "sku", "handle", "steel", "from_to", "note", "number_made")}
    auto = classify.classify_record(fam, full)
    if not key.startswith("wiki|"):
        auto["sku"] = fam.get("aliases", {}).get(auto["sku"], auto["sku"])
    return auto


def _expected_alt(raw_sku, sku):
    return f"{raw_sku} (wiki)" if sku != raw_sku else ""


def _base(src):
    return src.split("#")[0]


def _names(fam, row):
    return _sku_names(fam, row["sku"], row["src_raw"]["sku"], row["auto"]["sku"])


def _sku_names(fam, *skus):
    names = set(skus)
    aliases = fam.get("aliases", {})
    names |= {k for k, v in aliases.items() if v in names}
    names |= {aliases[n] for n in list(names) if n in aliases}
    return names


def _order_changed(fresh_raws, known_raws):
    for i, raw in enumerate(fresh_raws):
        if raw != known_raws[i] and any(raw == k for j, k in enumerate(known_raws) if j != i):
            return True
    return False


def diff(fam, records, keys):
    fresh = {k: wiki.raw_of(r) for k, r in zip(keys, records)}
    rows = {r["src"]: r for r in fam["rows"] if r["src"].startswith("wiki|") and "src_raw" in r}
    ignore = set(fam.get("ignore", []))

    relink = []
    grouped = set()
    for base in dict.fromkeys(_base(k) for k in [*fresh, *rows]):
        fresh_g = [k for k in fresh if _base(k) == base]
        known_g = [s for s in [*rows, *ignore] if s.startswith("wiki|") and _base(s) == base]
        known_g.sort(key=lambda s: int(s.split("#")[1]) if "#" in s else 1)
        if not fresh_g or not any(s in rows for s in known_g):
            continue
        if len(fresh_g) != len(known_g):
            regroup = True
        elif len(fresh_g) > 1:
            known_raws = [rows[s]["src_raw"] if s in rows else None for s in known_g]
            regroup = _order_changed([fresh[k] for k in fresh_g], known_raws)
        else:
            regroup = False
        if regroup:
            relink += [{"old": s, "new": fresh_g} for s in known_g if s in rows]
            grouped |= {*fresh_g, *known_g}

    new = [k for k in fresh if k not in rows and k not in ignore and k not in grouped]
    changed = []
    for k in fresh:
        if k in rows and k not in grouped and fresh[k] != rows[k]["src_raw"]:
            old = rows[k]["src_raw"]
            changed.append({"src": k, "diff": {f: [old.get(f), v] for f, v in fresh[k].items() if old.get(f) != v}})
    gone = []
    for src, row in rows.items():
        if src in fresh or src in grouped:
            continue
        names = _names(fam, row)
        cands = [k for k in new if fresh[k]["sku"] in names or k.split("|")[1] in names]
        if cands:
            relink.append({"old": src, "new": cands})
            new = [k for k in new if k not in cands]
        else:
            gone.append(src)
    for row in fam["rows"]:
        if row["src"].startswith("wiki|"):
            continue
        names = _sku_names(fam, row["sku"])
        cands = [k for k in new if fresh[k]["sku"] in names or k.split("|")[1] in names]
        if cands:
            relink.append({"old": row["src"], "new": cands})
            new = [k for k in new if k not in cands]
    listed = {*new, *(c["src"] for c in changed), *(k for r in relink for k in r["new"])}
    return {"new": new, "changed": changed, "gone": gone, "relink": relink,
            "unmatched": [], "raw": {k: v for k, v in fresh.items() if k in listed}}


def _known_skus(fam):
    aliases = fam.get("aliases", {})
    return {r["sku"] for r in fam["rows"]} | set(aliases) | set(aliases.values())


def _prefix_re(fam):
    return re.compile(rf"\b({re.escape(fam['id'])}[A-Z][A-Z0-9]*)\b")


def read_official(fam):
    path = paths.CACHE / "official.json"
    if not path.exists():
        return None
    prefix = _prefix_re(fam)
    found = []
    for product in json.loads(path.read_text(encoding="utf-8")):
        for sku in product.get("skus", []):
            if prefix.fullmatch(sku):
                found.append({"src": f"official|{sku}", "sku": sku, "title": product.get("title", "")})
    return found


def read_forum(fam):
    path = paths.CACHE / "forum.txt"
    if not path.exists():
        return None
    prefix = _prefix_re(fam)
    found = []
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.search(r" - ([A-Z]{3} \d{4})$", line.strip())
        if not m:
            continue
        for sku in prefix.findall(line):
            found.append({"src": f"forum|{sku}|{m.group(1)}", "sku": sku, "line": line.strip()})
    return found


def cross_check(fam):
    known = _known_skus(fam)
    ignore = set(fam.get("ignore", []))
    unmatched, notes = [], []
    for name, reader, file in (("official", read_official, "official.json"), ("forum", read_forum, "forum.txt")):
        entries = reader(fam)
        if entries is None:
            notes.append(f"{name} cross-check skipped (no cache/{file})")
            continue
        unmatched += [e for e in entries if e["sku"] not in known and e["src"] not in ignore]
    return unmatched, notes


def _wiki_text(fam, offline):
    path = paths.CACHE / "wiki" / f"{fam['wiki_page']}.txt"
    if offline:
        if not path.exists():
            raise FileNotFoundError(f"{path} missing; run `spy.py fetch wiki {fam['id']}` first")
        return path.read_text(encoding="utf-8")
    text = wiki.fetch(fam["wiki_page"])
    wiki.parse_tables(text)
    atomic_write(path, text)
    return text


def _summary(id_, proposal, notes):
    lines = []
    for src in proposal["new"]:
        raw = proposal["raw"][src]
        lines.append(f"NEW      {src}  {raw['from_to']}  {raw['handle']}  {raw['steel']}")
    for c in proposal["changed"]:
        lines.append(f"CHANGED  {c['src']}  " + "; ".join(f"{f}: {o!r} -> {n!r}" for f, (o, n) in c["diff"].items()))
    lines += [f"GONE     {src}" for src in proposal["gone"]]
    lines += [f"RELINK   {r['old']} -> {', '.join(r['new'])}" for r in proposal["relink"]]
    lines += [f"UNMATCHED {u['src']}" for u in proposal["unmatched"]]
    if not any(proposal[k] for k in ("new", "changed", "gone", "relink")):
        lines.append(f"{id_}: nothing to propose")
    else:
        lines.append(f"{id_}: " + ", ".join(f"{len(proposal[k])} {k}" for k in ("new", "changed", "gone", "relink")))
    lines += notes
    print("\n".join(lines))


def run(id_, offline):
    fam = data.load_family(id_)
    sha = _family_sha1(id_)
    records = wiki.parse_tables(_wiki_text(fam, offline))
    proposal = {"family_sha1": sha, **diff(fam, records, wiki.source_keys(records))}
    proposal["unmatched"], notes = cross_check(fam)
    path = _proposal_path(id_)
    atomic_write(path, dump_json(proposal))
    _summary(id_, proposal, notes)
    print(f"proposal: {path}")
    return path


def _insert_by_date(rows, row):
    key = classify.date_key(row["released"])
    last = None
    for i, other in enumerate(rows):
        if other["section"] != row["section"]:
            continue
        if classify.date_key(other["released"]) > key:
            rows.insert(i, row)
            return
        last = i
    rows.insert(len(rows) if last is None else last + 1, row)


def _new_row(fam, src, raw):
    auto = classify_record(fam, raw, src)
    row = {f: auto[f] for f in ROW_FIELDS}
    row.update(alt=_expected_alt(raw["sku"], auto["sku"]), src=src, src_raw=raw, auto=auto)
    return row


def _apply_changed(fam, row, src, raw):
    old_auto = row["auto"]
    auto_alt = row["alt"] == _expected_alt(row["src_raw"]["sku"], row["sku"])
    new_auto = classify_record(fam, raw, src)
    kept = []
    for f in ROW_FIELDS:
        if row[f] == old_auto[f]:
            row[f] = new_auto[f]
        elif row[f] != new_auto[f]:
            kept.append(f)
    if auto_alt:
        row["alt"] = _expected_alt(raw["sku"], row["sku"])
    row.update(src=src, src_raw=raw, auto=new_auto)
    return kept


def _adopt_non_wiki(fam, row, src, raw):
    row.update(src=src, src_raw=raw, auto=classify_record(fam, raw, src))
    return [f for f in ROW_FIELDS if row[f] != row["auto"][f]]


def _load_proposal(id_):
    path = _proposal_path(id_)
    if not path.exists():
        raise ValueError(f"no proposal for {id_}; run `spy.py update {id_}` first")
    proposal = json.loads(path.read_text(encoding="utf-8"))
    if proposal["family_sha1"] != _family_sha1(id_):
        raise StaleProposal(f"families/{id_}.json changed since `update`; run `spy.py update {id_}` again")
    return proposal


def accept(id_, srcs, all_new=False, changed=False, relink=None):
    proposal = _load_proposal(id_)
    fam = data.load_family(id_)
    pairs = [] if relink is None else [tuple(relink)] if isinstance(relink[0], str) else [tuple(p) for p in relink]
    changed_srcs = {c["src"] for c in proposal["changed"]}
    relink_by_old = {r["old"]: r for r in proposal["relink"]}
    relink_news = {k for r in proposal["relink"] for k in r["new"]}
    paired_news = {new for _, new in pairs}

    take_new, take_changed = [], []
    for src in srcs:
        if src in changed_srcs:
            if not changed:
                raise ValueError(f"{src} is CHANGED; pass --changed to accept it")
            take_changed.append(src)
        elif src in relink_news or src in relink_by_old:
            if src not in paired_news:
                raise ValueError(f"{src} is part of a RELINK; use --relink OLD NEW")
        elif src in proposal["new"]:
            take_new.append(src)
        else:
            raise ValueError(f"{src} is not in the proposal for {id_}")
    if all_new:
        take_new += [s for s in proposal["new"] if s not in take_new]
    if changed and not srcs:
        take_changed = sorted(changed_srcs)
    for old, new in pairs:
        if old not in relink_by_old or new not in relink_by_old[old]["new"]:
            raise ValueError(f"{old} -> {new} is not a proposed RELINK")
    if len({o for o, _ in pairs}) != len(pairs) or len(paired_news) != len(pairs):
        raise ValueError("each RELINK old/new src may appear once")

    by_src = {r["src"]: r for r in fam["rows"]}
    raw = proposal["raw"]
    report = []
    for old, new in pairs:
        row = by_src[old]
        kept = (_apply_changed if "auto" in row else _adopt_non_wiki)(fam, row, new, raw[new])
        report.append(f"RELINK   {old} -> {new}" + (f"  kept: {', '.join(kept)}" if kept else ""))
    for src in take_changed:
        kept = _apply_changed(fam, by_src[src], src, raw[src])
        report.append(f"CHANGED  {src}" + (f"  kept: {', '.join(kept)}" if kept else ""))
    for src in take_new:
        _insert_by_date(fam["rows"], _new_row(fam, src, raw[src]))
        report.append(f"NEW      {src}")
    errors = data.validate_family(fam)
    if errors:
        raise ValueError("; ".join(errors))
    data.save_family(fam)

    relinked = {old for old, _ in pairs}
    remaining_relink = [r for r in proposal["relink"] if r["old"] not in relinked]
    claimed = paired_news | {k for r in remaining_relink for k in r["new"]}
    freed = [k for r in proposal["relink"] if r["old"] in relinked for k in r["new"] if k not in claimed]
    proposal.update(
        family_sha1=_family_sha1(id_),
        new=[s for s in proposal["new"] if s not in take_new] + list(dict.fromkeys(freed)),
        changed=[c for c in proposal["changed"] if c["src"] not in take_changed],
        relink=remaining_relink,
    )
    atomic_write(_proposal_path(id_), dump_json(proposal))
    print("\n".join(report) if report else f"{id_}: nothing accepted")


def add_alias(id_, frm, to):
    fam = data.load_family(id_)
    aliases = {**fam.get("aliases", {}), frm: to}
    fam["aliases"] = dict(sorted(aliases.items()))
    data.save_family(fam)


def add_ignore(id_, src):
    fam = data.load_family(id_)
    ignore = fam.setdefault("ignore", [])
    if src not in ignore:
        ignore.append(src)
    data.save_family(fam)


def add_row(id_, fields):
    fam = data.load_family(id_)
    if not fields.get("sku") or not fields.get("section"):
        raise ValueError("add-row requires sku and section")
    if fields["section"] not in fam["sections"]:
        raise ValueError(f"unknown section {fields['section']!r}; sections: {fam['sections']}")
    row = {f: fields.get(f) or "" for f in (*ROW_FIELDS, "alt")}
    row["type"] = row["type"] or "Regular production"
    row["src"] = f"manual|{row['sku']}"
    if any(r["src"] == row["src"] for r in fam["rows"]):
        raise ValueError(f"{row['src']} already exists")
    _insert_by_date(fam["rows"], row)
    data.save_family(fam)


def init_family(id_, file, title, wiki_page, sections, rules):
    path = paths.FAMILIES / f"{id_}.json"
    if path.exists():
        raise ValueError(f"{path} already exists")
    section_rules = []
    for rule in rules:
        section, field, regex = rule if isinstance(rule, (list, tuple)) else rule.split(":", 2)
        if section not in sections or field not in RULE_FIELDS:
            raise ValueError(f"bad rule {rule!r}: section must be one of {sections}, field one of {RULE_FIELDS}")
        section_rules.append({"section": section, "field": field, "regex": regex})
    fam = {"id": id_, "file": file, "title": title, "wiki_page": wiki_page, "readme_label": file,
           "trailing_newline": True, "sections": list(sections), "section_rules": section_rules,
           "aliases": {}, "ignore": [], "rows": []}
    paths.FAMILIES.mkdir(parents=True, exist_ok=True)
    data.save_family(fam)
    order_path = paths.FAMILIES / "_order.json"
    if order_path.exists():
        order = json.loads(order_path.read_text(encoding="utf-8"))
        if id_ not in order:
            order.append(id_)
            atomic_write(order_path, dump_json(order))
    return path


def _cmd(fn):
    def handler(args):
        try:
            fn(args)
        except (StaleProposal, ValueError, FileNotFoundError, RuntimeError, data.FamilyError) as exc:
            print(f"error: {exc}")
            return 1
        return 0
    return handler


def register(subparsers):
    p = subparsers.add_parser("update", help="propose NEW/CHANGED/GONE/RELINK rows from the wiki")
    p.add_argument("id")
    p.add_argument("--offline", action="store_true", help="use cache/wiki/ instead of fetching")
    p.set_defaults(func=_cmd(lambda a: run(a.id, a.offline)))

    p = subparsers.add_parser("accept", help="apply decisions from the last `update` proposal")
    p.add_argument("id")
    p.add_argument("srcs", nargs="*")
    p.add_argument("--all-new", action="store_true", help="accept every NEW record (never RELINK ones)")
    p.add_argument("--changed", action="store_true", help="allow CHANGED srcs (all CHANGED when no src is listed)")
    p.add_argument("--relink", nargs=2, action="append", metavar=("OLD", "NEW"), help="move a row to a new src")
    p.set_defaults(func=_cmd(lambda a: accept(a.id, a.srcs, a.all_new, a.changed, a.relink)))

    p = subparsers.add_parser("alias", help="map a non-wiki SKU spelling to the canonical SKU")
    p.add_argument("id")
    p.add_argument("frm")
    p.add_argument("to")
    p.set_defaults(func=_cmd(lambda a: add_alias(a.id, a.frm, a.to)))

    p = subparsers.add_parser("ignore", help="exclude a src key from future proposals")
    p.add_argument("id")
    p.add_argument("src")
    p.set_defaults(func=_cmd(lambda a: add_ignore(a.id, a.src)))

    p = subparsers.add_parser("add-row", help="add a manual row (src=manual|SKU)")
    p.add_argument("id")
    p.add_argument("--sku", required=True)
    p.add_argument("--section", required=True)
    for field in ("released", "steel", "handle", "type", "qty", "alt"):
        p.add_argument(f"--{field}", default="")
    p.set_defaults(func=_cmd(lambda a: add_row(a.id, {f: getattr(a, f) for f in (*ROW_FIELDS, "alt")})))

    p = subparsers.add_parser("init", help="create a new family file with no rows")
    p.add_argument("id")
    p.add_argument("--file", required=True, help='catalog file name, e.g. "C41 Native 5"')
    p.add_argument("--title", required=True)
    p.add_argument("--wiki-page", required=True)
    p.add_argument("--sections", nargs="+", required=True)
    p.add_argument("--rule", action="append", default=[], help="section:field:regex (field: handle|sku|wiki_table)")
    p.set_defaults(func=_cmd(lambda a: print(init_family(a.id, a.file, a.title, a.wiki_page, a.sections, a.rule))))
