"""Roamate scenario solver: a small, runnable example.

Models a 2-day city break as a prize-collecting Team Orienteering Problem
with Time Windows (TOPTW) on OR-Tools' routing solver:
  - each day is a "vehicle" that starts and ends at the hotel,
  - each place is optional and earns its utility if visited (disjunction penalty),
  - opening hours are time windows, visit durations are service times,
  - lunch is a mandatory 60-minute break between 12:00 and 14:00,
  - a hard ground budget and a per-day walking cap are dimensions,
  - must-do places are mandatory.
Budget / Balanced / Comfort are the same model with different weights and
transport policies, plus a diversity constraint between scenarios.

Part 2 picks a hotel: hotels that lack a required feature are filtered out,
then the trip is solved once per remaining hotel (with the money left after
paying for the nights) and the hotel with the best total objective wins.
Taxi fares come from a metered tariff: flag fall + per km + per minute.

Run:  python3 solver_example.py      (needs: pip install ortools)
All data is fictional.
"""

import math
from dataclasses import dataclass

from ortools.constraint_solver import pywrapcp, routing_enums_pb2


@dataclass
class Place:
    name: str
    xy: tuple          # position on a km grid
    duration: int      # minutes on site
    open: int          # minutes after midnight
    close: int
    price: int         # admission per person, EUR
    tags: dict         # interest -> strength 0..1
    rating: float      # 0..5
    must_do: bool = False


HOTEL = (0.0, 0.0)   # Part 1: the traveler already booked this hotel

# Part 2: hotels to choose from when the traveler asks for a suggestion.
HOTELS = [
    dict(name="Central Palace", xy=(0.8, 0.6), night=190, rating=4.7, features={"breakfast", "pool"}),
    dict(name="Riverside Inn", xy=(-1.0, 0.5), night=110, rating=4.4, features={"breakfast"}),
    dict(name="Airport Lodge", xy=(-4.0, -3.5), night=70, rating=4.0, features={"breakfast", "parking"}),
    dict(name="Hill Hostel", xy=(2.5, 2.2), night=60, rating=4.3, features={"kitchen"}),
]
HOTEL_REQUEST = dict(required={"breakfast"}, nice_to_have={"pool": 15}, total_budget_eur=500)

# Metered taxi tariff (illustrative values; load the city's official tariff in production).
TAXI_TARIFF = dict(flag_eur=3.25, per_km_eur=0.58, per_min_eur=0.28)
PLACES = [
    Place("Cathedral", (0.6, 0.4), 45, 540, 1080, 0, {"architecture": 1.0}, 4.6),
    Place("Old Market Hall", (1.0, -0.5), 75, 480, 840, 0, {"food": 1.0}, 4.5),
    Place("Art Museum", (2.2, 1.0), 120, 600, 1080, 18, {"museums": 1.0, "architecture": 0.3}, 4.7),
    Place("Castle Hill", (2.8, 2.6), 90, 540, 1140, 12, {"architecture": 0.8, "views": 1.0}, 4.6, must_do=True),
    Place("Riverside Walk", (-1.2, 0.8), 60, 0, 1440, 0, {"nature": 0.8, "views": 0.6}, 4.4),
    Place("Tile Museum", (4.5, -1.5), 90, 600, 1080, 8, {"museums": 0.9, "architecture": 0.5}, 4.5),
    Place("Food Tour", (0.9, 1.5), 180, 660, 900, 65, {"food": 1.0}, 4.8),
    Place("Botanical Garden", (-2.0, -1.8), 75, 600, 1080, 5, {"nature": 1.0}, 4.3),
    Place("Modern Gallery", (3.6, 0.2), 75, 600, 1140, 14, {"museums": 0.8}, 4.2),
    Place("Sunset Viewpoint", (1.8, 3.4), 45, 0, 1440, 0, {"views": 1.0}, 4.7),
]

TRIP = dict(
    days=2, party=2, day_start=540, day_end=1140,  # 09:00 - 19:00
    budget_eur=160,                                 # hard cap: admissions + local transport, whole party
    interests={"food": 1.0, "architecture": 0.8, "museums": 0.6, "views": 0.5, "nature": 0.2},
)

SCENARIOS = {
    #  weights: utility, travel time, money, walking;  walk cap and pace (stops) per day;  taxi allowed
    "Budget":   dict(w_u=3.0, w_t=0.5, w_m=3.0, w_w=0.1, walk_cap=150, max_stops=4, taxi=False),
    "Balanced": dict(w_u=3.0, w_t=1.0, w_m=1.0, w_w=0.3, walk_cap=120, max_stops=4, taxi=False),
    "Comfort":  dict(w_u=3.0, w_t=1.5, w_m=0.3, w_w=1.0, walk_cap=60, max_stops=3, taxi=True),
}


def utility(p: Place) -> float:
    """Preference score. In production this is a learned ranking model."""
    match = sum(TRIP["interests"].get(k, 0) * v for k, v in p.tags.items())
    return 100 * match * (p.rating / 5)


def leg(a, b, taxi_ok):
    """Pick a transport mode for one leg. Returns (minutes, eur_for_party, walk_minutes)."""
    km = math.dist(a, b) * 1.3                      # detour factor over straight line
    walk = round(km * 12)                           # 5 km/h
    if km <= 1.2:
        return walk, 0, walk
    if taxi_ok:
        mins = round(km * 3 + 5)                    # includes pickup wait
        fare = TAXI_TARIFF["flag_eur"] + TAXI_TARIFF["per_km_eur"] * km + TAXI_TARIFF["per_min_eur"] * (mins - 5)
        return mins, round(fare), 0                 # one cab for up to 4 people
    return round(km * 3 + 10), 2 * 2 * TRIP["party"] // 2, 6   # metro: wait+ride, 2 EUR pp, 6 min walking


def solve(name, cfg, exclude_same_as=None, hotel=HOTEL, budget=TRIP["budget_eur"], quiet=False):
    """Solve one scenario. Returns (visited place numbers, objective value), or None if infeasible."""
    nodes = [hotel] + [p.xy for p in PLACES]
    n, days = len(nodes), TRIP["days"]
    legs = [[leg(nodes[i], nodes[j], cfg["taxi"]) for j in range(n)] for i in range(n)]

    mgr = pywrapcp.RoutingIndexManager(n, days, 0)
    rt = pywrapcp.RoutingModel(mgr)

    def node(ix):
        return mgr.IndexToNode(ix)

    # Time dimension: travel + time on site at the origin node.
    def time_cb(i, j):
        a, b = node(i), node(j)
        service = PLACES[a - 1].duration if a else 0
        return legs[a][b][0] + service
    t_cb = rt.RegisterTransitCallback(time_cb)
    rt.AddDimension(t_cb, 120, TRIP["day_end"], False, "Time")
    time = rt.GetDimensionOrDie("Time")

    # Money dimension: admission for the party + transport fare.
    def money_cb(i, j):
        a, b = node(i), node(j)
        entry = PLACES[b - 1].price * TRIP["party"] if b else 0
        return legs[a][b][1] + entry
    m_cb = rt.RegisterTransitCallback(money_cb)
    rt.AddDimension(m_cb, 0, budget, True, "Money")
    money = rt.GetDimensionOrDie("Money")

    # Walking dimension with a per-day cap.
    w_cb = rt.RegisterTransitCallback(lambda i, j: legs[node(i)][node(j)][2])
    rt.AddDimension(w_cb, 0, cfg["walk_cap"], True, "Walk")

    # Pace: at most max_stops places per day.
    s_cb = rt.RegisterUnaryTransitCallback(lambda i: 1 if node(i) else 0)
    rt.AddDimension(s_cb, 0, cfg["max_stops"], True, "Stops")

    # Balance the days: penalise the gap between the longest and shortest day.
    time.SetGlobalSpanCostCoefficient(1)

    # Objective part 1: weighted travel time, money and walking on every arc.
    def arc_cost(i, j):
        a, b = node(i), node(j)
        mins, eur, walk = legs[a][b]
        entry = PLACES[b - 1].price * TRIP["party"] if b else 0
        return round(cfg["w_t"] * mins + cfg["w_m"] * (eur + entry) + cfg["w_w"] * walk)
    rt.SetArcCostEvaluatorOfAllVehicles(rt.RegisterTransitCallback(arc_cost))

    # Objective part 2: dropping a place costs its utility (prize collecting).
    for k, p in enumerate(PLACES, start=1):
        ix = mgr.NodeToIndex(k)
        # Arrive early enough to finish the visit before closing.
        time.CumulVar(ix).SetRange(max(p.open, TRIP["day_start"]), p.close - p.duration)
        if not p.must_do:
            rt.AddDisjunction([ix], round(cfg["w_u"] * utility(p)))

    solver = rt.solver()
    for d in range(days):
        time.CumulVar(rt.Start(d)).SetRange(TRIP["day_start"], TRIP["day_start"] + 60)
        time.CumulVar(rt.End(d)).SetMax(TRIP["day_end"])
        # Lunch: 60 minutes starting between 12:00 and 13:00.
        lunch = solver.FixedDurationIntervalVar(720, 780, 60, False, f"lunch{d}")
        # Service time per index, so lunch can't overlap a visit.
        visit = [PLACES[node(i) - 1].duration if node(i) else 0 for i in range(rt.Size())]
        time.SetBreakIntervalsOfVehicle([lunch], d, visit)

    # Hard budget across all days (Money is cumulated per day/vehicle).
    solver.Add(solver.Sum([money.CumulVar(rt.End(d)) for d in range(days)]) <= budget)

    # Diversity: share at most |S|-2 places with an earlier scenario.
    if exclude_same_as:
        prev = [mgr.NodeToIndex(k) for k in exclude_same_as]
        solver.Add(solver.Sum([rt.ActiveVar(ix) for ix in prev]) <= len(prev) - 2)

    params = pywrapcp.DefaultRoutingSearchParameters()
    params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    params.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    params.time_limit.seconds = 3
    sol = rt.SolveWithParameters(params)
    if not sol:
        if not quiet:
            print(f"\n{name}: no feasible plan under these constraints")
        return None

    visited, spent = set(), 0
    say = (lambda *a: None) if quiet else print
    say(f"\n=== {name} ===")
    for d in range(days):
        ix, stops = rt.Start(d), []
        while not rt.IsEnd(ix):
            k = node(ix)
            if k:
                t = sol.Value(time.CumulVar(ix))
                stops.append(f"{t // 60:02d}:{t % 60:02d} {PLACES[k - 1].name}")
                visited.add(k)
            ix = sol.Value(rt.NextVar(ix))
        end = sol.Value(time.CumulVar(ix))
        spent += sol.Value(money.CumulVar(ix))
        say(f"Day {d + 1}: " + " -> ".join(stops) + f"  (back {end // 60:02d}:{end % 60:02d})")
    dropped = [p.name for k, p in enumerate(PLACES, 1) if k not in visited]
    u = sum(utility(PLACES[k - 1]) for k in visited)
    say(f"Spent {spent} EUR of {budget} | utility {u:.0f} | skipped: {', '.join(dropped)}")
    return visited, sol.ObjectiveValue()


def choose_hotel(cfg):
    """Filter hotels by required features, solve the trip from each, keep the best total."""
    req, nights = HOTEL_REQUEST, TRIP["days"]
    print("\n=== Hotel choice (Balanced weights) ===")
    best = None
    for h in HOTELS:
        if not req["required"] <= h["features"]:
            print(f"{h['name']:15} skipped: missing {', '.join(req['required'] - h['features'])}")
            continue
        stay = h["night"] * nights
        result = solve(h["name"], cfg, hotel=h["xy"], budget=req["total_budget_eur"] - stay, quiet=True)
        if result is None:
            print(f"{h['name']:15} no feasible trip with the money left after {stay} EUR of nights")
            continue
        bonus = sum(v for f, v in req["nice_to_have"].items() if f in h["features"]) + 20 * h["rating"]
        total = result[1] + cfg["w_m"] * stay - bonus  # lower is better
        print(f"{h['name']:15} nights {stay:3} EUR | trip objective {result[1]:5} | total {total:7.0f}")
        if best is None or total < best[0]:
            best = (total, h)
    if best:
        h = best[1]
        print(f"Chosen: {h['name']}")
        solve(f"Balanced from {h['name']}", cfg, hotel=h["xy"],
              budget=req["total_budget_eur"] - h["night"] * nights)


if __name__ == "__main__":
    previous = None
    for name, cfg in SCENARIOS.items():
        result = solve(name, cfg, exclude_same_as=previous)
        previous = result[0] if result else previous
    choose_hotel(SCENARIOS["Balanced"])
