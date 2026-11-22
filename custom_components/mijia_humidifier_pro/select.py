"""Display brightness setting."""

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import HumidifierCoordinator, HumidifierEntry
from .device import Property
from .entity import MijiaEntity

PARALLEL_UPDATES = 0

_OPTIONS = ("dim", "bright")


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HumidifierEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([MijiaDisplayBrightness(entry.runtime_data)])


class MijiaDisplayBrightness(MijiaEntity, SelectEntity):
    """Represent the two display levels from the device specification."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "display_brightness"
    _attr_options = list(_OPTIONS)

    def __init__(self, coordinator: HumidifierCoordinator) -> None:
        super().__init__(coordinator, "display_brightness", Property.DISPLAY_BRIGHTNESS)

    @property
    def current_option(self) -> str | None:
        value = self.value
        return _OPTIONS[value] if value is not None else None

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.async_write(
            Property.DISPLAY_BRIGHTNESS, _OPTIONS.index(option)
        )
