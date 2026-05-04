"""Async Last.fm API client with basic TTL caching."""

from __future__ import annotations

import time
from collections.abc import Callable

from aiohttp import ClientSession


class TTLCache:
    """Tiny TTL cache helper."""

    def __init__(self, ttl_seconds: int) -> None:
        self._ttl_seconds = ttl_seconds
        self._store: dict[str, tuple[float, object]] = {}

    def get(self, key: str) -> object | None:
        item = self._store.get(key)
        if not item:
            return None
        expires_at, payload = item
        if expires_at < time.monotonic():
            self._store.pop(key, None)
            return None
        return payload

    def set(self, key: str, payload: object) -> None:
        self._store[key] = (time.monotonic() + self._ttl_seconds, payload)


class LastFmApiClient:
    """Client for Last.fm endpoints used by the integration."""

    def __init__(
        self,
        session: ClientSession,
        api_key: str,
        cache_ttl_seconds: int = 24 * 60 * 60,
    ) -> None:
        self._session = session
        self._api_key = api_key
        self._cache = TTLCache(cache_ttl_seconds)

    async def artist_get_similar(self, artist: str, limit: int = 20) -> list[dict]:
        cache_key = f"similar::{artist.lower()}::{limit}"

        async def _fetch() -> list[dict]:
            data = await self._request(
                method="artist.getSimilar",
                artist=artist,
                limit=str(limit),
            )
            artists = data.get("similarartists", {}).get("artist", [])
            return artists if isinstance(artists, list) else []

        return await self._get_or_fetch(cache_key, _fetch)

    async def artist_get_top_albums(self, artist: str, limit: int = 30) -> list[dict]:
        cache_key = f"topalbums::{artist.lower()}::{limit}"

        async def _fetch() -> list[dict]:
            data = await self._request(
                method="artist.getTopAlbums",
                artist=artist,
                limit=str(limit),
            )
            albums = data.get("topalbums", {}).get("album", [])
            return albums if isinstance(albums, list) else []

        return await self._get_or_fetch(cache_key, _fetch)

    async def _get_or_fetch(self, key: str, fetcher: Callable[[], object]) -> object:
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        payload = await fetcher()
        self._cache.set(key, payload)
        return payload

    async def _request(self, **params: str) -> dict:
        query = {
            "api_key": self._api_key,
            "format": "json",
            **params,
        }
        async with self._session.get("https://ws.audioscrobbler.com/2.0/", params=query) as resp:
            resp.raise_for_status()
            data = await resp.json()
            return data if isinstance(data, dict) else {}
