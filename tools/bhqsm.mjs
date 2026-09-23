import { chromium } from 'playwright-core';
import fs from 'fs';
const b = await chromium.launchPersistentContext('./prof', { channel: 'chrome', headless: false, args:['--disable-blink-features=AutomationControlled'] });
const p = b.pages()[0] || await b.newPage();
await p.goto('https://www.bladehq.com/', { waitUntil: 'load', timeout: 60000 }).catch(()=>{}); await p.waitForTimeout(4000);
const get = async u => p.evaluate(async u => { const r = await fetch(u); return r.status+'\n'+(await r.text()); }, u);
const idx = await get('/sitemap.xml'); console.log(idx.slice(0,600));
const subs = [...idx.matchAll(/<loc>([^<]+)<\/loc>/g)].map(m=>m[1]);
let all=[];
for (const s of subs.slice(0,60)) { const x = await get(s); const l=[...x.matchAll(/<loc>([^<]+)<\/loc>/g)].map(m=>m[1]); all.push(...l); }
fs.writeFileSync('bhq_sitemap.txt', all.join('\n')); console.log('urls', all.length);
await b.close();
