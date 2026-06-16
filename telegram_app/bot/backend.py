"""Async HTTP client for the Hotel backend used by the bot."""

from __future__ import annotations

from typing import Any

import httpx

from .config import BotConfig


class BackendClient:
    """Thin wrapper around the backend Mini App OTP endpoints."""

    def __init__(self, config: BotConfig) -> None:
        self._config = config
        self._headers = {
            "X-Telegram-Bot-Env": config.env,
            "User-Agent": f"hotel-bot/{config.env}",
        }

    async def _request(self, method: str, path: str, *, json: dict | None = None) -> httpx.Response:
        url = f"{self._config.api_base_url}{path}"
        async with httpx.AsyncClient(timeout=self._config.request_timeout) as client:
            return await client.request(method, url, json=json, headers=self._headers)

    async def start_otp(self, phone: str) -> tuple[bool, dict[str, Any]]:
        response = await self._request("POST", "/auth/telegram/phone/start/", json={"phone": phone})
        return response.is_success, response.json() if response.content else {}

    async def verify_otp(self, phone: str, code: str) -> tuple[bool, dict[str, Any]]:
        response = await self._request(
            "POST",
            "/auth/telegram/phone/verify/",
            json={"phone": phone, "code": code},
        )
        return response.is_success, response.json() if response.content else {}
