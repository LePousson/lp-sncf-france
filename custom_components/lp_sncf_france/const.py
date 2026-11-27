"""Constants for LP SNCF France."""

from __future__ import annotations

from datetime import timedelta
from zoneinfo import ZoneInfo

DOMAIN = "lp_sncf_france"
TZ = ZoneInfo("Europe/Paris")

ATTRIBUTION = "Données SNCF Open Data / Gares & Connexions — licence ODbL"

# --- Open data sources (no API key required) ---------------------------------
ODS_BASE = "https://ressources.data.sncf.com/api/explore/v2.1/catalog/datasets"
DS_STATIONS = "gares-de-voyageurs"
DS_ASSISTANCE = "assistance-psh-pmr"
DS_LIFTS = "etat-fonctionnement-elevatique-gare"

GTFS_URL = "https://eu.ftp.opendatasoft.com/sncf/plandata/Export_OpenData_SNCF_GTFS_NewTripId.zip"
RT_ET_URL = "https://proxy.transport.data.gouv.fr/resource/sncf-siri-lite-estimated-timetable"
RT_SX_URL = "https://proxy.transport.data.gouv.fr/resource/sncf-siri-lite-situation-exchange"

# --- Refresh cadence ---------------------------------------------------------
REF_INTERVAL = timedelta(hours=24)
LIFTS_INTERVAL = timedelta(hours=1)
GTFS_INTERVAL = timedelta(hours=6)       # rebuild window; download when zip older than GTFS_MAX_AGE
GTFS_MAX_AGE = timedelta(hours=20)
RT_INTERVAL = timedelta(minutes=2)
SX_INTERVAL = timedelta(minutes=5)
BOARD_INTERVAL = timedelta(minutes=1)

HTTP_TIMEOUT = 60

# --- Config entry ------------------------------------------------------------
CONF_UIC = "uic"
CONF_STATION_ID = "station_id"
CONF_STATION_NAME = "station_name"
CONF_QUERY = "query"
CONF_ROWS = "rows"
CONF_HORIZON = "horizon_hours"
CONF_HIDE_MINOR = "hide_minor_messages"

DEFAULT_ROWS = 15
DEFAULT_HORIZON = 24
DEFAULT_HIDE_MINOR = False

# --- Display labels ----------------------------------------------------------
MODE_GTFS = {
    "Train TER": "TER",
    "Car TER": "Car TER",
    "TGV INOUI": "TGV INOUI",
    "OUIGO": "OUIGO",
    "OUIGO Train Classique": "OUIGO Classique",
    "INTERCITES": "Intercités",
    "INTERCITES de nuit": "Intercités de nuit",
    "TramTrain": "Tram-train",
    "Navette": "Navette",
}
MODE_SIRI = {
    "highSpeedRail": "TGV",
    "regionalRail": "TER",
    "interregionalRail": "Intercités",
    "longDistance": "Intercités",
    "nightRail": "Intercités de nuit",
    "suburbanRailway": "Transilien",
    "railShuttle": "Navette",
    "bus": "Car",
}

STATUS_SCHEDULED = "scheduled"
STATUS_ON_TIME = "on_time"
STATUS_DELAYED = "delayed"
STATUS_CANCELLED = "cancelled"

ASSIST_OPEN = "open"
ASSIST_CLOSED = "closed"
ASSIST_NONE = "none"
ASSIST_MOBILE = "mobile"
ASSIST_UNKNOWN = "unknown"

SERVICE_GET_BOARD = "get_board"
SERVICE_SEARCH = "search_stations"
SERVICE_REFRESH = "refresh"
