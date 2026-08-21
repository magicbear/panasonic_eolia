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
from .eolia_api import (
    EoliaAuth,
    EoliaAuthError,
    EoliaError,
    EoliaResponseError,
    EoliaSession,
)

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

            # Restore code_verifier from context if lost during serialization
            if not self._code_verifier and "code_verifier" in self.context:
                self._code_verifier = self.context["code_verifier"]

            try:
                # 1. Determine whether input is a redirect callback URL / code or a token
                is_callback = "panasonic-eolia://" in raw_input or "code=" in raw_input or len(raw_input) < 100

                code: Optional[str] = None
                if "panasonic-eolia://" in raw_input or "code=" in raw_input:
                    parsed = urllib.parse.urlparse(raw_input)
                    query_params = urllib.parse.parse_qs(parsed.query)
                    code = query_params.get("code", [None])[0]
                    if not code and parsed.fragment:
                        fragment_params = urllib.parse.parse_qs(parsed.fragment)
                        code = fragment_params.get("code", [None])[0]
                elif is_callback and not raw_input.startswith("eyJ") and "." not in raw_input:
                    code = raw_input

                auth = EoliaAuth()

                if code:
                    if not self._code_verifier:
                        _LOGGER.warning("Authorization code provided but code_verifier is missing.")
                        raise EoliaAuthError("Session expired or invalid code_verifier. Please log in again.")

                    _LOGGER.debug("Exchanging authorization code for tokens...")
                    token_data = await self.hass.async_add_executor_job(
                        auth.exchange_code, code, self._code_verifier
                    )
                    refresh_token = token_data.get("refresh_token")
                    access_token = token_data.get("access_token")
                else:
                    # User provided a direct refresh_token or access_token
                    _LOGGER.debug("Using direct token provided by user.")
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

            except EoliaAuthError as err:
                _LOGGER.warning("Authentication failed: %s", err)
                errors["base"] = "invalid_auth"
            except EoliaResponseError as err:
                _LOGGER.warning("Eolia API response error (status %s): %s", err.status_code, err.message)
                if err.status_code in (401, 403):
                    errors["base"] = "invalid_auth"
                else:
                    errors["base"] = "cannot_connect"
            except EoliaError as err:
                _LOGGER.warning("Eolia connection error: %s", err)
                errors["base"] = "cannot_connect"
            except Exception as err:
                _LOGGER.exception("Unexpected exception in config flow: %s", err)
                errors["base"] = "unknown"

        # Generate a fresh PKCE pair and Auth URL for the user
        verifier, challenge = EoliaAuth.generate_pkce_pair()
        self._code_verifier = verifier
        self.context["code_verifier"] = verifier
        self._auth_url = EoliaAuth.get_authorize_url(challenge)
        self.context["auth_url"] = self._auth_url

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            description_placeholders={"auth_url": self._auth_url},
            errors=errors,
        )

    async def async_step_import(self, import_config: Dict[str, Any]) -> FlowResult:
        """Handle import from configuration.yaml."""
        return await self.async_step_user({"token_or_url": import_config.get(CONF_REFRESH_TOKEN, "")})
