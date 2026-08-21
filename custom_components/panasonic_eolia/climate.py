"""Support for Panasonic Eolia Air Conditioners via v6 Cloud API."""

from __future__ import annotations

import functools
import logging
from typing import Any, Dict, List, Optional

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_TEMPERATURE,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    AirSwingUD,
    FanSpeed,
    OperationMode,
)
from .coordinator import EoliaDeviceCoordinator, PanasonicEoliaBaseEntity
from .eolia_api import EoliaError

_LOGGER = logging.getLogger(__name__)

# Mapping between Home Assistant HVACMode and Panasonic OperationMode
HVAC_TO_EOLIA = {
    HVACMode.HEAT_COOL: OperationMode.AUTO.value,
    HVACMode.COOL: OperationMode.COOL.value,
    HVACMode.HEAT: OperationMode.HEAT.value,
    HVACMode.DRY: OperationMode.DRY.value,
    HVACMode.FAN_ONLY: OperationMode.FAN.value,
}

EOLIA_TO_HVAC = {
    OperationMode.AUTO.value: HVACMode.HEAT_COOL,
    OperationMode.COOL.value: HVACMode.COOL,
    OperationMode.HEAT.value: HVACMode.HEAT,
    OperationMode.DRY.value: HVACMode.DRY,
    OperationMode.DEHUMIDIFY.value: HVACMode.DRY,
    OperationMode.CLOTHES_DRYER.value: HVACMode.DRY,
    OperationMode.FAN.value: HVACMode.FAN_ONLY,
    OperationMode.NANOE.value: HVACMode.FAN_ONLY,
    OperationMode.MOIST_COOLING.value: HVACMode.COOL,
    OperationMode.KEEP_HEATING.value: HVACMode.HEAT,
}

# Fan Speed Mappings
FAN_MODES = {
    "Auto": FanSpeed.AUTO,
    "Quiet": FanSpeed.QUIET,
    "Low": FanSpeed.LOW,
    "Mid": FanSpeed.MID,
    "HighMid": FanSpeed.HIGH_MID,
    "High": FanSpeed.HIGH,
}
FAN_SPEED_TO_NAME = {v.value: k for k, v in FAN_MODES.items()}

# Swing Modes (Vertical)
SWING_MODES = {
    "Auto": AirSwingUD.AUTO,
    "Up": AirSwingUD.UP,
    "UpMid": AirSwingUD.UP_MID,
    "Mid": AirSwingUD.MID,
    "DownMid": AirSwingUD.DOWN_MID,
    "Down": AirSwingUD.DOWN,
}
SWING_UD_TO_NAME = {v.value: k for k, v in SWING_MODES.items()}

SUPPORT_FLAGS = (
    ClimateEntityFeature.TARGET_TEMPERATURE
    | ClimateEntityFeature.FAN_MODE
    | ClimateEntityFeature.SWING_MODE
    | ClimateEntityFeature.TURN_ON
    | ClimateEntityFeature.TURN_OFF
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Panasonic Eolia climate entities from a config entry."""
    coordinators: Dict[str, EoliaDeviceCoordinator] = hass.data[DOMAIN][entry.entry_id]["coordinators"]
    entities = [PanasonicEoliaClimate(coordinator) for coordinator in coordinators.values()]
    if entities:
        async_add_entities(entities)
    else:
        _LOGGER.warning("No Panasonic Eolia devices found for entry %s.", entry.title)


class PanasonicEoliaClimate(PanasonicEoliaBaseEntity, ClimateEntity):
    """Representation of a Panasonic Eolia air conditioner climate entity."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = SUPPORT_FLAGS
    _attr_hvac_modes = [
        HVACMode.OFF,
        HVACMode.HEAT_COOL,
        HVACMode.COOL,
        HVACMode.HEAT,
        HVACMode.DRY,
        HVACMode.FAN_ONLY,
    ]
    _attr_fan_modes = list(FAN_MODES.keys())
    _attr_swing_modes = list(SWING_MODES.keys())
    _attr_min_temp = 16.0
    _attr_max_temp = 30.0
    _attr_target_temperature_step = 0.5
    _attr_name = None  # Use device name directly

    def __init__(self, coordinator: EoliaDeviceCoordinator) -> None:
        """Initialize the Eolia climate entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"panasonic_eolia_{self.appliance_id}"

    @property
    def is_on(self) -> bool:
        """Return True if device is on."""
        if not self.coordinator.data or not self.coordinator.data.status:
            return False
        return bool(self.coordinator.data.status.get("operation_status", False))

    @property
    def target_temperature(self) -> Optional[float]:
        """Return the target temperature."""
        if not self.coordinator.data or not self.coordinator.data.status:
            return None
        temp = self.coordinator.data.status.get("temperature")
        return float(temp) if temp is not None and temp != 126 else None

    @property
    def current_temperature(self) -> Optional[float]:
        """Return the indoor temperature."""
        if not self.coordinator.data or not self.coordinator.data.status:
            return None
        inside_temp = self.coordinator.data.status.get("inside_temp")
        return float(inside_temp) if inside_temp is not None and inside_temp != 126 else None

    @property
    def current_humidity(self) -> Optional[int]:
        """Return the indoor humidity if available."""
        if not self.coordinator.data or not self.coordinator.data.status:
            return None
        inside_hum = self.coordinator.data.status.get("inside_humidity")
        return int(inside_hum) if inside_hum is not None and inside_hum != 126 else None

    @property
    def hvac_mode(self) -> HVACMode:
        """Return the current HVAC operation mode."""
        if not self.is_on:
            return HVACMode.OFF
        mode = self.coordinator.data.status.get("operation_mode", OperationMode.COOL.value)
        return EOLIA_TO_HVAC.get(mode, HVACMode.HEAT_COOL)

    @property
    def fan_mode(self) -> str:
        """Return current fan mode."""
        if not self.coordinator.data or not self.coordinator.data.status:
            return "Auto"
        wind_volume = self.coordinator.data.status.get("wind_volume", 0)
        return FAN_SPEED_TO_NAME.get(wind_volume, "Auto")

    @property
    def swing_mode(self) -> str:
        """Return current vertical swing mode."""
        if not self.coordinator.data or not self.coordinator.data.status:
            return "Auto"
        wind_direction = self.coordinator.data.status.get("wind_direction", 0)
        return SWING_UD_TO_NAME.get(wind_direction, "Auto")

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return extra state attributes for sensor monitoring."""
        if not self.coordinator.data or not self.coordinator.data.status:
            return {}
        data = self.coordinator.data.status
        attrs = {
            "appliance_id": self.appliance_id,
            "model": self.coordinator.device_model,
            "raw_operation_mode": data.get("operation_mode"),
            "outside_temperature": (
                float(data["outside_temp"])
                if data.get("outside_temp") is not None and data["outside_temp"] != 126
                else None
            ),
            "nanoex": bool(data.get("nanoex", False)),
            "air_flow": str(data.get("air_flow", "not_set")),
        }
        if "device_errstatus" in data:
            attrs["error_status"] = data["device_errstatus"]
        if "ai_control" in data:
            attrs["ai_control"] = data["ai_control"]
        return attrs

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        target_temp = kwargs.get(ATTR_TEMPERATURE)
        if target_temp is None:
            return

        _LOGGER.debug("Setting %s temperature to %s°C", self.name, target_temp)
        try:
            await self.hass.async_add_executor_job(
                functools.partial(
                    self._session.set_device_status,
                    self.appliance_id,
                    temperature=target_temp,
                )
            )
            await self.coordinator.async_request_refresh()
        except EoliaError as err:
            _LOGGER.error("Failed to set temperature on %s: %s", self.name, err)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set operation mode."""
        _LOGGER.debug("Setting %s HVAC mode to %s", self.name, hvac_mode)
        try:
            if hvac_mode == HVACMode.OFF:
                await self.hass.async_add_executor_job(
                    functools.partial(
                        self._session.set_device_status,
                        self.appliance_id,
                        power=False,
                    )
                )
            else:
                eolia_mode = HVAC_TO_EOLIA.get(hvac_mode, OperationMode.AUTO.value)
                await self.hass.async_add_executor_job(
                    functools.partial(
                        self._session.set_device_status,
                        self.appliance_id,
                        power=True,
                        mode=eolia_mode,
                    )
                )
            await self.coordinator.async_request_refresh()
        except EoliaError as err:
            _LOGGER.error("Failed to set HVAC mode on %s: %s", self.name, err)

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set fan mode."""
        _LOGGER.debug("Setting %s fan mode to %s", self.name, fan_mode)
        fan_speed_enum = FAN_MODES.get(fan_mode, FanSpeed.AUTO)
        try:
            await self.hass.async_add_executor_job(
                functools.partial(
                    self._session.set_device_status,
                    self.appliance_id,
                    fan_speed=fan_speed_enum,
                )
            )
            await self.coordinator.async_request_refresh()
        except EoliaError as err:
            _LOGGER.error("Failed to set fan mode on %s: %s", self.name, err)

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set vertical swing mode."""
        _LOGGER.debug("Setting %s swing mode to %s", self.name, swing_mode)
        swing_enum = SWING_MODES.get(swing_mode, AirSwingUD.AUTO)
        try:
            await self.hass.async_add_executor_job(
                functools.partial(
                    self._session.set_device_status,
                    self.appliance_id,
                    air_swing_vertical=swing_enum,
                )
            )
            await self.coordinator.async_request_refresh()
        except EoliaError as err:
            _LOGGER.error("Failed to set swing mode on %s: %s", self.name, err)

    async def async_turn_on(self) -> None:
        """Turn on the device."""
        _LOGGER.debug("Turning on %s", self.name)
        try:
            await self.hass.async_add_executor_job(
                functools.partial(
                    self._session.set_device_status,
                    self.appliance_id,
                    power=True,
                )
            )
            await self.coordinator.async_request_refresh()
        except EoliaError as err:
            _LOGGER.error("Failed to turn on %s: %s", self.name, err)

    async def async_turn_off(self) -> None:
        """Turn off the device."""
        _LOGGER.debug("Turning off %s", self.name)
        try:
            await self.hass.async_add_executor_job(
                functools.partial(
                    self._session.set_device_status,
                    self.appliance_id,
                    power=False,
                )
            )
            await self.coordinator.async_request_refresh()
        except EoliaError as err:
            _LOGGER.error("Failed to turn off %s: %s", self.name, err)
