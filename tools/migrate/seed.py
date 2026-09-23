"""One-time migration: build families/*.json and data/images.json from the current catalogs."""

import json
import re
import shutil
from pathlib import Path

from lib import classify, data, paths, wiki

LW = "FRN|FRCP"

FAMILIES = [
    dict(id="C81", file="C81 Para-Military", snapshot="wt_pm.txt", wiki_page="C81_Para-Military",
         title="C81 Para-Military — Para-Military, ParaMilitary 2 & ParaMilitary 2 Lightweight",
         readme_label="C81 Para-Military / ParaMilitary 2 / PM2 Lightweight",
         sections=["Para-Military", "ParaMilitary 2", "ParaMilitary 2 Lightweight"],
         section_rules=[{"section": "ParaMilitary 2 Lightweight", "field": "handle", "regex": LW},
                        {"section": "Para-Military", "field": "wiki_table", "regex": "^Variations of the Paramilitary$"},
                        {"section": "ParaMilitary 2", "field": "wiki_table", "regex": "^Variations of the Paramilitary 2$"}]),
    dict(id="C223", file="C223 Para 3", snapshot="wt_para3.txt", wiki_page="C223_Para_3",
         title="C223 Para 3 — Para 3 & Para 3 Lightweight",
         readme_label="C223 Para 3 / Para 3 Lightweight",
         sections=["Para 3", "Para 3 Lightweight"],
         section_rules=[{"section": "Para 3 Lightweight", "field": "handle", "regex": LW}]),
    dict(id="C101", file="C101 Manix 2", snapshot="wt_mx.txt", wiki_page="C101_Manix",
         title="C101 Manix 2 — Manix 2 & Manix 2 Lightweight",
         readme_label="C101 Manix 2 / Manix 2 Lightweight",
         sections=["Manix 2", "Manix 2 Lightweight"],
         section_rules=[{"section": "Manix 2 Lightweight", "field": "handle", "regex": "FRCP|FRN|Moonglow"}]),
    dict(id="C229", file="C229 Shaman", snapshot="wt_sh.txt", wiki_page="C229_Shaman",
         title="C229 Shaman — Shaman & Shaman Lightweight",
         readme_label="C229 Shaman / Shaman Lightweight",
         sections=["Shaman", "Shaman Lightweight"],
         section_rules=[{"section": "Shaman Lightweight", "field": "handle", "regex": LW}]),
    dict(id="C36", file="C36 Military", snapshot="wt_mil.txt", wiki_page="C36_Military",
         title="C36 Military — Military & Military 2",
         readme_label="C36 Military / Military 2",
         sections=["Military", "Military 2"],
         section_rules=[{"section": "Military 2", "field": "wiki_table", "regex": "^Variations of the Military 2$"}]),
    dict(id="C85", file="C85 Yojimbo", snapshot="wt_yo.txt", wiki_page="C85_Yojimbo",
         title="C85 Yojimbo — Yojimbo & Yojimbo 2",
         readme_label="C85 Yojimbo / Yojimbo 2",
         sections=["Yojimbo", "Yojimbo 2"],
         section_rules=[{"section": "Yojimbo 2", "field": "sku", "regex": "2$"}]),
    dict(id="C240", file="C240 Smock", snapshot="wt_sm.txt", wiki_page="C240_Smock",
         title="C240 Smock",
         readme_label="C240 Smock",
         sections=["Smock"],
         section_rules=[]),
]

# Old SKU corrections, verbatim from the reference final.py / gen2.py.
fix = {'C81FCGR2': 'C81CFGR2', 'C223GPRBK': 'C223GPPRBK', 'C223GNGRBK': 'C223GPNGRBK'}
o2 = {'C81GBK2': 'C81GPBK2', 'C81GCMO2': 'C81GPCMO2', 'C81GCMOBK2': 'C81GPCMOBK2', 'C81MCW2': 'C81MPCW2', 'C81GCBL2': 'C81GPCBL2',
      'C223GCBL': 'C223GPCBL', 'C223MCW': 'C223MPCW', 'C223GMCBK': 'C223GMCBKP', 'C223GBKYLMC': 'C223GBKYLMCP', 'C223YL': 'C223PYL',
      'C223GNDMCPBK': 'C223GNDMCBKP', 'C223GBN15V': 'C223GPBN15V', 'C223BN15V': 'C223PBN15V'}
FIX = {'mx': {'C101GP2OR': 'C101GPOR2', ('C101GPRBK2', '2021'): 'C101GPPRBK2', 'C101MGR2': 'C101PMGR2', 'C101GODFDE2': 'C101GPODFDE2', 'C101GBN15V2': 'C101GPBN15V2', 'C101BN15V2': 'C101PBN15V2',
              'C101JGRBK2': 'C101PJGRBK2', 'C101YL2': 'C101PYL2', 'C101MCW2': 'C101MPCW2', 'C101GMCBK2': 'C101GMCBKP2'},
       'sh': {'C229GFGBK': 'C229GPFGBK', 'C229GORBK': 'C229GPORBK', 'C229GOR': 'C229GPOR', 'C229GODFDE': 'C229GPODFDE', 'C229MM4': 'C229MPM4', 'C229BMBN': 'C229BMBNP',
              'C229GGY': 'C229GPGY', 'C229GBN15V': 'C229GPBN15V', 'C229BK': 'C229PBK', 'C229BBK': 'C229PBBK', 'C229GCBL': 'C229GPCBL', 'C229GRDBK': 'C229GPRDBK'}}
FIXM = {'C36TIF': 'C36TIFP', 'C36G2': 'C36GP2', 'C36GBK2': 'C36GPBK2', 'C36GCMO2': 'C36GPCMO2', 'C36GCMOBK2': 'C36GPCMOBK2', 'C36GDBL2': 'C36GPDBL2', 'C36MCW2': 'C36MPCW2', 'C36CF2': 'C36CFP2', 'C36GCBL2': 'C36GPCBL2', 'C36GBN15V2': 'C36GPBN15V2', 'C36GMCBK2': 'C36GMCBKP2'}
FIXY = {'C85GPCBL': 'C85GPCBL2', 'C85GBN15V2': 'C85GPBN15V2', 'C85GPNBK2': 'C85GPNBKP2', 'C85GPTNBLK2': 'C85GPTNBK2'}
FIXS = {'C240GRD': 'C240GPRD'}


def canonical_sku(fid, record):
    """Old transforms' SKU for a wiki record (final.py, gen2.py)."""
    s = record["sku"].split()[0]
    d, steel = record["from_to"], record["steel"]
    if fid in ("C81", "C223"):
        s = fix.get(s, s)
        if s == 'C81GDGYRX76BKP2' and 'Feb' in d:
            return 'C81GDGYRX76P2'
        if s == 'C81GBKYLMC2':
            return 'C81GMCBKP2' if 'DLC' in steel else 'C81GBKYLMCP2'
        if s == 'C81BK2':
            return 'C81PBBK2' if 'DLC' in steel else 'C81PBK2'
        if s == 'C223PN':
            return 'C223PPNBK' if 'DLC' in steel else 'C223PPN'
        return o2.get(s, s)
    if fid == "C101":
        if s == 'C101GPRBK2' and '2021' not in d:
            return s
        return FIX['mx'].get((s, d[-4:]), FIX['mx'].get(s, s))
    if fid == "C229":
        return FIX['sh'].get(s, s)
    if fid == "C36":
        if s == 'C36GBK' and 'S30V' in steel:
            return 'C36GPBK'
        return FIXM.get(s, s)
    if fid == "C85":
        return FIXY.get(s, s)
    if fid == "C240":
        return FIXS.get(s, s)
    return s


_SKU_TOKEN = re.compile(r"C\d+[A-Z0-9]+")
_TAGS = ("🟥 ", "🟦 ", "🟪 ")


def parse_catalog(text):
    sections, rows = [], []
    section = None
    for line in text.split("\n"):
        m = re.match(r"^## (.+) \(\d+\)$", line)
        if m:
            section = m.group(1)
            sections.append(section)
            continue
        if not re.match(r"^\| \d+ \|", line):
            continue
        cells = [c.strip() for c in line[1:-1].split("|")]
        _, img, sku, released, steel, handle, type_, qty, alt = cells
        for t in _TAGS:
            if type_.startswith(t):
                type_ = type_[len(t):]
        rows.append({"sku": sku, "section": section, "released": released, "steel": steel, "handle": handle,
                     "type": type_, "qty": qty, "alt": alt, "_images": re.findall(r'<img src="([^"]+)"', img)})
    return sections, rows


def _wiki_alt_tokens(alt):
    return set(re.findall(r"(C\d+[A-Z0-9]+) \(wiki\)", alt))


def _score(row, record):
    return (4 * (classify.first_date(record["from_to"]) == row["released"])
            + 2 * (record["steel"] == row["steel"]) + (record["handle"] == row["handle"]))


def link(fid, rows, records):
    """Returns {row index: record index}; each record links at most one row."""
    pairs = []
    for ri, row in enumerate(rows):
        wiki_alts = _wiki_alt_tokens(row["alt"])
        for ki, rec in enumerate(records):
            raw = rec["sku"].split()[0] if rec["sku"].split() else ""
            if canonical_sku(fid, rec) == row["sku"] or raw == row["sku"] or raw in wiki_alts:
                pairs.append((-_score(row, rec), ri, ki))
    pairs.sort()
    linked, used = {}, set()
    for _, ri, ki in pairs:
        if ri not in linked and ki not in used:
            linked[ri] = ki
            used.add(ki)
    return linked


def _site_skus(ref):
    out = set()
    for product in json.loads((ref / "site_all.json").read_text(encoding="utf-8")):
        out.update(s.split(" :: ")[0].strip() for s in product.get("skus", []))
    return out


def _forum_month(forum_text, sku):
    for line in forum_text.split("\n"):
        if re.search(rf"\b{sku}\b", line):
            m = re.search(r"- ([A-Z]{3}) (\d{4})\s*$", line)
            return f"{m.group(1).title()} {m.group(2)}" if m else "?"
    return None


def _aliases(rows, alts):
    skus = {r["sku"] for r in rows}
    pairs = []
    for r in rows:
        wiki_alts = _wiki_alt_tokens(r["alt"])
        pairs += [(t, r["sku"]) for t in _SKU_TOKEN.findall(r["alt"]) if t not in wiki_alts]
    for sku in sorted(skus):
        pairs += [(a, sku) for a in alts.get(sku, [])]
    targets = {}
    for src, dst in pairs:
        if src != dst and src not in skus:
            targets.setdefault(src, set()).add(dst)
    return {k: next(iter(v)) for k, v in sorted(targets.items()) if len(v) == 1}


def _copy_snapshot(ref, cfg):
    for dest in (paths.CACHE / "wiki", paths.TOOLS / "tests" / "fixtures" / "wiki"):
        dest.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ref / cfg["snapshot"], dest / f"{cfg['wiki_page']}.txt")
    return (ref / cfg["snapshot"]).read_text(encoding="utf-8")


def seed(force=False, ref_dir=None):
    ref = Path(ref_dir)
    existing = [p for p in paths.FAMILIES.glob("*.json")] if paths.FAMILIES.exists() else []
    if existing and not force:
        raise SystemExit(f"{paths.FAMILIES} already has family files; pass --force to overwrite")
    paths.FAMILIES.mkdir(parents=True, exist_ok=True)
    site = _site_skus(ref)
    forum = (ref / "forum_p1.txt").read_text(encoding="utf-8")
    alts = json.loads((ref / "alts.json").read_text(encoding="utf-8"))
    old_imgs = json.loads((ref / "imgs.json").read_text(encoding="utf-8"))
    images, report = {}, {}
    for cfg in FAMILIES:
        records = wiki.parse_tables(_copy_snapshot(ref, cfg))
        keys = wiki.source_keys(records)
        text = (paths.CATALOGS / f"{cfg['file']}.md").read_text(encoding="utf-8")
        sections, rows = parse_catalog(text)
        if sections != cfg["sections"]:
            raise SystemExit(f"{cfg['id']}: catalog sections {sections} != {cfg['sections']}")
        fam = {k: cfg[k] for k in ("id", "file", "title", "wiki_page", "readme_label")}
        fam["trailing_newline"] = text.endswith("\n")
        fam["sections"] = cfg["sections"]
        fam["section_rules"] = cfg["section_rules"]
        linked = link(cfg["id"], rows, records)
        used_src, fallback, weak = set(), [], []
        out_rows = []
        for ri, row in enumerate(rows):
            srcs = row.pop("_images")
            if srcs:
                rec = {"file": srcs[0], "extra": srcs[1:]}
                if images.get(row["sku"], rec) != rec:
                    raise SystemExit(f"{row['sku']}: rows disagree on image")
                images[row["sku"]] = rec
            if ri in linked:
                record = records[linked[ri]]
                row["src"] = keys[linked[ri]]
                row["src_raw"] = wiki.raw_of(record)
                row["auto"] = classify.classify_record(fam, record)
                if _score(row, record) < 7:
                    weak.append(f"{row['sku']} {row['released']} <- {row['src']}")
            else:
                sku = row["sku"]
                month = _forum_month(forum, sku)
                if sku in site:
                    row["src"] = f"official|{sku}"
                elif month:
                    row["src"] = f"forum|{sku}|{month}"
                else:
                    row["src"] = f"manual|{sku}"
                base, n = row["src"], 1
                while row["src"] in used_src:
                    n += 1
                    row["src"] = f"{base}#{n}"
                fallback.append(row["src"])
            used_src.add(row["src"])
            out_rows.append(row)
        fam["aliases"] = _aliases(out_rows, alts)
        fam["ignore"] = [k for i, k in enumerate(keys) if i not in linked.values()]
        fam["rows"] = out_rows
        errors = data.validate_family(fam)
        if errors:
            raise SystemExit(f"{cfg['id']}: {errors}")
        data.save_family(fam)
        report[cfg["id"]] = {"rows": len(out_rows), "wiki_linked": len(linked), "fallback": fallback,
                             "ignored": fam["ignore"], "weak": weak}
    for sku, rec in images.items():
        meta = old_imgs.get(sku, {})
        rec.update({k: meta[k] for k in ("url", "src", "page", "verified") if k in meta})
    data.save_images(images)
    (paths.FAMILIES / "_order.json").write_text(json.dumps([c["id"] for c in FAMILIES], indent=1) + "\n", encoding="utf-8")
    shutil.copyfile(ref / "bad_md5.txt", paths.DATA / "bad_md5.txt")
    return report


def print_report(report):
    for fid, r in report.items():
        print(f"{fid}: rows={r['rows']} wiki_linked={r['wiki_linked']} fallback={len(r['fallback'])} ignored={len(r['ignored'])}")
        for label in ("fallback", "ignored", "weak"):
            for item in r[label]:
                print(f"  {label}: {item}")
