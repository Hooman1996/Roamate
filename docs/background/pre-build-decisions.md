# Roamate: four decisions before the build

**Status:** historical background, not binding. Where it differs from the [implementation plan](../plan/implementation-plan.md), the plan wins (plan §0).

**Date:** 20 October 2026
**Basis:** *Roamate Product Vision and Business Review Brief* (18 Oct 2026), which fixes the stack (React Native/Expo, FastAPI, LangGraph, PostgreSQL/pgvector, Redis/Celery, OR-Tools), the real-media-first rule, the solver-plus-validator design and a prototype scoped to one local demo user. Market facts below come from dated public sources listed at the end; no competitor was tested hands-on for this note.

| # | Question | Recommendation |
| --- | --- | --- |
| 1 | Pre-curated places and images, or search everything live? | **Hybrid.** A curated, stored catalog for a small number of launch cities, plus a live freshness layer for facts that change (hours, weather, routes, prices). Store what licenses allow; reference what they don't. |
| 2 | Is it multi-agent, and what architecture fits? | **An orchestrated agentic workflow, not a free-roaming multi-agent system.** One LangGraph graph with a few bounded LLM nodes, deterministic solver and validator nodes, inside a modular-monolith backend. |
| 3 | How can the build teach professional implementation? | **Build in ten vertical-slice milestones**, each with a design record, tests and a measured result, and use AI coding agents as a reviewed team while you write the core pieces yourself. |
| 4 | Is it worth doing when ChatGPT and Claude can plan trips? Is "social" an advantage? | **Yes as a learning project, and yes as a product only if it wins on what chat is bad at:** checked feasibility, a persistent shared trip object, and group decisions. Private group planning and remixable shared trips are an advantage; a public feed is not, at least early. |

---

## 1. Curated catalog or live search?

### Recommendation

Use a **curated catalog for one to three launch cities**, enriched with **live, cached lookups for volatile facts** at planning time. Live search is a fallback for places outside the catalog, and its results are labeled as less verified.

### Why not "search everything live"

- **The solver needs structured inputs.** OR-Tools needs, per candidate place, coordinates, opening windows, a typical visit duration, a cost estimate and a category. Live web or places search returns these incompletely and inconsistently; you would spend every request re-cleaning the same data.
- **Reproducibility and evaluation.** The brief requires measured violation rates and a revision flow tested on identical requests. A plan built from whatever a search returned today cannot be re-run tomorrow for comparison. A versioned catalog makes evals possible.
- **Latency and cost.** Every planning run would fan out dozens of place, photo and detail calls. Free tiers run out fast and time to first result grows.
- **Media quality and honesty.** The brief requires real, attributable media and distinguishes "this exact venue" from "generic city photo". That labeling is easy for media you vetted once and hard for images scraped live.

### Why not "everything pre-downloaded"

Opening hours, closures, admission prices, weather and transit change. The brief requires every recommendation to carry a source and an update time, and forbids silently showing fixture data as live.

### How to split the data, by how fast it changes

| Volatility | Examples | Where it lives | Refresh |
| --- | --- | --- | --- |
| Stable | Coordinates, category, description, typical visit duration, neighborhood, interest tags, embeddings | Postgres catalog + pgvector | On ingestion; manual review |
| Slow | Opening hours, admission price, accessibility notes | Postgres, with `source` and `fetched_at` per field | Scheduled re-check (e.g. weekly Celery job) and re-check of the chosen stops at plan time |
| Live | Weather, route times, events, availability, fares | Not stored as truth; Redis cache with a TTL | Fetched per plan |

Each field keeps its provenance (`source`, `fetched_at`, `confidence`), which is exactly what the Budget and Place-details views need to show "estimated vs checked vs unknown".

### Provider terms decide what you may store

This matters more than it looks, and it should shape the data model now:

- **Google Places** lets you store place IDs indefinitely; coordinates may be cached up to 30 days; other content, including photos, may not be pre-fetched or stored, and photos and reviews require author attribution. So with Google you store a reference and fetch the photo when you render it.
- **Open data** (OpenStreetMap, Overture Maps, Wikidata) can be stored and redistributed under their licenses with attribution. These are good foundations for the stored catalog.
- **Wikimedia Commons** images can be stored and shown if you keep each file's license and author and display the credit; many are CC BY-SA.
- Your own or explicitly licensed photos are the cleanest option for hero images in launch cities.

Model media as a `MediaAsset` with `kind` (exact venue / area / generic city / AI-generated decorative), `license`, `author`, `source_url`, `storable: bool`. That single table enforces the real-media-first rule and the legal limits at once.

### For the prototype

Build the catalog for **one city**: ingest OSM/Overture places and Wikidata facts, attach Wikimedia media, hand-review the top ~150 places (durations, tags, hero image), embed descriptions into pgvector. Add live weather and routing behind provider adapters, plus a recorded "demo mode" dataset that is visibly labeled. Growing the catalog later is the same pipeline run on a new city.

---

## 2. Is it multi-agent, and which architecture?

### Recommendation

Call it what it is: **an orchestrated agentic workflow with specialist LLM steps and deterministic tools.** Build it as a single LangGraph `StateGraph` where most nodes are plain code, a few are LLM calls with structured outputs, and only one or two are true tool-using agent loops with step limits. Do not build agents that converse with each other.

This is not a downgrade. The brief already says "multi-agent architecture is an implementation choice; customers experience its value only through better outcomes", and that the solver and validator, not the LLM, own schedules and budgets. Anthropic's published guidance on building agents makes the same point: start with the simplest composable workflow and add autonomy only where the path genuinely can't be predicted. Autonomous agent-to-agent chatter makes runs slower, costlier, non-reproducible and hard to evaluate, which conflicts with the brief's validator and measurement goals.

### Where an LLM belongs and where it doesn't

| Step | Type | Why |
| --- | --- | --- |
| Intake: free text → `TripBrief` | LLM, structured output + clarification loop | Language understanding; may ask questions |
| Brief confirmation | Human-in-the-loop interrupt | Brief requires the user to correct the interpretation |
| Candidate retrieval | Code: SQL filters + pgvector similarity, then live enrichment | Deterministic and testable |
| Curation: rank candidates and write "why this fits you" | LLM, structured output | Taste and explanation |
| Long-tail research (place not in catalog) | Tool-using agent, bounded steps and budget | The only genuinely open-ended search |
| Scheduling ×3 scenarios | OR-Tools, parallel fan-out | Math, not language |
| Validation | Deterministic code | Must be independent of whoever produced the plan |
| Repair loop | Code routes validator diagnostics back to curation or solver, max N tries | Explains infeasibility instead of hiding it |
| Story chapters | LLM per day, parallel, constrained to the validated itinerary | Narrative only; cannot change the schedule |
| Media resolution | Code | Licensing and labels are rules |
| Revision: "less walking on day two" → constraint delta | LLM, structured output | Then re-solve with locked stops, validate, diff |

Rule of thumb for the codebase: **LLMs propose structured data; code checks it; only code writes trip state.** Every LLM output is a Pydantic model; every number the user sees comes from the solver or the budget calculator.

### System shape

```
Expo app (Story / Timeline / Map / Budget views)
   │  REST (OpenAPI-generated TS client) + SSE for progress events
FastAPI  ── modular monolith: trips, catalog, planning, media, users
   │  enqueue planning/revision job
Celery workers ── run the LangGraph graph
   │      ├─ LLM provider adapter
   │      ├─ places / routing / weather / media adapters (Redis TTL cache)
   │      └─ OR-Tools solver, validator
PostgreSQL ── trip versions (source of truth), catalog, pgvector,
              LangGraph checkpoints
Redis ── Celery broker, provider cache, progress pub/sub
```

Choices worth making explicitly:

- **Modular monolith, not microservices.** One deployable backend with clear module boundaries. Splitting services teaches ops pain, not architecture, at this size.
- **Trip versions are immutable rows.** A revision creates a new version with a parent pointer; approval marks one version. This gives the brief's "original plan and approved revisions remain recoverable" for free, and later group editing builds on it.
- **Progress is real graph events.** Each node emits a progress event over SSE, which gives the brief's "watch useful progress" step honestly.
- **Graph checkpointing in Postgres** so a crashed worker resumes and human-in-the-loop interrupts survive restarts.
- **Observability from day one:** trace each graph run (an LLM tracing tool such as Langfuse or LangSmith, plus OpenTelemetry) with token cost per run.

### When real multi-agent would earn its place

Later, group planning could use one "advocate" per member to argue preferences, but even there the better design is to collect each member's constraints and let the solver optimize a multi-objective plan, with the LLM explaining trade-offs. Revisit multi-agent only if an eval shows a measurable gain.

---

## 3. Structuring the build so it teaches professional practice

### Recommendation

Treat the project as a **curriculum of ten vertical-slice milestones**. Each milestone ends with something runnable and the same four artifacts professionals produce: a short architecture decision record (ADR), automated tests, a measured number, and a one-paragraph retro. Use AI coding agents as a team you direct and review, but write the core pieces yourself the first time.

### The milestones

| # | Milestone | You learn | Done when |
| --- | --- | --- | --- |
| 0 | Foundation: monorepo (`apps/mobile`, `services/api`, `packages/schemas`), Docker Compose, uv, ruff, mypy, pytest, pre-commit, GitHub Actions CI | Reproducible environments, CI | `docker compose up` + green CI on an empty app |
| 1 | Domain model and catalog: Pydantic models (`TripBrief`, `Place`, `MediaAsset`, `Itinerary`, `TripVersion`), Alembic migrations, ingestion of one city | Data modeling, ETL, provenance, licensing | Catalog of one city loaded with sources and media licenses |
| 2 | Solver and validator, no LLM yet: OR-Tools routing with time windows, budget, rest; validator with property-based tests (Hypothesis) | Constraint modeling, test-first design | 50 fixed requests solved; validator finds 0 violations; infeasible cases explained |
| 3 | API and background jobs: FastAPI endpoints, Celery job, SSE progress, idempotent job submission | Async architecture, API design | Plan request runs end-to-end from curl |
| 4 | First LLM node: intake → `TripBrief` with structured output, prompt versioning, a 30-case eval set | Structured output, evals, prompt management | Eval score recorded and tracked in CI |
| 5 | LangGraph orchestration: full graph, checkpoints, human-in-the-loop confirm, scenario fan-out, repair loop | Agent orchestration, state machines, retries | One request yields 3 validated scenarios, resumable after a worker kill |
| 6 | Retrieval: embeddings + hybrid search over the catalog | RAG done properly | Retrieval recall@k measured on a labeled set |
| 7 | Mobile app: Expo, four synchronized views, map, TanStack Query | Mobile architecture, typed API clients | Brief's demo flow works in the Android emulator |
| 8 | Story and media: chapters bound to the itinerary, media labels, optional generated cover in the background | LLM UX, graceful degradation | Image-generation failure doesn't block the itinerary |
| 9 | Revision flow: constraint delta, locks, re-solve, visual diff, version history | Versioned state, diffs | "Less walking on day two" passes its tests |
| 10 | Hardening: tracing, cost budgets per run, rate limits, caching, demo mode, p50/p95 timing | Production readiness | Latency and failure rates reported as the brief asks |

The order is deliberate: **the deterministic core (solver, validator, data) comes before any LLM**, so when you add AI you can measure whether it improved anything. That is the main habit that separates professional AI systems from demos.

### Using AI agents as a team, without outsourcing the learning

You suggested a multi-agentic setup that teaches you. The most useful version is a development team of AI agents with defined roles, where you are the tech lead:

- **Architect role:** for each milestone, ask an agent to draft options and trade-offs; you write the ADR and make the call.
- **Implementer role:** delegate boilerplate (CRUD endpoints, migrations, UI scaffolding, test fixtures).
- **Write by hand first:** the OR-Tools model, the validator, one LangGraph node, the trip-version schema. These are the concepts you are here to learn; ask an agent to review your version afterwards.
- **Reviewer role:** run an AI code review on every pull request and answer each finding, even when you disagree.
- **Tester role:** ask an agent to attack your validator with edge cases you didn't think of.
- **Work through pull requests**, even solo: small PRs, CI green, review comments resolved. That's the workflow you'd use on any team.

I can act as any of these roles in this project, open the repository and draft the milestone plans when you're ready to start.

---

## 4. Is it worth doing, and is "social" an advantage?

### Recommendation

**As a learning project: clearly yes.** The skills it exercises (agent orchestration, evals, constraint solving, data pipelines with licensing, mobile app architecture) are the ones in demand, and a general assistant cannot learn them for you.

**As a product: yes only if you compete on what a chat transcript is bad at,** because "AI writes an itinerary" is now a commodity:

- ChatGPT has had an Expedia app since October 2025 that shows live hotel and flight prices on interactive maps inside the chat, and group chats with up to 20 people since November 2025, with trip planning as a showcased use.
- Google Search AI Overviews generate itineraries with photos, reviews and a map that you can save as a Google Maps list, and Maps can turn travel screenshots into saved places.
- Dedicated planners already cover much of Roamate's surface: Mindtrip (visual planning, shared trips, imports from videos and saved Google Maps places), Layla (conversational planning with booking), Wanderlog (collaborative editing and expenses), Feedtrip (TikTok/Instagram saves turned into mapped stops).

### Where Roamate can genuinely beat a general assistant

1. **Checked feasibility.** A chat answer can state opening hours and travel times confidently and be wrong. A solver plus an independent validator that shows "checked / estimated / unknown" per item is a measurable difference. The brief already plans to measure violation rates on identical requests; run that comparison against ChatGPT, Gemini and Mindtrip early, because it is the core claim.
2. **A persistent, structured trip object.** A chat produces text; Roamate produces a versioned trip with synchronized story, timeline, map and budget that can be revised without regenerating everything.
3. **Group decisions.** A group chat with an AI is good for discussion but has no votes, locks, permissions or "who agreed to which version". That structure is real product value.
4. **Explicit trust rules**: media labels, budget scope and booking states that never pretend.

These leads are narrow and the big assistants will keep closing them. One strategic consequence: rather than only competing with ChatGPT and Claude, Roamate's planning engine could later also be offered inside them (as an app or MCP server), which the provider-adapter design already makes possible.

### Is being social-media-like a positive?

**Partly.** It depends on which "social" you mean:

| Social feature | Advantage? | Why |
| --- | --- | --- |
| Private group planning (invite, vote, lock, approve) | **Strong** | Real coordination pain; every invite brings a new user; general assistants lack structured group decisions |
| Shareable story links posted to existing networks | **Strong** | Uses Instagram/WhatsApp/TikTok distribution instead of competing with it |
| "Make this trip mine" remix | **Strong if it works** | Turns any shared trip into a re-checked personal plan; the check is the part chat can't do reliably |
| Post-trip structured feedback ("needed 3 hours, had stairs") | **Strong, long term** | Proprietary ground truth that improves durations and accessibility data; an LLM doesn't have it |
| Public feed, likes, follows, creators | **Weak early** | Cold start, moderation cost, and inspiration already lives on TikTok and Instagram; Feedtrip and Mindtrip import from there |

So the advantage of "social" is not engagement but **distribution through groups and shared links, plus data no general model has**. Build private groups, share links and remix first, as the brief's own section 7 already suggests, and add a public feed only after those loops show real conversion.

---

## Sources

- Google, *Policies and attributions for Places API*: https://developers.google.com/maps/documentation/places/web-service/policies
- Open Places API blog, *Can you store Places API results? Every caching policy, compared* (validated 4 Aug 2026): https://openplacesapi.com/blog/can-you-store-places-api-results
- MediaWiki, *Wikimedia APIs / Content reuse*: https://www.mediawiki.org/wiki/Wikimedia_APIs/Content_reuse
- Anthropic, *Building effective agents*: https://www.anthropic.com/research/building-effective-agents
- Expedia newsroom, *New Expedia app in ChatGPT* (6 Oct 2025): https://www.expedia.com/newsroom/smart-trip-planning-new-expedia-app-in-chatgpt-to-plan-your-trip
- TechRadar, *ChatGPT enters the group chat globally* (21 Nov 2025): https://www.techradar.com/ai-platforms-assistants/chatgpt/chatgpt-enters-the-group-chat-globally
- TechCrunch, *Google rolls out new vacation planning features to Search, Maps and Gemini* (27 Mar 2025): https://techcrunch.com/2025/03/27/google-rolls-out-new-vacation-planning-features-to-search-maps-and-gemini
- Unite.AI, *Best AI tools for travel planning* (updated 5 Oct 2026): https://www.unite.ai/best-ai-tools-for-travel-planning/
