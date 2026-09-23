// Shared plumbing for browser/*.mjs helpers: job/result I/O, Chrome profile, verification
// detection and exit-code mapping. lib/sources.py is the only caller of these scripts.
import { chromium } from 'playwright-core';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
export const TOOLS_DIR = path.resolve(HERE, '..');
export const PROFILE_DIR = path.join(TOOLS_DIR, '.profiles', 'main');

export const VERIFY_RE = /moment|verif|attention required/i;

export class VerificationError extends Error {
  constructor(title) {
    super(`verification page detected: ${title}`);
    this.name = 'VerificationError';
  }
}

export function readJob() {
  const jobPath = process.argv[2];
  if (!jobPath) {
    console.error('usage: node <script> <job.json>');
    process.exit(1);
  }
  return { job: JSON.parse(fs.readFileSync(jobPath, 'utf8')), jobPath };
}

export function writeResult(job, data) {
  fs.writeFileSync(job.result, JSON.stringify(data, null, 1));
}

// Rate limiting: jittered delay, >= 4s, between page loads.
export function jitterDelay(base = 4000, spread = 1500) {
  return base + Math.random() * spread;
}

export async function launch() {
  return chromium.launchPersistentContext(PROFILE_DIR, {
    channel: 'chrome',
    headless: false,
    args: ['--disable-blink-features=AutomationControlled'],
  });
}

function classifyError(err) {
  if (err && err.name === 'VerificationError') return 2;
  const msg = String((err && err.message) || err);
  if (/\b403\b|forbidden/i.test(msg)) return 3;
  if (/timeout|timed out|net::|ENOTFOUND|ECONNRESET|ECONNREFUSED/i.test(msg)) return 4;
  return 1;
}

// Runs `task(page, job)`, writes its return value as the result JSON, and maps any thrown
// error (or VerificationError) to the exit codes lib/sources.py expects.
export async function run(name, task) {
  const { job } = readJob();
  let browser;
  try {
    browser = await launch();
    const page = browser.pages()[0] || (await browser.newPage());
    const result = await task(page, job);
    writeResult(job, result);
    process.exitCode = 0;
  } catch (err) {
    process.exitCode = classifyError(err);
    console.error(`${name}: ${(err && err.message) || err}`);
  } finally {
    if (browser) await browser.close().catch(() => {});
  }
}
