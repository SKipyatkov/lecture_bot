import os
from pathlib import Path

# lecture_bot/ — на два уровня выше bot/core/
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _under_root(value: str) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path


DATA_DIR = _under_root(os.getenv("DATA_DIR", "data"))
LOG_DIR = DATA_DIR / "logs"
CACHE_DIR = DATA_DIR / "cache"
BACKUP_DIR = DATA_DIR / "backups"
TEMP_DIR = DATA_DIR / "temp"
