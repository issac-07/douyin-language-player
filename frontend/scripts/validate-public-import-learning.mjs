// Verify the ACTUAL downloaded media and its real OCR/language cache in Edge.
import { spawn, spawnSync } from 'node:child_process';
import { readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium, expect } from '@playwright/test';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const imported = JSON.parse(await readFile(path.join(root, 'data/validation/phase4-debug/public-edge-import.json'), 'utf8'));
const verified = JSON.parse(await readFile(path.join(root, 'data/validation/phase4-debug/imported-learning.json'), 'utf8'));
if (imported.status !== 'completed' || verified.status !== 'passed') throw new Error('Real import and OCR must finish first.');
const children = [];
let browser;
function start(command, args, cwd, env) {
  const child = spawn(command, args, { cwd, env: { ...process.env, ...env }, windowsHide: true, stdio: 'ignore' });
  children.push(child);
}
async function ready(url) {
  for (let index = 0; index < 120; index++) {
    try { if ((await fetch(url)).ok) return; } catch {}
    if (children.some((child) => child.exitCode !== null)) throw new Error('Validation preview process stopped.');
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw new Error('Validation preview was not ready.');
}
try {
  start(path.join(root, '.venv/Scripts/python.exe'), ['-m', 'uvicorn', 'app.main:app', '--app-dir', 'backend', '--host', '127.0.0.1', '--port', '8012'], root,
    { DLP_DATA_DIR: imported.library, DLP_ALLOWED_ORIGINS: 'http://127.0.0.1:5175' });
  start(process.execPath, ['node_modules/vite/bin/vite.js', '--host', '127.0.0.1', '--port', '5175', '--strictPort'], path.join(root, 'frontend'), { DLP_API_URL: 'http://127.0.0.1:8012' });
  await ready('http://127.0.0.1:8012/api/health'); await ready('http://127.0.0.1:5175');
  browser = await chromium.launch({ channel: 'msedge', headless: true });
  const page = await browser.newPage({ baseURL: 'http://127.0.0.1:5175', viewport: { width: 1440, height: 1050 } });
  const errors = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await page.goto('/');
  const video = page.locator('video');
  await expect.poll(() => video.evaluate((media) => media.readyState)).toBeGreaterThanOrEqual(2);
  const duration = await video.evaluate((media) => media.duration);
  expect(duration).toBeCloseTo(imported.video.duration, 1);
  await page.getByRole('slider', { name: 'Seek video' }).fill(String(duration - 1.2));
  await page.getByRole('button', { name: 'Play', exact: true }).click();
  await expect.poll(() => video.evaluate((media) => media.currentTime)).toBeGreaterThan(duration - .9);
  await video.evaluate((media) => media.pause());
  const document = await page.request.get(`/api/videos/${imported.video.id}/subtitles`).then((response) => response.json());
  const learning = await page.request.get(`/api/videos/${imported.video.id}/learning`).then((response) => response.json());
  let chosen;
  for (const segment of learning.segments.filter((item) => item.translation.status === 'completed')) {
    for (const token of segment.tokens.filter((item) => item.selectable)) {
      const dictionary = await page.request.get(`/api/dictionary?word=${encodeURIComponent(token.text)}`).then((response) => response.json());
      if (dictionary.entries.length) { chosen = { segment, token, dictionary }; break; }
    }
    if (chosen) break;
  }
  expect(chosen).toBeTruthy();
  const timing = document.segments.find((item) => item.id === chosen.segment.id);
  await page.getByRole('slider', { name: 'Seek video' }).fill(String(timing.start_time + .05));
  const overlay = page.locator('.video-stage').getByTestId('interactive-overlay');
  await expect(overlay).toBeVisible();
  await expect(overlay.getByTestId('word-pinyin').first()).not.toBeEmpty();
  await expect(page.getByTestId('subtitle-vietnamese')).toContainText(chosen.segment.translation.text);
  await page.getByRole('button', { name: 'Play', exact: true }).click();
  await overlay.getByRole('button', { name: `Look up ${chosen.token.text}`, exact: true }).first().click();
  await expect(page.getByTestId('dictionary-panel')).toContainText(chosen.dictionary.entries[0].meanings[0]);
  expect(await video.evaluate((media) => media.paused)).toBe(false);
  await video.evaluate((media) => media.pause());
  await expect(page.getByRole('dialog')).toHaveCount(0);
  const screenshot = path.join(root, 'data/validation/phase4-debug/live-import-learning.png');
  await page.screenshot({ path: screenshot });
  expect(errors).toEqual([]);
  const report = { status: 'passed', real_download: true, video_id: imported.video.id, duration, decoded_final_seconds: true,
    ocr_subtitles: document.segments.length, source: chosen.segment.text, pinyin: chosen.token.pinyin,
    translation: chosen.segment.translation.text, dictionary_word: chosen.token.text, page_errors: errors, screenshot };
  await writeFile(path.join(root, 'data/validation/phase4-debug/live-import-learning-edge.json'), JSON.stringify(report, null, 2));
  console.log(JSON.stringify(report));
} finally {
  await browser?.close();
  for (const child of children.reverse()) if (child.exitCode === null) {
    if (process.platform === 'win32') spawnSync('taskkill', ['/PID', String(child.pid), '/T', '/F'], { windowsHide: true, stdio: 'ignore' });
    else child.kill('SIGTERM');
  }
}
