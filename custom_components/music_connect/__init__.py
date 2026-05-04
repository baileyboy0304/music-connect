"""Music Connect integration."""

from __future__ import annotations

from pathlib import Path

from aiohttp.web import Request, Response, json_response
from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import HomeAssistantView
from homeassistant.components.panel_custom import async_register_panel
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_MASS_TOKEN,
    CONF_MASS_URL,
    DOMAIN,
    PANEL_ICON,
    PANEL_PATH,
    PANEL_TITLE,
)
from .music_assistant_api import MusicAssistantApiClient


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up integration from yaml (unused)."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Music Connect from a config entry."""
    session = async_get_clientsession(hass)
    api_client = MusicAssistantApiClient(
        session=session,
        base_url=entry.data[CONF_MASS_URL],
        token=entry.data[CONF_MASS_TOKEN],
    )

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {"api_client": api_client}

    frontend_dir = Path(__file__).parent / "frontend"
    js_url = f"/api/{DOMAIN}/panel.js"

    hass.http.register_static_path(js_url, str(frontend_dir / "panel.js"), cache_headers=False)
    add_extra_js_url(hass, js_url)

    async_register_panel(
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

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    hass.data[DOMAIN].pop(entry.entry_id, None)
    return True


class MusicConnectBaseView(HomeAssistantView):
    """Base class for Music Connect API views."""

    requires_auth = True

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self.hass = hass
        self.entry_id = entry_id

    @property
    def api_client(self) -> MusicAssistantApiClient:
        return self.hass.data[DOMAIN][self.entry_id]["api_client"]


class MusicConnectPlayersView(MusicConnectBaseView):
    """Return Music Assistant players."""

    name = "api:music_connect:players"
    url = f"/api/{DOMAIN}/players"

    async def get(self, request: Request) -> Response:
        players = await self.api_client.players_all()
        return json_response({"players": players})


class MusicConnectSearchView(MusicConnectBaseView):
    """Search Music Assistant music library."""

    name = "api:music_connect:search"
    url = f"/api/{DOMAIN}/search"

    async def get(self, request: Request) -> Response:
        query = request.query.get("q", "").strip()
        if not query:
            return json_response({"results": {}}, status=400)

        results = await self.api_client.search(query)
        return json_response({"results": results})
