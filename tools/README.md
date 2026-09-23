# tools

Scripts that build `Catalogs/*.md` and download `Catalogs/images/`. Run from this folder.

Setup: `npm i` (playwright-core, uses installed Chrome) and `python3 -m venv venv && venv/bin/pip install pillow`.

- Rebuild lists: `python3 final.py && python3 gen2.py` (C81/C223 from `merged.json`; C101/C229/C36 from `rows_*.json`). Image links come from `imgs.json`.
- Download images: `node gallery.mjs <candidates.json>` where the JSON is `{"SKU": ["product page url", ...]}`. Accepts a page only if it shows the SKU (or an alt from `alts.json`); otherwise saves to `review/` for manual check. Prefers white-background open+closed shots; skips hashes in `bad_md5.txt`.
- spyderco.com official images: `node spyfix.mjs <SKU...>` prints the `_Both` image URL per SKU.
- Dealer sitemap index: `python3 smap.py <domain...>` → `smap.json` (gitignored; Blade HQ via `node bhqsm.mjs` → `bhq_sitemap.txt`).
- `prof/`, `prof2/`: Chrome profiles holding site verification cookies (gitignored). KnifeCenter may need `node kcopen.mjs` to clear its check by hand.
