import os
from datetime import UTC, datetime, timedelta
from pathlib import Path


class Settings:
    _ENV_BASE_FOLDER = os.environ.get("BASE_FOLDER")
    BASE_FOLDER = Path(_ENV_BASE_FOLDER) if _ENV_BASE_FOLDER else Path(__file__).parent.parent
    DATA_FOLDER = BASE_FOLDER / "data"


class Defaults:
    RECENT_RANGE = timedelta(days=60)

    RECENT_SINCE = datetime.now(tz=UTC) - RECENT_RANGE
    RECENT_SINCE_STR = RECENT_SINCE.strftime("%Y-%m-%d")

    RECENT_UNTIL = datetime.now(tz=UTC) + timedelta(days=1)
    RECENT_UNTIL_STR = RECENT_UNTIL.strftime("%Y-%m-%d")

    NOW = datetime.now(tz=UTC)

    MIN_UPLOADS = 500
    MIN_EDITS = 2000
    MIN_NOTES = 2000
