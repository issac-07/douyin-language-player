// Opt-in verification of the NORMAL app and REAL downloader in a fresh Edge profile.
import { chromium, expect } from '@playwright/test';
import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const url = process.argv[2];
if (!url) throw new Error('Usage: node scripts/validate-live-import.mjs <authorized-public-Douyin-URL>');
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const output = path.join(root, 'data/validation');
await mkdir(output, { recursive: true });
const browser = await chromium.launch({ channel: 'msedge', headless: true });
try {
  const page = await browser.newPage({ baseURL: 'http://127.0.0.1:5173', viewport: { width: 1440, height: 1050 } });
  const errors = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await page.goto('http://127.0.0.1:5173');
  const health = await page.request.get('/api/health').then((response) => response.json());
  expect(health.phase).toBe(4);
  await page.getByLabel('Douyin link or sharing text').fill(url);
  const submitted = page.waitForResponse((response) => response.url().endsWith('/api/imports/douyin') && response.request().method() === 'POST');
  await page.getByRole('button', { name: 'Import link', exact: true }).click();
  let job = await (await submitted).json();
  await expect.poll(async () => {
    job = await page.request.get(`/api/imports/${job.id}`).then((response) => response.json());
    return ['completed', 'failed', 'cancelled'].includes(job.status);
  }, { timeout: 150_000 }).toBe(true);
  const status = page.getByLabel('Douyin import status');
  if (job.status === 'failed') {
    await expect(status).toContainText(job.error);
    await expect(page.getByRole('button', { name: 'Import a local MP4 instead', exact: true })).toBeVisible();
  } else if (job.status === 'completed') {
    await expect(page.locator('video')).toHaveCount(1);
    await expect.poll(() => page.locator('video').evaluate((media) => media.readyState)).toBeGreaterThanOrEqual(2);
  }
  expect(errors).toEqual([]);
  await page.screenshot({ path: path.join(output, 'phase4-edge-live-user-link.png') });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: path.join(output, 'phase4-edge-live-user-link-mobile.png') });
  const report = { tested_at: new Date().toISOString(), real_network: true, browser: 'Microsoft Edge',
    backend_phase: health.phase, job, page_errors: errors, responsive_width_check: true };
  await writeFile(path.join(output, 'phase4-edge-live-user-link.json'), JSON.stringify(report, null, 2), 'utf8');
  console.log(JSON.stringify({ ui_verification: 'passed', import_status: job.status, error_code: job.error_code,
    canonical_url: job.canonical_url, elapsed_seconds: job.elapsed_seconds, page_errors: errors }));
} finally { await browser.close(); }
