"""Application configuration."""

import os

from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()


class Settings(BaseModel):
    """Application settings loaded from environment variables."""

    # Environment
    env: str = os.getenv("APP_ENV", "development")
    api_secret_key: str = os.getenv("API_SECRET_KEY", "dev-secret-key")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    # Database
    database_url: str = os.getenv("DATABASE_URL", "postgresql://localhost/cloudagent")

    # Sandbox
    novita_api_key: str | None = os.getenv("NOVITA_API_KEY")

    # Claude
    system_anthropic_api_key: str | None = os.getenv("SYSTEM_ANTHROPIC_API_KEY")
    system_github_token: str | None = os.getenv("SYSTEM_GITHUB_TOKEN")


settings = Settings()
