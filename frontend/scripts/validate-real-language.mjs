// Review the real video's already-computed OCR/language cache in Edge, without rerunning OCR.
import { spawn, spawnSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium, expect } from '@playwright/test';

const frontend = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const root = path.resolve(frontend, '..');
const library = path.resolve(process.argv[2] ?? path.join(root, 'data/validation/run-9cdaa450257e419290e5b2676e818075'));
const python = path.join(root, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
const children = [];
let browser;
let diagnostics = '';
function launch(command, args, options) {
  const process = spawn(command, args, { windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'], ...options });
  children.push(process);
  process.stdout.on('data', (value) => { diagnostics = (diagnostics + value.toString()).slice(-5000); });
  process.stderr.on('data', (value) => { diagnostics = (diagnostics + value.toString()).slice(-5000); });
  return process;
}
async function ready(url) {
  for (let count = 0; count < 100; count++) {
    try { if ((await fetch(url)).ok) return; } catch { /* Startup is asynchronous. */ }
    if (children.some((process) => process.exitCode !== null)) throw new Error(`Preview startup failed: ${diagnostics}`);
    await new Promise((resolve) => setTimeout(resolve, 200));
  }
  throw new Error(`Preview was not ready: ${diagnostics}`);
}
try {
  launch(python, ['-m', 'uvicorn', 'app.main:app', '--app-dir', 'backend', '--host', '127.0.0.1', '--port', '8012'], { cwd: root, env: { ...process.env, DLP_DATA_DIR: library, DLP_ALLOWED_ORIGINS: 'http://127.0.0.1:5175' } });
  launch(process.execPath, ['node_modules/vite/bin/vite.js', '--host', '127.0.0.1', '--port', '5175', '--strictPort'], { cwd: frontend, env: { ...process.env, DLP_API_URL: 'http://127.0.0.1:8012' } });
  await ready('http://127.0.0.1:8012/api/health');
  await ready('http://127.0.0.1:5175');
  browser = await chromium.launch({ channel: 'msedge', headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 960 } });
  const errors = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await page.goto('http://127.0.0.1:5175');
  await expect(page.locator('video')).toBeVisible();
  await expect.poll(() => page.locator('video').evaluate((media) => media.readyState)).toBeGreaterThanOrEqual(2);
  await page.getByRole('slider', { name: 'Seek video' }).fill('120');
  const overlay = page.getByTestId('interactive-overlay');
  await expect(overlay).toHaveAttribute('data-translation-status', 'completed', { timeout: 20000 });
  await expect(overlay.locator('[data-word-text]').first()).toBeVisible();
  const source = (await overlay.locator('[data-word-text], .subtitle-punctuation').allTextContents()).join('');
  expect(source).toBe('老登你给我接电话');
  await page.getByRole('button', { name: 'Play', exact: true }).click();
  await overlay.getByRole('button', { name: 'Look up 你', exact: true }).click();
  await expect(page.getByTestId('dictionary-panel')).toContainText('you');
  expect(await page.locator('video').evaluate((media) => media.paused)).toBe(false);
  await page.locator('video').evaluate((media) => media.pause());
  const bounds = await page.getByTestId('subtitle-image-bounds').boundingBox();
  const actual = await overlay.boundingBox();
  expect(actual.x).toBeGreaterThanOrEqual(bounds.x);
  expect(actual.x + actual.width).toBeLessThanOrEqual(bounds.x + bounds.width + 1);
  expect(actual.y + actual.height).toBeLessThanOrEqual(bounds.y + bounds.height * .87);
  const screenshot = path.join(frontend, 'test-results/phase3-real-video.png');
  await page.screenshot({ path: screenshot, fullPage: true });
  expect(errors).toEqual([]);
  console.log(JSON.stringify({ status: 'passed', library, source, translation: await page.getByTestId('subtitle-vietnamese').textContent(), screenshot }));
} finally {
  await browser?.close();
  for (const child of children.reverse()) {
    if (child.exitCode === null) {
      if (process.platform === 'win32') spawnSync('taskkill', ['/PID', String(child.pid), '/T', '/F'], { windowsHide: true, stdio: 'ignore' });
      else child.kill('SIGTERM');
    }
  }
}
