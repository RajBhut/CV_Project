from pathlib import Path

from app.config import DATA_DIR


def relative_data_path(path: Path) -> str:
    """Return a persisted path relative to the configured local data directory."""
    return path.resolve().relative_to(DATA_DIR).as_posix()


def resolve_data_path(stored_path: str) -> Path:
    candidate = Path(stored_path)
    resolved = (candidate if candidate.is_absolute() else DATA_DIR / candidate).resolve()
    try:
        resolved.relative_to(DATA_DIR)
    except ValueError as exc:
        raise ValueError("Stored path is outside the local data directory.") from exc
    return resolved
