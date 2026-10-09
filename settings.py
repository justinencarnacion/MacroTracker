import base64
import json
import os
from dataclasses import dataclass
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dotenv import load_dotenv

load_dotenv()


class SettingsError(RuntimeError):
    pass


def load_google_credentials(default_file="credentials.json"):
    """Load the service-account JSON from the environment or a file.

    Checked in order: GOOGLE_CREDENTIALS_JSON (raw JSON),
    GOOGLE_CREDENTIALS_B64 (base64-encoded JSON), then the file at
    GOOGLE_CREDENTIALS_FILE (default: credentials.json).
    """
    raw = os.getenv("GOOGLE_CREDENTIALS_JSON")
    if raw:
        return json.loads(raw)
    encoded = os.getenv("GOOGLE_CREDENTIALS_B64")
    if encoded:
        return json.loads(base64.b64decode(encoded))
    path = os.getenv("GOOGLE_CREDENTIALS_FILE", default_file)
    try:
        with open(path, "r") as f:
            return json.load(f)
    except FileNotFoundError as error:
        raise SettingsError(
            f"Google credentials not found at '{path}'. Set GOOGLE_CREDENTIALS_FILE, "
            "GOOGLE_CREDENTIALS_JSON, or GOOGLE_CREDENTIALS_B64."
        ) from error


def _require(name):
    value = os.getenv(name, "").strip()
    if not value:
        raise SettingsError(f"{name} is required.")
    return value


def _optional_int(name):
    value = os.getenv(name, "").strip()
    if not value:
        return None
    try:
        return int(value)
    except ValueError as error:
        raise SettingsError(f"{name} must be a number, got '{value}'.") from error


def _model_list():
    """GEMINI_MODEL first, then GEMINI_FALLBACK_MODELS, without duplicates."""
    primary = os.getenv("GEMINI_MODEL", "gemini-3.6-flash").strip()
    fallbacks = os.getenv(
        "GEMINI_FALLBACK_MODELS", "gemini-3.5-flash,gemini-3.5-flash-lite"
    )
    models = [primary, *(name.strip() for name in fallbacks.split(","))]
    return tuple(dict.fromkeys(name for name in models if name))


@dataclass(frozen=True)
class Settings:
    discord_token: str
    gemini_api_key: str
    gemini_models: tuple
    google_credentials: dict
    sheet_name: str
    sheet_id: str | None
    default_timezone: str
    allowed_guild_id: int | None
    rate_limit_count: int
    rate_limit_seconds: int

    @classmethod
    def from_env(cls):
        default_timezone = os.getenv("DEFAULT_TIMEZONE", "America/Los_Angeles")
        try:
            ZoneInfo(default_timezone)
        except (ZoneInfoNotFoundError, ValueError) as error:
            raise SettingsError(
                f"DEFAULT_TIMEZONE '{default_timezone}' is not a valid IANA timezone."
            ) from error

        return cls(
            discord_token=_require("DISCORD_TOKEN"),
            gemini_api_key=_require("GEMINI_API_KEY"),
            gemini_models=_model_list(),
            google_credentials=load_google_credentials(),
            sheet_name=os.getenv("GOOGLE_SHEET_NAME", "Macro Tracker"),
            sheet_id=os.getenv("GOOGLE_SHEET_ID") or None,
            default_timezone=default_timezone,
            allowed_guild_id=_optional_int("ALLOWED_GUILD_ID"),
            rate_limit_count=_optional_int("RATE_LIMIT_COUNT") or 10,
            rate_limit_seconds=_optional_int("RATE_LIMIT_SECONDS") or 60,
        )
