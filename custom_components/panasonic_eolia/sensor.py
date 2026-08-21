"""Sensor platform for Panasonic Eolia AC."""

from __future__ import annotations

import logging
from typing import Dict, Optional

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTemperature
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
    """Set up Panasonic Eolia sensors from a config entry."""
    coordinators: Dict[str, EoliaDeviceCoordinator] = hass.data[DOMAIN][entry.entry_id]["coordinators"]
    entities: list[SensorEntity] = []

    for coordinator in coordinators.values():
        entities.extend(
            [
                PanasonicEoliaInsideTemperatureSensor(coordinator),
                PanasonicEoliaOutsideTemperatureSensor(coordinator),
                PanasonicEoliaInsideHumiditySensor(coordinator),
            ]
        )

    if entities:
        async_add_entities(entities)


class PanasonicEoliaInsideTemperatureSensor(PanasonicEoliaBaseEntity, SensorEntity):
    """Sensor for Panasonic Eolia indoor temperature."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_translation_key = "inside_temperature"

    def __init__(self, coordinator: EoliaDeviceCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"panasonic_eolia_{self.appliance_id}_inside_temperature"

    @property
    def native_value(self) -> Optional[float]:
        """Return the indoor temperature."""
        if not self.coordinator.data or not self.coordinator.data.status:
            return None
        val = self.coordinator.data.status.get("inside_temp")
        if val is None or val == 126:
            return None
        return float(val)


class PanasonicEoliaOutsideTemperatureSensor(PanasonicEoliaBaseEntity, SensorEntity):
    """Sensor for Panasonic Eolia outdoor temperature."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_translation_key = "outside_temperature"

    def __init__(self, coordinator: EoliaDeviceCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"panasonic_eolia_{self.appliance_id}_outside_temperature"

    @property
    def native_value(self) -> Optional[float]:
        """Return the outdoor temperature."""
        if not self.coordinator.data or not self.coordinator.data.status:
            return None
        val = self.coordinator.data.status.get("outside_temp")
        if val is None or val == 126:
            return None
        return float(val)


class PanasonicEoliaInsideHumiditySensor(PanasonicEoliaBaseEntity, SensorEntity):
    """Sensor for Panasonic Eolia indoor humidity."""

    _attr_device_class = SensorDeviceClass.HUMIDITY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_translation_key = "inside_humidity"

    def __init__(self, coordinator: EoliaDeviceCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"panasonic_eolia_{self.appliance_id}_inside_humidity"

    @property
    def native_value(self) -> Optional[int]:
        """Return the indoor humidity."""
        if not self.coordinator.data or not self.coordinator.data.status:
            return None
        val = self.coordinator.data.status.get("inside_humidity")
        if val is None or val == 126:
            return None
        return int(val)
