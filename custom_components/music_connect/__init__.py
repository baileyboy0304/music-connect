"""Music Connect integration."""

from __future__ import annotations

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


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    session = async_get_clientsession(hass)
    api_client = MusicAssistantApiClient(
        session=session,
        base_url=entry.data[CONF_MASS_URL],
        token=entry.data[CONF_MASS_TOKEN],
    )
    lastfm_client = LastFmApiClient(
        session=session,
        api_key=entry.data[CONF_LASTFM_API_KEY],
        cache_ttl_seconds=LASTFM_CACHE_TTL_SECONDS,
    )

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "api_client": api_client,
        "lastfm_client": lastfm_client,
    }

    if not hass.data[DOMAIN].get("panel_registered"):
        frontend_dir = Path(__file__).parent / "frontend"
        js_url = f"/api/{DOMAIN}/panel.js"
        await hass.http.async_register_static_paths(
            [StaticPathConfig(url_path=js_url, path=str(frontend_dir / "panel.js"), cache_headers=False)]
        )
        add_extra_js_url(hass, js_url)

        await async_register_panel(
            hass,
            webcomponent_name="music-connect-panel",
            frontend_url_path=PANEL_PATH,
            module_url=js_url,
            sidebar_title=PANEL_TITLE,
            sidebar_icon=PANEL_ICON,
            require_admin=False,
            config={"entry_id": entry.entry_id},
        )

        hass.http.register_view(MusicConnectPlayersView(hass, entry.entry_id))
        hass.http.register_view(MusicConnectSearchView(hass, entry.entry_id))
        hass.http.register_view(MusicConnectSimilarView(hass, entry.entry_id))
        hass.http.register_view(MusicConnectTopAlbumsView(hass, entry.entry_id))
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
                return json_response(
                    {"error": "Music Assistant authentication failed. Verify your long-lived Music Assistant token."},
                    status=401,
                )
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
        players = await self.api_client.players_all()
        return json_response({"players": players})


class MusicConnectSearchView(MusicConnectBaseView):
    name = "api:music_connect:search"
    url = f"/api/{DOMAIN}/search"

    async def get(self, request: Request) -> Response:
        query = request.query.get("q", "").strip()
        if not query:
            return json_response({"results": {}}, status=400)

        return await self._safe_execute(lambda: self._search(query))

    async def _search(self, query: str) -> Response:
        results = await self.api_client.search(query)
        return json_response({"results": results})


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
        artists = await self.lastfm_client.artist_get_similar(artist, limit=limit)
        return json_response({"artist": artist, "similar": artists})


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
        albums = await self.lastfm_client.artist_get_top_albums(artist, limit=limit)
        return json_response({"artist": artist, "albums": albums})
