"""Break-even + trailing decision logic, on the real GABFXARMY SELL scenario:
entry ~4348.25, SL 4354, TP1 4340.  Run: python tests/test_manager.py
"""

import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.manager import Group, plan_sl_update  # noqa: E402

CFG = SimpleNamespace(
    be_enabled=True, be_offset=1.0,
    trail_enabled=True, trail_start=5.0, trail_distance=3.0, trail_step=0.5,
)


def sell_group(sl=4354.0, be_done=False):
    return Group("g1", "XAUUSD", "SELL", entry=4348.25, sl=sl, tp1=4340.0,
                 tickets=[1, 2], be_done=be_done)


def test_no_action_far_from_target():
    # price barely moved (4347) — not in profit by trail_start, TP1 not reached
    d = plan_sl_update(sell_group(), 4347.0, CFG)
    assert d.new_sl is None and not d.be_armed


def test_trailing_kicks_in():
    # profit = 4348.25 - 4341 = 7.25 >= 5 → trail to 4341 + 3 = 4344
    d = plan_sl_update(sell_group(), 4341.0, CFG)
    assert d.new_sl == 4344.0


def test_breakeven_at_tp1():
    # price hits TP1 (4340) → BE armed; SL → entry - offset = 4347.25,
    # but trailing is also active (profit 8.25) → 4343, the tighter wins
    d = plan_sl_update(sell_group(), 4340.0, CFG)
    assert d.be_armed
    assert d.new_sl == 4343.0   # min(4347.25, 4340+3)


def test_breakeven_only_when_trailing_off():
    cfg = SimpleNamespace(**{**CFG.__dict__, "trail_enabled": False})
    d = plan_sl_update(sell_group(), 4340.0, cfg)
    assert d.be_armed and d.new_sl == 4347.25   # entry - 1.0


def test_never_loosens():
    # SL already tightened to 4343; price 4342.9 would trail to 4345.9 (looser) → no-op
    d = plan_sl_update(sell_group(sl=4343.0), 4342.9, CFG)
    assert d.new_sl is None


def test_step_debounce():
    # current SL 4344, price 4341.2 → trail 4344.2 (looser for SELL) → None;
    # price 4340.8 → trail 4343.8, improvement 0.2 < step 0.5 → None
    assert plan_sl_update(sell_group(sl=4344.0), 4340.8, CFG).new_sl is None


def test_buy_trailing_and_be():
    g = Group("g2", "XAUUSD", "BUY", entry=4300.0, sl=4294.0, tp1=4312.0,
              tickets=[3])
    # price 4312 hits TP1; BE → 4301; trailing profit 12 → 4312-3 = 4309 (tighter, higher)
    d = plan_sl_update(g, 4312.0, CFG)
    assert d.be_armed and d.new_sl == 4309.0


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all passed")
