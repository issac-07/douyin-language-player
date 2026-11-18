"""Pinned local translation model catalog; safe to import from the installer."""
DEFAULT_MODEL = 'hymt-1.8b-q8'
MODELS = {
    'marian': {'label': 'OPUS / Marian (original)'},
    DEFAULT_MODEL: {'label': 'Hy-MT2 1.8B Q8', 'folder': 'hy-mt2-1.8b-q8', 'repo': 'tencent/Hy-MT2-1.8B-GGUF',
        'file': 'Hy-MT2-1.8B-Q8_0.gguf', 'revision': 'a0c709d9fac510f2c807aa3af52872340dc37a4a',
        'sha256': '5c3fe0b1408a5ceb0143184ef247b11b579c525f4b02b060e6c851bb76fef1a4', 'size': 1908528192, 'quantization': 'Q8_0'},
    'hymt-7b-q4km': {'label': 'Hy-MT2 7B Q4_K_M', 'folder': 'hy-mt2-7b-q4km', 'repo': 'tencent/Hy-MT2-7B-GGUF',
        'file': 'Hy-MT2-7B-Q4_K_M.gguf', 'revision': 'ab8472660ac61fac25f1af43fac2599d52a8a775',
        'sha256': '9f96256500f3fc1ab4d64336b58f52a949a95ad7516b0c229476eef782f9f77b', 'size': 4624648896, 'quantization': 'Q4_K_M'},
}
