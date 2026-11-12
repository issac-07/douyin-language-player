import csv
import io
from typing import Literal
from uuid import UUID
from fastapi import APIRouter, HTTPException, Query, Request
from starlette.responses import Response

from app.api.videos import require_video
from app.models.learning import DictionaryResult, LearningDocument, PlayerSettings, SavedWord, TranslationEdit, VocabularyInput

router = APIRouter(prefix='/api', tags=['language learning'])


@router.get('/videos/{video_id}/learning', response_model=LearningDocument)
def learning(request: Request, video_id: UUID, target: Literal["vi", "en"] | None = None):
    require_video(request, video_id)
    return request.app.state.learning.document(request.app.state.repository.document(video_id), target)


@router.post('/videos/{video_id}/learning/retry', response_model=LearningDocument)
def retry(request: Request, video_id: UUID, target: Literal["en", "vi"] | None = None):
    require_video(request, video_id)
    document = request.app.state.repository.document(video_id)
    request.app.state.learning.retry(document, target)
    return request.app.state.learning.document(document, target)


@router.put('/videos/{video_id}/subtitles/{segment_id}/translation', response_model=LearningDocument)
def translation_edit(request: Request, video_id: UUID, segment_id: UUID, body: TranslationEdit):
    target = body.target_language
    require_video(request, video_id)
    if not body.translation.strip():
        raise HTTPException(422, 'Translation cannot be empty.')
    if not request.app.state.learning.save_translation(video_id, segment_id, body):
        raise HTTPException(409, 'The subtitle changed. Reload before editing its translation.')
    return request.app.state.learning.document(request.app.state.repository.document(video_id), target)


@router.get('/dictionary', response_model=DictionaryResult)
def dictionary(request: Request, word: str = Query(min_length=1, max_length=64), target: Literal['en', 'vi'] = 'en'):
    result = request.app.state.learning.dictionary.lookup(word)
    if target == 'vi':
        result.translation = request.app.state.learning.translation(word, 'vi')
        result.translation.target_language = 'vi'
    return result


@router.get('/vocabulary', response_model=list[SavedWord])
def vocabulary(request: Request):
    return request.app.state.learning.words()


@router.put('/vocabulary', response_model=SavedWord)
def save_vocabulary(request: Request, body: VocabularyInput):
    try:
        return request.app.state.learning.save_word(body)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.delete('/vocabulary/{word_id}', status_code=204)
def delete_vocabulary(request: Request, word_id: UUID):
    service = request.app.state.learning
    word = next((word for word in service.words() if word.id == word_id), None)
    if not word:
        raise HTTPException(404, 'Saved word not found.')
    with request.app.state.repository.connect() as db:
        db.execute('DELETE FROM vocabulary WHERE word=?', (word.word,))


@router.get('/vocabulary/export/csv')
def export_vocabulary(request: Request):
    stream = io.StringIO(newline='')
    writer = csv.writer(stream)
    writer.writerow(['Chinese', 'Pinyin', 'English definitions', 'Status', 'Notes', 'Dictionary source'])
    def safe(value):
        return "'" + value if value.startswith(('=', '+', '-', '@')) else value
    for word in request.app.state.learning.words():
        meanings = '; '.join(meaning for entry in word.entries for meaning in entry.meanings)
        writer.writerow([safe(value) for value in [word.word, word.pinyin, meanings, word.status, word.notes, 'CC-CEDICT / MDBG (CC-BY-SA-4.0)']])
    return Response(stream.getvalue().encode('utf-8-sig'), media_type='text/csv', headers={'Content-Disposition': 'attachment; filename="vocabulary.csv"'})


@router.get('/player-settings', response_model=PlayerSettings)
def player_settings(request: Request):
    return request.app.state.learning.get_player_settings()


@router.put('/player-settings', response_model=PlayerSettings)
def save_player_settings(request: Request, body: PlayerSettings):
    return request.app.state.learning.save_player_settings(body)
