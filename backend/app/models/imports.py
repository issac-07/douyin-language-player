from datetime import datetime
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field
from app.models.schemas import ProcessingSettings, Video


class DouyinImportRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    text: str = Field(min_length=1, max_length=8192)
    analyze_after_import: bool = False
    processing_settings: ProcessingSettings | None = None
    roi_confirmed: bool = False
    use_public_page: bool = False


class SourceMetadata(BaseModel):
    video_id: str
    canonical_url: str
    title: str | None = None
    uploader: str | None = None
    duration: float | None = None
    extractor: str = 'yt-dlp'
    extractor_version: str


class ImportDiagnostic(BaseModel):
    operation: str
    event: str
    category: str | None = None
    http_status: int | None = None
    host: str | None = None
    endpoint: str | None = None
    exception_type: str | None = None
    upstream_reason: str | None = None


class ImportJob(BaseModel):
    id: UUID
    input_url: str
    canonical_url: str | None = None
    status: Literal['pending', 'resolving', 'downloading', 'validating', 'importing', 'completed', 'failed', 'cancelled'] = 'pending'
    created_at: datetime
    completed_at: datetime | None = None
    bytes_downloaded: int = 0
    total_bytes: int | None = None
    attempt: int = 1
    max_attempts: int = 3
    metadata: SourceMetadata | None = None
    video: Video | None = None
    reused: bool = False
    error: str | None = None
    error_code: str | None = None
    error_operation: str | None = None
    extractor_version: str | None = None
    extraction_method: Literal['direct', 'public_page'] = 'direct'
    upstream_http_status: int | None = None
    diagnostics: list[ImportDiagnostic] = Field(default_factory=list)
    conversion: str = 'none'
    elapsed_seconds: float = 0
    analysis_job_id: UUID | None = None
    analysis_message: str | None = None
    analyze_after_import: bool = False
