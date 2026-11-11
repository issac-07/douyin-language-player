import { execFileSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

export default function setup() {
  const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
  const python = path.join(root, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
  execFileSync(python, [path.join(root, 'scripts/generate_test_video.py')], { stdio: 'inherit', windowsHide: true });
  execFileSync(python, [path.join(root, 'scripts/generate_test_video.py'), '--landscape', '--output', path.join(root, 'data/fixtures/mandarin-landscape.mp4')], { stdio: 'inherit', windowsHide: true });
}
