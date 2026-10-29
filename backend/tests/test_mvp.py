from datetime import datetime

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app
from app.models import AnalysisJob, Event, Video
from app.services.video_reader import read_metadata


@pytest.fixture
def test_database(tmp_path):
    engine = create_engine(
        f"sqlite:///{(tmp_path / 'test.sqlite3').as_posix()}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    try:
        yield session_factory
    finally:
        engine.dispose()


@pytest.fixture
def client(test_database):
    def override_get_db():
        with test_database() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def add_video_and_job(session_factory):
    with session_factory() as db:
        video = Video(
            id="test-video",
            original_filename="clip.mp4",
            stored_path="clip.mp4",
            file_size_bytes=123,
            duration_seconds=4,
            width=640,
            height=360,
            fps=30,
        )
        job = AnalysisJob(
            id="test-job",
            video_id=video.id,
            status="queued",
            model_name="yolo11n.pt",
            settings_json='{"sample_fps": 2}',
        )
        db.add_all([video, job])
        db.commit()


def test_upload_validation_returns_friendly_errors(client):
    unsupported = client.post(
        "/api/videos", files={"file": ("notes.txt", b"not a video", "text/plain")}
    )
    assert unsupported.status_code == 400
    assert unsupported.json()["detail"] == "Upload an MP4, MOV, or AVI video file."

    corrupt = client.post(
        "/api/videos", files={"file": ("broken.mp4", b"not a video", "video/mp4")}
    )
    assert corrupt.status_code == 400
    assert "readable video" in corrupt.json()["detail"]


def test_video_metadata_extraction(tmp_path):
    path = tmp_path / "generated.mp4"
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 10, (64, 48))
    if not writer.isOpened():
        pytest.skip("OpenCV MP4 writer is unavailable on this machine")
    for _ in range(20):
        writer.write(np.zeros((48, 64, 3), dtype=np.uint8))
    writer.release()

    metadata = read_metadata(path)
    assert metadata.frame_count == 20
    assert metadata.width == 64
    assert metadata.height == 48
    assert metadata.duration_seconds == pytest.approx(2.0, abs=0.15)


def test_job_state_transitions_persist(test_database):
    add_video_and_job(test_database)
    with test_database() as db:
        job = db.get(AnalysisJob, "test-job")
        assert job is not None and job.status == "queued"
        job.status = "processing"
        job.frames_total = 4
        job.frames_processed = 2
        job.progress = 50
        db.commit()
        job.status = "completed"
        job.frames_processed = 4
        job.progress = 100
        job.completed_at = datetime.utcnow()
        db.commit()
    with test_database() as db:
        job = db.get(AnalysisJob, "test-job")
        assert job is not None
        assert (job.status, job.progress, job.frames_processed) == ("completed", 100, 4)


def test_event_filtering_by_class_and_confidence(client, test_database):
    add_video_and_job(test_database)
    with test_database() as db:
        db.add_all(
            [
                Event(job_id="test-job", timestamp_seconds=1, frame_index=30, class_id=0,
                      class_name="person", confidence=0.8, x1=1, y1=2, x2=30, y2=40),
                Event(job_id="test-job", timestamp_seconds=2, frame_index=60, class_id=0,
                      class_name="person", confidence=0.3, x1=1, y1=2, x2=30, y2=40),
                Event(job_id="test-job", timestamp_seconds=3, frame_index=90, class_id=2,
                      class_name="car", confidence=0.9, x1=1, y1=2, x2=30, y2=40),
            ]
        )
        db.commit()

    response = client.get(
        "/api/jobs/test-job/events",
        params={"class_name": "person", "min_confidence": 0.7, "sort": "asc"},
    )
    assert response.status_code == 200
    events = response.json()
    assert len(events) == 1
    assert events[0]["class_name"] == "person"
    assert events[0]["timestamp_seconds"] == 1
