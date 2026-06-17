"""Position sizing: convert account-risk % + SL distance into a lot size.

XAUUSD: contract size is 100 oz, so a 1.00 lot position gains/loses ~$100 per
$1.00 (= 100 "points" at 2-decimal pricing... but brokers quote gold to 2dp,
so 1 "point" = 0.01 and $1.00 move = $100/lot). We work in PRICE units to stay
broker-agnostic:

    risk_$        = balance * risk_pct
    sl_distance   = |entry - sl|              # in price (e.g. 4354 - 4348 = 6.0)
    value_per_lot = sl_distance * contract_size   # $ lost per 1.0 lot if SL hit
    lots          = risk_$ / value_per_lot
"""

from __future__ import annotations

import math


def lot_for_risk(
    balance: float,
    risk_pct: float,
    entry: float,
    sl: float,
    contract_size: float = 100.0,
    min_lot: float = 0.01,
    max_lot: float = 100.0,
    lot_step: float = 0.01,
) -> float:
    risk_cash = balance * risk_pct
    sl_distance = abs(entry - sl)
    if sl_distance <= 0:
        return 0.0
    value_per_lot = sl_distance * contract_size
    lots = risk_cash / value_per_lot
    # snap down to broker lot step, clamp to limits
    lots = math.floor(lots / lot_step) * lot_step
    lots = max(min_lot, min(lots, max_lot))
    return round(lots, 2)


def split_lots(total_lot: float, n: int, lot_step: float = 0.01, min_lot: float = 0.01) -> list[float]:
    """Split a total lot across n TP legs as evenly as the lot step allows.
    Remainder is added to the first (nearest-TP) leg."""
    if n <= 0:
        return []
    steps = round(total_lot / lot_step)
    base = steps // n
    rem = steps - base * n
    legs = []
    for i in range(n):
        s = base + (1 if i < rem else 0)
        legs.append(max(min_lot, round(s * lot_step, 2)))
    return legs
