"""DataUpdateCoordinator pro Etatherm."""

import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import EtathermClient, RoomState

log = logging.getLogger(__name__)


class EtathermCoordinator(DataUpdateCoordinator[dict[int, RoomState]]):
    """Koordinátor pro polling Etatherm jednotky.

    Serializuje přístup k jednotce (má pomalé CPU) a sdílí data
    mezi všemi entitami (climate, sensor, binary_sensor).
    """

    def __init__(self, hass: HomeAssistant, client: EtathermClient,
                 poll_interval: int = 60) -> None:
        super().__init__(
            hass,
            log,
            name="Etatherm",
            update_interval=timedelta(seconds=poll_interval),
        )
        self.client = client

    async def _async_update_data(self) -> dict[int, RoomState]:
        """Načte data z jednotky (běží v executoru — blokující IO)."""
        try:
            rooms = await self.hass.async_add_executor_job(self.client.get_all_rooms)
        except Exception as err:
            raise UpdateFailed(f"Chyba komunikace s Etatherm: {err}") from err
        if not rooms:
            raise UpdateFailed("Etatherm nevrátil žádná data")
        return rooms

    async def async_set_roz(self, device_id: int, temp: float,
                            duration_hours: float) -> bool:
        """Nastaví ROZ — běží v executoru."""
        result = await self.hass.async_add_executor_job(
            self.client.set_roz, device_id, temp, duration_hours
        )
        if result:
            await self.async_request_refresh()
        return result

    async def async_cancel_roz(self, device_id: int) -> bool:
        """Zruší ROZ — běží v executoru."""
        result = await self.hass.async_add_executor_job(
            self.client.cancel_roz, device_id
        )
        if result:
            await self.async_request_refresh()
        return result
