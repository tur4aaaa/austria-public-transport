"""Constants for the Austria Public Transport integration."""

from datetime import timedelta

DOMAIN = "austria_public_transport"

API_ENDPOINT = "https://www.wienerlinien.at/ogd_realtime/monitor"
TRAFFIC_INFO_ENDPOINT = "https://www.wienerlinien.at/ogd_realtime/trafficInfoList"

API_TIMEOUT = 10

CONF_STOPS = "stops"
CONF_MAX_DEPARTURES = "max_departures"
DEFAULT_NAME = "Wiener Linien"
DEFAULT_MAX_DEPARTURES = 5
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=60)

FETCH_DEPARTURES_SERVICE_NAME = "fetch_departures"

WIENERLINIEN_TRAFFIC_INFO_SERVICE_NAME = "wienerlinien_traffic_info"
# Category names used by Wiener Linien trafficINfoList API
TRAFFIC_INFO_CATEGORIES = ["aufzugsinfo", "stoerunglang", "stoerungkurz"]
# Response order: disruptions before elevator outages, so max_alerts
# cuts elevator outages first

TRAFFIC_INFO_CATEGORY_ORDER = {"stoerunglang": 0, "stoerungkurz": 1, "aufzugsinfo": 2}
# message.messageCode of a successfull Wiener Linien OGD response

TRAFFIC_INFO_OK_CODE = 1
# successful API response code

# OeBB API
OEBB_API_ENDPOINT = "https://fahrplan.oebb.at/bin/mgate.exe"
OEBB_API_TIMEOUT = 15
OEBB_AUTH_AID = "OWDL4fE4ixNiPBBm"
OEBB_CLIENT_ID = "OEBB"
OEBB_CLIENT_TYPE = "WEB"
OEBB_CLIENT_NAME = "webapp"
OEBB_CLIENT_L = "vs_webapp"
OEBB_API_VERSION = "1.67"
OEBB_API_LANG = "deu"

# All 16 bits set — includes all product classes, notably bit 12 (4096)
# for private operators like Westbahn and RegioJet.
OEBB_ALL_PRODUCTS = 65535

OEBB_SEARCH_STATION_SERVICE_NAME = "oebb_search_station"
OEBB_STATION_BOARD_SERVICE_NAME = "oebb_station_board"
OEBB_TRIP_SEARCH_SERVICE_NAME = "oebb_trip_search"
OEBB_SERVICE_ALERTS_SERVICE_NAME = "oebb_service_alerts"
