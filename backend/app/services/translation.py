"""Offline Hy-MT2 (default) or explicitly selected legacy Marian inference. Never downloads weights from a playback/API request."""
import json
import os
import threading
from pathlib import Path
from time import perf_counter

from app.models.learning import Translation
from app.services.translation_models import DEFAULT_MODEL, MODELS


class LocalTranslator:
    def __init__(self, resource_dir: Path, target: str = "vi", backend=None, model_id=None):
        if target not in ('vi', 'en'):
            raise ValueError('Unsupported translation target')
        self.target = target
        self.backend = None
        self.model_id = model_id or ('marian' if os.environ.get('DLP_TRANSLATION_ENGINE') == 'marian' else DEFAULT_MODEL)
        if self.model_id not in MODELS:
            raise ValueError('Unknown translation model')
        if self.model_id != 'marian':
            from app.services.hymt import HyMTBackend
            self.backend = backend or HyMTBackend(resource_dir, self.model_id)
            self.available = self.backend.available
            self.identity = f'zh->{target}:{self.backend.identity}'
            return
        self.folder = resource_dir / f'opus-mt-zh-{target}'
        self.model = None
        self.tokenizer = None
        self.lock = threading.Lock()
        self.identity = f'zh->{target}:Helsinki-NLP/opus-mt-zh-{target}:uninstalled'
        manifest = self.folder / 'local-model.json'
        self.available = manifest.is_file() and (self.folder / 'pytorch_model.bin').is_file()
        if self.available:
            metadata = json.loads(manifest.read_text(encoding='utf-8'))
            self.identity = f"zh->{target}:{metadata['model']}@{metadata['revision']}:beam4-v1"

    def translate(self, text: str) -> Translation:
        if not self.available:
            return Translation(target_language=self.target, status='unavailable', model=self.identity, error=f'Install translation resources with scripts/setup_hymt.py --model {self.model_id} and restart the backend.' if self.backend else f'Install legacy resources for {self.target} and restart the backend.')
        if len(text) > 1000:
            return Translation(target_language=self.target, status='failed', model=self.identity, error='Sentence exceeds 1,000 characters. Split or shorten it before translating; input is not silently truncated.')
        if self.backend:
            started = perf_counter()
            try:
                translated = self.backend.translate(text, self.target)
                return Translation(target_language=self.target, status='completed', text=translated, model=self.identity, seconds=perf_counter() - started)
            except Exception as exc:
                return Translation(target_language=self.target, status='failed', model=self.identity, error=f'Local Hy-MT2 inference failed: {exc}')
        with self.lock:
            try:
                import torch
                from transformers import MarianMTModel, MarianTokenizer
                torch.set_num_threads(2)
                if self.model is None:
                    self.tokenizer = MarianTokenizer.from_pretrained(str(self.folder), local_files_only=True)
                    self.model = MarianMTModel.from_pretrained(str(self.folder), local_files_only=True, use_safetensors=False).to('cpu').eval()
                started = perf_counter()
                inputs = self.tokenizer(text, return_tensors='pt', truncation=False)
                if inputs['input_ids'].shape[1] > 500:
                    raise ValueError('Sentence exceeds the translation model token limit; input was not truncated.')
                with torch.inference_mode():
                    output = self.model.generate(**inputs, max_new_tokens=192, num_beams=4, do_sample=False, renormalize_logits=True)
                translated = self.tokenizer.decode(output[0], skip_special_tokens=True).strip()
                if not translated:
                    raise ValueError('The model returned no translation.')
                return Translation(target_language=self.target, status='completed', text=translated, model=self.identity, seconds=perf_counter() - started)
            except Exception as exc:
                return Translation(target_language=self.target, status='failed', model=self.identity, error=f'Local zh->{self.target} inference failed: {exc}')

    def unload(self):
        if self.backend:
            self.backend.unload()
        else:
            with self.lock:
                self.model = None
                self.tokenizer = None
