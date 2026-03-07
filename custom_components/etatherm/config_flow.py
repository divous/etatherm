"""Config flow pro Etatherm integraci."""

import socket
import logging

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT

from .const import DOMAIN, DEFAULT_PORT

log = logging.getLogger(__name__)


class EtathermConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow pro Etatherm ETH1eD."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input.get(CONF_PORT, DEFAULT_PORT)

            # Test TCP spojení
            can_connect = await self.hass.async_add_executor_job(
                self._test_connection, host, port
            )
            if can_connect:
                await self.async_set_unique_id(f"etatherm_{host}")
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=f"Etatherm ({host})",
                    data={CONF_HOST: host, CONF_PORT: port},
                )
            else:
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_HOST, default="192.168.68.75"): str,
                vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
            }),
            errors=errors,
        )

    @staticmethod
    def _test_connection(host: str, port: int) -> bool:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(5)
            s.connect((host, port))
            s.close()
            return True
        except Exception:
            return False
