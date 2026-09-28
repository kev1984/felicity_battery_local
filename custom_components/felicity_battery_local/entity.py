"""Shared helpers for Felicity Battery (Local) entities."""
from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo

from . import iter_devices
from .const import DOMAIN
from .coordinator import FelicityBatteryCoordinator


def get_path(data: dict, path: list) -> Any:
    """Safely walk nested dict/list structures, returning None if missing."""
    cur: Any = data
    for key in path:
        try:
            cur = cur[key]
        except (KeyError, IndexError, TypeError):
            return None
    return cur


def device_info(identifier: str, title: str, host: str, data: dict | None) -> DeviceInfo:
    """Build DeviceInfo, filling in serial/version fields once we have data."""
    info = DeviceInfo(
        identifiers={(DOMAIN, identifier)},
        name=title,
        manufacturer="Felicity",
        model="LUX-E-48250LG03",
        configuration_url=f"http://{host}",
    )
    if data:
        serial = data.get("DevSN")
        if serial:
            info["serial_number"] = serial
        comm_ver = data.get("CommVer")
        if comm_ver is not None:
            info["sw_version"] = f"CommVer {comm_ver}"
        mod_id = data.get("modID")
        if mod_id is not None:
            # "modID" appears to identify this unit's position/role among
            # parallel-connected batteries (observed values 1 and 2 across
            # two units on the same bus) - not officially documented.
            info["hw_version"] = f"Module {mod_id}"
    return info


def iter_platform_devices(hass: HomeAssistant, entry: ConfigEntry):
    """Yield (coordinator, identifier, title, host, subentry_id) for every
    device configured on this entry (the primary one plus every subentry)."""
    coordinators: dict[str | None, FelicityBatteryCoordinator] = hass.data[DOMAIN][
        entry.entry_id
    ]
    for subentry_id, host, port in iter_devices(entry):  # noqa: B007 - port unused here
        coordinator = coordinators[subentry_id]
        title = entry.title if subentry_id is None else entry.subentries[subentry_id].title
        identifier = entry.entry_id if subentry_id is None else subentry_id
        yield coordinator, identifier, title, host, subentry_id
