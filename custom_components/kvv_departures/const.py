"""Constants for KVV Departures."""
DOMAIN = "kvv_departures"
VERSION = "2.1.0"  # keep in sync with manifest.json (checked by tests)

# Lovelace card shipped with the integration
CARD_FILE = "kvv-departures-card.js"
CARD_URL = f"/{DOMAIN}/{CARD_FILE}"

CONF_STOP_ID = "stop_id"
CONF_STOP_GID = "stop_gid"
CONF_STOP_NAME = "stop_name"

CONF_SOURCE = "source"
CONF_TRIAS_URL = "trias_url"
CONF_TRIAS_REF = "trias_requestor_ref"
CONF_LINES = "lines"
CONF_WALK = "walk_minutes"
CONF_COUNT = "departures"
CONF_INTERVAL = "scan_interval"

SOURCE_EFA = "efa"
SOURCE_TRIAS = "trias"

DEFAULT_COUNT = 5
DEFAULT_INTERVAL = 60
