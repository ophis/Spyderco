"""Wiki table parsing and source keys, ported from reference tools/parse.py."""

import json
import re
import urllib.error
import urllib.parse
import urllib.request

from lib import classify

_WIKILINK_RE = re.compile(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]")
_EXTLINK_RE = re.compile(r"\[https?://\S+ ([^\]]*)\]")
_MARKUP_RE = re.compile(r"'''?|<[^>]+>")
_VALIGN_RE = re.compile(r'^valign="top" \|')
_TABLE_RE = re.compile(r"\{\|(.*?)\n\|\}", re.S)
_HEADING_RE = re.compile(r"^(={2,4})([^=\n]+?)\1\s*$", re.M)
_TABLEHEADING_RE = re.compile(r"\{\{Tableheading\}\}(.*)")
_SKU_RE = re.compile(r"^C\d")

_STANDARD_FIELDS = {
    "sku": "sku",
    "handle": "handle",
    "edge": "edge",
    "steel": "steel",
    "from/to": "from_to",
    "msrp": "msrp",
    "note": "note",
    "number made": "number_made",
}
_RAW_KEYS = ("table", "sku", "handle", "edge", "steel", "from_to", "note", "number_made")


def clean(s):
    """Port of reference parse.clean, plus stripping a leading '|' and whitespace."""
    s = _WIKILINK_RE.sub(r"\1", s)
    s = _EXTLINK_RE.sub(r"\1", s)
    s = _MARKUP_RE.sub("", s)
    s = _VALIGN_RE.sub("", s.strip())
    s = s.lstrip("|")
    return re.sub(r"\s+", " ", s).strip()


def _norm_header(header):
    return re.sub(r"\(s\)$", "", header.strip().lower())


def _heading_before(text, pos):
    heading = ""
    for m in _HEADING_RE.finditer(text):
        if m.start() >= pos:
            break
        heading = clean(m.group(2))
    return heading


def parse_tables(wikitext):
    records = []
    for tm in _TABLE_RE.finditer(wikitext):
        body = tm.group(1)
        heads = [clean(h) for h in _TABLEHEADING_RE.findall(body)]
        if not heads:
            continue
        heading = _heading_before(wikitext, tm.start())
        for chunk in re.split(r"\n\|-", body):
            cells = [
                clean(line[1:])
                for line in chunk.split("\n")
                if line.startswith("|") and not line.startswith("|-") and not line.startswith("|}")
            ]
            if not cells or not _SKU_RE.match(cells[0]):
                continue
            fields = dict(zip(heads, cells))
            record = {"table": heading, "fields": fields}
            for key in _STANDARD_FIELDS.values():
                record[key] = ""
            for header, cell in fields.items():
                key = _STANDARD_FIELDS.get(_norm_header(header))
                if key:
                    record[key] = cell
            records.append(record)
    if not records:
        raise ValueError("no variation tables")
    return records


def source_keys(records):
    counts = {}
    keys = []
    for record in records:
        sku = record["sku"]
        token = sku.split()[0] if sku.split() else sku
        base = f"wiki|{token}|{classify.start_year(record['from_to'])}"
        counts[base] = counts.get(base, 0) + 1
        n = counts[base]
        keys.append(base if n == 1 else f"{base}#{n}")
    return keys


def raw_of(record):
    return {k: record[k] for k in _RAW_KEYS}


def fetch(page):
    url = "https://www.spydiewiki.com/api.php?" + urllib.parse.urlencode(
        {"action": "parse", "page": page, "prop": "wikitext", "format": "json"}
    )
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.load(resp)
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"fetch failed for {page!r}: {exc}") from exc
    try:
        return data["parse"]["wikitext"]["*"]
    except (KeyError, TypeError) as exc:
        raise RuntimeError(f"unexpected response for {page!r}: {data}") from exc
