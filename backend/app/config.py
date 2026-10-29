from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    google_cloud_project: str = ""
    google_cloud_location: str = "us-central1"
    gemini_model: str = ""
    gemini_chat_model: str = ""
    gemini_synthesis_model: str = ""
    gemini_research_model: str = ""
    research_timeout_seconds: float = 240
    research_search_timeout_seconds: float = 150
    research_synthesis_timeout_seconds: float = 75
    research_excerpt_timeout_seconds: float = 4
    chat_timeout_seconds: float = 180
    clarification_intent_timeout_seconds: float = 60
    clarification_reply_timeout_seconds: float = 90
    gemini_research_thinking_level: str = "low"
    database_url: str = "sqlite:///./integration_copilot.db"
    mongodb_uri: str = ""
    mongodb_database: str = "integration_copilot"
    frontend_url: str = "http://localhost:3000"
    cookie_secure: bool = False
    guide_freshness_days: int = 30
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[1] / ".env", extra="ignore"
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls,
        init_settings,
        env_settings,
        dotenv_settings,
        file_secret_settings,
    ):
        # An explicit local file is authoritative over inherited desktop/shell
        # settings. Deployments without that file continue to use environment vars.
        return init_settings, dotenv_settings, env_settings, file_secret_settings


settings = Settings()
