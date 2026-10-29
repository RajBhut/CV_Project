import json
import logging
import math
from datetime import datetime
from pathlib import Path

import cv2
from sqlalchemy import select

from app.config import DATA_DIR
from app.database import SessionLocal
from app.models import AnalysisJob, Artifact, Event, Video
from app.services.detector import get_model, inference_device
from app.services.storage import relative_data_path, resolve_data_path
from app.services.video_reader import iter_sampled_frames

logger = logging.getLogger(__name__)


def _make_writer(output_dir: Path, width: int, height: int, sample_fps: float):
    webm_path = output_dir / "annotated.webm"
    writer = cv2.VideoWriter(
        str(webm_path), cv2.VideoWriter_fourcc(*"VP80"), sample_fps, (width, height)
    )
    if writer.isOpened():
        return writer, webm_path
    writer.release()

    mp4_path = output_dir / "annotated.mp4"
    writer = cv2.VideoWriter(
        str(mp4_path), cv2.VideoWriter_fourcc(*"mp4v"), sample_fps, (width, height)
    )
    if writer.isOpened():
        return writer, mp4_path
    writer.release()
    return None, None


def _write_thumbnail(frame, box, destination: Path) -> bool:
    height, width = frame.shape[:2]
    x1, y1, x2, y2 = (int(round(v)) for v in box)
    pad_x, pad_y = max(8, (x2 - x1) // 8), max(8, (y2 - y1) // 8)
    x1, x2 = max(0, x1 - pad_x), min(width, x2 + pad_x)
    y1, y2 = max(0, y1 - pad_y), min(height, y2 + pad_y)
    crop = frame[y1:y2, x1:x2]
    if crop.size == 0:
        crop = frame
    return bool(cv2.imwrite(str(destination), crop))


def run_analysis(job_id: str) -> None:
    """Run one job sequentially in the single-worker executor."""
    with SessionLocal() as db:
        job = db.get(AnalysisJob, job_id)
        if job is None:
            logger.error("Queued job %s no longer exists", job_id)
            return
        video = db.get(Video, job.video_id)
        if video is None:
            job.status = "failed"
            job.error_message = "The source video is no longer available."
            job.completed_at = datetime.utcnow()
            db.commit()
            return

        try:
            source_path = resolve_data_path(video.stored_path)
        except ValueError:
            logger.exception("Unsafe video path for job %s", job_id)
            job.status = "failed"
            job.error_message = "The source video could not be found in local storage."
            job.completed_at = datetime.utcnow()
            db.commit()
            return
        settings = json.loads(job.settings_json)
        sample_fps = settings["sample_fps"]
        job.status = "processing"
        job.started_at = datetime.utcnow()
        db.commit()

        output_dir = DATA_DIR / "jobs" / job_id
        output_dir.mkdir(parents=True, exist_ok=True)
        writer = None
        preview_path = None
        preview_attempted = False
        output_error_logged = False
        try:
            estimated = max(
                1,
                math.ceil((video.duration_seconds or 0) * sample_fps),
            )
            job.frames_total = estimated
            db.commit()
            model = get_model()
            predictor = getattr(model, "predictor", None)
            for tracker in getattr(predictor, "trackers", []):
                tracker.reset()

            processed = 0
            for frame_index, timestamp, frame in iter_sampled_frames(source_path, sample_fps):
                height, width = frame.shape[:2]
                if not preview_attempted:
                    preview_attempted = True
                    writer, preview_path = _make_writer(output_dir, width, height, sample_fps)
                    if writer is None and not output_error_logged:
                        logger.warning("Could not create preview writer for job %s", job_id)
                        output_error_logged = True

                predict_args = {
                    "source": frame,
                    "imgsz": settings["image_size"],
                    "conf": settings["confidence_threshold"],
                    "device": inference_device(),
                    "verbose": False,
                }
                if settings.get("enable_tracking", True):
                    result = model.track(
                        **predict_args, persist=True, tracker="bytetrack.yaml"
                    )[0]
                else:
                    result = model.predict(**predict_args)[0]

                annotated = result.plot()
                if writer is not None:
                    writer.write(annotated)

                boxes = result.boxes
                coords = boxes.xyxy.cpu().tolist() if boxes is not None else []
                classes = boxes.cls.cpu().tolist() if boxes is not None else []
                confidences = boxes.conf.cpu().tolist() if boxes is not None else []
                ids = boxes.id.int().cpu().tolist() if boxes is not None and boxes.id is not None else []
                names = result.names
                for index, box in enumerate(coords):
                    thumbnail_path = output_dir / "thumbnails" / f"{processed:06d}-{index:03d}.jpg"
                    thumbnail_path.parent.mkdir(parents=True, exist_ok=True)
                    thumb_saved = _write_thumbnail(frame, box, thumbnail_path)
                    class_id = int(classes[index])
                    db.add(
                        Event(
                            job_id=job_id,
                            timestamp_seconds=timestamp,
                            frame_index=frame_index,
                            class_id=class_id,
                            class_name=str(names[class_id]),
                            confidence=float(confidences[index]),
                            x1=float(box[0]),
                            y1=float(box[1]),
                            x2=float(box[2]),
                            y2=float(box[3]),
                            track_id=int(ids[index]) if index < len(ids) else None,
                            thumbnail_path=relative_data_path(thumbnail_path) if thumb_saved else None,
                        )
                    )

                processed += 1
                job.frames_processed = processed
                job.progress = min(99.0, processed / estimated * 100)
                db.commit()

            if processed == 0:
                raise ValueError("No video frames could be decoded for analysis.")
            if writer is not None:
                writer.release()
                writer = None
            if preview_path is not None and preview_path.is_file() and preview_path.stat().st_size > 0:
                db.add(
                    Artifact(
                        job_id=job_id,
                        artifact_type="annotated_video",
                        stored_path=relative_data_path(preview_path),
                    )
                )
            elif preview_path is not None:
                logger.warning("Preview output was empty for job %s", job_id)

            job.status = "completed"
            job.progress = 100
            job.completed_at = datetime.utcnow()
            db.commit()
        except Exception as exc:
            if writer is not None:
                writer.release()
            logger.exception("Analysis failed for job %s", job_id)
            job.status = "failed"
            job.error_message = "Video analysis failed. Check the backend log for details."
            job.completed_at = datetime.utcnow()
            db.commit()
