"""The Felicity Battery (Local) integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_HOST, CONF_PORT, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL, DOMAIN
from .coordinator import FelicityBatteryCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "binary_sensor"]


def iter_devices(entry: ConfigEntry):
    """Yield (subentry_id, host, port) for the main device and every subentry.

    subentry_id is None for the device configured directly on the entry
    (the first battery), and the subentry's id for every battery added
    afterwards via the "+ Add device" button on the entry's page.
    """
    yield None, entry.data[CONF_HOST], entry.data[CONF_PORT]
    for subentry_id, subentry in entry.subentries.items():
        yield subentry_id, subentry.data[CONF_HOST], subentry.data[CONF_PORT]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    scan_interval = entry.options.get(
        CONF_SCAN_INTERVAL, entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    )

    coordinators: dict[str | None, FelicityBatteryCoordinator] = {}
    for subentry_id, host, port in iter_devices(entry):
        coordinator = FelicityBatteryCoordinator(hass, host, port, scan_interval)
        # Use async_refresh (not async_config_entry_first_refresh) so that one
        # unreachable battery doesn't raise ConfigEntryNotReady and abort setup
        # for every other battery on this entry - it just starts "unavailable"
        # and keeps retrying on its own polling schedule.
        await coordinator.async_refresh()
        if not coordinator.last_update_success:
            _LOGGER.warning(
                "Felicity battery at %s:%s did not respond on first refresh "
                "(will keep retrying): %s",
                host,
                port,
                coordinator.last_exception,
            )
        coordinators[subentry_id] = coordinator

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinators

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_update_options))
    return True


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
