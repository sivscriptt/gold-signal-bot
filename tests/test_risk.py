"""Position sizing + realized-P&L accounting. Run: python tests/test_risk.py"""

import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.sizing import lot_for_risk, split_lots   # noqa: E402
from bot.executor import sum_deal_pnl              # noqa: E402


def test_lot_scales_with_sl_distance():
    # tight SL → bigger lot, wide SL → smaller lot, same dollar risk
    tight = lot_for_risk(10000, 0.01, 4348, 4350)   # 2.0 distance
    wide = lot_for_risk(10000, 0.01, 4348, 4360)    # 12.0 distance
    assert tight > wide
    # $100 risk / (2.0 * 100) = 0.5 lot
    assert tight == 0.5


def test_lot_respects_min_and_step():
    # huge SL distance → would be < min_lot, clamps up to min
    assert lot_for_risk(100, 0.01, 4348, 4448, min_lot=0.01) == 0.01
    # result is snapped to lot_step (0.01) and never rounds up past the risk
    lot = lot_for_risk(10000, 0.01, 4348, 4353.75)   # 5.75 distance → 0.173..
    assert lot == 0.17


def test_split_lots_even_and_remainder():
    assert split_lots(0.10, 2) == [0.05, 0.05]
    # 0.17 over 2 → remainder goes to the first (nearest-TP) leg
    assert split_lots(0.17, 2) == [0.09, 0.08]
    assert round(sum(split_lots(0.17, 2)), 2) == 0.17


def deal(profit, commission=0.0, swap=0.0, magic=778899):
    return SimpleNamespace(profit=profit, commission=commission, swap=swap, magic=magic)


def test_sum_deal_pnl_filters_magic_and_sums_costs():
    deals = [
        deal(50.0, commission=-2.0, swap=-1.0),     # net +47 (ours)
        deal(-30.0, commission=-2.0),               # net -32 (ours)
        deal(999.0, magic=111),                     # someone else's EA — ignored
    ]
    assert sum_deal_pnl(deals, 778899) == 15.0       # 47 - 32


def test_sum_deal_pnl_loss_day():
    deals = [deal(-120.0), deal(-40.0, commission=-3.0)]
    pnl = sum_deal_pnl(deals, 778899)
    assert pnl == -163.0
    assert max(0.0, -pnl) == 163.0                   # daily_loss() would report 163


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all passed")
