import json
import sqlite3
from contextlib import closing
from pathlib import Path

from pypinyin.contrib.tone_convert import to_tone
from app.models.learning import DictionaryEntry, DictionaryResult


class Dictionary:
    def __init__(self, directory: Path):
        self.path = directory / 'cedict.sqlite3'

    @property
    def available(self) -> bool:
        return self.path.is_file()

    def lookup(self, word: str) -> DictionaryResult:
        if not self.available:
            return DictionaryResult(word=word, available=False, entries=[])
        with closing(sqlite3.connect(f'{self.path.as_uri()}?mode=ro', uri=True)) as db:
            rows = db.execute('SELECT traditional,simplified,pinyin,meanings FROM entries WHERE simplified=? OR traditional=? LIMIT 50', (word, word)).fetchall()
        entries = [DictionaryEntry(traditional=t, simplified=s, pinyin=' '.join(to_tone(syllable) for syllable in p.split()), meanings=json.loads(m)) for t, s, p, m in rows]
        return DictionaryResult(word=word, available=True, entries=entries)
