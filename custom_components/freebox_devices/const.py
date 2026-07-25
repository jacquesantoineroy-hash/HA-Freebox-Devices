"""Constantes pour l'intégration Freebox Devices."""

DOMAIN = "freebox_devices"

# Identité de l'application déclarée auprès de la Freebox (distincte de
# l'intégration core `freebox`, qui a son propre app_id).
APP_ID = "fr.familleroy.freebox_devices"
APP_NAME = "Freebox Devices (Home Assistant)"
APP_VERSION = "1.0.0"
DEVICE_NAME = "Home Assistant"

CONF_HOST = "host"
CONF_PORT = "port"
CONF_APP_TOKEN = "app_token"

DEFAULT_HOST = "mafreebox.freebox.fr"
DEFAULT_PORT = 443

# Versions d'API distinctes utilisées volontairement : v8 pour
# login/lan/mac_filter, v10 pour wifi/ap (stations + signal). Ce sont les
# versions confirmées fonctionnelles sur le boitier de l'utilisateur
# (Freebox Ultra / V9) lors des tests précédents sur le relais Pi.
API_VERSION_MAIN = "v8"
API_VERSION_WIFI = "v10"

DEFAULT_SCAN_INTERVAL = 10  # secondes
DEFAULT_CONSIDER_HOME = 90  # secondes, cf. doc officielle freebox (délai de déconnexion)

STORAGE_VERSION = 1
STORAGE_KEY_TEMPLATE = "freebox_devices_conn_cache_{entry_id}"

# Statuts possibles de GET /login/authorize/{track_id}/
AUTHORIZE_STATUS_PENDING = "pending"
AUTHORIZE_STATUS_GRANTED = "granted"
AUTHORIZE_STATUS_DENIED = "denied"
AUTHORIZE_STATUS_TIMEOUT = "timeout"

# Champs exposés par le coordinator pour chaque appareil (dict indexé par MAC)
ATTR_MAC = "mac"
ATTR_HOSTNAME = "hostname"
ATTR_IP = "ip"
ATTR_ACTIVE = "active"
ATTR_WIFI = "wifi"
ATTR_CONNECTIVITY_TYPE = "connectivity_type"
ATTR_HOST_TYPE = "host_type"
ATTR_VENDOR = "vendor"
ATTR_BLOCKED = "blocked"
ATTR_SIGNAL = "signal"
