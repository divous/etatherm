"""Climate entity pro Etatherm — jedna per místnost."""

import logging
from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MIN_TEMP, MAX_TEMP, TEMP_STEP, DEFAULT_ROZ_HOURS, DEFAULT_ROZ_TEMP
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
        entities.append(EtathermClimate(coordinator, device_id, room.name))
    async_add_entities(entities)


class EtathermClimate(CoordinatorEntity[EtathermCoordinator], ClimateEntity):
    """Climate entita pro jednu místnost Etatherm."""

    _attr_has_entity_name = True
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = [HVACMode.AUTO, HVACMode.HEAT]
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_min_temp = MIN_TEMP
    _attr_max_temp = MAX_TEMP
    _attr_target_temperature_step = TEMP_STEP

    def __init__(self, coordinator: EtathermCoordinator,
                 device_id: int, name: str) -> None:
        super().__init__(coordinator)
        self._device_id = device_id
        self._attr_name = name
        self._attr_unique_id = f"etatherm_climate_{device_id}"

    @property
    def _room(self):
        if self.coordinator.data:
            return self.coordinator.data.get(self._device_id)
        return None

    @property
    def current_temperature(self) -> float | None:
        room = self._room
        return room.real_temp if room else None

    @property
    def target_temperature(self) -> float | None:
        room = self._room
        if not room:
            return None
        # Pokud je ROZ aktivní, zobrazit ROZ teplotu jako cíl
        if room.roz_active and room.roz_temp is not None:
            return room.roz_temp
        return room.target_temp

    @property
    def hvac_mode(self) -> HVACMode:
        """AUTO = běží program, HEAT = ROZ aktivní."""
        room = self._room
        if room and room.roz_active:
            return HVACMode.HEAT
        return HVACMode.AUTO

    @property
    def hvac_action(self) -> HVACAction:
        room = self._room
        if not room or room.real_temp is None or room.target_temp is None:
            return HVACAction.IDLE
        target = room.roz_temp if (room.roz_active and room.roz_temp) else room.target_temp
        if room.real_temp < target:
            return HVACAction.HEATING
        return HVACAction.IDLE

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        room = self._room
        attrs = {"device_id": self._device_id}
        if room:
            attrs["program_target"] = room.target_temp
            if room.roz_active:
                attrs["roz_active"] = True
                attrs["roz_temp"] = room.roz_temp
                attrs["roz_end"] = room.roz_end.isoformat() if room.roz_end else None
            else:
                attrs["roz_active"] = False
        return attrs

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Nastavení teploty → aktivuje ROZ s defaultní dobou."""
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is not None:
            log.info("async_set_temperature: device_id=%d, temp=%.1f", self._device_id, temp)
            result = await self.coordinator.async_set_roz(
                self._device_id, float(temp), DEFAULT_ROZ_HOURS
            )
            log.info("async_set_temperature result: %s", result)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """AUTO = zrušit ROZ, HEAT = aktivovat ROZ s aktuální cílovou teplotou."""
        log.info("async_set_hvac_mode: device_id=%d, mode=%s", self._device_id, hvac_mode)
        if hvac_mode == HVACMode.AUTO:
            await self.coordinator.async_cancel_roz(self._device_id)
        elif hvac_mode == HVACMode.HEAT:
            # Použít ROZ preset teplotu z jednotky, nebo aktuální cíl, nebo default
            room = self._room
            if room and room.roz_temp is not None:
                temp = room.roz_temp
            elif room and room.target_temp is not None:
                temp = room.target_temp
            else:
                temp = DEFAULT_ROZ_TEMP
            log.info("HEAT: device_id=%d, temp=%.1f", self._device_id, temp)
            await self.coordinator.async_set_roz(
                self._device_id, float(temp), DEFAULT_ROZ_HOURS
            )
