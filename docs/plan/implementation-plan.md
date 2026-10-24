# Roamate implementation plan

**Date:** 24 October 2026
**Builds on:** `Roamate_Product_Vision_and_Business_Review_Brief.md` (18 Oct 2026), `pre-build-decisions.md` and `solver-retrieval-evaluation.md` (20 Oct 2026), and the runnable `solver_example.py`.
**Companion files:** [implementation-steps.md](implementation-steps.md) (every step title as a checklist) and the visual roadmap.

---

## 1. What we are building first

The first version is a **web app** that one person (a built-in demo user, no login) can use in a browser to:

1. Enter a trip: city, dates, travelers, budget, interests, pace, must-do places, walking limit.
2. Get up to three checked scenarios (**Budget**, **Balanced**, **Comfort**) built by a solver and verified by an independent validator.
3. Explore the chosen plan in four linked views: **Story**, **Timeline**, **Map**, **Budget**.
4. Ask for one kind of change ("less walking on day 2", "keep this museum", "slower afternoon"), see what changed, and approve a version.
5. Close the browser, come back, and find the saved trip with its version history.

Next to the traveler screens, the web app has a **Lab** section for us, the builders, where each part of the system can be tried on its own: browse the catalog, run the solver with custom weights, test search, test the AI intake, and read evaluation results. That is how we "use and test different aspects and features" without guessing.

The **mobile app** comes after the web app works and has been tested. Because all trip logic lives in the backend, the mobile app is a second screen layer on the same API, not a second product.

### Success test for the web version

The brief's demo scenario, run in a browser: a user enters a 3-day Lisbon trip for two with a ground budget, receives checked scenarios with real images, explores map and costs, asks for less walking on day 2, approves the revision, and reopens it after restarting the app. Every number on screen comes from the solver or the budget calculator, and the validator reports zero violations.

---

## 2. Keeping it simple

The earlier design documents describe the full target architecture. To keep the code understandable, we start with the smallest version of each piece and add the heavier tool only when a real need appears. Each addition is a planned step, not a surprise.

| Area | Start with | Add later, only when needed | Trigger to add it |
| --- | --- | --- | --- |
| Background work | A `planning_job` table and a FastAPI background task; the web app polls the job every second | Redis + Celery worker | Plans take long enough that API restarts lose runs, or we need several workers (M12) |
| Live progress | Polling `GET /jobs/{id}` | Server-Sent Events | Polling feels laggy in testing |
| AI orchestration | A plain Python function `plan_trip()` that calls steps in order | LangGraph graph with checkpoints | Once we have a clarification pause, a repair loop and revisions (M10) |
| Geography | Distances computed in Python (haversine × detour factor), one city of ~150–300 places | PostGIS | More cities or radius queries become slow |
| Travel times | Estimates by mode from distance, labeled "estimated" | A routing provider (OpenRouteService) behind an adapter | M9, once the core works |
| Search | SQL filters + interest-tag scoring | pgvector + full-text hybrid search | M8 |
| Itinerary storage | The whole itinerary as JSON inside a trip version row | Normalized tables | Only if we need to query inside itineraries |
| Identity | One demo user, no login | Accounts and auth | Public testing beyond a few people (later phase) |
| Frontend shared code | Types generated from the API into the web app | A small `shared/` package used by web and mobile | Start of mobile (M13) |
| Monitoring | Structured logs + a run log table with timings and token cost | Tracing tool (Langfuse/OpenTelemetry) | M12 |

Code rules we keep from the design decisions, because they make the system understandable rather than more complex:

- **LLMs propose structured data; code checks it; only code writes trip state.** Every LLM output is a Pydantic model.
- **Every number the user sees comes from the solver or the budget calculator,** never from model text.
- **Trip versions are immutable.** A revision creates a new version with a pointer to its parent.
- **Real media first.** Every image carries its kind (exact venue, area, generic city, AI decorative), license and author.
- **Never present demo or estimated data as live or checked.** Every fact shows its source and age.

---

## 3. Technology choices

| Layer | Choice | Why |
| --- | --- | --- |
| Backend language | Python 3.12, managed with **uv** | OR-Tools, LangGraph and ML libraries are Python-first |
| API | **FastAPI** + Pydantic v2 | Typed request/response models and automatic OpenAPI docs |
| Database | **PostgreSQL 16** with the **pgvector** extension, via **SQLAlchemy 2** + **Alembic** migrations | One database for trips, catalog and (later) embeddings |
| Solver | **OR-Tools** routing solver (port of `solver_example.py`) | Already prototyped; handles time windows, optional stops, caps |
| LLM | **Claude** through the Anthropic SDK, behind one `ai/llm.py` adapter; model name in config | Structured outputs; one place to swap or mock the model |
| Embeddings (M8) | A small local **sentence-transformers** model (e.g. `bge-small-en`, 384 dims) | No API key, free, deterministic |
| Weather | **Open-Meteo** (no key) | Forecast for near dates, labeled seasonal climate data for far dates |
| Place data | **OpenStreetMap** (Overpass), **Wikidata**, **Wikimedia Commons** images, then hand review | Storable open data with clear licenses |
| Web frontend | **React + TypeScript + Vite**, **React Router**, **TanStack Query**, **Tailwind CSS** | Plain single-page app; no server rendering needed; widely understood |
| Web map | **Leaflet** (react-leaflet) with OpenStreetMap tiles and attribution | Simplest map library that works well |
| API types in the web app | **openapi-typescript** generates `web/src/api/schema.ts` from FastAPI's OpenAPI | Backend and frontend never disagree about shapes |
| Tests | **pytest** + **Hypothesis** (backend), **Vitest** + Testing Library (web), **Playwright** (end-to-end in a browser) | One tool per job |
| Code quality | **ruff** (Python lint/format), **ESLint** + **Prettier** + `tsc` (web), **pre-commit** | Fast, standard |
| CI | **GitHub Actions**: lint + tests on every pull request | Keeps `main` always working |
| Local run | **Docker Compose** for Postgres; backend and web run with `uv run` and `npm run dev`. A second Compose profile runs everything | Fast reload while developing, one command for a full run |
| Mobile (M13+) | **Expo** (React Native) + Expo Router, react-native-maps, same generated API types | Same language and data layer as the web app |

**Launch city:** Lisbon is the default (compact center, many free and paid sights, good open data). Changing the city later means running the same ingestion pipeline on another city.

---

## 4. Repository layout

```
roamate/
├── backend/                  FastAPI app (Python)
│   ├── app/
│   │   ├── main.py           creates the FastAPI app, includes routers
│   │   ├── config.py         settings from environment variables
│   │   ├── db.py             database engine and session
│   │   ├── models.py         SQLAlchemy tables
│   │   ├── schemas/          Pydantic models: brief, place, itinerary, scenario, validation
│   │   ├── api/              one router file per area: trips, jobs, catalog, intake, lab
│   │   ├── catalog/          place queries, search, utility scoring
│   │   ├── planning/         travel.py, solver.py, scenarios.py, budget.py, validator.py, feasibility.py, pipeline.py
│   │   ├── ai/               llm.py, intake.py, curation.py, story.py, revision.py, (M10) graph.py, prompts/
│   │   └── providers/        weather.py, routing.py, media.py (each with a live and a demo version)
│   ├── migrations/           Alembic
│   ├── scripts/              ingest_city.py, load_catalog.py, seed_demo.py, run_evals.py
│   └── tests/                unit/, integration/, fixtures/
├── web/                      React + Vite app
│   └── src/
│       ├── api/              generated schema.ts + small fetch client
│       ├── pages/            Home, NewTrip, TripView, MyTrips, lab/*
│       ├── components/       shared UI pieces
│       └── features/         trip-form, story, timeline, map, budget, revision
├── mobile/                   Expo app (from M13)
├── data/cities/lisbon/       places.yaml (reviewed catalog), media.yaml, raw/ (ingestion output)
├── evals/                    intake cases, retrieval labels, personas, results/
├── docs/
│   ├── plan/                 this plan, the step list
│   └── adr/                  short architecture decision records
├── docker-compose.yml
├── .env.example
└── .github/workflows/ci.yml
```

Each backend folder has one job, and the names say what it is. A new contributor should be able to find "where is the budget calculated?" in one guess: `planning/budget.py`.

---

## 5. Core data model

### Database tables

| Table | Key columns | Notes |
| --- | --- | --- |
| `city` | id, name, country, timezone, currency, center_lat, center_lon | One row (Lisbon) at first |
| `place` | id, city_id, name, category, lat, lon, description, interest_tags (JSON: interest → 0..1), visit_minutes, price_per_person, opening_hours (JSON by weekday), curated_score (1–5), accessibility_notes, website_url, booking_url, osm_id, wikidata_id, field_sources (JSON: field → {source, fetched_at, confidence}) | `embedding` and `search_text` columns added in M8 |
| `media_asset` | id, place_id (nullable), city_id, kind (`exact_venue` / `area` / `generic_city` / `ai_decorative`), url, license, author, source_url, storable, attribution_text | Enforces the real-media-first rule |
| `trip` | id, owner (demo user), title, created_at, current_version_id, approved_version_id | |
| `trip_version` | id, trip_id, parent_version_id, number, brief (JSON), scenarios (JSON), selected_scenario, change_summary, story (JSON), created_at, status (`draft` / `approved`) | Immutable after creation, except status |
| `planning_job` | id, trip_id, kind (`plan` / `revise`), status, events (JSON list), result_version_id, error, timings (JSON), created_at, finished_at | The web app polls this |
| `run_log` | id, job_id, step, duration_ms, llm_tokens_in/out, cost_estimate, ok, details | Added in M7, used for cost and latency reports |

### Main Pydantic schemas (`backend/app/schemas/`)

- **`TripBrief`**: city_id, start_date, end_date, travelers, budget (amount, currency, scope `party`, covers e.g. `[admissions, local_transport]`), known_costs (e.g. hotel already paid), interests (interest → weight), pace (`relaxed` / `normal` / `packed`), transport (walk / metro / taxi allowed), max_walk_minutes_per_day, day_start, day_end, hotel location, must_do place ids, excluded place ids, notes.
- **`Stop`**: place_id, day, arrive, depart, travel_from_previous (mode, minutes, walk_minutes, cost), why (filled by curation).
- **`Itinerary`**: days → list of stops + lunch break + return time.
- **`Scenario`**: name, parameters used, itinerary, budget breakdown, metrics (utility, walking, travel time, spend), skipped places with reasons, validation report.
- **`BudgetBreakdown`**: lines by category, each marked `quoted` / `estimated` / `unknown` / `excluded`, totals, currency, scope text.
- **`ValidationReport`**: list of checks (name, passed, details), violation count.
- **`ProgressEvent`**: step, message, at, partial result (optional).

The TypeScript types for the web (and later mobile) app are generated from these, so the frontend always matches.

---

## 6. API (first version)

| Method and path | Purpose | Milestone |
| --- | --- | --- |
| `GET /health` | Liveness check | M0 |
| `GET /cities`, `GET /cities/{id}/places` | Catalog browse with filters | M2 |
| `GET /places/{id}` | Place details with media and sources | M2 |
| `POST /trips` | Create a trip from a `TripBrief`, start a planning job | M5 |
| `GET /trips`, `GET /trips/{id}` | My trips, one trip with current version | M5 |
| `GET /trips/{id}/versions`, `GET /trips/{id}/versions/{n}` | Version history | M5 |
| `GET /jobs/{id}` | Job status, progress events, result | M5 |
| `POST /intake/parse` | Free text → draft `TripBrief` + clarification questions | M7 |
| `POST /trips/{id}/revisions` | Request a change, start a revise job | M11 |
| `POST /trips/{id}/versions/{n}/approve` | Approve a version | M11 |
| `POST /lab/solve`, `POST /lab/validate`, `POST /lab/search` | Builder tools: run one part synchronously and show its raw output | M4, M8 |

FastAPI serves interactive docs at `/docs`, which is the quickest way to try any endpoint.

---

## 7. How a plan is produced

The same pipeline is used by the web app and the Lab. In the first version it is one readable function:

```python
def plan_trip(brief: TripBrief, job: JobReporter) -> TripVersion:
    job.event("checking_places")
    candidates = catalog.find_candidates(brief)            # filters + scoring (M2), hybrid search (M8)
    problems = feasibility.precheck(brief, candidates)     # e.g. must-do admissions exceed budget
    if problems:
        return job.fail_with_choices(problems)

    job.event("estimating_routes")
    travel = planning.travel.matrix(candidates, brief)     # estimates (M3), routing provider (M9)

    job.event("comparing_options")
    scenarios = planning.scenarios.build_all(brief, candidates, travel)  # Budget / Balanced / Comfort
    for s in scenarios:
        s.budget = planning.budget.breakdown(brief, s.itinerary)
        s.validation = planning.validator.check(brief, s.itinerary, candidates)

    job.event("preparing_story")                           # M9
    story = ai.story.write(brief, scenarios)               # cannot change the schedule

    return trips.save_new_version(brief, scenarios, story)
```

In M10 this function becomes a LangGraph graph with the same steps as nodes, so we gain checkpoints, a pause for "confirm your brief", and a repair loop, without changing what each step does.

### Solver (port of `solver_example.py`)

- Model: prize-collecting Team Orienteering Problem with Time Windows on OR-Tools routing. Each day is a vehicle that starts and ends at the hotel; each place is optional and dropping it costs its utility; must-do places are mandatory.
- Constraints: opening hours, day start/end, a 60-minute lunch break, hard budget, walking cap per day, stops per day (pace), days balanced.
- Scenarios: the same model with three parameter sets (weights for utility, travel time, money, walking; transport policy; walking cap; stops per day), plus a diversity rule so each scenario differs by at least two places. If three meaningfully different feasible plans do not exist, the app says so.
- Determinism: tests use a fixed solution limit instead of a wall-clock limit so results repeat.

### Validator

Plain code, written separately from the solver, that re-computes the itinerary's timings and costs from the catalog and checks: each stop inside opening hours, the day window, the lunch break, no duplicate places, must-dos present, the hard budget, the walking cap, the pace limit, and time continuity between stops. It is tested with Hypothesis (random itineraries, some deliberately broken) and must catch every planted violation.

### Infeasible requests

`feasibility.precheck()` explains the common conflicts before solving (must-do admissions above budget, a must-do closed on all trip days, must-dos that cannot fit in the available hours). If the solver still finds nothing, the app offers concrete choices: remove a named must-do, allow taxis, raise the budget by a shown amount. Hard limits are never relaxed without the user agreeing.

---

## 8. The web app

### Traveler screens

| Screen | What it does |
| --- | --- |
| Home | Short explanation, "Plan a trip", "My trips", one example trip to open |
| New trip | Step form: destination and dates → travelers and budget (with "what does this budget cover?") → interests and pace → must-dos and limits → summary to confirm. From M7, a free-text box at the top fills the form |
| Planning | Real progress steps from the job, partial results where available |
| Trip view | Scenario switcher (Budget / Balanced / Comfort) and four tabs: Story, Timeline, Map, Budget. Selecting a stop highlights it everywhere. Place drawer with why it fits, duration, price and source, media credit, booking link |
| Revise | Change box + quick chips ("less walking on day 2", "slower afternoon"), lock icons on stops, a "what changed" diff, approve button |
| My trips | Saved trips with version history |

Visible trust labels throughout: `Checked`, `Estimated`, `Unknown`, `Demo data`, and image labels (`This venue`, `This area`, `City photo`, `AI illustration`).

### Lab screens (for builders and testers)

| Lab page | Use |
| --- | --- |
| Catalog | Browse and filter places, see missing fields, opening hours, media licenses |
| Solver | Pick a sample brief, edit weights and caps, run all three scenarios, see the raw itinerary, skipped places and validator report |
| Validator | Paste or edit an itinerary and see which checks fail |
| Search (M8) | Type interests, compare tag-only, vector, keyword and hybrid results with scores |
| Intake (M7) | Type free text, see the extracted `TripBrief` and the questions the AI would ask |
| Runs | Recent planning jobs with step timings, token use and errors |
| Evals (M12) | Latest evaluation results per suite |

The Lab is hidden from the traveler navigation and available at `/lab`.

---

## 9. Milestones

Each milestone ends with something runnable, tests, and a short note in `docs/adr/` when it contains a real decision. Sizes are rough guesses for one developer working with AI coding help: **S** ≈ under a week, **M** ≈ 1–2 weeks, **L** ≈ 2–3 weeks.

### Phase 1 — Foundation

**M0. Project foundation (S)**
Repository layout, backend and web skeletons, Postgres in Docker Compose, lint and tests in CI, `.env.example`, README with run instructions.
*You can test:* `docker compose up db`, start the backend and web app, see the web page call `/health`.

### Phase 2 — Planning core, no AI yet

**M1. Trip data model and database (S)**
Pydantic schemas, SQLAlchemy tables, first Alembic migration, demo user, sample trip briefs as test fixtures.
*You can test:* run migrations, create and read a trip in tests and in `/docs`.

**M2. Lisbon catalog (M)**
Ingestion script (OSM + Wikidata + Wikimedia Commons) writes a draft `places.yaml`; hand review of ~150 places (visit time, tags, price, hours, hero image); loader into Postgres with sources and licenses; catalog API.
*You can test:* Lab → Catalog page lists reviewed Lisbon places with images and credits.

**M3. Solver: one scenario (M)**
Travel-time estimates, utility scoring, OR-Tools model from `solver_example.py` on real catalog data, deterministic test mode.
*You can test:* run the solver on a sample brief from a script and see a 3-day plan.

**M4. Three scenarios, budget and validator (M)**
Scenario parameters and diversity rule, budget breakdown with scope and unknowns, independent validator with property-based tests, infeasibility pre-checks, Lab Solver and Validator pages.
*You can test:* Lab → Solver: change weights and watch Budget, Balanced, Comfort change; break an itinerary in Lab → Validator and see it caught.

### Phase 3 — First usable web app ("Web Alpha")

**M5. Planning API and jobs (S)**
`POST /trips` starts a background job, job progress events, trip versions saved, `GET /trips`.
*You can test:* create a trip in `/docs`, poll the job, read the saved version.

**M6. Web app: plan, explore, save (L)**
New-trip form, planning progress screen, trip view with scenario switcher and Timeline, Map, Budget tabs, linked selection, place drawer, My trips, first Playwright end-to-end test.
*You can test:* the whole flow in a browser with a form and no AI: plan a Lisbon trip, compare scenarios, see the map and costs, reload and find it saved.

### Phase 4 — The AI layer

**M7. AI trip intake (M)**
LLM adapter with structured output and a mock for tests, free text → `TripBrief`, clarification questions, confirmation summary, 30-case intake eval set, run log with tokens and cost, Lab Intake page.
*You can test:* type "3 relaxed days in Lisbon for two, love food and tiles, max 200 euros, my partner can't walk much" and check the filled form and questions.

**M8. Smarter place search (M)**
Embeddings in pgvector, Postgres full-text search, hybrid fusion and re-ranking into utility, labeled retrieval set with recall@50, Lab Search page.
*You can test:* Lab → Search: compare result lists and the measured recall for each method.

**M9. Story, media and live context (M)**
"Why this fits you" per stop (curation), day chapters grounded in stored descriptions and bound to the validated itinerary, media resolution with labels, Open-Meteo weather (forecast vs seasonal), routing provider adapter, demo-mode fixtures, Story tab.
*You can test:* open a trip and read day chapters with real images and credits; switch off the network in demo mode and see the "Demo data" label.

**M10. Workflow orchestration with LangGraph (M)**
Convert `plan_trip()` to a LangGraph graph with Postgres checkpoints, a confirm-brief pause, scenario fan-out, a repair loop driven by validator results (max 2 tries), and clear infeasibility choices.
*You can test:* stop the backend mid-plan, restart it, and see the job resume; submit an impossible request and get understandable choices.

### Phase 5 — Revise, approve, harden ("Web Beta")

**M11. Revision, versions and approval (M)**
Change request → structured constraint delta (LLM), locked stops, re-solve and validate, "what changed" diff, version history, approve, explicit outbound booking links that never mark anything as booked.
*You can test:* "less walking on day 2" on a saved trip, see the diff, approve, reload, and open the previous version.

**M12. Evaluation, hardening and test deployment (L)**
Persona-based evaluation harness, fixed regression suite in CI, metamorphic solver tests, p50/p95 timings for first result and completion, cost limits per run, error states for every provider failure, accessibility pass, Redis/Celery only if measurements require it, deploy to one small server with HTTPS and a shared password, Lab Evals page, invite a few testers.
*You can test:* the deployed web app from any browser; the Evals page shows violation rate, intake accuracy, recall and latency.

### Phase 6 — Mobile app

**M13. Mobile app core (L)**
Expo app with Expo Router, move shared TypeScript code into `shared/`, trip intake, planning progress, trip view with the four tabs on phone screens, map with react-native-maps, revision and approval, tested in the Android emulator.
*You can test:* the brief's original demo flow in the Android emulator against the same backend.

**M14. Mobile polish and tester release (M)**
Offline view of a saved trip, reduced-motion and screen-reader checks, slow-network handling, app icon and splash, internal test builds with EAS for Android (then iOS).
*You can test:* install the test build on a real phone.

### Later (not planned in detail yet)

Accounts and privacy controls, private group planning (invite, vote, lock, approve), share links and "Make this trip mine", more cities, learned ranking from saves and skips, visit-duration prediction, booking integrations after separate validation. The brief keeps these outside the first version, and the earlier decisions recommend groups and share links before any public feed.

---

## 10. Testing strategy

| Layer | What we test | Tool |
| --- | --- | --- |
| Schemas | Valid and invalid briefs, money and date rules | pytest |
| Solver | Sample briefs give feasible plans; must-dos kept; budget, hours and walking respected; same input gives same output | pytest |
| Validator | Catches every planted violation in random itineraries | Hypothesis |
| Solver properties | Every plan passes the validator; raising the budget never lowers utility on exact small cases; removing an unused place leaves the plan unchanged | Hypothesis, metamorphic tests |
| Catalog | Every place has coordinates, a visit time, a source; every image has a license and author | pytest data checks |
| AI steps | Run against a mock LLM in normal CI; real-model evals in a separate, manually triggered workflow | pytest + eval scripts |
| API | Endpoints with a test database | pytest + FastAPI TestClient |
| Web components | Form validation, linked selection, labels | Vitest + Testing Library |
| End to end | Plan → explore → revise → approve → reload in a real browser | Playwright |
| Quality over time | Intake accuracy, recall@50, violation rate, persona pass rate, p50/p95 latency, cost per plan | `evals/` + Lab Evals page |

Rule: CI must pass before merging to `main`, and a failing test is fixed, never skipped.

---

## 11. How we work

- **One step = one branch = one small pull request.** Branch names follow the step ID, e.g. `m3-2-travel-estimates`.
- **Every PR** has a short description, tests for new behavior, and green CI. An AI review runs on each PR and each finding gets an answer.
- **Write the core pieces by hand first** (solver model, validator, one AI step, the version schema); use AI help for boilerplate, fixtures and UI scaffolding, as the earlier decision record recommends.
- **ADRs** (`docs/adr/0001-*.md`, half a page each) only for real decisions: web-first stack, polling before Celery, catalog licensing rules, LangGraph adoption, mobile map library.
- **Secrets** live in `.env` (never committed). The app runs without an API key in demo mode, using recorded fixtures, clearly labeled.
- **Definition of done for a milestone:** the "You can test" item works in the running app, tests and CI are green, the README run steps still work, and the step checklist is ticked.

---

## 12. Risks and how the plan handles them

| Risk | Handling |
| --- | --- |
| Opening hours and prices in open data are incomplete | Hand review for the launch city; missing values shown as `Unknown`, never guessed silently |
| Solver too slow with many candidates | Cap candidates at 30–60 after search; measure solve time in M4 |
| LLM output drifts or breaks | Structured outputs, Pydantic validation, retries, mock in CI, eval set tracked over time |
| Free-tier provider limits | Caching, demo mode, provider adapters that can be swapped |
| Image licensing | Store only storable media with license and author; display credit everywhere |
| Scope creep into social features | Social and booking are explicitly in "Later" |
| Web and mobile drift apart | One backend owns all logic; both apps use the same generated types |
