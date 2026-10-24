# Roamate implementation plan

**Version:** 2.2 (approved) · 24 October 2026
**Builds on:** `Roamate_Product_Vision_and_Business_Review_Brief.md` (18 Oct 2026), `pre-build-decisions.md` and `solver-retrieval-evaluation.md` (20 Oct 2026), the runnable `solver_example.py`, and hooman's 11 changes and follow-up of 24 Oct 2026.
**Companion files:** [implementation-steps.md](implementation-steps.md) (every step title as a checklist) and the visual roadmap.

---

## 1. What we are building first

The first version is a **web app** with real user accounts. A signed-in user can:

1. Enter a trip, either through a form or by describing it in free text: city, dates, travelers, budget, interests, pace, must-do places, walking limit.
2. Get up to three checked scenarios (**Budget**, **Balanced**, **Comfort**) built by a solver and verified by an independent validator.
3. Explore the chosen plan in four linked views: **Story**, **Timeline**, **Map**, **Budget**.
4. Ask for one kind of change ("less walking on day 2", "keep this museum", "slower afternoon"), see what changed, and approve a version.
5. Sign out, sign back in, and find the saved trip with its version history.

An **admin** user also gets:

- **Cities**: add a new city, watch the automatic data collection, review the places it found, and publish the city.
- **Lab**: try each part of the system on its own (models, search, solver, validator, AI intake, graph runs, evaluations).

The **mobile app** comes after the web app works and has been tested. All trip logic lives in the backend, so the mobile app is a second screen layer on the same API.

### Success test for the web version

The brief's demo scenario, run in a browser: a user signs in, enters a 3-day trip for two with a ground budget, receives checked scenarios with real images, explores the map and costs, asks for less walking on day 2, approves the revision, signs out, signs in again and reopens it. Every number on screen comes from the solver or the budget calculator, and the validator reports zero violations. An admin can add a second city through the Cities screen without writing code.

---

## 2. What changed in version 2

| # | Change requested | Where it shows up in this plan |
| --- | --- | --- |
| 1 | PostgreSQL for relational data, Qdrant for vectors, MinIO for objects | §4 infrastructure, §7 data design. pgvector is no longer used |
| 2 | LangGraph from the start | §10. The planning workflow is a LangGraph graph from its first version (M9) |
| 3 | Ready database images, as in RagBot | §4. Roamate connects to the services already running for RagBot, with its own database, collections and buckets |
| 4 | Every step approved before implementation | §13. M0 is a full design phase; nothing is coded until its design is approved, and each step gets a go-ahead |
| 5 | Users and login from the start | M2. Email and password accounts with user and admin roles |
| 6 | Free-tier API keys or local vLLM, with fallback | §8. One model gateway; free-tier API models first, local vLLM last, order set in one line; embeddings via TEI |
| 7 | A stage to collect cities and places, with easy semi-automatic ingestion | §9, M5 and M6. A staged city pipeline with a review queue and an auto-approve mode |
| 8 | Conda environment named `roamate` | §5. `environment.yml` replaces uv |
| 9 | Embedding model to be chosen | §8. A measured comparison of candidate models in M8 |
| 10 | All frontend files local, no internet needed for them | §11. Bundled packages and fonts, local map tiles, images served from our own object storage, and a build check |
| 11 | Work on `main` for the early phases | §13. Direct commits to `main` until Web Alpha, then branches and pull requests |

---

## 3. Keeping it simple

We start with the smallest version of each piece and add a heavier tool only when a real need appears.

| Area | Start with | Add later, only when needed |
| --- | --- | --- |
| Background work | A `planning_job` table; the API runs the graph as an asyncio background task; the web app polls the job every second | Redis + Celery or a separate worker process, if measurements in M12 show we need it |
| Live progress | Polling `GET /jobs/{id}` | Server-Sent Events, if polling feels laggy |
| Geography | Distances computed in Python (haversine × detour factor) | PostGIS, if spatial queries get slow |
| Travel times | Estimates by mode from distance, labeled "estimated" | A routing engine (local OSRM/Valhalla or an API) behind an adapter |
| Itinerary storage | The whole itinerary as JSON inside a trip version row | Normalized tables, only if we need to query inside itineraries |
| LLM access | Our own small gateway over OpenAI-compatible endpoints | A routing library, only if our gateway stops being enough |
| Travel profile | Defaults stored on the user | A separate profile model with history |

Code rules that keep the system understandable:

- **LLMs propose structured data; code checks it; only code writes trip state.** Every LLM output is a Pydantic model.
- **Every number the user sees comes from the solver or the budget calculator,** never from model text.
- **Trip versions are immutable.** A revision creates a new version with a pointer to its parent.
- **Real media first.** Every image carries its kind (exact venue, area, generic city, AI decorative), license and author.
- **Never present estimated data as checked.** Every fact shows its source and age; LLM-estimated fields are labeled as estimates.

---

## 4. Infrastructure

Roamate reuses the services that already run on the server for RagBot. It does not share any data with RagBot: it gets its own database, collections and buckets.

| Service | Existing container | Roamate uses |
| --- | --- | --- |
| PostgreSQL | `postgres-server` | Database `roamate` with its own user `roamate` |
| Qdrant | `qdrant-server` (`qdrant/qdrant:v1.16.2`) | Collections prefixed `roamate_` |
| Object storage | `minio-server` | Buckets prefixed `roamate-` with their own access key (see below) |
| TEI embedding | `tei-embedding` (`text-embeddings-inference:cuda-1.9`, currently `jina-embeddings-v5-text-small-retrieval`) | Dense embeddings for places |
| TEI reranker | `tei-reranker` (currently `bge-reranker-v2-m3`) | Re-ranking search candidates |
| vLLM | `gemma4-vllm` (`vllm/vllm-openai`) | Local chat model, first in the fallback list |

All hosts, ports and credentials come from `.env`. For a fresh machine without these services, `infra/docker-compose.yml` starts the same images with the same names, so a new developer can run `docker compose -f infra/docker-compose.yml up -d` and get the same setup. The exact image tags are pinned there in M1.

### Object storage: MinIO, easy to replace

MinIO stopped publishing community Docker images and binaries in October 2025 and archived its open-source repository in 2026, so it no longer gets updates. The image already running on the server keeps working, and Roamate only needs simple features (put, get, list, delete objects), so we can start with it. Roamate's storage code talks plain S3 through `boto3`, so moving to another S3-compatible server means changing the endpoint and keys in `.env` and copying the buckets.

| Option | License | Fit for Roamate |
| --- | --- | --- |
| **SeaweedFS** | Apache 2.0 | Mature, actively released, runs on one machine (`weed server -s3`), good with many small files such as images and thumbnails. **Recommended if we switch.** |
| **RustFS** | Apache 2.0 | Closest to MinIO in feel and setup, single-node friendly, but young; fine for development, watch it before production |
| **Garage** | AGPL v3 | Light and simple, designed for several small servers; lacks bucket policies and versioning (we don't need them) |
| **Ceph RGW** | LGPL | Very complete, but heavy to run; only worth it if you already run Ceph |

**Decision (24 Oct 2026): stay with MinIO for now.** We revisit only if it causes problems; SeaweedFS is the first replacement to try.

---

## 5. Technology choices

| Layer | Choice | Why |
| --- | --- | --- |
| Environment | **Conda** env `roamate` from `environment.yml` (Python 3.12 and Node.js 22); Python packages listed in `backend/pyproject.toml` and installed with pip | One command to create the whole dev environment |
| API | **FastAPI** + Pydantic v2 | Typed models and automatic OpenAPI docs |
| Relational data | **PostgreSQL** via **SQLAlchemy 2** + **Alembic** migrations | Users, cities, places, trips, jobs, logs |
| Vector search | **Qdrant** with dense vectors (TEI) and sparse BM25 vectors, fused with Qdrant's query API | Hybrid semantic and keyword search in one query |
| Object storage | **MinIO** (decided), accessed through **boto3** so any S3-compatible server can replace it | Place images, city map tiles, raw ingestion data |
| Workflow | **LangGraph** with the Postgres checkpointer | Readable graph of steps, pauses for the user, resume after restart |
| LLM | Our **model gateway** over OpenAI-compatible APIs (9Router, OpenRouter, Gemini free tier, local vLLM) using the `openai` Python SDK | One interface, fallback order set in one line, every call logged |
| Embeddings and reranking | **TEI** `/embed` and `/rerank` | Already running; local and fast |
| Solver | **OR-Tools** routing solver (port of `solver_example.py`) | Already prototyped |
| Auth | Email + password, **argon2** hashes, server-side sessions in Postgres, httpOnly cookie | Simple, secure, no third-party service |
| Weather | **Open-Meteo**, cached | Free, no key; labeled forecast vs seasonal |
| Place data | **OpenStreetMap** (Overpass, Nominatim), **Wikidata**, **Wikipedia**, **Wikimedia Commons** | Open data we may store, with clear licenses |
| Web frontend | **React + TypeScript + Vite**, **React Router**, **TanStack Query**, **Tailwind CSS** | Plain single-page app; everything bundled locally |
| Web map | **MapLibre GL JS** with a local **PMTiles** map file per city | Works without an internet tile server |
| Fonts and icons | `@fontsource` packages and `lucide-react`, bundled | No font or icon CDN |
| API types in the web app | **openapi-typescript** generates `web/src/api/schema.ts` | Frontend always matches backend |
| Tests | **pytest** + **Hypothesis**, **Vitest** + Testing Library, **Playwright** | One tool per job |
| Code quality | **ruff**, **ESLint** + **Prettier** + `tsc`, **pre-commit** | Fast, standard |
| CI | **GitHub Actions** on every push to `main` (and on pull requests later) | Keeps `main` working |
| Mobile (M13+) | **Expo** (React Native) + Expo Router, same generated API types | Same language and data layer |

---

## 6. Repository layout

```
roamate/
├── environment.yml           conda env "roamate"
├── .env.example              every setting with a comment, no secrets
├── config/
│   └── models.yaml           LLM providers and their order, embedding and reranker settings
├── infra/
│   ├── docker-compose.yml    Postgres, Qdrant, object storage (and optional TEI/vLLM) for a fresh machine
│   └── setup/                scripts: create database, create collections, create buckets
├── backend/
│   ├── pyproject.toml
│   ├── app/
│   │   ├── main.py           creates the FastAPI app, includes routers
│   │   ├── config.py         settings from environment variables
│   │   ├── db.py             Postgres engine and session
│   │   ├── vectors.py        Qdrant client and collection helpers
│   │   ├── storage.py        S3 client (boto3) and object helpers
│   │   ├── models/           SQLAlchemy tables, one file per area
│   │   ├── schemas/          Pydantic models: brief, place, itinerary, scenario, budget, validation, delta
│   │   ├── auth/             passwords, sessions, dependencies (current_user, require_admin)
│   │   ├── api/              routers: auth, cities, places, trips, jobs, admin, lab
│   │   ├── llm/              gateway.py, providers.py, structured.py, embeddings.py, reranker.py
│   │   ├── ingestion/        discover.py, collect.py, merge.py, enrich.py, score.py, review.py, publish.py, tiles.py, pipeline.py
│   │   ├── catalog/          place queries, hybrid search, utility scoring
│   │   ├── planning/         travel.py, solver.py, scenarios.py, budget.py, validator.py, feasibility.py, diff.py
│   │   ├── workflow/         state.py, graph.py, nodes/, prompts/, runner.py
│   │   └── providers/        weather.py
│   ├── migrations/           Alembic
│   ├── scripts/              ingest_city.py, create_admin.py, run_evals.py
│   └── tests/
├── web/
│   └── src/
│       ├── api/              generated schema.ts + fetch client
│       ├── auth/             login, register, route guard
│       ├── pages/            Home, NewTrip, TripView, MyTrips, admin/Cities, admin/Review, lab/*
│       ├── components/
│       └── features/         trip-form, story, timeline, map, budget, revision
├── mobile/                   Expo app (from M13)
├── evals/                    intake cases, retrieval labels, personas, results/
└── docs/
    ├── plan/                 this plan and the step list
    ├── design/               approved design documents (M0)
    └── adr/                  short decision records
```

---

## 7. Data design (first draft, approved in M0)

These are drafts so the shape of the system is visible. Each one becomes a full design document in M0 (columns, types, indexes, examples) and is approved before any migration is written.

### PostgreSQL tables

| Table | Main columns | Purpose |
| --- | --- | --- |
| `app_user` | id, email (unique), password_hash, display_name, role (`user` / `admin`), default_preferences (JSON), created_at, last_login_at | Accounts |
| `user_session` | id, token_hash, user_id, created_at, expires_at, user_agent | Login sessions behind the cookie |
| `city` | id, slug, name, country, bbox, center_lat, center_lon, timezone, currency, status (`collecting` / `in_review` / `published`), tiles_object_key, published_at | One row per city |
| `ingest_run` | id, city_id, stage, status, mode (`auto` / `semi`), params (JSON), stats (JSON), error, started_by, started_at, finished_at | Tracks each pipeline run so it can resume |
| `place_candidate` | id, city_id, ingest_run_id, osm_id, wikidata_id, name, lat, lon, raw (JSON), proposed (JSON), field_sources (JSON), quality_score, status (`pending` / `approved` / `rejected` / `merged`), reviewed_by, reviewed_at | What the pipeline found, before review |
| `place` | id, city_id, candidate_id, name, category, lat, lon, description, interest_tags (JSON), visit_minutes, price_per_person, opening_hours (JSON by weekday), popularity, accessibility_notes, website_url, booking_url, osm_id, wikidata_id, field_sources (JSON), updated_at | Published places the planner may use |
| `media_asset` | id, place_id, city_id, kind (`exact_venue` / `area` / `generic_city` / `ai_decorative`), object_key, original_url, license, author, attribution_text, width, height | Images in object storage with their credits |
| `trip` | id, user_id, city_id, title, created_at, current_version_id, approved_version_id | A user's trip |
| `trip_version` | id, trip_id, parent_version_id, number, brief (JSON), scenarios (JSON), selected_scenario, story (JSON), change_summary, status (`draft` / `approved`), created_at | Immutable plan versions |
| `planning_job` | id, trip_id, user_id, kind (`plan` / `revise`), graph_thread_id, status (`running` / `waiting_for_user` / `done` / `failed`), events (JSON), result_version_id, error, timings (JSON), created_at, finished_at | What the web app polls |
| `llm_call` | id, job_id, node, provider, model, attempt, ok, error_kind, latency_ms, tokens_in, tokens_out, created_at | Which provider answered, failures, cost and speed |
| LangGraph checkpoint tables | managed by `langgraph-checkpoint-postgres` | Graph state for pause and resume |

### Qdrant collections

| Collection | Point | Vectors | Payload (filterable) |
| --- | --- | --- | --- |
| `roamate_places__<model-slug>` | One per published place, id = place id | `dense` from TEI, `sparse` BM25 | city_id, category, interest tags, price_per_person, visit_minutes, open weekdays, popularity |

The embedding model's name is part of the collection name. Switching models means creating a new collection, re-embedding (minutes for a few thousand places), and changing one setting.

### Object storage buckets

| Bucket | Object layout | Access |
| --- | --- | --- |
| `roamate-media` | `cities/{city_slug}/places/{place_id}/{asset_id}.{ext}` plus `…/{asset_id}_thumb.webp` | Served to the app through the backend |
| `roamate-tiles` | `cities/{city_slug}/basemap.pmtiles` | Served to the map through the backend |
| `roamate-raw` | `ingest/{run_id}/{stage}/{file}.json` | Private; raw API responses for repeatable runs |

### Domain data structures (Pydantic)

- **`TripBrief`**: city_id, start_date, end_date, travelers, budget (amount, currency, scope, covered categories), known_costs, interests (interest → weight), pace (`relaxed` / `normal` / `packed`), transport (walk, metro, taxi allowed), max_walk_minutes_per_day, day_start, day_end, hotel location, must_do, excluded, notes.
- **`Stop`**, **`DayPlan`**, **`Itinerary`**: ordered stops with arrive/depart times, travel from the previous stop (mode, minutes, walking, cost), lunch break, return time.
- **`Scenario`**: name, parameters used, itinerary, budget breakdown, metrics, skipped places with reasons, validation report.
- **`BudgetBreakdown`**: lines by category marked `quoted` / `estimated` / `unknown` / `excluded`, totals, currency, scope text.
- **`ValidationReport`**: named checks with pass/fail and details.
- **`ConstraintDelta`**: the structured form of a change request (e.g. day 2 walking cap 40 min, lock stop X, remove stop Y).
- **`ProgressEvent`**: step, message, time, optional partial result.

---

## 8. Model gateway (LLMs, embeddings, reranker)

All model calls go through `backend/app/llm/`. Nothing else in the code talks to a model provider directly.

### Chat models with fallback

`config/models.yaml` defines each provider once, and a single line chooses the order. Free-tier API models, which are usually stronger than our local model, come first; the local vLLM model is the last safety net. Keys stay in `.env`; the YAML only names the variable.

```yaml
# Order to try. Change this line (or set LLM_CHAIN in .env) to reorder; nothing else changes.
chain: [nineroute, openrouter-free, gemini-free, local-gemma]

providers:
  nineroute:                    # 9Router running on our server; does its own fallback across its free providers
    base_url: ${NINEROUTER_BASE_URL}        # e.g. http://localhost:20128/v1
    model: ${NINEROUTER_MODEL}              # a 9Router combo name
    api_key_env: NINEROUTER_API_KEY
  openrouter-free:              # OpenRouter; tries the listed free models in order on its side
    base_url: https://openrouter.ai/api/v1
    models: [<nemotron :free id>, <deepseek :free id>]
    api_key_env: OPENROUTER_API_KEY
  gemini-free:                  # Gemini free tier through its OpenAI-compatible endpoint
    base_url: https://generativelanguage.googleapis.com/v1beta/openai/
    model: <gemini flash model id>
    api_key_env: GEMINI_API_KEY
  local-gemma:                  # vLLM on our GPU: always available, private, no quota
    base_url: ${VLLM_BASE_URL}
    model: /app/model
```

Which services and models we actually use is left open on purpose: each one is a config entry, and we add, remove or reorder them as we test them. Exact model ids are filled in when a provider is first set up, since free model lists change often.

How a call works:

1. `gateway.structured(prompt, OutputModel)` tries the first provider in `chain`.
2. It moves to the next provider on a connection error, a timeout, HTTP 429 or 5xx, or an answer that is still invalid JSON for `OutputModel` after one repair retry.
3. A provider that returned 429 is skipped for a cool-down period (e.g. 60 seconds) so we don't hammer it.
4. Every attempt is written to `llm_call` with provider, the model that actually answered, latency, tokens and error type, and the Lab shows it.
5. If every provider fails, the job stops with a clear message instead of making something up.

**Two levels of fallback.** OpenRouter (its `models` list) and 9Router (its combos) already fall back between models inside their own service. Our gateway adds the outer level: across services, to the local model, and on answers that are not valid for our schema, which a router cannot judge. One rule: OpenRouter's list contains only `:free` model ids, because if it falls back to a paid model it bills that model.

All these services expose the OpenAI-compatible chat API, so one client class covers them; each entry differs only in URL, model(s) and key. Tests use a fake provider that can be told to fail, time out or return bad JSON.

**9Router** is open-source (MIT) software that we run ourselves (`npm install -g 9router`, local server on port 20128). It is deployed as one more service next to vLLM and TEI.

### Embeddings and reranking

- `embeddings.py` calls TEI `/embed` with the model's query and document prefixes, and records the model name with every vector written.
- `reranker.py` calls TEI `/rerank` (currently `bge-reranker-v2-m3`) to reorder the top search candidates.
- **Choosing the embedding model (M8):** we label 20–30 trip briefs with the places a good planner would consider, then measure recall@50 for each candidate on our own city data, and pick by recall, GPU memory and license.

| Candidate | Size | Vector size | Context | License | Notes |
| --- | --- | --- | --- | --- | --- |
| `jinaai/jina-embeddings-v5-text-small-retrieval` | 677M | 1024 (can be cut to 512, 256, …) | 32k | CC BY-NC 4.0: non-commercial; commercial use needs a license from Jina | Already running in TEI for RagBot; prefixes `Query: ` / `Document: ` |
| `google/embeddinggemma-2` | 270M text backbone (740M with image and audio encoders) | 768 (can be cut to 512, 256, 128) | 8k | Apache 2.0 | Prefixes `task: search result \| query: …` / `title: none \| text: …`; must run in bfloat16, not float16; TEI support to be confirmed in M0 |
| `Qwen/Qwen3-Embedding` (0.6B, 4B, 8B) | 0.6B to 8B | up to 4096 | 32k | Apache 2.0 | 8B needs about 16 GB of GPU memory next to vLLM; test 0.6B first |

Fine for development with any of them. If Roamate becomes a commercial product, the Jina model needs a paid license or a switch to one of the Apache 2.0 models.

---

## 9. City data pipeline

Adding a city is one command or one button: `python -m scripts.ingest_city "Lisbon, Portugal" --mode semi`, or **Admin → Cities → Add city**. The pipeline runs as stages. Each stage stores its output, can be re-run on its own, and records progress in `ingest_run`.

| Stage | What it does | Output |
| --- | --- | --- |
| 1. Discover | Look up the city in Nominatim and Wikidata: boundary, bounding box, center, timezone, currency | `city` row (status `collecting`) |
| 2. Collect | Query Overpass for tourist categories (museums, monuments, viewpoints, parks, markets, galleries, historic sites, food spots) and Wikidata for notable items inside the boundary | Raw responses in `roamate-raw`, rows in `place_candidate` |
| 3. Merge | Join OSM and Wikidata records (by Wikidata tag, then name and distance); remove duplicates | One candidate per real place |
| 4. Enrich | Wikipedia summary, Wikimedia Commons images with license and author (downloaded to `roamate-media`), parsed OSM opening hours, website. The LLM proposes interest tags, typical visit time and price band, each marked `estimated_by_llm` | Filled `proposed` fields with sources |
| 5. Score | Popularity (Wikipedia language links, page views) and completeness (required fields present) | `quality_score` per candidate |
| 6. Review | **Semi mode:** the admin review screen lists candidates by score with missing fields highlighted; approve in bulk, edit, reject. **Auto mode:** approve every candidate above a score threshold that has all required fields | Approved candidates |
| 7. Publish | Copy approved candidates into `place` and `media_asset`, embed and upsert into Qdrant, extract the city's map file (PMTiles) into `roamate-tiles`, set the city to `published` | A city the planner can use |

Rules:

- Respect the public services' usage policies (Nominatim at most one request per second, polite Overpass use) and cache raw responses so re-runs don't call them again.
- Only store media whose license allows it, and always keep the author and license for display.
- Required fields for a place to be usable by the planner: coordinates, category, visit time, at least one interest tag, and opening hours or an explicit "hours unknown".

The first city is chosen in M0 (Lisbon is the default). A second city is added in M6 to prove that adding a city needs no code changes.

---

## 10. Planning workflow (LangGraph)

The whole planning flow is one LangGraph graph from its first version.

```
                ┌──────────────┐
 free text ───▶ │ intake (LLM) │──missing info──▶ [pause: clarify] ─┐
                └──────┬───────┘                                    │
 form ─────────────────┤◀──────────────────────────────────────────┘
                       ▼
               [pause: confirm brief]
                       ▼
               feasibility precheck ──conflict──▶ explain choices (end)
                       ▼
               retrieve candidates (Qdrant hybrid + rerank + utility)
                       ▼
               live context (weather)
                       ▼
       ┌───────────────┼───────────────┐
   solve Budget   solve Balanced   solve Comfort      (parallel)
       └───────────────┼───────────────┘
                       ▼
                   validate ──violations, tries < 2──▶ repair ──▶ solve
                       ▼
                   budget breakdown
                       ▼
                   curate "why this fits you" (LLM)
                       ▼
                   write story chapters (LLM, cannot change the schedule)
                       ▼
                   save trip version
```

- **State** (`workflow/state.py`): user and trip ids, raw request, brief, open questions, confirmed flag, candidates, scenarios, validation results, repair attempts, story, events, errors.
- **Pauses** use LangGraph's `interrupt()`. The job's status becomes `waiting_for_user`, the web app shows the question or the brief summary, and `POST /jobs/{id}/resume` continues the same graph thread.
- **Checkpoints** in Postgres mean a backend restart doesn't lose a run.
- **Revision** is a second, smaller graph: parse the change (LLM → `ConstraintDelta`) → re-solve with locked stops → validate → diff → save a new version.
- **Progress events** are written by each node into `planning_job.events`, which the web app polls.

### Solver (port of `solver_example.py`)

- Prize-collecting Team Orienteering Problem with Time Windows on OR-Tools routing: each day is a vehicle starting and ending at the hotel, each place is optional and dropping it costs its utility, must-dos are mandatory.
- Constraints: opening hours by weekday, day start/end, a 60-minute lunch break, hard budget, walking cap per day, stops per day (pace), balanced days.
- Scenarios: three parameter sets plus a diversity rule (each differs by at least two places). If three meaningfully different plans do not exist, the app says so.
- Tests use a fixed solution limit instead of a time limit so results repeat.

### Validator and infeasibility

The validator is separate code that recomputes timings and costs from the catalog and checks opening hours, day window, lunch, duplicates, must-dos, budget, walking cap, pace and time continuity. Hypothesis tests plant violations and the validator must catch every one. The feasibility precheck explains common conflicts before solving and offers concrete choices; hard limits are never relaxed without the user agreeing.

---

## 11. The web app

### Screens

| Screen | Who | What it does |
| --- | --- | --- |
| Sign up, sign in | Everyone | Email and password |
| Home | User | "Plan a trip", "My trips", an example trip |
| New trip | User | Free-text box that fills the form, then the step form; confirm summary |
| Clarify / confirm | User | Answers the graph's questions; confirms the brief |
| Planning | User | Real progress steps from the job |
| Trip view | User | Scenario switcher and four tabs: Story, Timeline, Map, Budget; linked selection; place drawer with reasons, duration, price and source, media credit, booking link |
| Revise | User | Change box, quick chips, stop locks, "what changed" diff, approve |
| My trips | User | Saved trips with version history |
| Cities | Admin | Add a city, run progress per stage, publish |
| Review | Admin | Candidate queue: bulk approve, edit, reject |
| Lab | Admin | Models, Search, Solver, Validator, Intake, Runs, Evals |

Trust labels throughout: `Checked`, `Estimated`, `Unknown`, and image labels (`This venue`, `This area`, `City photo`, `AI illustration`).

### Everything served locally

- All JavaScript and CSS packages are bundled by Vite into `web/dist`. No CDN links.
- Fonts come from `@fontsource` packages and icons from `lucide-react`, both bundled.
- The map uses MapLibre GL JS with the city's PMTiles file, plus the map style, glyphs and sprites stored in the repository, all served by our backend.
- Place images are served from object storage through the backend.
- A build check fails CI if the built app references any external URL.

The backend itself still needs the internet for API-based models, weather and city ingestion. With the local vLLM model and cached weather, a trip can be planned for an already published city with no internet at all.

---

## 12. Milestones

Sizes are rough guesses for one developer working with AI coding help: **S** ≈ under a week, **M** ≈ 1–2 weeks, **L** ≈ 2–3 weeks. They are not commitments.

### Phase 1 — Design and approval

**M0. Design and approval (M)**
Write and approve every design before coding: infrastructure and environment, Postgres schema, Qdrant collections, object storage layout, domain data structures, auth, model gateway, city pipeline, LangGraph graph, API contract, web screens, launch city and evaluation cases. Each design is a file in `docs/design/`.
*You can test:* read and approve each design; nothing is coded yet.

### Phase 2 — Foundation and accounts

**M1. Foundation (S)**
Conda environment, backend and web skeletons, connections and health checks for Postgres, Qdrant, object storage, TEI, vLLM and 9Router, setup scripts for Roamate's database, collections and buckets, local-only frontend assets, lint, tests and CI.
*You can test:* `conda activate roamate`, start the backend and web app, and see a health page with every service green.

**M2. Accounts and login (S)**
User and session tables, register, sign in, sign out, current user, user and admin roles, an admin creation command, sign-in pages and protected routes in the web app.
*You can test:* create an account, sign in, sign out; an admin sees the Admin menu and a normal user does not.

**M3. Core data layer (M)**
Migrations for all remaining tables, Pydantic domain models, Qdrant collection and S3 bucket helpers, generated TypeScript types, test fixtures.
*You can test:* run migrations and setup scripts on an empty database and see every table, collection and bucket created; tests create and read each kind of record.

### Phase 3 — Models and city data

**M4. Model gateway (M)**
Providers from `config/models.yaml`, ordered fallback with cool-down, structured output with validation and repair, `llm_call` logging, TEI embedding and reranker clients, Lab → Models page.
*You can test:* Lab → Models: send a test prompt, stop vLLM, and watch the next provider answer, with each attempt listed.

**M5. City data pipeline (L)**
Discover, collect, merge, enrich, score, with resumable stages, raw data in object storage, images with licenses, LLM-estimated fields marked, and a command-line entry point.
*You can test:* run the ingest command for the launch city and inspect the candidates, their sources and images.

**M6. City review and publishing (L)**
Admin Cities and Review screens, auto-approve rules, publish to Postgres, Qdrant and object storage, local map tiles, the launch city reviewed and published, a second city added through the UI only.
*You can test:* Admin → Cities → Add city, follow the stages, approve places in Review, publish, and see the city's places on its local map.

### Phase 4 — Planning engine

**M7. Solver and scenarios (M)**
Utility scoring, travel estimates, OR-Tools model on catalog data, all constraints, three scenarios with the diversity rule, deterministic test mode, Lab → Solver page.
*You can test:* Lab → Solver: pick a city and a sample brief, change weights and caps, and compare Budget, Balanced and Comfort.

**M8. Validator, budget and search (M)**
Independent validator with Hypothesis tests, budget breakdown, feasibility precheck, Qdrant hybrid search with reranking feeding utility, retrieval label set, embedding model comparison, Lab → Validator and Lab → Search pages.
*You can test:* break an itinerary in Lab → Validator and see it caught; compare search methods and embedding models with measured recall in Lab → Search.

### Phase 5 — AI workflow and web app ("Web Alpha")

**M9. LangGraph planning workflow (L)**
Graph state and nodes for the form path, intake node with clarify pause, confirm pause, parallel scenarios, validate and repair loop, budget, curation and story nodes, Postgres checkpoints and resume, job runner and job API, weather provider, intake eval set, Lab → Intake and Lab → Runs pages.
*You can test:* start a plan through `/docs` or Lab → Runs, answer a clarification, restart the backend mid-run and see it resume.

**M10. Web app: plan, explore, save (L)**
App shell, new-trip form with free text, clarify and confirm screens, progress screen, trip view with Story, Timeline, Map and Budget, linked selection, place drawer, My trips, Playwright end-to-end test, Web Alpha check, tag `v0.1-alpha`.
*You can test:* the full flow in a browser: sign in, describe a trip, confirm, compare scenarios, read the story, check the map and costs, sign out and back in, reopen it.

### Phase 6 — Revise, evaluate, deploy ("Web Beta")

**M11. Revision and approval (M)**
Revision graph with `ConstraintDelta`, stop locks, "what changed" diff, version history, approve, outbound booking links that never mark anything as booked, end-to-end test.
*You can test:* "less walking on day 2" on a saved trip, see the diff, approve, and open the previous version.

**M12. Evaluation, hardening and deployment (L)**
Persona-based evaluation harness, graders, regression suite in CI, metamorphic solver tests, p50/p95 timings, provider quota and failure tracking, friendly errors, accessibility pass, a worker process or Celery only if measurements require it, deployment on the server next to the existing services, Lab → Evals page, a few testers.
*You can test:* the deployed web app from another computer; the Evals page shows violation rate, intake accuracy, recall and latency.

### Phase 7 — Mobile app

**M13. Mobile app core (L)**
Expo app with Expo Router, shared TypeScript code moved into `shared/`, sign-in, trip intake, progress, trip view tabs, map with the city's local tiles, revision and approval, tested in the Android emulator.
*You can test:* the brief's demo flow in the Android emulator against the same backend.

**M14. Mobile polish and tester release (M)**
Offline view of saved trips, accessibility and slow-network checks, app icon and splash, internal test builds with EAS (Android, then iOS).
*You can test:* install the test build on a real phone.

### Later (not planned in detail yet)

Password reset by email, private group planning (invite, vote, lock, approve), share links and "Make this trip mine", learned ranking from saves and skips, visit-duration prediction, local routing engine, booking integrations after separate validation.

---

## 13. How we work

### Approval before implementation

1. **M0 designs everything first.** Each design document in `docs/design/` (schemas, data structures, API, graph, pipeline, screens) is posted for review and changed until hooman approves it. Nothing is coded before its design is approved.
2. **Each step gets a go-ahead.** Before starting a step, Claude posts a short step brief: what will be built, which files change, how it will be tested, and any detail the design left open. Work starts after approval.
3. **Design changes during coding** go back to step 1 for the affected document; the code follows the approved document.

### Branches

- **Until Web Alpha (end of M10):** commits go directly to `main`, one commit or a few per step, each with tests passing. CI runs on every push.
- **From Web Alpha on:** `main` stays the working version. Each step is a branch (`m11-2-stop-locks`) and a pull request that is merged after review and green CI.

### Other rules

- Write the core pieces by hand first (solver model, validator, one graph node, the version schema), and use AI help for boilerplate, as the earlier decision record recommends.
- Secrets live only in `.env` (never committed). `.env.example` lists every setting.
- Definition of done for a milestone: its "You can test" item works in the running app, tests and CI are green, the README run steps still work, and the step checklist is ticked.

---

## 14. Testing strategy

| Layer | What we test | Tool |
| --- | --- | --- |
| Schemas | Valid and invalid briefs, money and date rules | pytest |
| Auth | Passwords hashed, sessions expire, roles enforced on every admin route | pytest |
| Model gateway | Fallback order, cool-down, bad-JSON repair, logging, all with fake providers | pytest |
| Ingestion | Each stage on recorded raw responses; merge rules; license rules | pytest with fixtures from `roamate-raw` |
| Solver | Feasible plans on sample briefs; constraints respected; repeatable output | pytest |
| Validator | Catches every planted violation | Hypothesis |
| Solver properties | Every plan passes the validator; metamorphic checks | Hypothesis |
| Graph | Each node alone; full graph with a fake LLM; pause and resume; restart recovery | pytest |
| API | Endpoints with a test database and test collections | pytest + FastAPI TestClient |
| Web | Form validation, linked selection, labels, route guards | Vitest + Testing Library |
| Local assets | Built app has no external URLs | CI build check |
| End to end | Sign in → plan → explore → revise → approve → reopen | Playwright |
| Quality over time | Intake accuracy, recall@50, violation rate, persona pass rate, latency, cost | `evals/` + Lab → Evals |

CI uses fake model providers, so it never needs API keys or a GPU. Real-model evaluations run in a separate, manually started workflow or on the server.

---

## 15. Risks and open questions

| Item | Handling |
| --- | --- |
| Free-tier limits: daily caps, rate limits and models that change or disappear | Configurable fallback chain, cool-down, local vLLM as the last safety net, per-provider usage shown in the Lab |
| Free models vary in JSON quality | Validation and repair retry; fallback on invalid output; eval results recorded per provider |
| Some free tiers may log prompts or use them for training | Send only what a step needs; no emails, names or passwords in prompts |
| Shared services with RagBot | Separate database, user, collections and buckets; setup scripts never touch anything without the `roamate` prefix |
| GPU memory shared by vLLM and TEI models | Measure before adding a large embedding model; prefer smaller models if recall is similar |
| Open data has gaps in hours and prices | Review screen highlights gaps; unknown values shown as `Unknown`, never guessed silently |
| Embedding model licenses | Jina v5 is non-commercial (CC BY-NC 4.0); EmbeddingGemma-2 and Qwen3-Embedding are Apache 2.0. Fine for development; revisit before any commercial launch |
| MinIO's open-source project is archived and gets no updates | Decided to stay with the running MinIO image; plain S3 code via boto3 keeps a later switch (SeaweedFS first) to a config change |
| Scope creep into social features | Social and booking stay in "Later" |
