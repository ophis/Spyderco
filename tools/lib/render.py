"""Renders family data into catalog Markdown, and the README family table."""

from lib import classify, data, paths

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


def _image_cell(sku, images):
    record = images.get(sku)
    if not record:
        return ""
    files = [record["file"], *record.get("extra", [])]
    links = [f'<a href="{f}"><img src="{f}" width="160"></a>' for f in files if (paths.CATALOGS / f).exists()]
    return " ".join(links)


def render_family(fam, images):
    wiki_page = fam["wiki_page"]
    lines = [f"# {fam['title']}", ""]
    lines.extend(HEADER_TEMPLATE.format(wiki_label=wiki_page.replace("_", " "), wiki_page=wiki_page).split("\n"))
    lines.append("")
    rows_by_section = {}
    for row in fam["rows"]:
        rows_by_section.setdefault(row["section"], []).append(row)
    for section in fam["sections"]:
        rows = rows_by_section.get(section, [])
        lines.append(f"## {section} ({len(rows)})")
        lines.append("")
        lines.append(TABLE_HEADER)
        lines.append(TABLE_SEP)
        for i, row in enumerate(rows, 1):
            img = _image_cell(row["sku"], images)
            lines.append(
                f"| {i} | {img} | {row['sku']} | {row['released']} | {row['steel']} | "
                f"{row['handle']} | {classify.tag(row['type'])} | {row['qty']} | {row['alt']} |"
            )
        lines.append("")
    text = "\n".join(lines)
    if not fam.get("trailing_newline", True):
        text = text.rstrip("\n")
    return text


def render_readme_table(families):
    lines = [README_HEADER, README_SEP]
    for fam in families:
        url = fam["file"].replace(" ", "%20")
        lines.append(f"| {fam['readme_label']} | [{fam['file']}](Catalogs/{url}.md) | {len(fam['rows'])} |")
    return "\n".join(lines)


def _update_readme(families):
    if not paths.README.exists():
        return None
    text = paths.README.read_text(encoding="utf-8")
    start = text.find(FAMILIES_START)
    end = text.find(FAMILIES_END)
    if start == -1 or end == -1:
        return None
    before = text[: start + len(FAMILIES_START)]
    after = text[end:]
    new_text = f"{before}\n{render_readme_table(families)}\n{after}"
    if new_text == text:
        return None
    paths.README.write_text(new_text, encoding="utf-8")
    return paths.README


def write_all(ids):
    images = data.load_images()
    loaded = {}
    written = []
    for id_ in ids:
        fam = data.load_family(id_)
        loaded[id_] = fam
        path = paths.CATALOGS / f"{fam['file']}.md"
        path.write_text(render_family(fam, images), encoding="utf-8")
        written.append(path)
    all_ids = data.all_family_ids()
    all_families = [loaded[i] if i in loaded else data.load_family(i) for i in all_ids]
    readme_path = _update_readme(all_families)
    if readme_path is not None:
        written.append(readme_path)
    return written


def _cmd_render(args):
    ids = data.all_family_ids() if args.all else args.ids
    if not ids:
        print("no family ids given (pass ids or --all)")
        return 1
    for path in write_all(ids):
        print(path)
    return 0


def register(subparsers):
    parser = subparsers.add_parser("render", help="render family JSON into Catalogs Markdown")
    parser.add_argument("ids", nargs="*", help="family ids to render")
    parser.add_argument("--all", action="store_true", help="render every family")
    parser.set_defaults(func=_cmd_render)
