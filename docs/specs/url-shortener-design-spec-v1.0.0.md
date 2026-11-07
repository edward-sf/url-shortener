# URL Shortener Service — Design Spec v1.0.0

**Date:** 2026-11-05

**Portfolio:** Python Starter Portfolio

**Version:** 1.0.0

---

## 1. Purpose and success criteria

**Goal:** A FastAPI URL shortener that creates short links, redirects them, counts clicks and expires old links, with a minimal front end. It's a portfolio piece aimed at **backend/Python developer roles**, kept separate from platform/DevOps work.

**What it must demonstrate:** FastAPI, relational database design, input validation, and a real deployment.

**Success looks like:**
- A live public URL that a reviewer can use from a browser, from `curl`, and from `/docs`.
- A clean, layered codebase that a reviewer can follow in minutes.
- A test suite running in CI with enforced coverage on business logic.
- A README that explains the design decisions and known limits, written for the interview conversation.

**Explicitly out of scope for v1:** user accounts, QR codes, editing links, bulk import, custom domains, malware/phishing URL scanning (documented as a known gap).

**Planned later releases:** (1) hand-rolled user accounts (argon2 passwords + JWT) on top of API keys; (2) optionally a React client using the same JSON API.

---

## 2. Key decisions

| Area | Decision |
|---|---|
| Ownership | **API keys.** Each link belongs to one key. No user accounts in v1. |
| Browser identity | Key **issued automatically, on demand** (when the first link is created), stored in an HttpOnly cookie. |
| Click tracking | **Event table** (`clicks`), inserted via FastAPI `BackgroundTasks`. Stores referrer *domain* and a coarse device category. **No IP addresses stored.** |
| Short codes | **Random 7-character base62**, collision handled by unique constraint + retry. Optional **custom aliases**. |
| Expiry | **30-day default**; creator may choose a duration, a date, or "never". Max 365 days. Enforced at request time (410); cleanup job deletes old expired links. |
| Front end | **Jinja2 + HTMX**, served by the same FastAPI app. No hand-written JS except copy-to-clipboard. |
| Database | **PostgreSQL + SQLAlchemy 2.0 (async, asyncpg) + Alembic.** Pydantic schemas and ORM models kept separate. |
| Hosting | **Cloudflare Containers** (Workers Paid, ~$5/mo) for the app. |
| Database host | **PlanetScale Postgres, single node** (~$5/mo), created and billed through Cloudflare. Connected directly from the container (no Hyperdrive). |
| Total cost | ~$10/month, one vendor invoice. |

### Rules that keep a future React client cheap
1. HTML routes and API routes call the **same service layer**. No feature exists only in HTML.
2. HTML routes live in their own router package (`web/`), separate from `api/`.
3. A single auth dependency accepts the key from **either** `Authorization: Bearer` **or** the `sk` cookie.

---

## 3. Architecture

```
Browser / curl / /docs
        │
Cloudflare Worker (thin router required by Containers; also hosts the Cron Trigger)
        │
Container: FastAPI app (uvicorn)
 ├── api/        JSON routes under /api
 ├── web/        HTML routes (Jinja2 + HTMX)
 ├── redirect    GET /{code}
 ├── deps/       get_db_session, require_api_key, require_same_origin, rate limits
 ├── services/   links, keys, clicks, codes, stats — all business logic
 ├── repos/      all SQLAlchemy queries, one module per table
 ├── models/     SQLAlchemy ORM models
 ├── schemas/    Pydantic request/response models
 └── core/       settings (pydantic-settings), errors, logging
        │
PlanetScale Postgres   ← Alembic migrations run from CI before deploy
```

**Layer rules:**
- **Routes** parse input, call one service, shape the response. No business logic, no queries.
- **Services** hold all logic and are unit-testable without HTTP.
- **Repos** are the only code that builds queries.
- **Schemas ≠ models.** Pydantic schemas (`LinkCreate`, `LinkOut`, `StatsOut`, …) are never ORM models.

**Scheduled cleanup:** a Cloudflare Cron Trigger (daily) on the Worker calls `POST /internal/cleanup` with a shared secret header (`X-Cleanup-Secret`). The endpoint deletes links whose `expires_at` is more than **30 days** in the past (clicks cascade). Request-time expiry checks keep behavior correct even if cleanup hasn't run.

**Redirect status:** **307 Temporary Redirect.** A 301 would be cached by browsers, so repeat clicks wouldn't be counted and expired links would keep working.

---

## 4. Data model

All timestamps are `timestamptz` in UTC. Primary keys are `bigint` identity columns.

### `api_keys`
| Column | Type | Notes |
|---|---|---|
| id | bigint PK | |
| prefix | varchar(16), unique, not null | e.g. `sk_3fA9xQ2m` (`sk_` + 8 base62 chars). Used for lookup and display. |
| key_hash | char(64), not null | SHA-256 hex of the full key. Raw key never stored. |
| created_at | timestamptz, not null, default now() | |
| last_used_at | timestamptz, null | Updated at most once per minute per key. |
| revoked_at | timestamptz, null | Revoked keys fail auth. |

**Key format:** `sk_` + 8-char public part + `_` + 32-char random base62 secret (generated with `secrets`). Lookup by prefix, then constant-time compare (`hmac.compare_digest`) of SHA-256 hashes.

**Why SHA-256, not argon2:** keys have ≥190 bits of entropy, so a fast hash is safe. Slow hashes are for low-entropy passwords (used in the later accounts release).

### `links`
| Column | Type | Notes |
|---|---|---|
| id | bigint PK | |
| code | varchar(32), unique, not null | Random code or custom alias. |
| is_custom | boolean, not null, default false | |
| target_url | text, not null | ≤ 2,048 chars, enforced in validation. |
| api_key_id | bigint FK → api_keys(id) ON DELETE CASCADE, not null | |
| created_at | timestamptz, not null, default now() | |
| expires_at | timestamptz, null | Null = never expires. |

**Indexes:**
- unique `(code)` — hot path for redirects.
- `(api_key_id, created_at DESC, id DESC)` — "My links" listing and cursor pagination.
- partial `(expires_at) WHERE expires_at IS NOT NULL` — cleanup job.

### `clicks`
| Column | Type | Notes |
|---|---|---|
| id | bigint PK | |
| link_id | bigint FK → links(id) ON DELETE CASCADE, not null | |
| clicked_at | timestamptz, not null, default now() | |
| referrer_domain | varchar(255), null | Host only, lowercased; never full referrer URL. |
| device_category | varchar(16), not null | CHECK in (`desktop`, `mobile`, `tablet`, `bot`, `other`). |

**Index:** `(link_id, clicked_at)`.

**Deliberately omitted:** no denormalized `click_count` (`COUNT(*)` over the index is fast at this scale; rollups are the documented scaling path); no soft deletes.

**Device category:** a small in-house User-Agent heuristic in `services/clicks.py` (bot keywords → `bot`; tablet markers → `tablet`; mobile markers → `mobile`; known desktop OS → `desktop`; else `other`). No third-party UA library.

---

## 5. Short codes and aliases

**Random codes:** 7 characters from `[0-9A-Za-z]` via `secrets.choice` (~3.5 trillion combinations). Insert; on unique-violation (`IntegrityError` on `links.code`), regenerate and retry up to **5** times, then raise a 500-class `code_generation_failed` error. Codes are case-sensitive.

**Custom aliases:**
- Lowercased, then must match `^[a-z0-9-]{3,32}$`, must not start or end with `-`.
- Reserved (rejected): `api`, `docs`, `redoc`, `openapi.json`, `links`, `key`, `static`, `internal`, `health`, `favicon.ico`, `robots.txt`.
- Already taken → **409** `alias_taken`.

---

## 6. API

All JSON routes live under `/api`. FastAPI's `/docs` is enabled in production with a Bearer auth scheme so reviewers can click **Authorize** and paste a key.

| Method & path | Auth | Purpose | Success |
|---|---|---|---|
| `POST /api/keys` | none (rate-limited per IP) | Issue a key. Full key returned **once**. | 201 `{key, prefix, created_at}` |
| `POST /api/links` | key | Create link. | 201 + `Location` header, `LinkOut` |
| `GET /api/links?cursor=&limit=` | key | Caller's links, newest first. `limit` default 20, max 100. Opaque cursor encodes `(created_at, id)`. | 200 `{items, next_cursor}` |
| `GET /api/links/{code}` | key, owner | Link details. | 200 `LinkOut` |
| `GET /api/links/{code}/stats` | key, owner | Totals, per-day series, top referrers, device split. | 200 `StatsOut` |
| `DELETE /api/links/{code}` | key, owner | Delete link and its clicks. | 204 |
| `GET /{code}` | none | Redirect. | 307 |
| `GET /health` | none | Liveness + `SELECT 1`. | 200 `{status: "ok"}` |
| `POST /internal/cleanup` | `X-Cleanup-Secret` | Delete old expired links. | 200 `{deleted: n}` |

**Ownership:** a link owned by another key returns **404**, never 403, so nobody can discover which codes exist.

**`LinkOut`:** `code`, `short_url`, `target_url`, `is_custom`, `created_at`, `expires_at`, `is_expired`, `click_count` (computed by query for detail/list views).

**`StatsOut`:** `total_clicks`, `daily` (30 entries, last 30 UTC days including today, zero-filled), `top_referrers` (top 5 `{domain, count}`, `null` domain shown as "direct"), `devices` (`{category: count}`).

### Validation (`LinkCreate`)
- `url` (required): scheme `http` or `https`; has a host; ≤ 2,048 chars. Rejected: other schemes (`javascript:`, `data:`, `ftp:` …), a host equal to our own `BASE_URL` host (prevents loops), and literal private/loopback/link-local IPs (`ipaddress` module). Hostnames are **not** DNS-resolved.
- `alias` (optional): rules in §5.
- Expiry, **at most one** of:
  - `expires_in_days`: int 1–365
  - `expires_at`: datetime, must be timezone-aware, in the future, ≤ 365 days from now
  - `never_expires: true`
  - none given → now + 30 days
  - more than one given → 422 `conflicting_expiry` (model validator)

### Error envelope
Every error, including FastAPI's validation errors, uses one shape:
```json
{"error": {"code": "alias_taken", "message": "That alias is already in use.", "field": "alias"}}
```
`field` is omitted when not applicable. Validation errors (422) include a `details` list of `{field, message}` objects.

| Status | Codes |
|---|---|
| 400 | `invalid_cursor` |
| 401 | `missing_api_key`, `invalid_api_key` |
| 403 | `cross_origin_rejected` (web only), `invalid_cleanup_secret` |
| 404 | `link_not_found` |
| 409 | `alias_taken` |
| 410 | `link_expired` |
| 422 | `validation_error`, `conflicting_expiry` |
| 429 | `rate_limited` (+ `Retry-After` header) |

### Rate limiting
In-process limiter (`slowapi`), suitable for a single container:
- `POST /api/keys` and lazy web key issuance: **5 per hour per client IP**.
- `POST /api/links` (API and web): **60 per hour per key**.
- Client IP taken from the `CF-Connecting-IP` header (the container is only reachable through the Cloudflare Worker); falls back to the socket address locally.
- README notes: multiple instances would need a shared store (Redis).

### Redirect flow (`GET /{code}`)
1. Look up `code` (exact match).
2. Not found → 404 (HTML page if `Accept` includes `text/html`, else JSON envelope).
3. `expires_at` ≤ now → 410 (same content negotiation).
4. Otherwise schedule a click insert via `BackgroundTasks` (referrer domain + device category) and return **307** with `Location: target_url` and `Cache-Control: no-store`.
5. A failed click insert is logged and dropped. It never affects the redirect.

---

## 7. Web front end (Jinja2 + HTMX)

| Path | Content |
|---|---|
| `/` | Create form: URL, optional alias, expiry select (7 / 30 (default) / 90 / 365 days / never). HTMX `hx-post` to `/` swaps in a result card with the short URL and a copy button, or inline field errors. |
| `/links` | "My links" table: code, target (truncated), clicks, expiry, delete button (`hx-delete`, removes row). Empty state if no key or no links. "Load more" via cursor. |
| `/links/{code}` | Stats: total, 30-day bar chart rendered **server-side as SVG**, top referrers, device split. 404 if not owner. |
| `/key` | Key prefix, "reveal & copy full key" (read from the cookie), and a "use a different key" form. |
| 404 / 410 pages | Friendly not-found and expired pages with a link home. |

**Cookie key handling:**
- Key is issued **lazily** on the first link creation from the browser (not on first visit), so crawlers don't mint keys.
- Cookie `sk`: `HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=31536000`. `Secure` is disabled only when `ENV=local`.
- "Use a different key" validates the pasted key before replacing the cookie. This is how a user regains access on another device.
- The server only ever stores the hash. `/key` shows the full key because the browser's own cookie supplies it.

**CSRF:** every state-changing web request (POST, DELETE) must pass `require_same_origin`, which checks the `Origin` header (falling back to `Referer`) against `BASE_URL`. Otherwise 403 `cross_origin_rejected`. `/api` routes with Bearer auth skip this check. Requests that authenticate to `/api` **via cookie** also go through the check, so a future same-origin React client is protected.

**Assets:** htmx from a pinned CDN URL with SRI hash; one hand-written stylesheet (responsive, WCAG AA contrast, visible focus states). The only JavaScript is the clipboard `onclick` handler.

---

## 8. Configuration

Loaded with `pydantic-settings` from environment variables. Production values are Cloudflare secrets/vars.

| Variable | Purpose | Default |
|---|---|---|
| `ENV` | `local`, `test`, `production` | `local` |
| `DATABASE_URL` | `postgresql+asyncpg://…` (TLS required in production) | — |
| `BASE_URL` | Public origin, e.g. `https://example.com` | `http://localhost:8000` |
| `CLEANUP_SECRET` | Shared secret for `/internal/cleanup` | — |
| `DEFAULT_EXPIRY_DAYS` | Default link lifetime | 30 |
| `MAX_EXPIRY_DAYS` | Upper bound | 365 |
| `CLEANUP_GRACE_DAYS` | Days past expiry before deletion | 30 |
| `RATE_KEYS_PER_HOUR` | Per-IP key issuance | 5 |
| `RATE_LINKS_PER_HOUR` | Per-key link creation | 60 |

---

## 9. Testing

**Stack:** pytest, pytest-asyncio, httpx `AsyncClient` with ASGI transport, real Postgres (Docker locally, service container in CI). Each test runs in a transaction that is rolled back.

**Unit (services):**
- Code generation; collision retry with a forced-collision fake; retry exhaustion.
- Alias normalization, pattern, reserved words.
- Expiry resolution: each valid option, default, conflicting combinations, past dates, over-max.
- URL validation: allowed/blocked schemes, own-host rejection, private/loopback IPs, length.
- Referrer-domain extraction and device classification.
- Key generation, hashing, verification, revoked keys.

**Integration (repos + DB):**
- Owner scoping (another key's link → not found).
- Cascades: delete link removes clicks; delete key removes links.
- Stats: per-day buckets are correct and zero-filled across UTC day boundaries; top referrers ordering.
- Cleanup deletes only links past the grace period.
- Cursor pagination is stable and complete.

**End-to-end HTTP:**
- Create → redirect (307, `Cache-Control: no-store`) → click recorded → stats reflect it.
- Expired → 410; unknown → 404; HTML vs JSON negotiation.
- Error envelope shape for 401/404/409/410/422/429.
- Rate limits return 429 with `Retry-After`.
- Web: lazy key issuance sets the cookie; cookie attributes; "use a different key"; cross-origin POST/DELETE rejected.
- `/internal/cleanup` rejects missing/wrong secret.

**Migrations:** `alembic upgrade head` → `downgrade base` → `upgrade head` on an empty database.

**Coverage:** ≥ 90% line coverage on `services/` and `repos/`, enforced in CI.

**Development approach:** test-driven. Write the failing test first for each unit of behavior.

---

## 10. Tooling, CI/CD and deployment

**Tooling:** Python 3.12; `uv` (dependencies + lockfile); `ruff` (lint + format); `mypy --strict` on `services/`, `repos/`, `schemas/`, `core/`; `pre-commit`.

**Local development:** `docker compose up` (Postgres + app with reload). Task runner (`Makefile` or `uv run` scripts): `migrate`, `test`, `lint`, `typecheck`, `seed`, `dev`.

**CI (GitHub Actions, every PR):** ruff → mypy → pytest with Postgres service container + coverage gate → Docker image build.

**CD (merge to `main`):**
1. Build image.
2. `alembic upgrade head` against PlanetScale (`DATABASE_URL` in GitHub secrets).
3. `wrangler deploy` — pushes the container image and deploys the Worker + daily Cron Trigger. Follow the current Cloudflare Containers documentation for the Worker/container wiring at implementation time.
4. Smoke test: `GET /health`, then create a link with a CI-only key and follow its redirect.

**Migration policy:** additive and backward-compatible, so the previous container keeps working during rollout. Destructive changes take two deploys (expand → contract).

**Container image:** multi-stage, slim Python base, non-root user, `uvicorn` with a single worker (matches the in-process rate limiter), port from env.

**Database:** PlanetScale Postgres single node, created from the Cloudflare dashboard (Storage & databases → Postgres & MySQL). SQLAlchemy async engine with a small pool (e.g. `pool_size=5`, `pool_pre_ping=True`), TLS required.
