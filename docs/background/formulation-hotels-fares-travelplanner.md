# Roamate: base formulation, hotels, utility, fares and TravelPlanner

**Date:** 24 October 2026
**Follows:** [solver-retrieval-evaluation.md](solver-retrieval-evaluation.md)
**Runnable example, updated:** [solver_example.py](solver_example.py) now also picks a hotel and prices taxis with a metered tariff.

---

## 1. Is the objective a known formula?

**Yes. Roamate's model is a known problem family with a few standard extensions,** so you can cite a lineage instead of presenting an invented formula.

### The stepping stone: Team Orienteering Problem with Time Windows (TOPTW)

This is the canonical model for multi-day tourist itineraries (Vansteenwegen et al. 2009; surveyed for tourism by Gavalas et al. 2014 and, most recently, Shen et al. 2025). Places $i = 2..N{-}1$, start node $1$ and end node $N$ (the hotel), days $d = 1..m$, score $S_i$, visit time $T_i$, travel time $t_{ij}$, opening window $[O_i, C_i]$, day length $T_{\max}$:

$$
\max \sum_{d=1}^{m} \sum_{i=2}^{N-1} S_i \, y_{id}
$$

subject to

$$
\sum_{d}\sum_{j} x_{1jd} = \sum_{d}\sum_{i} x_{iNd} = m
\qquad\text{(every day leaves and returns to the hotel)}
$$

$$
\sum_{i} x_{ikd} = \sum_{j} x_{kjd} = y_{kd}, \qquad \sum_d y_{kd} \le 1
\qquad\text{(flow; each place at most once)}
$$

$$
s_{id} + T_i + t_{ij} - s_{jd} \le M(1 - x_{ijd}), \qquad O_i \le s_{id} \le C_i
\qquad\text{(timing; opening hours)}
$$

$$
\sum_{i}\Big(T_i\, y_{id} + \sum_j t_{ij}\, x_{ijd}\Big) \le T_{\max}
\qquad\text{(day length)}
$$

### The variants that match Roamate's extras

| Roamate needs | Known variant | Reference |
| --- | --- | --- |
| Budget on admissions, opening hours that differ by day | **Multiconstraint TOP with Multiple Time Windows (MC-TOP-MTW)**: extra knapsack-style constraints and several windows per place | Souffriau, Vansteenwegen et al., *Transportation Science* (2013) |
| Choosing the hotel(s) | **Orienteering Problem with Hotel Selection (OPHS)** | Divsalar, Vansteenwegen, Sörensen, Cattrysse, *EJOR* (2014) |
| Hotel selection plus a money budget | **OPHS with budget constraint** | Päprer & Zipfel, *OR Proceedings 2022* (2023) |
| Transit and traffic times that depend on the hour | **Time-dependent OP / TOPTW** | Covered in the Shen et al. survey |

### What Roamate adds on top

The only non-textbook part of the objective I proposed is the **weighted penalty terms** (travel time, money, walking, day balance). That is the standard *generalized cost* idea in vehicle routing; Google's Route Optimization API uses the same structure (a penalty for each skipped stop plus costs per hour and per kilometer). So the honest description for a paper is:

> A multi-day MC-TOP-MTW with optional hotel selection, solved per scenario with a generalized-cost objective $\max\ \alpha\sum u_i y_i - \beta\,\text{time} - \gamma\,\text{money} - \delta\,\text{walking}$, where the weight vector defines the scenario.

### How Hao et al. (NAACL 2025) fits

Their formulation is a **different kind of model**, and it's the right stepping stone for the TravelPlanner work in section 5, not for the intra-day schedule:

- It is **satisfiability, not optimization**: the LLM writes Z3 code with integer index variables (which city, which flight, which hotel per city, which restaurant per meal, which attraction per day), plus a running `spent ≤ budget` assertion. Any plan that satisfies all constraints counts; there's no objective.
- It plans at **day level**: no clock times, opening hours or travel times within a day.
- When unsatisfiable, it extracts the **unsat core** with Z3 and has the LLM propose a relaxation. Roamate should copy this idea for its "explain the conflict" feature.

So Roamate's model is richer inside a city (times, routes, effort), and Hao's is the reference for multi-city, booking-level choices.

---

## 2. Is node 0 (the hotel) given, or something we suggest?

**Both, depending on the traveler.** In the formula, the hotel is the start and end of every day. Two cases:

1. **Already booked** (as in the brief's own example): the hotel is an input, a fixed start and end point. That's what the earlier example did.
2. **"Suggest a hotel with breakfast and a pool, near the metro"**: the hotel becomes a **decision variable**. Where you sleep changes every day's travel, and its price uses the same budget as the activities, so it should be chosen *together* with the itinerary, not separately.

### How to choose the hotel (recommendation)

Use **filter, shortlist, solve per candidate**. It's simple, exact over the shortlist, and runs in parallel:

1. **Extract preferences**: the LLM turns "breakfast, pool would be nice, quiet area, under €120 a night" into a structured `HotelPreferences`: *required* features (hard filter), *nice-to-have* features with weights, price cap, area.
2. **Filter** hotels that miss a required feature or the price cap.
3. **Shortlist** the top 5–10 by a hotel score (rating, feature match, location).
4. **Solve the whole trip once from each shortlisted hotel**, giving the solver the money left after paying for the nights.
5. **Pick the best total**: trip objective + money weight × hotel cost − hotel bonus (features, rating). Show the top two or three so the traveler sees the trade-off.

Mathematically this enumerates the hotel choice $z_h$ with $\sum_h z_h = 1$; a single model with $z_h$ inside is possible in CP-SAT, but OR-Tools routing needs fixed start points, and enumeration is easier to explain and debug. Moving between hotels or cities during a trip is the OPHS case above; leave it for later.

### Actual output from the updated example

Required: breakfast. Nice to have: pool. €500 total for 2 nights plus the trip.

```
=== Hotel choice (Balanced weights) ===
Central Palace  nights 380 EUR | trip objective  1164 | total    1435
Riverside Inn   nights 220 EUR | trip objective  1143 | total    1275
Airport Lodge   nights 140 EUR | trip objective  1258 | total    1318
Hill Hostel     skipped: missing breakfast
Chosen: Riverside Inn

=== Balanced from Riverside Inn ===
Day 1: 09:19 Old Market Hall -> 10:58 Tile Museum -> 13:46 Modern Gallery -> 15:30 Riverside Walk  (back 16:36)
Day 2: 09:31 Sunset Viewpoint -> 10:31 Castle Hill -> 13:18 Art Museum -> 15:35 Cathedral  (back 16:36)
Spent 140 EUR of 280 | utility 560 | skipped: Food Tour, Botanical Garden
```

The luxury hotel leaves only €120 for activities, so the trip has to skip paid places. The cheapest hotel is far out, so every day starts with a long ride. The middle option wins. This joint trade-off ("the cheap hotel costs you in travel time") is something a chat answer doesn't compute.

**Data note:** hotel locations and some features come from OpenStreetMap, but nightly prices need a provider (an affiliate or booking API). For the prototype, store a labeled price estimate per hotel and show it as an estimate.

---

## 3. Is $u_i$ the retrieval score?

**No. The retrieval score is one input to $u_i$, not $u_i$ itself.**

| | Retrieval score | Utility $u_i$ |
| --- | --- | --- |
| Question it answers | Is this place relevant to the words of the request? | How much is visiting this place worth to *this* traveler? |
| Comes from | Embedding similarity, keyword match, reranker | A scoring model over several features |
| Used for | Deciding which ~50 places reach the solver | The solver's reward for visiting a place |
| Comparable across queries? | No (raw scores aren't calibrated) | Yes, by design |

A first, hand-written version:

$$
u_i = 100 \cdot \big(w_1\,\text{interest\_match}_i + w_2\,\text{rerank}_i + w_3\,\text{quality}_i + w_4\,\text{iconic}_i\big)
$$

- **interest_match**: the traveler's interest weights against the place's tags.
- **rerank**: the reranker score, normalized to 0–1 within the query.
- **quality**: a Bayesian-averaged rating, so 4.9 from 8 reviews doesn't beat 4.6 from 20,000.
- **iconic**: landmark status for first-time visitors.

Two modelling rules:

- **Don't put price or duration into $u_i$.** The solver already charges for money and time; counting them twice skews the trade-off.
- **Additive utility ignores repetition**: three museums in a row each keep full value. Add simple caps (at most two museums per day) as constraints; a diminishing-returns objective is a good later research extension.

Version 2 learns the weights from behavior (saves, approvals, stops users remove) with learning-to-rank, and must beat the hand-written version on held-out data before it replaces it.

---

## 4. Where taxi fares from i to j come from

**Compute them from the city's metered tariff and a road-distance matrix; don't call a ride-hailing API per leg.**

$$
\text{fare}_{ij} = F + a \cdot \text{km}_{ij} + b \cdot \text{min}_{ij}, \quad\text{times a night, holiday or large-vehicle factor where the tariff has one}
$$

- **Tariff ($F$, $a$, $b$):** Taxi fares are regulated, so the tariff is public. Portugal's transport regulator (AMT) published a new national taxi fare model in June 2026 with a flag fall plus per-km and per-minute charges, and surcharges for holidays and larger vehicles. Lusa's report cites €0.58/km and €0.28/min but doesn't make clear whether those are the old or the new rates, so the real values should be read from the official tariff and stored in a `city_tariff` config, one row per city and period.
- **Road km and minutes:** a self-hosted **OSRM** (or Valhalla) server built from the same OpenStreetMap extract as the catalog returns a full distance and duration matrix for all candidate pairs in one call. It works without internet, which fits the plan's offline requirement. OSRM doesn't model live traffic, so apply a time-of-day factor (rush hour ×1.3, for example) and show the fare as a range.
- **Ride-hailing (Uber, Bolt):** Uber has a price-estimate endpoint that returns a low–high range per product, but I couldn't confirm what access a new app gets today, and Bolt has no public estimate API. Don't build on them; at most, collect a few dozen real quotes to **calibrate** $F, a, b$ with a linear regression. That's a small, honest ML piece with a measurable error.
- **Public transport:** travel times from GTFS feeds through a self-hosted router (OpenTripPlanner). Fares are often flat or a day pass. A day pass makes cost **non-additive** (pay once if you ride at all that day), which the model handles with one binary per day, $\text{pass}_d \ge x_{ijd}$ for transit legs.
- **Choosing the mode per leg:** because modes don't carry over between legs in our model (you don't have to "keep" a taxi), choosing for each pair $(i,j)$ the mode with the lowest generalized cost $\beta t + \gamma m + \delta w$ is exact, with two exceptions: the day pass above, and tight budgets where a slower, cheaper mode is needed. For those, offer the solver both options as parallel arcs.

The example now prices taxi legs this way (with illustrative tariff values).

---

## 5. TravelPlanner: adding it to the evaluation, and the paper question

### What TravelPlanner tests

- 1,225 queries (train 45, validation 180, test 1,000), 3/5/7-day US trips across 1–3 cities, with a closed sandbox of about four million records (flights, distances, restaurants, attractions, accommodations).
- Plans are **day level**: city, transport, three meals, attractions, accommodation. Accommodation choice *is* part of the plan, with room type, house rules and minimum nights.
- Scoring: delivery rate, commonsense pass rate, hard-constraint pass rate, **final pass rate**. Validation can be scored locally with the official script; test results go through the official Hugging Face leaderboard. Code is MIT licensed.

### How Roamate plugs in

Roamate's architecture already matches the winning pattern: LLM → structured constraints → solver → validator.

1. **Adapter, input side:** the intake LLM converts each query into a Roamate constraint spec (a JSON schema), not into solver code. Hao et al. have the LLM *write Z3 code*; a schema is more robust for small and free models.
2. **TravelPlanner solver mode:** a CP-SAT model for the multi-city, day-level structure (city order, inter-city transport, one accommodation per city, meals, attractions, budget), reusing the validator idea.
3. **Adapter, output side:** render plans into the official submission JSONL.
4. **Run validation locally**, iterate, then submit the test set once to the leaderboard.

### Can it become a paper? Honest assessment

**Feasibility alone is nearly solved**, so "we pass TravelPlanner" isn't a contribution. On the validation set, a 2026 preprint reports the Hao et al. solver approach reproduced at 85%, and its own method at 91.7% (two-stage) and 94.4% (sole-planning). A paper needs a claim beyond pass rate. Three credible angles, in order of how naturally Roamate produces them:

1. **Quality, not just feasibility.** Existing solver approaches return *any* valid plan. Roamate optimizes. Report the same pass rate plus cost, rating and effort of the plans, and show that satisfiability-only methods leave quality on the table. TripScore (Trip.com, Stanford and Chongqing University, 2025) argues TravelPlanner lacks soft constraints and preferences, so it's a natural second benchmark for this.
2. **Small, free models.** Schema-constrained extraction plus a solver might reach high pass rates with a local Gemma or free-tier models, where earlier work used GPT-4-class models. Cost per solved query and pass rate per model is a clean, useful result.
3. **A city-level benchmark with time windows.** TravelPlanner has no clock times, opening hours or travel times within a day. A small public benchmark built from Roamate's Lisbon catalog (queries, hidden personas, a checker) would be a dataset contribution; ChinaTravel (ICLR 2026) is the closest existing benchmark to compare against.

A workshop paper is the realistic first target. Decide the claim before running experiments, keep the test-set submission to one final run, and follow the benchmark's rules against tuning on validation or test.

### Where it goes in the plan

Proposed for the plan (sent to the plan thread, which owns those files):

- **A research track after Web Alpha**, alongside M11–M12: download the dataset and database, run the official validation scorer in CI's manual workflow, build the adapter, the CP-SAT TravelPlanner mode, and the results table per model.
- **Data design additions for the M0 approvals:** `HotelPreferences` (required, nice-to-have, price cap, area) and an optional fixed hotel in `TripBrief`; a `hotel` table with features and a labeled price estimate; a `city_tariff` table; a self-hosted OSRM service on the server; utility feature columns kept separate from retrieval scores.
- **Solver steps:** hotel shortlist and per-hotel solve; tariff-based fares; day-pass binary; unsat-core style conflict explanations.

---

## Sources

- Vansteenwegen et al., *Iterated local search for the team orienteering problem with time windows*, Computers & OR (2009), and Gavalas et al., *A survey on algorithmic approaches for solving tourist trip design problems*, J. Heuristics (2014): cited from the survey literature; formulation as commonly stated.
- Shen, Zhou, Lei, Wu, *A survey of the orienteering problem* (2025): https://arxiv.org/abs/2512.16865
- Souffriau et al., *The Multiconstraint Team Orienteering Problem with Multiple Time Windows*, Transportation Science: https://pubsonline.informs.org/doi/10.1287/trsc.1110.0377
- Divsalar et al., *A memetic algorithm for the orienteering problem with hotel selection*, EJOR 237(1) (2014): https://ideas.repec.org/a/eee/ejores/v237y2014i1p29-49.html
- Päprer & Zipfel, *Low Budget Traveling: The Orienteering Problem with Hotel Selection and Budget Constraint* (2023): https://fis.tu-dresden.de/portal/en/publications/low-budget-traveling-the-orienteering-problem-with-hotel-selection-and-budget-constraint(ab5162ca-b466-4f87-aa46-217e1e376965).html
- Hao et al., *Large Language Models Can Solve Real-World Planning Rigorously with Formal Verification Tools* (NAACL 2025): https://arxiv.org/abs/2404.11891
- Xie et al., *TravelPlanner* (ICML 2024): https://arxiv.org/abs/2402.01622 · code and data: https://github.com/OSU-NLP-Group/TravelPlanner · leaderboard: https://huggingface.co/spaces/osunlp/TravelPlannerLeaderboard
- *Decoupled Travel Planning with Behavior Forest* (2026 preprint, results table): https://arxiv.org/abs/2604.21354
- Qu et al., *TripScore* (2025): https://arxiv.org/abs/2510.09011
- *ChinaTravel* (ICLR 2026): https://arxiv.org/abs/2412.13682
- Google Maps Platform, *Route Optimization cost model*: https://developers.google.com/maps/documentation/route-optimization/cost-model
- Lusa via AMAN Alliance, new Portuguese taxi fare model (13 June 2026): https://aman-alliance.org/Home/ContentDetail/104056
- Uber, *Price estimates endpoint*: https://developer.uber.com/docs/riders/references/api/v1.2/estimates-price-get
- OSRM Table API overview: https://blog.afi.io/blog/osrm-table-api-free-and-open-source-distance-matrix-api.md
