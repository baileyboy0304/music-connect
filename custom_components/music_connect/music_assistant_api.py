"""Async Music Assistant API client."""

from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit

from aiohttp import ClientSession
from aiohttp.client_exceptions import ClientResponseError


class MusicAssistantApiClient:
    """Client for the Music Assistant command API."""

    def __init__(self, session: ClientSession, base_url: str, token: str) -> None:
        self._session = session
        self._base_url = self._normalize_base_url(base_url)
        self._token = token.strip()

    @staticmethod
    def _normalize_base_url(base_url: str) -> str:
        raw = base_url.strip()
        if not raw.startswith(("http://", "https://")):
            raw = f"http://{raw}"

        parsed = urlsplit(raw)
        netloc = parsed.netloc
        if parsed.port is None and parsed.hostname:
            netloc = f"{parsed.hostname}:8095"

        path = parsed.path.rstrip("/")
        if not path:
            path = "/api"

        return urlunsplit((parsed.scheme, netloc, path, parsed.query, parsed.fragment))

    async def players_all(self) -> list[dict]:
        data = await self._post_command({"command": "players/all"})
        return data if isinstance(data, list) else []

    async def search(self, search_query: str) -> dict:
        payload = {
            "command": "music/search",
            "args": {
                "search_query": search_query,
                "media_types": ["artist", "album", "track"],
                "limit": 30,
            },
        }
        data = await self._post_command(payload)
        return data if isinstance(data, dict) else {"result": data}

    async def play_media(self, player_id: str, media_uri: str) -> dict:
        payload = {
            "command": "player_queues/play_media",
            "args": {
                "queue_id": player_id,
                "media": [media_uri],
            },
        }
        data = await self._post_command(payload)
        return data if isinstance(data, dict) else {"result": data}

    async def album_tracks(self, album_uri: str) -> list[dict]:
        attempts = [
            {"command": "music/album/tracks", "args": {"album_uri": album_uri}},
            {"command": "music/albums/tracks", "args": {"album_uri": album_uri}},
            {"command": "music/album/tracks", "args": {"uri": album_uri}},
            {"command": "music/albums/tracks", "args": {"uri": album_uri}},
        ]
        last_error: Exception | None = None
        for payload in attempts:
            try:
                data = await self._post_command(payload)
                if isinstance(data, list):
                    return data
                if isinstance(data, dict):
                    tracks = data.get("tracks")
                    if isinstance(tracks, list):
                        return tracks
            except ClientResponseError as err:
                last_error = err
                continue
        if last_error:
            raise last_error
        return []

    async def _post_command(self, payload: dict) -> object:
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }
        async with self._session.post(self._base_url, json=payload, headers=headers) as resp:
            resp.raise_for_status()
            return await resp.json()
