import { chromium } from 'playwright-core';
import fs from 'fs';
const OUT='/Users/francis/playground/Spyderco/Catalogs/images/';
const skus = fs.readFileSync('skus.txt','utf8').trim().split('\n');
const site = JSON.parse(fs.readFileSync('site_all.json'));
const res = fs.existsSync('imgs.json') ? JSON.parse(fs.readFileSync('imgs.json')) : {};
const save = () => { const cur = JSON.parse(fs.readFileSync('imgs.json')); for (const [k,v] of Object.entries(res)) if (!cur[k] || cur[k].file !== v.file) cur[k] = v; fs.writeFileSync('imgs.json', JSON.stringify(cur,null,1)); };
const b = await chromium.launchPersistentContext('./prof', { channel: 'chrome', headless: false, args:['--disable-blink-features=AutomationControlled'] });
const p = b.pages()[0] || await b.newPage();
async function dl(sku, url, src, page) {
  let r; try { r = await b.request.get(url, { headers: { Referer: page || url }, timeout: 90000 }); await r.body(); } catch(e) { console.log(sku,'DLFAIL timeout',url); return false; }
  const ct = r.headers()['content-type'] || '';
  if (!r.ok() || !ct.startsWith('image')) { console.log(sku, 'DLFAIL', r.status(), url); return false; }
  const ext = ct.includes('png') ? 'png' : ct.includes('webp') ? 'webp' : 'jpg';
  const fam = sku.match(/^C\d+/)[0]; fs.mkdirSync(OUT + fam, {recursive:true}); fs.writeFileSync(OUT + fam + '/' + sku + '.' + ext, await r.body());
  res[sku] = { file: 'images/' + fam + '/' + sku + '.' + ext, url, src, page }; save();
  console.log(sku, 'OK', src); return true;
}
await p.goto('https://spyderco.com/', { waitUntil: 'domcontentloaded' }); await p.waitForTimeout(3000);
for (const [k,v] of Object.entries(res)) if (!v.file && v.url) { delete res[k]; }
for (const s of site) {
  let d; try { d = await p.evaluate(async h => (await fetch('/products/'+h+'.js')).json(), s.handle); } catch(e) { console.log(s.handle,'ERR spy'); continue; }
  for (const v of d.variants) if (v.sku && skus.includes(v.sku) && !res[v.sku]) {
    let src = (v.featured_image && v.featured_image.src) || d.images[0];
    if (src) await dl(v.sku, (src.startsWith('//')?'https:':'')+src.split('?')[0], 'spyderco.com', 'https://spyderco.com/products/'+s.handle);
  }
}
for (const sku of (process.env.KC ? skus : [])) {
  if (res[sku]) continue;
  const u = 'https://www.knifecenter.com/item/SP'+sku.slice(1);
  for (let t=0;t<2;t++) try {
    await p.goto(u, { waitUntil: 'load', timeout: 60000 }); await p.waitForTimeout(2500);
    const img = await p.$$eval('img,a', is=>is.map(i=>i.currentSrc||i.src||i.href).filter(s=>s&&/^https:\/\/pics\.knifecenter\.com\/(fit-in\/1500x1500\/)?knifecenter\/spyderco-knives\/images\//.test(s))[0]);
    const ttl = await p.title();
    if (ttl === 'knifecenter.com' || /verif/i.test(ttl)) { console.log(sku,'BLOCKED'); await b.close(); process.exit(2); }
    if (img) await dl(sku, img.replace('/fit-in/1500x1500',''), 'knifecenter.com', p.url()); else console.log(sku,'NONE', ttl);
    await p.waitForTimeout(6000 + Math.random()*4000);
    break;
  } catch(e){ console.log(sku,'ERR',e.message.slice(0,80)); await p.waitForTimeout(5000); }
}
await b.close();
import('child_process').then(cp=>console.log(cp.execSync('python3 final.py && python3 gen2.py').toString()));
