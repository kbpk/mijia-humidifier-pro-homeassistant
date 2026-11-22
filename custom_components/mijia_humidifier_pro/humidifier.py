"""The humidifier's power, humidity setpoint and mode."""

from typing import Any

from homeassistant.components.humidifier import (
    HumidifierDeviceClass,
    HumidifierEntity,
    HumidifierEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import MAX_HUMIDITY, MIN_HUMIDITY, MODES
from .coordinator import HumidifierCoordinator, HumidifierEntry
from .device import Property
from .entity import MijiaEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HumidifierEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([MijiaHumidifier(entry.runtime_data)])


class MijiaHumidifier(MijiaEntity, HumidifierEntity):
    """Represent the main appliance."""

    _attr_name = None
    _attr_translation_key = "humidifier"
    _attr_device_class = HumidifierDeviceClass.HUMIDIFIER
    _attr_min_humidity = MIN_HUMIDITY
    _attr_max_humidity = MAX_HUMIDITY
    _attr_target_humidity_step = 1
    _attr_supported_features = HumidifierEntityFeature.MODES
    _attr_available_modes = list(MODES)

    def __init__(self, coordinator: HumidifierCoordinator) -> None:
        super().__init__(coordinator, "humidifier", Property.POWER)

    @property
    def is_on(self) -> bool | None:
        value = self.value
        return value if isinstance(value, bool) else None

    @property
    def current_humidity(self) -> int | None:
        return self.coordinator.data.get(Property.HUMIDITY)

    @property
    def target_humidity(self) -> int | None:
        return self.coordinator.data.get(Property.TARGET_HUMIDITY)

    @property
    def mode(self) -> str | None:
        value = self.coordinator.data.get(Property.MODE)
        return MODES[value] if value is not None else None

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_write(Property.POWER, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_write(Property.POWER, False)

    async def async_set_humidity(self, humidity: int) -> None:
        await self.coordinator.async_write(Property.TARGET_HUMIDITY, round(humidity))

    async def async_set_mode(self, mode: str) -> None:
        await self.coordinator.async_write(Property.MODE, MODES.index(mode))
