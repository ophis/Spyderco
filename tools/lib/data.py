"""Family data model: load/save/validate family JSON and the image record store."""

import json

from lib import paths
from lib.fsio import atomic_write, dump_json

REQUIRED_KEYS = ("id", "file", "title", "wiki_page", "sections", "rows")


class FamilyError(Exception):
    pass


def _family_path(id_):
    return paths.FAMILIES / f"{id_}.json"


def load_family(id_):
    path = _family_path(id_)
    try:
        fam = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FamilyError(f"{path}: {exc}") from exc
    errors = validate_family(fam)
    if errors:
        raise FamilyError(f"{path}: {'; '.join(errors)}")
    return fam


def save_family(fam):
    atomic_write(_family_path(fam["id"]), dump_json(fam))


def validate_family(fam):
    errors = [f"missing key {key!r}" for key in REQUIRED_KEYS if key not in fam]
    if "sections" in fam and "rows" in fam:
        sections = set(fam["sections"])
        seen_src = set()
        for row in fam["rows"]:
            section = row.get("section")
            if section not in sections:
                errors.append(f"row {row.get('src', '?')!r} has unknown section {section!r}")
            src = row.get("src")
            if src in seen_src:
                errors.append(f"duplicate src {src!r}")
            seen_src.add(src)
    return errors


def all_family_ids():
    order_path = paths.FAMILIES / "_order.json"
    if order_path.exists():
        return json.loads(order_path.read_text(encoding="utf-8"))
    return sorted(p.stem for p in paths.FAMILIES.glob("*.json") if not p.name.startswith("_"))


def _images_path():
    return paths.DATA / "images.json"


def load_images():
    path = _images_path()
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_images(images):
    atomic_write(_images_path(), dump_json(images))
