"""Binary sensor platform for Panasonic Eolia AC."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import EoliaDeviceCoordinator, PanasonicEoliaBaseEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Panasonic Eolia binary sensors from a config entry."""
    coordinators: Dict[str, EoliaDeviceCoordinator] = hass.data[DOMAIN][entry.entry_id]["coordinators"]
    entities: list[BinarySensorEntity] = []

    for coordinator in coordinators.values():
        entities.extend(
            [
                PanasonicEoliaCleanFilterBinarySensor(coordinator),
                PanasonicEoliaErrorBinarySensor(coordinator),
            ]
        )

    if entities:
        async_add_entities(entities)


class PanasonicEoliaCleanFilterBinarySensor(PanasonicEoliaBaseEntity, BinarySensorEntity):
    """Binary sensor for filter cleaning notification."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_translation_key = "clean_filter"

    def __init__(self, coordinator: EoliaDeviceCoordinator) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"panasonic_eolia_{self.appliance_id}_clean_filter"

    @property
    def is_on(self) -> bool:
        """Return True if filter clean notice is active."""
        if not self.coordinator.data:
            return False

        # Check clean filter endpoint status if available
        if self.coordinator.data.filter_status:
            fs = self.coordinator.data.filter_status
            if fs.get("clean_filter_notice") or fs.get("filter_clean_status") in ("need_clean", "clean_required", True):
                return True

        # Check main device status flags if any
        status = self.coordinator.data.status or {}
        if status.get("clean_filter") or status.get("clean_filter_notice"):
            return True

        return False

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return extra filter status details."""
        if self.coordinator.data and self.coordinator.data.filter_status:
            return self.coordinator.data.filter_status
        return {}


class PanasonicEoliaErrorBinarySensor(PanasonicEoliaBaseEntity, BinarySensorEntity):
    """Binary sensor for device error status."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_translation_key = "error_status"

    def __init__(self, coordinator: EoliaDeviceCoordinator) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"panasonic_eolia_{self.appliance_id}_error_status"

    @property
    def is_on(self) -> bool:
        """Return True if an error is present."""
        if not self.coordinator.data or not self.coordinator.data.status:
            return False
        err = self.coordinator.data.status.get("device_errstatus")
        return bool(err and str(err) not in ("0", "none", "None", "false", "False", ""))

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return error attributes."""
        if not self.coordinator.data or not self.coordinator.data.status:
            return {}
        err = self.coordinator.data.status.get("device_errstatus")
        return {"error_code": err} if err else {}
