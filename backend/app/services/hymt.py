"""Local Hy-MT2 GGUF inference through a private, managed llama.cpp process."""
import atexit
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.request


from app.services.translation_models import MODELS, DEFAULT_MODEL


class HyMTBackend:
    def __init__(self, resource_dir: Path, model_id=DEFAULT_MODEL):
        spec = MODELS[model_id]
        self.folder = resource_dir / spec['folder']
        self.lock = threading.Lock()
        self.process = None
        self.log = None
        self.url = None
        self.key = secrets.token_urlsafe(32)
        self.closed = False
        self.metadata = {}
        manifest = self.folder / 'local-model.json'
        if manifest.is_file():
            try:
                self.metadata = json.loads(manifest.read_text(encoding='utf-8'))
            except (OSError, ValueError):
                self.metadata = {}
        self.model = self.folder / spec['file']
        self.executable = next((self.folder / 'runtime').rglob('llama-server.exe'), None)
        self.available = bool(self.executable and self.model.is_file() and self.model.stat().st_size == spec['size'] and all(self.metadata.get(key) == spec[key] for key in ('revision', 'sha256')))
        self.identity = (f"{spec['repo']}@{self.metadata.get('revision', 'uninstalled')}:"
                         f"{spec['quantization']}:{self.metadata.get('sha256', 'missing')}:llama-{self.metadata.get('runtime', 'missing')}:prompt-v1")
        atexit.register(self.close)

    def _request(self, path, body=None, timeout=5):
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(self.url + path, data=data,
                    headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + self.key})
        # Loopback must not be routed through a system HTTP proxy.
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request, timeout=timeout) as response:
            return json.load(response)

    def _stop(self):
        if self.process is not None:
            if self.process.poll() is None:
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=5)
            self.process = None
        if self.log:
            self.log.close()
            self.log = None

    def _start(self):
        if self.closed:
            raise RuntimeError('Translation service is shutting down.')
        if self.process is not None and self.process.poll() is None:
            return
        if not self.available:
            raise RuntimeError(f'Hy-MT2 resources are incomplete in {self.folder}; run the explicit model installer.')
        self._stop()
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            port = listener.getsockname()[1]
        self.url = f'http://127.0.0.1:{port}'
        self.log = (self.folder / 'inference.log').open('w', encoding='utf-8')
        args = [str(self.executable), '-m', str(self.model), '--host', '127.0.0.1', '--port', str(port),
                '--api-key', self.key, '-c', '4096', '-np', '1', '-ngl', os.environ.get('DLP_TRANSLATION_GPU_LAYERS', '99'),
                '-t', str(min(8, os.cpu_count() or 4)), '--jinja', '--no-webui', '--offline', '-lv', '4']
        self.process = subprocess.Popen(args, cwd=self.executable.parent, stdout=self.log, stderr=self.log,
                                        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                self._stop()
                raise RuntimeError("llama.cpp exited during model loading; see the selected model folder inference.log")
            try:
                if self._request('/health').get('status') == 'ok':
                    return
            except (OSError, ValueError):
                pass
            time.sleep(.25)
        self._stop()
        raise TimeoutError('Hy-MT2 model loading exceeded 120 seconds.')

    def translate(self, text, target):
        with self.lock:
            self._start()
            name = {'vi': '越南语', 'en': '英语'}[target]
            prompt = f'将以下文本翻译为{name}，注意只需要输出翻译后的结果，不要额外解释：\n\n{text}'
            try:
                result = self._request('/v1/chat/completions', {
                    'messages': [{'role': 'user', 'content': prompt}], 'max_tokens': 1024,
                    'temperature': .7, 'top_p': .6, 'top_k': 20, 'repeat_penalty': 1.05, 'seed': 42,
                    'stream': False}, timeout=120)
                choice = result['choices'][0]
                if choice.get('finish_reason') != 'stop':
                    raise ValueError('Translation was truncated; shorten the sentence and retry.')
                translated = choice['message']['content'].strip()
                if not translated:
                    raise ValueError('Hy-MT2 returned an empty translation.')
                return translated
            except Exception:
                # Abort timed-out generation instead of leaving it ahead of the next request.
                self._stop()
                raise

    def unload(self):
        with self.lock:
            self._stop()

    def close(self):
        with self.lock:
            self.closed = True
            self._stop()
