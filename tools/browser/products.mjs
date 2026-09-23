// Ported from reference allsku.mjs: paginate spyderco.com's /products.json through Chrome
// (avoids the anti-bot check a plain HTTP fetch would hit) and hand every raw product back
// to lib/sources.parse_products. Job: {url}. Result: the raw product list.
import { run, jitterDelay, VERIFY_RE, VerificationError } from './common.mjs';

async function fetchPage(page, n) {
  return page.evaluate(async (i) => {
    const r = await fetch(`/products.json?limit=250&page=${i}`);
    return { status: r.status, body: await r.text() };
  }, n);
}

async function fetchAllProducts(page) {
  const title = await page.title().catch(() => '');
  if (VERIFY_RE.test(title)) throw new VerificationError(title);

  const products = [];
  for (let i = 1; i <= 40; i++) {
    if (i > 1) await page.waitForTimeout(jitterDelay());
    const { status, body } = await fetchPage(page, i);
    if (status === 403) throw new Error('403 blocked fetching products.json');
    if (status !== 200) throw new Error(`products.json HTTP ${status} on page ${i}`);
    const data = JSON.parse(body);
    if (!data.products || !data.products.length) break;
    products.push(...data.products);
  }
  return products;
}

await run('products', async (page, job) => {
  await page.goto(job.url || 'https://www.spyderco.com/', { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.waitForTimeout(jitterDelay());
  return fetchAllProducts(page);
});
