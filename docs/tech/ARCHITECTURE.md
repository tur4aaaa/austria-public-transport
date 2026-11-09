# Architecture

## Purpose
Documents the project structure, module boundaries, data flow, and architectural patterns of the Wiener Linien Monitor integration.

## Responsibilities
- Defining module boundaries and ownership
- Describing data flow between layers
- Documenting the HA integration lifecycle (setup, polling, teardown)

## Non-Responsibilities
- Technology choices and tooling (see [TECH-STACK.md](TECH-STACK.md))
- Code style and naming rules (see [CONVENTIONS.md](CONVENTIONS.md))
- Domain concepts and terminology (see [Domain Overview](../domain/OVERVIEW.md))

## Overview

### Project Structure
```
custom_components/austria_public_transport/
  __init__.py       # Entry point: setup, teardown, service registration
  api.py            # Pure async API client for Wiener Linien (no HA imports)
  oebb_api.py       # Pure async API client for OeBB Scotty (no HA imports)
  coordinator.py    # DataUpdateCoordinator subclass (polling, error recovery)
  sensor.py         # SensorEntity platform (YAML + config entry setup)
  config_flow.py    # ConfigFlow + OptionsFlow (UI-driven setup)
  const.py          # All constants (URLs, keys, defaults)
  manifest.json     # HA/HACS metadata, version source-of-truth
  strings.json      # UI strings (English, canonical)
  services.yaml     # Service schema for HA UI
  translations/     # en.json, de.json
tests/
  conftest.py                  # HA mock injection via sys.modules
  test_api.py                  # Unit tests for api.py
  test_oebb_api.py             # Unit tests for oebb_api.py
  test_oebb_api_integration.py # Integration tests (real OeBB API)
```

### Architectural Pattern
Standard HA coordinator pattern with a clean API isolation layer:

```
api.py  <--  coordinator.py  <--  sensor.py
  ^               ^                    ^
  |               |                    |
  pure async      HA polling           HA entity
  no HA deps      orchestration        representation
```

### Module Boundaries

**`api.py`** -- Owns all HTTP communication with the Wiener Linien API.
- Input: `aiohttp.ClientSession`, `stop_id` (string)
- Output: normalized departure dict or error dict with `"message"` key
- Zero HA imports. Independently testable.

**`oebb_api.py`** -- Owns all HTTP communication with the OeBB Scotty API.
- Four public functions: `async_oebb_search_station`, `async_oebb_station_board`, `async_oebb_trip_search`, `async_oebb_service_alerts`
- Internal helpers: `_build_request_body` (POST envelope), `_async_loc_match` (raw LocMatch POST call), `_async_resolve_station` (station name-to-ID resolution, delegates to `_async_loc_match`), `_format_oebb_time` (date+time to ISO 8601), `_format_oebb_date` (OeBB `YYYYMMDD` to ISO 8601 date)
- Accepts station IDs (`extId`) or station names (auto-resolved via LocMatch) for board/trip services
- `async_oebb_trip_search` supports `time`/`time_mode` for future planning and `direct_only` (sets `maxChg: 0`) for non-stop connections
- `async_oebb_service_alerts` uses the `HimSearch` method with optional `product_filter` bitmask
- Output: normalized dicts or error dict with `"message"` key
- Zero HA imports. Independently testable.

**`coordinator.py`** -- Owns polling lifecycle for a single stop.
- Wraps `api.py` in a `DataUpdateCoordinator`
- Polls every 60 seconds (configurable via `const.MIN_TIME_BETWEEN_UPDATES`)
- On API error: raises `UpdateFailed`, so `last_update_success` flips false and the entities go unavailable
- During setup that failure is absorbed per stop: `async_setup_entry` (and the YAML `async_setup_platform`) calls `async_refresh()` per coordinator, keeps the healthy stops, and raises `ConfigEntryNotReady` / `PlatformNotReady` only if every stop failed -- an outage, rather than one wrong RBL number
- One coordinator instance per configured stop ID

**`sensor.py`** -- Owns translation of coordinator data into HA sensor entities.
- Subclasses `CoordinatorEntity` and `SensorEntity`
- State: departure count. Attributes: stop name, departures list (capped at `max_departures`), server time.
- Supports dual setup: YAML (`async_setup_platform`) and config entry (`async_setup_entry`)

**`__init__.py`** -- Owns entry lifecycle and service registration.
- Creates one coordinator per stop on `async_setup_entry`
- Registers five services in `async_setup`:
  - `fetch_departures` -- Wiener Linien departures (calls `api.py` directly)
  - `oebb_search_station` -- OeBB station search by name
  - `oebb_station_board` -- OeBB departures/arrivals at a station
  - `oebb_trip_search` -- OeBB connections between two stations
  - `oebb_service_alerts` -- OeBB service disruptions and infrastructure alerts
  - `wienerlinien_traffic_info` -- Wiener Linien disruptions and elevator outages (`api.async_fetch_traffic_info`)
- Defines `_require_one_of(*keys)` -- voluptuous validator factory enforcing "at least one of these keys" on service schemas (used by station board and trip search)
- Stores coordinators in `hass.data[DOMAIN][entry.entry_id]`

**`config_flow.py`** -- Owns UI setup and options editing.
- `ConfigFlow`: initial setup (name + comma-separated stop IDs)
- `OptionsFlow`: post-setup editing (stops + max_departures)
- Options take precedence over data via `.options.get(key, .data.get(key))`

**`const.py`** -- Pure data module. All magic values live here exclusively.

### Data Flow

1. User configures stop IDs (YAML or config flow)
2. `__init__.py` creates one `WienerLinienDataUpdateCoordinator` per stop
3. Coordinator polls `api.async_fetch_departures(session, stop_id)` every 60s
4. `api.py` sends GET to `https://www.wienerlinien.at/ogd_realtime/monitor?stopId=<id>`
5. API response is normalized: monitors and lines flattened into a sorted departure list
6. Coordinator caches the result; sensor reads from `coordinator.data`
7. Sensor exposes departure count as state, truncated list as attributes

The on-demand service (`fetch_departures`) bypasses steps 2-3 and calls `api.py` directly, returning data as a service response without updating sensor state.

### OeBB Data Flow (on-demand services only, no sensor entities)

1. User calls a service (e.g., `oebb_trip_search`) with station IDs or names
2. `__init__.py` handler calls the corresponding `oebb_api.py` function
3. If station names given: `_async_resolve_station` delegates to `_async_loc_match` to resolve to IDs
4. `oebb_api.py` sends POST to `https://fahrplan.oebb.at/bin/mgate.exe` with the appropriate method (LocMatch, StationBoard, TripSearch, or HimSearch)
5. Response is parsed: product names resolved from `common.prodL`, times converted to ISO 8601, locations resolved from `common.locL`
6. Normalized result returned directly as service response

`oebb_service_alerts` follows a simpler path (steps 1-2, then 4-6) -- no station resolution needed. It calls the `HimSearch` method with an optional `product_filter` bitmask to filter by transport type.

### Dual Setup Support
Both YAML and config entry setup paths are supported for backwards compatibility:
- YAML: `async_setup_platform` in `sensor.py` creates coordinators and sensors directly
- Config entry: `async_setup_entry` in `__init__.py` creates coordinators, then `async_setup_entry` in `sensor.py` creates sensors from stored coordinators

## Dependencies
- Internal: `const.py` is imported by all other modules. `api.py` is imported by `coordinator.py` and `__init__.py`. `oebb_api.py` is imported by `__init__.py`. `coordinator.py` is imported by `sensor.py` and `__init__.py`.
- External: `homeassistant` core, `aiohttp`, `voluptuous`

## Design Decisions
- API layer has zero HA imports -- enables unit testing without a running HA instance or complex mocking. Rationale: explicit isolation for testability.
- One coordinator per stop (not one coordinator for all stops) -- enables independent polling and error recovery per stop. Rationale: a single stop's API failure should not affect other stops.
- Error signaling via sentinel dicts (`{"message": "..."}`) instead of exceptions. Rationale not documented -- needs team input.
- No stale-data fallback -- the coordinator raises `UpdateFailed` rather than replaying the previous poll. Rationale: a silently stale departure count is worse than an unavailable entity, since automations cannot tell the difference.

## Known Risks
- Sentinel dict error pattern is fragile: callers must remember to check `if "message" in result`. An exception-based approach would be more Pythonic and harder to miss.
- YAML setup path duplicates coordinator creation logic that also exists in `__init__.py`. If one path is updated, the other may be forgotten.
- No rate limiting or backoff on API errors -- repeated failures still poll every 60s.
- OeBB Scotty API is reverse-engineered from the webapp -- response structure may change without notice. Integration tests help catch this early.
- `datetime.now()` used without timezone in `oebb_api.py` (suppressed via `# noqa: DTZ005`) -- may produce incorrect times when HA runs in a container with a non-local timezone.

## Extension Guidelines
- New modules should follow the existing layering: pure logic with no HA deps where possible, HA integration in a separate module.
- New entity platforms (e.g., binary_sensor) should follow the same `CoordinatorEntity` pattern as `sensor.py`.
- New services should be registered in `__init__.py` alongside the existing `fetch_departures` service.
- New config options should be added to both `ConfigFlow` and `OptionsFlow` in `config_flow.py`, with defaults in `const.py`.
