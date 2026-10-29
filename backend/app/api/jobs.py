import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import MODEL_NAME
from app.database import get_db
from app.models import AnalysisJob, Artifact, Event, Video
from app.schemas import ArtifactResponse, EventResponse, JobAccepted, JobCreate, JobResponse
from app.services.storage import resolve_data_path
from app.services.job_manager import enqueue

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _job_response(job: AnalysisJob, db: Session) -> JobResponse:
    grouped = db.execute(
        select(Event.class_name, func.count(Event.id))
        .where(Event.job_id == job.id)
        .group_by(Event.class_name)
    ).all()
    count = db.scalar(select(func.count(Event.id)).where(Event.job_id == job.id)) or 0
    preview = db.scalar(
        select(func.count(Artifact.id)).where(
            Artifact.job_id == job.id, Artifact.artifact_type == "annotated_video"
        )
    ) or 0
    return JobResponse(
        job_id=job.id,
        video_id=job.video_id,
        status=job.status,
        progress=job.progress,
        frames_total=job.frames_total,
        frames_processed=job.frames_processed,
        model_name=job.model_name,
        settings=json.loads(job.settings_json),
        error=job.error_message,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        detections_count=count,
        class_counts={name: n for name, n in grouped},
        annotated_video_available=bool(preview),
    )


@router.post("", response_model=JobAccepted, status_code=status.HTTP_202_ACCEPTED)
def create_job(payload: JobCreate, db: Session = Depends(get_db)) -> JobAccepted:
    video = db.get(Video, payload.video_id)
    if video is None:
        raise HTTPException(404, "Video not found.")
    job = AnalysisJob(
        id=str(uuid.uuid4()),
        video_id=video.id,
        status="queued",
        model_name=MODEL_NAME,
        settings_json=payload.model_dump_json(exclude={"video_id"}),
    )
    db.add(job)
    db.commit()
    enqueue(job.id)
    return JobAccepted(job_id=job.id, status=job.status)


@router.get("/{job_id}", response_model=JobResponse)
def get_job(job_id: str, db: Session = Depends(get_db)) -> JobResponse:
    job = db.get(AnalysisJob, job_id)
    if job is None:
        raise HTTPException(404, "Analysis job not found.")
    return _job_response(job, db)


@router.get("/{job_id}/events", response_model=list[EventResponse])
def list_events(
    job_id: str,
    class_name: str | None = None,
    min_confidence: float = Query(default=0, ge=0, le=1),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    sort: str = Query(default="asc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
) -> list[EventResponse]:
    if db.get(AnalysisJob, job_id) is None:
        raise HTTPException(404, "Analysis job not found.")
    query = select(Event).where(
        Event.job_id == job_id,
        Event.confidence >= min_confidence,
    )
    if class_name:
        query = query.where(Event.class_name == class_name)
    ordering = Event.timestamp_seconds.asc() if sort == "asc" else Event.timestamp_seconds.desc()
    events = db.scalars(query.order_by(ordering, Event.id.asc()).offset(offset).limit(limit)).all()
    return [
        EventResponse(
            id=event.id,
            timestamp_seconds=event.timestamp_seconds,
            frame_index=event.frame_index,
            class_id=event.class_id,
            class_name=event.class_name,
            confidence=event.confidence,
            bbox={"x1": event.x1, "y1": event.y1, "x2": event.x2, "y2": event.y2},
            track_id=event.track_id,
            thumbnail_url=(
                f"/api/jobs/{job_id}/events/{event.id}/thumbnail"
                if event.thumbnail_path
                else None
            ),
        )
        for event in events
    ]


@router.get("/{job_id}/events/{event_id}/thumbnail")
def event_thumbnail(job_id: str, event_id: int, db: Session = Depends(get_db)) -> FileResponse:
    event = db.scalar(
        select(Event).where(Event.id == event_id, Event.job_id == job_id)
    )
    if event is None or not event.thumbnail_path:
        raise HTTPException(404, "Event thumbnail not found.")
    try:
        path = resolve_data_path(event.thumbnail_path)
    except ValueError as exc:
        raise HTTPException(404, "Event thumbnail not found.") from exc
    if not path.is_file():
        raise HTTPException(404, "Event thumbnail not found.")
    return FileResponse(path, media_type="image/jpeg")


@router.get("/{job_id}/artifacts", response_model=list[ArtifactResponse])
def list_artifacts(job_id: str, db: Session = Depends(get_db)) -> list[ArtifactResponse]:
    if db.get(AnalysisJob, job_id) is None:
        raise HTTPException(404, "Analysis job not found.")
    artifacts = db.scalars(
        select(Artifact).where(Artifact.job_id == job_id).order_by(Artifact.created_at.asc())
    ).all()
    return [
        ArtifactResponse(
            artifact_type=artifact.artifact_type,
            url=f"/api/artifacts/{artifact.id}/file",
            created_at=artifact.created_at,
        )
        for artifact in artifacts
    ]
