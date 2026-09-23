"""Classification helpers ported from tools/gen2.py (kind, dkey, tag) and tools/norm.py (norm)."""

import json
import re

from lib import paths

_MONTHS = {m: i + 1 for i, m in enumerate("jan feb mar apr may jun jul aug sep oct nov dec".split())}

with open(paths.DATA / "dealers.json", encoding="utf-8") as _f:
    ALIASES = json.load(_f)["aliases"]


def tag(type_text):
    if type_text == "Regular production":
        return type_text
    if "Sprint" in type_text:
        return "🟥 " + type_text
    if "excl" in type_text:
        return "🟦 " + type_text
    return "🟪 " + type_text


def date_key(released):
    y = re.search(r"(19|20)\d\d", released)
    m = re.search(r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)", released.lower())
    return (int(y.group()) if y else 9999, _MONTHS[m.group(1)] if m else 0)


def first_date(raw):
    return re.split(r" / |, (?=[A-Z])", raw)[0].strip()


def kind(note, number_made):
    note = re.sub(r"\s*\([^)]*\)", "", note)
    t = (note + " " + number_made).lower()
    if re.match(r"regular", number_made, re.I) or "salt series" in t:
        return "Regular production"
    if t.startswith("limited. originally slated"):
        return "Limited"
    m = re.search(r"([\w.'& -]+?)\s+(dealer |distributor )exclusive", note, re.I)
    if m:
        return m.group(1).strip() + " excl."
    if "sprint" in t:
        return "Sprint Run"
    m = re.search(r"([\w.'& -]+?)\s+(dealer |distributor )?exclusive", note, re.I)
    if m and m.group(1).strip().lower() not in ("distributor", "dealer"):
        return m.group(1).strip().replace("Smokey Mountain Knifeworks", "Smoky Mountain Knife Works") + " excl."
    if "exclusive" in t:
        return "Exclusive"
    return "Limited"


def norm_dealer(type_text):
    if not type_text.endswith(" excl."):
        return type_text
    n = re.split(r"(?<=[a-z]{3})\. ", type_text[:-6])[-1].strip()
    return ALIASES.get(n.lower(), n) + " excl."


def clean_qty(number_made):
    if re.match(r"(limited|sprint|regular|n/a)", number_made, re.I) and len(number_made) < 20:
        return ""
    return number_made


def start_year(raw_from_to):
    m = re.search(r"\d{4}", raw_from_to)
    return m.group() if m else "?"


def _section(fam, record, sku):
    values = {"handle": record["handle"], "sku": sku, "wiki_table": record["table"]}
    for rule in fam.get("section_rules", []):
        if re.search(rule["regex"], values[rule["field"]]):
            return rule["section"]
    return fam["sections"][0]


def classify_record(fam, record):
    tokens = record["sku"].split()
    sku = tokens[0] if tokens else record["sku"]
    return {
        "sku": sku,
        "section": _section(fam, record, sku),
        "released": first_date(record["from_to"]),
        "steel": record["steel"],
        "handle": record["handle"],
        "type": norm_dealer(kind(record["note"], record["number_made"])),
        "qty": clean_qty(record["number_made"]),
    }
