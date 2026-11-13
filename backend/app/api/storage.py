"""Local storage inventory and explicitly selected, non-media cleanup."""
import os
from typing import Literal
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter(prefix='/api/storage', tags=['local storage'])


def size(path):
    if not path.exists() or path.is_symlink():
        return 0
    if path.is_file():
        return path.stat().st_size
    total = 0
    for root, dirs, files in os.walk(path, followlinks=False):
        dirs[:] = [d for d in dirs if not (path.__class__(root) / d).is_symlink() and not (path.__class__(root) / d).is_junction()]
        for name in files:
            item = path.__class__(root) / name
            try:
                if not item.is_symlink(): total += item.stat().st_size
            except OSError:
                pass
    return total


@router.get('')
def inventory(request: Request):
    settings = request.app.state.settings
    root = settings.data_dir
    repo = request.app.state.repository
    groups = {name: {'path': str(path), 'bytes': size(path)} for name, path in {
        'media': settings.media_dir, 'dictionary_and_models': settings.resource_dir,
        'database': repo.path, 'tests': root / 'tests', 'browser_tests': root / 'e2e',
        'validation': root / 'validation', 'optional_ocr_runtime': root / 'ocr-env',
    }.items()}
    with repo.connect() as db:
        counts = {table: db.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0] for table in
                  ('analyses', 'subtitle_segments', 'language_cache', 'translation_cache', 'vocabulary')}
        pages = db.execute('PRAGMA freelist_count').fetchone()[0]
        page_size = db.execute('PRAGMA page_size').fetchone()[0]
    return {'data_directory': str(root), 'groups': groups, 'counts': counts,
            'reusable_database_bytes': pages * page_size,
            'videos': [{'id': str(v.id), 'name': v.original_name, 'bytes': size(settings.media_dir / f'{v.id}.mp4')} for v in repo.list_videos()]}


class Cleanup(BaseModel):
    kind: Literal['translation_cache', 'language_cache', 'uncorrected_history']


@router.post('/cleanup')
def cleanup(request: Request, body: Cleanup):
    worker, learning = request.app.state.worker, request.app.state.learning
    with worker.lock, learning.lock:
        if worker.events or learning.scheduled:
            raise HTTPException(409, 'Wait for OCR and translation tasks to finish before cleaning caches.')
        with request.app.state.repository.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if body.kind in ('translation_cache', 'language_cache'):
                deleted = db.execute(f'DELETE FROM {body.kind}').rowcount
            else:
                # Preserve active results, all corrected transcripts and overrides.
                rows = db.execute("""SELECT a.id FROM analyses a
                    WHERE a.status NOT IN ('pending','processing')
                    AND a.id NOT IN (SELECT analysis_id FROM active_analyses)
                    AND NOT EXISTS (SELECT 1 FROM subtitle_segments s WHERE s.analysis_id=a.id AND
                        (json_extract(s.payload,'$.edited')=1 OR s.id IN (SELECT segment_id FROM translation_overrides)
                         OR s.id IN (SELECT segment_id FROM english_translation_overrides)))""").fetchall()
                for row in rows:
                    db.execute('DELETE FROM subtitle_segments WHERE analysis_id=?', (row[0],))
                    db.execute('DELETE FROM analyses WHERE id=?', (row[0],))
                deleted = len(rows)
    return {'deleted_records': deleted, 'note': 'SQLite may retain freed pages for reuse. Media, models, vocabulary and corrected/active transcripts were preserved.'}
