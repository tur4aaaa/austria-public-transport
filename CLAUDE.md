# Austria Public Transport (Wiener Linien & ÖBB)
> Home Assistant custom integration for real-time Vienna public transport departures via the Wiener Linien OGD Realtime API and OeBB (Austrian Federal Railways) train data via the OeBB Scotty API.

## Quick Reference
- **Install lint tooling**: `pip install -r requirements_lint.txt` (pins ruff, so local and CI agree)
- **Lint**: `ruff check .`
- **Format**: `ruff format .`
- **Test (unit)**: `pytest tests/ -v -m "not integration"`
- **Test (integration, real APIs)**: `pytest tests/ -v -m integration`
- **Validate (CI)**: Ruff + Hassfest + HACS + pytest unit tests (all must pass via `gate` job)

## Architecture Overview
Standard HA coordinator pattern with isolated API layer. All code lives in `custom_components/austria_public_transport/`.

- `api.py` -- pure async HTTP client for Wiener Linien (no HA imports, independently testable)
- `oebb_api.py` -- pure async HTTP client for OeBB Scotty API (no HA imports, independently testable)
- `coordinator.py` -- `DataUpdateCoordinator` subclass, one per stop, polls every 60s
- `sensor.py` -- `CoordinatorEntity` + `SensorEntity`, supports YAML and config entry setup
- `__init__.py` -- entry lifecycle, service registration (`fetch_departures`, `oebb_search_station`, `oebb_station_board`, `oebb_trip_search`, `oebb_service_alerts`, `wienerlinien_traffic_info`)
- `config_flow.py` -- `ConfigFlow` + `OptionsFlow` for UI-driven setup
- `const.py` -- all constants (URLs, keys, defaults)

Data flow (Wiener Linien): config -> coordinator -> `api.async_fetch_departures()` -> Wiener Linien API -> normalized departures -> sensor entity attributes.

Data flow (OeBB): service call -> `__init__.py` handler -> `oebb_api.async_oebb_*()` -> OeBB Scotty API -> normalized response -> service response. Trip search supports optional `time` (local time, CET/CEST), `time_mode` ("departure"/"arrival"), and `direct_only` (non-stop connections only).

## Tech Stack
- Python 3.12+, `from __future__ import annotations` in every file
- Home Assistant custom integration framework (`DataUpdateCoordinator`, `ConfigFlow`)
- `aiohttp` for async HTTP, `voluptuous` for schema validation
- `ruff` for linting/formatting, `pytest` + `pytest-asyncio` for testing
- `uv` for local environment management
- GitHub Actions CI (validate + auto-release from `manifest.json` version)

## Core Conventions
- All async functions use `async_` prefix (HA convention)
- Constants in `const.py` only -- no inline magic values
- Logger: `_LOGGER = logging.getLogger(__name__)` with `%s` formatting (not f-strings)
- Import order: `__future__` -> stdlib -> third-party -> HA -> local relative
- Classes: `WienerLinien*` prefix with HA suffix (e.g., `WienerLinienDataUpdateCoordinator`)
- Errors signaled via sentinel dict with `"message"` key, not exceptions
- Coordinator raises `UpdateFailed` on API error -- HA owns availability and retry backoff, and entities go unavailable instead of reporting stale departures
- Two failure paths follow from that: during setup, per-stop refreshes use `async_refresh()` so one unreachable stop cannot block the healthy ones, and only an entry where *every* stop failed raises `ConfigEntryNotReady` (`PlatformNotReady` on the YAML path) for HA to retry. After setup, a failed refresh just makes that stop's entity unavailable
- See [CONVENTIONS.md](docs/tech/CONVENTIONS.md) for full detail

## Business Domain
Vienna public transport departure monitoring and Austrian train connections. Each configured RBL stop ID becomes a sensor entity showing departure count and details. OeBB services provide on-demand station search, station departures, and trip planning. External APIs: Wiener Linien OGD Realtime API (public, no auth) and OeBB Scotty API (public, embedded auth). See [Domain Overview](docs/domain/OVERVIEW.md) for concepts and terminology.

## Structural Risks
- Test coverage exists for `api.py` and `oebb_api.py` -- coordinator, sensor, config flow are untested
- The `Tests` CI job installs `pytest pytest-asyncio aiohttp voluptuous homeassistant` inline and **unpinned**, so a Home Assistant release can change the verdict with no commit of ours. Only `ruff` is pinned (`requirements_lint.txt`). The job's Python must keep up with what current Home Assistant requires (3.14 as of 2026-10): on an older one pip silently resolves a years-old Home Assistant, which is how 3.12 broke the job
- `pyproject.toml` is tool configuration only; its `version` is inert and intentionally not synced with `manifest.json`, which is the one CI and `release.yml` read
- Sentinel dict error pattern is fragile -- callers must check `if "message" in result`
- YAML and config entry setup paths duplicate coordinator creation logic
- `trafficInfoList` endpoint constant defined but unused
- OeBB Scotty API is reverse-engineered (not officially documented) -- response structure may change without notice
- `datetime.now()` without timezone in `oebb_api.py` (suppressed via `noqa`) -- may be incorrect in non-local TZ containers

## Detailed Guides
- [Technical Context](docs/tech/README.md) -- architecture, tech stack, conventions, testing
- [Domain Context](docs/domain/README.md) -- business domain, entities, terminology, integrations
- [Documentation Contributing Guide](docs/README.md) -- how to maintain these docs
