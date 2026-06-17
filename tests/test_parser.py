"""Parser tests, including the exact GABFXARMY CIRCLE format from the screenshot.
Run:  python -m pytest -q   (or)  python tests/test_parser.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.parser import parse  # noqa: E402

GABFX = """Gold SELL Now INSTANT📈
@ 4344.5 - 4352
Take Profit 1 - 4340
Take Profit 2 - 4337
Stoploss - 4354"""


def test_gabfx_sell():
    s = parse(GABFX)
    assert s is not None
    assert s.direction == "SELL"
    assert s.entry_low == 4344.5 and s.entry_high == 4352
    assert s.sl == 4354
    assert s.tps == [4340, 4337]   # descending for a SELL
    assert s.instant is True
    assert s.is_sane()[0]


def test_buy_variant():
    s = parse("XAUUSD BUY now @ 4300-4305\nTP1: 4312\nTP2 4320\nSL - 4294")
    assert s is not None
    assert s.direction == "BUY"
    assert s.sl == 4294
    assert s.tps == [4312, 4320]   # ascending for a BUY
    assert s.is_sane()[0]


def test_single_price_entry():
    s = parse("Gold buy @ 4310\ntp 4318\nsl 4304")
    assert s is not None
    assert s.entry_low == s.entry_high == 4310


def test_rejects_inconsistent():
    # SELL but SL below entry and TP above -> mis-parse, must be rejected
    assert parse("Gold sell @ 4300\nTP 4350\nSL 4280") is None


def test_ignores_chatter():
    assert parse("good morning team, big moves today 🚀") is None


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all passed")
