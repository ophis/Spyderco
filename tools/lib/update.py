"""spy.py update/accept/take/wiki-error/alias/skip/manual/add-row/init: wiki records vs Catalogs/<file>.md."""

import hashlib
import json
import re

from lib import catalog, classify, paths, wiki
from lib.catalog import CatalogError, Row
from lib.fsio import atomic_write, dump_json

DIFF_FIELDS = ("released", "steel", "handle", "type", "qty")
ROW_FIELDS = ("sku", "section", *DIFF_FIELDS, "alt")


class StaleProposal(Exception):
    pass


def _sha1(cat):
    return hashlib.sha1(cat.path.read_bytes()).hexdigest()


def _proposal_path(id_):
    return paths.CACHE / "proposals" / f"{id_}.json"


def sku_token(sku):
    parts = sku.split()
    return parts[0] if parts else sku


def alt_tokens(alt):
    return {t for t in re.split(r"[\s,()]+", alt) if t and t != "wiki"}


def record_keys(records):
    return [k.removeprefix("wiki|") for k in wiki.source_keys(records)]


def _expected_alt(raw_sku, sku):
    return f"{raw_sku} (wiki)" if sku != raw_sku else ""


def _canonical(cat, key, token):
    aliases = cat.config.get("aliases", {})
    return aliases.get(key, aliases.get(token, token))


def wiki_row(cat, record, key):
    row = classify.classify_record({"section_rules": cat.config.get("section_rules", []), "sections": cat.sections}, record)
    row["sku"] = _canonical(cat, key, row["sku"])
    row["alt"] = _expected_alt(record["sku"], row["sku"])
    return row


def match(cat, records, keys):
    skip = set(cat.config.get("skip", []))
    live = [(k, r) for k, r in zip(keys, records) if k not in skip and sku_token(r["sku"]) not in skip]
    cands = {}
    for k, r in live:
        token = sku_token(r["sku"])
        canon = _canonical(cat, k, token)
        cands[k] = [i for i, row in enumerate(cat.rows) if row.sku == canon or token in alt_tokens(row.alt)]
    tiers = (
        lambda row, r: row.released == classify.first_date(r["from_to"]),
        lambda row, r: classify.start_year(row.released) == classify.start_year(r["from_to"]),
        lambda row, r: True,
    )
    used, paired = set(), {}
    for fits in tiers:
        for k, r in live:
            if k in paired:
                continue
            i = next((i for i in cands[k] if i not in used and fits(cat.rows[i], r)), None)
            if i is not None:
                paired[k] = i
                used.add(i)
    return paired, [k for k, _ in live if k not in paired]


def diff(cat, records, keys):
    by_key = dict(zip(keys, records))
    paired, unpaired = match(cat, records, keys)
    errors = cat.config.get("wiki_errors", {})
    manual = set(cat.config.get("manual", []))
    diffs = []
    for k in (k for k in keys if k in paired):  # wiki order, not pairing-tier order
        row, auto = cat.rows[paired[k]], wiki_row(cat, by_key[k], k)
        known = errors.get(f"{row.sku}|{row.released}", {})
        diffs += [{"sku": row.sku, "released": row.released, "field": f, "md": getattr(row, f), "wiki": auto[f]}
                  for f in DIFF_FIELDS if getattr(row, f) != auto[f] and known.get(f) != auto[f]]
    used = set(paired.values())
    return {"new": [{"key": k, "row": wiki_row(cat, by_key[k], k)} for k in unpaired],
            "diff": diffs,
            "orphan": [r.sku for i, r in enumerate(cat.rows) if i not in used and r.sku not in manual]}


def _prefix_re(id_):
    return re.compile(rf"\b({re.escape(id_)}[A-Z][A-Z0-9]*)\b")


def read_official(id_):
    path = paths.CACHE / "official.json"
    if not path.exists():
        return None
    prefix = _prefix_re(id_)
    return [sku for p in json.loads(path.read_text(encoding="utf-8")) for sku in p.get("skus", []) if prefix.fullmatch(sku)]


def read_forum(id_):
    path = paths.CACHE / "forum.txt"
    if not path.exists():
        return None
    prefix = _prefix_re(id_)
    return [sku for line in path.read_text(encoding="utf-8").splitlines()
            if re.search(r" - ([A-Z]{3} \d{4})$", line.strip()) for sku in prefix.findall(line)]


def cross_check(cat):
    aliases = cat.config.get("aliases", {})
    known = {r.sku for r in cat.rows} | set(aliases) | set(aliases.values()) | set(cat.config.get("skip", []))
    for r in cat.rows:
        known |= alt_tokens(r.alt)
    unmatched, notes = [], []
    for name, reader, file in (("official", read_official, "official.json"), ("forum", read_forum, "forum.txt")):
        skus = reader(cat.id)
        if skus is None:
            notes.append(f"{name} cross-check skipped (no cache/{file})")
            continue
        unmatched += [{"source": name, "sku": s} for s in dict.fromkeys(skus) if s not in known]
    return unmatched, notes


def _wiki_text(cat, offline):
    page = cat.config["wiki_page"]
    path = paths.CACHE / "wiki" / f"{page}.txt"
    if offline:
        if not path.exists():
            raise FileNotFoundError(f"{path} missing; run `spy.py fetch wiki {cat.id}` first")
        return path.read_text(encoding="utf-8")
    text = wiki.fetch(page)
    wiki.parse_tables(text)
    atomic_write(path, text)
    return text


def _summary(id_, p, notes, path):
    lines = [f"NEW {n['key']}  {n['row']['released']}  {n['row']['section']}  {n['row']['handle']}  {n['row']['steel']}"
             for n in p["new"]]
    lines += [f"DIFF {d['sku']} {d['field']}: md={d['md']!r} wiki={d['wiki']!r}" for d in p["diff"]]
    lines += [f"ORPHAN {s}" for s in p["orphan"]]
    lines += [f"UNMATCHED {u['source']} {u['sku']}" for u in p["unmatched"]]
    counts = {k: len(p[k]) for k in ("new", "diff", "orphan", "unmatched")}
    lines.append(f"{id_}: " + (", ".join(f"{n} {k}" for k, n in counts.items()) if any(counts.values())
                               else "nothing to propose"))
    print("\n".join([*lines, *notes, f"proposal: {path}"]))


def run(id_, offline):
    cat = catalog.load(id_)
    records = wiki.parse_tables(_wiki_text(cat, offline))
    proposal = {"md_sha1": _sha1(cat), **diff(cat, records, record_keys(records))}
    proposal["unmatched"], notes = cross_check(cat)
    path = _proposal_path(id_)
    atomic_write(path, dump_json(proposal))
    _summary(id_, proposal, notes, path)
    return path


def _insert(cat, row):
    row.images = next((list(r.images) for r in cat.rows if r.sku == row.sku), [])
    key = classify.date_key(row.released)
    last = None
    for i, other in enumerate(cat.rows):
        if other.section != row.section:
            continue
        if classify.date_key(other.released) > key:
            cat.rows.insert(i, row)
            return
        last = i
    cat.rows.insert(len(cat.rows) if last is None else last + 1, row)


def _load_proposal(cat):
    path = _proposal_path(cat.id)
    if not path.exists():
        raise ValueError(f"no proposal for {cat.id}; run `spy.py update {cat.id}` first")
    proposal = json.loads(path.read_text(encoding="utf-8"))
    if proposal["md_sha1"] != _sha1(cat):
        raise StaleProposal(f"{cat.path.name} changed since `update`; run `spy.py update {cat.id}` again")
    return proposal


def _save(cat, proposal):
    catalog.save(cat)
    proposal["md_sha1"] = _sha1(cat)
    atomic_write(_proposal_path(cat.id), dump_json(proposal))


def accept(id_, keys, all_new=False):
    cat = catalog.load(id_)
    proposal = _load_proposal(cat)
    by_key = {n["key"]: n["row"] for n in proposal["new"]}
    if not keys and not all_new:
        raise ValueError("pass NEW keys or --all-new")
    unknown = [k for k in keys if k not in by_key]
    if unknown:
        raise ValueError(f"not NEW in the proposal for {id_}: {', '.join(unknown)}")
    added, dups = [], []
    for k in list(by_key) if all_new else list(dict.fromkeys(keys)):
        row = Row(**by_key[k])
        if _exists(cat, row.sku, row.released):
            dups.append(k)
        else:
            _insert(cat, row)
            added.append(k)
    if dups and not all_new:
        raise ValueError(f"a row with the same SKU and Released exists for: {', '.join(dups)}; `skip` or `alias` them")
    proposal["new"] = [n for n in proposal["new"] if n["key"] not in added]
    _save(cat, proposal)
    lines = [f"NEW {k}" for k in added] + [f"DUPLICATE {k} (not added; `skip` or `alias` it)" for k in dups]
    print("\n".join(lines) or f"{id_}: nothing accepted")


def _exists(cat, sku, released, other_than=None):
    return any(r is not other_than and r.sku == sku and r.released == released for r in cat.rows)


def _entries(proposal, sku, fields, released):
    entries = [d for d in proposal["diff"] if d["sku"] == sku and d["field"] in fields and released in (None, d["released"])]
    rels = sorted({d["released"] for d in entries})
    if len(rels) > 1:
        raise ValueError(f"{sku} has DIFFs on rows released {rels}; pass --released")
    missing = sorted(set(fields) - {d["field"] for d in entries})
    if missing:
        raise ValueError(f"no proposed DIFF for {sku}: {', '.join(missing)}")
    return entries


def take(id_, sku, fields, released=None):
    cat = catalog.load(id_)
    proposal = _load_proposal(cat)
    entries = _entries(proposal, sku, fields, released)
    old = entries[0]["released"]
    row = next((r for r in cat.rows if r.sku == sku and r.released == old), None)
    if row is None:
        raise ValueError(f"no row {sku} released {old!r}")
    for d in entries:
        setattr(row, d["field"], d["wiki"])
    if row.released != old and _exists(cat, sku, row.released, other_than=row):
        raise ValueError(f"another {sku} row is already released {row.released!r}")
    errors = cat.config.get("wiki_errors", {})
    if row.released != old and f"{sku}|{old}" in errors:
        errors[f"{sku}|{row.released}"] = errors.pop(f"{sku}|{old}")
    proposal["diff"] = [d for d in proposal["diff"] if d not in entries]
    for d in proposal["diff"]:
        if d["sku"] == sku and d["released"] == old:
            d["released"] = row.released
    _save(cat, proposal)


def wiki_error(id_, sku, fields, released=None):
    cat = catalog.load(id_)
    proposal = _load_proposal(cat)
    entries = _entries(proposal, sku, fields, released)
    errors = cat.config.setdefault("wiki_errors", {})
    for d in entries:
        errors.setdefault(f"{d['sku']}|{d['released']}", {})[d["field"]] = d["wiki"]
    proposal["diff"] = [d for d in proposal["diff"] if d not in entries]
    _save(cat, proposal)


def add_alias(id_, frm, to):
    cat = catalog.load(id_)
    cat.config["aliases"] = dict(sorted({**cat.config.get("aliases", {}), frm: to}.items()))
    catalog.save(cat)


def _append(cat, key, value):
    values = cat.config.setdefault(key, [])
    if value not in values:
        values.append(value)


def add_skip(id_, value):
    cat = catalog.load(id_)
    _append(cat, "skip", value)
    catalog.save(cat)


def add_manual(id_, sku):
    cat = catalog.load(id_)
    if sku not in {r.sku for r in cat.rows}:
        raise ValueError(f"{sku} is not a row of {id_}")
    _append(cat, "manual", sku)
    catalog.save(cat)


def add_row(id_, fields):
    cat = catalog.load(id_)
    if not fields.get("sku") or not fields.get("section"):
        raise ValueError("add-row requires sku and section")
    if fields["section"] not in cat.sections:
        raise ValueError(f"unknown section {fields['section']!r}; sections: {cat.sections}")
    row = Row(**{f: fields.get(f) or "" for f in ROW_FIELDS})
    row.type = row.type or "Regular production"
    if _exists(cat, row.sku, row.released):
        raise ValueError(f"{row.sku} released {row.released!r} already exists")
    _insert(cat, row)
    _append(cat, "manual", row.sku)
    catalog.save(cat)


def init_catalog(id_, file, title, wiki_page, sections, rules, readme_label=None):
    path = paths.CATALOGS / f"{file}.md"
    if path.exists():
        raise ValueError(f"{path} already exists")
    if id_ in catalog.all_ids():
        raise ValueError(f"id {id_} is already used")
    section_rules = []
    for rule in rules:
        parts = rule.split(":", 2)
        if len(parts) != 3:
            raise ValueError(f"bad rule {rule!r}; expected section:field:regex")
        section_rules.append(dict(zip(("section", "field", "regex"), parts)))
    config = {"id": id_, "wiki_page": wiki_page, "readme_label": readme_label or file, "section_rules": section_rules,
              "aliases": {}, "skip": [], "manual": [], "wiki_errors": {}}
    preamble = catalog.HEADER_TEMPLATE.format(wiki_label=wiki_page.replace("_", " "), wiki_page=wiki_page).split("\n")
    cat = catalog.Catalog(path, title, [*preamble, ""], list(sections), [], config)
    problems = catalog.config_problems(cat)
    if problems:
        raise ValueError("; ".join(problems))
    catalog.save(cat)
    return path


def _cmd(fn):
    def handler(args):
        try:
            fn(args)
        except (StaleProposal, ValueError, FileNotFoundError, RuntimeError, CatalogError) as exc:
            print(f"error: {exc}")
            return 1
        return 0
    return handler


def register(subparsers):
    p = subparsers.add_parser("update", help="list NEW/DIFF/ORPHAN/UNMATCHED against the wiki (never edits the catalog)")
    p.add_argument("id")
    p.add_argument("--offline", action="store_true", help="use cache/wiki/ instead of fetching")
    p.set_defaults(func=_cmd(lambda a: run(a.id, a.offline)))

    p = subparsers.add_parser("accept", help="insert proposed NEW rows by release date")
    p.add_argument("id")
    p.add_argument("keys", nargs="*", help="NEW record keys (<raw SKU>|<year>[#n])")
    p.add_argument("--all-new", action="store_true")
    p.set_defaults(func=_cmd(lambda a: accept(a.id, a.keys, a.all_new)))

    for name, fn, text in (("take", take, "copy the proposed wiki value(s) of a DIFF into the row"),
                           ("wiki-error", wiki_error, "record the proposed wiki value(s) as a known wiki error")):
        p = subparsers.add_parser(name, help=text)
        p.add_argument("id")
        p.add_argument("sku")
        p.add_argument("fields", nargs="+", choices=DIFF_FIELDS)
        p.add_argument("--released", help="the row's Released value, when the SKU has several rows")
        p.set_defaults(func=_cmd(lambda a, fn=fn: fn(a.id, a.sku, a.fields, a.released)))

    p = subparsers.add_parser("alias", help="map a wiki/official/forum spelling or one record key to a catalog SKU")
    p.add_argument("id")
    p.add_argument("frm")
    p.add_argument("to")
    p.set_defaults(func=_cmd(lambda a: add_alias(a.id, a.frm, a.to)))

    p = subparsers.add_parser("skip", help="never propose a wiki record key / report a SKU")
    p.add_argument("id")
    p.add_argument("value", help="<raw SKU>|<year>[#n] or SKU")
    p.set_defaults(func=_cmd(lambda a: add_skip(a.id, a.value)))

    p = subparsers.add_parser("manual", help="mark an existing row as intentionally not on the wiki")
    p.add_argument("id")
    p.add_argument("sku")
    p.set_defaults(func=_cmd(lambda a: add_manual(a.id, a.sku)))

    p = subparsers.add_parser("add-row", help="add a row by hand (also marks its SKU manual)")
    p.add_argument("id")
    p.add_argument("--sku", required=True)
    p.add_argument("--section", required=True)
    for f in ("released", "steel", "handle", "type", "qty", "alt"):
        p.add_argument(f"--{f}", default="")
    p.set_defaults(func=_cmd(lambda a: add_row(a.id, {f: getattr(a, f) for f in ROW_FIELDS})))

    p = subparsers.add_parser("init", help="write a new Catalogs/<file>.md with config and empty sections")
    p.add_argument("id")
    p.add_argument("--file", required=True, help='catalog file name, e.g. "C41 Native 5"')
    p.add_argument("--title", required=True)
    p.add_argument("--wiki-page", required=True)
    p.add_argument("--sections", nargs="+", required=True)
    p.add_argument("--rule", action="append", default=[], help="section:field:regex (field: sku|handle|wiki_table)")
    p.add_argument("--readme-label", help="README model column (default: --file)")
    p.set_defaults(func=_cmd(lambda a: print(init_catalog(a.id, a.file, a.title, a.wiki_page, a.sections, a.rule,
                                                         a.readme_label))))
