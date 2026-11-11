import { expect, test } from '@playwright/test';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const fixture = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../data/fixtures/mandarin-test.mp4');

test('real MP4 import, decoding, playback, seek, speed, fullscreen, and persistence', async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Bring a little Mandarin into your day.' })).toBeVisible();
  await page.getByLabel('Choose MP4 file').setInputFiles(fixture);
  await expect(page.getByRole('heading', { name: 'mandarin-test.mp4' })).toBeVisible();
  const video = page.locator('video');
  await expect.poll(() => video.evaluate((media: HTMLVideoElement) => media.readyState)).toBeGreaterThanOrEqual(2);
  expect(await video.evaluate((media: HTMLVideoElement) => [media.videoWidth, media.videoHeight])).toEqual([360, 640]);
  await page.getByRole('button', { name: 'Play', exact: true }).click();
  await expect.poll(() => video.evaluate((media: HTMLVideoElement) => media.currentTime)).toBeGreaterThan(0.2);
  await page.getByRole('button', { name: 'Pause', exact: true }).click();
  expect(await video.evaluate((media: HTMLVideoElement) => media.paused)).toBe(true);
  const pausedTime = await video.evaluate((media: HTMLVideoElement) => media.currentTime);
  await page.waitForTimeout(250);
  expect(await video.evaluate((media: HTMLVideoElement) => media.currentTime)).toBeCloseTo(pausedTime, 1);
  await page.getByRole('slider', { name: 'Seek video' }).fill('4');
  await expect.poll(() => video.evaluate((media: HTMLVideoElement) => media.currentTime)).toBeCloseTo(4, 1);
  await page.getByLabel('Playback speed').selectOption('1.5');
  expect(await video.evaluate((media: HTMLVideoElement) => media.playbackRate)).toBe(1.5);
  await page.getByRole('button', { name: 'Mute', exact: true }).click();
  expect(await video.evaluate((media: HTMLVideoElement) => media.muted)).toBe(true);
  await page.getByRole('button', { name: 'Fullscreen', exact: true }).click();
  await expect.poll(() => page.evaluate(() => Boolean(document.fullscreenElement))).toBe(true);
  await page.getByRole('button', { name: 'Fullscreen', exact: true }).click();
  await expect.poll(() => page.evaluate(() => Boolean(document.fullscreenElement))).toBe(false);
  await page.locator('h1').click();
  await page.keyboard.press('ArrowLeft');
  await expect.poll(() => video.evaluate((media: HTMLVideoElement) => media.currentTime)).toBe(0);
  await page.keyboard.press('k');
  await expect(page.getByRole('button', { name: 'Pause', exact: true })).toBeVisible();
  await page.keyboard.press('k');
  await expect(page.getByRole('button', { name: 'Play', exact: true })).toBeVisible();

  await page.getByText('Subtitle analysis settings', { exact: true }).click();
  await page.getByLabel('Samples / second').fill('3');
  await page.getByRole('button', { name: 'Save settings' }).click();
  await expect(page.getByText('Settings saved locally. No analysis has been run.')).toBeVisible();
  await page.reload();
  await expect(page.getByRole('heading', { name: 'mandarin-test.mp4' })).toBeVisible();
  await page.getByText('Subtitle analysis settings', { exact: true }).click();
  await expect(page.getByLabel('Samples / second')).toHaveValue('3');
  await page.getByLabel('Choose MP4 file').setInputFiles(fixture);
  await expect(page.getByText('Opened the existing local copy. No duplicate was stored.')).toBeVisible();
  expect(errors).toEqual([]);
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: 'test-results/player-desktop.png', fullPage: true });
});

test('invalid file rejection and responsive workspace', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');
  await page.getByLabel('Choose MP4 file').setInputFiles({ name: 'not-a-video.mp4', mimeType: 'video/mp4', buffer: Buffer.from('not a video') });
  await expect(page.getByRole('alert')).toContainText('valid MP4 header');
  await page.getByRole('tab', { name: 'Vocabulary' }).click();
  await expect(page.getByRole('tabpanel')).toContainText('Phase 3');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: 'test-results/player-mobile.png', fullPage: true });
});
