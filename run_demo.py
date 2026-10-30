"""Run the engine and both baselines over the sample batch.

    python run_demo.py              # summary table, metrics, kill-threshold checks
    python run_demo.py --explain    # also print the full decision record for every order
    python run_demo.py --explain O-1005 O-1010   # only for those orders

Writes decisions.json (the machine-readable decision records).
"""

from __future__ import annotations

import json
import sys
from datetime import datetime

import metrics
import sample_data as sd
from engine import RoutingEngine, fmt


def line(d) -> str:
    o = d.order
    if d.chosen:
        pick = f"{d.chosen.label:<12} ${d.chosen.cost:<3} arr {fmt(d.chosen.arrival)}"
        prem = f"${d.promise_premium}"
    else:
        pick, prem = "-", "-"
    return (f"{o.id}  {o.merchant_id:<7} {o.shopper_region:<8} promised {fmt(o.promised)}  "
            f"{d.status:<12} {pick:<27} premium {prem}")


def print_metrics(summaries) -> None:
    print(f"{'':<20}{'on-time':>9}{'on-time %':>11}{'spend':>8}{'$/on-time':>11}{'avg premium':>13}{'over cap':>10}")
    for s in summaries:
        cpot = "n/a" if s.cost_per_on_time is None else f"${s.cost_per_on_time:.2f}"
        print(f"{s.name:<20}{s.on_time:>6}/{s.orders:<2}{s.on_time_rate:>10.0%}{'$' + str(s.total_cost):>8}"
              f"{cpot:>11}{'$%.2f' % s.avg_premium:>13}{s.cap_violations:>10}")


def main(argv) -> int:
    explain = "--explain" in argv
    wanted = {a for a in argv if a.startswith("O-")}
    merchants = sd.make_merchants()
    orders = sd.sample_orders()
    state = sd.make_state(sd.sample_inventory())

    engine = RoutingEngine(state.copy(), merchants)
    decisions = engine.route_batch(orders)
    stream = RoutingEngine(state.copy(), merchants).route_stream(orders)

    print("=== Routing decisions (promise first, cost as tiebreaker) ===")
    for d in decisions:
        print(line(d))
    print()
    for d in decisions:
        if explain and (not wanted or d.order.id in wanted):
            print(d.explain())
            print()

    a = metrics.summarize("Baseline A", metrics.baseline_a(state, merchants, orders))
    b = metrics.summarize("Baseline B", metrics.baseline_b(state, merchants, orders))
    e = metrics.summarize("Engine", metrics.outcomes_from_decisions(decisions))
    s = metrics.summarize("Engine (FCFS)", metrics.outcomes_from_decisions(stream))

    print("=== Metrics ===")
    print("A = closest FC with stock, Ground.  B = fastest service from the FC that arrives soonest.")
    print("FCFS = same engine, but contested stock goes to whichever order came first.\n")
    print_metrics([a, b, s, e])
    print()

    print("=== Kill-threshold checks (engine vs baselines) ===")
    for name, ok, detail in metrics.kill_checks(e, a, b, decisions):
        print(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}")
    print()

    print("=== At-risk and review queue ===")
    flagged = [d for d in decisions if d.status in ("AT_RISK", "NEEDS_REVIEW", "UNFULFILLABLE")]
    for d in flagged:
        extra = f"revised EDD {fmt(d.revised_edd)}" if d.revised_edd else ""
        if d.cost_to_meet_date is not None:
            extra += f"; meeting the date would cost ${d.cost_to_meet_date} (above cap)"
        print(f"{d.order.id}: {d.status} {extra}")
    if not flagged:
        print("none")
    print()

    # Re-shop demo: Atlanta reports damaged items on an order to Georgia, near the Dallas cutoff.
    print("=== Re-shop demo: Atlanta cannot fill an order to Georgia (promised Nov 5) ===")
    from engine import Order
    for hour, minute in ((12, 30), (13, 30)):
        st = sd.make_state({("ATL", "X"): 5, ("DAL", "X"): 5, ("PHX", "X"): 5})
        eng = RoutingEngine(st, merchants | {"M": __import__("engine").Merchant("M", "Demo")})
        order = Order("RESHOP", "M", "X", "East", sd.at(9, 0), sd.on(11, 5))
        first = eng.route_order(order)
        new = eng.reshop(first, sd.at(hour, minute))
        c = new.chosen
        print(f"re-shop at {hour}:{minute:02d}: {first.chosen.label} -> {c.label} ${c.cost}, "
              f"ships {fmt(c.ship_date)}, arrives {fmt(c.arrival)}, {new.status}")
    print()

    with open("decisions.json", "w") as f:
        json.dump([d.to_dict() for d in decisions], f, indent=2)
    print("Wrote decisions.json")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
