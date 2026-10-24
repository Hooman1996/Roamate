# Roamate implementation steps

**Version:** 2.3 (approved) · 24 October 2026

Every step starts only after its design is approved (M0) and its short step brief gets a go-ahead. Until Web Alpha (end of M10), steps are committed directly to `main`; after that, each step is a branch named after its ID (`m11-2-stop-locks`) and a pull request. Details for each milestone are in [implementation-plan.md](implementation-plan.md).

## Phase 1 — Design and approval

### M0. Design and approval
- [x] **M0.1** Approve the implementation plan (approved 24 Oct 2026)
- [ ] **M0.2** Design: infrastructure, shared services, routing service, conda environment and `.env` settings
- [ ] **M0.3** Design: PostgreSQL schema (every table, column, index, with examples)
- [ ] **M0.4** Design: Qdrant collections, vectors and payload indexes
- [ ] **M0.5** Design: MinIO buckets, object layout and access rules
- [ ] **M0.6** Design: domain data structures (TripBrief with HotelChoice, UtilityFeatures, Itinerary, Scenario, BudgetBreakdown, ValidationReport, ConflictReport, ConstraintDelta)
- [ ] **M0.7** Design: accounts, sessions, roles and sign-in flows
- [ ] **M0.8** Design: model gateway: provider config format, chain order and fallback rules
- [ ] **M0.9** Design: city ingestion stages, review rules and auto-approve thresholds
- [ ] **M0.10** Design: LangGraph state, nodes, edges, pauses and revision graph
- [ ] **M0.11** Design: API contract (endpoints, requests, responses, errors)
- [ ] **M0.12** Design: web screens and navigation (wireframes)
- [ ] **M0.13** Choose the launch city, candidate embedding models and the first evaluation cases

## Phase 2 — Foundation and accounts

### M1. Foundation
- [ ] **M1.1** Create the repository layout and README with run instructions
- [ ] **M1.2** Add `environment.yml` for the conda env `roamate` (Python 3.12, Node.js 22)
- [ ] **M1.3** Set up the FastAPI backend skeleton with settings from `.env` and `.env.example`
- [ ] **M1.4** Add `infra/docker-compose.yml` with the same pinned images as the RagBot server
- [ ] **M1.5** Add setup scripts for the `roamate` database and user, Qdrant collections and object storage buckets
- [ ] **M1.6** Add connection clients and a health endpoint for Postgres, Qdrant, object storage, TEI, vLLM and 9Router
- [ ] **M1.7** Set up the React + Vite + TypeScript web app with Tailwind, React Router and bundled fonts and icons
- [ ] **M1.8** Build the health page in the web app
- [ ] **M1.9** Add a build check that fails on any external URL in the built web app
- [ ] **M1.10** Add ruff, ESLint, Prettier and pre-commit hooks
- [ ] **M1.11** Add GitHub Actions CI on every push to `main`

### M2. Accounts and login
- [ ] **M2.1** Create the user and session tables and their migration
- [ ] **M2.2** Add password hashing and session handling
- [ ] **M2.3** Add register, sign in, sign out and current-user endpoints
- [ ] **M2.4** Add user and admin roles and the admin creation command
- [ ] **M2.5** Build the sign-up and sign-in pages and protected routes
- [ ] **M2.6** Add auth tests (hashing, expiry, role checks on every admin route)

### M3. Core data layer
- [ ] **M3.1** Write the Pydantic domain models from the approved design
- [ ] **M3.2** Create migrations for city, ingestion, place, media, trip, version, job and LLM call tables
- [ ] **M3.3** Add the Qdrant collection helpers (create, upsert, hybrid query)
- [ ] **M3.4** Add the S3 storage helpers with boto3 (upload, read, serve through the backend)
- [ ] **M3.5** Generate TypeScript types for the web app from the OpenAPI schema
- [ ] **M3.6** Add test fixtures: sample places, briefs (normal, tight budget, low walking, impossible)

## Phase 3 — Models and city data

### M4. Model gateway
- [ ] **M4.1** Load providers and the chain order from `config/models.yaml` (overridable by `LLM_CHAIN`) and keys from `.env`
- [ ] **M4.2** Write the OpenAI-compatible client and chain fallback with cool-down
- [ ] **M4.3** Add OpenRouter model lists (free models only) and set up 9Router on the server
- [ ] **M4.4** Add structured output with Pydantic validation and one repair retry
- [ ] **M4.5** Log every attempt to the `llm_call` table
- [ ] **M4.6** Add the TEI embedding and reranker clients
- [ ] **M4.7** Add gateway tests with fake providers (fail, timeout, 429, bad JSON)
- [ ] **M4.8** Build the Lab → Models page

### M5. City data pipeline
- [ ] **M5.1** Write the pipeline runner with resumable stages and `ingest_run` tracking
- [ ] **M5.2** Write the Discover stage (Nominatim and Wikidata)
- [ ] **M5.3** Write the Collect stage (Overpass and Wikidata) with raw data saved to object storage
- [ ] **M5.4** Write the Merge stage (OSM–Wikidata matching and duplicates)
- [ ] **M5.5** Write the Enrich stage: Wikipedia summaries, Commons images with licenses, opening hours
- [ ] **M5.6** Collect hotels with features from OSM tags and labeled nightly price estimates
- [ ] **M5.7** Add LLM-estimated tags, visit times and price bands, marked as estimates
- [ ] **M5.8** Write the Score stage (popularity, rating, iconic status and completeness)
- [ ] **M5.9** Add the `ingest_city` command and stage tests on recorded data

### M6. City review and publishing
- [ ] **M6.1** Build the Admin → Cities page with add city and stage progress
- [ ] **M6.2** Build the Admin → Review page for places and hotels (bulk approve, edit, reject, gaps highlighted)
- [ ] **M6.3** Add the tariff form: taxi tariff and transit ticket prices with source link and valid dates
- [ ] **M6.4** Add auto-approve rules for auto mode
- [ ] **M6.5** Write the Publish stage: places, hotels and media to Postgres, vectors to Qdrant
- [ ] **M6.6** Extract the city map file (PMTiles) and serve it with local map styles
- [ ] **M6.7** Set up the routing service and build the city's routing data when publishing
- [ ] **M6.8** Ingest, review and publish the launch city
- [ ] **M6.9** Add a second city through the UI only and record what was needed

## Phase 4 — Planning engine

### M7. Solver and scenarios
- [ ] **M7.1** Write utility scoring from separate features (interest match, rerank, quality, iconic)
- [ ] **M7.2** Get walking and driving matrices from the routing service, with labeled distance estimates as fallback
- [ ] **M7.3** Add taxi fares from the city tariff and the transit day pass
- [ ] **M7.4** Port the OR-Tools model from `solver_example.py` to `planning/solver.py` on catalog data
- [ ] **M7.5** Add opening hours by weekday, lunch, must-dos, budget, walking cap, pace and category caps
- [ ] **M7.6** Add the hotel filter, shortlist and per-hotel solve with the best-total choice
- [ ] **M7.7** Add Budget, Balanced and Comfort parameter sets and the diversity rule
- [ ] **M7.8** Add deterministic test mode and solver tests on the sample briefs
- [ ] **M7.9** Build the Lab → Solver page

### M8. Validator, budget and search
- [ ] **M8.1** Write the independent validator
- [ ] **M8.2** Add property-based validator tests with Hypothesis
- [ ] **M8.3** Write the budget breakdown with hotel nights, scope and quoted/estimated/unknown labels
- [ ] **M8.4** Write the feasibility precheck and the conflict finder (smallest set of clashing constraints) with clear user choices
- [ ] **M8.5** Write hybrid search (dense + BM25) with reranking feeding utility
- [ ] **M8.6** Label 20–30 briefs with good candidate places
- [ ] **M8.7** Compare embedding models and search methods by recall@50 and pick the model
- [ ] **M8.8** Build the Lab → Validator and Lab → Search pages

## Phase 5 — AI workflow and web app ("Web Alpha")

### M9. LangGraph planning workflow
- [ ] **M9.1** Define the graph state and the form-path graph (precheck, retrieve, solve, validate, save)
- [ ] **M9.2** Add Postgres checkpoints and resume after restart
- [ ] **M9.3** Write the job runner and job API (start, status, events, resume)
- [ ] **M9.4** Add the intake node (free text → TripBrief, including hotel preferences) with versioned prompts
- [ ] **M9.5** Add the clarify and confirm pauses
- [ ] **M9.6** Add the hotel node (fixed hotel, or shortlist and choose)
- [ ] **M9.7** Run the three scenarios in parallel
- [ ] **M9.8** Add the validate and repair loop (max 2 tries)
- [ ] **M9.9** Add the weather provider (forecast vs seasonal, cached)
- [ ] **M9.10** Add the curation node ("why this fits you")
- [ ] **M9.11** Add the story node, bound to the validated itinerary
- [ ] **M9.12** Build the 30-case intake eval set and scoring script
- [ ] **M9.13** Build the Lab → Intake and Lab → Runs pages

### M10. Web app: plan, explore, save
- [ ] **M10.1** Build the app shell, navigation and API client with TanStack Query
- [ ] **M10.2** Build the new-trip page: free-text box and step form
- [ ] **M10.3** Build the clarify and confirm screens
- [ ] **M10.4** Build the planning progress screen
- [ ] **M10.5** Build the trip view with the scenario switcher and the hotel choice with runner-ups
- [ ] **M10.6** Build the Story tab with media labels and credits
- [ ] **M10.7** Build the Timeline tab
- [ ] **M10.8** Build the Map tab with MapLibre and the city's local tiles
- [ ] **M10.9** Build the Budget tab with scope, labels and unknowns
- [ ] **M10.10** Link selection across tabs and add the place details drawer
- [ ] **M10.11** Build the My trips page
- [ ] **M10.12** Add the Playwright end-to-end test: sign in, plan, explore, reopen
- [ ] **M10.13** Run the Web Alpha check, tag `v0.1-alpha`, switch to branches and pull requests

## Phase 6 — Revise, evaluate, deploy ("Web Beta")

### M11. Revision and approval
- [ ] **M11.1** Add the change parser node (change request → ConstraintDelta)
- [ ] **M11.2** Add stop locks in the solver
- [ ] **M11.3** Build the revision graph: re-solve, validate, save a new version
- [ ] **M11.4** Compute the "what changed" diff (stops, time, walking, cost)
- [ ] **M11.5** Build the revision panel, quick-change chips and diff view
- [ ] **M11.6** Add approve and version history in the web app
- [ ] **M11.7** Add outbound booking links with honest states
- [ ] **M11.8** Add the Playwright test: "less walking on day 2" → approve → reopen

### M12. Evaluation, hardening and deployment
- [ ] **M12.1** Build the persona generator and simulated-user runner
- [ ] **M12.2** Add graders: deterministic checks and an LLM judge with a rubric
- [ ] **M12.3** Add the regression suite to CI and a manual full-eval workflow
- [ ] **M12.4** Add metamorphic solver tests
- [ ] **M12.5** Measure p50/p95 time to first result, completion and revision
- [ ] **M12.6** Track usage and failures per provider; friendly errors for every failure
- [ ] **M12.7** Run an accessibility pass (keyboard, contrast, screen reader, reduced motion)
- [ ] **M12.8** Decide on a separate worker or Celery from measurements; add only if needed
- [ ] **M12.9** Deploy the backend and web app on the server next to the existing services
- [ ] **M12.10** Build the Lab → Evals page
- [ ] **M12.11** Run the Web Beta with a few testers and collect feedback

## Research track — TravelPlanner (alongside M11–M12)

### R1. TravelPlanner setup and baseline
- [ ] **R1.1** Download the TravelPlanner dataset and sandbox database
- [ ] **R1.2** Run the official validation scorer in the manual evaluation workflow
- [ ] **R1.3** Record the published baselines
- [ ] **R1.4** Write the paper claim and experiment plan (for approval)

### R2. TravelPlanner adapter and solver mode
- [ ] **R2.1** Design: TravelPlanner constraint spec schema (for approval)
- [ ] **R2.2** Write the query → constraint spec adapter through the model gateway
- [ ] **R2.3** Load the sandbox data (flights, distances, restaurants, attractions, accommodation)
- [ ] **R2.4** Write the CP-SAT model for multi-city, day-level plans
- [ ] **R2.5** Write the validator for TravelPlanner's commonsense and hard constraints
- [ ] **R2.6** Render plans to the official submission JSONL
- [ ] **R2.7** Score the 180 validation queries

### R3. Experiments and submission
- [ ] **R3.1** Run the validation set for each model in the chain
- [ ] **R3.2** Build the results table (pass rates, plan cost and quality, cost per query) on Lab → Evals
- [ ] **R3.3** Optional: run the TripScore benchmark
- [ ] **R3.4** Submit the test set once to the official leaderboard
- [ ] **R3.5** Write the workshop-paper draft

## Phase 7 — Mobile app

### M13. Mobile app core
- [ ] **M13.1** Design: mobile screens, navigation and map library (for approval)
- [ ] **M13.2** Move shared TypeScript code (API types, formatting, labels) into `shared/`
- [ ] **M13.3** Set up the Expo app with Expo Router, sign-in and the API client
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
