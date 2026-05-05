"""Async Music Assistant API client."""

from __future__ import annotations

from aiohttp import ClientSession
from urllib.parse import urlsplit, urlunsplit


class MusicAssistantApiClient:
    """Client for the Music Assistant command API."""

    def __init__(self, session: ClientSession, base_url: str, token: str) -> None:
        self._session = session
        self._base_url = self._normalize_base_url(base_url)
        self._token = token


    @staticmethod
    def _normalize_base_url(base_url: str) -> str:
        raw = base_url.strip()
        if not raw.startswith(("http://", "https://")):
            raw = f"http://{raw}"

        parsed = urlsplit(raw)
        path = parsed.path.rstrip("/")
        if not path:
            path = "/api"

        return urlunsplit((parsed.scheme, parsed.netloc, path, parsed.query, parsed.fragment))

    async def players_all(self) -> list[dict]:
        """Fetch all players from Music Assistant."""
        payload = {"command": "players/all"}
        data = await self._post_command(payload)
        if isinstance(data, list):
            return data
        return []

    async def search(self, search_query: str) -> dict:
        """Search Music Assistant library."""
        payload = {
            "command": "music/search",
            "args": {
                "search_query": search_query,
                "media_types": ["artist", "album", "track"],
                "limit": 30,
            },
        }
        data = await self._post_command(payload)
        if isinstance(data, dict):
            return data
        return {"result": data}

    async def _post_command(self, payload: dict) -> object:
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }
        async with self._session.post(self._base_url, json=payload, headers=headers) as resp:
            resp.raise_for_status()
            return await resp.json()
