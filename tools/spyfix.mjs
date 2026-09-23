import { chromium } from 'playwright-core';
import fs from 'fs';
const site = JSON.parse(fs.readFileSync('site_all.json'));
const want = process.argv.slice(2);
const b = await chromium.launchPersistentContext('./prof', { channel: 'chrome', headless: false, args:['--disable-blink-features=AutomationControlled'] });
const p = b.pages()[0] || await b.newPage();
await p.goto('https://spyderco.com/', { waitUntil: 'domcontentloaded' }); await p.waitForTimeout(3000);
for (const s of site) {
  if (!s.skus.some(x=>want.includes(x.split(' :: ')[0]))) continue;
  const d = await p.evaluate(async h => (await fetch('/products/'+h+'.js')).json(), s.handle);
  for (const v of d.variants) if (want.includes(v.sku)) {
    const imgs = d.images.map(u=>(u.startsWith('//')?'https:':'')+u.split('?')[0]);
    const both = imgs.find(u=>u.split('/').pop().toUpperCase().startsWith(v.sku.toUpperCase()+'_') && /both/i.test(u)) || imgs.find(u=>u.split('/').pop().toUpperCase().startsWith(v.sku.toUpperCase()) && /both/i.test(u)) || imgs.find(u=>/both/i.test(u) && d.variants.length===1) || (v.featured_image && ('https:'+v.featured_image.src.replace(/^https?:/,'')).split('?')[0]) || imgs[0];
    console.log(v.sku, both, 'https://spyderco.com/products/'+s.handle);
  }
}
await b.close();
