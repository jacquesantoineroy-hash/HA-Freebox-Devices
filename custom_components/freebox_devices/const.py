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

# url_path du dashboard Lovelace "Freebox" de l'utilisateur — utilisé par
# number.py pour patcher directement le nombre de colonnes des sections
# Connectés/Déconnectés (pas de solution générique multi-dashboard pour
# l'instant, ce projet est taillé pour cet unique dashboard).
DASHBOARD_URL_PATH = "dashboard-freebox"

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
STORAGE_KEY_KNOWN_MACS_TEMPLATE = "freebox_devices_known_macs_{entry_id}"

# Événement HA émis la toute première fois qu'une MAC est vue (jamais vue
# depuis l'installation de l'intégration, persistant entre redémarrages) —
# à utiliser comme trigger "Événement" dans une automatisation pour être
# notifié des nouveaux appareils. data: mac, hostname, ip, vendor.
EVENT_NEW_DEVICE = f"{DOMAIN}_new_device"

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

# ------------------------------------------------------------------ #
# Contrôle parental (/api/v4/parental/) — nécessite la permission
# Freebox OS "Contrôle parental" en plus de "Modification des réglages",
# accordée manuellement par l'utilisateur (même principe que pour le
# verrou Wifi). cf. https://dev.freebox.fr/sdk/os/parental/
# ------------------------------------------------------------------ #
API_VERSION_PARENTAL = "v4"

DEFAULT_PARENTAL_SCAN_INTERVAL = 30  # secondes — les profils changent rarement

# filter_state / forced_mode / tmp_mode
PARENTAL_STATE_ALLOWED = "allowed"
PARENTAL_STATE_DENIED = "denied"
PARENTAL_STATE_WEBONLY = "webonly"

PARENTAL_TMP_MODE_DURATION = 3600  # secondes, durée du bouton "Pause 1h"

# Champs exposés par FreeboxParentalCoordinator pour chaque profil (dict
# indexé par id de filtre, cf. ParentalFilter dans la doc officielle)
ATTR_FILTER_ID = "id"
ATTR_DESC = "desc"
ATTR_HOSTS = "hosts"
ATTR_MACS = "macs"
ATTR_FORCED = "forced"
ATTR_FORCED_MODE = "forced_mode"
ATTR_TMP_MODE = "tmp_mode"
ATTR_TMP_MODE_EXPIRE = "tmp_mode_expire"
ATTR_SCHEDULING_MODE = "scheduling_mode"
ATTR_FILTER_STATE = "filter_state"
ATTR_NEXT_CHANGE = "next_change"
