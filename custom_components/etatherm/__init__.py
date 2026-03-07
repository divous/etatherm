"""Etatherm ETH1eD — Home Assistant integrace."""

import logging

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant, ServiceCall

from .client import EtathermClient
from .const import (
    DOMAIN, DEFAULT_PORT, DEFAULT_POLL_INTERVAL, DEFAULT_EXCLUDE_IDS,
    ROOM_NAMES, ATTR_DEVICE_ID, ATTR_TEMPERATURE, ATTR_DURATION_HOURS,
    DEFAULT_ROZ_TEMP, DEFAULT_ROZ_HOURS, SERVICE_SET_ROZ, SERVICE_CANCEL_ROZ,
    MIN_TEMP, MAX_TEMP,
)
from .coordinator import EtathermCoordinator

log = logging.getLogger(__name__)

PLATFORMS = [Platform.CLIMATE, Platform.SENSOR, Platform.BINARY_SENSOR]

SET_ROZ_SCHEMA = vol.Schema({
    vol.Required(ATTR_DEVICE_ID): vol.All(int, vol.Range(min=1, max=16)),
    vol.Optional(ATTR_TEMPERATURE, default=DEFAULT_ROZ_TEMP): vol.All(
        vol.Coerce(float), vol.Range(min=MIN_TEMP, max=MAX_TEMP)
    ),
    vol.Optional(ATTR_DURATION_HOURS, default=DEFAULT_ROZ_HOURS): vol.All(
        vol.Coerce(float), vol.Range(min=0.25, max=720)
    ),
})

CANCEL_ROZ_SCHEMA = vol.Schema({
    vol.Required(ATTR_DEVICE_ID): vol.All(int, vol.Range(min=1, max=16)),
})


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Nastavení integrace z config entry."""
    host = entry.data[CONF_HOST]
    port = entry.data.get(CONF_PORT, DEFAULT_PORT)

    client = EtathermClient(
        host=host,
        port=port,
        room_names=ROOM_NAMES,
        exclude_ids=set(DEFAULT_EXCLUDE_IDS),
    )

    # Počáteční připojení (blokující, v executoru)
    connected = await hass.async_add_executor_job(client.connect)
    if not connected:
        log.error("Nelze se připojit k Etatherm na %s:%d", host, port)
        return False

    coordinator = EtathermCoordinator(hass, client, DEFAULT_POLL_INTERVAL)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Registrace služeb (jen jednou)
    if not hass.services.has_service(DOMAIN, SERVICE_SET_ROZ):
        async def handle_set_roz(call: ServiceCall) -> None:
            device_id = call.data[ATTR_DEVICE_ID]
            temp = call.data.get(ATTR_TEMPERATURE, DEFAULT_ROZ_TEMP)
            hours = call.data.get(ATTR_DURATION_HOURS, DEFAULT_ROZ_HOURS)
            for coord in hass.data[DOMAIN].values():
                await coord.async_set_roz(device_id, temp, hours)

        async def handle_cancel_roz(call: ServiceCall) -> None:
            device_id = call.data[ATTR_DEVICE_ID]
            for coord in hass.data[DOMAIN].values():
                await coord.async_cancel_roz(device_id)

        hass.services.async_register(
            DOMAIN, SERVICE_SET_ROZ, handle_set_roz, schema=SET_ROZ_SCHEMA
        )
        hass.services.async_register(
            DOMAIN, SERVICE_CANCEL_ROZ, handle_cancel_roz, schema=CANCEL_ROZ_SCHEMA
        )

    log.info("Etatherm integrace nastavena (%s:%d)", host, port)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Odebrání integrace."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
