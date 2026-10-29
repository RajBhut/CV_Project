import logging
import mimetypes
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import DATA_DIR, MAX_UPLOAD_MB
from app.database import get_db
from app.models import AnalysisJob, Artifact, Video
from app.schemas import ArtifactLink, VideoResponse
from app.services.video_reader import read_metadata
from app.services.storage import relative_data_path, resolve_data_path

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/videos", tags=["videos"])
ALLOWED_EXTENSIONS = {".mp4", ".mov", ".avi"}


def _response(
    video: Video,
    latest_status: str | None = None,
    latest_job_id: str | None = None,
    artifacts: list[ArtifactLink] | None = None,
) -> VideoResponse:
    return VideoResponse(
        id=video.id,
        original_filename=video.original_filename,
        file_size_bytes=video.file_size_bytes,
        duration_seconds=video.duration_seconds,
        width=video.width,
        height=video.height,
        fps=video.fps,
        created_at=video.created_at,
        latest_status=latest_status,
        latest_job_id=latest_job_id,
        file_url=f"/api/videos/{video.id}/file",
        artifacts=artifacts or [],
    )


@router.post("", response_model=VideoResponse, status_code=status.HTTP_201_CREATED)
async def upload_video(file: UploadFile = File(...), db: Session = Depends(get_db)) -> VideoResponse:
    original_name = Path(file.filename or "video").name[:255]
    suffix = Path(original_name).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, "Upload an MP4, MOV, or AVI video file.")
    video_id = str(uuid.uuid4())
    video_dir = DATA_DIR / "videos"
    video_dir.mkdir(parents=True, exist_ok=True)
    destination = video_dir / f"{video_id}{suffix}"
    size = 0
    try:
        with destination.open("wb") as output:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_UPLOAD_MB * 1024 * 1024:
                    raise HTTPException(413, f"Video exceeds the {MAX_UPLOAD_MB} MB upload limit.")
                output.write(chunk)
        if size == 0:
            raise HTTPException(400, "The uploaded file is empty.")
        metadata = read_metadata(destination)
        video = Video(
            id=video_id,
            original_filename=original_name,
            stored_path=relative_data_path(destination),
            file_size_bytes=size,
            duration_seconds=metadata.duration_seconds,
            width=metadata.width,
            height=metadata.height,
            fps=metadata.fps,
        )
        db.add(video)
        db.commit()
        db.refresh(video)
        return _response(video)
    except HTTPException:
        destination.unlink(missing_ok=True)
        raise
    except ValueError as exc:
        destination.unlink(missing_ok=True)
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        logger.exception("Video upload failed")
        destination.unlink(missing_ok=True)
        raise HTTPException(500, "The video could not be saved.") from exc
    finally:
        await file.close()


@router.get("", response_model=list[VideoResponse])
def list_videos(db: Session = Depends(get_db)) -> list[VideoResponse]:
    videos = db.scalars(select(Video).order_by(Video.created_at.desc())).all()
    result = []
    for video in videos:
        latest = db.execute(
            select(AnalysisJob.status, AnalysisJob.id)
            .where(AnalysisJob.video_id == video.id)
            .order_by(AnalysisJob.created_at.desc())
            .limit(1)
        ).first()
        artifact_links: list[ArtifactLink] = []
        if latest:
            artifact_rows = db.scalars(
                select(Artifact).where(Artifact.job_id == latest[1]).order_by(Artifact.created_at.asc())
            ).all()
            artifact_links = [
                ArtifactLink(artifact_type=row.artifact_type, url=f"/api/artifacts/{row.id}/file")
                for row in artifact_rows
            ]
        result.append(
            _response(
                video,
                latest[0] if latest else None,
                latest[1] if latest else None,
                artifact_links,
            )
        )
    return result


@router.get("/{video_id}", response_model=VideoResponse)
def get_video(video_id: str, db: Session = Depends(get_db)) -> VideoResponse:
    video = db.get(Video, video_id)
    if video is None:
        raise HTTPException(404, "Video not found.")
    latest_job = db.scalar(
        select(AnalysisJob).where(AnalysisJob.video_id == video.id)
        .order_by(AnalysisJob.created_at.desc()).limit(1)
    )
    artifact_links: list[ArtifactLink] = []
    if latest_job:
        artifacts = db.scalars(
            select(Artifact).where(Artifact.job_id == latest_job.id).order_by(Artifact.created_at.asc())
        ).all()
        artifact_links = [
            ArtifactLink(artifact_type=row.artifact_type, url=f"/api/artifacts/{row.id}/file")
            for row in artifacts
        ]
    return _response(
        video,
        latest_job.status if latest_job else None,
        latest_job.id if latest_job else None,
        artifact_links,
    )


@router.get("/{video_id}/file")
def video_file(video_id: str, db: Session = Depends(get_db)) -> FileResponse:
    video = db.get(Video, video_id)
    if video is None:
        raise HTTPException(404, "Video not found.")
    try:
        path = resolve_data_path(video.stored_path)
    except ValueError as exc:
        logger.error("Invalid stored path for video %s", video_id)
        raise HTTPException(404, "Video file not found.") from exc
    if not path.is_file():
        raise HTTPException(404, "Video file not found.")
    media_type = mimetypes.guess_type(video.original_filename)[0] or "application/octet-stream"
    return FileResponse(
        path,
        filename=video.original_filename,
        media_type=media_type,
        content_disposition_type="inline",
    )
