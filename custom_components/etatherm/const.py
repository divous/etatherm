"""Konstanty pro Etatherm integraci."""

DOMAIN = "etatherm"

CONF_HOST = "host"
CONF_PORT = "port"
CONF_BUS_HIGH = "bus_high"
CONF_BUS_LOW = "bus_low"
CONF_POLL_INTERVAL = "poll_interval"
CONF_EXCLUDE_IDS = "exclude_ids"
CONF_ROOMS = "rooms"

DEFAULT_PORT = 50001
DEFAULT_BUS_HIGH = 0x00
DEFAULT_BUS_LOW = 0x01
DEFAULT_POLL_INTERVAL = 60
DEFAULT_EXCLUDE_IDS = [15]

DEFAULT_ROZ_TEMP = 21.0
DEFAULT_ROZ_HOURS = 48.0
MIN_TEMP = 6.0
MAX_TEMP = 35.0
TEMP_STEP = 1.0

ROOM_NAMES = {
    1: "Šatna",
    2: "Maja",
    3: "Anka",
    4: "Vašek",
    5: "Tom",
    6: "Ložnice",
    7: "Žlutý pokoj",
    8: "Schodiště",
    9: "R obývák",
    10: "R zimní zahrada",
    11: "Vstup",
    12: "Koupelna",
    13: "Kuchyň",
    14: "Obývák",
    15: "Černé podlaží",
    16: "Zimní zahrada R",
}

ATTR_DEVICE_ID = "device_id"
ATTR_TEMPERATURE = "temperature"
ATTR_DURATION_HOURS = "duration_hours"

SERVICE_SET_ROZ = "set_roz"
SERVICE_CANCEL_ROZ = "cancel_roz"
