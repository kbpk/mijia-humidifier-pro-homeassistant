"""MIoT properties for xiaomi.humidifier.600ek."""

from dataclasses import dataclass
from enum import Enum, StrEnum
from typing import Any

from .const import MAX_HUMIDITY, MIN_HUMIDITY, MODEL
from .miio import MiIOClient, MiIODeviceError, MiIOProtocolError


class Method(StrEnum):
    INFO = "miIO.info"
    READ = "get_properties"
    WRITE = "set_properties"


class Property(Enum):
    POWER = (2, 1)
    FAULT = (2, 2)
    MODE = (2, 3)
    TARGET_HUMIDITY = (2, 5)
    DRYING_TIME = (2, 10)
    OVERWET_PROTECTION = (2, 11)
    HUMIDITY = (3, 1)
    DISPLAY = (6, 1)
    DISPLAY_BRIGHTNESS = (6, 2)
    BEEPER = (7, 1)
    CHILD_LOCK = (8, 1)

    def request_fields(self) -> dict[str, str | int]:
        siid, piid = self.value
        return {"did": f"{siid}-{piid}", "siid": siid, "piid": piid}


class UnsupportedModel(MiIOProtocolError):
    """The authenticated device reports a different model."""


@dataclass(frozen=True, slots=True)
class Identity:
    device_id: str
    firmware: str | None


type State = dict[Property, bool | int]

_BOOLEAN = {
    Property.POWER,
    Property.DISPLAY,
    Property.BEEPER,
    Property.CHILD_LOCK,
    Property.OVERWET_PROTECTION,
}
_RANGES = {
    Property.FAULT: (0, 255),
    Property.MODE: (0, 3),
    Property.TARGET_HUMIDITY: (MIN_HUMIDITY, MAX_HUMIDITY),
    Property.DRYING_TIME: (0, 180),
    Property.HUMIDITY: (0, 100),
    Property.DISPLAY_BRIGHTNESS: (0, 1),
}
_BATCHES = (
    (
        Property.POWER,
        Property.MODE,
        Property.TARGET_HUMIDITY,
        Property.HUMIDITY,
        Property.FAULT,
        Property.DRYING_TIME,
    ),
    (
        Property.DISPLAY,
        Property.DISPLAY_BRIGHTNESS,
        Property.BEEPER,
        Property.CHILD_LOCK,
        Property.OVERWET_PROTECTION,
    ),
)
_WRITABLE = _BOOLEAN | {
    Property.MODE,
    Property.TARGET_HUMIDITY,
    Property.DISPLAY_BRIGHTNESS,
}


def _valid_value(prop: Property, value: Any) -> bool:
    if prop in _BOOLEAN:
        return type(value) is bool
    minimum, maximum = _RANGES[prop]
    return type(value) is int and minimum <= value <= maximum


def _result_rows(result: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(result, list):
        raise MiIOProtocolError("Expected a MIoT property list")
    rows = {}
    for row in result:
        if (
            not isinstance(row, dict)
            or not isinstance(did := row.get("did"), str)
            or type(row.get("code")) is not int
            or did in rows
        ):
            raise MiIOProtocolError("Malformed MIoT property reply")
        rows[did] = row
    return rows


def _row_for(rows: dict[str, dict[str, Any]], prop: Property) -> dict[str, Any] | None:
    fields = prop.request_fields()
    row = rows.get(str(fields["did"]))
    if row is not None and any(
        row.get(key, fields[key]) != fields[key] for key in ("siid", "piid")
    ):
        raise MiIOProtocolError("Unexpected MIoT property identifier")
    return row


def identify(client: MiIOClient) -> Identity:
    result = client.request(Method.INFO, [])
    if not isinstance(result, dict) or not isinstance(result.get("model"), str):
        raise MiIOProtocolError("Missing model in MiIO device info")
    if result["model"] != MODEL:
        raise UnsupportedModel("Unsupported Xiaomi humidifier model")
    assert client.device_id is not None
    firmware = result.get("fw_ver")
    return Identity(client.device_id, firmware if isinstance(firmware, str) else None)


def read_state(client: MiIOClient) -> State:
    state: State = {}
    for batch in _BATCHES:
        rows = _result_rows(
            client.request(Method.READ, [prop.request_fields() for prop in batch])
        )
        for prop in batch:
            row = _row_for(rows, prop)
            if (
                row is not None
                and row["code"] == 0
                and _valid_value(prop, row.get("value"))
            ):
                state[prop] = row["value"]
    if Property.POWER not in state:
        raise MiIOProtocolError("Device did not return its power state")
    return state


def write_property(client: MiIOClient, prop: Property, value: bool | int) -> None:
    if prop not in _WRITABLE or not _valid_value(prop, value):
        raise ValueError("Invalid value for writable MIoT property")
    result = client.request(Method.WRITE, [{**prop.request_fields(), "value": value}])
    row = _row_for(_result_rows(result), prop)
    if row is None:
        raise MiIOProtocolError("Missing MIoT write acknowledgment")
    if row["code"] != 0:
        raise MiIODeviceError(row["code"])
