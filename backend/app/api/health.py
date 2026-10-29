from fastapi import APIRouter

from app.config import MODEL_NAME
from app.services.detector import device_description, model_loaded

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str | bool]:
    """Return service liveness without triggering model initialization."""
    return {"status": "ok", "model_loaded": model_loaded(), "model_name": MODEL_NAME}


@router.get("/system")
def system() -> dict[str, bool | str | None]:
    cuda_available, device_name, device, warning = device_description()
    return {
        "cuda_available": cuda_available,
        "device_name": device_name,
        "model_name": MODEL_NAME,
        "inference_device": device,
        "warning": warning,
    }
