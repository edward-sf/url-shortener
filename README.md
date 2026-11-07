# url-shortener

[![CI](https://github.com/edward-sf/url-shortener/actions/workflows/ci.yml/badge.svg)](https://github.com/edward-sf/url-shortener/actions/workflows/ci.yml)

URL shortener built with FastAPI and hosted in Cloudflare Containers with Planetscale Postgres. Short links, click stats, link expiry, and a minimal Jinja2 + HTMX front end.

> **Status:** in development. The project skeleton, tooling and CI are in place;
> features are being built in the order listed in the
> [design spec](docs/specs/url-shortener-design-spec.md#12-suggested-build-order).

## v1.0.0 Dev Roadmap

- [x] :white_check_mark: P0: Project skeleton, settings, Docker Compose, CI (lint/type/test on an empty app).
- [ ] P1: Models, first Alembic migration, migration round-trip test, DB session and lifespan, `/health` running `SELECT 1`, transactional test fixture, `make migrate`.
- [ ] P2: Error envelope, then API keys: generation, hashing, `require_api_key` (header and cookie), `POST /api/keys`. Coverage gate in CI.
- [ ] P3: Links! Code generation, aliases, expiry, URL validation, create/list/get/delete, `make seed`.
- [ ] P4: Redirect, click recording, 404/410
- [ ] P5: Stats queries, `/stats` endpoint.
- [ ] P6: Rate limiting.
- [ ] P7: Web frontend (templates, HTMX, cookie flow, CSRF check, SVG chart).
- [ ] P8: Cleanup endpoint + Cron Trigger.
- [ ] P9: Production Dockerfile, CI image build, Cloudflare Containers + PlanetScale deployment, CD pipeline, smoke test
- [ ] P10: Go-live README edit, live URL, `curl` demo, publish to portfolio

## Architecture

```mermaid
flowchart TD
    client["Browser / curl / /docs"]

    subgraph cf["Cloudflare"]
        worker["Worker<br/>(router + daily Cron Trigger)"]
        subgraph container["Container: FastAPI app (uvicorn)"]
            direction TB
            subgraph routers["Routes: parse input, call one service, shape response"]
                api["api/<br/>JSON under /api"]
                web["web/<br/>GET /{code}"]
            end
            deps["deps/<br/>DB session, API key auth,<br/>same-origin check, rate limits"]
            services["services/<br/>all business logic"]
            repos["repos/<br/>all SQL queries"]
            models["models/<br/>SQLAlchemy ORM"]
            schemas["schemas/<br/>Pydantic I/O"]
            core["core/<br/>settings, errors, logging"]
        end
    end

    db[("PlanetScale Postgres")]
    ci["GitHub Actions<br/>alembic upgrade head"]

    client --> worker --> routes
    routes -. uses .-> deps
    routes -. validates with .-> schemas
    routes --> services
    services --> repos
    repos --> models
    repos --> db
    worker -. "cron: POST /internal/cleanup" .-> api
    ci -. migrations before deploy .-> db
```

### Layer rules
- **Routes** parse input, call one service, shape the response. No business logic, no queries.
- **Services** hold all logic and are unit-testable without HTTP.
- **Repos** are the only code that builds queries.
- **Schemas are not models.** Pydantic schemas (`LinkCreate`, `LinkOut`, `StatsOut`, ...) are never ORM models.

**Scheduled cleanup:** a Cloudflare Cron Trigger (daily) on the Worker calls `POST /internal/cleanup` with a shared secret header (`X-Cleanup-Secret`). The endpoint deletes links whose `exipres_at` is more than **30 days** in the past (clicks cascade). Request-time expiry checks keep behavior correct even if cleanup hasn't run.

**Redirect status:** **307 Temporary Redirect.** A 301 would be cached by browsers, so repeat clicks wouldn't be counted and expired links would keep working.

## Data model

**Completed in Task 2**

## Design decisions

- **API keys.** | Each link belongs to one key. No user accounts in v1.
- **Browser identity** | Key *issued automatically, on demand* (when the first link is created), stored in an HttpOnly cookie.
- **Event table** | Clicks are tracked in Postgres (`clicks`), inserted via FastAPI `BackgroundTasks`. Stores referrer *domain* and a coarse device category. No IP addresses stored.
- **Short codes** | Random 7-character base62, collision handled by unique constrain + retry. Optional custom aliases.
- **Code expiry** | 30-day default; creator may choose a duration, a date, or "never". Max 365 days. Enforced at request time (410); cleanup job deletes old expired links.
- **Frontend** | Jinja2 + HTMX, served by the same FastAPI app. Architecture separates stack concerns to make a later React frontend standup easier. The following rules make this later work simpler:
    1. HTML routes and API routes call the **same service layer**. No feature exists only in HTML.
    2. HTML routes live in their own router package (`web/`), separate from `api/`.
    3. A single auth dependency accepts the key from **either** `Authorization: Bearer` **or** the `sk` cookie.
- **Database** | PostgreSQL + SQLAlchemy 2.0 (async, asyncpg) + Alembic. Pydantic schemas and ORM models kept separate.
- **Hosting** | Cloudflare Containers (Workers Paid, ~$5/mo) for the app.
- **Database host** | PlanetScale Postgres, single node (~$5/mo), created and billed through Cloudflare. Connected directly from the container (no Hyperdrive).

## Known limits

TBD

## Running locally

### Requirements

- [uv](https://docs.astral.sh/uv/) (installs Python 3.12 for you)
- [Docker](https://docs.docker.com/get-docker/) or [OrbStack](https://orbstack.dev/)
- GNU Make

### Getting started
```
cp .env.example .env
uv sync
uv run pre-commit install
make dev
```

Then open http://localhost:8000/health or http://localhost:8000/docs.

### Development

| Command | What it does |
| ------- | ------------ |
| `make dev` | Start Postgres + the app with live reload |
| `make down` | Stop containers (keeps the database volume) |
| `make check` | Lint, type-check and test (same as CI) |
| `make format` | Auto-fix lint issues and format code |

Run `make` to list every command.

### Project layout
```
src/url_shortener/
    api/        JSON routers under /api
    web/        HTML routes (Jinja2 + HTMX)
    deps/       FastAPI dependencies (DB session, auth, rate limits)
    services/   business logic
    repos/      database queries
    models/     SQLAlchemy ORM models
    schemas/    Pydantic request/response models
    core/       settings, errors, logging
```

See the [design spec](docs/specs/url-shortener-design-spec.md) for the full architecture and the reasons behind it.

## Feature Roadmap

1. **User Accounts & Auth:** To expand beyond browser-bound API keys and allow persistent, cross-device management of one's URLs, we need to build features for secure, authenticated user accounts. Hand-rolling auth will be the primary set of skills demonstrated in this feature.

2. **React frontend:** We've built our current frontend as a quick-and-easy option to UI. We've also built it in a way that prepares for replacement with a more industry-standard frontend framework. It doesn't need to be React necessarily, but that would be an obvious choice.

## License

[MIT](LICENSE)

## Contributors

| Contributor | GitHub | Portfolio |
| ----------- | ------ | --------- |
| Edward Simpson-Fitzgibbon | [edward-sf](https://github.com/edward-sf) | [edward-sf.dev](https://edward-sf.dev)
