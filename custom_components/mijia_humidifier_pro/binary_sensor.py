"""Report water shortage from the device fault property."""

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import HumidifierCoordinator, HumidifierEntry
from .device import Property
from .entity import MijiaEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HumidifierEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([MijiaLowWater(entry.runtime_data)])


class MijiaLowWater(MijiaEntity, BinarySensorEntity):
    """Turn on when MIoT reports code 4."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_translation_key = "low_water"

    def __init__(self, coordinator: HumidifierCoordinator) -> None:
        super().__init__(coordinator, "low_water", Property.FAULT)

    @property
    def is_on(self) -> bool | None:
        value = self.value
        return value == 4 if value is not None else None
