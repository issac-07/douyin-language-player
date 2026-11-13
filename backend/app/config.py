import os
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    max_upload_bytes: int = 512 * 1024 * 1024
    ffprobe: str = "ffprobe"
    ffmpeg: str = "ffmpeg"
    node: str = 'node'
    max_download_bytes: int = 512 * 1024 * 1024
    import_timeout_seconds: float = 900
    resource_dir: Path = PROJECT_ROOT / "data" / "resources"
    allowed_origins: tuple[str, ...] = (
        "http://127.0.0.1:5173", "http://localhost:5173",
        "http://127.0.0.1:8000", "http://localhost:8000",
    )

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            data_dir=Path(os.environ.get("DLP_DATA_DIR", PROJECT_ROOT / "data")).resolve(),
            max_upload_bytes=int(os.environ.get("DLP_MAX_UPLOAD_MB", "512")) * 1024 * 1024,
            ffprobe=os.environ.get("DLP_FFPROBE", "ffprobe"),
            ffmpeg=os.environ.get("DLP_FFMPEG", "ffmpeg"),
            node=os.environ.get('DLP_NODE', 'node'),
            max_download_bytes=int(os.environ.get("DLP_MAX_DOWNLOAD_MB", "512")) * 1024 * 1024,
            import_timeout_seconds=float(os.environ.get("DLP_IMPORT_TIMEOUT_SECONDS", "900")),
            resource_dir=Path(os.environ.get("DLP_RESOURCE_DIR", PROJECT_ROOT / "data" / "resources")).resolve(),
            **({"allowed_origins": tuple(item.strip() for item in os.environ["DLP_ALLOWED_ORIGINS"].split(",") if item.strip())}
               if "DLP_ALLOWED_ORIGINS" in os.environ else {}),
        )

    @property
    def media_dir(self) -> Path:
        return self.data_dir / "media"
