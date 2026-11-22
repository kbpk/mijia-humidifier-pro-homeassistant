"""Local MiIO UDP transport, adapted from kbpk/philips-sread1-homeassistant (MIT)."""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import socket
import struct
from dataclasses import dataclass
from threading import Lock
from time import monotonic
from typing import Any

from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

_MAGIC = 0x2131
_HEADER_SIZE = 32
_HELLO_PACKET = bytes.fromhex(
    "21310020ffffffffffffffffffffffffffffffffffffffffffffffffffffffff"
)
PORT = 54321


class MiIOError(Exception):
    """Base exception for MiIO communication errors."""


class MiIOTimeoutError(MiIOError):
    """The device did not reply before the timeout."""


class MiIOHandshakeTimeoutError(MiIOTimeoutError):
    """The device did not reply to the unauthenticated handshake."""


class MiIORequestTimeoutError(MiIOTimeoutError):
    """The device did not reply to an authenticated request."""


class MiIOConnectionError(MiIOError):
    """The UDP connection could not be created or used."""


class MiIOProtocolError(MiIOError):
    """The device returned a malformed or unexpected packet."""


class MiIOChecksumError(MiIOProtocolError):
    """A packet checksum did not match."""


class MiIOInvalidTokenError(MiIOChecksumError):
    """The response checksum indicates that the configured token is invalid."""


class MiIOJsonError(MiIOProtocolError):
    """The decrypted response was not valid MiIO JSON."""


class MiIODeviceError(MiIOError):
    """The device returned a MiIO error object."""

    def __init__(self, code: int | None) -> None:
        """Initialize a device error without exposing request credentials."""
        self.code = code
        super().__init__(f"Device error {code}")


@dataclass(frozen=True, slots=True)
class MiIOHandshake:
    """Data obtained from a MiIO handshake."""

    device_id: bytes
    timestamp: int


def _md5(data: bytes) -> bytes:
    """Return the MD5 required by the MiIO wire protocol."""
    return hashlib.md5(data, usedforsecurity=False).digest()


def _key_and_iv(token: bytes) -> tuple[bytes, bytes]:
    """Derive the MiIO AES key and IV from a raw token."""
    key = _md5(token)
    return key, _md5(key + token)


def _encrypt(plaintext: bytes, token: bytes) -> bytes:
    """Encrypt and PKCS#7-pad a MiIO payload."""
    key, iv = _key_and_iv(token)
    padder = padding.PKCS7(algorithms.AES.block_size).padder()
    padded = padder.update(plaintext) + padder.finalize()
    encryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
    return encryptor.update(padded) + encryptor.finalize()


def _decrypt(ciphertext: bytes, token: bytes) -> bytes:
    """Decrypt and PKCS#7-unpad a MiIO payload."""
    if not ciphertext or len(ciphertext) % 16:
        raise MiIOProtocolError("Encrypted payload has an invalid length")

    key, iv = _key_and_iv(token)
    decryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
    padded = decryptor.update(ciphertext) + decryptor.finalize()
    unpadder = padding.PKCS7(algorithms.AES.block_size).unpadder()
    try:
        return unpadder.update(padded) + unpadder.finalize()
    except ValueError as err:
        raise MiIOProtocolError("Response has invalid PKCS#7 padding") from err


def _build_packet(
    device_id: bytes, timestamp: int, token: bytes, payload: dict[str, Any]
) -> bytes:
    """Build a checksummed and encrypted MiIO request packet."""
    if len(device_id) != 4:
        raise MiIOProtocolError("Device ID must contain four bytes")

    plaintext = (
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        + b"\x00"
    )
    encrypted = _encrypt(plaintext, token)
    packet_length = _HEADER_SIZE + len(encrypted)
    if packet_length > 0xFFFF:
        raise MiIOProtocolError("Request packet is too large")

    header = struct.pack(">HHI4sI", _MAGIC, packet_length, 0, device_id, timestamp)
    checksum = _md5(header + token + encrypted)
    return header + checksum + encrypted


def _parse_header(packet: bytes) -> tuple[bytes, int, bytes, bytes]:
    """Validate a MiIO packet header and return its relevant fields."""
    if len(packet) < _HEADER_SIZE:
        raise MiIOProtocolError(f"MiIO packet is too short ({len(packet)} bytes)")

    magic, declared_length = struct.unpack(">HH", packet[:4])
    if magic != _MAGIC:
        raise MiIOProtocolError(f"Invalid MiIO magic 0x{magic:04x}")
    if declared_length != len(packet):
        raise MiIOProtocolError(
            f"MiIO length mismatch: header={declared_length}, actual={len(packet)}"
        )

    device_id = packet[8:12]
    timestamp = struct.unpack(">I", packet[12:16])[0]
    checksum = packet[16:32]
    encrypted = packet[32:]
    return device_id, timestamp, checksum, encrypted


def _parse_handshake(packet: bytes) -> MiIOHandshake:
    """Parse a handshake without treating its checksum field as a token."""
    device_id, timestamp, _checksum, encrypted = _parse_header(packet)
    if encrypted:
        raise MiIOProtocolError("Handshake response unexpectedly contains a payload")
    if device_id in (b"\x00" * 4, b"\xff" * 4):
        raise MiIOProtocolError("Handshake returned an invalid device ID")
    return MiIOHandshake(device_id=device_id, timestamp=timestamp)


def _parse_response(
    packet: bytes, token: bytes, expected_device_id: bytes
) -> dict[str, Any]:
    """Validate, decrypt, and decode a normal MiIO response."""
    device_id, _, checksum, encrypted = _parse_header(packet)
    if device_id != expected_device_id:
        raise MiIOProtocolError("Response came from an unexpected MiIO device ID")
    if not encrypted:
        raise MiIOProtocolError("MiIO response does not contain a payload")

    expected_checksum = _md5(packet[:16] + token + encrypted)
    if not hmac.compare_digest(checksum, expected_checksum):
        raise MiIOInvalidTokenError(
            "Response checksum mismatch; the MiIO token is probably invalid"
        )

    plaintext = _decrypt(encrypted, token).rstrip(b"\x00")
    try:
        decoded = plaintext.decode("utf-8")
    except UnicodeDecodeError as err:
        raise MiIOJsonError("MiIO response is not valid UTF-8") from err

    try:
        payload = json.loads(decoded)
    except json.JSONDecodeError as err:
        raise MiIOJsonError("MiIO response is not valid JSON") from err
    if not isinstance(payload, dict):
        raise MiIOJsonError("MiIO response JSON is not an object")
    return payload


class MiIOClient:
    """Exchange one authenticated command at a time over a connected UDP socket."""

    def __init__(self, host: str, token: bytes, device_id: str | None = None) -> None:
        self.host = host
        self.device_id = device_id
        self._token = token
        self._lock = Lock()
        self._request_id = secrets.randbelow(9998)
        self._port = PORT
        self._timeout = 2.0

    def request(self, method: str, params: Any) -> Any:
        """Run from an executor. Each exchange starts with a fresh handshake."""
        with self._lock, socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(self._timeout)
            try:
                sock.connect((self.host, self._port))
                sock.send(_HELLO_PACKET)
                handshake = _parse_handshake(sock.recv(65535))
            except TimeoutError as err:
                raise MiIOHandshakeTimeoutError("MiIO handshake timed out") from err
            except OSError as err:
                raise MiIOConnectionError("MiIO handshake failed") from err

            device_id = handshake.device_id.hex()
            if self.device_id is not None and device_id != self.device_id:
                raise MiIOProtocolError(
                    "Unexpected MiIO device at the configured address"
                )

            self._request_id = self._request_id % 9998 + 1
            payload = {"id": self._request_id, "method": method, "params": params}
            packet = _build_packet(
                handshake.device_id,
                (handshake.timestamp + 1) & 0xFFFFFFFF,
                self._token,
                payload,
            )
            try:
                sock.send(packet)
                response = self._receive(sock, handshake.device_id)
            except TimeoutError as err:
                raise MiIORequestTimeoutError(
                    "MiIO command timed out after handshake"
                ) from err
            except OSError as err:
                raise MiIOConnectionError("MiIO command exchange failed") from err

            self.device_id = device_id
            if "error" in response:
                error = response["error"]
                code = error.get("code") if isinstance(error, dict) else None
                raise MiIODeviceError(code if type(code) is int else None)
            if "result" not in response:
                raise MiIOProtocolError("MiIO response has no result")
            return response["result"]

    def _receive(self, sock: socket.socket, device_id: bytes) -> dict[str, Any]:
        deadline = monotonic() + self._timeout
        while (remaining := deadline - monotonic()) > 0:
            sock.settimeout(remaining)
            packet = sock.recv(65535)
            if len(packet) == _HEADER_SIZE and packet[:4] == _HELLO_PACKET[:4]:
                continue
            if (
                len(packet) == _HEADER_SIZE
                and packet[:2] == _HELLO_PACKET[:2]
                and int.from_bytes(packet[2:4], "big") > _HEADER_SIZE
                and packet[8:12] == device_id
            ):
                raise MiIOInvalidTokenError("MiIO device rejected authentication")
            response = _parse_response(packet, self._token, device_id)
            if type(response.get("id")) is int and response["id"] == self._request_id:
                return response
        raise TimeoutError
