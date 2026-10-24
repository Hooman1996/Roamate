# Roamate implementation steps

Every step is meant to be one small pull request. IDs are used for branch names (`m3-2-travel-estimates`). Details for each milestone are in [implementation-plan.md](implementation-plan.md).

## Phase 1 — Foundation

### M0. Project foundation
- [ ] **M0.1** Create the repository layout (`backend/`, `web/`, `data/`, `evals/`, `docs/`) and a README with run instructions
- [ ] **M0.2** Set up the FastAPI backend skeleton with uv, settings from `.env`, and `GET /health`
- [ ] **M0.3** Add Postgres with pgvector in Docker Compose and the database connection
- [ ] **M0.4** Set up the React + Vite + TypeScript web app with Tailwind and React Router
- [ ] **M0.5** Show backend health on the web home page (first call from web to API)
- [ ] **M0.6** Add ruff, ESLint, Prettier and pre-commit hooks
- [ ] **M0.7** Add GitHub Actions CI: lint and tests for backend and web on every pull request
- [ ] **M0.8** Write ADR 0001: web first, simple stack, what we add later

## Phase 2 — Planning core, no AI yet

### M1. Trip data model and database
- [ ] **M1.1** Define the Pydantic schemas: TripBrief, Place, MediaAsset, Stop, Itinerary, Scenario, BudgetBreakdown, ValidationReport
- [ ] **M1.2** Create the SQLAlchemy tables and the first Alembic migration
- [ ] **M1.3** Add the demo user and seed script
- [ ] **M1.4** Add sample trip briefs as test fixtures (normal, tight budget, low walking, impossible)
- [ ] **M1.5** Generate TypeScript types for the web app from the OpenAPI schema

### M2. Lisbon catalog
- [ ] **M2.1** Write the OSM (Overpass) ingestion script for Lisbon places
- [ ] **M2.2** Enrich places with Wikidata facts and Wikimedia Commons images with license and author
- [ ] **M2.3** Produce the draft `data/cities/lisbon/places.yaml` for review
- [ ] **M2.4** Hand-review about 150 places: visit time, interest tags, price, opening hours, hero image
- [ ] **M2.5** Load the reviewed catalog into Postgres with field sources and dates
- [ ] **M2.6** Add catalog data checks (coordinates, visit time, source, media license)
- [ ] **M2.7** Add the catalog API (`/cities`, `/cities/{id}/places`, `/places/{id}`)
- [ ] **M2.8** Build the Lab → Catalog page

### M3. Solver: one scenario
- [ ] **M3.1** Write utility scoring from interest tags and curated score
- [ ] **M3.2** Write travel estimates by mode (walk, metro, taxi) from distance
- [ ] **M3.3** Write candidate selection: filters for city, opening days, price, exclusions
- [ ] **M3.4** Port the OR-Tools model from `solver_example.py` to `planning/solver.py` on catalog data
- [ ] **M3.5** Add opening hours by weekday, lunch break, must-dos, budget, walking cap and pace
- [ ] **M3.6** Add deterministic test mode and solver tests on the sample briefs

### M4. Three scenarios, budget and validator
- [ ] **M4.1** Define Budget, Balanced and Comfort parameter sets and the diversity rule
- [ ] **M4.2** Report "no meaningfully different options" honestly when scenarios collapse
- [ ] **M4.3** Write the budget breakdown with scope, categories and quoted/estimated/unknown labels
- [ ] **M4.4** Write the independent validator
- [ ] **M4.5** Add property-based validator tests with Hypothesis (planted violations)
- [ ] **M4.6** Write infeasibility pre-checks with clear user choices
- [ ] **M4.7** Add `POST /lab/solve` and `POST /lab/validate`
- [ ] **M4.8** Build the Lab → Solver and Lab → Validator pages

## Phase 3 — First usable web app ("Web Alpha")

### M5. Planning API and jobs
- [ ] **M5.1** Write the `plan_trip()` pipeline function with progress events
- [ ] **M5.2** Add the planning job table and run jobs as background tasks
- [ ] **M5.3** Add `POST /trips`, `GET /trips`, `GET /trips/{id}` and version endpoints
- [ ] **M5.4** Add `GET /jobs/{id}` with status, events and result
- [ ] **M5.5** Add API integration tests with a test database

### M6. Web app: plan, explore, save
- [ ] **M6.1** Build the app shell, navigation and API client with TanStack Query
- [ ] **M6.2** Build the new-trip step form with validation and the confirmation summary
- [ ] **M6.3** Build the planning progress screen (polling the job)
- [ ] **M6.4** Build the trip view with the scenario switcher
- [ ] **M6.5** Build the Timeline tab
- [ ] **M6.6** Build the Map tab with Leaflet, stops and day routes
- [ ] **M6.7** Build the Budget tab with scope, labels and unknowns
- [ ] **M6.8** Link selection across tabs and add the place details drawer
- [ ] **M6.9** Build the My trips page and reopen saved trips
- [ ] **M6.10** Add the first Playwright end-to-end test: plan, explore, reload
- [ ] **M6.11** Run the Web Alpha check and record issues

## Phase 4 — The AI layer

### M7. AI trip intake
- [ ] **M7.1** Write the LLM adapter with structured output, retries and a mock for tests
- [ ] **M7.2** Add the run log for step timings, tokens and cost
- [ ] **M7.3** Write free text → TripBrief extraction with versioned prompts
- [ ] **M7.4** Add clarification questions for missing essentials (dates, budget, mobility)
- [ ] **M7.5** Add `POST /intake/parse` and the free-text box that fills the form
- [ ] **M7.6** Build the 30-case intake eval set and scoring script
- [ ] **M7.7** Build the Lab → Intake and Lab → Runs pages

### M8. Smarter place search
- [ ] **M8.1** Add place embeddings with a local model and a pgvector column
- [ ] **M8.2** Add Postgres full-text search on names and descriptions
- [ ] **M8.3** Combine results with rank fusion and re-rank into utility
- [ ] **M8.4** Label 20–30 briefs with good candidate places
- [ ] **M8.5** Measure recall@50 for tag-only, vector, keyword and hybrid search
- [ ] **M8.6** Add `POST /lab/search` and the Lab → Search page

### M9. Story, media and live context
- [ ] **M9.1** Write "why this fits you" for each chosen stop (curation step)
- [ ] **M9.2** Write day chapters grounded in stored descriptions and bound to the itinerary
- [ ] **M9.3** Resolve media per stop with kind labels and credits
- [ ] **M9.4** Add the Open-Meteo weather provider with forecast vs seasonal labels
- [ ] **M9.5** Add the routing provider adapter (OpenRouteService) with caching and fallback to estimates
- [ ] **M9.6** Add demo mode with recorded fixtures and a visible "Demo data" label
- [ ] **M9.7** Build the Story tab linked to the other tabs
- [ ] **M9.8** Check that a story or image failure never blocks the itinerary

### M10. Workflow orchestration with LangGraph
- [ ] **M10.1** Write ADR: when and why we adopt LangGraph
- [ ] **M10.2** Convert `plan_trip()` steps into graph nodes with the same behavior
- [ ] **M10.3** Add Postgres checkpoints and resume after a backend restart
- [ ] **M10.4** Add the confirm-your-brief pause (human in the loop)
- [ ] **M10.5** Run the three scenarios in parallel
- [ ] **M10.6** Add the repair loop driven by validator results (max 2 tries)
- [ ] **M10.7** Show infeasibility choices in the web app

## Phase 5 — Revise, approve, harden ("Web Beta")

### M11. Revision, versions and approval
- [ ] **M11.1** Write change request → structured constraint delta (LLM)
- [ ] **M11.2** Add stop locks in the solver
- [ ] **M11.3** Add the revise job: re-solve, validate, save a new version
- [ ] **M11.4** Compute the "what changed" diff (stops, time, walking, cost)
- [ ] **M11.5** Build the revision panel, quick-change chips and diff view
- [ ] **M11.6** Add approve and version history in the web app
- [ ] **M11.7** Add outbound booking links with honest states (suggested, opened, never auto-booked)
- [ ] **M11.8** Add the Playwright test: "less walking on day 2" → approve → reload

### M12. Evaluation, hardening and test deployment
- [ ] **M12.1** Build the persona generator and simulated-user runner
- [ ] **M12.2** Add graders: deterministic checks and an LLM judge with a rubric
- [ ] **M12.3** Add the fixed regression suite to CI and a manual full-eval workflow
- [ ] **M12.4** Add metamorphic solver tests
- [ ] **M12.5** Measure p50/p95 time to first result, completion and revision
- [ ] **M12.6** Add cost limits per run and friendly errors for every provider failure
- [ ] **M12.7** Run an accessibility pass (keyboard, contrast, screen reader, reduced motion)
- [ ] **M12.8** Decide on Redis/Celery from measurements and add only if needed
- [ ] **M12.9** Deploy to one small server with HTTPS and a shared password
- [ ] **M12.10** Build the Lab → Evals page
- [ ] **M12.11** Run the Web Beta with a few testers and collect feedback

## Phase 6 — Mobile app

### M13. Mobile app core
- [ ] **M13.1** Write ADR: mobile stack and map library
- [ ] **M13.2** Move shared TypeScript code (API types, formatting, labels) into `shared/`
- [ ] **M13.3** Set up the Expo app with Expo Router and the API client
- [ ] **M13.4** Build trip intake on mobile
- [ ] **M13.5** Build planning progress on mobile
- [ ] **M13.6** Build the trip view tabs: Story, Timeline, Map, Budget
- [ ] **M13.7** Build revision and approval on mobile
- [ ] **M13.8** Run the brief's demo flow in the Android emulator

### M14. Mobile polish and tester release
- [ ] **M14.1** Make saved trips viewable offline
- [ ] **M14.2** Check reduced motion, screen readers and slow networks
- [ ] **M14.3** Add app icon, splash screen and store-ready names
- [ ] **M14.4** Ship internal test builds with EAS (Android, then iOS)
- [ ] **M14.5** Collect tester feedback and plan the next phase
