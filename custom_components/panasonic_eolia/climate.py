"""Support for Panasonic Eolia Air Conditioners via v6 Cloud API."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any, Dict, List, Optional

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.climate import (
    PLATFORM_SCHEMA,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_PASSWORD,
    CONF_USERNAME,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import (
    CONF_ACCESS_TOKEN,
    CONF_REFRESH_TOKEN,
    DOMAIN,
    AirSwingLR,
    AirSwingUD,
    FanSpeed,
    OperationMode,
)
from .eolia_api import EoliaAuth, EoliaAuthError, EoliaError, EoliaSession

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=60)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_REFRESH_TOKEN): cv.string,
        vol.Optional(CONF_ACCESS_TOKEN): cv.string,
        vol.Optional(CONF_USERNAME): cv.string,
        vol.Optional(CONF_PASSWORD): cv.string,
    }
)

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
    session: EoliaSession = hass.data[DOMAIN][entry.entry_id]

    try:
        devices_data = await hass.async_add_executor_job(session.get_devices)
    except EoliaError as err:
        _LOGGER.error("Failed to fetch Panasonic Eolia devices: %s", err)
        return

    entities = [PanasonicEoliaDevice(session, device) for device in devices_data]
    if entities:
        async_add_entities(entities, True)
    else:
        _LOGGER.warning("No Panasonic Eolia devices found for entry %s.", entry.title)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: Optional[DiscoveryInfoType] = None,
) -> None:
    """Set up the Panasonic Eolia climate platform from YAML."""
    refresh_token = config.get(CONF_REFRESH_TOKEN)
    access_token = config.get(CONF_ACCESS_TOKEN)

    if not refresh_token and not access_token:
        _LOGGER.error(
            "Panasonic Eolia now requires Auth0 authentication (refresh_token). "
            "Please use the Web UI integration flow or auth_helper.py script to configure."
        )
        return

    try:
        auth = EoliaAuth(refresh_token=refresh_token, access_token=access_token)
        session = EoliaSession(auth=auth)
        devices_data = session.get_devices()
    except EoliaError as err:
        _LOGGER.error("Failed to authenticate or fetch devices from Panasonic Eolia: %s", err)
        return

    entities = [PanasonicEoliaDevice(session, device) for device in devices_data]
    if entities:
        add_entities(entities, True)
    else:
        _LOGGER.warning("No Panasonic Eolia devices found on this account.")


class PanasonicEoliaDevice(ClimateEntity):
    """Representation of a Panasonic Eolia air conditioner device."""

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

    def __init__(self, session: EoliaSession, device: Dict[str, Any]) -> None:
        """Initialize the Eolia device entity."""
        self._session = session
        self._device = device
        self._appliance_id = device["id"]
        self._name = device.get("name") or self._appliance_id
        self._model = device.get("model", "")

        self._state_data: Dict[str, Any] = {}
        self._is_on: bool = False
        self._target_temp: Optional[float] = None
        self._inside_temp: Optional[float] = None
        self._outside_temp: Optional[float] = None
        self._inside_humidity: Optional[int] = None
        self._current_mode: str = OperationMode.COOL.value
        self._current_fan: str = "Auto"
        self._current_swing: str = "Auto"
        self._nanoex: bool = False
        self._air_flow: str = "not_set"

    @property
    def name(self) -> str:
        """Return the display name of this climate device."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return unique ID for this device."""
        return f"panasonic_eolia_{self._appliance_id}"

    @property
    def target_temperature(self) -> Optional[float]:
        """Return the target temperature."""
        return self._target_temp

    @property
    def current_temperature(self) -> Optional[float]:
        """Return the indoor temperature."""
        return self._inside_temp

    @property
    def current_humidity(self) -> Optional[int]:
        """Return the indoor humidity if available."""
        return self._inside_humidity

    @property
    def hvac_mode(self) -> HVACMode:
        """Return the current HVAC operation mode."""
        if not self._is_on:
            return HVACMode.OFF
        return EOLIA_TO_HVAC.get(self._current_mode, HVACMode.HEAT_COOL)

    @property
    def fan_mode(self) -> str:
        """Return current fan mode."""
        return self._current_fan

    @property
    def swing_mode(self) -> str:
        """Return current vertical swing mode."""
        return self._current_swing

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return extra state attributes for sensor monitoring."""
        attrs = {
            "appliance_id": self._appliance_id,
            "model": self._model,
            "raw_operation_mode": self._current_mode,
            "outside_temperature": self._outside_temp,
            "nanoex": self._nanoex,
            "air_flow": self._air_flow,
        }
        if "device_errstatus" in self._state_data:
            attrs["error_status"] = self._state_data["device_errstatus"]
        if "ai_control" in self._state_data:
            attrs["ai_control"] = self._state_data["ai_control"]
        return attrs

    def update(self) -> None:
        """Fetch updated state from Panasonic cloud."""
        try:
            data = self._session.get_device_status(self._appliance_id)
        except EoliaError as err:
            _LOGGER.error("Failed to update status for %s (%s): %s", self._name, self._appliance_id, err)
            return

        self._state_data = data

        # Power status
        self._is_on = bool(data.get("operation_status", False))

        # Operation Mode
        self._current_mode = data.get("operation_mode", OperationMode.COOL.value)

        # Target Temperature (126 indicates invalid/unset in Panasonic protocol)
        temp = data.get("temperature")
        self._target_temp = float(temp) if temp is not None and temp != 126 else None

        # Inside Temperature
        inside_temp = data.get("inside_temp")
        self._inside_temp = float(inside_temp) if inside_temp is not None and inside_temp != 126 else None

        # Outside Temperature
        outside_temp = data.get("outside_temp")
        self._outside_temp = float(outside_temp) if outside_temp is not None and outside_temp != 126 else None

        # Inside Humidity
        inside_hum = data.get("inside_humidity")
        self._inside_humidity = int(inside_hum) if inside_hum is not None and inside_hum != 126 else None

        # Fan Speed
        wind_volume = data.get("wind_volume", 0)
        self._current_fan = FAN_SPEED_TO_NAME.get(wind_volume, "Auto")

        # Swing Mode
        wind_direction = data.get("wind_direction", 0)
        self._current_swing = SWING_UD_TO_NAME.get(wind_direction, "Auto")

        # NanoeX & Air Flow
        self._nanoex = bool(data.get("nanoex", False))
        self._air_flow = str(data.get("air_flow", "not_set"))

    def set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        target_temp = kwargs.get(ATTR_TEMPERATURE)
        if target_temp is None:
            return

        _LOGGER.debug("Setting %s temperature to %s°C", self._name, target_temp)
        try:
            self._session.set_device_status(
                self._appliance_id,
                temperature=target_temp,
            )
            self._target_temp = target_temp
        except EoliaError as err:
            _LOGGER.error("Failed to set temperature on %s: %s", self._name, err)

    def set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set operation mode."""
        _LOGGER.debug("Setting %s HVAC mode to %s", self._name, hvac_mode)
        try:
            if hvac_mode == HVACMode.OFF:
                self._session.set_device_status(
                    self._appliance_id,
                    power=False,
                )
                self._is_on = False
            else:
                eolia_mode = HVAC_TO_EOLIA.get(hvac_mode, OperationMode.AUTO.value)
                self._session.set_device_status(
                    self._appliance_id,
                    power=True,
                    mode=eolia_mode,
                )
                self._is_on = True
                self._current_mode = eolia_mode
        except EoliaError as err:
            _LOGGER.error("Failed to set HVAC mode on %s: %s", self._name, err)

    def set_fan_mode(self, fan_mode: str) -> None:
        """Set fan mode."""
        _LOGGER.debug("Setting %s fan mode to %s", self._name, fan_mode)
        fan_speed_enum = FAN_MODES.get(fan_mode, FanSpeed.AUTO)
        try:
            self._session.set_device_status(
                self._appliance_id,
                fan_speed=fan_speed_enum,
            )
            self._current_fan = fan_mode
        except EoliaError as err:
            _LOGGER.error("Failed to set fan mode on %s: %s", self._name, err)

    def set_swing_mode(self, swing_mode: str) -> None:
        """Set vertical swing mode."""
        _LOGGER.debug("Setting %s swing mode to %s", self._name, swing_mode)
        swing_enum = SWING_MODES.get(swing_mode, AirSwingUD.AUTO)
        try:
            self._session.set_device_status(
                self._appliance_id,
                air_swing_vertical=swing_enum,
            )
            self._current_swing = swing_mode
        except EoliaError as err:
            _LOGGER.error("Failed to set swing mode on %s: %s", self._name, err)

    def turn_on(self) -> None:
        """Turn on the device."""
        _LOGGER.debug("Turning on %s", self._name)
        try:
            self._session.set_device_status(self._appliance_id, power=True)
            self._is_on = True
        except EoliaError as err:
            _LOGGER.error("Failed to turn on %s: %s", self._name, err)

    def turn_off(self) -> None:
        """Turn off the device."""
        _LOGGER.debug("Turning off %s", self._name)
        try:
            self._session.set_device_status(self._appliance_id, power=False)
            self._is_on = False
        except EoliaError as err:
            _LOGGER.error("Failed to turn off %s: %s", self._name, err)
