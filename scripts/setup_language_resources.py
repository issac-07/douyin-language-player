"""Download attributed CC-CEDICT and the official pinned Chinese→Vietnamese model locally."""
import argparse
import gzip
import hashlib
import json
import re
import sqlite3
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESOURCE_DIR = ROOT / "data" / "resources"
MODEL = "Helsinki-NLP/opus-mt-zh-vi"
CEDICT = "https://www.mdbg.net/chinese/export/cedict/cedict_1_0_ts_utf-8_mdbg.txt.gz"


def download(url: str, target: Path):
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".download")
    digest = hashlib.sha256()
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "DouyinLanguagePlayer-local-setup/0.3"}), timeout=120) as response, temporary.open("wb") as destination:
            total = 0
            while chunk := response.read(1024 * 1024):
                destination.write(chunk); digest.update(chunk); total += len(chunk)
                if total % (32 * 1024 * 1024) == 0:
                    print(f"{target.name}: {total // (1024 * 1024)} MiB", flush=True)
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    return digest.hexdigest()


def dictionary():
    archive = RESOURCE_DIR / "cedict.txt.gz"
    sha = download(CEDICT, archive)
    path = RESOURCE_DIR / "cedict.sqlite3"
    temporary = RESOURCE_DIR / "cedict.build.sqlite3"
    temporary.unlink(missing_ok=True)
    rows = []
    with gzip.open(archive, "rt", encoding="utf-8") as source:
        for line in source:
            match = re.match(r"^(\S+) (\S+) \[(.*?)\] /(.*)/$", line.strip())
            if match:
                traditional, simplified, pinyin, meanings = match.groups()
                rows.append((traditional, simplified, pinyin, json.dumps(meanings.split("/"), ensure_ascii=False)))
    if len(rows) < 100_000:
        raise RuntimeError("CC-CEDICT download did not contain the expected full dictionary.")
    with sqlite3.connect(temporary) as db:
        db.execute("CREATE TABLE entries(traditional TEXT,simplified TEXT,pinyin TEXT,meanings TEXT)")
        db.executemany("INSERT INTO entries VALUES(?,?,?,?)", rows)
        db.executescript("CREATE INDEX simplified_words ON entries(simplified); CREATE INDEX traditional_words ON entries(traditional);")
    db.close()
    temporary.replace(path)
    (RESOURCE_DIR / "cedict-source.json").write_text(json.dumps({"source": CEDICT, "sha256": sha, "entries": len(rows), "attribution": "CC-CEDICT contributors, distributed by MDBG", "license": "CC-BY-SA-4.0", "license_url": "https://creativecommons.org/licenses/by-sa/4.0/"}, indent=2), encoding="utf-8")
    print(f"Installed {len(rows)} CC-CEDICT entries", flush=True)


def translation(target="vi"):
    model = f"Helsinki-NLP/opus-mt-zh-{target}"
    folder = RESOURCE_DIR / f"opus-mt-zh-{target}"
    manifest = folder / "local-model.json"
    if manifest.is_file():
        print("Translation resources already installed; preserving the pinned revision.", flush=True)
        return
    with urllib.request.urlopen(f"https://huggingface.co/api/models/{model}", timeout=30) as response:
        revision = json.load(response)["sha"]
    hashes = {}
    for name in ["config.json", "generation_config.json", "pytorch_model.bin", "source.spm", "target.spm", "tokenizer_config.json", "vocab.json", "README.md"]:
        target = folder / name
        if not target.is_file():
            print(f"Downloading {name}", flush=True)
            hashes[name] = download(f"https://huggingface.co/{model}/resolve/{revision}/{name}", target)
        else:
            hashes[name] = hashlib.sha256(target.read_bytes()).hexdigest()
    manifest.write_text(json.dumps({"model": model, "revision": revision, "license": "CC-BY-4.0" if target == "en" else "Apache-2.0", "files": hashes}, indent=2), encoding="utf-8")
    print(f"Installed translation model revision {revision}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dictionary-only", action="store_true")
    parser.add_argument("--translation-only", action="store_true")
    parser.add_argument("--target", choices=["vi", "en"], default="vi")
    args = parser.parse_args()
    RESOURCE_DIR.mkdir(parents=True, exist_ok=True)
    if not args.translation_only:
        dictionary()
    if not args.dictionary_only:
        translation(args.target)
