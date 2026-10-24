# Roamate implementation plan

**Version:** 3.0 (revised after review 1, awaiting hooman's approval in step M0.18) · 24 October 2026
**Previous version:** 2.4, approved 24 October 2026. What changed and why: [review-response.md](review-response.md).
**Builds on:** the [product brief](../background/product-brief.md) (18 Oct 2026), [pre-build decisions](../background/pre-build-decisions.md) and [solver, search and evaluation notes](../background/solver-retrieval-evaluation.md) (20 Oct 2026), [formulation, hotels, fares and TravelPlanner](../background/formulation-hotels-fares-travelplanner.md) (24 Oct 2026), hooman's 11 changes and follow-ups of 24 Oct 2026, and review 1 (24 Oct 2026).
**Companion files:** [implementation-steps.md](implementation-steps.md) (every step as a checklist) and [roadmap.html](roadmap.html) (the visual roadmap, generated from this plan and the step list; open it in a browser).

---

## 0. How to read this plan

When two documents disagree, the higher one in this list wins:

| # | Source | What it governs | Status shown by |
| --- | --- | --- | --- |
| 1 | hooman's latest written decision, recorded in this plan or in `docs/adr/` | Anything it covers | The plan's version line or the ADR's date |
| 2 | This plan, latest approved version | Scope, order, limits, release gates and the rules that cut across components | The **Version** line above |
| 3 | Designs in `docs/design/` | The exact contract of one component (tables, fields, endpoints, settings) | The status block at the top of each file: `draft`, `approved` or `superseded` |
| 4 | [implementation-steps.md](implementation-steps.md) | What is done. A ticked step records its commit and the test it passed | The checkbox and its record |
| 5 | [roadmap.html](roadmap.html) | Nothing of its own: it is generated from 2 and 4 by `scripts/build_roadmap.py` and never edited by hand | `python scripts/build_roadmap.py --check` (run in CI) |
| 6 | `docs/background/` | Nothing: history and reasoning only. `solver_example.py` is an illustration with known issues listed in its header | A "historical" note at the top of each file |

A design marked `draft` is not a contract yet. A change found during coding goes back to the affected design (or ADR) and is approved before the code follows it.

---

## 1. What we are building first

The first version is a **web app** with real user accounts. A signed-in user can:

1. Enter a trip, either through a form or by describing it in free text: city, dates and arrival and departure times, travelers and rooms, budget and what it covers, interests, pace, must-do places, walking limit, hotel (booked, or preferences).
2. Get up to three checked options (**Budget**, **Balanced**, **Comfort**), each solved independently under the same hard limits and verified by an independent validator. If fewer than three useful, different options exist, the app shows fewer and says why.
3. Explore the chosen option in four linked views: **Story**, **Timeline**, **Map**, **Budget**.
4. Ask for one kind of change ("less walking on day 2", "keep this museum", "slower afternoon"), see what changed, and approve a version.
5. Sign out, sign back in, and find the saved trip with its version history, unchanged even if the city's data was updated since.

An **admin** user also gets:

- **Cities**: add a new city, watch the automatic data collection, review the places and hotels it found, and publish the city.
- **Lab**: try each part of the system on its own (models, search, solver, validator, AI intake, graph runs, evaluations).

The **mobile app** comes after the web app works and has been tested. All trip logic lives in the backend, so the mobile app is a second client of the same API.

### 1a. What the first version supports

These limits keep the problem small enough to solve and check reliably. Each is a setting, confirmed by hooman in M0.18. A request outside them gets a clear `unsupported_request` message that says which limit it hit.

| Limit | First version |
| --- | --- |
| Cities per trip | 1 (a published city) |
| Hotel | One hotel for the whole stay: booked by the traveler, or chosen from a shortlist of at most 5 |
| Trip length | 1–7 days; the first and last day can be partial (arrival and departure times) |
| Travelers | 1–8. Rooms: given by the traveler, or `ceil(travelers / 2)`. Taxis per ride: `ceil(travelers / 4)` |
| Candidates sent to the solver | At most 60, including must-dos; at most 10 must-dos |
| Options returned | 0–3, with an honest note when fewer than three |
| Currency | The city's currency only |
| Travel modes | Walking and driving (routed), metro (estimated from distance, labeled), taxi (tariff-based) |
| Per planning job | Deadline about 120 s, at most 30 model calls, at most 10 s per solve, at most 4 solver processes at once |

The second city (M6) proves that adding a city needs no code, not that every city in the world works.

### 1b. Releases

| Release | When | What it includes | Gate before it is called done |
| --- | --- | --- | --- |
| **Designs approved** | End of M0 | Every design approved, server facts recorded, two spikes passed | All designs marked `approved`; the compatibility manifest is filled in |
| **Engineering tracer** | End of M3 | A labeled fixture trip goes from a signed-in request through the database to the screen. No AI or live data yet | Clean migrations, job-runner recovery and concurrency tests pass |
| **Web Alpha** (`v0.1-alpha`) | End of M10 | Real city data, form and free-text intake with confirmation, up to three checked options, the four linked views, save and reopen, honest partial and error states. No revision yet | The Alpha flow works in a browser; every time and cost on screen passed the validator |
| **Web Beta** | End of M12 | Alpha plus revision, locks, diffs, approval, booking links, a secure deployment, a rehearsed restore, accessibility and a few real testers | The full success test below passes on the deployed app; no open critical correctness or isolation issue |
| **Mobile testers** | End of M14 | The same backend, secure mobile sign-in, offline reading per account, local maps, internal builds | Real-device test with no cross-account leaks. Store publication is a separate decision |

### Success test for the web version (Web Beta)

The brief's demo scenario, run in a browser on the deployed app: a user signs in, enters a 3-day trip for two with a ground budget, receives checked options with real images, explores the map and costs, asks for less walking on day 2, approves the revision, signs out, signs in again and reopens it. Every number on screen comes from the solver or the budget calculator, and the validator reports zero violations. An admin can add a second city through the Cities screen without writing code.

---

## 2. What changed

### In version 2 (hooman's changes)

| # | Change requested | Where it shows up in this plan |
| --- | --- | --- |
| 1 | PostgreSQL for relational data, Qdrant for vectors, MinIO for objects | §4 infrastructure, §7 data design. pgvector is not used |
| 2 | LangGraph from the start | §10. The planning workflow is a LangGraph graph from its first version (M9) |
| 3 | Ready database images, as in RagBot | §4. Roamate connects to the services already running for RagBot, with its own database, collections and buckets |
| 4 | Every step approved before implementation | §13. M0 is a full design phase; nothing is coded until its design is approved, and each step gets a go-ahead |
| 5 | Users and login from the start | M2. Email and password accounts with user and admin roles |
| 6 | Free-tier API keys or local vLLM, with fallback | §8. One model gateway; free-tier API models first, local vLLM last, order set in one line; embeddings via TEI |
| 7 | A stage to collect cities and places, with easy semi-automatic ingestion | §9, M5 and M6. A staged city pipeline with a review queue and an auto-approve mode |
| 8 | Conda environment named `roamate` | §5. `environment.yml` |
| 9 | Embedding model to be chosen | §8. A measured comparison of candidate models in M8 |
| 10 | All frontend files local, no internet needed for them | §11. Bundled packages and fonts, local map tiles, images served from our own storage, and a network-request check |
| 11 | Work on `main` for the early phases | §13. Direct commits to `main` until Web Alpha, then branches and pull requests |
| 12 | Hotels, taxi fares, local routing with rush-hour factors, and the TravelPlanner research track (24 Oct 2026) | §4, §7, §9, §10, Research track R1–R3 |

### In version 3 (review 1)

The architecture and the order of milestones stay. Version 3 adds the contracts the review found missing and removes claims we could not back. The main changes:

- **Limits and releases** (§1a, §1b): a stated support envelope, and four release gates with the full success test at Beta, not Alpha.
- **Jobs** (§10): a Postgres job table with leases and one small worker process, instead of background tasks inside the API. Solves run in a supervised child process.
- **Snapshots** (§7, §9): a city is published as a versioned snapshot across all stores and switched on at the end. Trip versions are frozen with the snapshot they used. Approval and selection live in their own table.
- **Solver honesty** (§10): input checks before OR-Tools, distinct solver statuses, independent option solves instead of a forced "differ by two places" rule, transport policies instead of an unproven per-leg mode choice, lunch placed inside full days, money in integer minor units, nights from dates.
- **Shared services** (§4): Roamate never stops or reconfigures a RagBot service, uses two Postgres roles, four buckets, its own Compose names, and a separate TEI container for embedding experiments.
- **Security and operations** (§5, §13, M12): Argon2id, hashed session tokens, Origin checks, ownership on every resource, redacted logs from M1, TLS, backups and a restore rehearsal before Beta.
- **Research gate** (R1): the TravelPlanner rules are checked before our method is used on test queries or submitted.

The full table of findings and answers is in [review-response.md](review-response.md).

---

## 3. Keeping it simple

We start with the smallest version of each piece and add a heavier tool only when a real need appears.

| Area | Start with | Add later, only when needed |
| --- | --- | --- |
| Background work | A `job` table in Postgres and one worker process (`python -m app.worker`) that claims jobs; solves run in a child process | More worker processes, or Redis + Celery, if M12 measurements show the worker cannot keep up |
| Live progress | Polling `GET /api/jobs/{id}/events?after=<seq>` every second | Server-Sent Events, if polling feels laggy |
| Geography | Distances computed in Python (haversine × detour factor) as the labeled fallback | PostGIS, if spatial queries get slow |
| Travel times | Walking and driving times from our own Valhalla service built from each city's OpenStreetMap data; metro estimated from distance and labeled; driving times multiplied by per-city rush-hour factors | Public transport times from timetables (GTFS); historical street speeds; a live traffic check for same-day taxis |
| Transport choice | Up to three fixed transport policies per option (e.g. walk + metro, walk + taxi, walk only), each solved and checked; the best valid one is kept | Joint per-leg mode choice (CP-SAT or an expanded graph), only if policies leave real value on the table |
| Itinerary storage | The whole frozen itinerary as JSON inside a trip version row | Normalized tables, only if we need to query inside itineraries |
| LLM access | Our own small gateway over OpenAI-compatible endpoints | A routing library, only if our gateway stops being enough |
| Travel profile | Defaults stored on the user | A separate profile model with history |

Code rules that keep the system understandable:

- **LLMs propose structured data; code checks it; only code writes trip state.** Every LLM output is a Pydantic model, followed by a check of its meaning against the brief.
- **Every number the user sees comes from the solver or the budget calculator,** never from model text.
- **Every solver input is checked before OR-Tools sees it,** and every solver output is checked by the independent validator before anyone sees it.
- **Trip versions are frozen.** A revision creates a new version on top of an expected base version. Refreshing a city never changes a saved trip.
- **Real media first.** Every image carries its kind (exact venue, area, generic city, AI decorative), license and author.
- **Never present estimated data as checked.** Every fact shows its source and age; unknown stays `Unknown`; LLM-estimated fields are labeled as estimates.
- **The user's hard limits are never relaxed without the user agreeing,** whether by a scenario profile, a repair, a fallback model or a change request.

---

## 4. Infrastructure

Roamate reuses the services that already run on the server for RagBot. It shares no data with RagBot: it gets its own database, collections and buckets. The exact contract, including the real versions found on the server, is the [M0.2 design](../design/02-infrastructure-and-environment.md) and the [compatibility manifest](../design/00-compatibility-manifest.md).

| Service | Existing container | Roamate uses |
| --- | --- | --- |
| PostgreSQL | `postgres-server` | Database `roamate`; role `roamate_owner` owns the schema and runs migrations; role `roamate_app` reads and writes data only |
| Qdrant | `qdrant-server` (`qdrant/qdrant:v1.16.2`) | Collections prefixed `roamate_`, reached through the alias `roamate_places` |
| Object storage | `minio-server` | Four buckets: `roamate-media`, `roamate-tiles`, `roamate-routing`, `roamate-raw`, with an access key limited to them |
| TEI embedding | `tei-embedding` (currently `jina-embeddings-v5-text-small-retrieval`) | Dense embeddings for places, read-only use |
| TEI reranker | `tei-reranker` (currently `bge-reranker-v2-m3`) | Re-ranking search candidates, read-only use |
| vLLM | `gemma4-vllm` (`vllm/vllm-openai`) | Local chat model, the last fallback in the chain, read-only use |
| Routing | new, Roamate's own: `roamate-routing` (Valhalla, port 8002) | Walking and driving times and distances, built from each city's OpenStreetMap extract; works offline |
| Embedding lab | new, Roamate's own, started only when needed: `roamate-tei-lab` (port 7999) | Trying candidate embedding models without touching RagBot's TEI |

### Rules for shared services

1. **Roamate never stops, restarts or reconfigures a RagBot service.** Failure tests use a fake provider or a deliberately wrong Roamate address, never a shutdown.
2. **Caps on shared endpoints:** at most 2 parallel requests to vLLM and 4 to each TEI service from Roamate (settings), with timeouts.
3. **Setup scripts** run as a dry run by default, print exactly what they will create, and refuse any name without the Roamate prefix. Admin logins are typed in when a script runs and never stored in `.env`.
4. **Compose** uses its own project name `roamate`, container names starting with `roamate-`, its own volumes and ports bound to `127.0.0.1`. Profile `shared` starts only Roamate's own services (routing, and the lab TEI on request). Profile `standalone` starts everything for a fresh machine that has no RagBot services.
5. **Isolation we can honestly claim during development:** `roamate_app` has no rights on any RagBot object (proven by tests). PostgreSQL lets any role connect to any database by default; revoking that for other databases is optional and only done by the server owner. Qdrant separation is by name only, since collection-scoped keys need a server config change. Both are accepted development boundaries. Before Beta (M12.9): collection-scoped Qdrant keys if the server owner enables them, or a dedicated Roamate Qdrant.

### Object storage: MinIO, easy to replace

MinIO stopped publishing community Docker images and binaries in October 2025 and archived its open-source repository in 2026, so it no longer gets updates. The image already running on the server keeps working, and Roamate only needs simple features (put, get, list, delete, range reads), so we start with it. Roamate's storage code talks plain S3 through `boto3`, so moving to another S3-compatible server is mostly a change of endpoint and keys, followed by copying the buckets and running our storage tests against the new server.

| Option | License | Fit for Roamate |
| --- | --- | --- |
| **SeaweedFS** | Apache 2.0 | Mature, actively released, runs on one machine (`weed server -s3`), good with many small files such as images and thumbnails. **Recommended if we switch.** |
| **RustFS** | Apache 2.0 | Closest to MinIO in feel and setup, single-node friendly, but young; fine for development, watch it before production |
| **Garage** | AGPL v3 | Light and simple, designed for several small servers; lacks bucket policies and versioning (we don't need them) |
| **Ceph RGW** | LGPL | Very complete, but heavy to run; only worth it if you already run Ceph |

**Decision (24 Oct 2026): stay with MinIO for now.** It is an accepted risk, reviewed again before Beta (M12.9). SeaweedFS is the first replacement to try, and a switch requires the storage test suite to pass against it.

---

## 5. Technology choices

| Layer | Choice | Why |
| --- | --- | --- |
| Environment | **Conda** env `roamate` from `environment.yml` (Python 3.12, Node.js 22); Python packages in `backend/pyproject.toml`, locked with pip-tools in `backend/requirements.lock`; web packages locked in `web/package-lock.json` | One command to create the environment, and the same versions everywhere |
| API | **FastAPI** + Pydantic v2 | Typed models and automatic OpenAPI docs |
| Relational data | **PostgreSQL** via **SQLAlchemy 2** + **Alembic** migrations | Users, cities, places, trips, jobs, logs |
| Background work | A Postgres `job` table and one worker process from the same codebase | Durable, restartable, no extra broker |
| Vector search | **Qdrant** with dense vectors (TEI) and sparse BM25 vectors, fused with Qdrant's query API | Hybrid semantic and keyword search in one query |
| Object storage | **MinIO** (decided), accessed through **boto3** so any S3-compatible server can replace it | Place images, map tiles, routing archives, raw ingestion data |
| Workflow | **LangGraph** with the Postgres checkpointer, run by the worker | Readable graph of steps, pauses for the user, resume after restart |
| LLM | Our **model gateway** over OpenAI-compatible APIs (OpenRouter, Gemini free tier, local vLLM; 9Router opt-in) using the `openai` Python SDK | One interface, fallback order set in one line, every call logged and budgeted |
| Embeddings and reranking | **TEI** `/embed` and `/rerank` | Already running; local and fast |
| Solver | **OR-Tools** routing solver (port of `solver_example.py`, with the fixes in §10), in a child process | Already prototyped; a native crash cannot take down the worker |
| Routing | **Valhalla** (MIT), provisional until the M0.16 spike | One service for every city and for both walking and driving |
| Auth | Email + password, **Argon2id** hashes, opaque session tokens stored hashed in Postgres; httpOnly cookie for the web, bearer token for mobile | Simple, secure, no third-party service |
| Weather | **Open-Meteo**, cached | Free for development; launch needs a commercial plan or self-hosting (M0.17) |
| Place data | **OpenStreetMap** (Overpass; Nominatim only for the city lookup), **Wikidata**, **Wikipedia**, **Wikimedia Commons** | Open data we may store, with clear licenses |
| Web frontend | **React + TypeScript + Vite**, **React Router**, **TanStack Query**, **Tailwind CSS** | Plain single-page app; everything bundled locally |
| Web map | **MapLibre GL JS** with a local **PMTiles** file per city | Works without an internet tile server |
| Fonts and icons | `@fontsource` packages and `lucide-react`, bundled | No font or icon CDN |
| API types in the web app | **openapi-typescript** generates `web/src/api/schema.ts`; CI fails if it is stale | Frontend always matches backend |
| Tests | **pytest** + **Hypothesis**, **Vitest** + Testing Library, **Playwright** | One tool per job |
| Code quality | **ruff**, **mypy** (not strict at first), **ESLint** + **Prettier** + `tsc --noEmit`, **gitleaks**, **pre-commit** | Fast, standard, catches type errors and leaked secrets |
| CI | **GitHub Actions** with Postgres, Qdrant and MinIO service containers; fake model providers | Real database and storage behavior, no keys or GPU needed |
| Production proxy | **Caddy** in front of the backend (M12) | Automatic TLS |
| Mobile (M13+) | **Expo** (React Native) + Expo Router, same generated API types | Same language and data layer |

---

## 6. Repository layout

```
roamate/
├── AGENTS.md                 how work is done here (CLAUDE.md imports it)
├── environment.yml           conda env "roamate"
├── .env.example              every setting with a comment, no secrets
├── config/
│   ├── models.yaml           development model chain, capabilities, embedding and reranker settings
│   └── models.launch.yaml    launch chain, added only after the M0.17 rights record
├── infra/
│   ├── docker-compose.yml    project "roamate"; profiles "shared" and "standalone"
│   └── setup/                dry-run-first scripts: database roles, collections, buckets
├── scripts/
│   └── build_roadmap.py      builds docs/plan/roadmap.html; --check is run in CI
├── backend/
│   ├── pyproject.toml
│   ├── requirements.lock     pip-tools lock
│   ├── app/
│   │   ├── main.py           creates the FastAPI app, includes routers
│   │   ├── worker.py         the job worker (python -m app.worker)
│   │   ├── config.py         settings from environment variables
│   │   ├── db.py             Postgres engine and session
│   │   ├── vectors.py        Qdrant client and collection helpers
│   │   ├── storage.py        S3 client (boto3) and object helpers
│   │   ├── models/           SQLAlchemy tables, one file per area
│   │   ├── schemas/          Pydantic models: brief, money, hours, place, itinerary, scenario, budget, validation, delta
│   │   ├── auth/             passwords, sessions, ownership and role dependencies
│   │   ├── jobs/             job table access, claiming, leases, events, budgets
│   │   ├── api/              routers: auth, cities, places, trips, jobs, admin, lab, health
│   │   ├── llm/              gateway.py, providers.py, structured.py, embeddings.py, reranker.py
│   │   ├── ingestion/        discover, collect, merge, enrich, score, review, publish, tiles, routing_build, pipeline
│   │   ├── catalog/          place queries, hybrid search, utility scoring
│   │   ├── planning/         travel.py, guards.py, solver.py, run_solver.py, scenarios.py, budget.py, validator.py, feasibility.py, diff.py
│   │   ├── workflow/         state.py, graph.py, nodes/, prompts/
│   │   └── providers/        weather.py
│   ├── migrations/           Alembic
│   ├── scripts/              ingest_city.py, create_admin.py, reset_password.py, run_evals.py
│   └── tests/
├── web/
│   ├── package-lock.json
│   └── src/
│       ├── api/              generated schema.ts + fetch client
│       ├── auth/             login, register, route guard
│       ├── shell/            app shell and navigation (from M1)
│       ├── pages/            Home, NewTrip, TripView, MyTrips, admin/Cities, admin/Review, lab/*
│       ├── components/
│       └── features/         trip-form, story, timeline, map, budget, revision
├── mobile/                   Expo app (from M13)
├── evals/                    intake cases, retrieval labels, personas (dev/ and heldout/), results/
└── docs/
    ├── plan/                 this plan, the step list, the review response, the roadmap and its template
    ├── design/               design documents, each with a status block (M0)
    ├── adr/                  short decision records
    └── background/           historical notes (not binding)
```

---

## 7. Data design (first draft, approved in M0)

These drafts show the shape of the system. Each becomes a full design document in M0 (columns, types, constraints, indexes, examples) and is approved before any migration is written. All money is stored as integer **minor units** (cents) with an ISO currency code. All timestamps are UTC; local times are computed with the city's time zone.

### PostgreSQL tables

| Table | Main columns | Purpose |
| --- | --- | --- |
| `app_user` | id, email (stored lower-case, unique), password_hash (Argon2id), display_name, role (`user` / `admin`, set only by the server), is_active, default_preferences (JSON), created_at, last_login_at | Accounts |
| `user_session` | id, token_hash (SHA-256 of a random 32-byte token), user_id, client (`web` / `mobile`), created_at, last_seen_at, expires_at, revoked_at, user_agent | Sign-in sessions behind the cookie or bearer token |
| `auth_attempt` | id, email_hash, ip, ok, created_at | Throttling sign-in and registration |
| `city` | id, slug, name, country, bbox, center_lat, center_lon, timezone, currency, status (`draft` / `active` / `retired`), active_snapshot_id | One row per city; the pointer to the snapshot users see |
| `city_snapshot` | id, city_id, number, status (`building` / `verifying` / `active` / `retired` / `failed`), manifest (JSON: object keys with checksums, Qdrant point count, PMTiles key, routing version, tariff and traffic profile ids), created_by_job_id, created_at, activated_at | A complete, versioned release of a city's data |
| `ingest_run` | id, city_id, job_id, stage, status, mode (`auto` / `semi`), params (JSON), stats (JSON), error, started_at, finished_at | One run of one pipeline stage |
| `place_candidate` | id, city_id, ingest_run_id, kind (`place` / `hotel`), osm_id, wikidata_id, name, lat, lon, raw (JSON), proposed (JSON), field_sources (JSON), scores (JSON: popularity, completeness, iconic), status (`pending` / `approved` / `rejected` / `merged`), reviewed_by, reviewed_at | What the pipeline found, before review |
| `review_override` | id, city_id, source_key (osm or wikidata id), field, value (JSON), action (`edit` / `approve` / `reject`), by, at, superseded_at | Reviewer decisions that survive a rerun |
| `place` | id, snapshot_id, city_id, candidate_id, name, category, lat, lon, description, interest_tags (JSON), visit_minutes, price_per_person_minor, price_state, hours (JSON: weekly windows plus date overrides, each with a state), hours_state (`confirmed` / `estimated` / `unknown`), popularity, completeness, iconic (0–1), rating and rating_count (nullable) with rating_source, accessibility_notes, website_url, booking_url, osm_id, wikidata_id, field_sources (JSON) | Published places in one snapshot |
| `hotel` | id, snapshot_id, city_id, candidate_id, osm_id, name, lat, lon, stars, features (JSON: breakfast, pool, parking, step-free access, …), guests_per_room, price_per_night_minor (estimate), price_source, price_fetched_at, rating and rating_count (nullable) with rating_source, field_sources (JSON) | Hotels the planner may suggest; prices are labeled estimates until a provider is connected |
| `city_tariff` | id, city_id, mode (`taxi` / `transit`), version, valid_from, valid_to, formula (JSON: flag_fall, per_km, per_min, surcharges by night, holiday or large vehicle, all minor units), single_ticket_minor, day_pass_minor, source_url, entered_by | Official fares, one row per city, mode and version |
| `city_traffic_profile` | id, city_id, version, factors (JSON: time-of-day window → driving time multiplier), calibrated (bool), calibration_notes, entered_by | Rush-hour factors, kept apart from fare surcharges so neither is applied twice |
| `media_asset` | id, place_id, city_id, kind (`exact_venue` / `area` / `generic_city` / `ai_decorative`), object_key, sha256, mime, bytes, width, height, original_url, license, author, attribution_text | Images in object storage with their credits |
| `trip` | id, user_id, city_id, title, created_at, current_version_id | A user's trip |
| `trip_version` | id, trip_id, number (unique per trip), base_version_id, brief (JSON), options (JSON: frozen itineraries, budgets, validation reports), refs (JSON: city_snapshot_id, routing version, tariff ids, traffic profile id, solver version, prompt and model ids, units), change_summary, created_by_job_id (unique), created_at | Frozen plan versions: never updated after insert |
| `trip_decision` | id, trip_id, version_id, kind (`select_option` / `approve`), option_key, by, at | Which option was selected and which version approved, as a history |
| `trip_story` | id, version_id, option_key, status (`ready` / `fallback` / `failed`), chapters (JSON referencing stop and day ids), prompt and model ids, created_at | Story text, generated separately so a failed story never blocks a valid plan |
| `job` | id, kind (`plan` / `revise` / `ingest` / `publish` / `story` / `test`), user_id, trip_id, city_id, status (`queued` / `running` / `waiting_for_user` / `succeeded` / `failed` / `cancelled`), graph_thread_id, resume_token_hash, idempotency_key (unique per user), locked_by, lease_until, heartbeat_at, attempts, max_attempts, deadline_at, budget (JSON: model calls, tokens, seconds, used and allowed), result (JSON refs), error_kind, error, created_at, started_at, finished_at | Durable work, claimed by the worker |
| `job_event` | id, job_id, seq, step, message, data (JSON), created_at | Append-only progress, what the web app polls |
| `llm_call` | id, job_id, trace_id, node, provider, model_requested, model_answered, attempt, ok, error_kind, latency_ms, tokens_in, tokens_out, created_at | Which provider answered, failures, cost and speed |
| LangGraph checkpoint tables | managed by `langgraph-checkpoint-postgres` | Graph state for pause and resume |

### Qdrant collections

| Collection | Point | Vectors | Payload (filterable) |
| --- | --- | --- | --- |
| `roamate_places__<model-slug>__<fingerprint>`, reached through the alias `roamate_places` | One per published place, id = place id | `dense` from TEI, `sparse` BM25 | city_id, snapshot_id, category, interest tags, price_per_person_minor, visit_minutes, open weekdays, popularity |

The **fingerprint** is a short hash of everything that makes vectors comparable: model id and revision, query and document prefixes, dimensions, normalization, the text template used to describe a place, and the sparse tokenizer settings. Switching models or templates means building a new collection, checking it, and moving the alias in one call. The old collection stays for rollback until hooman removes it. Search results are always filtered by city and active snapshot, then rechecked against Postgres.

### Object storage buckets

| Bucket | Object layout | Access |
| --- | --- | --- |
| `roamate-media` | `cities/{city_slug}/places/{place_id}/{asset_id}.{ext}` plus `…/{asset_id}_thumb.webp` | Public, licensed catalog images, served to the app through the backend |
| `roamate-tiles` | `cities/{city_slug}/{snapshot_number}/basemap.pmtiles` | Served to the map through the backend, with range requests |
| `roamate-routing` | `cities/{city_slug}/{snapshot_number}/extract.osm.pbf` and `builds/{routing_version}.tar.zst` | Private. Inputs and archives; the live routing data sits in a local versioned volume |
| `roamate-raw` | `ingest/{run_id}/{stage}/{file}.json` | Private. Raw API responses for repeatable runs, kept 90 days |

Private user documents (none in the first version) would get their own bucket and rules; they never go into `roamate-media`.

### Domain data structures (Pydantic)

- **`Money`**: amount_minor (int), currency (ISO code). Rounding happens once, at display.
- **`TripBrief`**: city_id; arrival (date and time) and departure (date and time), from which days, partial days and nights are derived; travelers; rooms (optional); budget (Money, scope: `ground_only` / `ground_and_lodging` / `everything`, covered categories); known_costs; interests (interest → weight); pace (`relaxed` / `normal` / `packed`); transport allowed (walk, metro, taxi); max_walk_minutes_per_day; day_start, day_end; hotel; hours_policy (`strict` / `allow_estimated`); must_do; excluded; notes.
- **`HotelChoice`**, part of `TripBrief`: a **fixed hotel** (booked: a hotel id or an address and location, with whether its cost is already paid) or **`HotelPreferences`**: required features (hard filter), nice-to-have features with weights, price cap per night, preferred area.
- **`OpeningWindow`**: local date or weekday, start, end (may pass midnight), state (`confirmed` / `estimated`), source. A place with no windows has hours state `unknown`.
- **`UtilityFeatures`** per candidate: interest match, rerank score (normalized within the query), popularity, quality (from a licensed rating, or a documented neutral prior when there is none), iconic, plus the normalization version. Kept separate from raw search scores, which only decide which places reach the solver.
- **`SolverInput`**: candidates, matrices with their version, windows per day, costs, limits and settings. It is checked by `guards.py` before any solve.
- **`SolveResult`**: status (`solved` / `no_solution_within_limit` / `proven_infeasible_precheck` / `invalid_input` / `solver_error`), the itinerary if any, objective parts, limits used, time taken.
- **`Stop`**, **`DayPlan`**, **`Itinerary`**: ordered stops with stable ids, arrive and depart times, waits, travel from the previous stop (mode, minutes, walking, cost, routed or estimated), the lunch break on full days, and the return leg to the hotel.
- **`Scenario`** (an option): profile (Budget, Balanced, Comfort), transport policy, the shared hotel and the runner-up hotels with their totals, itinerary, budget breakdown, metrics, skipped places with recorded reasons, validation report.
- **`BudgetBreakdown`**: lines by category marked `quoted` / `estimated` / `unknown` / `excluded`, nights and rooms, totals as Money, scope text.
- **`ValidationReport`**: named checks, each `passed` / `failed` / `not_checked`, with the day and stop where it failed.
- **`ConflictReport`**: proven conflicts found by the precheck (e.g. "the must-do is closed on every day of your trip"), and separately, relaxation suggestions labeled as suggestions (drop a must-do, allow taxis, raise the budget by a shown amount).
- **`ConstraintDelta`**: the structured form of a change request (e.g. day 2 walking cap 40 min, lock stop X, remove stop Y).
- **`ProgressEvent`**: sequence number, step, message, time, optional partial result.

---

## 8. Model gateway (LLMs, embeddings, reranker)

All model calls go through `backend/app/llm/`. Nothing else in the code talks to a model provider directly.

### Chat models with fallback

`config/models.yaml` defines each provider once, with what it can do, and a single line chooses the order. Free-tier API models, which are usually stronger than our local model, come first; the local vLLM model is the last fallback. Keys stay in `.env`; the YAML only names the variable. This file is the **development** configuration. The **launch** configuration, `config/models.launch.yaml`, is written only after M0.17 records each provider's usage rights, data retention and cost.

```yaml
# Order to try. Change this line (or set LLM_CHAIN in .env) to reorder; nothing else changes.
chain: [openrouter-free, gemini-free, local-gemma]

providers:
  openrouter-free:              # OpenRouter; tries the listed free models in order on its side
    base_url: https://openrouter.ai/api/v1
    models: [<nemotron :free id>, <deepseek :free id>]
    api_key_env: OPENROUTER_API_KEY
    capabilities: {json_mode: true, max_context: 32000}
  gemini-free:                  # Gemini free tier through its OpenAI-compatible endpoint
    base_url: https://generativelanguage.googleapis.com/v1beta/openai/
    model: <gemini flash model id>
    api_key_env: GEMINI_API_KEY
    capabilities: {json_mode: true, max_context: 100000}
  local-gemma:                  # vLLM on the shared GPU: fallback capacity, at most 2 parallel requests
    base_url: ${VLLM_BASE_URL}
    model: /app/model
    capabilities: {json_mode: true, max_context: 8000}
  nineroute:                    # opt-in: add to `chain` only after its upstream accounts are vetted (M4.3)
    base_url: ${NINEROUTER_BASE_URL}        # e.g. http://localhost:20128/v1
    model: ${NINEROUTER_MODEL}              # a 9Router combo name
    api_key_env: NINEROUTER_API_KEY
    capabilities: {json_mode: false, max_context: 32000}
```

Which services and models we actually use is left open on purpose: each one is a config entry, and we add, remove or reorder them as we test them. Exact model ids are filled in when a provider is first set up, since free model lists change often. A provider without a key or address is skipped with a note, not treated as an error.

How a call works:

1. `gateway.structured(prompt, OutputModel, job_budget)` tries the first provider in `chain` that has the needed capabilities.
2. It moves to the next provider on a connection error, a timeout, HTTP 429 or 5xx, or an answer that is still invalid for `OutputModel` after one repair retry. On 429 and 5xx it honors `Retry-After` and adds jitter.
3. HTTP 400, 401 and 403 are not retried: the provider is marked misconfigured until its settings change.
4. A provider that returned 429 is skipped for a cool-down period (60 s by default).
5. **One budget per job.** Every attempt, fallback and repair draws from the job's budget: at most 30 calls, a token cap and the job's deadline. When it runs out, the job stops with a clear message instead of making something up.
6. After the shape check, a **meaning check** compares the answer with the brief (dates inside the trip, the right city, no invented place ids).
7. Every attempt is written to `llm_call` with provider, requested and answering model, latency, tokens, error type and trace id, and the Lab shows it. Prompts in logs are redacted.

**Two levels of fallback.** OpenRouter (its `models` list) and 9Router (its combos) already fall back between models inside their own service. Our gateway adds the outer level: across services, to the local model, and on answers that are not valid for our schema, which a router cannot judge. OpenRouter's list contains only `:free` model ids, because a fallback to a paid model is billed. Fallback never changes a hard limit and never reaches a paid model that is not in the launch configuration.

All these services expose the OpenAI-compatible chat API, so one client class covers them. Tests use a fake provider that can be told to fail, time out, return 401 or 429, or return bad JSON.

**9Router** is open-source (MIT) software we would run ourselves (`npm install -g 9router`, port 20128). It is opt-in: its license covers the router, not the upstream accounts it uses, so each upstream account is checked for unattended use before 9Router joins the chain. At least one supported provider always works without it.

### Embeddings and reranking

- `embeddings.py` calls TEI `/embed` with the model's query and document prefixes, checks the vector size and that every value is finite, and records the collection fingerprint with every vector written.
- `reranker.py` calls TEI `/rerank` (currently `bge-reranker-v2-m3`) to reorder the top search candidates. Search still works without it.
- **Development model:** `jina-embeddings-v5-text-small-retrieval`, already running, is the provisional model.
- **Choosing the model (M8):** we label briefs with the places a good planner would consider, split them into a development set and a frozen held-out set (including exact names, other languages, no-result requests and must-dos), and measure recall@50 on the held-out set for dense, keyword, hybrid and reranked search. Candidate models run only on the separate `roamate-tei-lab` container. We pick by recall (reported with its uncertainty, since the set is small), GPU memory and license.

| Candidate | Size | Vector size | Context | License | Notes |
| --- | --- | --- | --- | --- | --- |
| `jinaai/jina-embeddings-v5-text-small-retrieval` | 677M | 1024 (can be cut to 512, 256, …) | 32k | CC BY-NC 4.0: non-commercial; commercial use needs a license from Jina | Already running in TEI for RagBot; prefixes `Query: ` / `Document: ` |
| `google/embeddinggemma-2` | 270M text backbone (740M with image and audio encoders) | 768 (can be cut to 512, 256, 128) | 8k | Apache 2.0 | Prefixes `task: search result \| query: …` / `title: none \| text: …`; must run in bfloat16, not float16; TEI support checked on the lab container |
| `Qwen/Qwen3-Embedding` (0.6B, 4B, 8B) | 0.6B to 8B | up to 4096 | 32k | Apache 2.0 | 8B needs about 16 GB of GPU memory next to vLLM; test 0.6B first |

**Launch gate:** a commercial launch needs a model whose license allows it (one of the Apache 2.0 models) or a paid Jina license.

---

## 9. City data pipeline

Adding a city is one command or one button: `python -m scripts.ingest_city "Lisbon, Portugal" --mode semi`, or **Admin → Cities → Add city**. The pipeline runs as a job on the worker, in stages. Each stage stores its output, can be re-run on its own, and records progress in `ingest_run` and `job_event`.

| Stage | What it does | Output |
| --- | --- | --- |
| 1. Discover | One Nominatim lookup for the city, plus Wikidata: boundary, bounding box, center, timezone, currency | `city` row (status `draft`) |
| 2. Collect | Query Overpass for tourist categories (museums, monuments, viewpoints, parks, markets, galleries, historic sites, food spots) and for accommodation (hotels, hostels, guest houses), and Wikidata for notable items inside the boundary | Raw responses in `roamate-raw`, rows in `place_candidate` |
| 3. Merge | Join OSM and Wikidata records (by Wikidata tag, then name and distance); remove duplicates; keep the source of every field | One candidate per real place |
| 4. Enrich | Wikipedia summary; Wikimedia Commons images with license and author (downloaded safely to `roamate-media`); OSM opening hours parsed into windows with a state; website. Hotels get features from OSM tags, a room capacity and a labeled nightly price estimate. The LLM proposes interest tags, typical visit time and price band, each marked `estimated_by_llm` | Filled `proposed` fields with sources |
| 5. Score | Popularity (Wikipedia language links, page views), completeness (required fields present), iconic (heritage listings and notability). Ratings only from a licensed source; none in the first version | `scores` per candidate |
| 6. Review | **Semi mode:** the admin review screen lists places and hotels by score with gaps and sources shown; approve in bulk, edit, reject. **Auto mode:** approve every candidate above a score threshold that has all required fields and an allowed license. Reviewer decisions go to `review_override` and are reapplied on every rerun | Approved candidates |
| 7. Publish | Build a new **city snapshot** (below) | A city the planner can use |

### Publishing a snapshot

1. Create `city_snapshot` with status `building`.
2. Write the snapshot's `place`, `hotel` and `media_asset` rows; embed and upsert Qdrant points with `snapshot_id`; extract the map file; build the routing data into a new versioned directory. Every artifact goes into the manifest with its checksum.
3. Status `verifying`: count rows and points, check checksums, load the map file, and run a routing smoke test (a few known walking and driving routes).
4. In one Postgres transaction: set the snapshot `active`, the previous one `retired`, and move `city.active_snapshot_id`. Then switch the routing service to the new directory.
5. If any step fails, the snapshot is marked `failed` and users keep the previous snapshot (or see "city not available yet" for a first publish). Retrying a publish is safe because every write is keyed by the snapshot.
6. A retired snapshot's Qdrant points and routing directory are removed after a retention period, once no running job uses them. Its Postgres rows stay. Saved trips do not need them, because each trip version holds its own frozen facts.

### Rules

- **Source policies:** Nominatim only for the one city lookup, never for listing places or autocomplete. Each source has one app-wide pacer (Nominatim at most one request per second, polite Overpass use), an identifying User-Agent with a contact address, caching of raw responses, and `Retry-After` handling. Response sizes and retries are capped.
- **Safe media downloads:** only `https`, no private or local addresses (also after redirects), a size cap, an allowed list of image types checked from the bytes, and no HTML. Only media whose license allows storing it, always with author and license for display.
- **Opening hours:** windows are `confirmed` (from OSM or the official site), `estimated` (from the LLM or a category default) or absent (`unknown`); they support date overrides, split and overnight windows and daylight-saving changes (Python `zoneinfo`), and public holidays come from the `holidays` package. Unknown is never shown as checked. In `strict` mode the planner skips places with unknown hours, except always-open outdoor categories (parks, viewpoints, squares, monument exteriors), which carry a visible "hours not confirmed" label. In `allow_estimated` mode estimated windows can be used, labeled.
- **Tariffs:** the admin enters the city's taxi formula and transit ticket prices on the Cities screen, copied from the official source with its link and valid dates, plus a separate rush-hour profile. A city cannot be published without them.
- **Required fields** for a place to be usable by the planner: coordinates, category, visit time, at least one interest tag, and an hours state.

The first city is chosen in M0.13 (Lisbon is the default). A second city is added in M6 to prove that adding a city needs no code changes.

### Map and routing data

- **Map:** `pmtiles extract` from a pinned Protomaps basemap build, over the city's bounding box plus a buffer of about 10 km. The map style, fonts (glyphs) and icons (sprites) are stored in the repository. The backend serves the file with `Range` requests, `ETag`, and correct 206 and 416 responses.
- **Routing:** a regional OpenStreetMap extract (Geofabrik or BBBike) cut to the same buffered area with `osmium`, built into Valhalla tiles in a new directory per routing version. Valhalla serves every published city from one tile set, so a new city means a rebuild that includes all active cities, followed by the smoke test and the switch.
- Both builds run as jobs with time, memory and disk limits. M0.16 tries both on a small area before M6 builds them for real.

---

## 10. Planning workflow (LangGraph)

The whole planning flow is one LangGraph graph from its first version, run by the worker.

```
                ┌──────────────┐
 free text ───▶ │ intake (LLM) │──missing info──▶ [pause: clarify] ─┐
                └──────┬───────┘                                    │
 form ─────────────────┤◀──────────────────────────────────────────┘
                       ▼
               [pause: confirm brief]
                       ▼
               precheck: limits, input checks, simple proven conflicts ──conflict──▶ explain choices (end)
                       ▼
               retrieve candidates (hybrid search + rerank + utility; must-dos always added)
                       ▼
               weather rule (forecast only; adjusts outdoor utility per day)
                       ▼
               choose hotel (fixed, or shortlist ≤ 5 → solve per hotel → best total)
                       ▼
       ┌───────────────┼───────────────┐
   solve Budget   solve Balanced   solve Comfort      (independent, at most 4 solver processes)
       └───────────────┼───────────────┘
                       ▼
                   validate each ──violation, tries < 2──▶ repair (never relaxes user limits) ──▶ solve
                       ▼
                   compare: drop duplicates and dominated options → 0–3 options
                       ▼
                   budget breakdown
                       ▼
                   curate "why this fits you" (LLM, from recorded facts)
                       ▼
                   save trip version (once per job)
                       ▼
                   story chapters (LLM, separate step; template text if it fails)
```

- **State** (`workflow/state.py`): user and trip ids, raw request, brief, open questions, confirmed flag, candidates, solve results, validation reports, repair attempts, options, events, errors, budget used. Lists that parallel branches write to use reducers.
- **Pauses** use LangGraph's `interrupt()`. The job's status becomes `waiting_for_user`, the web app shows the question or the brief summary, and `POST /api/jobs/{id}/resume` with the job's one-time resume token continues the same graph thread. Only the job's owner can resume; a second resume with the same token is refused.
- **Checkpoints** in Postgres keep the graph state. They do not run anything by themselves: the worker picks the job up again after a restart (below).
- **Revision** is a second, smaller graph: parse the change (LLM → `ConstraintDelta`, asking before any hard limit changes) → re-solve with locked stops → validate → diff → save a new version on the expected base version. If the trip moved on in the meantime, the save fails with a "this trip changed" message (HTTP 409).
- **Progress events** are appended to `job_event` by each node; the web app polls them.

### Jobs and the worker

- The API only creates jobs and reads them. One **worker process** (`python -m app.worker`, same codebase) runs them.
- The worker claims a `queued` job with `SELECT … FOR UPDATE SKIP LOCKED`, sets `locked_by` and `lease_until` (about 60 s ahead), and renews the lease every 15 s while it works.
- On start, and every minute, the worker takes back `running` jobs whose lease expired and resumes their graph thread from the last checkpoint. After 3 attempts a job fails with a clear error. Jobs `waiting_for_user` are never picked up until the user answers.
- Every job has a deadline (about 120 s of work for a plan) and a model budget (§8). Cancelling sets the status to `cancelled`; the worker checks for it between nodes and stops.
- Starting a job takes an idempotency key, so a double click gives the same job.
- **Replay safety:** a node may run twice after a crash, so its side effects use keys that make a second write harmless: events by sequence number, media by asset id, and the trip version by `created_by_job_id`, which is unique.

### Solver (port of `solver_example.py`, with fixes)

- **Model:** a prize-collecting Team Orienteering Problem with Time Windows on OR-Tools routing. Each day is a vehicle that starts and ends at the hotel. Each place is optional, and dropping it costs its utility. Must-dos are mandatory.
- **Units:** time in minutes, money in minor units, utility in integer points, walking in minutes. The weights that turn time and money into points are documented and tested.
- **Input checks first** (`guards.py`): all values finite, non-negative and below set caps; windows valid; at least one day; no more than 60 candidates; matrix sizes match. A hotel whose nights already exceed the budget is skipped with a reason, before the solver. A zero remaining budget is valid; free places can still be planned. Invalid input returns `invalid_input` without calling OR-Tools.
- **Supervised child process:** each solve runs in its own process with a 10-second limit and is killed if it overruns. A native crash fails that solve with `solver_error`, not the worker or the API.
- **Daily windows:** each place gets one copy (clone) per trip day, each with that day's opening window and allowed only on that day's vehicle. A "visit at most once" disjunction over the copies stops repeats. Split windows are separate copies; overnight windows are cut at the day's end.
- **Lunch:** on a full day, a 60-minute lunch break must start between 12:00 and 14:00 and lie between the day's start and the return to the hotel, and it is shown in the timeline. A partial day that does not cover the lunch window has no lunch, and the timeline says so.
- **Objective:** chosen explicitly in M0.6 and tested on small hand-computed cases. The proposal: maximize collected utility minus weighted travel time, money and walking, with a soft upper bound on each day's return time instead of OR-Tools' global span cost (which measures the latest finish minus the earliest start, not day balance).
- **Utility** (first, hand-written version): $u_i = 100 \cdot (w_1\,\text{interest match} + w_2\,\text{rerank} + w_3\,\text{quality} + w_4\,\text{iconic} + w_5\,\text{popularity})$. Quality uses a neutral prior when no licensed rating exists. Price and duration stay out of $u_i$ because the solver already charges for money and time. Simple caps (e.g. at most two museums a day) stop repetition. A learned version replaces it only if it beats this one on held-out data.
- **Transport policies:** each option is solved under up to three fixed policies (for example walk + metro, walk + taxi, walk only; only modes the user allowed). Within a policy, each leg uses the policy's mode for its distance band (e.g. walk under 1.2 km, otherwise the policy's other mode). Pairs the routing service cannot connect are left out, never set to zero. Every result is validated, and the best valid one is kept.
- **Transit day pass:** the solver prices transit legs at single-ticket fares, which is a safe upper bound for the budget cap. After the solve, each day is charged the cheaper of its single tickets and the day pass. The saving is shown.
- **Hotel choice:** a booked hotel is the fixed start and end of every day, and its cost is charged only if it is inside the budget scope and not already paid. Otherwise: filter hotels by required features and price cap, shortlist at most 5 by feature match, quality and location, solve the trip from each with Balanced weights and the money left after the nights (nights from check-in and check-out dates, times rooms), and pick the best total (trip objective + money weight × hotel cost − feature bonus). The three options share the chosen hotel. The runner-up hotels are shown so the traveler sees the trade-off.
- **Fares:** taxi fare per ride = flag fall + per-km × road km + per-minute × road minutes (from the city's tariff formula and the routing matrix), plus surcharges by time of day, times the number of taxis the party needs, shown as a range.
- **Traffic:** the routing service gives free-flow times. Driving times are multiplied by the city's rush-hour profile (e.g. ×1.3 at peak hours, ×1.1 midday). The profile is labeled `estimated` until calibrated against a few hundred real trip times at different hours. Buffers between stops absorb the rest. Traffic changes time only; fare surcharges stay in the tariff, so nothing is applied twice.
- **Options:** Budget, Balanced and Comfort are solved independently, in parallel, under the same hard limits. A profile can only make the user's limits stricter, never looser. Afterwards, options with the same stops are merged, an option that is worse on every shown metric than another is dropped, and the app shows 0–3 options with a note when there are fewer than three. A day without activities counts only if it is intentional free time (shown as such); otherwise it is flagged.
- **Statuses:** every solve reports `solved`, `no_solution_within_limit` (the time limit ran out without a plan, which proves nothing), `proven_infeasible_precheck`, `invalid_input` or `solver_error`. The app words each one differently.
- **Tests** use a fixed solution limit instead of a time limit so results repeat. Where ties make several routes equally good, tests check properties (validator passes, totals) instead of the exact order.

### Validator and conflicts

The validator is separate code that recomputes every time and cost from the frozen inputs (catalog facts, matrices, tariffs, passes, nights) instead of trusting the solver's totals. It checks opening windows on the actual date, day start and return, lunch rules, waits, duplicates, must-dos, locks, budget, walking cap, pace, travel modes and time continuity. Each check reports `passed`, `failed` (with day and stop) or `not_checked` (e.g. hours unknown). A hard violation blocks the option. Its first version is built with the solver in M7, and M8 extends it with Hypothesis tests that plant one violation at a time.

The **feasibility precheck** proves simple conflicts before solving (a must-do closed on every trip day, a budget below the cheapest hotel night, more must-do time than trip time). When the solver finds no plan and the precheck found nothing, the app does not claim the trip is impossible. It first retries with more candidates within the job's budget. If that also fails, it runs a few diagnostic solves with one limit loosened at a time and shows the results as suggestions ("allowing taxis on day 2 would make a plan possible"). Hard limits are never changed without the user agreeing.

### Weather

The weather rule runs before the hotel choice and the solves. A forecast exists only up to 16 days ahead. If a day's precipitation probability is 60% or more, outdoor places get utility × 0.6 on that day (through the day copies), so indoor places are preferred without forbidding anything. Must-dos stay. Seasonal climate data only appears in the story, labeled as seasonal. When no forecast is available, the plan and story make no weather claim. Forecasts are cached per city and day for 3 hours.

### Story and explanations

Curation and story text come from the LLM but reference stop and day ids. Every number shown next to them comes from domain data. Skipped-place reasons come from recorded facts (closed that day, over the walking cap, lower utility than the chosen alternative), not from the model. If the story fails or is invalid, the plan is still saved and shown with short template text per day and a "try again" button. Story text is stored in `trip_story`, separate from the frozen version.

---

## 11. The web app

### Screens

| Screen | Who | What it does |
| --- | --- | --- |
| Sign up, sign in | Everyone | Email and password |
| Home | User | "Plan a trip", "My trips", an example trip |
| New trip | User | Free-text box that fills the form, then the step form with the supported limits shown; confirm summary |
| Clarify / confirm | User | Answers the graph's questions; confirms the brief |
| Planning | User | Real progress steps from the job, with cancel and retry |
| Trip view | User | Option switcher (0–3) with an honest note, hotel choice with runner-ups, and four tabs: Story, Timeline, Map, Budget; linked selection; place drawer with reasons, duration, price, source and confidence, media credit, booking link |
| Revise | User | Change box, quick chips, stop locks, "what changed" diff, approve |
| My trips | User | Saved trips with version history |
| Cities | Admin | Add a city, run progress per stage, cancel, publish, snapshot history |
| Review | Admin | Place and hotel queue: bulk approve, edit, reject, sources and gaps shown |
| Lab | Admin | Models, Search, Solver, Validator, Intake, Runs, Evals |

Trust labels throughout: `Checked`, `Estimated`, `Unknown`, `Excluded`, and image labels (`This venue`, `This area`, `City photo`, `AI illustration`).

### Look and states

M0.12 designs the visual system before any screen is built: color and spacing tokens, type, motion (and reduced motion), how images and credits are composed, and the loading, empty, partial and error state of every screen. Each UI milestone checks keyboard use and contrast as it goes; M10.14 adds visual checks at desktop and phone sizes; M12.7 is the final audit.

### Everything served locally

- All JavaScript and CSS packages are bundled by Vite into `web/dist`. No CDN links.
- Fonts come from `@fontsource` packages and icons from `lucide-react`, both bundled.
- The map uses MapLibre GL JS with the city's PMTiles file, plus the map style, glyphs and sprites stored in the repository, all served by our backend.
- Place images are served from object storage through the backend.
- **Network-request check** (M1.9): a static check of the built files and the map style for undeclared external fetches, and a Playwright run that intercepts every request while the screens are used and fails on any request outside our own origin. Links the user clicks (booking, sources, licenses) and inert strings inside libraries are allowed.

The backend itself still needs the internet for API-based models, weather and city ingestion. With the local vLLM model, cached weather and an already published city, a trip can be planned with no internet at all.

---

## 12. Milestones

Sizes are rough guesses for one developer working with AI coding help: **S** ≈ under a week, **M** ≈ 1–2 weeks, **L** ≈ 2–3 weeks. They are not commitments. *Gate* is what must be true before the next milestone starts.

### Phase 1 — Design and approval

**M0. Design and approval (L)**
Approve this plan, then write and approve every design before coding: infrastructure and the real server facts, Postgres schema, Qdrant collections, object storage, domain structures with the solver objective, auth, model gateway, city pipeline, durable jobs, LangGraph graph, API contract, web screens and design system, provider rights, launch city and evaluation cases. Two small throwaway spikes check the solver formulation and the map and routing builds. Each design is a file in `docs/design/` with a status block.
*You can test:* read and approve each design and the two spike reports; no product code exists yet.
*Gate:* every design is marked approved, the compatibility manifest holds the real server facts, and the spikes' tiny cases match the hand-checked answers.
*Release:* Designs approved

### Phase 2 — Foundation and accounts

**M1. Foundation (M)**
Conda environment with locked packages, backend and web skeletons with a minimal app shell, Compose with its own names and profiles, dry-run setup scripts for the database roles, collections and four buckets, live, ready and diagnostics endpoints, correlation ids and redacted logs, the network-request check, lint, type checks and CI with real service containers.
*You can test:* `conda activate roamate`, start the backend and web app from the repository root, and see the status page; point the reranker setting at a wrong address and see it reported as degraded while the app still starts.
*Gate:* a clean machine reaches the status page with the documented commands, setup refuses non-Roamate names, and no shared service was changed.

**M2. Accounts and login (M)**
User, session and sign-in attempt tables, Argon2id passwords, hashed session tokens with expiry, rotation and revocation, register, sign in, sign out and current user, throttling and Origin checks, server-set roles, admin creation and password-reset commands, sign-in pages, protected navigation and the admin menu, and one ownership check used by every user resource.
*You can test:* create two accounts, sign in and out; an admin sees the Admin menu and a normal user does not; the second user gets "not found" for the first user's test resource.
*Gate:* the two-user denial and session lifecycle tests pass.

**M3. Core data layer (L)**
Migrations for all remaining tables including city snapshots, trip decisions and job events, Pydantic domain models, version numbering and the stale-version check, the reusable job runner and worker, Qdrant and S3 helpers tested on real services, generated TypeScript types, fixtures, and a fixture trip shown in the app.
*You can test:* run migrations and setup on an empty database; start the worker, submit a test job, kill the worker, and watch the job get picked up again; open the fixture trip in the app.
*Gate:* engineering tracer: a labeled fixture trip goes from a signed-in request through the database to the screen; clean-migration, lease-reclaim and concurrency tests pass.
*Release:* Engineering tracer

### Phase 3 — Models and city data

**M4. Model gateway (M)**
Providers and capabilities from `config/models.yaml`, ordered fallback with cool-down, `Retry-After` and jitter, no retries on auth errors, structured output with validation, one repair and a meaning check, a job-wide model budget, `llm_call` logging with the answering model, TEI clients with prefix and size checks, 9Router as an opt-in provider, separate development and launch configurations, Lab → Models page.
*You can test:* Lab → Models: send a test prompt; point the first provider at a wrong address and watch the next one answer, with each attempt and the budget used listed.
*Gate:* fake-provider tests prove a finite number of attempts and a deadline even when every provider and every repair fails; no shared service was stopped.

**M5. City data pipeline (L)**
The city pipeline as a job: discover, collect, merge, enrich, score, with resumable stages, one pacer per source, raw data in object storage, licensed images with safe downloads, opening hours with states, hotels as reviewable candidates, LLM-estimated fields marked per field, ratings only from licensed sources, and a command-line entry point.
*You can test:* run the ingest command for the launch city, stop it halfway, rerun it, and inspect the candidates, their sources, hours states and images.
*Gate:* a recorded ingestion repeats safely, and a rerun keeps review edits and license data.

**M6. City review and publishing (L)**
Admin Cities and Review screens, tariff and rush-hour profile entry, auto-approve rules, publishing as a city snapshot across Postgres, Qdrant, media, map tiles and routing with the switch at the end and rollback, the local map served with range requests, the routing service with versioned data, the launch city published, a second city added through the UI only, and a mobile map and sign-in check on an Android development build.
*You can test:* Admin → Cities → Add city, follow the stages, approve places in Review, publish, and see the city's places on its local map; publish a second city and check the first one still routes.
*Gate:* two cities render and route after a reload, and a publish that fails at any store leaves the previous snapshot active.

### Phase 4 — Planning engine

**M7. Solver and scenarios (L)**
Utility from separate features, travel matrices from the routing service with unreachable pairs left out, tariff-based taxi fares and transit costs in minor units, rush-hour factors labeled until calibrated, the OR-Tools model behind input checks in a supervised child process, the first independent validator on every solve, daily windows and lunch, transport policies and the day pass, the hotel shortlist and per-hotel solve with real nights and rooms, independent Budget, Balanced and Comfort solves with duplicates and dominated options removed, solver statuses, Lab → Solver page.
*You can test:* Lab → Solver: pick a city and a sample brief, ask for a hotel with breakfast, change weights and caps, compare the hotel totals and the options, and try an over-budget hotel to see it skipped with a reason.
*Gate:* every solve passes the validator; invalid input never reaches OR-Tools or stops the API; a timeout and a proven conflict are reported differently.

**M8. Validator, budget and search (M)**
The full validator with exact violation locations and property tests, the budget breakdown with nights, rooms and scope, the feasibility precheck with proven conflicts and labeled suggestions, hybrid search filtered by city and snapshot with must-dos always kept, embedding collection switch and rollback, development and held-out label sets, the embedding comparison on the lab TEI, Lab → Validator and Lab → Search pages.
*You can test:* break an itinerary in Lab → Validator and see the exact violation; compare search methods and embedding models by measured recall on the held-out set in Lab → Search.
*Gate:* planted violations of every hard rule are caught, a low-ranked must-do survives retrieval, and the chosen embedding model has a recorded license.

### Phase 5 — AI workflow and web app ("Web Alpha")

**M9. LangGraph planning workflow (L)**
Graph state and nodes for the form path, Postgres checkpoints resumed through the job runner, the planning job API with cancel and resume tokens, the intake node with clarify and confirm pauses, the hotel node, option solves in parallel under a process cap, validate and repair without relaxing user limits, the weather rule before solving, curation and story nodes with a template fallback, the intake eval set, recovery fault tests, Lab → Intake and Lab → Runs pages.
*You can test:* start a plan through `/docs` or Lab → Runs, answer a clarification, kill the worker mid-run, and see the job finish after restart without a duplicate version.
*Gate:* kill, restart, duplicate-resume and duplicate-save tests pass, and each result is validated and saved exactly once.

**M10. Web app: plan, explore, save (L)**
Trip navigation in the app shell, the new-trip form with free text and visible limits, clarify and confirm screens, progress with cancel and partial results, the trip view with 0–3 options and the hotel choice, Story, Timeline, Map and Budget tabs with linked selection, the place drawer, My trips, a Playwright end-to-end test on real local services, visual and network-request checks, and the Web Alpha tag.
*You can test:* the full flow in a browser: sign in, describe a trip, confirm, compare options, read the story, check the map and costs, sign out and back in, reopen it.
*Gate:* Web Alpha: the flow above works with real city data, every time and cost shown passed the validator, and failure states stay usable. Revision is not part of Alpha.
*Release:* Web Alpha

### Phase 6 — Revise, evaluate, deploy ("Web Beta")

**M11. Revision and approval (M)**
The change parser into `ConstraintDelta` that asks before changing hard limits, stop locks, the revision graph saving on the expected base version, the "what changed" diff, approval of an exact version and option, version history, outbound booking links that never mark anything as booked, concurrency tests, and the end-to-end test.
*You can test:* "less walking on day 2" on a saved trip, see the diff, approve, and open the previous version.
*Gate:* a revision on a stale version is refused, the approved version stays recoverable, and another user cannot revise or approve.

**M12. Evaluation, hardening and deployment (L)**
Persona harness with development and held-out sets, deterministic graders and an LLM judge checked against human labels, the regression suite in CI, qualified metamorphic tests, p50/p95 timings under a stated load, the provider usage dashboard, the final accessibility audit, a scaling decision for the worker from measurements, a backup, restore and rollback rehearsal with a RagBot load check, deployment behind TLS with scoped credentials, the Lab → Evals page, and the Web Beta with a few real testers.
*You can test:* the deployed web app from another computer, including the full success test; the Evals page shows violation rate, intake accuracy, recall, latency and cost.
*Gate:* Web Beta: the success test passes on the deployed app, a restore has been rehearsed, and no critical correctness or isolation issue is open.
*Release:* Web Beta

### Research track — TravelPlanner (side track, after Web Alpha)

This track starts after Web Alpha and runs next to M11 and M12 without delaying them. It reuses the model gateway, the validator idea and the evaluation tooling, and it does not change the traveler app. Background and the paper question: [formulation, hotels, fares and TravelPlanner](../background/formulation-hotels-fares-travelplanner.md), §5. The benchmark's README forbids converting **test** queries into structured formats for optimization, which is close to our method, so R1.0 settles what we may do before anything else.

**R1. TravelPlanner rules, setup and baseline (S)**
Check the benchmark's rules against our method first (asking the maintainers only with hooman's approval), then set up a separate `roamate-tp` environment (Python 3.9) with a pinned dataset, scorer and run manifest, download the dataset (train 45, validation 180, test 1,000 queries) and its sandbox, run the official validation scorer, record published baselines by split and mode, and write down the paper claim before any experiment.
*You can test:* run the official scorer on a sample submission and see delivery, commonsense, hard-constraint and final pass rates.
*Gate:* the rules check is written down; if our method is not allowed on the test set, no official submission is planned.

**R2. TravelPlanner adapter and solver mode (L)**
Query → Roamate constraint spec (a JSON schema filled by the LLM through the gateway; used on test queries only if R1.0 allows it), a loader for the sandbox data, a CP-SAT model with input checks and time limits for multi-city, day-level plans (city order, inter-city transport, one accommodation per city with room type, house rules and minimum nights, meals, attractions, budget), an independent validator, and a renderer to the official submission JSONL.
*You can test:* run the 180 validation queries and get a scored submission file.
*Gate:* the method is frozen before scoring, and failed queries count in the totals.

**R3. Experiments and submission (M)**
A results table for fixed single models, with the fallback chain reported as a separate system (pass rates, plan quality, cost per solved query, run ids), optional TripScore after checking its rules, at most one test-set submission and only if R1.0 allows it, and a workshop-paper draft with only the claims the results support. No tuning on the test set.
*You can test:* the Lab → Evals page shows the TravelPlanner table per model, reproducible from its run manifest.
*Gate:* the table reproduces from its manifest, and the side track has not delayed Web Beta.

### Phase 7 — Mobile app

**M13. Mobile app core (L)**
Expo app with Expo Router, shared TypeScript code in `shared/`, sign-in with a revocable token in secure storage, trip intake, progress that reconnects after the app was in the background, the trip view tabs, the map with the city's local tiles (approach checked in M6.11), revision and approval, tested on a real device and in the Android emulator.
*You can test:* the brief's demo flow in the Android emulator against the same backend, plus an expired session.
*Gate:* the demo works on an Android development build with local map tiles and secure sign-in.

**M14. Mobile polish and tester release (M)**
Offline view of saved trips per account, cleanup on sign-out and account switch, accessibility and slow-network checks, app icon and splash, internal test builds with EAS (Android, then iOS) with no secrets inside.
*You can test:* install the test build on a real phone, sign out, sign in as someone else, and see no trace of the first account's trips.
*Gate:* a real-device test passes with no cross-account leaks; store publication is a separate decision.
*Release:* Mobile testers

### Later (not planned in detail yet)

Password reset by email, private group planning (invite, vote, lock, approve), share links and "Make this trip mine", learned ranking from saves and skips, visit-duration prediction, joint per-leg mode choice, public transport routing with GTFS (OpenTripPlanner), historical street speeds in the routing service, a live traffic check (paid API) for the taxi legs of same-day trips, moving between hotels or cities in one trip, booking integrations after separate validation.

---

## 13. How we work

### Approval before implementation

1. **M0 designs everything first.** Each design document in `docs/design/` (schemas, data structures, API, graph, pipeline, screens) starts with a status block (status, version, approved by, date, supersedes) and is changed until hooman approves it. Nothing is coded before its design is approved.
2. **Spikes are allowed in M0, and labeled.** M0.15 and M0.16 write small throwaway code to answer a design question. Their code is not product code; their results go into the design they support.
3. **Each step gets a go-ahead.** Before starting a step, Claude posts a short step brief: the design it follows, what will be built, which files change, the acceptance command that proves it works, the tests, and any detail the design left open. Work starts after hooman approves.
4. **A finished step is ticked with evidence**: the commit and the test or command it passed, written next to the step (`done: abc1234, pytest tests/auth`). A chat message alone does not mark a step done.
5. **Design changes during coding** go back to the affected design or ADR; the code follows the approved version.
6. [AGENTS.md](../../AGENTS.md) holds these rules for any coding agent, together with the shared-service rules and the authority order from §0.

### Branches

- **Until Web Alpha (end of M10):** commits go directly to `main`, one commit or a few per step, each with tests passing. Before each step, pull the latest `main`; only one person or agent pushes at a time; the next step starts only when CI is green.
- **From Web Alpha on:** `main` stays the working version. Each step is a branch (`m11-2-stop-locks`) and a pull request that is merged after review and green CI.

### Other rules

- Write the core pieces by hand first (solver model, validator, one graph node, the version schema), and use AI help for boilerplate, as the earlier decision record recommends.
- Secrets live only in `.env` (never committed). `.env.example` lists every setting. gitleaks runs in pre-commit and CI.
- Definition of done for a milestone: its *You can test* item works in the running app, its *Gate* holds, tests and CI are green, the README run steps still work, and every step is ticked with evidence.

---

## 14. Testing strategy

| Layer | What we test | Tool |
| --- | --- | --- |
| Schemas | Valid and invalid briefs, money units and rounding, dates, nights, partial days, limits | pytest |
| Auth | Hashing, expiry, rotation, revocation, throttling, Origin checks, roles on every admin route, ownership on every user resource | pytest |
| Jobs | Claim, lease, heartbeat, reclaim after a kill, cancel, deadline, duplicate start and duplicate resume | pytest on a real Postgres |
| Model gateway | Fallback order, cool-down, no retry on auth errors, repair, budget exhaustion, logging, all with fake providers | pytest |
| Ingestion | Each stage on recorded raw responses; merge rules; kept review edits; license and media safety rules | pytest with recorded fixtures |
| Publishing | Failure injected at each store; rollback; second city keeps the first | pytest on real Postgres, Qdrant and MinIO |
| Solver | Input guards; feasible plans on sample briefs; constraints respected; statuses; repeatable output | pytest |
| Validator | Catches every planted violation at the right place | Hypothesis |
| Solver properties | Every plan passes the validator; metamorphic checks only where their assumptions hold | Hypothesis |
| Graph | Each node alone; full graph with a fake LLM; pause and resume; restart recovery; story fallback | pytest |
| API | Endpoints with a test database, test collections and test buckets | pytest + FastAPI TestClient |
| Web | Form validation, linked selection, labels, route guards, error states | Vitest + Testing Library |
| Network requests | No undeclared external request while using every screen | Static check + Playwright interception |
| End to end | Sign in → plan → explore → revise → approve → reopen | Playwright |
| Hotel choice and fares | Per-hotel solve picks the best total; nights and rooms; fares match the tariff formula; the day pass is the cheaper of tickets and pass per day | pytest |
| TravelPlanner | Official validation scorer on our submission files | Official scorer in `roamate-tp`, manual workflow |
| Quality over time | Intake accuracy, recall@50, violation rate, persona pass rate, latency, cost, on development and held-out sets separately | `evals/` + Lab → Evals |

**CI tiers:** fast checks (ruff, mypy, ESLint, `tsc --noEmit`, unit tests, gitleaks, OpenAPI type drift, `build_roadmap.py --check`), then integration tests against Postgres, Qdrant and MinIO service containers with pinned images, migrations on a clean database, and the fixture Playwright flow. CI uses fake model providers, so it never needs API keys or a GPU. Real-model evaluations run in a separate, manually started workflow with a fixed budget.

### Reserved regression cases

From review 1 (its Appendix C). Each must pass by the step shown, and stays in the suite after.

| # | Case | First passes in |
| --- | --- | --- |
| 1 | Over-budget hotel or negative remaining budget: no solver call, no API failure | M7.11 |
| 2 | Zero remaining budget with free places: planned normally | M7.11 |
| 3 | Hotel nights differ from sightseeing days; lodging left out of a ground-only budget | M7.7 |
| 4 | Two rooms or several taxis needed: party cost correct | M7.7 |
| 5 | A must-do ranked below the search cut-off is still kept | M8.9 |
| 6 | A must-do closed on the only possible day: a proven conflict, explained | M8.4 |
| 7 | Unknown hours or accessibility never labeled checked | M7.13 |
| 8 | Split hours, a holiday override, an overnight window and a daylight-saving date | M7.6 |
| 9 | Lunch inside a full day; a short partial day without lunch, said so | M7.6 |
| 10 | Zero or one possible place, or only must-dos: no failure from option rules | M7.8 |
| 11 | Option solves finishing in different orders give the same comparison | M9.7 |
| 12 | More budget never makes a plan impossible; no claim that it raises the score | M12.4 |
| 13 | Timeout without a plan versus a proven conflict: different results | M7.9 |
| 14 | A cheaper, slower mode needed for the budget; a walking limit stricter than the profile's | M7.12 |
| 15 | Day pass charged once per day; return leg and walks to stations included | M7.12 |
| 16 | Unreachable pair, a route crossing the city edge, a stale matrix version | M7.2 |
| 17 | Publish failing after each store's write, then recovery | M6.10 |
| 18 | Publishing a second city keeps the first city's data and routes | M6.9 |
| 19 | Embedding prefix, size or revision mismatch, and collection rollback | M8.9 |
| 20 | Nested fallback, repair and rate limits stop at the job budget | M4.9 |
| 21 | Missing reranker, model, router or weather: honest capability and partial results | M1.6, M10.14 |
| 22 | Story failure leaves a usable plan; invented ids or facts rejected | M9.11 |
| 23 | Worker or API killed, expired lease, duplicate resume, repeated effect, duplicate save | M9.14 |
| 24 | Two users try to read, revise, approve or resume across ownership | M2.7, M11.8 |
| 25 | Two revisions at once; approving an old versus a new version | M11.9 |
| 26 | Media redirect to a private address, oversized image, wrong type, missing license | M5.10 |
| 27 | A CDN font or tile request fails the check; a booking link passes | M1.9 |
| 28 | PMTiles 206, 416 and ETag behavior through the real serving path | M6.6 |
| 29 | Cold and warm timings under a stated load, with RagBot latency recorded | M12.5 |
| 30 | Mobile sign-out or account switch with saved trips and an expired session | M14.6 |

---

## 15. Risks and open questions

| Item | Handling |
| --- | --- |
| Free-tier limits: daily caps, rate limits and models that change or disappear | Configurable chain, cool-down, job budgets, local vLLM as fallback capacity, per-provider usage shown in the Lab |
| Free tiers are not launch rights | Separate development and launch configurations; the launch file needs the M0.17 rights, retention and cost record |
| Free models vary in JSON quality | Validation, one repair, a meaning check; fallback on invalid output; eval results recorded per provider |
| Some free tiers may log prompts or use them for training | Send only what a step needs; no emails, names or passwords in prompts; per-provider data policy in M0.17 |
| Shared services with RagBot | Never stopped or reconfigured; separate roles, collections, buckets and Compose names; request caps; a lab TEI for experiments; a RagBot load check before Beta |
| Qdrant separation is by name only during development | Accepted development boundary; collection-scoped keys or a dedicated instance before Beta |
| GPU memory shared by vLLM and TEI models | The lab TEI starts only when memory allows; prefer smaller models if recall is similar |
| Open data has gaps in hours and prices | Hours states, strict mode by default, review screen highlights gaps; unknown values shown as `Unknown`, never guessed silently |
| No licensed ratings at first | Ratings nullable; quality uses a neutral prior; popularity and iconic carry the signal |
| Embedding model licenses | Jina v5 is non-commercial (CC BY-NC 4.0); EmbeddingGemma-2 and Qwen3-Embedding are Apache 2.0. Fine for development; a licensed model is a launch gate |
| Weather data rights | Open-Meteo's free tier is non-commercial; launch needs a subscription or self-hosting |
| MinIO's open-source project is archived and gets no updates | Accepted risk, reviewed before Beta; plain S3 code via boto3; a switch (SeaweedFS first) must pass the storage tests |
| A native solver crash or a runaway solve | Input guards, child process with a hard time limit, process cap |
| Transport policies may miss a better mixed-mode plan | Labeled as a simplification; joint per-leg choice is a later option if the gap shows up in evaluations |
| Scope creep into social features | Social and booking stay in "Later" |
| Hotel prices are estimates until a booking provider is connected | Labeled `Estimated` everywhere; the budget view shows the hotel line as an estimate |
| Taxi tariffs change | Stored with source link, version and valid dates; the admin updates them; fares shown as a range |
| Routing service is one more service to run | Built from the same extract as the catalog; versioned with a smoke test before switching; if it is down, the planner falls back to distance estimates labeled `Estimated` |
| The research track pulls time from the product | Starts only after Web Alpha and never delays Beta; the rules check comes first; the claim is fixed in R1 before experiments; at most one test-set submission, only if allowed |
