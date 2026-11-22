"""Local Xiaomi Mijia Smart Evaporative Humidifier Pro integration."""

from homeassistant.const import CONF_HOST, CONF_TOKEN, Platform
from homeassistant.core import HomeAssistant

from .coordinator import HumidifierCoordinator, HumidifierEntry
from .miio import MiIOClient

_PLATFORMS = (
    Platform.HUMIDIFIER,
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.SWITCH,
    Platform.SELECT,
)


async def async_setup_entry(hass: HomeAssistant, entry: HumidifierEntry) -> bool:
    client = MiIOClient(
        entry.data[CONF_HOST], bytes.fromhex(entry.data[CONF_TOKEN]), entry.unique_id
    )
    coordinator = HumidifierCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: HumidifierEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
