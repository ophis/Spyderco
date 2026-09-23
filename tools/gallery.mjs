import { chromium } from 'playwright-core';
import fs from 'fs';
import { execSync } from 'child_process';
const AUD=!!process.env.AUDIT; const OUT=AUD?'audit/':'/Users/francis/playground/Spyderco/Catalogs/images/';
const urls = JSON.parse(fs.readFileSync(process.argv[2] || 'urls.json'));
const RES=AUD?'audit.json':'imgs.json'; const res = fs.existsSync(RES) ? JSON.parse(fs.readFileSync(RES)) : {};
const save = () => { const cur = fs.existsSync(RES) ? JSON.parse(fs.readFileSync(RES)) : {}; for (const [k,v] of Object.entries(res)) if (!cur[k] || cur[k].file !== v.file) cur[k] = v; fs.writeFileSync(RES, JSON.stringify(cur,null,1)); };
const full = u => u
  .replace(/\/stencil\/[^/]+\//, '/stencil/original/')
  .replace(/_(\d+x\d*|\d*x\d+)(?=\.(jpe?g|png|webp)(\?|$))/i, '')
  .replace(/-\d{2,4}x\d{2,4}(?=\.(jpe?g|png|webp)(\?|$))/i, '')
  .replace(/\/fit-in\/\d+x\d+\//, '/')
  .replace(/[?&](width|w|h|height)=\d+/g, '').replace(/-td-(thumb|small|medium)\.jpg/i, '-td-large.jpg');
const b = await chromium.launchPersistentContext('./prof2', { channel: 'chrome', headless: false, args:['--disable-blink-features=AutomationControlled'] });
const p = b.pages()[0] || await b.newPage();
for (const [sku, cand] of Object.entries(urls)) {
 for (const url of [].concat(cand||[])) {
  if (!url || (res[sku]||{}).file) continue;
  try {
    await p.goto(url, { waitUntil: 'load', timeout: 60000 }).catch(()=>{});
    for (let i=0;i<40;i++){ await p.waitForTimeout(1000); const t=await p.title().catch(()=>'Loading'); if(!/^Loading|moment|verif/i.test(t)) break; }
    await p.waitForTimeout(3000);
    const alts = (JSON.parse(fs.readFileSync('alts.json'))[sku] || []);
    const txt = ((await p.title().catch(()=>'')) + ' ' + p.url() + ' ' + (await p.evaluate(()=>document.body.innerText).catch(()=>''))).toUpperCase();
     const verified = [sku, ...alts].some(a => txt.includes(a.slice(1).toUpperCase()));
    const keys = [sku, ...alts].map(k=>k.toLowerCase());
    const cands = await p.evaluate((keys) => {
      const out = [];
      for (const m of document.querySelectorAll('meta[property="og:image"], meta[property="og:image:secure_url"], meta[name="twitter:image"], link[rel="image_src"]')) { const v = m.content || m.href; if (v) out.push(new URL(v, location.href).href); }
      try { for (const s of document.querySelectorAll('script[type="application/ld+json"]')) { const j = JSON.parse(s.textContent); for (const o of [].concat(j['@graph']||j)) { const im = o && o.image; for (const x of [].concat(im||[])) { const v = typeof x === 'string' ? x : x && x.url; if (v) out.push(new URL(v, location.href).href); } } } } catch(e) {}
      const attrs = ['data-zoom-image','data-image-gallery-zoom-image-url','data-large_image','data-src','data-zoom','href','src'];
      for (const e of document.querySelectorAll('img, a')) for (const a of attrs) { const v = a==='src' ? (e.currentSrc||e.src) : a==='href' ? e.href : e.getAttribute(a); if (v && /\.(jpe?g|png|webp)(\?|$)/i.test(v) && keys.some(k => v.toLowerCase().includes(k))) out.push(new URL(v, location.href).href); }
      return out;
    }, keys);
    const seen = new Set(); const list = [];
    for (const c of cands) { const f = full(c); const key = f.split('?')[0].replace(/__\d+\.\d+/, ''); if (!seen.has(key) && !/logo|icon|badge|sprite|payment|flag|attributes|placeholder|maintenance|social|share|og-image|coming|boker|hand-tools|seedprod|no-?image|default|coming-?soon|blank/i.test(f)) { seen.add(key); list.push(f); } }
    const files = []; const tmp = [];
    for (const u of list.slice(0, 8)) {
      let r; try { r = await b.request.get(u, { headers: { Referer: url }, timeout: 90000 }); } catch(e) { continue; }
      const ct = r.headers()['content-type'] || ''; if (!r.ok() || !ct.startsWith('image')) continue;
      const ext = ct.includes('png') ? 'png' : ct.includes('webp') ? 'webp' : 'jpg';
      const body = await r.body(); const h = (await import('crypto')).createHash('md5').update(body).digest('hex'); if ((fs.existsSync('bad_md5.txt') ? fs.readFileSync('bad_md5.txt','utf8') : '').includes(h)) continue; const t = `tmpimg/${sku}_${tmp.length}.${ext}`; fs.mkdirSync('tmpimg',{recursive:true}); fs.writeFileSync(t, body); tmp.push({t,ext,u});
    }
    if (tmp.length) {
      const info = execSync('venv/bin/python pick.py ' + tmp.map(x=>x.t).join(' ')).toString().trim().split('\n').map(l=>l.split(' '));
      const all = tmp.map((x,i)=>({...x, bg: info[i][1], w: +info[i][2], ar: +info[i][3]})).filter(x=>x.w>=200 && x.ar<=2.2 && x.ar>=0.4);
      const big = all.filter(x=>x.w>=600);
      const best = big.find(x=>x.bg==='WHITE') || big[0] || [...all].sort((a,b)=>b.w-a.w)[0];
      if (best && !verified) { fs.mkdirSync('review',{recursive:true}); fs.copyFileSync(best.t, 'review/' + sku + '.' + best.ext); const rv = fs.existsSync('review.json') ? JSON.parse(fs.readFileSync('review.json')) : {}; rv[sku] = { file: 'review/' + sku + '.' + best.ext, page: url, url: best.u, w: best.w, bg: best.bg }; fs.writeFileSync('review.json', JSON.stringify(rv,null,1)); console.log(sku, 'REVIEW', url); }
      else if (best) { const fam = sku.match(/^C\d+/)[0]; fs.mkdirSync(OUT + fam, {recursive:true}); const name = fam + '/' + sku + '.' + best.ext; fs.copyFileSync(best.t, OUT + name); files.push('images/' + name); list[0] = best.u; console.log(sku, 'bg', best.bg, best.w); }
      for (const x of tmp) fs.unlinkSync(x.t);
    }
    if (files.length) { res[sku] = { file: files[0], files, url: list[0], src: new URL(url).hostname, page: url }; save(); }
    console.log(sku, files.length ? 'OK ' + files.length : 'NONE', url);
  } catch(e) { console.log(sku, 'ERR', e.message.slice(0,80)); }
  await p.waitForTimeout(4000 + Math.random()*3000);
 }
}
await b.close();
if (!AUD) console.log(execSync('python3 final.py && python3 gen2.py').toString());
