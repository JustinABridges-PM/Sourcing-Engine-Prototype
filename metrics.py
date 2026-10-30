"""Success metrics (README 4.0): baselines, summaries, kill-threshold checks.

On-time is judged on the *planned* arrival date (ship date + transit days).
There is no carrier variance in this prototype, so "predicted vs. actual" is
not measurable here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

from engine import Decision, Merchant, NetworkState, Option, Order, RoutingEngine


@dataclass
class Outcome:
    order: Order
    option: Optional[Option]
    cheapest_cost: Optional[int]  # cheapest option overall, for the promise premium


@dataclass
class Summary:
    name: str
    orders: int
    shipped: int
    on_time: int
    total_cost: int
    avg_premium: float
    cap_violations: int

    @property
    def on_time_rate(self) -> float:
        return self.on_time / self.orders if self.orders else 0.0

    @property
    def cost_per_on_time(self) -> Optional[float]:
        return self.total_cost / self.on_time if self.on_time else None


def outcomes_from_decisions(decisions: Sequence[Decision]) -> List[Outcome]:
    return [
        Outcome(d.order, d.chosen, d.cheapest_overall.cost if d.cheapest_overall else None)
        for d in decisions
    ]


def _baseline(state: NetworkState, merchants: Dict[str, Merchant], orders: Sequence[Order], pick) -> List[Outcome]:
    engine = RoutingEngine(state.copy(), merchants)
    out: List[Outcome] = []
    for order in sorted(orders, key=lambda o: (o.placed_at, o.id)):
        options, _ = engine.build_options(order)
        if not options:
            out.append(Outcome(order, None, None))
            continue
        chosen = pick(engine, order, options)
        engine.state.reserve(chosen.fc_id, order.sku, order.qty)
        out.append(Outcome(order, chosen, min(o.cost for o in options)))
    return out


def baseline_a(state, merchants, orders) -> List[Outcome]:
    """Closest FC with stock, Ground (the README's assumed current rule)."""

    def pick(engine, order, options):
        ground = [o for o in options if o.service == "Ground"]
        return min(ground, key=lambda o: (engine._distance(o.fc_id, order), o.fc_id))

    return _baseline(state, merchants, orders, pick)


def baseline_b(state, merchants, orders) -> List[Outcome]:
    """Fastest service from whichever FC can arrive soonest, ignoring cost."""

    def pick(engine, order, options):
        return min(options, key=lambda o: (o.arrival, o.cost, engine._distance(o.fc_id, order), o.fc_id))

    return _baseline(state, merchants, orders, pick)


def summarize(name: str, outcomes: Sequence[Outcome]) -> Summary:
    shipped = [x for x in outcomes if x.option is not None]
    on_time = sum(1 for x in shipped if x.option.meets_date)
    premiums = [x.option.cost - x.cheapest_cost for x in shipped]
    return Summary(
        name=name,
        orders=len(outcomes),
        shipped=len(shipped),
        on_time=on_time,
        total_cost=sum(x.option.cost for x in shipped),
        avg_premium=sum(premiums) / len(premiums) if premiums else 0.0,
        cap_violations=sum(1 for x in shipped if x.option.over_cap),
    )


def kill_checks(
    engine: Summary,
    a: Summary,
    b: Summary,
    decisions: Sequence[Decision],
    max_avg_premium: float = 15.0,
) -> List[Tuple[str, bool, str]]:
    """Each check is (name, passed, detail). A failed check is a kill signal."""
    checks: List[Tuple[str, bool, str]] = []

    checks.append((
        "On-time rate above Baseline A",
        engine.on_time_rate > a.on_time_rate,
        f"engine {engine.on_time_rate:.0%} vs A {a.on_time_rate:.0%}",
    ))

    def cpot(s: Summary) -> str:
        return "n/a" if s.cost_per_on_time is None else f"${s.cost_per_on_time:.2f}"

    for base in (a, b):
        ok = (
            engine.cost_per_on_time is not None
            and (base.cost_per_on_time is None or engine.cost_per_on_time <= base.cost_per_on_time)
        )
        checks.append((
            f"Cost per on-time delivery at or below Baseline {base.name[-1]}",
            ok,
            f"engine {cpot(engine)} vs {base.name[-1]} {cpot(base)}",
        ))

    incomplete = [d.order.id for d in decisions if not d.is_complete()]
    checks.append((
        "Every decision has a complete explanation",
        not incomplete,
        "100% complete" if not incomplete else f"missing: {', '.join(incomplete)}",
    ))
    checks.append((
        "No order shipped above the merchant cap",
        engine.cap_violations == 0,
        f"{engine.cap_violations} exception(s)",
    ))
    checks.append((
        f"Average promise premium within ${max_avg_premium:.0f}",
        engine.avg_premium <= max_avg_premium,
        f"${engine.avg_premium:.2f} per order",
    ))
    return checks
