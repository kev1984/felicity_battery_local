"""DataUpdateCoordinator for Felicity Battery (Local)."""
from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CMD_REAL_INFO, SOCKET_TIMEOUT
from .protocol import FelicityConnectionError, FelicityNoDataError, async_send_command

_LOGGER = logging.getLogger(__name__)


class FelicityBatteryCoordinator(DataUpdateCoordinator[dict]):
    """Polls the battery's local WiFi module for live data."""

    def __init__(self, hass: HomeAssistant, host: str, port: int, scan_interval: int) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name="Felicity Battery (Local)",
            update_interval=timedelta(seconds=scan_interval),
        )
        self.host = host
        self.port = port

    async def _async_update_data(self) -> dict:
        try:
            return await async_send_command(
                self.host, self.port, CMD_REAL_INFO, SOCKET_TIMEOUT
            )
        except (FelicityConnectionError, FelicityNoDataError) as err:
            raise UpdateFailed(str(err)) from err
