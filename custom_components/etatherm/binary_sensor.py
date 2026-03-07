"""Binary senzory pro ROZ stav — Etatherm."""

import logging
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import EtathermCoordinator

log = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: EtathermCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = []
    for device_id, room in coordinator.data.items():
        entities.append(EtathermROZSensor(coordinator, device_id, room.name))
    async_add_entities(entities)


class EtathermROZSensor(CoordinatorEntity[EtathermCoordinator], BinarySensorEntity):
    """Indikátor aktivní ROZ pro místnost."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.RUNNING

    def __init__(self, coordinator: EtathermCoordinator,
                 device_id: int, room_name: str) -> None:
        super().__init__(coordinator)
        self._device_id = device_id
        self._attr_name = f"{room_name} ROZ"
        self._attr_unique_id = f"etatherm_roz_{device_id}"

    @property
    def is_on(self) -> bool:
        if self.coordinator.data:
            room = self.coordinator.data.get(self._device_id)
            return room.roz_active if room else False
        return False

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        if self.coordinator.data:
            room = self.coordinator.data.get(self._device_id)
            if room and room.roz_active:
                return {
                    "roz_temp": room.roz_temp,
                    "roz_end": room.roz_end.isoformat() if room.roz_end else None,
                }
        return {}
