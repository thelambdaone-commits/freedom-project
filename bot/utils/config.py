from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    telegram_bot_token: str = ""
    allowed_user_id: int = 0

    gmail_client_id: str = ""
    gmail_client_secret: str = ""
    gmail_redirect_uri: str = "http://localhost:8080"

    cloudflare_api_token: str = ""

    github_token: str = ""
    github_account_token: str = ""

    digitalplat_dashboard_url: str = "https://dash.domain.digitalplat.org"

    default_llm_provider: str = "auto"
    ollama_base_url: str = "http://localhost:11434"
    openrouter_api_key: str = ""
    groq_api_key: str = ""

    database_path: str = "data/bot.db"
    fernet_key: str = ""

    @property
    def is_telegram_configured(self) -> bool:
        return bool(self.telegram_bot_token)

    @property
    def is_gmail_configured(self) -> bool:
        return bool(self.gmail_client_id and self.gmail_client_secret)

    @property
    def is_cloudflare_configured(self) -> bool:
        return bool(self.cloudflare_api_token)

    @property
    def is_github_configured(self) -> bool:
        return bool(self.github_token or self.github_account_token)

    @property
    def is_encryption_configured(self) -> bool:
        return bool(self.fernet_key)

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
