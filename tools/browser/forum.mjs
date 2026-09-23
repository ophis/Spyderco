// Reads post 1 of the Spyderco forum Sprints/Exclusives thread (phpBB3 prosilver markup:
// .post .postbody .content). Job: {url}. Result: {text}, handed to lib/sources.parse_forum.
import { run, jitterDelay, VERIFY_RE, VerificationError } from './common.mjs';

const CONTENT_SELECTORS = ['.post .postbody .content', '.post .content', 'div[id^="p"] .content'];

async function firstPostText(page) {
  for (const selector of CONTENT_SELECTORS) {
    const locator = page.locator(selector).first();
    if (await locator.count()) {
      const text = await locator.innerText();
      if (text && text.trim()) return text;
    }
  }
  throw new Error('could not locate post 1 content');
}

await run('forum', async (page, job) => {
  await page.goto(job.url, { waitUntil: 'load', timeout: 60000 });
  const title = await page.title().catch(() => '');
  if (VERIFY_RE.test(title)) throw new VerificationError(title);
  await page.waitForTimeout(jitterDelay());
  return { text: await firstPostText(page) };
});
