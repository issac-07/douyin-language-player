import sqlite3
from contextlib import contextmanager
from pathlib import Path
from uuid import UUID

from app.models.schemas import AnalysisJob, JobStatus, ProcessingSettings, SubtitleDocument, SubtitleSegment, Video


class Repository:
    """One short-lived SQLite connection per operation, safe across worker threads."""

    def __init__(self, path: Path):
        self.path = path

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.path, timeout=15)
        try:
            with connection:
                connection.row_factory = sqlite3.Row
                connection.execute("PRAGMA foreign_keys=ON")
                yield connection
        finally:
            connection.close()

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS videos (
                    id TEXT PRIMARY KEY,
                    sha256 TEXT NOT NULL UNIQUE,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS processing_settings (
                    video_id TEXT PRIMARY KEY REFERENCES videos(id) ON DELETE CASCADE,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS analyses (
                    id TEXT PRIMARY KEY,
                    video_id TEXT NOT NULL REFERENCES videos(id),
                    cache_key TEXT NOT NULL,
                    status TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS analysis_cache ON analyses(video_id, cache_key, status);
                CREATE TABLE IF NOT EXISTS subtitle_segments (
                    id TEXT PRIMARY KEY,
                    analysis_id TEXT NOT NULL REFERENCES analyses(id),
                    payload TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS segments_analysis ON subtitle_segments(analysis_id);
                CREATE TABLE IF NOT EXISTS active_analyses (
                    video_id TEXT PRIMARY KEY REFERENCES videos(id),
                    analysis_id TEXT NOT NULL REFERENCES analyses(id)
                );
                CREATE TABLE IF NOT EXISTS language_cache (cache_key TEXT PRIMARY KEY,payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS translation_cache (cache_key TEXT PRIMARY KEY,payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS translation_overrides (segment_id TEXT PRIMARY KEY,source_text TEXT NOT NULL,translation TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS vocabulary (word TEXT PRIMARY KEY,payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS player_settings (id INTEGER PRIMARY KEY CHECK(id=1),payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS import_jobs (id TEXT PRIMARY KEY,payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS video_sources (canonical_url TEXT PRIMARY KEY,video_id TEXT NOT NULL REFERENCES videos(id),payload TEXT NOT NULL);
                PRAGMA user_version=4;
            """)

    def list_videos(self) -> list[Video]:
        with self.connect() as db:
            rows = db.execute("SELECT payload FROM videos ORDER BY rowid DESC").fetchall()
        return [Video.model_validate_json(row["payload"]) for row in rows]

    def get_video(self, video_id: UUID) -> Video | None:
        with self.connect() as db:
            row = db.execute("SELECT payload FROM videos WHERE id=?", (str(video_id),)).fetchone()
        return Video.model_validate_json(row["payload"]) if row else None

    def by_hash(self, fingerprint: str) -> Video | None:
        with self.connect() as db:
            row = db.execute("SELECT payload FROM videos WHERE sha256=?", (fingerprint,)).fetchone()
        return Video.model_validate_json(row["payload"]) if row else None

    def add(self, video: Video) -> Video:
        with self.connect() as db:
            db.execute(
                "INSERT OR IGNORE INTO videos (id, sha256, payload) VALUES (?, ?, ?)",
                (str(video.id), video.sha256, video.model_dump_json()),
            )
            row = db.execute("SELECT payload FROM videos WHERE sha256=?", (video.sha256,)).fetchone()
        return Video.model_validate_json(row["payload"])

    def get_settings(self, video_id: UUID) -> ProcessingSettings:
        with self.connect() as db:
            row = db.execute("SELECT payload FROM processing_settings WHERE video_id=?", (str(video_id),)).fetchone()
        return ProcessingSettings.model_validate_json(row["payload"]) if row else ProcessingSettings()

    def has_settings(self, video_id: UUID) -> bool:
        with self.connect() as db:
            return db.execute("SELECT 1 FROM processing_settings WHERE video_id=?", (str(video_id),)).fetchone() is not None

    def save_import(self, job) -> None:
        with self.connect() as db:
            db.execute("INSERT INTO import_jobs(id,payload) VALUES(?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload", (str(job.id), job.model_dump_json()))

    def get_import(self, job_id):
        from app.models.imports import ImportJob
        with self.connect() as db:
            row = db.execute("SELECT payload FROM import_jobs WHERE id=?", (str(job_id),)).fetchone()
        return ImportJob.model_validate_json(row['payload']) if row else None

    def list_imports(self, limit=20):
        from app.models.imports import ImportJob
        with self.connect() as db:
            rows = db.execute("SELECT payload FROM import_jobs ORDER BY rowid DESC LIMIT ?", (limit,)).fetchall()
        return [ImportJob.model_validate_json(row['payload']) for row in rows]

    def find_source(self, url):
        with self.connect() as db:
            row = db.execute("SELECT v.payload FROM video_sources s JOIN videos v ON v.id=s.video_id WHERE canonical_url=?", (url,)).fetchone()
        return Video.model_validate_json(row['payload']) if row else None

    def get_source(self, url):
        from app.models.imports import SourceMetadata
        with self.connect() as db:
            row = db.execute("SELECT payload FROM video_sources WHERE canonical_url=?", (url,)).fetchone()
        return SourceMetadata.model_validate_json(row['payload']) if row else None

    def attach_source(self, video, source):
        if not video.source_url:
            video = video.model_copy(update=dict(title=source.title, source_url=source.canonical_url, source_id=source.video_id, uploader=source.uploader, imported_from='douyin'))
        with self.connect() as db:
            db.execute("UPDATE videos SET payload=? WHERE id=?", (video.model_dump_json(), str(video.id)))
            db.execute("INSERT INTO video_sources(canonical_url,video_id,payload) VALUES(?,?,?) ON CONFLICT(canonical_url) DO UPDATE SET video_id=excluded.video_id,payload=excluded.payload", (source.canonical_url, str(video.id), source.model_dump_json()))
        return video

    def save_settings(self, video_id: UUID, settings: ProcessingSettings) -> None:
        with self.connect() as db:
            db.execute(
                "INSERT INTO processing_settings (video_id, payload) VALUES (?, ?) "
                "ON CONFLICT(video_id) DO UPDATE SET payload=excluded.payload",
                (str(video_id), settings.model_dump_json()),
            )

    def save_job(self, job: AnalysisJob) -> None:
        with self.connect() as db:
            db.execute(
                "INSERT INTO analyses(id,video_id,cache_key,status,payload) VALUES(?,?,?,?,?) "
                "ON CONFLICT(id) DO UPDATE SET status=excluded.status,payload=excluded.payload",
                (str(job.id), str(job.video_id), job.cache_key, job.status.value, job.model_dump_json()),
            )

    def get_job(self, job_id: UUID) -> AnalysisJob | None:
        with self.connect() as db:
            row = db.execute("SELECT payload FROM analyses WHERE id=?", (str(job_id),)).fetchone()
        return AnalysisJob.model_validate_json(row["payload"]) if row else None

    def latest_job(self, video_id: UUID, cache_key: str | None = None) -> AnalysisJob | None:
        with self.connect() as db:
            if cache_key:
                row = db.execute("SELECT payload FROM analyses WHERE video_id=? AND cache_key=? AND status='completed' ORDER BY rowid DESC LIMIT 1", (str(video_id), cache_key)).fetchone()
            else:
                row = db.execute("SELECT payload FROM analyses WHERE video_id=? ORDER BY rowid DESC LIMIT 1", (str(video_id),)).fetchone()
        return AnalysisJob.model_validate_json(row["payload"]) if row else None

    def recover_interrupted_jobs(self) -> None:
        with self.connect() as db:
            rows = db.execute("SELECT payload FROM analyses WHERE status IN ('pending','processing')").fetchall()
            for row in rows:
                job = AnalysisJob.model_validate_json(row["payload"])
                job.status = JobStatus.FAILED
                job.error = "The backend stopped before this analysis finished. Run Analyze again."
                db.execute("UPDATE analyses SET status=?,payload=? WHERE id=?", (job.status.value, job.model_dump_json(), str(job.id)))

    @staticmethod
    def _activate(db, video_id: UUID, job_id: UUID) -> None:
        db.execute("INSERT INTO active_analyses(video_id,analysis_id) VALUES(?,?) ON CONFLICT(video_id) DO UPDATE SET analysis_id=excluded.analysis_id", (str(video_id), str(job_id)))

    def activate(self, job: AnalysisJob) -> None:
        with self.connect() as db:
            self._activate(db, job.video_id, job.id)

    def complete(self, job: AnalysisJob, segments: list[SubtitleSegment]) -> None:
        # Results and the active pointer commit atomically; cancellations never reach here.
        with self.connect() as db:
            db.execute("UPDATE analyses SET status=?,payload=? WHERE id=?", (job.status.value, job.model_dump_json(), str(job.id)))
            db.executemany("INSERT INTO subtitle_segments(id,analysis_id,payload) VALUES(?,?,?)", [(str(s.id), str(job.id), s.model_dump_json()) for s in segments])
            self._activate(db, job.video_id, job.id)

    def document(self, video_id: UUID, analysis_id: UUID | None = None) -> SubtitleDocument:
        with self.connect() as db:
            if analysis_id:
                job_row = db.execute("SELECT payload FROM analyses WHERE id=? AND video_id=? AND status='completed'", (str(analysis_id), str(video_id))).fetchone()
            else:
                job_row = db.execute("SELECT a.payload FROM analyses a JOIN active_analyses c ON c.analysis_id=a.id WHERE c.video_id=?", (str(video_id),)).fetchone()
            if not job_row:
                return SubtitleDocument(video_id=video_id)
            job = AnalysisJob.model_validate_json(job_row["payload"])
            rows = db.execute("SELECT payload FROM subtitle_segments WHERE analysis_id=?", (str(job.id),)).fetchall()
        segments = sorted((SubtitleSegment.model_validate_json(row["payload"]) for row in rows), key=lambda s: (s.start_time, s.end_time))
        return SubtitleDocument(video_id=video_id, analysis=job, segments=segments)

    def change_segment(self, video_id: UUID, analysis_id: UUID, segment_id: UUID, revision: int, replacement: SubtitleSegment | None) -> bool:
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            active = db.execute("SELECT analysis_id FROM active_analyses WHERE video_id=?", (str(video_id),)).fetchone()
            row = db.execute("SELECT payload FROM subtitle_segments WHERE id=? AND analysis_id=?", (str(segment_id), str(analysis_id))).fetchone()
            if not active or active["analysis_id"] != str(analysis_id) or not row or SubtitleSegment.model_validate_json(row["payload"]).revision != revision:
                return False
            if replacement:
                # Reject overlaps inside the write transaction, including concurrent edits.
                rows = db.execute("SELECT payload FROM subtitle_segments WHERE analysis_id=? AND id!=?", (str(analysis_id), str(segment_id))).fetchall()
                for item in rows:
                    other = SubtitleSegment.model_validate_json(item["payload"])
                    if replacement.start_time < other.end_time and other.start_time < replacement.end_time:
                        raise ValueError("Subtitle times overlap another segment.")
                db.execute("UPDATE subtitle_segments SET payload=? WHERE id=?", (replacement.model_dump_json(), str(segment_id)))
            else:
                db.execute("DELETE FROM subtitle_segments WHERE id=?", (str(segment_id),))
        return True
