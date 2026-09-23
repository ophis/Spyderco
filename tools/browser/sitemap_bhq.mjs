// Ported from reference bhqsm.mjs: Blade HQ blocks plain HTTP sitemap fetches, so this
// crawls sitemap.xml (and its sub-sitemaps) through fetch() inside a real Chrome page.
// Job: {domain}. Result: {urls}.
import { run, jitterDelay, VERIFY_RE, VerificationError } from './common.mjs';

async function fetchViaPage(page, url) {
  return page.evaluate(async (u) => {
    const r = await fetch(u);
    return { status: r.status, body: await r.text() };
  }, url);
}

function locsOf(text) {
  return [...text.matchAll(/<loc>([^<]+)<\/loc>/g)].map((m) => m[1]);
}

async function crawl(page, domain) {
  const title = await page.title().catch(() => '');
  if (VERIFY_RE.test(title)) throw new VerificationError(title);

  const idx = await fetchViaPage(page, `https://www.${domain}/sitemap.xml`);
  if (idx.status === 403) throw new Error('403 blocked fetching sitemap.xml');
  if (idx.status !== 200) throw new Error(`sitemap.xml HTTP ${idx.status}`);

  const subs = locsOf(idx.body).slice(0, 60);
  const urls = [];
  for (const sub of subs) {
    await page.waitForTimeout(jitterDelay());
    const x = await fetchViaPage(page, sub);
    if (x.status === 200) urls.push(...locsOf(x.body));
  }
  return { urls };
}

await run('sitemap_bhq', async (page, job) => {
  await page
    .goto(`https://www.${job.domain}/`, { waitUntil: 'load', timeout: 60000 })
    .catch(() => {});
  await page.waitForTimeout(jitterDelay());
  return crawl(page, job.domain);
});
