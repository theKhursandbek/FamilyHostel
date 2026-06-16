"""Bot configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class BotConfig:
    """All knobs the bot needs at startup."""

    env: str                   # "prod" | "staging"
    token: str                 # bot token for the chosen env
    api_base_url: str          # e.g. https://api.familyhostel.uz/api/v1
    mini_app_url: str          # https://mini.familyhostel.uz?env=prod
    mini_app_short_name: str   # bot's WebApp short name (BotFather)
    request_timeout: float = 10.0

    @staticmethod
    def from_env() -> "BotConfig":
        env = os.environ.get("TELEGRAM_BOT_ENV", "staging").lower()
        if env not in ("prod", "staging"):
            raise SystemExit(f"TELEGRAM_BOT_ENV must be prod|staging (got {env!r})")

        token_var = "TELEGRAM_BOT_TOKEN_PROD" if env == "prod" else "TELEGRAM_BOT_TOKEN_STAGING"
        token = os.environ.get(token_var, "").strip()
        if not token:
            raise SystemExit(f"{token_var} env var is required for env={env}")

        api_base = os.environ.get(
            "BACKEND_API_URL", "http://localhost:8000/api/v1"
        ).rstrip("/")
        mini_app_url = os.environ.get(
            "MINI_APP_URL", f"https://example.com/?env={env}"
        )
        mini_app_short_name = os.environ.get("MINI_APP_SHORT_NAME", "app")
        return BotConfig(
            env=env,
            token=token,
            api_base_url=api_base,
            mini_app_url=mini_app_url,
            mini_app_short_name=mini_app_short_name,
        )
