// Production fallback: normal official page in a disposable Edge session.
// Session cookies never leave this browser; no profile import or challenge solving.
import { chromium } from '@playwright/test';

const [canonical, proxy] = process.argv.slice(2);
const url = new URL(canonical);
if (url.origin !== 'https://www.douyin.com' || !/^\/video\/[0-9]{10,24}$/.test(url.pathname) || url.search || url.hash) process.exit(2);
if (!/^http:\/\/127\.0\.0\.1:[0-9]+$/.test(proxy)) process.exit(2);
let browser;
let cancelled = false;
const diagnostics = [];
process.stdin.setEncoding('utf8');
process.stdin.on('data', () => { cancelled = true; void browser?.close(); });
try {
  browser = await chromium.launch({ channel: 'msedge', proxy: { server: proxy, bypass: '<-loopback>' },
    args: ['--disable-quic', '--force-webrtc-ip-handling-policy=disable_non_proxied_udp'] });
  const context = await browser.newContext({ serviceWorkers: 'block', acceptDownloads: false });
  const page = await context.newPage();
  await page.route('**/*', async (route) => {
    const request = route.request();
    if (!request.url().startsWith('https://') || ['media', 'image', 'font'].includes(request.resourceType())) return route.abort();
    return route.continue();
  });
  const expected = url.pathname.split('/').at(-1);
  const metadata = new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('metadata_timeout')), 40_000);
    page.on('response', async (response) => {
      try {
        const endpoint = new URL(response.url());
        if (endpoint.protocol !== 'https:' || !(endpoint.hostname === 'douyin.com' || endpoint.hostname.endsWith('.douyin.com')) || endpoint.port || endpoint.pathname !== '/aweme/v1/web/aweme/detail/') return;
        if (diagnostics.length < 12) diagnostics.push({ host: endpoint.hostname, status: response.status() });
        if (response.status() !== 200) return;
        const body = await response.body();
        if (body.length > 16 * 1024 * 1024) return;
        const item = JSON.parse(body.toString('utf8')).aweme_detail;
        if (!item || String(item.aweme_id) !== expected) return;
        // Only data needed by the existing media parser crosses stdout. No headers/session fields.
        const detail = { aweme_id: item.aweme_id, desc: item.desc, video: item.video, is_live: item.is_live,
          author: { nickname: item.author?.nickname, unique_id: item.author?.unique_id },
          status: { is_private: item.status?.is_private, is_delete: item.status?.is_delete },
          hybrid_label: item.hybrid_label };
        clearTimeout(timer); resolve(detail);
      } catch { /* Ignore unrelated/incomplete responses without exposing their data. */ }
    });
  });
  // Navigation is ordinary website execution. No injection, cookies API or verification interaction.
  const navigation = page.goto(canonical, { waitUntil: 'domcontentloaded', timeout: 35_000 });
  const detail = await Promise.all([metadata, navigation]).then(([value]) => value);
  process.stdout.write(JSON.stringify({ status: 'ok', detail }));
} catch {
  process.stdout.write(JSON.stringify({ status: cancelled ? 'cancelled' : 'unavailable', diagnostics }));
} finally {
  await browser?.close().catch(() => {});
  process.stdin.pause();
}
