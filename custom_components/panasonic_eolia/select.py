"""Select platform for Panasonic Eolia AC."""

from __future__ import annotations

import functools
import logging
from typing import Dict, Optional

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, AirSwingLR
from .coordinator import EoliaDeviceCoordinator, PanasonicEoliaBaseEntity
from .eolia_api import EoliaError

_LOGGER = logging.getLogger(__name__)

HORIZONTAL_SWING_MODES = {
    "Auto": AirSwingLR.AUTO,
    "Front": AirSwingLR.FRONT,
    "Spot": AirSwingLR.SPOT,
    "Wide": AirSwingLR.WIDE,
    "Left": AirSwingLR.TO_LEFT,
    "Nearby Left": AirSwingLR.NEARBY_LEFT,
    "Nearby Right": AirSwingLR.NEARBY_RIGHT,
    "Right": AirSwingLR.TO_RIGHT,
}
HORIZONTAL_SWING_TO_NAME = {v.value: k for k, v in HORIZONTAL_SWING_MODES.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Panasonic Eolia select entities from a config entry."""
    coordinators: Dict[str, EoliaDeviceCoordinator] = hass.data[DOMAIN][entry.entry_id]["coordinators"]
    entities: list[SelectEntity] = []

    for coordinator in coordinators.values():
        entities.append(PanasonicEoliaHorizontalSwingSelect(coordinator))

    if entities:
        async_add_entities(entities)


class PanasonicEoliaHorizontalSwingSelect(PanasonicEoliaBaseEntity, SelectEntity):
    """Select entity for Panasonic Eolia horizontal air swing."""

    _attr_icon = "mdi:arrow-left-right"
    _attr_translation_key = "horizontal_swing"
    _attr_options = list(HORIZONTAL_SWING_MODES.keys())

    def __init__(self, coordinator: EoliaDeviceCoordinator) -> None:
        """Initialize horizontal swing select entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"panasonic_eolia_{self.appliance_id}_horizontal_swing"

    @property
    def current_option(self) -> Optional[str]:
        """Return the current horizontal swing mode."""
        if not self.coordinator.data or not self.coordinator.data.status:
            return "Auto"
        raw_val = str(self.coordinator.data.status.get("wind_direction_horizon", "auto")).lower()
        return HORIZONTAL_SWING_TO_NAME.get(raw_val, "Auto")

    async def async_select_option(self, option: str) -> None:
        """Change horizontal swing mode."""
        _LOGGER.debug("Setting %s horizontal swing mode to %s", self.name, option)
        swing_enum = HORIZONTAL_SWING_MODES.get(option, AirSwingLR.AUTO)
        try:
            await self.hass.async_add_executor_job(
                functools.partial(
                    self._session.set_device_status,
                    self.appliance_id,
                    air_swing_horizontal=swing_enum,
                )
            )
            await self.coordinator.async_request_refresh()
        except EoliaError as err:
            _LOGGER.error("Failed to set horizontal swing on %s: %s", self.name, err)
