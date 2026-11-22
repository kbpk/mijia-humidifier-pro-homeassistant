"""Humidity, remaining drying time and device fault code."""

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import HumidifierCoordinator, HumidifierEntry
from .device import Property
from .entity import MijiaEntity

PARALLEL_UPDATES = 0

_SENSORS = {
    Property.HUMIDITY: SensorEntityDescription(
        key="humidity",
        translation_key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    Property.DRYING_TIME: SensorEntityDescription(
        key="drying_time",
        translation_key="drying_time",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
    ),
    Property.FAULT: SensorEntityDescription(
        key="fault_code",
        translation_key="fault_code",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HumidifierEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities(
        MijiaSensor(entry.runtime_data, prop, description)
        for prop, description in _SENSORS.items()
    )


class MijiaSensor(MijiaEntity, SensorEntity):
    """Expose an individual read-only MIoT property."""

    def __init__(
        self,
        coordinator: HumidifierCoordinator,
        prop: Property,
        description: SensorEntityDescription,
    ) -> None:
        super().__init__(coordinator, description.key, prop)
        self.entity_description = description

    @property
    def native_value(self) -> int | None:
        return self.value
