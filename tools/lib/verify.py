"""spy.py verify: offline consistency checks over Catalogs/*.md and the README model table."""

from lib import catalog, paths


def _check(path, text):
    cat = catalog.parse(text, path)
    name = path.name
    problems = [f"{name}: {p}" for p in catalog.config_problems(cat)]
    if catalog.render(cat) != text:
        problems.append(f"{name}: not in rendered form; run `spy.py render {cat.config.get('id', '')}`")
    seen = set()
    for r in cat.rows:
        if (r.sku, r.released) in seen:
            problems.append(f"{name}: duplicate sku {r.sku!r} with released {r.released!r}")
        seen.add((r.sku, r.released))
        problems += [f"{name}: {r.sku}: broken image link {f}" for f in r.images if not (paths.CATALOGS / f).exists()]
    return cat, problems


def run():
    problems, cats = [], []
    for path in sorted(paths.CATALOGS.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        if not catalog.has_config(text):
            continue
        try:
            cat, found = _check(path, text)
        except catalog.CatalogError as exc:
            problems.append(str(exc))
            continue
        problems += found
        if all(k in cat.config for k in catalog.REQUIRED_CONFIG):
            cats.append(cat)
    expected = catalog.readme_expected(catalog.ordered(cats))
    if expected is not None and expected != paths.README.read_text(encoding="utf-8"):
        problems.append("README family table is out of date; run `spy.py render --all`")
    return problems


def _cmd_verify(args):
    problems = run()
    print("\n".join(problems) if problems else "verify: ok")
    return 1 if problems else 0


def register(subparsers):
    p = subparsers.add_parser("verify", help="offline checks: rendered form, README table, image links, config, duplicates")
    p.set_defaults(func=_cmd_verify)
