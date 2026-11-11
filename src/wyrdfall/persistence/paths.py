from pathlib import Path

import platformdirs

APP_NAME = "Wyrdfall"
APP_AUTHOR = "Wyrdfall"


def save_dir() -> Path:
    path = Path(platformdirs.user_data_dir(APP_NAME, APP_AUTHOR))
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_db_path() -> Path:
    return save_dir() / "wyrdfall.db"
