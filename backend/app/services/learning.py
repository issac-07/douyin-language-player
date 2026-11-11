import hashlib
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from uuid import uuid4

from app.models.learning import LearningDocument, LearningSegment, PlayerSettings, SavedWord, Translation, VocabularyInput, WordToken
from app.services.chinese_processing import VERSION, process_chinese
from app.services.dictionary import Dictionary
from app.services.translation import LocalTranslator


def cache_key(text: str, version: str) -> str:
    return hashlib.sha256((version + '\0' + text).encode()).hexdigest()


class LearningService:
    def __init__(self, repository, settings):
        self.repo = repository
        self.dictionary = Dictionary(settings.resource_dir)
        self.translator = LocalTranslator(settings.resource_dir)
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='vietnamese')
        self.lock = threading.RLock()
        self.scheduled = set()
        self.closing = False

    def _get(self, table, key):
        with self.repo.connect() as db:
            row = db.execute(f'SELECT payload FROM {table} WHERE cache_key=?', (key,)).fetchone()
        return json.loads(row['payload']) if row else None

    def _put(self, table, key, payload):
        with self.repo.connect() as db:
            db.execute(f'INSERT INTO {table}(cache_key,payload) VALUES(?,?) ON CONFLICT(cache_key) DO UPDATE SET payload=excluded.payload', (key, json.dumps(payload, ensure_ascii=False)))

    def tokens(self, text):
        key = cache_key(text, VERSION)
        saved = self._get('language_cache', key)
        if saved is None:
            tokens = list(process_chinese(text))
            self._put('language_cache', key, [token.model_dump() for token in tokens])
            return tokens
        return [WordToken.model_validate(token) for token in saved]

    def translation(self, text):
        key = cache_key(text, self.translator.identity)
        with self.lock:
            saved = self._get('translation_cache', key)
            if saved and saved['status'] != 'pending':
                return Translation.model_validate(saved)
            if not self.translator.available:
                return Translation(status='unavailable', model=self.translator.identity, error='Install the local Vietnamese model with scripts/setup_language_resources.py, then restart.')
            if key not in self.scheduled and not self.closing and len(self.scheduled) < 512:
                self.scheduled.add(key)
                self._put('translation_cache', key, Translation(status='pending', model=self.translator.identity).model_dump())
                self.pool.submit(self._translate, key, text)
            return Translation(status='pending', model=self.translator.identity)

    def _translate(self, key, text):
        try:
            if not self.closing:
                result = self.translator.translate(text)
                self._put('translation_cache', key, result.model_dump())
        finally:
            with self.lock:
                self.scheduled.discard(key)

    def document(self, document):
        segments = []
        with self.repo.connect() as db:
            overrides = {row['segment_id']: row for row in db.execute('SELECT * FROM translation_overrides').fetchall()}
        for segment in document.segments:
            override = overrides.get(str(segment.id))
            translation = (Translation(status='manual', text=override['translation'])
                           if override and override['source_text'] == segment.text else self.translation(segment.text))
            segments.append(LearningSegment(id=segment.id, revision=segment.revision, text=segment.text, tokens=self.tokens(segment.text), translation=translation))
        return LearningDocument(video_id=document.video_id, analysis_id=document.analysis.id if document.analysis else None,
                                segments=segments, dictionary_available=self.dictionary.available)

    def retry(self, document):
        with self.repo.connect() as db:
            for segment in document.segments:
                key = cache_key(segment.text, self.translator.identity)
                row = db.execute('SELECT payload FROM translation_cache WHERE cache_key=?', (key,)).fetchone()
                if row and json.loads(row['payload'])['status'] in ('failed', 'unavailable'):
                    db.execute('DELETE FROM translation_cache WHERE cache_key=?', (key,))

    def save_translation(self, video_id, segment_id, body):
        with self.repo.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT s.payload,a.analysis_id FROM subtitle_segments s JOIN active_analyses a ON a.analysis_id=s.analysis_id WHERE a.video_id=? AND s.id=?', (str(video_id), str(segment_id))).fetchone()
            if not row:
                return False
            segment = json.loads(row['payload'])
            if row['analysis_id'] != str(body.analysis_id) or segment['revision'] != body.revision or segment['text'] != body.source_text:
                return False
            db.execute('INSERT INTO translation_overrides VALUES(?,?,?) ON CONFLICT(segment_id) DO UPDATE SET source_text=excluded.source_text,translation=excluded.translation', (str(segment_id), body.source_text, body.translation.strip()))
        return True

    def words(self):
        with self.repo.connect() as db:
            rows = db.execute('SELECT payload FROM vocabulary ORDER BY rowid DESC').fetchall()
        return [SavedWord.model_validate_json(row['payload']) for row in rows]

    def save_word(self, body: VocabularyInput):
        word = body.word.strip()
        if not word:
            raise ValueError('Enter a Chinese word.')
        lookup = self.dictionary.lookup(word)
        pinyin = next((token.pinyin for token in self.tokens(word) if token.selectable), '')
        if lookup.entries:
            pinyin = lookup.entries[0].pinyin
        with self.repo.connect() as db:
            previous = db.execute('SELECT payload FROM vocabulary WHERE word=?', (word,)).fetchone()
            word_id = SavedWord.model_validate_json(previous['payload']).id if previous else uuid4()
            result = SavedWord(id=word_id, word=word, pinyin=pinyin, entries=lookup.entries, status=body.status,
                               notes=body.notes, updated_at=datetime.now(timezone.utc).isoformat())
            db.execute('INSERT INTO vocabulary VALUES(?,?) ON CONFLICT(word) DO UPDATE SET payload=excluded.payload', (word, result.model_dump_json()))
        return result

    def get_player_settings(self):
        with self.repo.connect() as db:
            row = db.execute('SELECT payload FROM player_settings WHERE id=1').fetchone()
        return PlayerSettings.model_validate_json(row['payload']) if row else PlayerSettings()

    def save_player_settings(self, body):
        with self.repo.connect() as db:
            db.execute('INSERT INTO player_settings VALUES(1,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload', (body.model_dump_json(),))
        return body

    def shutdown(self):
        with self.lock:
            self.closing = True
        self.pool.shutdown(wait=True, cancel_futures=True)
