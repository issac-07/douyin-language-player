"""Offline Marian inference. Never downloads weights from a playback/API request."""
import json
import threading
from pathlib import Path
from time import perf_counter

from app.models.learning import Translation


class LocalTranslator:
    def __init__(self, resource_dir: Path, target: str = "vi"):
        self.target = target
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
            return Translation(target_language=self.target, status='unavailable', model=self.identity, error=f'Install local zh->{self.target} resources with scripts/setup_language_resources.py --translation-only --target {self.target}, then restart the backend.')
        if len(text) > 1000:
            return Translation(target_language=self.target, status='failed', model=self.identity, error='Sentence exceeds 1,000 characters. Split or shorten it before translating; input is not silently truncated.')
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
