"""Teplotní senzory pro Etatherm — pro historii a grafy."""

import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
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
        entities.append(EtathermRealTempSensor(coordinator, device_id, room.name))
        entities.append(EtathermTargetTempSensor(coordinator, device_id, room.name))
    async_add_entities(entities)


class EtathermRealTempSensor(CoordinatorEntity[EtathermCoordinator], SensorEntity):
    """Skutečná teplota — pro graf historie."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(self, coordinator: EtathermCoordinator,
                 device_id: int, room_name: str) -> None:
        super().__init__(coordinator)
        self._device_id = device_id
        self._attr_name = f"{room_name} teplota"
        self._attr_unique_id = f"etatherm_real_temp_{device_id}"

    @property
    def native_value(self) -> float | None:
        if self.coordinator.data:
            room = self.coordinator.data.get(self._device_id)
            return room.real_temp if room else None
        return None


class EtathermTargetTempSensor(CoordinatorEntity[EtathermCoordinator], SensorEntity):
    """Cílová teplota (programová nebo ROZ) — pro graf historie."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(self, coordinator: EtathermCoordinator,
                 device_id: int, room_name: str) -> None:
        super().__init__(coordinator)
        self._device_id = device_id
        self._attr_name = f"{room_name} cíl"
        self._attr_unique_id = f"etatherm_target_temp_{device_id}"

    @property
    def native_value(self) -> float | None:
        if self.coordinator.data:
            room = self.coordinator.data.get(self._device_id)
            if room:
                if room.roz_active and room.roz_temp is not None:
                    return room.roz_temp
                return room.target_temp
        return None
