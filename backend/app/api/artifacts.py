import mimetypes

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Artifact
from app.services.storage import resolve_data_path

router = APIRouter(prefix="/artifacts", tags=["artifacts"])


@router.get("/{artifact_id}/file")
def artifact_file(artifact_id: int, db: Session = Depends(get_db)) -> FileResponse:
    artifact = db.get(Artifact, artifact_id)
    if artifact is None:
        raise HTTPException(404, "Artifact not found.")
    try:
        path = resolve_data_path(artifact.stored_path)
    except ValueError as exc:
        raise HTTPException(404, "Artifact not found.") from exc
    if not path.is_file():
        raise HTTPException(404, "Artifact file not found.")
    media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return FileResponse(
        path,
        filename=path.name,
        media_type=media_type,
        content_disposition_type="inline",
    )
