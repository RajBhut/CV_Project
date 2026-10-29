from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.config import CONFIDENCE_THRESHOLD, IMAGE_SIZE, SAMPLE_FPS


class ArtifactLink(BaseModel):
    artifact_type: str
    url: str


class VideoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    original_filename: str
    file_size_bytes: int
    duration_seconds: float | None
    width: int | None
    height: int | None
    fps: float | None
    created_at: datetime
    latest_status: str | None = None
    latest_job_id: str | None = None
    file_url: str
    artifacts: list[ArtifactLink] = Field(default_factory=list)


class JobCreate(BaseModel):
    video_id: str
    sample_fps: float = Field(default=SAMPLE_FPS, ge=0.1, le=30)
    confidence_threshold: float = Field(default=CONFIDENCE_THRESHOLD, ge=0.05, le=0.95)
    image_size: int = Field(default=IMAGE_SIZE, ge=320, le=640)
    enable_tracking: bool = True


class JobAccepted(BaseModel):
    job_id: str
    status: str


class JobResponse(BaseModel):
    job_id: str
    video_id: str
    status: str
    progress: float
    frames_total: int | None
    frames_processed: int
    model_name: str
    settings: dict
    error: str | None = None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    detections_count: int
    class_counts: dict[str, int]
    annotated_video_available: bool


class EventResponse(BaseModel):
    id: int
    timestamp_seconds: float
    frame_index: int
    class_id: int
    class_name: str
    confidence: float
    bbox: dict[str, float]
    track_id: int | None
    thumbnail_url: str | None


class ArtifactResponse(BaseModel):
    artifact_type: str
    url: str
    created_at: datetime
