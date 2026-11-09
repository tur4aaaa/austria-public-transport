# Austria Public Transport (Wiener Linien & ÖBB)

Home Assistant custom integration for Austrian public transport: real-time Vienna departures from the [Wiener Linien OGD Realtime API](https://www.wienerlinien.at/ogd_realtime) and Austrian rail data from the [ÖBB Scotty API](https://fahrplan.oebb.at).

Can be used standalone or together with [vienna-transport-card](https://github.com/0Paul89/vienna-transport-card).

## Installation

**Requires Home Assistant 2026.3.0 or newer** (the version from which the integration's brand icons are served).

### HACS (recommended)

The integration is in the [HACS](https://hacs.xyz/) default store.

[![Open your Home Assistant instance and open this repository inside HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=slettmayer&repository=austria-public-transport&category=integration)

1. In HACS, search for **"Austria Public Transport"** and download it (or use the button above).
2. Restart Home Assistant.

### Manual

Copy `custom_components/austria_public_transport/` into your Home Assistant `config/custom_components/` directory and restart.

## Setup

Add the integration through the UI:

**Settings → Devices & Services → Add Integration → "Austria Public Transport"**

Enter one or more Wiener Linien stop IDs (comma-separated). You can find stop IDs with [till.mabe.at/rbl](https://till.mabe.at/rbl/).

Each stop becomes a sensor entity whose:
- **State:** number of upcoming departures
- **Attributes:** stop name, next departures (line, direction, countdown, planned/real time, accessibility info), server time

ÖBB train data (station search, departure boards, trip search, service alerts) is available on demand through the **services** below — no configuration required.

## Services

### `austria_public_transport.fetch_departures`

Fetches all departures for a given Wiener Linien stop ID on demand (returns data directly, does not update sensors).

| Field     | Required | Description                                          |
|-----------|----------|------------------------------------------------------|
| `stop_id` | Yes      | Stop ID from https://till.mabe.at/rbl/               |

Example:
```yaml
service: austria_public_transport.fetch_departures
data:
  stop_id: "4609"
response_variable: departures
```

The response includes `departures_count`, `stop_id`, `stop_name`, `departures` (list), and `server_time`.

---

### `austria_public_transport.wienerlinien_traffic_info`

Fetches current Wiener Linien disruptions and elevator outages on demand.

| Field        | Required | Description                                                                                                    |
|--------------|----------|----------------------------------------------------------------------------------------------------------------|
| `category`   | No       | `aufzugsinfo` (elevator outages), `stoerunglang` (long-term disruptions) or `stoerungkurz` (short-term disruptions). Default: all |
| `line`       | No       | Only alerts affecting this line, e.g. `U3` (case-insensitive)                                                  |
| `stop_id`    | No       | Only alerts affecting this stop ID. Long-term disruptions often list no stops and are then left out           |
| `max_alerts` | No       | Max alerts to return (default: 20)                                                                             |

Example:
```yaml
service: austria_public_transport.wienerlinien_traffic_info
data:
  category: aufzugsinfo
  line: U6
response_variable: traffic
```

Disruptions are listed before elevator outages, so `max_alerts` cuts elevator outages first. The response includes `alerts_count`, `total_count` (all matching alerts before the `max_alerts` cut, so you can tell the list was truncated) and `alerts` (list with `id`, `category`, `title`, `description`, `status`, `location`, `reason`, `priority`, `lines`, `stops`, `start`, `end`).

---

### `austria_public_transport.oebb_search_station`

Search OeBB stations by name to find station IDs.

| Field         | Required | Description                              |
|---------------|----------|------------------------------------------|
| `query`       | Yes      | Station name or partial name             |
| `max_results` | No       | Max stations to return (default: 10)     |

Example:
```yaml
service: austria_public_transport.oebb_search_station
data:
  query: "Wien Hauptbahnhof"
response_variable: stations
```

The response includes `results_count` and `stations` (list with `name`, `station_id`, `lid`, `type`, `latitude`, `longitude`).

---

### `austria_public_transport.oebb_station_board`

Fetch departures or arrivals at an OeBB station. Provide either `station_id` or `station_name` (auto-resolved).

| Field          | Required | Description                                        |
|----------------|----------|----------------------------------------------------|
| `station_id`   | No*      | OeBB station ID (use `oebb_search_station` to find)|
| `station_name` | No*      | Station name (auto-resolved via search)            |
| `board_type`   | No       | `DEP` for departures, `ARR` for arrivals (default: `DEP`) |
| `max_journeys` | No       | Max journeys to return (default: 10)               |

\* At least one of `station_id` or `station_name` is required.

Example:
```yaml
service: austria_public_transport.oebb_station_board
data:
  station_name: "Wien Hbf"
  board_type: "DEP"
  max_journeys: 5
response_variable: board
```

The response includes `station_name`, `station_id`, `board_type`, `journeys_count`, and `journeys` (list with `product`, `direction`, `time_planned`, `time_real`, `platform`).

---

### `austria_public_transport.oebb_trip_search`

Search for train connections between two OeBB stations. Provide either ID or name for each station.

| Field               | Required | Description                              |
|---------------------|----------|------------------------------------------|
| `from_station_id`   | No*      | Departure station ID                     |
| `from_station_name` | No*      | Departure station name (auto-resolved)   |
| `to_station_id`     | No*      | Arrival station ID                       |
| `to_station_name`   | No*      | Arrival station name (auto-resolved)     |
| `max_connections`   | No       | Max connections to return (default: 5)   |
| `time`              | No       | Departure or arrival time in local time (default: now) |
| `time_mode`         | No       | `departure` or `arrival` (default: `departure`) |
| `direct_only`       | No       | Only non-stop connections (default: `false`)    |

\* At least one of `from_station_id`/`from_station_name` and one of `to_station_id`/`to_station_name` required.

**Note:** The `time` field expects local time (Austrian CET/CEST). If omitted, the current time is used.

Example (next departures):
```yaml
service: austria_public_transport.oebb_trip_search
data:
  from_station_name: "Wien Hbf"
  to_station_name: "Salzburg Hbf"
  max_connections: 3
response_variable: trips
```

Example (future trip, arrive by 12:00):
```yaml
service: austria_public_transport.oebb_trip_search
data:
  from_station_name: "Wien Hbf"
  to_station_name: "Salzburg Hbf"
  time: "2026-04-15 12:00:00"
  time_mode: "arrival"
response_variable: trips
```

The response includes `from_station`, `to_station`, `connections_count`, and `connections` (list with `departure`, `arrival`, `duration`, `changes`, `platform_departure`, `platform_arrival`, and `legs` with per-segment details).

---

### `austria_public_transport.oebb_service_alerts`

Fetch current OeBB service alerts and disruptions (delays, cancellations, track closures).

| Field            | Required | Description                                          |
|------------------|----------|------------------------------------------------------|
| `max_alerts`     | No       | Max alerts to return (default: 20)                   |
| `product_filter` | No       | Bitmask for transport types (default: 65535 = all)   |

**Product filter bitmask values:** 1=ICE/RJX, 2=IC/EC, 4=NJ, 8=D/EN, 16=REX/R, 32=S-Bahn, 64=Bus, 128=Ferry, 256=U-Bahn, 512=Tram, 4096=private operators (Westbahn/RegioJet). Combine by adding values (e.g., 3 = ICE + IC only).

Example:
```yaml
service: austria_public_transport.oebb_service_alerts
data:
  max_alerts: 10
response_variable: alerts
```

The response includes `alerts_count` and `alerts` (list with `id`, `headline`, `text`, `priority`, `start_date`, `end_date`, `from_station`, `to_station`).

## Credits

Originally based on [wl_monitor](https://github.com/0Paul89/wl_monitor) by [@0Paul89](https://github.com/0Paul89); ÖBB support and ongoing maintenance by [@slettmayer](https://github.com/slettmayer). Licensed under [MIT](LICENSE) with the original author's consent.
