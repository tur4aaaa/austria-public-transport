# Tech Stack

## Purpose
Documents the languages, frameworks, build tools, testing infrastructure, and external dependencies used by the Wiener Linien Monitor integration.

## Responsibilities
- Enumerating all runtime and development dependencies
- Documenting build, lint, and test tooling
- Describing CI/CD pipeline structure

## Non-Responsibilities
- Architectural patterns and data flow (see [ARCHITECTURE.md](ARCHITECTURE.md))
- Coding style rules and naming conventions (see [CONVENTIONS.md](CONVENTIONS.md))
- Test patterns and coverage details (see [TESTING.md](TESTING.md))

## Overview

### Language
- Python 3.12+ (minimum required)
- `from __future__ import annotations` in every source file
- Type annotations used consistently on function signatures and non-trivial locals

### Framework
- Home Assistant custom integration framework (`custom_components` convention)
- Key HA abstractions used: `DataUpdateCoordinator`, `CoordinatorEntity`, `SensorEntity`, `ConfigFlow`, `OptionsFlow`, `async_get_clientsession`
- All I/O is fully async via `asyncio` and HA's shared `aiohttp` session
- `iot_class: cloud_polling` -- polls a remote API, no local device communication

### Key Libraries
- `aiohttp` -- async HTTP client (used in `api.py`, session provided by HA)
- `voluptuous` -- schema validation for config flows and service input
- `homeassistant` -- HA core APIs (coordinator, entity, config flow, services)

### Build and Dev Tools
- `uv` -- Python package/environment manager (local dev)
- `ruff` -- linter and formatter (configured in `pyproject.toml`)
- `pytest` + `pytest-asyncio` -- test runner with `asyncio_mode = "auto"`

### CI/CD
- GitHub Actions with three workflows:
  - `validate.yml` -- runs on push to `main` and PRs: Ruff lint+format, Hassfest, HACS validation, pytest. A `gate` job aggregates results.
  - `release.yml` -- triggered after validate succeeds on `main`: reads version from `manifest.json`, extracts `CHANGELOG.md` section, builds `austria_public_transport.zip`, creates the GitHub Release with that archive attached.
  - `dependabot-auto-merge.yml` -- enables squash auto-merge on Dependabot PRs, so they land once `gate` passes. Uses the GitHub App token (`GH_ACTION_APP_CLIENT_ID` / `GH_ACTION_APP_PRIVATE_KEY`, in both the Actions and Dependabot secret stores) because a `GITHUB_TOKEN` merge triggers no workflows.
- Dependabot configured for weekly GitHub Actions (Thursdays) and `pip` (Mondays) (the ruff pin in `requirements_lint.txt`) updates. A Dependabot merge gets no version bump and produces no release: nothing it updates is in the release archive, and `manifest.json` declares no requirements. The update ships with the next real release.

### External APIs
- Wiener Linien OGD Realtime API (`https://www.wienerlinien.at/ogd_realtime/monitor`) -- read-only, public, no auth required.
- Wiener Linien `trafficInfoList` endpoint (`https://www.wienerlinien.at/ogd_realtime/trafficInfoList`) -- disruptions and elevator outages, used by the `wienerlinien_traffic_info` service.
- OeBB Scotty API (`https://fahrplan.oebb.at/bin/mgate.exe`) -- JSON POST API with embedded authentication (AID token). Used for station search, station boards, and trip planning. Not officially documented (reverse-engineered from webapp).

### Distribution
- HACS (Home Assistant Community Store) default store -- configured via `hacs.json`; listed since 2026-10-18 ([hacs/default#9256](https://github.com/hacs/default/pull/9256))
- No Docker, Kubernetes, or other infrastructure tooling

#### The release archive (`zip_release`)
`hacs.json` sets `zip_release: true` and `filename: "austria_public_transport.zip"`, so HACS downloads that one
release asset instead of fetching every file through the GitHub API. Two constraints bind how `release.yml`
builds it:

- **The integration's files must sit at the archive root.** HACS runs
  `zip_file.extractall(<config>/custom_components/austria_public_transport)`, so a top-level
  `austria_public_transport/` directory inside the zip would install as
  `custom_components/austria_public_transport/austria_public_transport/`. That is why the workflow `cd`s into
  the integration directory and zips `.`.
- **The asset name must equal `filename` exactly.** HACS requests that one name from the release and fails the
  download if it is absent. Renaming one without the other breaks every install.

The HACS validation action only checks that `filename` is set when `zip_release` is true -- it does **not**
verify the asset exists on a release, so a broken archive step fails silently at install time, never in CI.
The archive is therefore attached in the same `gh release create` call, so a release cannot be published
without it.

The motive is measurement as much as speed: GitHub reports a download count per release asset, which is the
only install signal this project has.

Releases before 1.0.5 carry no archive. Their tagged `hacs.json` has no `zip_release`, so HACS falls back to
the file-by-file download for them -- downgrades keep working.

## Dependencies
- Runtime: `homeassistant`, `aiohttp`, `voluptuous` (all provided by the HA environment)
- Dev: `ruff`, `pytest`, `pytest-asyncio`, `uv`
- External: Wiener Linien OGD Realtime API, OeBB Scotty API

## Design Decisions
- `manifest.json` is the single source of truth for versioning (CI reads it exclusively). `pyproject.toml` version exists but is not authoritative.
- Ruff replaces separate linter/formatter/isort tools with a single unified tool.
- `uv` chosen over pip/pipenv/poetry for local environment management.

## Known Risks
- Version in `pyproject.toml` is out of sync with `manifest.json` -- could cause confusion if `pyproject.toml` version is ever referenced.
- `uv.lock` exists locally but is untracked and not in `.gitignore` -- local environment reproducibility is not enforced for contributors or CI.

## Extension Guidelines
- Add new Python dependencies to `manifest.json` under `requirements` (HA convention), not `pyproject.toml`.
- New CI jobs should be added to `validate.yml` and included in the `gate` job's dependency list.
- Ruff rule sets can be extended in `pyproject.toml` under `[tool.ruff.lint]`.
