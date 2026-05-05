"""Music Connect integration."""

from __future__ import annotations

import logging
import re
import unicodedata
from pathlib import Path

from aiohttp import ClientError, ClientResponseError
from aiohttp.web import Request, Response, json_response
from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import HomeAssistantView, StaticPathConfig
from homeassistant.components.panel_custom import async_register_panel
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_LASTFM_API_KEY,
    CONF_MASS_TOKEN,
    CONF_MASS_URL,
    DOMAIN,
    LASTFM_CACHE_TTL_SECONDS,
    PANEL_ICON,
    PANEL_PATH,
    PANEL_TITLE,
)
from .lastfm_api import LastFmApiClient
from .music_assistant_api import MusicAssistantApiClient

_LOGGER = logging.getLogger(__name__)
_EDITION_RE = re.compile(r"\b(expanded|deluxe|remaster(?:ed)?|anniversary|edition)\b", re.IGNORECASE)


def _normalize_title(value: str) -> str:
    val = unicodedata.normalize("NFKD", (value or "")).lower()
    val = re.sub(r"\([^)]*\)|\[[^]]*\]", " ", val)
    val = _EDITION_RE.sub(" ", val)
    val = re.sub(r"[^a-z0-9]+", " ", val)
    return re.sub(r"\s+", " ", val).strip()


def _artist_matches(active_artist: str, artists: list[dict] | None) -> bool:
    target = _normalize_title(active_artist)
    for artist in artists or []:
        if target and target in _normalize_title(artist.get("name", "")):
            return True
    return False


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    session = async_get_clientsession(hass)
    api_client = MusicAssistantApiClient(session=session, base_url=entry.data[CONF_MASS_URL], token=entry.data[CONF_MASS_TOKEN])
    lastfm_client = LastFmApiClient(session=session, api_key=entry.data[CONF_LASTFM_API_KEY], cache_ttl_seconds=LASTFM_CACHE_TTL_SECONDS)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {"api_client": api_client, "lastfm_client": lastfm_client}

    if not hass.data[DOMAIN].get("panel_registered"):
        frontend_dir = Path(__file__).parent / "frontend"
        js_url = f"/api/{DOMAIN}/panel.js"
        await hass.http.async_register_static_paths([StaticPathConfig(url_path=js_url, path=str(frontend_dir / "panel.js"), cache_headers=False)])
        add_extra_js_url(hass, js_url)
        await async_register_panel(hass, webcomponent_name="music-connect-panel", frontend_url_path=PANEL_PATH, module_url=js_url, sidebar_title=PANEL_TITLE, sidebar_icon=PANEL_ICON, require_admin=False, config={"entry_id": entry.entry_id})

        hass.http.register_view(MusicConnectPlayersView(hass, entry.entry_id))
        hass.http.register_view(MusicConnectSearchView(hass, entry.entry_id))
        hass.http.register_view(MusicConnectSimilarView(hass, entry.entry_id))
        hass.http.register_view(MusicConnectTopAlbumsView(hass, entry.entry_id))
        hass.http.register_view(MusicConnectArtistMediaView(hass, entry.entry_id))
        hass.http.register_view(MusicConnectPlayView(hass, entry.entry_id))
        hass.http.register_view(MusicConnectAlbumTracksView(hass, entry.entry_id))
        hass.data[DOMAIN]["panel_registered"] = True
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data[DOMAIN].pop(entry.entry_id, None)
    return True


class MusicConnectBaseView(HomeAssistantView):
    requires_auth = True

    async def _safe_execute(self, callback):
        try:
            return await callback()
        except ClientResponseError as err:
            if err.status == 401:
                return json_response({"error": "Music Assistant authentication failed. Verify your long-lived Music Assistant token."}, status=401)
            return json_response({"error": f"Music Assistant API error: {err}"}, status=502)
        except ClientError as err:
            return json_response({"error": f"Music Assistant API error: {err}"}, status=502)
        except Exception as err:
            return json_response({"error": f"Unexpected error: {err}"}, status=500)

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self.hass = hass
        self.entry_id = entry_id

    @property
    def api_client(self) -> MusicAssistantApiClient:
        return self.hass.data[DOMAIN][self.entry_id]["api_client"]

    @property
    def lastfm_client(self) -> LastFmApiClient:
        return self.hass.data[DOMAIN][self.entry_id]["lastfm_client"]


class MusicConnectPlayersView(MusicConnectBaseView):
    name = "api:music_connect:players"
    url = f"/api/{DOMAIN}/players"

    async def get(self, request: Request) -> Response:
        return await self._safe_execute(self._get_players)

    async def _get_players(self) -> Response:
        return json_response({"players": await self.api_client.players_all()})


class MusicConnectSearchView(MusicConnectBaseView):
    name = "api:music_connect:search"
    url = f"/api/{DOMAIN}/search"

    async def get(self, request: Request) -> Response:
        query = request.query.get("q", "").strip()
        if not query:
            return json_response({"results": {}}, status=400)
        return await self._safe_execute(lambda: self._search(query))

    async def _search(self, query: str) -> Response:
        return json_response({"results": await self.api_client.search(query)})


class MusicConnectSimilarView(MusicConnectBaseView):
    name = "api:music_connect:lastfm_similar"
    url = f"/api/{DOMAIN}/lastfm/similar"

    async def get(self, request: Request) -> Response:
        artist = request.query.get("artist", "").strip()
        limit = int(request.query.get("limit", "20"))
        if not artist:
            return json_response({"error": "artist is required"}, status=400)
        return await self._safe_execute(lambda: self._get_similar(artist, limit))

    async def _get_similar(self, artist: str, limit: int) -> Response:
        return json_response({"artist": artist, "similar": await self.lastfm_client.artist_get_similar(artist, limit=limit)})


class MusicConnectTopAlbumsView(MusicConnectBaseView):
    name = "api:music_connect:lastfm_top_albums"
    url = f"/api/{DOMAIN}/lastfm/top_albums"

    async def get(self, request: Request) -> Response:
        artist = request.query.get("artist", "").strip()
        limit = int(request.query.get("limit", "30"))
        if not artist:
            return json_response({"error": "artist is required"}, status=400)
        return await self._safe_execute(lambda: self._get_top_albums(artist, limit))

    async def _get_top_albums(self, artist: str, limit: int) -> Response:
        return json_response({"artist": artist, "albums": await self.lastfm_client.artist_get_top_albums(artist, limit=limit)})


class MusicConnectArtistMediaView(MusicConnectBaseView):
    name = "api:music_connect:artist_media"
    url = f"/api/{DOMAIN}/artist_media"

    async def get(self, request: Request) -> Response:
        artist = request.query.get("artist", "").strip()
        if not artist:
            return json_response({"error": "artist is required"}, status=400)
        return await self._safe_execute(lambda: self._get_media(artist))

    async def _get_media(self, artist: str) -> Response:
        ma = await self.api_client.search(artist)
        lastfm_albums = await self.lastfm_client.artist_get_top_albums(artist, limit=50)
        lastfm_rank = {_normalize_title(a.get("name", "")): idx for idx, a in enumerate(lastfm_albums)}

        all_albums = ma.get("albums", []) if isinstance(ma, dict) else []
        filtered_albums = [a for a in all_albums if _artist_matches(artist, a.get("artists"))]
        filtered_out_albums = len(all_albums) - len(filtered_albums)

        for album in filtered_albums:
            rank = lastfm_rank.get(_normalize_title(album.get("name", "")))
            album["_lastfm_rank"] = rank if rank is not None else 10_000

        filtered_albums.sort(key=lambda a: (a.get("_lastfm_rank", 10_000), a.get("year") or 9999, a.get("name", "")))

        all_tracks = ma.get("tracks", []) if isinstance(ma, dict) else []
        filtered_tracks = [t for t in all_tracks if _artist_matches(artist, t.get("artists"))]
        dedup: dict[str, dict] = {}
        for track in filtered_tracks:
            key = _normalize_title(track.get("name", ""))
            current = dedup.get(key)
            popularity = track.get("metadata", {}).get("popularity") or -1
            if not current or popularity > (current.get("metadata", {}).get("popularity") or -1):
                dedup[key] = track
        filtered_tracks = list(dedup.values())
        filtered_tracks.sort(key=lambda t: (-(t.get("metadata", {}).get("popularity") or -1), t.get("name", "")))

        _LOGGER.debug("Filtered MA results for artist=%s: albums_out=%s tracks_out=%s", artist, filtered_out_albums, len(all_tracks) - len(filtered_tracks))
        return json_response({"artist": artist, "albums": filtered_albums[:30], "tracks": filtered_tracks[:30]})




class MusicConnectAlbumTracksView(MusicConnectBaseView):
    name = "api:music_connect:album_tracks"
    url = f"/api/{DOMAIN}/album_tracks"

    async def get(self, request: Request) -> Response:
        artist = request.query.get("artist", "").strip()
        album = request.query.get("album", "").strip()
        if not artist or not album:
            return json_response({"error": "artist and album are required"}, status=400)
        return await self._safe_execute(lambda: self._get_album_tracks(artist, album))

    async def _get_album_tracks(self, artist: str, album: str) -> Response:
        ma = await self.api_client.search(f"{artist} {album}")
        tracks = ma.get("tracks", []) if isinstance(ma, dict) else []
        target_album = _normalize_title(album)
        filtered = []
        for track in tracks:
            if not _artist_matches(artist, track.get("artists")):
                continue
            track_album = _normalize_title((track.get("album") or {}).get("name", ""))
            if target_album and track_album and target_album != track_album:
                continue
            filtered.append(track)
        filtered.sort(key=lambda t: ((t.get("track_number") or 999), t.get("name", "")))
        return json_response({"artist": artist, "album": album, "tracks": filtered[:100]})
class MusicConnectPlayView(MusicConnectBaseView):
    name = "api:music_connect:play"
    url = f"/api/{DOMAIN}/play"

    async def post(self, request: Request) -> Response:
        data = await request.json()
        player_id = (data or {}).get("player_id", "").strip()
        media_uri = (data or {}).get("media_uri", "").strip()
        if not player_id or not media_uri:
            return json_response({"error": "player_id and media_uri are required"}, status=400)
        return await self._safe_execute(lambda: self._play(player_id, media_uri))

    async def _play(self, player_id: str, media_uri: str) -> Response:
        _LOGGER.info("Playback request player_id=%s media_uri=%s", player_id, media_uri)
        result = await self.api_client.play_media(player_id, media_uri)
        return json_response({"ok": True, "result": result})
