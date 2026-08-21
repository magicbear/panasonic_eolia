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

    if not refresh_token and not access_token:
        _LOGGER.warning(
            "未找到松下 Eolia 账号 '%s' 的认证 Token。请在 Home Assistant「设置 > 设备与服务」中点击「重新认证」或「重新配置」输入 Token。",
            entry.title,
        )
        raise ConfigEntryAuthFailed(
            f"未找到认证 Token ({entry.title})，请在「设置 > 设备与服务」中重新认证。"
        )

    auth = EoliaAuth(refresh_token=refresh_token, access_token=access_token)
    session = EoliaSession(auth=auth)

    # Fetch all devices
    try:
        devices_data = await hass.async_add_executor_job(session.get_devices)
    except EoliaAuthError as err:
        _LOGGER.warning(
            "松下 Eolia 账号 '%s' 认证已过期或无效 (%s)。请在 Home Assistant「设置 > 设备与服务」中点击「重新认证」或「重新配置」以更新 Token。",
            entry.title,
            err,
        )
        raise ConfigEntryAuthFailed(
            f"认证已失效 ({entry.title})。请在「设置 > 设备与服务」中重新认证更新 Token。"
        ) from err
    except EoliaError as err:
        if "E-21291-00002" in str(err):
            _LOGGER.warning(
                "松下 Eolia 系统时钟误差过大 (E-21291-00002)。主机时间与日本标准时间 (JST) 误差超过 5 分钟，请开启 NTP 网络对时并校准系统时间。"
            )
            raise ConfigEntryNotReady(
                "松下 Eolia 系统时钟误差过大 (E-21291-00002)，请校准系统时间。"
            ) from err
        _LOGGER.warning(
            "暂时无法连接到松下 Eolia 云端服务器 (%s): %s。Home Assistant 将在稍后自动重试连接。",
            entry.title,
            err,
        )
        raise ConfigEntryNotReady(
            f"暂时无法连接到松下 Eolia 云端服务器 ({entry.title}): {err}"
        ) from err

    if not devices_data:
        _LOGGER.warning(
            "未在松下 Eolia 账号 '%s' 下找到任何空调设备。请确认该松下账号在官方 App 中已添加空调设备。",
            entry.title,
        )

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
