"""Device registry metadata shared by the humidifier entities."""

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MODEL, NAME
from .coordinator import HumidifierCoordinator
from .device import Property


class MijiaEntity(CoordinatorEntity[HumidifierCoordinator]):
    """Group every entity under the authenticated MiIO device ID."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: HumidifierCoordinator, key: str, prop: Property | None = None
    ) -> None:
        super().__init__(coordinator)
        identity = coordinator.identity
        self.prop = prop
        self._attr_unique_id = f"{identity.device_id}-{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, identity.device_id)},
            manufacturer="Xiaomi",
            model=NAME,
            model_id=MODEL,
            name=NAME,
            sw_version=identity.firmware,
        )

    @property
    def available(self) -> bool:
        return super().available and (
            self.prop is None or self.prop in self.coordinator.data
        )

    @property
    def value(self) -> bool | int | None:
        if self.prop is None:
            return None
        return self.coordinator.data.get(self.prop)
