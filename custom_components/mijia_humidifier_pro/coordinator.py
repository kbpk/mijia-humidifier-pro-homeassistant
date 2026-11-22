"""Poll device state and serialize writes with refreshes."""

import asyncio
import logging
from datetime import timedelta
from time import monotonic

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    HomeAssistantError,
)
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN
from .device import (
    Identity,
    Property,
    State,
    UnsupportedModel,
    identify,
    read_state,
    write_property,
)
from .miio import (
    MiIOClient,
    MiIOConnectionError,
    MiIOError,
    MiIOInvalidTokenError,
    MiIOTimeoutError,
)

_LOGGER = logging.getLogger(__name__)
_TRANSIENT_ERRORS = (MiIOTimeoutError, MiIOConnectionError)

type HumidifierEntry = ConfigEntry[HumidifierCoordinator]


class HumidifierCoordinator(DataUpdateCoordinator[State]):
    """Maintain a single state snapshot for all entities."""

    def __init__(
        self, hass: HomeAssistant, entry: HumidifierEntry, client: MiIOClient
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=20),
            always_update=False,
        )
        self.client = client
        self.identity: Identity
        self._lock = asyncio.Lock()
        self._last_success: float | None = None

    async def _async_setup(self) -> None:
        try:
            self.identity = await self.hass.async_add_executor_job(
                identify, self.client
            )
        except UnsupportedModel as err:
            raise ConfigEntryError(str(err)) from err
        except MiIOInvalidTokenError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except MiIOError as err:
            raise UpdateFailed(str(err)) from err

    async def _async_update_data(self) -> State:
        async with self._lock:
            try:
                try:
                    state = await self.hass.async_add_executor_job(
                        read_state, self.client
                    )
                except _TRANSIENT_ERRORS:
                    await asyncio.sleep(0.25)
                    state = await self.hass.async_add_executor_job(
                        read_state, self.client
                    )
            except _TRANSIENT_ERRORS as err:
                if (
                    self.last_update_success
                    and self._last_success is not None
                    and monotonic() - self._last_success < 40
                ):
                    return self.data
                raise UpdateFailed(str(err)) from err
            except MiIOInvalidTokenError as err:
                raise ConfigEntryAuthFailed(str(err)) from err
            except MiIOError as err:
                raise UpdateFailed(str(err)) from err
            self._last_success = monotonic()
            return state

    async def async_write(self, prop: Property, value: bool | int) -> None:
        async with self._lock:
            try:
                await self.hass.async_add_executor_job(
                    write_property, self.client, prop, value
                )
            except (MiIOError, ValueError) as err:
                raise HomeAssistantError(
                    translation_domain=DOMAIN, translation_key="command_failed"
                ) from err

            # Confirmed settings can be reflected immediately. When recovering from
            # a failed poll, wait for a full refresh before marking entities available.
            if self.last_update_success:
                self.async_set_updated_data({**self.data, prop: value})
