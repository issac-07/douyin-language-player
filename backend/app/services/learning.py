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
from app.services.translation_models import MODELS, DEFAULT_MODEL


def cache_key(text: str, version: str) -> str:
    return hashlib.sha256((version + '\0' + text).encode()).hexdigest()


class LearningService:
    def __init__(self, repository, settings):
        self.repo = repository
        self.dictionary = Dictionary(settings.resource_dir)
        self.model_translators = {}
        for model_id in MODELS:
            vi = LocalTranslator(settings.resource_dir, model_id=model_id)
            self.model_translators[model_id] = {'vi': vi, 'en': LocalTranslator(settings.resource_dir, 'en', backend=vi.backend, model_id=model_id)}
        self.translators = self.model_translators[DEFAULT_MODEL]
        self.translator = self.translators['vi']
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='translation')
        self.pools = {'vi': self.pool, 'en': self.pool}
        self.loaded_model = None
        self.requested_model = None
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

    def translation(self, text, target="vi", model_id=None):
        model_id = model_id or self.get_player_settings().translation_model
        translator = self.model_translators[model_id][target]
        key = cache_key(text, translator.identity)
        with self.lock:
            self.requested_model = model_id
            saved = self._get('translation_cache', key)
            if saved and saved['status'] != 'pending':
                return Translation.model_validate(saved)
            if not translator.available:
                return Translation(status='unavailable', model=translator.identity, error=f'The selected model {MODELS[model_id]["label"]} is not installed. Install its local resources and restart the backend.')
            if key not in self.scheduled and not self.closing and len(self.scheduled) < 512:
                self.scheduled.add(key)
                self._put('translation_cache', key, Translation(status='pending', model=translator.identity).model_dump())
                self.pools[target].submit(self._translate, key, text, translator, model_id)
            return Translation(status='pending', model=translator.identity)

    def _translate(self, key, text, translator, model_id):
        try:
            if not self.closing and self.requested_model == model_id:
                if self.loaded_model != model_id:
                    for other_id, pair in self.model_translators.items():
                        if other_id != model_id:
                            for other in pair.values():
                                other.unload()
                    self.loaded_model = model_id
                if model_id == 'marian':
                    for other in self.model_translators['marian'].values():
                        if other is not translator:
                            other.unload()
                result = translator.translate(text)
                self._put('translation_cache', key, result.model_dump())
        finally:
            with self.lock:
                self.scheduled.discard(key)

    def document(self, document, target=None, model_id=None):
        model_id = model_id or self.get_player_settings().translation_model
        target = target or self.get_player_settings().sentence_language
        segments = []
        with self.repo.connect() as db:
            table = 'english_translation_overrides' if target == 'en' else 'translation_overrides'
            overrides = {row['segment_id']: row for row in db.execute(f'SELECT * FROM {table}').fetchall()}
        for segment in document.segments:
            override = overrides.get(str(segment.id))
            translation = (Translation(status='manual', text=override['translation'])
                           if override and override['source_text'] == segment.text else self.translation(segment.text, target, model_id))
            translation.target_language = target
            segments.append(LearningSegment(id=segment.id, revision=segment.revision, text=segment.text, tokens=self.tokens(segment.text), translation=translation))
        return LearningDocument(translation_model=model_id, model_label=MODELS[model_id]['label'], video_id=document.video_id, analysis_id=document.analysis.id if document.analysis else None,
                                target_language=target, segments=segments, dictionary_available=self.dictionary.available)

    def retry(self, document, target=None, model_id=None):
        translator = self.model_translators[model_id or self.get_player_settings().translation_model][target or self.get_player_settings().sentence_language]
        with self.repo.connect() as db:
            for segment in document.segments:
                key = cache_key(segment.text, translator.identity)
                row = db.execute('SELECT payload FROM translation_cache WHERE cache_key=?', (key,)).fetchone()
                if row and json.loads(row['payload'])['status'] in ('failed', 'unavailable'):
                    db.execute('DELETE FROM translation_cache WHERE cache_key=?', (key,))

    def save_translation(self, video_id, segment_id, body):
        table = "english_translation_overrides" if body.target_language == "en" else "translation_overrides"
        with self.repo.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT s.payload,a.analysis_id FROM subtitle_segments s JOIN active_analyses a ON a.analysis_id=s.analysis_id WHERE a.video_id=? AND s.id=?', (str(video_id), str(segment_id))).fetchone()
            if not row:
                return False
            segment = json.loads(row['payload'])
            if row['analysis_id'] != str(body.analysis_id) or segment['revision'] != body.revision or segment['text'] != body.source_text:
                return False
            db.execute(f'INSERT INTO {table} VALUES(?,?,?) ON CONFLICT(segment_id) DO UPDATE SET source_text=excluded.source_text,translation=excluded.translation', (str(segment_id), body.source_text, body.translation.strip()))
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
        for pool in set(self.pools.values()):
            pool.shutdown(wait=True, cancel_futures=True)
        for pair in self.model_translators.values():
            if pair['vi'].backend:
                pair['vi'].backend.close()
            else:
                for translator in pair.values():
                    translator.unload()
