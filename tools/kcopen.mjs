import { chromium } from 'playwright-core';
const b = await chromium.launchPersistentContext('./prof', { channel: 'chrome', headless: false, args:['--disable-blink-features=AutomationControlled'] });
const p = b.pages()[0] || await b.newPage();
await p.bringToFront();
await p.goto('https://www.knifecenter.com/item/SP81CFP2', { waitUntil: 'load', timeout: 60000 });
for (let i=0;i<600;i++){ await p.waitForTimeout(1000); const t=await p.title().catch(()=>''); if (t && t!=='knifecenter.com' && !/verif/i.test(t)) { console.log('PASSED', t); break; } }
await p.waitForTimeout(3000); await b.close();
