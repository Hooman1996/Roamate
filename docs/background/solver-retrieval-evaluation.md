# Roamate: the solver, POI search and persona-based evaluation

**Date:** 20 October 2026
**Companion to:** [pre-build-decisions.md](pre-build-decisions.md)
**Runnable example:** [solver_example.py](solver_example.py) (`pip install ortools`, then `python3 solver_example.py`; all data is fictional)
**Update, 24 Oct 2026:** the published lineage of this formulation, hotel selection, how $u_i$ differs from the retrieval score, taxi fares and the TravelPlanner plan are in [formulation-hotels-fares-travelplanner.md](formulation-hotels-fares-travelplanner.md). The example's Comfort plan now uses a metered taxi tariff, so its output below changed slightly.

---

## 1. How a non-LLM node can generate a scenario

A **scenario is the solution of an optimization problem**, not a piece of written text. The planning question "which places, on which day, in which order, at what time, within this budget?" is a combinatorial optimization problem with a precise mathematical form. A solver searches the space of possible itineraries and returns the best one it can find that satisfies every hard constraint.

The solver generates *different* scenarios because you give it different **parameters**: the weights in the objective (how much money, travel time and walking matter), which transport modes are allowed, and how many stops per day the pace allows. Budget, Balanced and Comfort are three parameter vectors fed to the same model. Nothing creative is needed; the creativity lives in the model design.

The work splits like this:

| Part | Who does it |
| --- | --- |
| Understand "relaxed pace, love food, my partner can't walk much" | LLM → structured `TripBrief` |
| Score how well each place fits this traveler (utility) | Ranking model (rules first, then learned) |
| Choose places, days, order and times under constraints | **Solver** (OR-Tools) |
| Check the result independently | Validator (plain code) |
| Explain why a place was chosen or skipped, write the story | LLM, given the solver's output |

"Deterministic" here means: same inputs and same solver settings give the same plan, every number is computed rather than generated, and every constraint is guaranteed by construction. (One practical note: local search with a wall-clock time limit can vary with machine speed; for reproducible tests, stop on a fixed solution or iteration limit instead.)

---

## 2. The formulation

### What problem this is

Itinerary planning is a well-studied problem in operations research called the **Tourist Trip Design Problem**. Its standard model is the **Team Orienteering Problem with Time Windows (TOPTW)**:

- **Orienteering**: you cannot visit everything, so you pick a subset of places that maximizes total reward within a time budget (unlike the travelling salesman problem, which must visit every node).
- **Team**: several routes are planned at once. In Roamate, each **day** is one route starting and ending at the hotel.
- **Time windows**: each place can only be visited while it is open.

Roamate adds a hard money budget, a walking cap, lunch breaks, must-do places and mode choice, which makes it a rich variant of this model. Routing solvers cast it as a **prize-collecting vehicle routing problem**: each place is optional, and skipping it costs a penalty equal to its utility.

### Sets and inputs

- $P$: candidate places (from retrieval, typically 30–60), node $0$ is the hotel
- $D$: trip days
- $u_i$: utility of place $i$ for this traveler
- $s_i$: visit duration of place $i$ (minutes)
- $[o_{id}, c_{id}]$: opening window of place $i$ on day $d$ (closed days have no window)
- $t_{ij}, w_{ij}, m_{ij}$: travel minutes, walking minutes and fare from $i$ to $j$ under the scenario's mode policy
- $p_i$: admission price for the party
- $[S_d, E_d]$: day start and latest return; $L$: lunch window and duration
- $B$: hard budget; $W$: walking cap per day; $K$: max stops per day (pace)
- $M \subseteq P$: must-do places

### Decision variables

- $y_{id} \in \{0,1\}$: place $i$ is visited on day $d$
- $x_{ijd} \in \{0,1\}$: on day $d$ you go directly from $i$ to $j$
- $T_{i} \ge 0$: arrival time at place $i$

### Objective (one scenario $\theta = (\alpha, \beta, \gamma, \delta)$)

$$
\max \;\; \alpha \sum_{i,d} u_i\, y_{id}
\;-\; \beta \sum_{i,j,d} t_{ij}\, x_{ijd}
\;-\; \gamma \Big(\sum_{i,j,d} m_{ij}\, x_{ijd} + \sum_{i,d} p_i\, y_{id}\Big)
\;-\; \delta \sum_{i,j,d} w_{ij}\, x_{ijd}
\;-\; \epsilon \,\big(\max_d \text{len}_d - \min_d \text{len}_d\big)
$$

Collected utility, minus weighted travel time, money and walking, minus a small term that keeps days balanced.

### Constraints

1. Each place at most once: $\sum_d y_{id} \le 1$; must-do places exactly once: $\sum_d y_{id} = 1,\ i \in M$
2. Route structure: each day leaves and returns to the hotel; flow in = flow out = $y_{jd}$ for every visited place
3. Time propagation: $T_j \ge T_i + s_i + t_{ij} - \text{BigM}\,(1 - x_{ijd})$
4. Opening hours: $o_{id} \le T_i$ and $T_i + s_i \le c_{id}$ (finish before closing)
5. Day window: leave after $S_d$, return by $E_d$
6. Lunch: a 60-minute break starting inside $L$ that does not overlap a visit
7. Hard budget: $\sum_{i,j,d} m_{ij} x_{ijd} + \sum_{i,d} p_i y_{id} \le B$
8. Walking: $\sum_{i,j} w_{ij} x_{ijd} \le W$ for every day $d$
9. Pace: $\sum_i y_{id} \le K$ for every day $d$

This is a mixed-integer program. It is NP-hard, so for 30–60 candidates you use a **metaheuristic** (OR-Tools routing: cheapest-arc start plus guided local search, bounded by time) rather than proving optimality. That is why the brief says "a bounded solve does not imply a globally optimal trip".

### How the three scenarios are generated

| Scenario | Weights and policy |
| --- | --- |
| Budget | high $\gamma$ (money), metro allowed, no taxi, 4 stops/day |
| Balanced | equal weights, moderate walking cap, 4 stops/day |
| Comfort | high $\delta$ (walking) and $\beta$ (travel time), taxi allowed, 60 min walking/day, 3 stops/day |

Plus a **diversity constraint**: each later scenario must drop at least two of the places the previous one used, $\sum_{i \in S_{\text{prev}}} y_i \le |S_{\text{prev}}| - 2$. If that makes the problem infeasible, there are no meaningfully different options, and the brief says to say so rather than invent differences.

A more principled version, good for showcasing optimization depth: compute a **Pareto front** over (utility, cost, effort) using the ε-constraint method (maximize utility subject to cost ≤ ε, sweep ε), then pick three well-spread points as the scenarios.

### When there's no feasible plan

The validator and solver report which constraint binds: must-do places whose opening hours clash, a budget below the must-do admissions, a walking cap too tight for the area. Research on LLM-plus-solver travel planning shows solvers can identify the unsatisfiable core of a request and suggest which constraint to relax, which is exactly the brief's "explain the conflict and offer choices" requirement.

---

## 3. What others do

- **Research**: the tourist trip design literature solves TOPTW variants with iterated local search, simulated annealing, constraint programming and, more recently, learned heuristics (pointer networks with reinforcement learning). The 2025 survey by Shen et al. is a good map of the field.
- **Industry routing engines**: Google's Route Optimization API uses the same shape as Roamate's model: every shipment has a `penaltyCost` it incurs if skipped, vehicles have cost per hour and per kilometer, and time windows can be hard or soft with penalty costs. Swap "shipment" for "attraction" and "vehicle" for "day" and it's the same formulation.
- **LLM-only vs LLM-plus-solver**: on the TravelPlanner benchmark (ICML 2024), GPT-4 produced a fully valid travel plan only 0.6% of the time. Hao et al. (NAACL 2025) had the LLM translate the request into constraints for a formal solver and reached 93.9%, against about 10% for o1-preview alone. This is the strongest evidence for Roamate's design choice, and it's a good citation for your portfolio.
- **Consumer AI planners** (Mindtrip, Layla, Wanderlog and others) don't publish how they plan, so I can't say whether they use solvers. That gap is an opportunity: a published, measured solver-backed approach is itself a differentiator.

---

## 4. Worked example (actual output)

Fictional city, 2 days, 2 travelers, 10 candidate places, budget €160 for admissions and local transport, day 09:00–19:00, lunch between 12:00 and 13:00, Castle Hill is a must-do. Interests: food 1.0, architecture 0.8, museums 0.6, views 0.5, nature 0.2. Utility is `100 × interest match × rating/5`.

```
=== Budget ===
Day 1: 09:29 Old Market Hall -> 11:08 Tile Museum -> 14:05 Castle Hill  (back 16:13)
Day 2: 09:31 Riverside Walk -> 10:56 Sunset Viewpoint -> 13:00 Art Museum -> 15:17 Cathedral  (back 16:13)
Spent 108 EUR of 160 | utility 520 | skipped: Food Tour, Botanical Garden, Modern Gallery

=== Balanced ===
Day 1: 09:14 Old Market Hall -> 10:53 Tile Museum -> 13:41 Modern Gallery  (back 15:20)
Day 2: 09:11 Cathedral -> 10:18 Castle Hill -> 13:05 Art Museum  (back 15:24)
Spent 132 EUR of 160 | utility 472 | skipped: Riverside Walk, Food Tour, Botanical Garden, Sunset Viewpoint

=== Comfort ===
Day 1: 10:00 Art Museum -> 12:12 Cathedral -> 14:09 Riverside Walk  (back 15:20)
Day 2: 09:55 Old Market Hall -> 11:29 Castle Hill -> 14:09 Sunset Viewpoint  (back 15:14)
Spent 118 EUR of 160 | utility 435 | skipped: Tile Museum, Food Tour, Botanical Garden, Modern Gallery
```

What to notice:

- **Must-do respected**: Castle Hill is in every scenario. **Budget respected**: all under €160. Lunch is placed between visits, and day lengths are balanced.
- **The Food Tour is never chosen** even though it has the top rating and matches "food": at €130 for two and three hours, its cost outweighs its utility. That's the kind of trade-off the app should explain ("skipped because it would use 80% of your budget").
- **Comfort** takes taxis, keeps walking low and finishes earliest, with fewer stops.
- **Balanced spends more than Budget yet scores lower utility.** That's the diversity constraint at work: Budget took the best set, and Balanced was forced to differ. It shows why the Pareto approach is better than fixed weights plus a diversity cut.
- **The Sunset Viewpoint at 10:56** shows a missing piece: time-of-day preferences. The fix is a time-dependent utility $u_i(T_i)$ or a soft time window with a penalty, which OR-Tools supports.

These imperfections are the useful part of a learning project: each one is a model improvement you can make and measure.

---

## 5. pgvector POI search

**Yes**: places of interest are stored with an **embedding** (a vector representing the meaning of their description, tags and reviews), and you search by similarity in that embedding space. But it is not "just RAG", and it shouldn't be vector-only.

It's best understood the way recommender systems work: **candidate generation, then ranking, then optimization**.

1. **Hard filters (SQL)**: city, open on at least one trip day, price within budget, accessibility requirements, not excluded by the user.
2. **Geo filter (PostGIS)**: within reach of the hotel or the day's area.
3. **Semantic recall (pgvector)**: embed the traveler's interests ("street food, tiled facades, slow mornings") and find the nearest place embeddings by cosine distance.
4. **Keyword recall (Postgres full-text search)**: catches exact names and terms the embedding blurs ("pastéis", "Gaudí").
5. **Fusion and re-ranking**: merge the two lists with reciprocal rank fusion, then score with a ranking model whose features include similarity, rating, popularity, price fit, distance and must-do. That score is the $u_i$ the solver uses.
6. **Top 30–60 candidates go to the solver**, not into a prompt.

A sketch of step 3 combined with steps 1–2:

```sql
SELECT id, name, 1 - (embedding <=> :interest_vec) AS similarity
FROM place
WHERE city_id = :city
  AND price_eur <= :max_price
  AND ST_DWithin(geom, :hotel_geom, 6000)          -- 6 km
  AND NOT (id = ANY(:excluded))
ORDER BY embedding <=> :interest_vec
LIMIT 100;
```

**Where RAG actually appears**: after the solver picks places, their stored descriptions and source facts are retrieved and given to the story LLM, so "why this fits you" and the day chapters are grounded in stored evidence instead of the model's memory. So retrieval serves two consumers: the solver (structured candidates) and the LLM (grounding text).

**What to measure**: label 20–30 trip briefs with the places a good planner would consider, then report recall@50 for vector-only, keyword-only and hybrid. Showing hybrid beats vector-only with numbers is a strong portfolio result.

---

## 6. Persona agents for the evaluation harness

**Yes, and you should.** This is called **user simulation**, and it's how serious agent evaluations work (Sierra's τ-bench, for example, uses an LLM-simulated user and measures whether an agent succeeds consistently across repeated runs, which it calls pass^k).

### How it works

1. **Persona generator** creates a structured persona card with hidden ground truth: budget, dates, party, pace, mobility limits, interests, must-dos, dislikes, plus *how they talk* (vague, terse, contradictory, non-native English, changes their mind).
2. **Simulated user agent** gets the card and talks to Roamate's intake. It answers clarification questions only from the card, and never volunteers the hidden facts unless asked.
3. **Roamate runs** the full graph: intake, retrieval, solver, validator, story, then one revision the persona requests ("less walking on day two").
4. **Graders score the run**:
   - **Deterministic checks** (most important): did intake extract the budget, dates and mobility limit correctly? Does an independent re-run of the validator find zero violations *against the persona's hidden truth*? Were must-dos kept? Did the revision change only what was asked?
   - **LLM-as-judge** for subjective quality (story faithfulness to the itinerary, relevance of "why this fits you"), with a written rubric, calibrated against 30–50 runs you label yourself.
   - **Efficiency**: number of clarification questions, tokens and latency per run.

### Rules that make it trustworthy

- Keep a **fixed, versioned regression suite** (same personas and seeds every run, gated in CI) separate from **fresh random personas** for exploration. When a fresh persona finds a bug, promote it into the fixed suite.
- Include **adversarial personas**: impossible requests, conflicting constraints, a budget below the must-do cost, prompt injection in free text.
- Don't let the same model grade its own work without a rubric and human calibration; simulated users also tend to be more cooperative than real ones.
- Add **property-based and metamorphic tests** for the solver: raising the budget never lowers the best utility found by an exact solve; removing a non-chosen place doesn't change the plan; every returned plan passes the validator.

---

## 7. Where each discipline shows up

You said you're happy with heavy math and want to showcase AI, ML and software engineering. This is where each can be demonstrated with something measurable:

| Area | Roamate component | What you can show |
| --- | --- | --- |
| Optimization / OR | TOPTW solver, Pareto scenarios, infeasibility explanations | A formal model, solver comparison (OR-Tools routing vs CP-SAT exact on small cases), optimality gap |
| Machine learning | Utility ranking model (learning-to-rank from saves, approvals and skips) | Offline nDCG vs the hand-written baseline |
| Machine learning | Visit-duration prediction with quantile regression | Use the 80th percentile as $s_i$ so plans have honest slack; measure plan robustness |
| Machine learning | Learn scenario weights from which scenario users pick (preference learning / inverse optimization) | Weights that match real choices better than hand-tuned ones |
| Information retrieval | Hybrid pgvector + full-text + rerank | recall@K for vector-only vs hybrid |
| LLM / agents | Structured intake, LangGraph orchestration, grounded story, revision as constraint delta | Extraction accuracy, faithfulness, pass^k from the persona harness |
| Evaluation | Persona simulation, LLM-judge calibration, metamorphic tests | A dashboard of metrics per commit |
| Software engineering | Modular monolith, versioned trip state, async jobs, CI, tracing, cost budgets | Clean architecture, test coverage, p50/p95 latency |

Keep the hand-written version of each ML piece as a baseline and add the learned version only when you can show it beats the baseline. That's the habit reviewers look for.

---

## Sources

- Shen, Zhou, Lei, Wu, *A survey of the orienteering problem: model evolution, algorithmic advances, and future directions*: https://arxiv.org/abs/2512.16865
- Google OR-Tools, *Penalties and dropping visits*: https://developers.google.com/optimization/routing/penalties
- Google Maps Platform, *Route Optimization: cost model*: https://developers.google.com/maps/documentation/route-optimization/cost-model
- Xie et al., *TravelPlanner: A Benchmark for Real-World Planning with Language Agents* (ICML 2024): https://arxiv.org/abs/2402.01622
- Hao et al., *Large Language Models Can Solve Real-World Planning Rigorously with Formal Verification Tools* (NAACL 2025): https://arxiv.org/abs/2404.11891
- Yao et al. (Sierra), *τ-bench*: https://arxiv.org/abs/2406.12045
