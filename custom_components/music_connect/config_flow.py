"""Config flow for Music Connect."""

from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries

from .const import CONF_LASTFM_API_KEY, CONF_MASS_TOKEN, CONF_MASS_URL, DOMAIN


class MusicConnectConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Music Connect."""

    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None):
        errors: dict[str, str] = {}

        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_MASS_URL])
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title="Music Connect", data=user_input)

        schema = vol.Schema(
            {
                vol.Required(CONF_MASS_URL): str,
                vol.Required(CONF_MASS_TOKEN): str,
                vol.Required(CONF_LASTFM_API_KEY): str,
            }
        )

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)
