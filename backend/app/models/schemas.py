from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ROI(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    x: float = Field(default=0.05, ge=0, lt=1)
    y: float = Field(default=0.60, ge=0, lt=1)
    width: float = Field(default=0.90, gt=0, le=1)
    height: float = Field(default=0.30, gt=0, le=1)

    @model_validator(mode="after")
    def within_frame(self) -> "ROI":
        if self.x + self.width > 1.000001 or self.y + self.height > 1.000001:
            raise ValueError("Subtitle region must fit entirely within the video frame.")
        return self


class ProcessingSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    roi: ROI = Field(default_factory=ROI)
    sample_fps: float = Field(default=2.0, ge=0.25, le=10)


class Video(BaseModel):
    id: UUID
    original_name: str
    sha256: str
    size_bytes: int
    duration: float
    width: int
    height: int
    fps: float
    video_codec: str
    audio_codec: str | None
    created_at: datetime
    media_url: str
    codec_warning: str | None = None


class ImportResult(BaseModel):
    video: Video
    reused: bool


class JobStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AnalysisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    settings: ProcessingSettings | None = None
    force: bool = False


class AnalysisMetrics(BaseModel):
    frames_processed: int = 0
    ocr_calls: int = 0
    reused_frames: int = 0
    inference_seconds: float = 0
    total_seconds: float = 0
    unique_segments: int = 0
    average_confidence: float = 0


class AnalysisJob(BaseModel):
    id: UUID
    video_id: UUID
    cache_key: str
    engine_version: str
    settings: ProcessingSettings
    status: JobStatus = JobStatus.PENDING
    created_at: datetime
    completed_at: datetime | None = None
    progress: float = 0
    total_frames: int
    error: str | None = None
    metrics: AnalysisMetrics = Field(default_factory=AnalysisMetrics)
    timestamp_uncertainty: float


class AnalysisStarted(BaseModel):
    job: AnalysisJob
    cached: bool = False


class SubtitleSegment(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    id: UUID
    start_time: float = Field(ge=0)
    end_time: float = Field(gt=0)
    text: str = Field(min_length=1, max_length=5000)
    confidence: float = Field(ge=0, le=1)
    edited: bool = False
    revision: int = 0
    metadata: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def time_order(self) -> "SubtitleSegment":
        if self.start_time >= self.end_time:
            raise ValueError("Subtitle start must be earlier than its end.")
        return self


class SubtitleDocument(BaseModel):
    video_id: UUID
    analysis: AnalysisJob | None = None
    segments: list[SubtitleSegment] = Field(default_factory=list)


class SubtitleEdit(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    analysis_id: UUID
    revision: int = Field(ge=0)
    text: str = Field(min_length=1, max_length=5000)
    start_time: float = Field(ge=0)
    end_time: float = Field(gt=0)

    @model_validator(mode="after")
    def valid_content(self) -> "SubtitleEdit":
        self.text = self.text.strip()
        if not self.text or self.start_time >= self.end_time:
            raise ValueError("Enter subtitle text and a start earlier than the end.")
        return self
