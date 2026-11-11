import { expect, test } from '@playwright/test';
import { readFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const fixture = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../data/fixtures/mandarin-test.mp4');

test('real OCR, visual ROI mapping, synchronization, edits, export, cancellation and safe video switching', async ({ page }) => {
  test.setTimeout(120_000);
  const errors: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await page.goto('/');
  await page.getByLabel('Choose MP4 file').setInputFiles(fixture);
  await expect(page.getByRole('heading', { name: 'mandarin-test.mp4' })).toBeVisible();
  await page.getByText('Subtitle analysis settings', { exact: true }).click();
  const canvas = page.getByTestId('roi-canvas');
  await expect(canvas).toBeVisible();
  await canvas.scrollIntoViewIfNeeded();
  const box = (await canvas.boundingBox())!;
  // Pointer positions use actual portrait image bounds, excluding the wide preview's black bars.
  expect(box.width / box.height).toBeCloseTo(360 / 640, 2);
  await page.mouse.move(box.x + box.width * .02, box.y + box.height * .55);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width * .98, box.y + box.height * .93, { steps: 8 });
  await page.mouse.up();
  expect(Number(await page.getByLabel('Region x', { exact: true }).inputValue())).toBeCloseTo(.02, 2);
  expect(Number(await page.getByLabel('Region width', { exact: true }).inputValue())).toBeCloseTo(.96, 2);
  // Reposition and resize the actual crop with pointer capture.
  const selection = (await page.getByRole('group', { name: 'OCR subtitle region' }).boundingBox())!;
  await page.mouse.move(selection.x + selection.width / 2, selection.y + selection.height / 2);
  await page.mouse.down();
  await page.mouse.move(selection.x + selection.width / 2, selection.y + selection.height / 2 - box.height * .05, { steps: 5 });
  await page.mouse.up();
  expect(Number(await page.getByLabel('Region y', { exact: true }).inputValue())).toBeCloseTo(.50, 2);
  const handle = (await page.locator('[data-handle="se"]').boundingBox())!;
  await page.mouse.move(handle.x + handle.width / 2, handle.y + handle.height / 2);
  await page.mouse.down();
  await page.mouse.move(handle.x + handle.width / 2 - box.width * .10, handle.y + handle.height / 2 - box.height * .05, { steps: 5 });
  await page.mouse.up();
  expect(Number(await page.getByLabel('Region width', { exact: true }).inputValue())).toBeCloseTo(.86, 2);
  for (const [name, value] of Object.entries({ x: '.05', y: '.60', width: '.90', height: '.30' })) {
    await page.getByLabel(`Region ${name}`, { exact: true }).fill(value);
  }
  await page.getByLabel('Samples / second').fill('2');
  await page.getByRole('button', { name: 'Analyze Video', exact: true }).click();
  await expect(page.getByTestId('analysis-status')).toHaveAttribute('data-status', 'completed', { timeout: 60_000 });
  const rows = page.getByTestId('subtitle-row');
  await expect(rows).toHaveCount(3);
  await expect(rows.nth(0)).toContainText('今天我们一起去吃饭');
  await expect(rows.nth(1)).toContainText('你在干什么？');
  await expect(rows.nth(2)).toContainText('我不知道发生了什么');
  await page.getByRole('slider', { name: 'Seek video' }).fill('1');
  await expect.poll(async () => (await page.getByTestId('interactive-overlay').locator('[data-word-text], .subtitle-punctuation').allTextContents()).join('')).toBe('今天我们一起去吃饭');
  await page.getByRole('slider', { name: 'Seek video' }).fill('2.5');
  await expect(page.getByTestId('interactive-overlay')).toHaveCount(0);
  await page.getByRole('slider', { name: 'Seek video' }).fill('4');
  await expect.poll(async () => (await page.getByTestId('interactive-overlay').locator('[data-word-text], .subtitle-punctuation').allTextContents()).join('')).toBe('你在干什么？');

  await rows.first().getByRole('button', { name: 'Edit subtitle' }).click();
  await page.getByLabel('Subtitle text', { exact: true }).fill('今天我们一起去吃饭！');
  await page.getByLabel('Start (seconds)').fill('.75');
  await page.getByLabel('End (seconds)').fill('2.25');
  await page.getByRole('button', { name: 'Save subtitle', exact: true }).click();
  await expect(rows.first()).toContainText('今天我们一起去吃饭！');
  await expect(rows.first()).toContainText('edited');
  await page.getByRole('button', { name: 'Analyze Video', exact: true }).click();
  await expect(page.getByText('Loaded cached subtitles, including your corrections. No OCR rerun was needed.')).toBeVisible();
  for (const format of ['JSON', 'SRT']) {
    const downloading = page.waitForEvent('download');
    await page.getByRole('link', { name: `Export ${format}` }).click();
    const download = await downloading;
    const content = await readFile((await download.path())!, 'utf8');
    expect(content).toContain('今天我们一起去吃饭！');
    if (format === 'SRT') expect(content).toContain('00:00:00,750 --> 00:00:02,250');
  }
  await page.reload();
  await expect(rows).toHaveCount(3);
  await expect(rows.first()).toContainText('今天我们一起去吃饭！');
  await page.getByText('Subtitle analysis settings', { exact: true }).click();
  await page.getByRole('button', { name: 'Rerun OCR', exact: true }).click();
  await page.getByRole('button', { name: 'Cancel analysis', exact: true }).click();
  await expect(page.getByTestId('analysis-status')).toHaveAttribute('data-status', 'cancelled');
  await expect(rows.first()).toContainText('今天我们一起去吃饭！');

  // A second valid MP4 identity: trailing bytes preserve the original MP4 streams.
  await page.getByLabel('Choose MP4 file').setInputFiles({ name: 'second-video.mp4', mimeType: 'video/mp4', buffer: Buffer.concat([await readFile(fixture), Buffer.from('second-video-test')]) });
  await expect(page.getByRole('heading', { name: 'second-video.mp4' })).toBeVisible();
  await expect(rows).toHaveCount(0);
  await page.getByText('Subtitle analysis settings', { exact: true }).click();
  await page.getByRole('button', { name: 'Analyze Video', exact: true }).click();
  await page.locator('.recent-video').filter({ hasText: 'mandarin-test.mp4' }).click();
  await expect(page.getByRole('heading', { name: 'mandarin-test.mp4' })).toBeVisible();
  await expect(rows.first()).toContainText('今天我们一起去吃饭！');
  const videos = await (await page.request.get('/api/videos')).json();
  const second = videos.find((video: { original_name: string }) => video.original_name === 'second-video.mp4');
  await expect.poll(async () => (await (await page.request.get(`/api/videos/${second.id}/analyses/latest`)).json()).status, { timeout: 60_000 }).toBe('completed');
  await expect(rows.first()).toContainText('今天我们一起去吃饭！');
  await page.locator('.recent-video').filter({ hasText: 'second-video.mp4' }).click();
  await expect(rows).toHaveCount(3);
  await expect(rows.first()).not.toContainText('！');
  await rows.last().getByRole('button', { name: 'Delete subtitle' }).click();
  await expect(rows).toHaveCount(2);
  await page.getByRole('slider', { name: 'Seek video' }).fill('4');
  await expect.poll(async () => (await page.getByTestId('interactive-overlay').locator('[data-word-text], .subtitle-punctuation').allTextContents()).join('')).toBe('你在干什么？');
  await page.getByText('Subtitle analysis settings', { exact: true }).click();
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: 'test-results/ocr-workspace.png', fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByTestId('roi-canvas')).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: 'test-results/ocr-workspace-mobile.png', fullPage: true });
  expect(errors).toEqual([]);
});
