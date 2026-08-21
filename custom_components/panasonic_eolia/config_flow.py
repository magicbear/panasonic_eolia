"""Config flow for Panasonic Eolia AC integration."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
import urllib.parse

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
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
        self._reauth_entry: Optional[config_entries.ConfigEntry] = None

    async def _async_verify_token_or_url(
        self, raw_input: str
    ) -> tuple[Optional[str], Optional[str], List[Dict[str, Any]]]:
        """Verify token or url and return refresh_token, access_token, and devices."""
        raw_input = raw_input.strip()
        refresh_token: Optional[str] = None
        access_token: Optional[str] = None

        if not self._code_verifier and "code_verifier" in self.context:
            self._code_verifier = self.context["code_verifier"]

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
            _LOGGER.debug("Using direct token provided by user.")
            refresh_token = raw_input
            auth.refresh_token = refresh_token

        session = EoliaSession(auth=auth)
        devices = await self.hass.async_add_executor_job(session.get_devices)
        if not devices:
            raise EoliaError("No devices found on this account.")

        return refresh_token or auth.refresh_token, access_token or auth.access_token, devices

    def _ensure_auth_url(self) -> str:
        """Ensure auth URL and code verifier are generated."""
        if not self._auth_url or not self._code_verifier:
            verifier, challenge = EoliaAuth.generate_pkce_pair()
            self._code_verifier = verifier
            self.context["code_verifier"] = verifier
            self._auth_url = EoliaAuth.get_authorize_url(challenge)
            self.context["auth_url"] = self._auth_url
        return self._auth_url

    async def async_step_user(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: Dict[str, str] = {}

        if user_input is not None:
            raw_input = user_input.get("token_or_url", "").strip()
            try:
                refresh_token, access_token, devices = await self._async_verify_token_or_url(raw_input)

                unique_id = f"eolia_account_{devices[0]['id']}"
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()

                title = f"Panasonic Eolia ({len(devices)} AC)"
                if devices[0].get("name"):
                    title = f"Panasonic Eolia ({devices[0]['name']})"

                return self.async_create_entry(
                    title=title,
                    data={
                        CONF_REFRESH_TOKEN: refresh_token,
                        CONF_ACCESS_TOKEN: access_token,
                    },
                )
            except EoliaAuthError as err:
                _LOGGER.warning("Authentication failed: %s", err)
                errors["base"] = "invalid_auth"
            except EoliaResponseError as err:
                _LOGGER.warning("Eolia API response error (status %s): %s", err.status_code, err.message)
                if "E-21291-00002" in str(err.message):
                    errors["base"] = "time_sync_error"
                elif err.status_code in (401, 403):
                    errors["base"] = "invalid_auth"
                else:
                    errors["base"] = "cannot_connect"
            except EoliaError as err:
                _LOGGER.warning("Eolia connection error: %s", err)
                if "No devices" in str(err):
                    errors["base"] = "no_devices"
                else:
                    errors["base"] = "cannot_connect"
            except Exception as err:
                _LOGGER.exception("Unexpected exception in config flow: %s", err)
                errors["base"] = "unknown"

        auth_url = self._ensure_auth_url()
        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            description_placeholders={"auth_url": auth_url},
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: Dict[str, Any]) -> FlowResult:
        """Handle re-authentication."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Confirm reauth dialog."""
        errors: Dict[str, str] = {}
        entry = self._reauth_entry or self.hass.config_entries.async_get_entry(self.context.get("entry_id"))

        if user_input is not None and entry:
            raw_input = user_input.get("token_or_url", "").strip()
            try:
                refresh_token, access_token, devices = await self._async_verify_token_or_url(raw_input)

                self.hass.config_entries.async_update_entry(
                    entry,
                    data={
                        CONF_REFRESH_TOKEN: refresh_token,
                        CONF_ACCESS_TOKEN: access_token,
                    },
                )
                await self.hass.config_entries.async_reload(entry.entry_id)
                return self.async_abort(reason="reauth_successful")
            except EoliaAuthError:
                errors["base"] = "invalid_auth"
            except EoliaResponseError as err:
                if "E-21291-00002" in str(err.message):
                    errors["base"] = "time_sync_error"
                elif err.status_code in (401, 403):
                    errors["base"] = "invalid_auth"
                else:
                    errors["base"] = "cannot_connect"
            except EoliaError:
                errors["base"] = "cannot_connect"
            except Exception as err:
                _LOGGER.exception("Unexpected exception in reauth: %s", err)
                errors["base"] = "unknown"

        auth_url = self._ensure_auth_url()
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=DATA_SCHEMA,
            description_placeholders={"auth_url": auth_url},
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Handle re-configuration of an existing entry."""
        errors: Dict[str, str] = {}
        entry = self.hass.config_entries.async_get_entry(self.context.get("entry_id"))

        if user_input is not None and entry:
            raw_input = user_input.get("token_or_url", "").strip()
            try:
                refresh_token, access_token, devices = await self._async_verify_token_or_url(raw_input)

                self.hass.config_entries.async_update_entry(
                    entry,
                    data={
                        CONF_REFRESH_TOKEN: refresh_token,
                        CONF_ACCESS_TOKEN: access_token,
                    },
                )
                await self.hass.config_entries.async_reload(entry.entry_id)
                return self.async_abort(reason="reconfigure_successful")
            except EoliaAuthError:
                errors["base"] = "invalid_auth"
            except EoliaResponseError as err:
                if "E-21291-00002" in str(err.message):
                    errors["base"] = "time_sync_error"
                elif err.status_code in (401, 403):
                    errors["base"] = "invalid_auth"
                else:
                    errors["base"] = "cannot_connect"
            except EoliaError:
                errors["base"] = "cannot_connect"
            except Exception as err:
                _LOGGER.exception("Unexpected exception in reconfigure: %s", err)
                errors["base"] = "unknown"

        auth_url = self._ensure_auth_url()
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=DATA_SCHEMA,
            description_placeholders={"auth_url": auth_url},
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""
        return PanasonicEoliaOptionsFlowHandler(config_entry)

    async def async_step_import(self, import_config: Dict[str, Any]) -> FlowResult:
        """Handle import from configuration.yaml."""
        return await self.async_step_user({"token_or_url": import_config.get(CONF_REFRESH_TOKEN, "")})


class PanasonicEoliaOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for updating token and reloading."""

    def __init__(self, config_entry: Optional[config_entries.ConfigEntry] = None) -> None:
        """Initialize options flow."""
        self._custom_config_entry = config_entry
        self._code_verifier: Optional[str] = None
        self._auth_url: Optional[str] = None

    @property
    def _entry(self) -> config_entries.ConfigEntry:
        """Return the config entry."""
        if hasattr(self, "config_entry") and self.config_entry is not None:
            return self.config_entry
        return self._custom_config_entry

    async def async_step_init(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Manage the options."""
        errors: Dict[str, str] = {}
        entry = self._entry

        if user_input is not None:
            raw_input = user_input.get("token_or_url", "").strip()
            if raw_input:
                try:
                    is_callback = "panasonic-eolia://" in raw_input or "code=" in raw_input or len(raw_input) < 100
                    code = None
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
                            raise EoliaAuthError("Session expired. Please log in again.")
                        token_data = await self.hass.async_add_executor_job(
                            auth.exchange_code, code, self._code_verifier
                        )
                        refresh_token = token_data.get("refresh_token")
                        access_token = token_data.get("access_token")
                    else:
                        refresh_token = raw_input
                        auth.refresh_token = refresh_token
                        access_token = None

                    session = EoliaSession(auth=auth)
                    await self.hass.async_add_executor_job(session.get_devices)

                    self.hass.config_entries.async_update_entry(
                        entry,
                        data={
                            CONF_REFRESH_TOKEN: refresh_token or auth.refresh_token,
                            CONF_ACCESS_TOKEN: access_token or auth.access_token,
                        },
                    )
                    await self.hass.config_entries.async_reload(entry.entry_id)
                    return self.async_create_entry(title="", data={})
                except Exception as err:
                    _LOGGER.warning("Options update token failed: %s", err)
                    errors["base"] = "invalid_auth"
            else:
                # If left empty, simply reload the integration
                await self.hass.config_entries.async_reload(entry.entry_id)
                return self.async_create_entry(title="", data={})

        verifier, challenge = EoliaAuth.generate_pkce_pair()
        self._code_verifier = verifier
        self._auth_url = EoliaAuth.get_authorize_url(challenge)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional("token_or_url"): cv.string,
                }
            ),
            description_placeholders={"auth_url": self._auth_url},
            errors=errors,
        )
