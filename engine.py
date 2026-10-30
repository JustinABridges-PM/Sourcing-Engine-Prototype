"""Order routing engine prototype.

Implements the decision flow (README 3.2) and edge cases (README 3.3):

  1. Check eligibility   - FCs with enough available stock and capacity left
  2. Build and filter    - every eligible FC x service; reject options that
                           arrive after the promised date or exceed the
                           merchant's cost cap
  3. Rank by cost        - ties: earlier arrival, then closer FC
  4. Select and record   - decision record with every rejected option,
                           the promise premium, and any revised EDD
  5. Reserve inventory   - so the next order sees updated stock

Edge cases: FC out of stock, FC cannot fill after assignment (re-shop with
cutoff times), competing orders (resolved jointly), no option meets the date
(ship earliest option and flag), merchant cost cap (cap overrides promise).

Standard library only.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Dict, List, Optional, Sequence, Tuple

REGIONS = ("West", "Central", "East")
SERVICES = ("Ground", "Air", "Express")
# (cost in USD, transit days) when the FC is in the shopper's region
BASE_RATES = {"Ground": (5, 3), "Air": (10, 2), "Express": (15, 1)}

ON_TIME = "ON_TIME"
AT_RISK = "AT_RISK"
NEEDS_REVIEW = "NEEDS_REVIEW"
UNFULFILLABLE = "UNFULFILLABLE"


def fmt(d: date) -> str:
    return d.strftime("%b %d")


# --------------------------------------------------------------------------
# Data model
# --------------------------------------------------------------------------


class RateCard:
    """Cost and transit time by service and region distance.

    Same region = 1x, one region away = 2x, two regions away = 3x, applied to
    both cost and transit days (README 2.1).
    """

    def __init__(self, base_rates=None, regions: Sequence[str] = REGIONS):
        self.base_rates = dict(base_rates or BASE_RATES)
        self.regions = tuple(regions)

    def distance(self, region_a: str, region_b: str) -> int:
        return abs(self.regions.index(region_a) - self.regions.index(region_b))

    def multiplier(self, region_a: str, region_b: str) -> int:
        return 1 + self.distance(region_a, region_b)

    def quote(self, fc_region: str, shopper_region: str, service: str) -> Tuple[int, int]:
        cost, days = self.base_rates[service]
        m = self.multiplier(fc_region, shopper_region)
        return cost * m, days * m


@dataclass
class FC:
    id: str
    name: str
    region: str
    daily_capacity: int = 100
    cutoff: Optional[time] = None  # last carrier handoff; None = ships same day
    service_cutoffs: Dict[str, time] = field(default_factory=dict)

    def cutoff_for(self, service: str) -> Optional[time]:
        return self.service_cutoffs.get(service, self.cutoff)


@dataclass
class Merchant:
    id: str
    name: str
    cost_cap: Optional[int] = None  # max shipping cost per order, USD


@dataclass
class Order:
    id: str
    merchant_id: str
    sku: str
    shopper_region: str
    placed_at: datetime
    promised: date
    qty: int = 1


class NetworkState:
    """Inventory, reservations, and capacity across the FC network."""

    def __init__(
        self,
        fcs: Sequence[FC],
        on_hand: Dict[Tuple[str, str], int],
        rate_card: Optional[RateCard] = None,
        handling_buffer_minutes: int = 60,
    ):
        self.fcs: Dict[str, FC] = {fc.id: fc for fc in fcs}
        self.on_hand: Dict[Tuple[str, str], int] = dict(on_hand)
        self.rate_card = rate_card or RateCard()
        self.handling_buffer = timedelta(minutes=handling_buffer_minutes)
        self.reserved: Dict[Tuple[str, str], int] = {}
        self.assigned: Dict[str, int] = {fc.id: 0 for fc in fcs}

    def available(self, fc_id: str, sku: str) -> int:
        key = (fc_id, sku)
        return self.on_hand.get(key, 0) - self.reserved.get(key, 0)

    def capacity_left(self, fc_id: str) -> int:
        return self.fcs[fc_id].daily_capacity - self.assigned[fc_id]

    def reserve(self, fc_id: str, sku: str, qty: int) -> None:
        key = (fc_id, sku)
        self.reserved[key] = self.reserved.get(key, 0) + qty
        self.assigned[fc_id] += 1

    def release(self, fc_id: str, sku: str, qty: int) -> None:
        key = (fc_id, sku)
        self.reserved[key] = max(0, self.reserved.get(key, 0) - qty)
        self.assigned[fc_id] = max(0, self.assigned[fc_id] - 1)

    def write_off(self, fc_id: str, sku: str, qty: int) -> None:
        key = (fc_id, sku)
        self.on_hand[key] = max(0, self.on_hand.get(key, 0) - qty)

    def copy(self) -> "NetworkState":
        return copy.deepcopy(self)


@dataclass
class Option:
    fc_id: str
    service: str
    cost: int
    transit_days: int
    ship_date: date
    arrival: date
    meets_date: bool
    over_cap: bool
    days_late: int
    reasons: List[str] = field(default_factory=list)

    @property
    def label(self) -> str:
        return f"{self.fc_id} {self.service}"


@dataclass
class Decision:
    order: Order
    status: str
    chosen: Optional[Option]
    options: List[Option]
    removed_fcs: Dict[str, str]
    cheapest_overall: Optional[Option] = None
    promise_premium: Optional[int] = None
    revised_edd: Optional[date] = None
    cost_to_meet_date: Optional[int] = None  # cheapest option that meets the date but was removed by the cap
    notes: List[str] = field(default_factory=list)
    reshopped_from: Optional[str] = None

    def is_complete(self) -> bool:
        """Explanation completeness (README 4.0): chosen option, a reason for
        every rejected option, the cost of alternatives, and the premium."""
        if self.chosen is not None:
            return self.promise_premium is not None and all(
                o.reasons for o in self.options if o is not self.chosen
            )
        if self.status == NEEDS_REVIEW:
            return bool(self.options) and all(o.reasons for o in self.options)
        if self.status == UNFULFILLABLE:
            return bool(self.removed_fcs) or bool(self.notes)
        return False

    def explain(self) -> str:
        o = self.order
        lines = [
            f"Order {o.id} | {o.merchant_id} | {o.sku} x{o.qty} | to {o.shopper_region} | "
            f"placed {o.placed_at:%b %d %H:%M} | promised {fmt(o.promised)}",
            f"  Decision: {self.status}",
        ]
        if self.chosen:
            c = self.chosen
            lines.append(
                f"  Chosen: {c.label} ${c.cost}, ships {fmt(c.ship_date)}, arrives {fmt(c.arrival)}"
            )
            if self.cheapest_overall is not None:
                lines.append(
                    f"  Promise premium: ${self.promise_premium} "
                    f"(cheapest option overall: {self.cheapest_overall.label} ${self.cheapest_overall.cost})"
                )
        if self.revised_edd:
            lines.append(f"  Revised EDD: {fmt(self.revised_edd)} (promise of {fmt(o.promised)} cannot be met)")
        if self.cost_to_meet_date is not None:
            lines.append(f"  Meeting the date would have cost ${self.cost_to_meet_date}, above the merchant cap")
        for fc_id, why in sorted(self.removed_fcs.items()):
            lines.append(f"  FC removed: {fc_id}: {why}")
        if self.options:
            lines.append("  Options:")
            for opt in sorted(self.options, key=lambda x: (x.fc_id, x.cost)):
                mark = ">>" if opt is self.chosen else "  "
                lines.append(
                    f"   {mark} {opt.label:<14} ${opt.cost:<3} arrives {fmt(opt.arrival)}  "
                    f"{'; '.join(opt.reasons)}"
                )
        for n in self.notes:
            lines.append(f"  Note: {n}")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        def opt_dict(opt: Option) -> dict:
            return {
                "fc": opt.fc_id,
                "service": opt.service,
                "cost": opt.cost,
                "ship_date": opt.ship_date.isoformat(),
                "arrival": opt.arrival.isoformat(),
                "meets_date": opt.meets_date,
                "over_cap": opt.over_cap,
                "reasons": opt.reasons,
            }

        return {
            "order_id": self.order.id,
            "merchant": self.order.merchant_id,
            "sku": self.order.sku,
            "promised": self.order.promised.isoformat(),
            "status": self.status,
            "chosen": opt_dict(self.chosen) if self.chosen else None,
            "promise_premium": self.promise_premium,
            "revised_edd": self.revised_edd.isoformat() if self.revised_edd else None,
            "cost_to_meet_date_over_cap": self.cost_to_meet_date,
            "removed_fcs": self.removed_fcs,
            "options": [opt_dict(o) for o in self.options],
            "notes": self.notes,
            "reshopped_from": self.reshopped_from,
            "explanation_complete": self.is_complete(),
        }


# --------------------------------------------------------------------------
# Engine
# --------------------------------------------------------------------------


class RoutingEngine:
    def __init__(self, state: NetworkState, merchants: Dict[str, Merchant]):
        self.state = state
        self.merchants = merchants

    # ---- step 1 + 2: eligibility and options ------------------------------

    def ship_date_for(self, fc: FC, service: str, now: datetime) -> date:
        """Same day if the order can be handed off before the cutoff (minus the
        handling buffer); otherwise the next day. No cutoff = ships same day."""
        cutoff = fc.cutoff_for(service)
        if cutoff is None:
            return now.date()
        latest_handoff = datetime.combine(now.date(), cutoff) - self.state.handling_buffer
        return now.date() if now <= latest_handoff else now.date() + timedelta(days=1)

    def build_options(
        self, order: Order, now: Optional[datetime] = None, exclude: Sequence[str] = ()
    ) -> Tuple[List[Option], Dict[str, str]]:
        now = now or order.placed_at
        cap = self.merchants[order.merchant_id].cost_cap
        removed: Dict[str, str] = {}
        options: List[Option] = []
        for fc in self.state.fcs.values():
            if fc.id in exclude:
                removed[fc.id] = "excluded: could not fill this order after assignment"
                continue
            avail = self.state.available(fc.id, order.sku)
            if avail < order.qty:
                removed[fc.id] = f"insufficient stock (available {avail}, need {order.qty})"
                continue
            if self.state.capacity_left(fc.id) <= 0:
                removed[fc.id] = "at daily capacity"
                continue
            for service in SERVICES:
                cost, days = self.state.rate_card.quote(fc.region, order.shopper_region, service)
                ship = self.ship_date_for(fc, service, now)
                arrival = ship + timedelta(days=days)
                options.append(
                    Option(
                        fc_id=fc.id,
                        service=service,
                        cost=cost,
                        transit_days=days,
                        ship_date=ship,
                        arrival=arrival,
                        meets_date=arrival <= order.promised,
                        over_cap=cap is not None and cost > cap,
                        days_late=max(0, (arrival - order.promised).days),
                    )
                )
        return options, removed

    # ---- step 3: ranking ----------------------------------------------------

    def _distance(self, fc_id: str, order: Order) -> int:
        return self.state.rate_card.distance(self.state.fcs[fc_id].region, order.shopper_region)

    def _rank_key(self, order: Order):
        return lambda o: (o.cost, o.arrival, self._distance(o.fc_id, order), o.fc_id)

    def _candidates(self, order: Order, options: List[Option]) -> List[Option]:
        """One candidate per FC, best first.

        At each FC: the cheapest option that meets the date and is under the
        cap; if none, the earliest-arriving option under the cap (a late
        candidate). Across FCs, on-time candidates rank by cost, then arrival,
        then proximity; late candidates rank by arrival, then cost.
        """
        by_fc: Dict[str, List[Option]] = {}
        for o in options:
            by_fc.setdefault(o.fc_id, []).append(o)
        on_time: List[Option] = []
        late: List[Option] = []
        for opts in by_fc.values():
            ok = [o for o in opts if o.meets_date and not o.over_cap]
            if ok:
                on_time.append(min(ok, key=self._rank_key(order)))
                continue
            under = [o for o in opts if not o.over_cap]
            if under:
                late.append(min(under, key=lambda o: (o.arrival, o.cost, o.service)))
        on_time.sort(key=self._rank_key(order))
        late.sort(key=lambda o: (o.arrival, o.cost, self._distance(o.fc_id, order), o.fc_id))
        return on_time + late

    # ---- step 4: select and record -------------------------------------------

    def _annotate(self, order: Order, options: List[Option], chosen: Optional[Option], blocked: str = "",
                  taken: Optional[Dict[str, str]] = None) -> None:
        taken = taken or {}
        cap = self.merchants[order.merchant_id].cost_cap
        for o in options:
            o.reasons = []
            if o is chosen:
                o.reasons.append("chosen")
                continue
            if blocked:
                o.reasons.append(blocked)
                continue
            if o.over_cap:
                o.reasons.append(f"cost ${o.cost} above merchant cap ${cap}")
            if o.fc_id in taken and not o.over_cap and chosen is not None and o.fc_id != chosen.fc_id:
                o.reasons.append(f"{o.fc_id} stock allocated to {taken[o.fc_id]} in the same batch (joint resolution)")
                continue
            if not o.meets_date:
                o.reasons.append(f"arrives {fmt(o.arrival)}, {o.days_late} day(s) late")
                if chosen is not None and not chosen.meets_date and not o.over_cap:
                    if o.arrival > chosen.arrival:
                        o.reasons.append("arrives later than chosen")
                    else:
                        o.reasons.append("no earlier than chosen and costs more")
            elif not o.over_cap and chosen is not None:
                if o.cost > chosen.cost:
                    o.reasons.append(f"meets date but costs ${o.cost - chosen.cost} more than chosen")
                else:
                    o.reasons.append("meets date; ranked below chosen on tie-breakers")
            if not o.reasons:
                o.reasons.append("not selected")

    def _make_decision(
        self,
        order: Order,
        options: List[Option],
        removed: Dict[str, str],
        chosen: Optional[Option],
        notes: Optional[List[str]] = None,
        allocated_away: bool = False,
        taken: Optional[Dict[str, str]] = None,
    ) -> Decision:
        notes = list(notes or [])
        if not options:
            return Decision(order, UNFULFILLABLE, None, [], removed, notes=notes + ["no FC has stock for this order"])
        cheapest = min(options, key=lambda o: (o.cost, o.arrival, o.fc_id))
        capped_but_meets = [o for o in options if o.meets_date and o.over_cap]
        if allocated_away:
            self._annotate(order, options, None, blocked="stock allocated to other orders in the same batch")
            return Decision(
                order, UNFULFILLABLE, None, options, removed, cheapest_overall=cheapest, notes=notes
            )
        self._annotate(order, options, chosen, taken=taken)
        if chosen is None:
            cost_to_meet = min((o.cost for o in capped_but_meets), default=None)
            return Decision(
                order,
                NEEDS_REVIEW,
                None,
                options,
                removed,
                cheapest_overall=cheapest,
                cost_to_meet_date=cost_to_meet,
                notes=notes + ["every option exceeds the merchant cost cap; held for merchant review"],
            )
        premium = chosen.cost - cheapest.cost
        if chosen.meets_date:
            return Decision(
                order, ON_TIME, chosen, options, removed,
                cheapest_overall=cheapest, promise_premium=premium, notes=notes,
            )
        cost_to_meet = min((o.cost for o in capped_but_meets), default=None)
        if cost_to_meet is not None:
            flag = "no option under the merchant cap meets the promised date; shipped earliest option and flagged"
        elif any(o.meets_date and not o.over_cap for o in options):
            flag = ("the only on-time options were at FCs whose stock went to other orders in the batch; "
                    "shipped earliest remaining option and flagged")
        else:
            flag = "no FC and service can arrive by the promised date; shipped earliest option and flagged"
        flag_notes = [flag]
        return Decision(
            order, AT_RISK, chosen, options, removed,
            cheapest_overall=cheapest, promise_premium=premium,
            revised_edd=chosen.arrival, cost_to_meet_date=cost_to_meet,
            notes=notes + flag_notes,
        )

    def decide(
        self,
        order: Order,
        now: Optional[datetime] = None,
        exclude: Sequence[str] = (),
        notes: Optional[List[str]] = None,
    ) -> Decision:
        """Steps 1-4 for a single order. Does not reserve inventory."""
        options, removed = self.build_options(order, now, exclude)
        cands = self._candidates(order, options)
        return self._make_decision(order, options, removed, cands[0] if cands else None, notes)

    # ---- step 5: reserve ------------------------------------------------------

    def route_order(
        self,
        order: Order,
        now: Optional[datetime] = None,
        exclude: Sequence[str] = (),
        notes: Optional[List[str]] = None,
    ) -> Decision:
        """Full flow for one order, first come first served."""
        d = self.decide(order, now, exclude, notes)
        if d.chosen is not None:
            self.state.reserve(d.chosen.fc_id, order.sku, order.qty)
        return d

    def route_stream(self, orders: Sequence[Order]) -> List[Decision]:
        """Orders arrive one at a time; each reserves stock before the next."""
        return [self.route_order(o) for o in sorted(orders, key=lambda o: (o.placed_at, o.id))]

    # ---- edge case: competing orders ---------------------------------------------

    def route_batch(self, orders: Sequence[Order], max_joint: int = 8) -> List[Decision]:
        """Orders that compete for scarce stock or capacity are resolved
        together; everything else is routed as in route_stream."""
        ordered = sorted(orders, key=lambda o: (o.placed_at, o.id))
        info = {}
        for o in ordered:
            options, removed = self.build_options(o)
            info[o.id] = (options, removed, self._candidates(o, options))

        decisions: Dict[str, Decision] = {}
        for comp in self._components(ordered, info):
            if len(comp) < 2:
                continue
            assignment, notes, taken = self._solve_component(comp, info, max_joint)
            for o in comp:
                options, removed, _ = info[o.id]
                chosen = assignment[o.id]
                decisions[o.id] = self._make_decision(
                    o, options, removed, chosen, notes[o.id], allocated_away=chosen is None,
                    taken=taken[o.id],
                )
                if chosen is not None:
                    self.state.reserve(chosen.fc_id, o.sku, o.qty)
        for o in ordered:
            if o.id not in decisions:
                decisions[o.id] = self.route_order(o)
        return [decisions[o.id] for o in ordered]

    def _components(self, ordered: List[Order], info) -> List[List[Order]]:
        parent = {o.id: o.id for o in ordered}

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a, b):
            parent[find(a)] = find(b)

        by_stock: Dict[Tuple[str, str], List[Order]] = {}
        by_fc: Dict[str, List[Order]] = {}
        for o in ordered:
            for cand in info[o.id][2]:
                by_stock.setdefault((cand.fc_id, o.sku), []).append(o)
                by_fc.setdefault(cand.fc_id, []).append(o)
        for (fc_id, sku), lst in by_stock.items():
            if sum(o.qty for o in lst) > self.state.available(fc_id, sku):
                for o in lst[1:]:
                    union(lst[0].id, o.id)
        for fc_id, lst in by_fc.items():
            if len(lst) > self.state.capacity_left(fc_id):
                for o in lst[1:]:
                    union(lst[0].id, o.id)
        groups: Dict[str, List[Order]] = {}
        for o in ordered:
            groups.setdefault(find(o.id), []).append(o)
        return sorted(groups.values(), key=lambda g: (g[0].placed_at, g[0].id))

    def _solve_component(self, comp: List[Order], info, max_joint: int):
        """Choose one candidate (or none) per order.

        Objective, in priority order: most promises kept, most orders filled,
        lowest total cost, then earlier orders get their better candidates.
        Exact search up to max_joint orders; greedy (tightest promise first)
        beyond that - a documented shortcut.
        """
        cands = {o.id: info[o.id][2] for o in comp}
        avail = {}
        for o in comp:
            for c in cands[o.id]:
                avail.setdefault((c.fc_id, o.sku), self.state.available(c.fc_id, o.sku))
        cap = {fc_id: self.state.capacity_left(fc_id) for fc_id in self.state.fcs}

        def fits(o: Order, c: Option, a, k) -> bool:
            return a[(c.fc_id, o.sku)] >= o.qty and k[c.fc_id] >= 1

        def score(assign: List[Tuple[int, Optional[Option]]]):
            on_time = sum(1 for _, c in assign if c is not None and c.meets_date)
            filled = sum(1 for _, c in assign if c is not None)
            cost = sum(c.cost for _, c in assign if c is not None)
            return (-on_time, -filled, cost, tuple(i for i, _ in assign))

        if len(comp) <= max_joint:
            best = {"score": None, "assign": None}
            a, k = dict(avail), dict(cap)
            current: List[Tuple[int, Optional[Option]]] = []

            def dfs(i: int) -> None:
                if i == len(comp):
                    s = score(current)
                    if best["score"] is None or s < best["score"]:
                        best["score"], best["assign"] = s, list(current)
                    return
                o = comp[i]
                options = list(enumerate(cands[o.id])) + [(len(cands[o.id]), None)]
                for idx, c in options:
                    if c is not None:
                        if not fits(o, c, a, k):
                            continue
                        a[(c.fc_id, o.sku)] -= o.qty
                        k[c.fc_id] -= 1
                    current.append((idx, c))
                    dfs(i + 1)
                    current.pop()
                    if c is not None:
                        a[(c.fc_id, o.sku)] += o.qty
                        k[c.fc_id] += 1

            dfs(0)
            assignment = {o.id: c for o, (_, c) in zip(comp, best["assign"])}
            method = "exact search"
        else:
            assignment = {}
            a, k = dict(avail), dict(cap)
            for o in sorted(comp, key=lambda x: (x.promised, x.placed_at, x.id)):
                pick = None
                for c in cands[o.id]:
                    if fits(o, c, a, k):
                        pick = c
                        a[(c.fc_id, o.sku)] -= o.qty
                        k[c.fc_id] -= 1
                        break
                assignment[o.id] = pick
            method = "greedy fallback (tightest promise first; batch too large for exact search)"

        # first come, first served on the same candidates, for comparison
        fcfs_on_time = 0
        a, k = dict(avail), dict(cap)
        for o in comp:
            for c in cands[o.id]:
                if fits(o, c, a, k):
                    a[(c.fc_id, o.sku)] -= o.qty
                    k[c.fc_id] -= 1
                    fcfs_on_time += 1 if c.meets_date else 0
                    break
        joint_on_time = sum(1 for c in assignment.values() if c is not None and c.meets_date)
        joint_cost = sum(c.cost for c in assignment.values() if c is not None)

        notes: Dict[str, List[str]] = {}
        taken: Dict[str, Dict[str, str]] = {}
        for o in comp:
            others = ", ".join(x.id for x in comp if x.id != o.id)
            n = [
                f"Contested stock: resolved together with {others} ({method}). "
                f"Joint assignment keeps {joint_on_time} of {len(comp)} promises at ${joint_cost} total."
            ]
            if fcfs_on_time < joint_on_time:
                n.append(f"First come, first served would have kept only {fcfs_on_time} of {len(comp)} promises.")
            mine = assignment[o.id]
            t: Dict[str, str] = {}
            for x in comp:
                got = assignment[x.id]
                if x.id != o.id and got is not None and x.sku == o.sku and (mine is None or got.fc_id != mine.fc_id):
                    t[got.fc_id] = (t[got.fc_id] + ", " if got.fc_id in t else "") + x.id
            taken[o.id] = t
            best_c = cands[o.id][0] if cands[o.id] else None
            if best_c is not None and (mine is None or mine.fc_id != best_c.fc_id) and best_c.fc_id in t:
                n.append(f"Individually best option {best_c.label} was lost: {best_c.fc_id} stock went to {t[best_c.fc_id]}.")
            elif mine is not None:
                lost = [x.id for x in comp if x.id != o.id and cands[x.id]
                        and cands[x.id][0].fc_id == mine.fc_id and assignment[x.id] is not None
                        and assignment[x.id].fc_id != mine.fc_id]
                if lost:
                    n.append(f"Holds the contested unit at {mine.fc_id}; {', '.join(lost)} re-sourced elsewhere.")
            notes[o.id] = n
        return assignment, notes, taken

    # ---- edge case: FC cannot fill after assignment ---------------------------------

    def reshop(self, decision: Decision, now: datetime, reason: str = "damaged items") -> Decision:
        """The assigned FC cannot fill the order. Release the reservation,
        write off the units, and re-run the flow from the current time
        without that FC. Cutoff times apply from `now`."""
        if decision.chosen is None:
            raise ValueError("decision has no assigned FC to re-shop from")
        order = decision.order
        failed = decision.chosen.fc_id
        self.state.release(failed, order.sku, order.qty)
        self.state.write_off(failed, order.sku, order.qty)
        notes = [
            f"Re-shop: originally {decision.chosen.label} (${decision.chosen.cost}, arrives "
            f"{fmt(decision.chosen.arrival)}); {failed} could not fill it ({reason}). "
            f"Re-run at {now:%b %d %H:%M}."
        ]
        new = self.route_order(order, now=now, exclude=(failed,), notes=notes)
        new.reshopped_from = failed
        return new
