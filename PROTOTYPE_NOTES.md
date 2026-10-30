## 5.0 Prototype: how to run it

Python 3.9+, standard library only.

```
python test_engine.py     # 20 tests; reproduces every worked example in this README
python run_demo.py        # sample batch, both baselines, metrics, kill-threshold checks
python run_demo.py --explain O-1005 O-1010   # full decision record for chosen orders
```

| File | What it does |
|---|---|
| `engine.py` | Rate card, eligibility, option building, ranking, decision records, cost cap, at-risk flagging, joint resolution of competing orders, re-shop |
| `sample_data.py` | 3 FCs, 4 merchants (different sizes, footprints, caps), 14 orders |
| `metrics.py` | Baselines A and B, on-time rate, cost per on-time delivery, kill-threshold checks |
| `run_demo.py` | Runs everything and writes `decisions.json` |
| `test_engine.py` | Worked examples from 2.1 and 3.3 as assertions |

## 5.1 How the code maps to the Decision Flow

1. **Eligibility**: `build_options` drops FCs with `on hand - reserved < qty` or no capacity left, and records why.
2. **Options**: every remaining FC x service is priced with the rate card (1x/2x/3x on cost and days). Ship date is today if the order can be handed off before the cutoff minus the handling buffer, otherwise tomorrow.
3. **Rank**: per FC, the cheapest option that meets the date and cap. Across FCs: cost, then earlier arrival, then closer FC.
4. **Record**: `Decision.explain()` lists the chosen option, every rejected option with a reason, and the promise premium (chosen cost minus cheapest option overall, including late ones).
5. **Reserve**: one unit is reserved at the chosen FC.

Edge cases: out of stock (step 1), cap (removes options before ranking), no option meets the date (earliest arrival shipped, status `AT_RISK`, revised EDD recorded), cap leaves nothing (`NEEDS_REVIEW`), FC cannot fill (`reshop`, re-runs from the current time without that FC), competing orders (`route_batch`).

## 5.2 Assumptions and shortcuts

- **Sequential vs. joint (resolves the conflict between step 5 and 3.3).** Orders in the same batch window that compete for scarce stock or capacity are resolved together by exact search: most promises kept, then most orders filled, then lowest total cost, then the earlier order. Orders that do not compete are routed one at a time. Above 8 competing orders the solver falls back to a greedy pass (tightest promise first). The batch window length is a product decision; the prototype treats the whole sample file as one window.
- **Tie in the sample batch.** O-1005 loses Atlanta Express to O-1004 and O-1006 because "most promises, then lowest cost" ties on promises (2 of 3) and the cheaper assignment wins. A merchant may want a different rule (for example tightest promise first); this is a rule change in one place (`_solve_component`'s score).
- **Cutoffs.** Only the Dallas Ground trailer (2 PM) is given in the PRD. It is the only cutoff in the sample data. Air and Express are assumed to ship the same day.
- **Handling buffer** is 60 minutes (configurable). An order must reach the FC at least that long before the cutoff.
- **Calendar days**, no weekends or holidays. Transit days scale with the same multiplier as cost.
- **Single-item orders**, one unit of one SKU. No split shipments.
- **Default service is Ground** for Baseline A.
- **On-time is planned, not actual.** There is no carrier variance, so "predicted vs. actual on-time gap" cannot be measured here.
- **Promise premium limit** in the kill checks is set to $15 average per order. This is a placeholder.
- **Re-shop wording.** The PRD says the Dallas Air re-shop arrives Nov 4. In the code, Air has no cutoff, so a 1:30 PM re-shop still ships Oct 30 and Air arrives Nov 3. To match the PRD, give Dallas Air a cutoff or a general Dallas cutoff.

## 5.3 First-run findings (sample batch of 14 orders)

| | On-time | Spend | $ per on-time delivery |
|---|---|---|---|
| Baseline A (closest FC, Ground) | 5/14 (36%) | $110 | $22.00 |
| Baseline B (fastest service) | 14/14 (100%) | $330 | $23.57 |
| Engine | 13/14 (93%) | $225 | $17.31 |

- The engine clears every kill threshold on this data: higher on-time rate than A, lower cost per on-time delivery than A and B, 100% explanation completeness, 0 cap exceptions.
- Baseline B is the only way to get 14/14, and it costs $105 more than the engine for one extra on-time order. It also ships one order above its merchant's cap.
- The one at-risk order (O-1005) is a result of a $25 cap plus three orders competing for two units in Atlanta. The record says so, and says meeting the date would have required a $30 option.
- This is fabricated data. The result is evidence that the logic behaves as specified, not that it will perform on real orders.
