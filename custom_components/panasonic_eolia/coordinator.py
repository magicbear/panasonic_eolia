"""DataUpdateCoordinator and Base Entity for Panasonic Eolia."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Any, Dict, Optional

from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import DOMAIN
from .eolia_api import EoliaError, EoliaSession

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=60)


@dataclass
class EoliaDeviceData:
    """Class representing device state data."""

    device: Dict[str, Any]
    status: Dict[str, Any]
    filter_status: Optional[Dict[str, Any]] = None


class EoliaDeviceCoordinator(DataUpdateCoordinator[EoliaDeviceData]):
    """Coordinator to manage polling data for a single Panasonic Eolia device."""

    def __init__(
        self,
        hass: HomeAssistant,
        session: EoliaSession,
        device: Dict[str, Any],
        update_interval: timedelta = SCAN_INTERVAL,
    ) -> None:
        """Initialize the coordinator."""
        self.session = session
        self.device = device
        self.appliance_id: str = device["id"]
        self.device_name: str = device.get("name") or self.appliance_id
        self.device_model: str = device.get("model", "")

        super().__init__(
            hass,
            _LOGGER,
            name=f"Panasonic Eolia ({self.device_name})",
            update_interval=update_interval,
        )

    async def _async_update_data(self) -> EoliaDeviceData:
        """Fetch status and filter status from Eolia cloud API."""
        try:
            status = await self.hass.async_add_executor_job(
                self.session.get_device_status, self.appliance_id
            )
        except EoliaError as err:
            raise UpdateFailed(
                f"Failed to update device {self.device_name} ({self.appliance_id}): {err}"
            ) from err

        filter_status = None
        try:
            filter_status = await self.hass.async_add_executor_job(
                self.session.get_clean_filter_status, self.appliance_id
            )
        except Exception as err:
            _LOGGER.debug(
                "Could not fetch filter status for %s: %s", self.appliance_id, err
            )

        return EoliaDeviceData(
            device=self.device,
            status=status,
            filter_status=filter_status,
        )


class PanasonicEoliaBaseEntity(CoordinatorEntity[EoliaDeviceCoordinator]):
    """Base entity for Panasonic Eolia devices."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: EoliaDeviceCoordinator) -> None:
        """Initialize the base entity."""
        super().__init__(coordinator)
        self.appliance_id: str = coordinator.appliance_id
        self._session: EoliaSession = coordinator.session

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.appliance_id)},
            name=coordinator.device_name,
            manufacturer="Panasonic",
            model=coordinator.device_model or "Eolia Air Conditioner",
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        if not super().available or self.coordinator.data is None:
            return False
        return bool(self.coordinator.data.status)
