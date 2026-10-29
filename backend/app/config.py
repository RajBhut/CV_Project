import os
from pathlib import Path


APP_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("SCENETRACE_DATA_DIR", str(APP_DIR / "data"))).resolve()
DATABASE_URL = f"sqlite:///{(DATA_DIR / 'scenetrace.sqlite3').as_posix()}"
FRONTEND_ORIGIN = os.getenv("SCENETRACE_FRONTEND_ORIGIN", "http://localhost:5173")
MODEL_NAME = os.getenv("SCENETRACE_MODEL_NAME", "yolo11n.pt")
MAX_UPLOAD_MB = int(os.getenv("SCENETRACE_MAX_UPLOAD_MB", "200"))
SAMPLE_FPS = float(os.getenv("SCENETRACE_SAMPLE_FPS", "2"))
CONFIDENCE_THRESHOLD = float(os.getenv("SCENETRACE_CONFIDENCE_THRESHOLD", "0.4"))
IMAGE_SIZE = int(os.getenv("SCENETRACE_IMAGE_SIZE", "640"))
