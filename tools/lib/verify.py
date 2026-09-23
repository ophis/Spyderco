"""spy.py verify: offline consistency checks across families/, Catalogs/ and data/images.json."""

import json
import re

from lib import data, paths, render

_IMG_SRC_RE = re.compile(r'<img src="([^"]+)"')


def _load_raw(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _missing_src_rows(id_, fam):
    return [f"{id_}: row {row.get('sku', '?')!r} has no src" for row in fam.get("rows", []) if not row.get("src")]


def _duplicate_skus(id_, fam):
    seen, problems = set(), []
    for row in fam["rows"]:
        key = (row.get("sku"), row.get("released"))
        if key in seen:
            problems.append(f"{id_}: duplicate sku {key[0]!r} with released {key[1]!r}")
        seen.add(key)
    return problems


def _check_render(id_, fam, images):
    path = paths.CATALOGS / f"{fam['file']}.md"
    if not path.exists():
        return [f"{id_}: {path} does not exist"]
    if render.render_family(fam, images).encode("utf-8") != path.read_bytes():
        return [f"{id_}: rendered output differs from {path}"]
    return []


def _check_image_links(id_, fam):
    path = paths.CATALOGS / f"{fam['file']}.md"
    if not path.exists():
        return []
    return [f"{id_}: broken image link {rel}" for rel in _IMG_SRC_RE.findall(path.read_text(encoding="utf-8"))
            if not (paths.CATALOGS / rel).exists()]


def _check_readme(families):
    if not paths.README.exists():
        return []
    text = paths.README.read_text(encoding="utf-8")
    start, end = text.find(render.FAMILIES_START), text.find(render.FAMILIES_END)
    if start == -1 or end == -1:
        return []
    expected = f"\n{render.render_readme_table(families)}\n"
    if text[start + len(render.FAMILIES_START):end] != expected:
        return ["README family table is out of date; run `spy.py render --all`"]
    return []


def _check_images(images, family_skus):
    problems = []
    for sku, rec in images.items():
        for f in (rec.get("file"), *rec.get("extra", [])):
            if f and not (paths.IMAGES.parent / f).exists():
                problems.append(f"image record {sku}: missing file {f}")
        if sku not in family_skus:
            problems.append(f"image record {sku}: not a SKU of any family")
    return problems


def run():
    problems = []
    images = data.load_images()
    families, family_skus = [], set()
    for id_ in data.all_family_ids():
        path = paths.FAMILIES / f"{id_}.json"
        try:
            fam = _load_raw(path)
        except (OSError, json.JSONDecodeError) as exc:
            problems.append(f"{id_}: {exc}")
            continue
        problems += [f"{id_}: {e}" for e in data.validate_family(fam)]
        if any(key not in fam for key in data.REQUIRED_KEYS):
            continue
        problems += _missing_src_rows(id_, fam)
        problems += _duplicate_skus(id_, fam)
        family_skus |= {row["sku"] for row in fam["rows"] if row.get("sku")}
        try:
            problems += _check_render(id_, fam, images)
            problems += _check_image_links(id_, fam)
            if "readme_label" in fam:
                families.append(fam)
        except (KeyError, TypeError) as exc:
            problems.append(f"{id_}: {exc}")
    try:
        problems += _check_readme(families)
    except (KeyError, TypeError) as exc:
        problems.append(f"README: {exc}")
    problems += _check_images(images, family_skus)
    return problems


def _cmd_verify(args):
    problems = run()
    if problems:
        print("\n".join(problems))
        return 1
    print("verify: ok")
    return 0


def register(subparsers):
    p = subparsers.add_parser("verify", help="offline consistency checks (render diff, README, images, row data)")
    p.set_defaults(func=_cmd_verify)
