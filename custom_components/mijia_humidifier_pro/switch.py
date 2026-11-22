"""Display, beeper, child lock and overwet-protection settings."""

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import HumidifierCoordinator, HumidifierEntry
from .device import Property
from .entity import MijiaEntity

PARALLEL_UPDATES = 0

_SWITCHES = {
    "display": Property.DISPLAY,
    "beeper": Property.BEEPER,
    "child_lock": Property.CHILD_LOCK,
    "overwet_protection": Property.OVERWET_PROTECTION,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HumidifierEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities(
        MijiaSwitch(entry.runtime_data, key, prop) for key, prop in _SWITCHES.items()
    )


class MijiaSwitch(MijiaEntity, SwitchEntity):
    """Expose an MIoT boolean setting."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self, coordinator: HumidifierCoordinator, key: str, prop: Property
    ) -> None:
        super().__init__(coordinator, key, prop)
        self._attr_translation_key = key
        self.prop = prop

    @property
    def is_on(self) -> bool | None:
        value = self.value
        return value if isinstance(value, bool) else None

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_write(self.prop, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_write(self.prop, False)
