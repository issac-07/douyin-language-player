import { defineConfig } from '@playwright/test';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const python = path.join(root, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');

export default defineConfig({
  testDir: './e2e',
  workers: 1,
  projects: [
    { name: 'phase1', testMatch: '**/player.spec.ts' },
    { name: 'phase2', testMatch: '**/ocr.spec.ts', dependencies: ['phase1'] },
  ],
  timeout: 30_000,
  globalSetup: './e2e/setup.ts',
  use: {
    baseURL: 'http://127.0.0.1:5174',
    browserName: 'chromium',
    channel: 'msedge',
    headless: true,
    trace: 'retain-on-failure',
  },
  webServer: [
    {
      command: `"${python}" -m uvicorn app.main:app --app-dir "${path.join(root, 'backend')}" --host 127.0.0.1 --port 8011`,
      url: 'http://127.0.0.1:8011/api/health',
      env: { DLP_DATA_DIR: path.join(root, 'data', 'e2e', `run-${Date.now()}`), DLP_ALLOWED_ORIGINS: 'http://127.0.0.1:5174' },
      reuseExistingServer: false,
    },
    {
      command: 'node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 5174 --strictPort',
      url: 'http://127.0.0.1:5174',
      env: { DLP_API_URL: 'http://127.0.0.1:8011' },
      reuseExistingServer: false,
    },
  ],
});
