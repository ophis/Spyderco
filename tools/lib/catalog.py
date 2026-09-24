"""Catalogs/<file>.md is the whole record of a family: parse, render, load/save, README model table."""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import unquote

from lib import classify, paths
from lib.fsio import atomic_write

HEADER_TEMPLATE = (
    "Sources: Spydiewiki [{wiki_label}](https://www.spydiewiki.com/index.php?title={wiki_page}) variation table; "
    "Spyderco forum thread [Sprints/Exclusives since Jan 2019]"
    "(https://forum.spyderco.com/viewtopic.php?f=2&t=90980); spyderco.com product listings "
    '(model numbers checked where still listed). "Alt SKU" = other spelling used by the wiki or retailers. '
    "Rows sharing a model number are the same model in different steel generations.\n\n"
    "Type: 🟥 Sprint Run · 🟦 Dealer/distributor exclusive · 🟪 Other limited/exclusive · (no mark) Regular production"
)
TABLE_HEADER = "| # | Image | Model No. | Released | Steel | Handle | Type | Qty | Alt SKU |"
TABLE_SEP = "|---|---|---|---|---|---|---|---|---|"
README_HEADER = "| Model | File | Variants |"
README_SEP = "|---|---|---|"
FAMILIES_START = "<!-- families:start -->"
FAMILIES_END = "<!-- families:end -->"
CONFIG_START, CONFIG_END = "<!-- spy", "-->"
REQUIRED_CONFIG = ("id", "wiki_page", "readme_label")
RULE_FIELDS = ("sku", "handle", "wiki_table")

_SECTION_RE = re.compile(r"^## (.+) \((\d+)\)$")
_IMG_RE = re.compile(r'<a href="([^"]+)"><img src="\1" width="160"></a>')
_TAGS = ("🟥 ", "🟦 ", "🟪 ")


class CatalogError(Exception):
    pass


@dataclass
class Row:
    sku: str
    section: str
    released: str = ""
    steel: str = ""
    handle: str = ""
    type: str = "Regular production"
    qty: str = ""
    alt: str = ""
    images: list = field(default_factory=list)


@dataclass
class Catalog:
    path: Path
    title: str
    preamble: list
    sections: list
    rows: list
    config: dict = None
    trailing_newline: bool = True

    @property
    def id(self):
        return self.config["id"]


def image_cell(images):
    return " ".join(f'<a href="{f}"><img src="{f}" width="160"></a>' for f in images)


def has_config(text):
    return text.split("\n", 3)[2:3] == [CONFIG_START]


def _row(line, section, err):
    if not line.endswith(" |"):
        raise err("table row must end with ' |'")
    cells = line[2:-2].split(" | ")
    if len(cells) != 9:
        raise err(f"expected 9 cells, got {len(cells)}")
    _, img, sku, released, steel, handle, type_cell, qty, alt = cells
    images = _IMG_RE.findall(img)
    if image_cell(images) != img:
        raise err("unrecognised image cell")
    type_ = next((type_cell[len(t):] for t in _TAGS if type_cell.startswith(t)), type_cell)
    if classify.tag(type_) != type_cell:
        raise err(f"type tag does not match the type in {type_cell!r}")
    return Row(sku, section, released, steel, handle, type_, qty, alt, images)


def parse(text, path):
    def err(i, msg):
        return CatalogError(f"{path}:{i + 1}: {msg}")

    trailing = text.endswith("\n")
    lines = (text if trailing else text + "\n").split("\n")
    if not lines[0].startswith("# ") or len(lines) < 2 or lines[1] != "":
        raise err(0, "expected '# <title>' followed by a blank line")
    i, config = 2, None
    if lines[2:3] == [CONFIG_START]:
        try:
            end = lines.index(CONFIG_END, 3)
        except ValueError:
            raise err(2, "unterminated spy config comment") from None
        try:
            config = json.loads("\n".join(lines[3:end]))
        except json.JSONDecodeError as exc:
            raise err(2 + exc.lineno, f"bad config JSON: {exc.msg}") from None
        if lines[end + 1:end + 2] != [""]:
            raise err(end + 1, "expected a blank line after the config comment")
        i = end + 2
    start = i
    while i < len(lines) and not lines[i].startswith("## "):
        i += 1
    preamble, sections, rows = lines[start:i], [], []
    while i < len(lines):
        m = _SECTION_RE.match(lines[i])
        if not m:
            raise err(i, "expected '## <section> (<n>)'")
        if lines[i + 1:i + 4] != ["", TABLE_HEADER, TABLE_SEP]:
            raise err(i + 1, "expected a blank line and the standard table header")
        sections.append(m.group(1))
        i += 4
        while i < len(lines) and lines[i].startswith("| "):
            rows.append(_row(lines[i], m.group(1), lambda msg, i=i: err(i, msg)))
            i += 1
        if lines[i:i + 1] != [""]:
            raise err(i, "expected a blank line after the table")
        i += 1
    return Catalog(Path(path), lines[0][2:], preamble, sections, rows, config, trailing)


def render(cat):
    unknown = {r.section for r in cat.rows} - set(cat.sections)
    if unknown:
        raise CatalogError(f"{cat.path}: rows in unknown sections {sorted(unknown)}")
    lines = [f"# {cat.title}", ""]
    if cat.config is not None:
        lines += [CONFIG_START, *json.dumps(cat.config, ensure_ascii=False, indent=1).split("\n"), CONFIG_END, ""]
    lines += cat.preamble
    for section in cat.sections:
        rows = [r for r in cat.rows if r.section == section]
        lines += [f"## {section} ({len(rows)})", "", TABLE_HEADER, TABLE_SEP]
        lines += [f"| {n} | {image_cell(r.images)} | {r.sku} | {r.released} | {r.steel} | {r.handle} | "
                  f"{classify.tag(r.type)} | {r.qty} | {r.alt} |" for n, r in enumerate(rows, 1)]
        lines.append("")
    text = "\n".join(lines)
    return text if cat.trailing_newline else text[:-1]


def _readme_files():
    if not paths.README.exists():
        return []
    text = paths.README.read_text(encoding="utf-8")
    start, end = text.find(FAMILIES_START), text.find(FAMILIES_END)
    if start == -1 or end == -1:
        return []
    return [unquote(f) for f in re.findall(r"\]\(Catalogs/([^)]+)\.md\)", text[start:end])]


def ordered(cats):
    rank = {f: n for n, f in reversed(list(enumerate(_readme_files())))}
    return sorted(cats, key=lambda c: (rank.get(c.path.stem, len(rank)), c.path.name))


def _catalogs():
    found = {}
    for path in sorted(paths.CATALOGS.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        if not has_config(text):
            continue
        cat = parse(text, path)
        id_ = cat.config.get("id")
        if not id_:
            raise CatalogError(f"{path}: spy config has no 'id'")
        if id_ in found:
            raise CatalogError(f"{path}: id {id_!r} is also used by {found[id_].path}")
        found[id_] = cat
    return ordered(found.values())


def all_ids():
    return [c.id for c in _catalogs()]


def load(id_):
    cat = next((c for c in _catalogs() if c.id == id_), None)
    if cat is None:
        raise CatalogError(f"no catalog in {paths.CATALOGS} has id {id_!r}")
    return cat


def readme_table(cats):
    lines = [README_HEADER, README_SEP]
    for cat in cats:
        file = cat.path.stem
        lines.append(f"| {cat.config['readme_label']} | [{file}](Catalogs/{file.replace(' ', '%20')}.md) | {len(cat.rows)} |")
    return "\n".join(lines)


def readme_expected(cats):
    if not paths.README.exists():
        return None
    text = paths.README.read_text(encoding="utf-8")
    start, end = text.find(FAMILIES_START), text.find(FAMILIES_END)
    if start == -1 or end == -1:
        return None
    return f"{text[:start + len(FAMILIES_START)]}\n{readme_table(cats)}\n{text[end:]}"


def save(cat):
    atomic_write(cat.path, render(cat))
    written = [cat.path]
    cats = [cat if c.id == cat.id else c for c in _catalogs()]
    expected = readme_expected(cats)
    if expected is not None and expected != paths.README.read_text(encoding="utf-8"):
        atomic_write(paths.README, expected)
        written.append(paths.README)
    return written


def config_problems(cat):
    cfg = cat.config
    problems = [f"missing config key {k!r}" for k in REQUIRED_CONFIG if k not in cfg]
    for rule in cfg.get("section_rules", []):
        if rule.get("section") not in cat.sections:
            problems.append(f"section rule for unknown section {rule.get('section')!r}")
        if rule.get("field") not in RULE_FIELDS:
            problems.append(f"section rule field {rule.get('field')!r} not one of {RULE_FIELDS}")
        try:
            re.compile(rule.get("regex", ""))
        except (re.error, TypeError) as exc:
            problems.append(f"bad section rule regex {rule.get('regex')!r}: {exc}")
    keys = {f"{r.sku}|{r.released}" for r in cat.rows}
    skus = {r.sku for r in cat.rows}
    problems += [f"wiki_errors key {k!r} matches no row" for k in cfg.get("wiki_errors", {}) if k not in keys]
    problems += [f"manual SKU {s!r} matches no row" for s in cfg.get("manual", []) if s not in skus]
    return problems


def _cmd_render(args):
    try:
        ids = all_ids() if args.all else args.ids
        if not ids:
            print("no family ids given (pass ids or --all)")
            return 1
        written = []
        for id_ in ids:
            written += [p for p in save(load(id_)) if p not in written]
    except CatalogError as exc:
        print(f"error: {exc}")
        return 1
    print("\n".join(str(p) for p in written))
    return 0


def register(subparsers):
    p = subparsers.add_parser("render", help="rewrite catalogs in normal form (numbering, counts) and the README table")
    p.add_argument("ids", nargs="*", help="family ids")
    p.add_argument("--all", action="store_true", help="every catalog")
    p.set_defaults(func=_cmd_render)
