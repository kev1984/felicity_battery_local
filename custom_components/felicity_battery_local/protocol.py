"""Low-level TCP client for Felicity's local WiFi-module protocol."""
from __future__ import annotations

import asyncio
import json
import logging

from .const import READ_IDLE_TIMEOUT

_LOGGER = logging.getLogger(__name__)


class FelicityConnectionError(Exception):
    """Raised when the device cannot be reached."""


class FelicityNoDataError(Exception):
    """Raised when the device replied but with nothing usable."""


def _split_json_objects(raw: str) -> list[dict]:
    """Extract one or more top-level JSON objects from a raw response.

    The device sometimes glues multiple replies together, e.g. "{...}{...}"
    (typically one object per attached device: inverter + battery). This
    scans by brace-depth instead of naive string splitting, so it still
    works even if a value itself happens to contain "}{" text.
    """
    objects: list[dict] = []
    depth = 0
    start = None
    for i, ch in enumerate(raw):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            if depth > 0:
                depth -= 1
                if depth == 0 and start is not None:
                    chunk = raw[start : i + 1]
                    try:
                        obj = json.loads(chunk)
                        if isinstance(obj, dict):
                            objects.append(obj)
                    except json.JSONDecodeError:
                        _LOGGER.debug("Skipping malformed JSON chunk: %s", chunk)
                    start = None
    return objects


async def async_send_command(host: str, port: int, command: str, timeout: float) -> dict:
    """Open a TCP connection, send a command, and return the merged JSON reply."""
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=timeout
        )
    except (OSError, asyncio.TimeoutError) as err:
        raise FelicityConnectionError(f"Could not connect to {host}:{port}: {err}") from err

    try:
        writer.write(command.encode("ascii"))
        await writer.drain()

        chunks: list[bytes] = []
        try:
            while True:
                chunk = await asyncio.wait_for(reader.read(4096), timeout=READ_IDLE_TIMEOUT)
                if not chunk:
                    break
                chunks.append(chunk)
        except asyncio.TimeoutError:
            # Device went quiet - that's the normal end-of-reply signal for
            # this protocol (it doesn't close the socket itself).
            pass
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except OSError:
            pass

    raw = b"".join(chunks).decode("utf-8", errors="ignore").strip()
    if not raw:
        raise FelicityNoDataError(f"Empty reply from {host}:{port}")

    objects = _split_json_objects(raw)
    if not objects:
        raise FelicityNoDataError(f"Could not parse JSON from reply: {raw[:200]!r}")

    merged: dict = {}
    for obj in objects:
        merged.update(obj)
    return merged
