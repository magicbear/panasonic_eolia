"""The Panasonic Eolia integration."""

from __future__ import annotations

import logging
from typing import Any, Dict

from homeassistant.config_entries import ConfigEntry, SOURCE_IMPORT
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.typing import ConfigType

from .const import CONF_ACCESS_TOKEN, CONF_REFRESH_TOKEN, DOMAIN
from .coordinator import EoliaDeviceCoordinator
from .eolia_api import EoliaAuth, EoliaAuthError, EoliaError, EoliaSession

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.CLIMATE,
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.SWITCH,
    Platform.SELECT,
]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Panasonic Eolia component from configuration.yaml."""
    hass.data.setdefault(DOMAIN, {})

    # Support YAML configuration import if present
    if DOMAIN in config:
        conf = config[DOMAIN]
        if isinstance(conf, list):
            for entry_conf in conf:
                hass.async_create_task(
                    hass.config_entries.flow.async_init(
                        DOMAIN,
                        context={"source": SOURCE_IMPORT},
                        data=entry_conf,
                    )
                )
        elif isinstance(conf, dict):
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN,
                    context={"source": SOURCE_IMPORT},
                    data=conf,
                )
            )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Panasonic Eolia from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    refresh_token = entry.data.get(CONF_REFRESH_TOKEN)
    access_token = entry.data.get(CONF_ACCESS_TOKEN)

    auth = EoliaAuth(refresh_token=refresh_token, access_token=access_token)
    session = EoliaSession(auth=auth)

    # Fetch all devices
    try:
        devices_data = await hass.async_add_executor_job(session.get_devices)
    except EoliaAuthError as err:
        raise ConfigEntryAuthFailed(
            f"Authentication failed for {entry.title}: {err}"
        ) from err
    except EoliaError as err:
        raise ConfigEntryNotReady(
            f"Failed to connect to Panasonic Eolia for {entry.title}: {err}"
        ) from err

    coordinators: Dict[str, EoliaDeviceCoordinator] = {}
    for device in devices_data:
        appliance_id = device.get("id")
        if not appliance_id:
            continue
        coordinator = EoliaDeviceCoordinator(hass, session, device)
        await coordinator.async_config_entry_first_refresh()
        coordinators[appliance_id] = coordinator

    hass.data[DOMAIN][entry.entry_id] = {
        "session": session,
        "coordinators": coordinators,
        "devices": devices_data,
    }

    # Listen for options/entry updates to automatically reload
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry when options or data change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)

    return unload_ok
