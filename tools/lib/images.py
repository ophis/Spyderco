"""Photo mechanics: candidate lists, browser fetch, gallery, contact sheets, accept/reject into the catalog."""

import hashlib
import json
import re
import shutil
import uuid
from pathlib import Path
from urllib.parse import urlparse

from lib import catalog, paths, sources
from lib.fsio import atomic_write, dump_json

JUNK_RE = (r"logo|icon|badge|sprite|payment|flag|attributes|placeholder|maintenance|seedprod|sorry|not-?found|404"
           r"|coming|boker|hand-tools|social|share|og-image|no-?image|default|coming-?soon|blank")
GALLERY_JUNK_RE = r"logo|icon|badge|sprite|payment|flag|placeholder|banner|avatar|review"
SEARCH_RE = r"[/?](search|find)[/?=]"
_FORMATS = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}
_SHEET_T, _SHEET_C, _SHEET_R = 180, 8, 5


def md5_bytes(content):
    return hashlib.md5(content).hexdigest()


def md5_file(path):
    return md5_bytes(Path(path).read_bytes())


def _bad_path():
    return paths.DATA / "bad_md5.txt"


def bad_md5s():
    p = _bad_path()
    return set(p.read_text(encoding="utf-8").split()) if p.exists() else set()


def _abs(rel):
    return paths.IMAGES.parent / rel


def _load_json(path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def key_pattern(keys):
    """JS/Python-compatible regex: a SKU/alias (leading C optional) not glued to other SKU characters."""
    cores = sorted({re.escape(k.upper()[1:] if k.upper().startswith("C") else k.upper()) for k in keys}, key=len, reverse=True)
    return r"(?<![A-Z0-9])C?(?:" + "|".join(cores) + r")(?:BOTH|(?![A-Z0-9]))"


def analyse(path):
    from PIL import Image

    with Image.open(path) as im:
        w, h = im.size
        if im.mode in ("RGBA", "LA", "P"):
            rgba = im.convert("RGBA")
            bg = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
            bg.alpha_composite(rgba)
            im = bg
        im = im.convert("RGB")
        k = max(4, w // 50)
        corners = [im.getpixel((x, y)) for x, y in ((k, k), (w - k, k), (k, h - k), (w - k, h - k))]
    return {"w": w, "h": h, "white": all(min(p) > 235 for p in corners), "ratio": round(w / h, 2)}


def choose(cands):
    bad = bad_md5s()
    ok = [c for c in cands
          if c["w"] >= 200 and 0.4 <= c["ratio"] <= 2.2
          and (c.get("md5") or md5_file(c["path"])) not in bad]
    big = [c for c in ok if c["w"] >= 600]
    return next((c for c in big if c["white"]), None) or (big[0] if big else None) or max(ok, key=lambda c: c["w"], default=None)


def target_name(id_, sku, ext, extra, content):
    stem = f"{sku}_2" if extra else sku
    rel = f"images/{id_}/{stem}.{ext}"
    if _abs(rel).exists():
        rel = f"images/{id_}/{stem}.{md5_bytes(content)[:6]}.{ext}"
    return rel


def _family_skus(cat):
    return list(dict.fromkeys(r.sku for r in cat.rows))


def _images_of(cat, sku):
    return next((list(r.images) for r in cat.rows if r.sku == sku), [])


def _aliases(cat, sku):
    # record-key aliases ("SKU|year") are not spellings; they would corrupt key_pattern
    return [a for a, s in cat.config.get("aliases", {}).items() if s == sku and "|" not in a]


def _record_page(id_, sku, page):
    path = _candidates_path(id_)
    cands = _load_json(path, {})
    cands.setdefault(sku, {"candidates": []})["page"] = page
    atomic_write(path, dump_json(cands))


def _image_ext(path):
    from PIL import Image

    try:
        with Image.open(path) as im:
            fmt = im.format
    except OSError as exc:
        raise ValueError(f"{path}: not an image ({exc})") from exc
    if fmt not in _FORMATS:
        raise ValueError(f"{path}: unsupported format {fmt}")
    return _FORMATS[fmt]


def _cached_meta(file):
    """page recorded for a file saved by `photos fetch` (review) or `photos gallery`."""
    file = Path(file).resolve()
    for index in (paths.CACHE / "review" / "review.json", paths.CACHE / "gallery" / "gallery.json"):
        entry = _load_json(index, {}).get(file.name)
        if entry and file.parent == index.parent.resolve() and entry.get("page"):
            return {"page": entry["page"]}
    return {}


def accept(id_, sku, file, extra=False, replace=False, page=None):
    cat = catalog.load(id_)
    if sku not in _family_skus(cat):
        raise ValueError(f"{sku} is not a SKU of family {id_}")
    file = Path(file)
    content = file.read_bytes()
    digest = md5_bytes(content)
    if digest in bad_md5s():
        raise ValueError(f"{file}: md5 {digest} is blacklisted")
    ext = _image_ext(file)
    current = _images_of(cat, sku)
    if extra and not current:
        raise ValueError(f"{sku} has no main photo; accept one before an extra")
    if not extra and current and not replace:
        raise ValueError(f"{sku} already has a main photo ({current[0]}); pass --replace")
    if any(_abs(f).exists() and md5_file(_abs(f)) == digest for f in current):
        raise ValueError(f"{file}: already recorded for {sku}")
    rel = target_name(id_, sku, ext, extra, content)
    atomic_write(_abs(rel), content)
    new = [*current, rel] if extra else [rel, *current[1:]]
    for r in cat.rows:
        if r.sku == sku:
            r.images = list(new)
    catalog.save(cat)
    page = page or _cached_meta(file).get("page")
    if page and not extra:
        _record_page(id_, sku, page)
    if not extra and current and current[0] != rel and _abs(current[0]).exists():
        _abs(current[0]).unlink()
    return rel


def reject(file):
    digest = md5_file(file)
    if digest not in bad_md5s():
        p = _bad_path()
        text = p.read_text(encoding="utf-8") if p.exists() else ""
        atomic_write(p, text + ("\n" if text and not text.endswith("\n") else "") + digest + "\n")
    return digest


def _url_has(url, keys):
    return re.search(key_pattern(keys), url, re.I) is not None


def _filename(url):
    return urlparse(url).path.rsplit("/", 1)[-1]


def _official(sku):
    products = _load_json(paths.CACHE / "official.json", [])
    out = []
    for product in products:
        for img in product.get("images", []):
            name = _filename(img).upper()
            if "BOTH" in name and (name.startswith(sku.upper() + "_") or name.startswith(sku.upper() + "BOTH")):
                out.append((img, f"https://www.spyderco.com/products/{product['handle']}"))
    return out


def _dealer_domain(cat, sku):
    dealers = _load_json(paths.DATA / "dealers.json", {}).get("domains", {})
    for row in cat.rows:
        if row.sku == sku and row.type.endswith(" excl."):
            domain = dealers.get(row.type[:-6])
            if domain:
                return domain
    return None


def _candidates_path(id_):
    return paths.CACHE / "candidates" / f"{id_}.json"


def candidates(id_, skus=None, add=()):
    cat = catalog.load(id_)
    family_skus = _family_skus(cat)
    extra = []
    for item in add:
        sku, sep, url = item.partition("=")
        if not sep or not url.startswith("http"):
            raise ValueError(f"--add expects SKU=URL, got {item!r}")
        if sku not in family_skus:
            raise ValueError(f"{sku} is not a SKU of family {id_}")
        extra.append((sku, url))
    targets = list(skus) if skus else [s for s in family_skus if not _images_of(cat, s)]
    targets += [s for s, _ in extra if s not in targets]
    unknown = [s for s in targets if s not in family_skus]
    if unknown:
        raise ValueError(f"not SKUs of family {id_}: {', '.join(unknown)}")

    sitemaps = _load_json(paths.CACHE / "sitemaps.json", {})
    path = _candidates_path(id_)
    out = _load_json(path, {})
    for sku in targets:
        keys = [sku, *_aliases(cat, sku)]
        found = [(url, page, "official") for url, page in _official(sku)]
        dealer = _dealer_domain(cat, sku)
        if dealer:
            found += [(u, u, "dealer") for u in sitemaps.get(dealer, []) if _url_has(u, keys)]
        for domain, urls in sitemaps.items():
            if domain != dealer:
                found += [(u, u, "sitemap") for u in urls if _url_has(u, keys)]
        found += [(u, u, "add") for s, u in extra if s == sku]

        entry = out.setdefault(sku, {"candidates": []})
        entry["aliases"] = keys[1:]
        known = {c["url"] for c in entry["candidates"]}
        for url, page, source in found:
            if url not in known:
                known.add(url)
                entry["candidates"].append({"url": url, "page": page, "source": source, "status": "pending"})
    atomic_write(path, dump_json(out))
    return path


def _review(sku, best, result):
    review_dir = paths.CACHE / "review"
    src = Path(best["path"])
    name = f"{sku}.{best['md5'][:6]}.{_image_ext(src)}"
    review_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, review_dir / name)
    index_path = review_dir / "review.json"
    index = _load_json(index_path, {})
    index[name] = {"sku": sku, "page": result["page"], "url": best["url"], "w": best["w"], "h": best["h"],
                   "white": best["white"], "verified": result.get("verified", False)}
    atomic_write(index_path, dump_json(index))
    return review_dir / name


def _take(id_, sku, res, entry, summary):
    found = []
    for img in res.get("images", []):
        try:
            found.append({**img, **analyse(img["path"]), "md5": md5_file(img["path"])})
        except OSError:
            continue
    best = choose(found)
    if best is None:
        return "none"
    if _images_of(catalog.load(id_), sku):
        return "skipped"
    if res.get("verified"):
        accept(id_, sku, best["path"])
        # fetch rewrites the candidates file from its in-memory copy at the end; record the page there
        entry.update(done=True, page=res["page"])
        summary["accepted"].append(sku)
        return "accepted"
    summary["review"].append(str(_review(sku, best, res)))
    return "review"


def fetch(id_, cmd=None):
    """Visit pending candidates; auto-accept only page-verified finds for SKUs still without a photo."""
    cat = catalog.load(id_)
    path = _candidates_path(id_)
    if not path.exists():
        raise FileNotFoundError(f"{path}: run `spy.py photos candidates {id_}` first")
    cands = _load_json(path, {})
    has = {r.sku for r in cat.rows if r.images}

    items = []
    for sku, entry in cands.items():
        if entry.get("done") or sku in has:
            continue
        urls = []
        for c in entry["candidates"]:
            if c["status"] == "pending" and re.search(SEARCH_RE, c["url"], re.I):
                c["status"] = "search"
            elif c["status"] in ("pending", "error"):
                urls.append(c["url"])
        if urls:
            items.append({"sku": sku, "keys": [sku, *entry.get("aliases", [])], "urls": urls})
    if not items:
        atomic_write(path, dump_json(cands))
        return {"accepted": [], "review": [], "stopped": None}

    tmp = paths.CACHE / "tmp" / uuid.uuid4().hex
    job = {"mode": "best", "items": [{**i, "verify_re": key_pattern(i["keys"])} for i in items], "out": str(tmp),
           "junk_re": JUNK_RE, "bad_md5": sorted(bad_md5s()), "max": 8}
    summary = {"accepted": [], "review": []}
    try:
        result = sources.run_helper("gallery.mjs", job, cmd=cmd)
        pages = {(sku, c["url"]): c for sku, entry in cands.items() for c in entry["candidates"]}
        for res in result.get("results", []):
            sku, cand = res["sku"], pages.get((res["sku"], res["url"]))
            if cand is None:
                continue
            if res["status"] != "ok":
                cand["status"] = "pending" if res["status"] == "verify" else res["status"]
                if res.get("error"):
                    cand["error"] = res["error"]
                continue
            try:
                cand["status"] = _take(id_, sku, res, cands[sku], summary)
            except (ValueError, OSError) as exc:
                cand.update(status="error", error=str(exc))
        summary["stopped"] = result.get("stopped")
    finally:
        atomic_write(path, dump_json(cands))
        shutil.rmtree(tmp, ignore_errors=True)
    return summary


def gallery(id_, sku, page=None, cmd=None):
    cat = catalog.load(id_)
    if sku not in _family_skus(cat):
        raise ValueError(f"{sku} is not a SKU of family {id_}")
    current = _images_of(cat, sku)
    page = page or _load_json(_candidates_path(id_), {}).get(sku, {}).get("page")
    if not page or not page.startswith("http"):
        raise ValueError(f"{sku}: no source page in cache/candidates/{id_}.json; pass --page URL")
    out_dir = paths.CACHE / "gallery"
    out_dir.mkdir(parents=True, exist_ok=True)
    index_path = out_dir / "gallery.json"
    index = {k: v for k, v in _load_json(index_path, {}).items() if v.get("sku") != sku}
    for old in out_dir.glob(f"{sku}_*"):
        old.unlink()
    exclude = sorted(bad_md5s() | ({md5_file(_abs(current[0]))} if current and _abs(current[0]).exists() else set()))
    keys = [sku, *_aliases(cat, sku)]
    job = {"mode": "gallery", "items": [{"sku": sku, "keys": keys, "urls": [page]}], "out": str(out_dir),
           "junk_re": GALLERY_JUNK_RE, "bad_md5": exclude, "max": 8, "min_bytes": 15000}
    result = sources.run_helper("gallery.mjs", job, cmd=cmd)
    files = []
    for res in result.get("results", []):
        for img in res.get("images", []):
            name = Path(img["path"]).name
            index[name] = {"sku": sku, "page": res.get("page", page), "url": img["url"]}
            files.append(out_dir / name)
    atomic_write(index_path, dump_json(index))
    return files


def _sheet_files(id_, mode):
    cat = catalog.load(id_)
    skus = set(_family_skus(cat))
    if mode == "all":
        return [_abs(f) for s in _family_skus(cat) for f in _images_of(cat, s) if _abs(f).exists()]
    folder = paths.CACHE / mode
    index = _load_json(folder / f"{mode}.json", {})
    return [folder / name for name, e in sorted(index.items()) if e.get("sku") in skus and (folder / name).exists()]


def sheet(id_, mode="review"):
    from PIL import Image, ImageDraw

    if mode not in ("review", "gallery", "all"):
        raise ValueError(f"unknown sheet mode {mode!r}")
    files = _sheet_files(id_, mode)
    if not files:
        raise ValueError(f"no {mode} images for {id_}")
    out_dir = paths.CACHE / "sheets"
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob(f"{id_}-{mode}-*.jpg"):
        old.unlink()
    t, c, r = _SHEET_T, _SHEET_C, _SHEET_R
    per = c * r
    sheets, index = [], {}
    for start in range(0, len(files), per):
        sh = Image.new("RGB", (c * t, r * (t + 18)), "white")
        draw = ImageDraw.Draw(sh)
        for i, f in enumerate(files[start:start + per]):
            n = start + i + 1
            index[str(n)] = str(f)
            x, y = (i % c) * t, (i // c) * (t + 18)
            try:
                with Image.open(f) as im:
                    im = im.convert("RGB")
                    im.thumbnail((t, t))
                    sh.paste(im, (x + (t - im.width) // 2, y + (t - im.height) // 2))
            except OSError:
                pass
            draw.text((x + 2, y + t + 2), f"{n} {f.name}"[:28], fill="red")
        out = out_dir / f"{id_}-{mode}-{start // per + 1}.jpg"
        sh.save(out, quality=80)
        sheets.append(out)
    atomic_write(out_dir / f"{id_}-{mode}.json", dump_json(index))
    return sheets


def _handler(fn):
    def run(args):
        try:
            fn(args)
        except (sources.FetchError, ValueError, FileNotFoundError, catalog.CatalogError) as exc:
            print(f"error: {exc}")
            return 1
        return 0
    return run


def _print_fetch(summary):
    for sku in summary["accepted"]:
        print(f"accepted {sku}")
    for f in summary["review"]:
        print(f"review {f}")
    if summary.get("stopped") == "verify":
        print("stopped at a verification page — run `spy.py browser open <url>` and rerun fetch")


def register(subparsers):
    p = subparsers.add_parser("photos", help="photo candidates, fetch, gallery, contact sheets, accept/reject")
    sub = p.add_subparsers(dest="photos_cmd", required=True)

    cp = sub.add_parser("candidates", help="build cache/candidates/<ID>.json for rows without a photo")
    cp.add_argument("id")
    cp.add_argument("--sku", action="append", help="limit to these SKUs (repeatable)")
    cp.add_argument("--add", action="append", default=[], metavar="SKU=URL", help="extra candidate URL (repeatable)")
    cp.set_defaults(func=_handler(lambda a: print(candidates(a.id, a.sku, a.add))))

    fp = sub.add_parser("fetch", help="visit pending candidates in the browser; auto-accept verified finds")
    fp.add_argument("id")
    fp.set_defaults(func=_handler(lambda a: _print_fetch(fetch(a.id))))

    gp = sub.add_parser("gallery", help="download every gallery image of a SKU's source page to cache/gallery/")
    gp.add_argument("id")
    gp.add_argument("--sku", required=True)
    gp.add_argument("--page")
    gp.set_defaults(func=_handler(lambda a: [print(f) for f in gallery(a.id, a.sku, a.page)]))

    sp = sub.add_parser("sheet", help="numbered contact sheets in cache/sheets/")
    sp.add_argument("id")
    mode = sp.add_mutually_exclusive_group()
    for m in ("review", "gallery", "all"):
        mode.add_argument(f"--{m}", dest="mode", action="store_const", const=m)
    sp.set_defaults(mode="review", func=_handler(lambda a: [print(f) for f in sheet(a.id, a.mode)]))

    ap = sub.add_parser("accept", help="copy a photo into Catalogs/images/<ID>/ and the row's image cell")
    ap.add_argument("id")
    ap.add_argument("sku")
    ap.add_argument("file")
    ap.add_argument("--extra", action="store_true", help="add as an extra photo (<SKU>_2)")
    ap.add_argument("--replace", action="store_true", help="replace the existing main photo")
    ap.add_argument("--page", help="source page, kept in cache/candidates/ for photos gallery")
    ap.set_defaults(func=_handler(lambda a: print(accept(
        a.id, a.sku, a.file, extra=a.extra, replace=a.replace, page=a.page))))

    rp = sub.add_parser("reject", help="add a file's md5 to data/bad_md5.txt")
    rp.add_argument("file")
    rp.set_defaults(func=_handler(lambda a: print(reject(a.file))))
