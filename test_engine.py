"""Tests that reproduce the README's worked examples (order placed Oct 30, 2026).

    python test_engine.py        # no dependencies
    python -m pytest             # if pytest is installed
"""

from __future__ import annotations

from datetime import time

import metrics
import sample_data as sd
from engine import (
    AT_RISK, NEEDS_REVIEW, ON_TIME, Merchant, Order, RateCard, RoutingEngine,
)

SKU = "X"


def merchants(cap=None):
    return {"M": Merchant("M", "Test merchant", cap)}


def stocked(atl=10, dal=10, phx=10, **kw):
    return sd.make_state({("ATL", SKU): atl, ("DAL", SKU): dal, ("PHX", SKU): phx}, **kw)


def order(oid="T", promised=None, region="East", placed=None):
    return Order(oid, "M", SKU, region, placed or sd.at(9, 0), promised or sd.on(11, 2))


def table(decision):
    return {(o.fc_id, o.service): (o.cost, o.arrival, o.meets_date) for o in decision.options}


# ---- rate card ---------------------------------------------------------------


def test_rate_card_multipliers():
    rc = RateCard()
    assert rc.quote("East", "East", "Ground") == (5, 3)
    assert rc.quote("Central", "East", "Ground") == (10, 6)
    assert rc.quote("West", "East", "Ground") == (15, 9)
    assert rc.quote("West", "East", "Express") == (45, 3)
    for shopper in ("West", "Central", "East"):  # Dallas never above 2x
        assert rc.multiplier("Central", shopper) <= 2


# ---- README 2.1 ----------------------------------------------------------------


def test_order_2_1_atlanta_out_of_stock():
    eng = RoutingEngine(stocked(atl=0), merchants())
    d = eng.route_order(order())
    t = table(d)
    assert t[("DAL", "Ground")] == (10, sd.on(11, 5), False)
    assert t[("DAL", "Air")] == (20, sd.on(11, 3), False)
    assert t[("DAL", "Express")] == (30, sd.on(11, 1), True)
    assert t[("PHX", "Ground")] == (15, sd.on(11, 8), False)
    assert t[("PHX", "Air")] == (30, sd.on(11, 5), False)
    assert t[("PHX", "Express")] == (45, sd.on(11, 2), True)
    assert not any(fc == "ATL" for fc, _ in t)
    assert "ATL" in d.removed_fcs
    assert d.status == ON_TIME
    assert (d.chosen.fc_id, d.chosen.service, d.chosen.cost) == ("DAL", "Express", 30)
    assert d.promise_premium == 20
    assert d.cheapest_overall.label == "DAL Ground"
    assert d.is_complete()
    assert all(o.reasons for o in d.options)


def test_nov3_variation_engine_vs_baselines():
    st = stocked(atl=0)
    o = order(promised=sd.on(11, 3))
    a = metrics.baseline_a(st, merchants(), [o])[0]
    b = metrics.baseline_b(st, merchants(), [o])[0]
    assert (a.option.label, a.option.cost, a.option.arrival) == ("DAL Ground", 10, sd.on(11, 5))
    assert not a.option.meets_date
    assert (b.option.label, b.option.cost) == ("DAL Express", 30)
    assert b.option.cost - b.cheapest_cost == 20
    d = RoutingEngine(st, merchants()).route_order(o)
    assert (d.chosen.label, d.chosen.cost, d.chosen.arrival) == ("DAL Air", 20, sd.on(11, 3))
    assert d.promise_premium == 10


def test_oct31_promise_is_at_risk():
    d = RoutingEngine(stocked(atl=0), merchants()).route_order(order(promised=sd.on(10, 31)))
    assert d.status == AT_RISK
    assert d.chosen.label == "DAL Express"
    assert d.revised_edd == sd.on(11, 1)
    assert d.is_complete()


# ---- competing orders ----------------------------------------------------------


def _competing():
    a = Order("A", "M", SKU, "East", sd.at(9, 5), sd.on(10, 31))
    b = Order("B", "M", SKU, "East", sd.at(9, 0), sd.on(11, 2))  # B arrived first
    return a, b


def test_first_come_first_served_misses_a_promise():
    a, b = _competing()
    ds = {d.order.id: d for d in RoutingEngine(stocked(atl=1), merchants()).route_stream([a, b])}
    assert ds["B"].chosen.label == "ATL Ground"
    assert ds["A"].status == AT_RISK


def test_competing_orders_resolved_jointly_keep_both_promises():
    a, b = _competing()
    ds = {d.order.id: d for d in RoutingEngine(stocked(atl=1), merchants()).route_batch([a, b])}
    assert (ds["A"].chosen.label, ds["A"].chosen.cost) == ("ATL Express", 15)
    assert (ds["B"].chosen.label, ds["B"].chosen.cost) == ("DAL Express", 30)
    assert ds["A"].status == ds["B"].status == ON_TIME
    assert ds["A"].chosen.cost + ds["B"].chosen.cost == 45
    assert any("First come, first served would have kept only 1" in n for n in ds["A"].notes)
    assert all(d.is_complete() for d in ds.values())


def test_joint_resolution_reserves_stock():
    a, b = _competing()
    eng = RoutingEngine(stocked(atl=1), merchants())
    eng.route_batch([a, b])
    assert eng.state.available("ATL", SKU) == 0
    assert eng.state.available("DAL", SKU) == 9


def test_stock_is_never_oversold():
    orders = [Order(f"N{i}", "M", SKU, "East", sd.at(9, i), sd.on(11, 5)) for i in range(5)]
    eng = RoutingEngine(sd.make_state({("ATL", SKU): 2, ("DAL", SKU): 1}), merchants())
    ds = eng.route_batch(orders)
    shipped = [d for d in ds if d.chosen]
    assert len(shipped) == 3
    assert sum(1 for d in shipped if d.chosen.fc_id == "ATL") == 2
    assert sum(1 for d in shipped if d.chosen.fc_id == "DAL") == 1
    assert sum(1 for d in ds if d.status == "UNFULFILLABLE") == 2
    assert all(d.is_complete() for d in ds)


# ---- merchant cost cap ----------------------------------------------------------


def test_cap_30_removes_phoenix_express():
    d = RoutingEngine(stocked(atl=0), merchants(30)).route_order(order())
    assert d.chosen.label == "DAL Express"
    px = next(o for o in d.options if o.label == "PHX Express")
    assert px.over_cap and "cap" in " ".join(px.reasons)


def test_cap_25_ships_dallas_air_and_flags():
    d = RoutingEngine(stocked(atl=0), merchants(25)).route_order(order())
    assert d.status == AT_RISK
    assert (d.chosen.label, d.chosen.cost, d.chosen.arrival) == ("DAL Air", 20, sd.on(11, 3))
    assert d.revised_edd == sd.on(11, 3)
    assert d.cost_to_meet_date == 30
    assert d.chosen.cost <= 25  # the cap overrides the promise


def test_cap_below_every_option_goes_to_review():
    d = RoutingEngine(stocked(atl=0), merchants(5)).route_order(order())
    assert d.status == NEEDS_REVIEW and d.chosen is None
    assert d.is_complete()


# ---- re-shop near the cutoff ----------------------------------------------------


def _reshop(hour, minute):
    eng = RoutingEngine(stocked(), merchants())
    first = eng.route_order(order(promised=sd.on(11, 5)))
    assert first.chosen.label == "ATL Ground"
    new = eng.reshop(first, sd.at(hour, minute))
    return eng, new


def test_reshop_trailer_made():
    eng, new = _reshop(12, 30)
    assert (new.chosen.label, new.chosen.cost, new.chosen.arrival) == ("DAL Ground", 10, sd.on(11, 5))
    assert new.status == ON_TIME and new.reshopped_from == "ATL"
    assert "ATL" in new.removed_fcs
    assert eng.state.available("ATL", SKU) == 9  # damaged unit written off, reservation released


def test_reshop_trailer_missed_upgrades_to_air():
    _, new = _reshop(13, 30)
    t = table(new)
    assert t[("DAL", "Ground")] == (10, sd.on(11, 6), False)  # ships Oct 31, arrives Nov 6
    # Only the Ground trailer has a cutoff in the README, so Air still ships Oct 30
    # (4 days -> Nov 3). The README text says Nov 4; see "Assumptions" in the README.
    assert (new.chosen.label, new.chosen.cost, new.chosen.arrival) == ("DAL Air", 20, sd.on(11, 3))
    assert new.status == ON_TIME


def test_handling_buffer_decides_the_cutoff():
    eng = RoutingEngine(stocked(handling_buffer_minutes=0), merchants())
    first = eng.route_order(order(promised=sd.on(11, 5)))
    new = eng.reshop(first, sd.at(13, 30))  # no buffer: 1:30 PM still makes a 2 PM trailer
    assert new.chosen.label == "DAL Ground"


# ---- capacity and ranking ----------------------------------------------------------


def test_capacity_limit_removes_fc():
    eng = RoutingEngine(stocked(daily_capacity=1), merchants())
    first = eng.route_order(order("T1"))
    second = eng.route_order(order("T2"))
    assert first.chosen.fc_id == "ATL"
    assert "daily capacity" in second.removed_fcs["ATL"]
    assert second.chosen.fc_id != "ATL"


def test_ties_break_on_earlier_arrival_then_proximity():
    # Dallas Express to the East costs $30 and so does Phoenix Air; a Nov 2 promise
    # is met by both, and Dallas arrives earlier (Nov 1 vs Nov 5 is late, so use Phoenix Express).
    d = RoutingEngine(stocked(atl=0, dal=0), merchants()).route_order(order(promised=sd.on(11, 5)))
    assert d.chosen.label == "PHX Air"  # only Phoenix left: cheapest option that meets Nov 5


# ---- sample batch ------------------------------------------------------------------


def _sample():
    merch = sd.make_merchants()
    st = sd.make_state(sd.sample_inventory())
    orders = sd.sample_orders()
    return merch, st, orders, RoutingEngine(st.copy(), merch).route_batch(orders)


def test_sample_batch_every_decision_explained():
    _, _, _, ds = _sample()
    assert len(ds) == 14
    assert all(d.is_complete() for d in ds)


def test_sample_batch_cap_compliance():
    merch, _, _, ds = _sample()
    for d in ds:
        cap = merch[d.order.merchant_id].cost_cap
        if d.chosen and cap is not None:
            assert d.chosen.cost <= cap, d.order.id


def test_sample_batch_beats_fcfs_and_baseline_a_on_time():
    merch, st, orders, ds = _sample()
    joint = metrics.summarize("Engine", metrics.outcomes_from_decisions(ds))
    fcfs = metrics.summarize(
        "FCFS", metrics.outcomes_from_decisions(RoutingEngine(st.copy(), merch).route_stream(orders))
    )
    a = metrics.summarize("A", metrics.baseline_a(st, merch, orders))
    assert joint.on_time >= fcfs.on_time
    assert joint.on_time_rate > a.on_time_rate


def test_sample_batch_never_oversells():
    _, st, _, ds = _sample()
    used = {}
    for d in ds:
        if d.chosen:
            key = (d.chosen.fc_id, d.order.sku)
            used[key] = used.get(key, 0) + d.order.qty
    for key, n in used.items():
        assert n <= st.on_hand[key], key


if __name__ == "__main__":
    import sys
    failed = 0
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    for name, fn in tests:
        try:
            fn()
            print(f"PASS {name}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"FAIL {name}: {type(exc).__name__}: {exc}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)
