"""Explicit, checksum-verified Windows installation. Never called by API requests."""
import argparse
import hashlib
import json
from pathlib import Path
import urllib.request
import zipfile

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from app.services.translation_models import MODELS, DEFAULT_MODEL

RUNTIME = 'b12347'
RUNTIME_SHA = '7dccbc28c03dc929687df80894d736c9fd91c71b88537f7f1a7d2eefb85a86c5'


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def download(url, path, checksum):
    if path.is_file() and digest(path) == checksum:
        return
    part = path.with_suffix(path.suffix + '.part')
    print(f'Downloading {path.name}', flush=True)
    with urllib.request.urlopen(url, timeout=120) as source, part.open('wb') as output:
        total = 0
        reported = 0
        while chunk := source.read(4 * 1024 * 1024):
            output.write(chunk)
            total += len(chunk)
            if total - reported >= 100 * 1024 * 1024:
                print(f'  {total / 1e6:.0f} MB', flush=True)
                reported = total
    if digest(part) != checksum:
        raise ValueError(f'Checksum mismatch: {part}')
    part.replace(path)


def install(root, model_id=DEFAULT_MODEL):
    spec = MODELS[model_id]
    REVISION, MODEL, SHA256, SIZE = (spec[key] for key in ('revision', 'file', 'sha256', 'size'))
    folder = root / spec['folder']
    folder.mkdir(parents=True, exist_ok=True)
    download(f"https://huggingface.co/{spec['repo']}/resolve/{REVISION}/{MODEL}", folder / MODEL, SHA256)
    archive = folder / f'llama-{RUNTIME}-vulkan.zip'
    download(f'https://github.com/ggml-org/llama.cpp/releases/download/{RUNTIME}/llama-{RUNTIME}-bin-win-vulkan-x64.zip', archive, RUNTIME_SHA)
    runtime = folder / 'runtime'
    with zipfile.ZipFile(archive) as bundle:
        for item in bundle.infolist():
            if not (runtime / item.filename).resolve().is_relative_to(runtime.resolve()):
                raise ValueError('Unsafe archive member')
        bundle.extractall(runtime)
    manifest = {'model': spec['repo'], 'revision': REVISION, 'file': MODEL,
                'sha256': SHA256, 'size': SIZE, 'runtime': RUNTIME, 'quantization': spec['quantization'], 'license': 'Apache-2.0'}
    temp = folder / 'local-model.json.tmp'
    temp.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    temp.replace(folder / 'local-model.json')
    print(f'Installed and verified: {folder}', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--resource-dir', type=Path, default=Path(__file__).resolve().parents[1] / 'data/resources')
    parser.add_argument('--model', choices=[key for key in MODELS if key != 'marian'], default=DEFAULT_MODEL)
    args = parser.parse_args()
    install(args.resource_dir, args.model)
