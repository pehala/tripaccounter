"""Application settings loaded from environment variables."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-backed configuration for the database, the static files, and this build."""

    model_config = SettingsConfigDict(env_prefix="TA_")

    database_url: str = "sqlite:///./dev.db"
    static_dir: Path = Path(__file__).resolve().parent.parent / "static"

    # Image tag / git sha; empty for dev. Drives the asset mount in app/main.py — see DEPLOY.md.
    build_id: str = ""
