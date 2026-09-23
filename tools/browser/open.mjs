// `spy.py browser open <url>`: opens a URL in the tool's Chrome profile so a human can clear
// a verification check by hand, then waits (up to 10 min) for the title to stop matching
// VERIFY_RE before closing. Ported from reference kcopen.mjs. Job: {url}. Result: {url, title}.
import { readJob, writeResult, launch, VERIFY_RE } from './common.mjs';

const { job } = readJob();
let browser;
try {
  browser = await launch();
  const page = browser.pages()[0] || (await browser.newPage());
  await page.bringToFront();
  await page.goto(job.url, { waitUntil: 'load', timeout: 60000 });

  let title = await page.title().catch(() => '');
  for (let i = 0; i < 600 && VERIFY_RE.test(title); i++) {
    await page.waitForTimeout(1000);
    title = await page.title().catch(() => '');
  }
  await page.waitForTimeout(2000);

  writeResult(job, { url: job.url, title });
  process.exitCode = 0;
} catch (err) {
  const msg = String((err && err.message) || err);
  console.error(`open: ${msg}`);
  process.exitCode = /\b403\b|forbidden/i.test(msg) ? 3 : 4;
} finally {
  if (browser) await browser.close().catch(() => {});
}
