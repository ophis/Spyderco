# Review points

Checklist for every model list in `Catalogs/`, and for every new model line fetched.

Run `python3 tools/spy.py verify` before committing catalog changes.

## 1. Model data

- [ ] Every variant from the Spydiewiki variation table is present; original generation included (e.g. C81 Para-Military, C85 Yojimbo), not only the current one.
- [ ] Cross-checked against spyderco.com listings and the forum [Sprints/Exclusives thread](https://forum.spyderco.com/viewtopic.php?f=2&t=90980); no forum entry for this model is missing.
- [ ] Model numbers use the spelling spyderco.com or retailers use (wiki often drops the `P`, e.g. `C81BK2` → `C81PBK2`); the wiki spelling goes in **Alt SKU**.
- [ ] Watch for wiki typos (`C81FCGR2` → `C81CFGR2`) and swapped letters (`C101GP2OR` → `C101GPOR2`).
- [ ] Two rows with the same model number are only allowed for steel generations of the same model (e.g. C101GP2 154CM → S30V → MagnaMax); otherwise one is a wrong SKU.
- [ ] Lightweight (FRN/FRCP) variants are in their own section.
- [ ] Type is 🟥 Sprint Run / 🟦 named dealer exclusive / 🟪 only when no dealer is known. "Exclusive" without a dealer name is a gap to research.
- [ ] Dealer names are normalized (Blade HQ, KnifeCenter, St. Nick's Knives, DLT Trading, …).
- [ ] Dates: month + year, no launch times/time zones; unknown year marked clearly.
- [ ] Qty is a number or short range; notes like "(1st run)" belong in Type/notes, not Qty.
- [ ] Header links the model's Spydiewiki page and the forum thread; no dead forum links.
- [ ] README table lists the file with the correct variant count.

## 2. Photos

Preference: **open and folded (clip side) in one photo** → **open + folded clip side as two photos** (`SKU` + `SKU_2`) → best available photo of the exact variant. Lower quality beats no photo.

- [ ] Source order: spyderco.com (`_Both` image) → the exclusive dealer's own site → other retailers → last resort: any photo of the exact variant that can be found online.
- [ ] The photo is the exact variant: handle material/color, steel stamp, **blade finish (satin vs black DLC/TiCN)**, edge (Plain / Combo / SpyderEdge), blade shape (clip point / Wharncliffe / tanto). Retailers often carry satin and black-blade pages side by side — check the page title.
- [ ] Page shows the model number (or an Alt SKU); otherwise inspect by eye before accepting.
- [ ] Not a logo, banner, "coming soon", "page not found", placeholder, maintenance or related-product thumbnail.
- [ ] The folded photo shows the clip side.
- [ ] White background preferred; no promo text.
- [ ] Never replace an accurate photo while filling gaps; when replacing a main photo, use a new filename (viewers cache by path).
- [ ] No broken image links in the `.md` files.

## 3. Open issues in the current docs

- **No photo (3):** C101GPPN2, C223KBPI, C85GBK.
- **Type without a dealer (17):** C101GP2, C101GPPN2, C101KBPI, C223GPRD, C223KBPI, C36CFP, C36GPOR, C36GPLE, C36TIFP, C81GPORBK2, C81GPNP2, C81GPBKBS2, C81GPDGYS90V2, C81GBKRDMCBKP2, C81GPORRX1212, C81GPWCORRX1212, C81GPORRX121BK2. Several are known (e.g. C81GPORRX1212 / C81GPWCORRX1212 / C81GPORRX121BK2 = Cutlery Shoppe, C81GBKRDMCBKP2 = Crucible, C81GPBKBS2 = BayouShooter).
- **Dates with launch time/time zone (22):** e.g. C101GPRD2 "Jan. 15, 2019 @ 11AM CST", C81GPCB2 "Mar. 18, 2020 @ ~7AM PST (preorder)". Mixed month formats (Mar. / March / 03).
- **Date without year:** C36GBK "late 90s?".
- **Long Qty text (8):** C101GPRD2, C223GPBL, C81GBLM3902, C81GM4P2, C81GM4BKP2, C81GPTN2, C81GPDGYS90V2, C85CFP2.
- **Repeated model numbers:** C101 Manix 2 (C101GP2, C101GPS2, C101GPBBK2, C101GPSBBK2 — steel generations, OK), C229BMBNP (two KnifeCenter runs), C36G / C36GBK (steel generations), C36GPCMOBK2 (factory-seconds row).
- **Small main photos (<600 px, 14):** C101GPBL2, C101GPGY2, C101MBGP2, C101MGPBRBBK, C101POR2, C223GPODFDE, C81CFM4P2, C81GPBK, C81GPBN2, C81GPDGYS90V2, C85CF20CVP2, C85GM4P2, C85GM4PBK2, C85GPBNBK2.
- **Single photos:** roughly 100 models have one photo that may not show the folded clip side (dealer composites are not always detectable from the URL); needs a visual pass against the photo preference.
- **Weaker matches to double-check:** C36GBK (ATS-34 not confirmable from photo), C101GPRBK2 (listing text described another Manix), C81GPBK and C81GSBK (small, first-gen shape not verified).
