"""Config flow for Panasonic Eolia AC integration."""

from __future__ import annotations

import logging
import urllib.parse
from typing import Any, Dict, Optional

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv

from .const import CONF_ACCESS_TOKEN, CONF_REFRESH_TOKEN, DOMAIN
from .eolia_api import EoliaAuth, EoliaAuthError, EoliaError, EoliaSession

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required("token_or_url"): cv.string,
    }
)


class PanasonicEoliaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Panasonic Eolia AC."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._code_verifier: Optional[str] = None
        self._auth_url: Optional[str] = None

    async def async_step_user(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: Dict[str, str] = {}

        if user_input is not None:
            raw_input = user_input.get("token_or_url", "").strip()
            refresh_token: Optional[str] = None
            access_token: Optional[str] = None

            try:
                # 1. Check if user passed a callback URL or code
                parsed = urllib.parse.urlparse(raw_input)
                query_params = urllib.parse.parse_qs(parsed.query)
                code = query_params.get("code", [None])[0]
                if not code and parsed.fragment:
                    fragment_params = urllib.parse.parse_qs(parsed.fragment)
                    code = fragment_params.get("code", [None])[0]

                # If raw_input is just a code
                if not code and len(raw_input) > 20 and not raw_input.startswith("eyJ") and "=" not in raw_input and " " not in raw_input and self._code_verifier:
                    code = raw_input

                auth = EoliaAuth()

                if code and self._code_verifier:
                    # Exchange authorization code for tokens
                    token_data = await self.hass.async_add_executor_job(
                        auth.exchange_code, code, self._code_verifier
                    )
                    refresh_token = token_data.get("refresh_token")
                    access_token = token_data.get("access_token")
                else:
                    # Assume user provided a refresh_token or access_token directly
                    refresh_token = raw_input
                    auth.refresh_token = refresh_token

                session = EoliaSession(auth=auth)

                # Validate connection & credentials by fetching devices
                devices = await self.hass.async_add_executor_job(session.get_devices)

                if not devices:
                    errors["base"] = "no_devices"
                else:
                    # Use unique ID based on first appliance ID to prevent duplicate entries
                    unique_id = f"eolia_account_{devices[0]['id']}"
                    await self.async_set_unique_id(unique_id)
                    self._abort_if_unique_id_configured()

                    title = f"Panasonic Eolia ({len(devices)} AC)"
                    if devices[0].get("name"):
                        title = f"Panasonic Eolia ({devices[0]['name']})"

                    return self.async_create_entry(
                        title=title,
                        data={
                            CONF_REFRESH_TOKEN: refresh_token or auth.refresh_token,
                            CONF_ACCESS_TOKEN: access_token or auth.access_token,
                        },
                    )

            except EoliaAuthError:
                errors["base"] = "invalid_auth"
            except EoliaError:
                errors["base"] = "cannot_connect"
            except Exception as err:
                _LOGGER.exception("Unexpected exception in config flow: %s", err)
                errors["base"] = "unknown"

        # Generate a new PKCE pair and Auth URL for the user
        verifier, challenge = EoliaAuth.generate_pkce_pair()
        self._code_verifier = verifier
        self._auth_url = EoliaAuth.get_authorize_url(challenge)

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            description_placeholders={"auth_url": self._auth_url},
            errors=errors,
        )

    async def async_step_import(self, import_config: Dict[str, Any]) -> FlowResult:
        """Handle import from configuration.yaml."""
        return await self.async_step_user({"token_or_url": import_config.get(CONF_REFRESH_TOKEN, "")})
