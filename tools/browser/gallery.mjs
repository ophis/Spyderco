// `spy.py photos fetch|gallery`: ported from reference gallery.mjs (mode "best") and galall.mjs
// (mode "gallery"). Visits each item's candidate URLs, downloads candidate images into job.out and
// reports them; lib/images.py measures, chooses and accepts. Regexes (junk_re, verify_re) come from
// lib/images.py. Job: {mode, items:[{sku, keys, urls, verify_re}], out, junk_re, bad_md5, max, min_bytes}.
// Result: {results:[{sku, url, page, status: ok|none|search|verify|error, verified, images:[{path, url}], error}], stopped}.
import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { run, jitterDelay, VERIFY_RE } from './common.mjs';

const IMG_RE = /\.(jpe?g|png|webp)(\?|$)/i;
const SEARCH_PAGE_RE = /[/?](search|find)[/?=]/i;

// Strip CDN resize parameters to reach the original image.
export const full = (u) => u
  .replace(/\/stencil\/[^/]+\//, '/stencil/original/')
  .replace(/_(\d+x\d*|\d*x\d+)(?=\.(jpe?g|png|webp)(\?|$))/i, '')
  .replace(/-\d{2,4}x\d{2,4}(?=\.(jpe?g|png|webp)(\?|$))/i, '')
  .replace(/\/fit-in\/\d+x\d+\//, '/')
  .replace(/\/images\/products\/(big|small)\//, '/images/products/orig/')
  .replace(/[?&](width|w|h|height)=\d+/g, '')
  .replace(/-td-(thumb|small|medium)\.jpg/i, '-td-large.jpg');

// Mode "best": normalise, drop junk, dedupe by path (ignoring Shopify-style __N.N version tags).
export function bestCandidates(raw, junkRe) {
  const seen = new Set();
  const out = [];
  for (const c of raw) {
    const f = full(c);
    const key = f.split('?')[0].replace(/__\d+\.\d+/, '');
    if (seen.has(key) || junkRe.test(f)) continue;
    seen.add(key);
    out.push(f);
  }
  return out;
}

// Mode "gallery": everything on the page that looks like a product image of this listing.
export function galleryCandidates(raw, { keys, og, page, junkRe }) {
  const ogDir = og ? og.split('?')[0].replace(/[^/]+$/, '') : null;
  const bhq = (page.match(/--(\d+)$/) || [])[1];
  return [...new Set(raw.map(full))].filter((u) => {
    const l = u.toLowerCase();
    if (junkRe.test(l)) return false;
    return keys.some((k) => l.includes(k.toLowerCase())) || (ogDir && u.startsWith(ogDir))
      || (bhq && l.includes('bhq-' + bhq)) || /\/products\/|\/product\/|\/files\/|\/uploads\//.test(l);
  });
}

function extOf(ct) {
  return ct.includes('png') ? 'png' : ct.includes('webp') ? 'webp' : 'jpg';
}

async function waitReady(page) {
  for (let i = 0; i < 40; i++) {
    await page.waitForTimeout(1000);
    const t = await page.title().catch(() => 'Loading');
    if (!/^Loading|moment|verif/i.test(t)) break;
  }
  await page.waitForTimeout(3000);
}

async function collectBest(page, keys) {
  return page.evaluate((keys) => {
    const out = [];
    for (const m of document.querySelectorAll('meta[property="og:image"], meta[property="og:image:secure_url"], meta[name="twitter:image"], link[rel="image_src"]')) {
      const v = m.content || m.href;
      if (v) out.push(new URL(v, location.href).href);
    }
    for (const s of document.querySelectorAll('script[type="application/ld+json"]')) {
      try {
        const j = JSON.parse(s.textContent);
        for (const o of [].concat(j['@graph'] || j)) {
          for (const x of [].concat((o && o.image) || [])) {
            const v = typeof x === 'string' ? x : x && x.url;
            if (v) out.push(new URL(v, location.href).href);
          }
        }
      } catch (e) { /* malformed JSON-LD */ }
    }
    const attrs = ['data-zoom-image', 'data-image-gallery-zoom-image-url', 'data-large_image', 'data-src', 'data-zoom', 'href', 'src'];
    for (const e of document.querySelectorAll('img, a')) {
      for (const a of attrs) {
        const v = a === 'src' ? (e.currentSrc || e.src) : a === 'href' ? e.href : e.getAttribute(a);
        if (v && /\.(jpe?g|png|webp)(\?|$)/i.test(v) && keys.some((k) => v.toLowerCase().includes(k))) out.push(new URL(v, location.href).href);
      }
    }
    return out;
  }, keys.map((k) => k.toLowerCase()));
}

async function collectGallery(page) {
  const og = await page.$$eval('meta[property="og:image"]', (m) => m.map((x) => x.content)).catch(() => []);
  const all = await page.evaluate(() => {
    const o = [];
    const attrs = ['data-zoom-image', 'data-image-gallery-zoom-image-url', 'data-large_image', 'data-src', 'data-zoom', 'data-full', 'href', 'src', 'srcset'];
    for (const e of document.querySelectorAll('img,a,source')) {
      for (const a of attrs) {
        let v = a === 'src' ? (e.currentSrc || e.src) : a === 'href' ? e.href : e.getAttribute(a);
        if (!v) continue;
        if (a === 'srcset') v = v.split(',').pop().trim().split(' ')[0];
        if (/\.(jpe?g|png|webp)(\?|$)/i.test(v)) { try { o.push(new URL(v, location.href).href); } catch (e) { /* bad URL */ } }
      }
    }
    return o;
  });
  return { og: og[0], all };
}

// Downloads `urls` in order, keeping at most job.max files not in job.bad_md5 (nor duplicates).
async function download(request, urls, referer, sku, job, state) {
  const bad = new Set(job.bad_md5 || []);
  const saved = [];
  for (const u of urls) {
    if (saved.length >= (job.max || 8)) break;
    let r;
    try { r = await request.get(u, { headers: referer ? { Referer: referer } : {}, timeout: 90000 }); } catch (e) { continue; }
    const ct = r.headers()['content-type'] || '';
    if (!r.ok() || !ct.startsWith('image')) continue;
    const body = await r.body();
    if (body.length < (job.min_bytes || 0)) continue;
    const h = crypto.createHash('md5').update(body).digest('hex');
    if (bad.has(h)) continue;
    bad.add(h);
    fs.mkdirSync(job.out, { recursive: true });
    const file = path.join(job.out, `${sku}_${state.n++}.${extOf(ct)}`);
    fs.writeFileSync(file, body);
    saved.push({ path: file, url: u });
  }
  return saved;
}

async function visit(page, item, url, job, state) {
  const request = page.context().request;
  const verifyRe = new RegExp(item.verify_re, 'i');
  if (IMG_RE.test(url)) {
    const images = await download(request, [url], null, item.sku, { ...job, min_bytes: 0 }, state);
    return { page: url, status: images.length ? 'ok' : 'none', verified: verifyRe.test(url), images };
  }
  if (state.loaded) await page.waitForTimeout(jitterDelay());
  state.loaded = true;
  await page.goto(url, { waitUntil: 'load', timeout: 60000 }).catch(() => {});
  await waitReady(page);
  const title = await page.title().catch(() => '');
  if (VERIFY_RE.test(title)) return { page: page.url(), status: 'verify', verified: false, images: [] };
  if (SEARCH_PAGE_RE.test(page.url())) return { page: page.url(), status: 'search', verified: false, images: [] };
  const text = `${title} ${page.url()} ${await page.evaluate(() => document.body.innerText).catch(() => '')}`;
  const verified = verifyRe.test(text);
  const junkRe = new RegExp(job.junk_re, 'i');
  let urls;
  if (job.mode === 'gallery') {
    const { og, all } = await collectGallery(page);
    urls = galleryCandidates(all, { keys: item.keys, og, page: url, junkRe }).slice(0, 20);
  } else {
    urls = bestCandidates(await collectBest(page, item.keys), junkRe).slice(0, job.max || 8);
  }
  const images = await download(request, urls, url, item.sku, job, state);
  return { page: page.url(), status: images.length ? 'ok' : 'none', verified, images };
}

async function main(page, job) {
  const results = [];
  const state = { n: 0, loaded: false };
  for (const item of job.items) {
    for (const url of item.urls) {
      let res;
      try {
        res = await visit(page, item, url, job, state);
      } catch (err) {
        res = { page: url, status: 'error', verified: false, images: [], error: String((err && err.message) || err).slice(0, 200) };
      }
      results.push({ sku: item.sku, url, ...res });
      if (res.status === 'verify') return { results, stopped: 'verify' };
      if (job.mode === 'best' && res.verified && res.images.length) break;
    }
  }
  return { results, stopped: null };
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  await run('gallery', main);
}
