# Roamate implementation steps

**Version:** 3.0 (revised after review 1, awaiting hooman's approval in step M0.18) · 24 October 2026

Every step starts only after its design is approved (M0) and its short step brief gets a go-ahead. Until Web Alpha (end of M10), steps are committed directly to `main`; after that, each step is a branch named after its ID (`m11-2-stop-locks`) and a pull request. Details for each milestone are in [implementation-plan.md](implementation-plan.md); what changed in version 3.0 is in [review-response.md](review-response.md).

- **IDs never change.** Steps added in version 3.0 sit where they are done inside their milestone, so a higher number can come before a lower one (M0.18 is the first open step of M0).
- **Spike** steps write small throwaway code to answer a design question; they are not product code.
- **A step is ticked with evidence:** `- [x] **M1.3** … (done: <commit>, <test or command>)`.
- The roadmap is generated from this file and the plan: `python scripts/build_roadmap.py`. CI fails if it is out of date or if the two files disagree.

## Phase 1 — Design and approval

### M0. Design and approval
- [x] **M0.1** Approve the implementation plan (version 2.4, approved 24 Oct 2026)
- [ ] **M0.18** Approve plan version 3.0: authority order, support limits, release gates and the compatibility manifest template
- [ ] **M0.2** Design: infrastructure, shared-service isolation, four buckets, routing service, conda environment and `.env`, with the real server facts recorded
- [ ] **M0.3** Design: PostgreSQL schema with constraints, roles and grants, city snapshots, trip decisions, jobs and events
- [ ] **M0.4** Design: Qdrant collections, payload filters (city, snapshot), representation fingerprint, alias and access
- [ ] **M0.5** Design: object storage buckets, object layout, access rules, retention and range serving
- [ ] **M0.6** Design: domain data structures with money units, stay dates, hours states, solver statuses and the solver objective
- [ ] **M0.7** Design: accounts, sessions, ownership checks, Origin checks and throttling, web cookie and mobile token
- [ ] **M0.8** Design: model gateway: provider config, capabilities, chain order, fallback rules and job-wide budgets
- [ ] **M0.9** Design: city ingestion stages, source policies, review rules, kept edits, snapshot publishing and auto-approve thresholds
- [ ] **M0.14** Design: durable jobs: states, leases, recovery, cancellation, events, replay safety and solver process isolation
- [ ] **M0.10** Design: LangGraph state, nodes, pauses, replay safety, bounded parallel solves, weather rule and the revision graph
- [ ] **M0.11** Design: API contract (endpoints, auth, idempotency, version checks, cancellation, typed errors)
- [ ] **M0.12** Design: web screens, design system and every loading, empty, partial and error state
- [ ] **M0.15** Spike: show the transport-policy, day-pass, daily-window and lunch solver formulation on tiny hand-checked cases
- [ ] **M0.16** Spike: build a PMTiles map and a Valhalla routing build for a small area and serve them locally
- [ ] **M0.17** Record usage rights, limits, cost and data policy for every model provider, data source and embedding model
- [ ] **M0.13** Choose the launch city and its data and tariff sources, the provisional embedding model, and the development and held-out evaluation cases

## Phase 2 — Foundation and accounts

### M1. Foundation
- [ ] **M1.1** Create the repository layout and the README with run commands from the repository root
- [ ] **M1.2** Add `environment.yml` for the conda env `roamate` (Python 3.12, Node.js 22)
- [ ] **M1.12** Add dependency locks (`backend/requirements.lock`, `web/package-lock.json`), a compatibility smoke script, and the shared and standalone run modes
- [ ] **M1.3** Set up the FastAPI backend skeleton: settings from `.env` checked at start, the launcher using `APP_PORT`, typed errors
- [ ] **M1.13** Add request correlation IDs, safe error messages, request limits and redacted logs
- [ ] **M1.4** Add `infra/docker-compose.yml` (project `roamate`, `roamate-*` names, loopback ports, pinned images, `shared` and `standalone` profiles)
- [ ] **M1.5** Add setup scripts for the database roles, Qdrant collections and the four buckets, with dry run and name checks
- [ ] **M1.6** Add connection clients and the live, ready and admin diagnostics endpoints
- [ ] **M1.7** Set up the React + Vite + TypeScript web app with Tailwind, React Router, bundled fonts and icons, and a minimal app shell
- [ ] **M1.8** Build the status page (public summary; full diagnostics for admins from M2)
- [ ] **M1.9** Add the check that the built web app makes no undeclared network requests (static scan plus browser interception)
- [ ] **M1.10** Add ruff, mypy, ESLint, Prettier, `tsc --noEmit`, gitleaks and pre-commit hooks
- [ ] **M1.11** Add GitHub Actions CI: lint and type checks, unit tests, integration tests on service containers, secret scan, roadmap check

### M2. Accounts and login
- [ ] **M2.1** Create the user, session and sign-in attempt tables and their migration
- [ ] **M2.2** Add Argon2id password hashing and hashed session tokens with expiry, rotation and revocation
- [ ] **M2.3** Add register, sign in, sign out and current-user endpoints with throttling, safe errors and Origin checks
- [ ] **M2.4** Add user and admin roles (set only by the server) and the admin creation and password-reset commands
- [ ] **M2.5** Build the sign-up and sign-in pages, protected routes and the admin menu in the app shell
- [ ] **M2.6** Add auth tests (hashing, expiry, revocation, role checks on every admin route)
- [ ] **M2.7** Add the ownership check for every user resource and the two-user denial tests

### M3. Core data layer
- [ ] **M3.1** Write the Pydantic domain models from the approved design (money, stay dates, hours states, statuses)
- [ ] **M3.2** Create migrations for city, snapshot, ingestion, review, place, hotel, tariff, media, trip, version, job and LLM call tables
- [ ] **M3.7** Add trip decisions, version numbering and the stale-version check, with concurrency tests
- [ ] **M3.8** Write the reusable job runner and worker: claim, lease, heartbeat, reclaim, cancel, deadline
- [ ] **M3.3** Add the Qdrant collection helpers (create, upsert, hybrid query, alias switch), tested on a real Qdrant
- [ ] **M3.4** Add the S3 storage helpers with boto3 (upload with checksum, streaming and range reads, private buckets)
- [ ] **M3.5** Generate TypeScript types from the OpenAPI schema and fail CI when they are stale
- [ ] **M3.6** Add test fixtures (normal, tight budget, low walking, impossible, unknown hours, partial days, several rooms) and a fixture trip shown in the app

## Phase 3 — Models and city data

### M4. Model gateway
- [ ] **M4.1** Load providers, capabilities and the chain order from `config/models.yaml` (overridable by `LLM_CHAIN`) and keys from `.env`; skip providers that are not set up
- [ ] **M4.2** Write the OpenAI-compatible client and chain fallback with cool-down, `Retry-After`, jitter and no retries on auth errors
- [ ] **M4.3** Add OpenRouter free-model lists, and 9Router as an opt-in provider after its upstream accounts are checked
- [ ] **M4.4** Add structured output with Pydantic validation, one repair retry and a meaning check against the brief
- [ ] **M4.5** Log every attempt to `llm_call` with the answering model, error kind, budget used and trace ID
- [ ] **M4.9** Add the job-wide model budget (calls, tokens, time) shared by every fallback and repair
- [ ] **M4.6** Add the TEI embedding and reranker clients with prefix, vector-size and batch checks
- [ ] **M4.7** Add gateway tests with fake providers (fail, timeout, 429, 401, bad JSON, budget used up)
- [ ] **M4.10** Write the separate development and launch model configurations and check each one
- [ ] **M4.8** Build the Lab → Models page (admin only, redacted traces)

### M5. City data pipeline
- [ ] **M5.1** Build the city pipeline on the job runner, with resumable stages and `ingest_run` tracking
- [ ] **M5.2** Write the Discover stage (one Nominatim lookup per city, Wikidata)
- [ ] **M5.3** Write the Collect stage (Overpass and Wikidata) with one pacer per source and raw responses saved to object storage
- [ ] **M5.4** Write the Merge stage (OSM–Wikidata matching and duplicates), keeping the source of every field
- [ ] **M5.5** Write the Enrich stage: Wikipedia summaries, Commons images with licenses and safe downloads, opening hours with states
- [ ] **M5.6** Collect hotels as reviewable candidates with features, room capacity and labeled nightly price estimates
- [ ] **M5.7** Add LLM-estimated tags, visit times and price bands, marked as estimates per field
- [ ] **M5.8** Write the Score stage (popularity, completeness, iconic; ratings only from a licensed source)
- [ ] **M5.9** Add the `ingest_city` command and stage tests on recorded data
- [ ] **M5.10** Test reruns: kept review edits, removed places, source throttling and unsafe media

### M6. City review and publishing
- [ ] **M6.1** Build the Admin → Cities page with add city, stage progress, cancel and clear stage errors
- [ ] **M6.2** Build the Admin → Review page for places and hotels (bulk approve, edit, reject, gaps and sources shown)
- [ ] **M6.3** Add the tariff form (taxi formula, transit tickets) and the separate rush-hour profile, each with source and valid dates
- [ ] **M6.4** Add auto-approve rules for auto mode, within the field-quality and license rules
- [ ] **M6.5** Write the Publish stage as a city snapshot: Postgres rows, Qdrant points and media, checked, then switched on
- [ ] **M6.6** Extract the city map (PMTiles, buffered area) and serve it with range requests and local styles, glyphs and sprites
- [ ] **M6.7** Set up the routing service and build versioned routing data with a smoke test before switching
- [ ] **M6.10** Test publish failures at each store, and rollback to the previous snapshot
- [ ] **M6.8** Ingest, review and publish the launch city
- [ ] **M6.9** Add a second city through the UI only, check the first city still routes, and record what was needed
- [ ] **M6.11** Check the mobile map and sign-in approach on an Android development build with a published city

## Phase 4 — Planning engine

### M7. Solver and scenarios
- [ ] **M7.1** Write utility scoring from separate features (interest match, rerank, popularity, quality with a neutral prior, iconic)
- [ ] **M7.2** Get walking and driving matrices from the routing service; leave out unreachable pairs; label distance estimates
- [ ] **M7.3** Add taxi fares from the tariff and transit ticket costs, in minor currency units
- [ ] **M7.4** Add rush-hour factors per city, labeled estimated until calibrated against real trip times
- [ ] **M7.5** Port the OR-Tools model from `solver_example.py` to `planning/solver.py` on catalog data
- [ ] **M7.11** Check every solver input before OR-Tools, and run each solve in a supervised child process with a time limit
- [ ] **M7.13** Write the first independent validator and run it on every solve
- [ ] **M7.6** Add daily opening windows (one copy per day), lunch on full days, must-dos, budget, walking cap, pace and category caps
- [ ] **M7.12** Add transport policies per option and the day pass priced after the solve; test cases that need a slower, cheaper mode
- [ ] **M7.7** Add the hotel filter, shortlist (at most 5) and per-hotel solve, using real nights, rooms and budget scope
- [ ] **M7.8** Solve Budget, Balanced and Comfort independently under the same hard limits; drop duplicates and dominated options
- [ ] **M7.9** Add deterministic test mode, solver statuses and solver tests on the sample briefs
- [ ] **M7.10** Build the Lab → Solver page (status, objective parts, evidence labels)

### M8. Validator, budget and search
- [ ] **M8.1** Extend the validator to every hard rule, with exact violation locations and "not checked" results
- [ ] **M8.2** Add property-based validator tests with Hypothesis
- [ ] **M8.3** Write the budget breakdown with nights, rooms, scope and quoted/estimated/unknown/excluded labels
- [ ] **M8.4** Write the feasibility precheck (proven conflicts) and labeled relaxation suggestions, with clear user choices
- [ ] **M8.5** Write hybrid search (dense + BM25) with reranking feeding utility, filtered by city and snapshot
- [ ] **M8.9** Keep must-dos past the search cut-off, and test switching and rolling back the embedding collection
- [ ] **M8.6** Label briefs with good candidate places, split into development and frozen held-out sets
- [ ] **M8.7** Compare embedding models (on the lab TEI) and search methods by held-out recall@50, and record the chosen model's license
- [ ] **M8.8** Build the Lab → Validator and Lab → Search pages

## Phase 5 — AI workflow and web app ("Web Alpha")

### M9. LangGraph planning workflow
- [ ] **M9.1** Define the graph state and the form-path graph (precheck, retrieve, solve, validate, save)
- [ ] **M9.2** Add Postgres checkpoints and resume through the job runner after a restart
- [ ] **M9.3** Write the planning job API on the job runner (start, status, events, cancel, resume with token)
- [ ] **M9.4** Add the intake node (free text → TripBrief, including hotel preferences and budget scope) with versioned prompts and meaning checks
- [ ] **M9.5** Add the clarify and confirm pauses (owner only, stale confirmations refused)
- [ ] **M9.6** Add the hotel node (fixed hotel, or shortlist and choose, skipping over-budget hotels)
- [ ] **M9.7** Run the option solves in parallel under the process cap
- [ ] **M9.8** Add the validate and repair loop (max 2 tries, never relaxing the user's limits)
- [ ] **M9.9** Add the weather provider and the weather rule applied before solving (forecast vs seasonal, cached)
- [ ] **M9.10** Add the curation node ("why this fits you") from recorded facts only
- [ ] **M9.11** Add the story node with stop references and a template fallback
- [ ] **M9.12** Build the intake eval set (development and held-out, including contradictory requests) and scoring script
- [ ] **M9.13** Build the Lab → Intake and Lab → Runs pages (admin only, redacted)
- [ ] **M9.14** Test recovery: kill the worker, expired lease, duplicate resume, duplicate save

### M10. Web app: plan, explore, save
- [ ] **M10.1** Add trip navigation to the app shell and the API client with TanStack Query
- [ ] **M10.2** Build the new-trip page: free-text box and step form, showing the supported limits
- [ ] **M10.3** Build the clarify and confirm screens
- [ ] **M10.4** Build the planning progress screen with cancel, retry and partial results
- [ ] **M10.5** Build the trip view with 0–3 options, the hotel choice with runner-ups and honest statuses
- [ ] **M10.6** Build the Story tab with media labels, credits and the template fallback
- [ ] **M10.7** Build the Timeline tab with lunch, waits and the return leg
- [ ] **M10.8** Build the Map tab with MapLibre and the city's local tiles
- [ ] **M10.9** Build the Budget tab with scope, labels and unknowns
- [ ] **M10.10** Link selection across tabs by stop ID, with keyboard focus, and add the place details drawer
- [ ] **M10.11** Build the My trips page (own trips only; saved versions never silently refreshed)
- [ ] **M10.12** Add the Playwright end-to-end test: sign in, plan, explore, reopen, on real local services and fake models
- [ ] **M10.14** Run the visual, network-request and partial-result checks at desktop and phone sizes
- [ ] **M10.13** Run the Web Alpha check, tag `v0.1-alpha`, switch to branches and pull requests

## Phase 6 — Revise, evaluate, deploy ("Web Beta")

### M11. Revision and approval
- [ ] **M11.1** Add the change parser node (change request → ConstraintDelta), asking before any hard limit changes
- [ ] **M11.2** Add stop locks (place, day, time) in the solver
- [ ] **M11.3** Build the revision graph: re-solve, validate, save a new version on the expected base version
- [ ] **M11.4** Compute the "what changed" diff (stops, time, walking, cost)
- [ ] **M11.5** Build the revision panel, quick-change chips and diff view
- [ ] **M11.6** Add approve (exact version and option) and version history in the web app
- [ ] **M11.7** Add outbound booking links with honest states
- [ ] **M11.9** Test concurrent revisions and approvals: stale base refused, approved version kept
- [ ] **M11.8** Add the Playwright test: "less walking on day 2" → approve → reopen, plus cross-user denial

### M12. Evaluation, hardening and deployment
- [ ] **M12.1** Build the persona generator and simulated-user runner (development and held-out personas)
- [ ] **M12.2** Add graders: deterministic checks first, and an LLM judge checked against human labels
- [ ] **M12.3** Add the regression suite to CI and a manual full-eval workflow with a fixed budget
- [ ] **M12.4** Add metamorphic solver tests (only where their assumptions hold)
- [ ] **M12.5** Measure p50/p95 time to first result, completion and revision under a stated load
- [ ] **M12.6** Add the provider usage and failure dashboard; friendly errors for every failure
- [ ] **M12.7** Run the final accessibility audit (keyboard, contrast, screen reader, reduced motion)
- [ ] **M12.8** Decide from measurements whether the worker needs scaling (more processes, or Celery); add only if needed
- [ ] **M12.12** Rehearse backup and restore, deployment rollback, and the load effect on RagBot
- [ ] **M12.9** Deploy behind TLS on the server next to the existing services, with scoped credentials
- [ ] **M12.10** Build the Lab → Evals page
- [ ] **M12.11** Run the Web Beta with a few testers on their own trips and collect feedback

## Research track — TravelPlanner (side track, after Web Alpha)

### R1. TravelPlanner rules, setup and baseline
- [ ] **R1.0** Check the benchmark rules against our method and write down what is allowed; ask the maintainers only with hooman's approval
- [ ] **R1.5** Set up the separate `roamate-tp` environment (Python 3.9) with a pinned dataset, scorer and run manifest
- [ ] **R1.1** Download the TravelPlanner dataset and sandbox database, with checksums recorded
- [ ] **R1.2** Run the official validation scorer in the manual evaluation workflow
- [ ] **R1.3** Record the published baselines by split, mode and scorer
- [ ] **R1.4** Write the paper claim and experiment plan (for approval)

### R2. TravelPlanner adapter and solver mode
- [ ] **R2.1** Design: TravelPlanner constraint spec schema (for approval, within the R1.0 rules)
- [ ] **R2.2** Write the query → constraint spec adapter through the model gateway (test queries only if R1.0 allows it)
- [ ] **R2.3** Load the sandbox data (flights, distances, restaurants, attractions, accommodation)
- [ ] **R2.4** Write the CP-SAT model for multi-city, day-level plans, with input checks and time limits
- [ ] **R2.5** Write the independent validator for TravelPlanner's commonsense and hard constraints
- [ ] **R2.6** Render plans to the official submission JSONL
- [ ] **R2.7** Score the 180 validation queries with the method frozen

### R3. Experiments and submission
- [ ] **R3.1** Run the validation set with fixed single models, and the fallback chain as a separate system
- [ ] **R3.2** Build the results table (pass rates, plan quality, cost per solved query, run IDs) on Lab → Evals
- [ ] **R3.3** Optional: run the TripScore benchmark after checking its rules
- [ ] **R3.4** Submit the test set once to the official leaderboard, only if R1.0 allows it
- [ ] **R3.5** Write the workshop-paper draft with only the claims the results support

## Phase 7 — Mobile app

### M13. Mobile app core
- [ ] **M13.1** Design: mobile screens and navigation (for approval), using the M6.11 map and sign-in check
- [ ] **M13.2** Move shared TypeScript code (API types, formatting, labels) into `shared/`
- [ ] **M13.3** Set up the Expo app with Expo Router, sign-in with a token in secure storage, and the API client
- [ ] **M13.4** Build trip intake on mobile
- [ ] **M13.5** Build planning progress on mobile (reconnects after the app was in the background)
- [ ] **M13.6** Build the trip view tabs: Story, Timeline, Map, Budget
- [ ] **M13.7** Build revision and approval on mobile
- [ ] **M13.9** Test sign-in, API access over HTTPS and the local map on a real device
- [ ] **M13.8** Run the brief's demo flow in the Android emulator, plus an expired session and a failed provider

### M14. Mobile polish and tester release
- [ ] **M14.1** Make saved trips viewable offline, per account
- [ ] **M14.6** Test that sign-out and account switch remove the other account's offline trips
- [ ] **M14.2** Check reduced motion, screen readers and slow networks
- [ ] **M14.3** Add app icon, splash screen and store-ready names
- [ ] **M14.4** Ship internal test builds with EAS (Android, then iOS), with no secrets in the app
- [ ] **M14.5** Collect tester feedback and plan the next phase
