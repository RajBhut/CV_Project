from functools import lru_cache
from threading import Lock

import torch
from ultralytics import YOLO

from app.config import MODEL_NAME

_load_lock = Lock()


def inference_device() -> str:
    return "0" if torch.cuda.is_available() else "cpu"


def device_description() -> tuple[bool, str | None, str, str | None]:
    if torch.cuda.is_available():
        name = torch.cuda.get_device_name(0)
        return True, name, "cuda:0", None
    return False, None, "cpu", "CUDA is unavailable; inference will use the CPU and may be slow."


@lru_cache(maxsize=1)
def _load_model(model_name: str) -> YOLO:
    with _load_lock:
        return YOLO(model_name)


def get_model() -> YOLO:
    return _load_model(MODEL_NAME)


def model_loaded() -> bool:
    return _load_model.cache_info().currsize > 0
