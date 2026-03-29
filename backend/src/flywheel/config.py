"""Environment-driven configuration using Pydantic Settings."""

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    flywheel_backend: str = "flatfile"
    database_url: str = "postgresql+asyncpg://flywheel:flywheel@localhost:5432/flywheel"
    debug: bool = True
    cors_origins: list[str] = ["http://localhost:5173"]

    # Supabase
    supabase_url: str = ""
    supabase_service_key: str = Field(
        "",
        validation_alias=AliasChoices(
            "SUPABASE_SERVICE_KEY",
            "SUPABASE_SERVICE_ROLE_KEY",
            "supabase_service_key",
        ),
    )
    supabase_jwt_secret: str = ""

    # BYOK encryption (base64-encoded 32-byte AES-256 key)
    encryption_key: str = ""

    # Rate limiting
    rate_limit_magic_link: str = "3/hour"
    rate_limit_default: str = "60/minute"

    # Subsidized API key for anonymous onboarding (~$0.50/trial)
    flywheel_subsidy_api_key: str = ""

    # Email (Resend)
    resend_api_key: str = ""  # empty = email disabled, log instead
    email_domain: str = "flywheel.app"  # verified domain in Resend

    # Frontend URL (for email links)
    frontend_url: str = "http://localhost:5173"

    # Google Calendar OAuth
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:5173/api/v1/integrations/google-calendar/callback"

    # Google Gmail OAuth (same Google Cloud project, separate scope)
    google_gmail_redirect_uri: str = "http://localhost:5173/api/v1/integrations/gmail/callback"

    # Google Gmail Read OAuth (separate credential from send-only gmail)
    google_gmail_read_redirect_uri: str = "http://localhost:5173/api/v1/integrations/gmail-read/callback"

    # Microsoft Outlook OAuth (Azure AD app registration)
    microsoft_client_id: str = ""
    microsoft_client_secret: str = ""
    microsoft_redirect_uri: str = "http://localhost:5173/api/v1/integrations/outlook/callback"

    # Slack OAuth (workspace install via Events API)
    slack_client_id: str = ""
    slack_client_secret: str = ""
    slack_signing_secret: str = ""
    slack_redirect_uri: str = "http://localhost:5173/api/v1/integrations/slack/callback"

    # External APIs
    tavily_api_key: str = ""  # empty = web search disabled

    # Production deployment
    environment: str = "development"  # development, staging, production
    sentry_dsn: str = ""  # empty = disabled

    # Email drafting
    draft_visibility_delay_days: int = 0  # 0 = immediate visibility for dogfood

    # Feedback flywheel — voice update
    voice_update_min_edits: int = 1  # minimum edit count before voice update triggers (1 = every edit)

    # Feedback flywheel — dismiss signal
    dismiss_lookback_days: int = 30  # rolling window for dismiss signal (days)
    dismiss_threshold: int = 3  # minimum dismissals to trigger scoring signal

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
