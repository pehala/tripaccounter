"""Application settings loaded from environment variables."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-backed configuration for the database, the static files, and this build."""

    model_config = SettingsConfigDict(env_prefix="TA_")

    database_url: str = "sqlite:///./dev.db"
    static_dir: Path = Path(__file__).resolve().parent.parent / "static"

    # Identity of this build — an image tag, a git sha, any string unique per build.
    # Set, the static assets are mounted under `/s/{build_id}/`, so a proxy can cache
    # them permanently; unset, they are served unversioned at `/`, which is what the
    # dev server wants. See DEPLOY.md.
    build_id: str = ""
