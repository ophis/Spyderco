"""Network sources (wiki, spyderco.com, forum, dealer sitemaps) and the Python <-> browser helper interface."""

import json
import re
import subprocess
import urllib.error
import urllib.request
import uuid

from lib import catalog, paths, wiki
from lib.fsio import atomic_write, dump_json

FORUM_URL = "https://forum.spyderco.com/viewtopic.php?f=2&t=90980"
BLADEHQ_DOMAINS = ("bladehq.com",)

_MONTHS = "JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split()
_FORUM_LINE_RE = re.compile(r"- (" + "|".join(_MONTHS) + r") (20\d\d)$")
_SKU_RE = re.compile(r"\bC\d[A-Z0-9]*\b")
_LOC_RE = re.compile(r"<loc>\s*([^<\s]+)")

HELPER_MESSAGES = {
    2: "verification page — run `spy.py browser open <url>` and retry",
    3: "blocked (403)",
    4: "timeout/network",
}


class FetchError(Exception):
    pass


def run_helper(script, job, cmd=None):
    """Run a browser/*.mjs helper (or `cmd`, for tests) on `job`, return its parsed result JSON."""
    jobs_dir = paths.CACHE / "jobs"
    jobs_dir.mkdir(parents=True, exist_ok=True)
    job_id = uuid.uuid4().hex
    job_path = jobs_dir / f"{job_id}.json"
    result_path = jobs_dir / f"{job_id}.result.json"
    atomic_write(job_path, dump_json({**job, "result": str(result_path)}))

    command = list(cmd) if cmd is not None else ["node", str(paths.TOOLS / "browser" / script)]
    proc = subprocess.run([*command, str(job_path)], capture_output=True, text=True)

    if proc.returncode == 0:
        if not result_path.exists():
            raise FetchError(f"{script}: exited 0 but wrote no result")
        return json.loads(result_path.read_text(encoding="utf-8"))
    if proc.returncode in HELPER_MESSAGES:
        raise FetchError(HELPER_MESSAGES[proc.returncode])
    detail = (proc.stderr or proc.stdout or "").strip()
    raise FetchError(f"{script} exited {proc.returncode}" + (f": {detail}" if detail else ""))


def parse_products(pages):
    """Trim raw spyderco.com products.json product dicts to the cache/official.json record shape."""
    out = []
    for product in pages:
        skus = [v["sku"] for v in product.get("variants", []) if v.get("sku")]
        images = [img["src"] for img in product.get("images", []) if img.get("src")]
        out.append({
            "title": product.get("title", ""),
            "handle": product.get("handle", ""),
            "published": product.get("published_at", ""),
            "skus": skus,
            "images": images,
        })
    if not out:
        raise ValueError("no products")
    return out


def parse_forum(text):
    """Parse forum post-1 release lines ('... - MON YYYY') into {line, skus, month_year} records."""
    out = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        m = _FORUM_LINE_RE.search(line)
        if not m:
            continue
        out.append({"line": line, "skus": _SKU_RE.findall(line), "month_year": f"{m.group(1)} {m.group(2)}"})
    if not out:
        raise ValueError("no forum release lines found")
    return out


def fetch_wiki(id_):
    page = catalog.load(id_).config["wiki_page"]
    text = wiki.fetch(page)
    wiki.parse_tables(text)
    path = paths.CACHE / "wiki" / f"{page}.txt"
    atomic_write(path, text)
    return path


def fetch_official(cmd=None):
    products = run_helper("products.mjs", {"url": "https://www.spyderco.com/"}, cmd=cmd)
    parsed = parse_products(products)
    path = paths.CACHE / "official.json"
    atomic_write(path, dump_json(parsed))
    return path


def fetch_forum(cmd=None):
    result = run_helper("forum.mjs", {"url": FORUM_URL}, cmd=cmd)
    text = result["text"] if isinstance(result, dict) else result
    parse_forum(text)
    path = paths.CACHE / "forum.txt"
    atomic_write(path, text)
    return path


def _needs_browser(domain):
    return any(domain == d or domain.endswith(f".{d}") for d in BLADEHQ_DOMAINS)


def _sitemap_locs(text):
    return [loc.replace("&amp;", "&") for loc in _LOC_RE.findall(text)]


def _fetch_url(url, timeout=60):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="ignore")
    except (urllib.error.URLError, OSError):
        return ""


def _crawl_sitemap(domain, max_pages=80):
    """Port of reference smap.py: follow sitemap indexes (incl. product sub-sitemaps), collect leaf URLs."""
    seen = set()
    todo = [f"https://www.{domain}/sitemap.xml", f"https://{domain}/sitemap.xml", f"https://www.{domain}/xmlsitemap.php"]
    locs = set()
    while todo:
        url = todo.pop()
        if url in seen or len(seen) > max_pages:
            continue
        seen.add(url)
        for loc in _sitemap_locs(_fetch_url(url)):
            if re.search(r"sitemap|\.xml", loc, re.I) and (
                re.search(r"product", loc, re.I) or not re.search(r"blog|page|collection|categor|brand|image|post", loc, re.I)
            ):
                todo.append(loc)
            else:
                locs.add(loc)
    return sorted(locs)


def fetch_sitemaps(domains, cmd=None):
    out = {}
    for domain in domains:
        if _needs_browser(domain):
            result = run_helper("sitemap_bhq.mjs", {"domain": domain}, cmd=cmd)
            out[domain] = result.get("urls", []) if isinstance(result, dict) else result
        else:
            out[domain] = _crawl_sitemap(domain)
    if not any(out.values()):
        raise ValueError("no sitemap URLs found")
    path = paths.CACHE / "sitemaps.json"
    atomic_write(path, dump_json(out))
    return path


def browser_open(url, cmd=None):
    run_helper("open.mjs", {"url": url}, cmd=cmd)
    return url


def _cmd_handler(fn):
    def handler(args):
        try:
            fn(args)
        except (FetchError, ValueError, FileNotFoundError, RuntimeError, catalog.CatalogError) as exc:
            print(f"error: {exc}")
            return 1
        return 0
    return handler


def register(subparsers):
    p = subparsers.add_parser("fetch", help="fetch a source into cache/")
    sub = p.add_subparsers(dest="source", required=True)

    wp = sub.add_parser("wiki", help="fetch a family's Spydiewiki page")
    wp.add_argument("id")
    wp.set_defaults(func=_cmd_handler(lambda a: print(fetch_wiki(a.id))))

    op = sub.add_parser("official", help="fetch spyderco.com products.json")
    op.set_defaults(func=_cmd_handler(lambda a: print(fetch_official())))

    fp = sub.add_parser("forum", help="fetch forum post 1 (Sprints/Exclusives thread)")
    fp.set_defaults(func=_cmd_handler(lambda a: print(fetch_forum())))

    sp = sub.add_parser("sitemaps", help="crawl dealer sitemaps (Blade HQ via the browser helper)")
    sp.add_argument("domains", nargs="*")
    sp.set_defaults(func=_cmd_handler(lambda a: print(fetch_sitemaps(a.domains))))

    bp = subparsers.add_parser("browser", help="browser utilities")
    bsub = bp.add_subparsers(dest="browser_cmd", required=True)
    ob = bsub.add_parser("open", help="open a URL in the tool's Chrome profile for manual verification")
    ob.add_argument("url")
    ob.set_defaults(func=_cmd_handler(lambda a: print(browser_open(a.url))))
