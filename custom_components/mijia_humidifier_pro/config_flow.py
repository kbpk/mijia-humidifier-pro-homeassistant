"""Add and reconfigure a humidifier by local IPv4 address and token."""

import re
from ipaddress import IPv4Address
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_TOKEN
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import DOMAIN, NAME
from .device import UnsupportedModel, identify, read_state
from .miio import (
    MiIOClient,
    MiIOConnectionError,
    MiIOError,
    MiIOHandshakeTimeoutError,
    MiIOInvalidTokenError,
    MiIORequestTimeoutError,
)


def _probe(client: MiIOClient) -> str:
    identity = identify(client)
    read_state(client)
    return identity.device_id


class HumidifierConfigFlow(ConfigFlow, domain=DOMAIN):
    """Validate local access before saving config."""

    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        return await self._async_connection_form("user", user_input)

    async def async_step_reconfigure(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        return await self._async_connection_form("reconfigure", user_input)

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        return await self._async_connection_form("reauth_confirm", user_input)

    async def _async_connection_form(
        self,
        step_id: str,
        user_input: dict[str, Any] | None,
    ) -> ConfigFlowResult:
        entry = None
        if step_id == "reconfigure":
            entry = self._get_reconfigure_entry()
        elif step_id == "reauth_confirm":
            entry = self._get_reauth_entry()
        previous_host = entry.data[CONF_HOST] if entry is not None else ""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            token = user_input[CONF_TOKEN].strip()
            previous_host = host
            try:
                address = IPv4Address(host)
                if (
                    address.is_unspecified
                    or address.is_multicast
                    or int(address) == 0xFFFFFFFF
                ):
                    raise ValueError
            except ValueError:
                errors[CONF_HOST] = "invalid_host"
            if not re.fullmatch(r"[0-9a-fA-F]{32}", token):
                errors[CONF_TOKEN] = "invalid_token_format"

            if not errors:
                client = MiIOClient(host, bytes.fromhex(token))
                try:
                    device_id = await self.hass.async_add_executor_job(_probe, client)
                except (MiIOHandshakeTimeoutError, MiIOConnectionError):
                    errors["base"] = "cannot_connect"
                except MiIORequestTimeoutError:
                    errors["base"] = "no_authenticated_reply"
                except MiIOInvalidTokenError:
                    errors["base"] = "invalid_auth"
                except UnsupportedModel:
                    errors["base"] = "unsupported_model"
                except MiIOError:
                    errors["base"] = "invalid_response"
                else:
                    await self.async_set_unique_id(device_id)
                    data = {CONF_HOST: host, CONF_TOKEN: token.lower()}
                    if entry is not None:
                        self._abort_if_unique_id_mismatch()
                        return self.async_update_reload_and_abort(
                            entry, data_updates=data
                        )
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(title=NAME, data=data)

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_HOST, description={"suggested_value": previous_host}
                ): TextSelector(),
                vol.Required(CONF_TOKEN): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.PASSWORD)
                ),
            }
        )
        return self.async_show_form(step_id=step_id, data_schema=schema, errors=errors)
