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
    # Default uses postgres user with trust auth (configured in Novita sandbox via start-services.sh)
    database_url: str = os.getenv(
        "DATABASE_URL", "postgresql://postgres@localhost/cloudagent"
    )

    # Celery
    celery_broker_url: str = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379")

    # Sandbox
    novita_api_key: str | None = os.getenv("NOVITA_API_KEY")

    # Claude
    system_anthropic_api_key: str | None = os.getenv("SYSTEM_ANTHROPIC_API_KEY")
    system_github_token: str | None = os.getenv("SYSTEM_GITHUB_TOKEN")

    # Timeouts (in seconds)
    sandbox_timeout: int = int(os.getenv("SANDBOX_TIMEOUT", "600"))  # 10 minutes
    claude_code_timeout: int = int(os.getenv("CLAUDE_CODE_TIMEOUT", "300"))  # 5 minutes


settings = Settings()
