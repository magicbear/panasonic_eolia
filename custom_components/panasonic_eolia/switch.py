"""Switch platform for Panasonic Eolia AC."""

from __future__ import annotations

import functools
import logging
from typing import Any, Dict

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import EoliaDeviceCoordinator, PanasonicEoliaBaseEntity
from .eolia_api import EoliaError

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Panasonic Eolia switches from a config entry."""
    coordinators: Dict[str, EoliaDeviceCoordinator] = hass.data[DOMAIN][entry.entry_id]["coordinators"]
    entities: list[SwitchEntity] = []

    for coordinator in coordinators.values():
        entities.append(PanasonicEoliaNanoexSwitch(coordinator))

    if entities:
        async_add_entities(entities)


class PanasonicEoliaNanoexSwitch(PanasonicEoliaBaseEntity, SwitchEntity):
    """Switch to toggle Panasonic nanoeX mode."""

    _attr_icon = "mdi:virus-outline"
    _attr_translation_key = "nanoex"

    def __init__(self, coordinator: EoliaDeviceCoordinator) -> None:
        """Initialize the nanoeX switch."""
        super().__init__(coordinator)
        self._attr_unique_id = f"panasonic_eolia_{self.appliance_id}_nanoex"

    @property
    def is_on(self) -> bool:
        """Return True if nanoeX is active."""
        if not self.coordinator.data or not self.coordinator.data.status:
            return False
        return bool(self.coordinator.data.status.get("nanoex", False))

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on nanoeX."""
        _LOGGER.debug("Enabling nanoeX on %s", self.name)
        try:
            await self.hass.async_add_executor_job(
                functools.partial(
                    self._session.set_device_status,
                    self.appliance_id,
                    nanoex=True,
                )
            )
            await self.coordinator.async_request_refresh()
        except EoliaError as err:
            _LOGGER.error("Failed to enable nanoeX on %s: %s", self.name, err)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off nanoeX."""
        _LOGGER.debug("Disabling nanoeX on %s", self.name)
        try:
            await self.hass.async_add_executor_job(
                functools.partial(
                    self._session.set_device_status,
                    self.appliance_id,
                    nanoex=False,
                )
            )
            await self.coordinator.async_request_refresh()
        except EoliaError as err:
            _LOGGER.error("Failed to disable nanoeX on %s: %s", self.name, err)
