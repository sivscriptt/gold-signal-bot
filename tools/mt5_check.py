"""Standalone MT5 connectivity + symbol + sizing check. WINDOWS ONLY.

Run on the box where the MT5 terminal is installed and logged in:

    python tools/mt5_check.py

It does NOT place any orders. It:
  1. connects with the MT5_* creds (from .env / config.yaml),
  2. prints account info (balance, currency, leverage),
  3. confirms your gold symbol exists & is tradable (and hunts for it if not),
  4. pulls a live tick,
  5. dry-runs position sizing for a sample SELL signal against the real balance.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.config import Config          # noqa: E402
from bot.sizing import lot_for_risk, split_lots   # noqa: E402

try:
    import MetaTrader5 as mt5
except Exception:
    print("✗ MetaTrader5 package not available — run this on the Windows box "
          "with MT5 installed (pip install MetaTrader5).")
    sys.exit(1)


def find_gold(symbol):
    """Return a usable gold symbol name, selecting it into Market Watch if needed."""
    info = mt5.symbol_info(symbol)
    if info is None:
        # search every symbol for a gold candidate (XAUUSD, GOLD, XAUUSD.m, etc.)
        cands = [s.name for s in (mt5.symbols_get() or [])
                 if "XAU" in s.name.upper() or "GOLD" in s.name.upper()]
        print(f"✗ '{symbol}' not found. Gold-like symbols on this broker: {cands or 'none'}")
        if not cands:
            return None
        symbol = cands[0]
        print(f"→ trying '{symbol}' instead")
        info = mt5.symbol_info(symbol)
    if info is not None and not info.visible:
        mt5.symbol_select(symbol, True)
        info = mt5.symbol_info(symbol)
    return symbol if info is not None else None


def main():
    cfg = Config.load("config.yaml")
    print(f"connecting to {cfg.mt5_server} as {cfg.mt5_login} ...")
    # Only pass `path` when it's set. MT5 rejects path=None with
    # (-2, 'Invalid "path" argument'); omitting it lets MT5 auto-detect
    # the already-running terminal.
    init_kwargs = dict(login=cfg.mt5_login, password=cfg.mt5_password,
                       server=cfg.mt5_server)
    if cfg.mt5_terminal_path:
        init_kwargs["path"] = cfg.mt5_terminal_path
    ok = mt5.initialize(**init_kwargs)
    if not ok:
        print(f"✗ initialize failed: {mt5.last_error()}")
        print("  → check MT5 terminal is running, login/password/server correct, "
              "and 'Algo Trading' is enabled (button in the toolbar).")
        sys.exit(1)

    acc = mt5.account_info()
    print(f"✓ connected. balance={acc.balance:.2f} {acc.currency}  "
          f"leverage=1:{acc.leverage}  trade_allowed={acc.trade_allowed}")

    symbol = find_gold(cfg.symbol)
    if not symbol:
        print("✗ no tradable gold symbol — cannot proceed.")
        mt5.shutdown(); sys.exit(1)
    if symbol != cfg.symbol:
        print(f"⚠ set  mt5.symbol: \"{symbol}\"  in config.yaml")

    si = mt5.symbol_info(symbol)
    tick = mt5.symbol_info_tick(symbol)
    print(f"✓ symbol {symbol}: bid={tick.bid} ask={tick.ask} "
          f"point={si.point} min_lot={si.volume_min} lot_step={si.volume_step} "
          f"stops_level={si.trade_stops_level}pts")

    # dry sizing for the screenshot signal: SELL, entry ~4348.25, SL 4354, TP1/2
    entry, sl, tps = 4348.25, 4354.0, [4340.0, 4337.0]
    total = lot_for_risk(acc.balance, cfg.risk_pct, entry, sl,
                         contract_size=cfg.contract_size,
                         min_lot=max(cfg.min_lot, si.volume_min),
                         max_lot=cfg.max_lot, lot_step=si.volume_step)
    legs = split_lots(total, len(tps), si.volume_step, max(cfg.min_lot, si.volume_min))
    print(f"✓ sizing @ {cfg.risk_pct*100:g}% risk on {acc.balance:.0f}: "
          f"{total} lot total → legs {legs} for TP {tps}")
    print("\nAll good. This was read-only — no orders placed.")
    mt5.shutdown()


if __name__ == "__main__":
    main()
