"""Fabricated sample data: 3 FCs, 4 merchants of different sizes and FC
footprints, and a batch of 14 orders placed on Oct 30, 2026.

Network (README 2.1): Phoenix = West, Dallas = Central, Atlanta = East.
The only cutoff specified in the README is Dallas's 2 PM Ground trailer.
"""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Dict, List, Optional, Tuple

from engine import FC, Merchant, NetworkState, Order, RateCard


def at(hour: int, minute: int = 0) -> datetime:
    """A time on Oct 30, 2026."""
    return datetime(2026, 10, 30, hour, minute)


def on(month: int, day: int) -> date:
    return date(2026, month, day)


def make_fcs(daily_capacity: int = 100) -> List[FC]:
    return [
        FC("PHX", "Phoenix", "West", daily_capacity),
        FC("DAL", "Dallas", "Central", daily_capacity, service_cutoffs={"Ground": time(14, 0)}),
        FC("ATL", "Atlanta", "East", daily_capacity),
    ]


def make_state(on_hand: Dict[Tuple[str, str], int], handling_buffer_minutes: int = 60,
               daily_capacity: int = 100) -> NetworkState:
    return NetworkState(make_fcs(daily_capacity), on_hand, RateCard(), handling_buffer_minutes)


def make_merchants() -> Dict[str, Merchant]:
    merchants = [
        Merchant("PEAK", "Peak Outdoors"),            # large, stocked in all 3 FCs, no cap
        Merchant("BLOOM", "Bloom Skincare", 25),      # mid-size, Dallas + Atlanta, $25 cap
        Merchant("DESERT", "Desert Threads"),         # small, Phoenix only, no cap
        Merchant("HARBOR", "Harbor Coffee", 30),      # small, Atlanta + Dallas, $30 cap
    ]
    return {m.id: m for m in merchants}


def sample_inventory() -> Dict[Tuple[str, str], int]:
    return {
        ("PHX", "TENT-1"): 50, ("DAL", "TENT-1"): 50, ("ATL", "TENT-1"): 50,
        ("DAL", "SERUM-1"): 30, ("ATL", "SERUM-1"): 2,     # Atlanta nearly out
        ("PHX", "TEE-1"): 20,
        ("ATL", "BEANS-1"): 1, ("DAL", "BEANS-1"): 10,     # Atlanta has one unit left
    }


def sample_orders() -> List[Order]:
    o = Order
    return [
        # PEAK: large merchant, stock everywhere
        o("O-1001", "PEAK", "TENT-1", "East", at(9, 0), on(11, 4)),
        o("O-1002", "PEAK", "TENT-1", "West", at(9, 10), on(11, 3)),
        o("O-1003", "PEAK", "TENT-1", "Central", at(9, 15), on(11, 2)),
        o("O-1013", "PEAK", "TENT-1", "East", at(9, 20), on(10, 31)),      # impossible promise -> at risk
        o("O-1014", "PEAK", "TENT-1", "Central", at(13, 30), on(11, 2)),   # misses Dallas Ground trailer
        # BLOOM: Atlanta has 2 units, three East orders want them; $25 cap
        o("O-1004", "BLOOM", "SERUM-1", "East", at(10, 0), on(11, 2)),
        o("O-1005", "BLOOM", "SERUM-1", "East", at(10, 5), on(10, 31)),
        o("O-1006", "BLOOM", "SERUM-1", "East", at(10, 10), on(11, 2)),
        # DESERT: Phoenix only, so everything ships from far away
        o("O-1007", "DESERT", "TEE-1", "East", at(11, 0), on(11, 8)),
        o("O-1008", "DESERT", "TEE-1", "Central", at(11, 5), on(11, 3)),
        o("O-1009", "DESERT", "TEE-1", "East", at(11, 10), on(11, 2)),
        # HARBOR: one unit left in Atlanta, two East orders compete; $30 cap
        o("O-1010", "HARBOR", "BEANS-1", "East", at(12, 0), on(10, 31)),
        o("O-1011", "HARBOR", "BEANS-1", "East", at(12, 5), on(11, 2)),
        o("O-1012", "HARBOR", "BEANS-1", "West", at(12, 10), on(11, 1)),
    ]
