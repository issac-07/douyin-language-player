// Read-only check of the official public page in a fresh Edge profile.
// No user profile/cookies, stealth flags, challenge solver or account interaction.
import { chromium } from '@playwright/test';
import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const input = new URL(process.argv[2]);
if (input.origin !== 'https://www.douyin.com' || !/^\/video\/[0-9]{10,24}$/.test(input.pathname) || input.search || input.hash) {
  throw new Error('Use a canonical public Douyin video URL.');
}
const browser = await chromium.launch({ channel: 'msedge', headless: true });
const responses = [];
const hosts = new Set();
let requestedMetadata = null;
try {
  const page = await browser.newPage();
  page.on('request', (request) => { try { hosts.add(new URL(request.url()).hostname); } catch {} });
  page.on('response', (response) => {
    const url = new URL(response.url());
    const type = response.request().resourceType();
    if (type === 'document' || type === 'media' || url.pathname === '/aweme/v1/web/aweme/detail/') {
      responses.push({ host: url.hostname, endpoint: type === 'media' ? 'media' : type === 'document' ? 'page' : 'web_detail_api', status: response.status() });
    }
    if (['www.douyin.com', 'www-hj.douyin.com'].includes(url.hostname) && url.pathname === '/aweme/v1/web/aweme/detail/' && response.status() === 200) {
      void response.json().then((body) => { const detail = body.aweme_detail; if (String(detail?.aweme_id) === input.pathname.split('/').at(-1)) requestedMetadata = { video_id: String(detail.aweme_id), duration: detail.video?.duration, width: detail.video?.width, height: detail.video?.height }; }).catch(() => {});
    }
  });
  let navigationError = null;
  try {
    await page.goto(input.href, { waitUntil: 'domcontentloaded', timeout: 25_000 });
    await page.waitForTimeout(12_000);
  } catch (error) { navigationError = error.name; }
  const videos = await page.locator('video').evaluateAll((items) => items.map((video) => ({ readyState: video.readyState,
    duration: Number.isFinite(video.duration) ? video.duration : null, width: video.videoWidth, height: video.videoHeight })));
  const report = { tested_at: new Date().toISOString(), browser: 'fresh Microsoft Edge', real_network: true,
    canonical_url: input.href, responses, videos, requested_metadata: requestedMetadata, asset_hosts: [...hosts].filter(Boolean), navigation_error_type: navigationError,
    no_account_or_cookie_import: true, challenge_solver_used: false };
  const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
  const output = path.join(root, 'data/validation/phase4-debug/public-edge-page.json');
  await mkdir(path.dirname(output), { recursive: true });
  await writeFile(output, JSON.stringify(report, null, 2));
  console.log(JSON.stringify(report));
} finally { await browser.close(); }
