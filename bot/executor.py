"""MT5 order execution. Real on Windows (MetaTrader5 package); dry-run elsewhere.

The MetaTrader5 Python package is Windows-only and talks to a running MT5
terminal on the same machine. On macOS/Linux (or when config.dry_run is true)
we use a stub that logs the orders it *would* place, so the whole pipeline —
listen → parse → size → confirm — is testable without a broker.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from .parser import Signal
from .sizing import lot_for_risk, split_lots

log = logging.getLogger("executor")


def sum_deal_pnl(deals, magic: int) -> float:
    """Net realized P&L (profit + commission + swap) across closed deals tagged
    with our magic. Pure — testable with any deal-like objects."""
    return sum(d.profit + d.commission + d.swap for d in deals if d.magic == magic)

try:
    import MetaTrader5 as mt5  # type: ignore
    HAVE_MT5 = True
except Exception:  # pragma: no cover - absent on mac/linux
    mt5 = None
    HAVE_MT5 = False


@dataclass
class Order:
    direction: str
    lot: float
    entry: float
    sl: float
    tp: float


@dataclass
class ExecResult:
    ok: bool
    detail: str
    orders: list[Order]
    tickets: list[int] = field(default_factory=list)


class Executor:
    def __init__(self, cfg):
        self.cfg = cfg
        self.live = HAVE_MT5 and not cfg.dry_run
        self._connected = False
        self._dry_ticket = 0   # fake ticket source for dry-run group tracking

    # ---- connection -------------------------------------------------------
    def connect(self) -> bool:
        if not self.live:
            log.info("DRY-RUN executor (MT5 %s, dry_run=%s)",
                     "present" if HAVE_MT5 else "absent", self.cfg.dry_run)
            return True
        # Only pass `path` when set. MT5 rejects path=None with
        # (-2, 'Invalid "path" argument'); omitting it lets MT5 auto-detect
        # the already-running terminal.
        init_kwargs = dict(
            login=self.cfg.mt5_login,
            password=self.cfg.mt5_password,
            server=self.cfg.mt5_server,
        )
        if self.cfg.mt5_terminal_path:
            init_kwargs["path"] = self.cfg.mt5_terminal_path
        if not mt5.initialize(**init_kwargs):
            log.error("mt5.initialize failed: %s", mt5.last_error())
            return False
        self._connected = True
        info = mt5.account_info()
        log.info("MT5 connected: %s balance=%.2f", info.login, info.balance)
        return True

    def balance(self) -> float:
        if self.live and self._connected:
            return float(mt5.account_info().balance)
        return float(self.cfg.demo_balance)

    def current_price(self, side: str) -> float | None:
        """Bid for SELL, Ask for BUY."""
        if self.live and self._connected:
            tick = mt5.symbol_info_tick(self.cfg.symbol)
            if not tick:
                return None
            return tick.bid if side == "SELL" else tick.ask
        return None  # unknown in dry-run

    # ---- planning ---------------------------------------------------------
    def plan(self, sig: Signal) -> list[Order]:
        """Turn a Signal into concrete per-TP orders with computed lots.
        Does NOT place anything — used to build the confirmation card."""
        bal = self.balance()
        entry = self.current_price(sig.direction) or sig.entry_mid
        total = lot_for_risk(
            balance=bal,
            risk_pct=self.cfg.risk_pct,
            entry=entry,
            sl=sig.sl,
            contract_size=self.cfg.contract_size,
            min_lot=self.cfg.min_lot,
            max_lot=self.cfg.max_lot,
            lot_step=self.cfg.lot_step,
        )
        tps = sig.tps or [sig.entry_mid]
        legs = split_lots(total, len(tps), self.cfg.lot_step, self.cfg.min_lot)
        return [Order(sig.direction, lot, entry, sig.sl, tp)
                for lot, tp in zip(legs, tps)]

    def staleness_guard(self, sig: Signal) -> tuple[bool, str]:
        """Reject signals the market has already run past (price beyond TP1)."""
        px = self.current_price(sig.direction)
        if px is None:
            return True, "no live price (dry-run) — skipping staleness guard"
        tp1 = sig.tps[0]
        if sig.direction == "SELL" and px <= tp1:
            return False, f"price {px} already at/below TP1 {tp1} — too late"
        if sig.direction == "BUY" and px >= tp1:
            return False, f"price {px} already at/above TP1 {tp1} — too late"
        return True, f"price {px} ok vs TP1 {tp1}"

    def _filling_mode(self):
        """Pick an order-filling mode the symbol actually supports.
        MetaQuotes-Demo gold typically rejects IOC; hardcoding it makes live
        order_send fail with retcode 10030. symbol_info.filling_mode is a
        bitmask of the allowed modes."""
        info = mt5.symbol_info(self.cfg.symbol)
        allowed = getattr(info, "filling_mode", 0) if info else 0
        if allowed & mt5.SYMBOL_FILLING_FOK:
            return mt5.ORDER_FILLING_FOK
        if allowed & mt5.SYMBOL_FILLING_IOC:
            return mt5.ORDER_FILLING_IOC
        return mt5.ORDER_FILLING_RETURN

    # ---- execution --------------------------------------------------------
    def execute(self, orders: list[Order]) -> ExecResult:
        if not self.live:
            tickets = []
            for o in orders:
                self._dry_ticket += 1
                tickets.append(self._dry_ticket)
                log.info("[DRY-RUN] would %s %.2f lot @ %.2f SL %.2f TP %.2f",
                         o.direction, o.lot, o.entry, o.sl, o.tp)
            return ExecResult(True, f"dry-run: {len(orders)} order(s) logged",
                              orders, tickets)

        placed: list[Order] = []
        tickets: list[int] = []
        order_type = mt5.ORDER_TYPE_SELL if orders[0].direction == "SELL" else mt5.ORDER_TYPE_BUY
        filling = self._filling_mode()
        for o in orders:
            tick = mt5.symbol_info_tick(self.cfg.symbol)
            price = tick.bid if o.direction == "SELL" else tick.ask
            req = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": self.cfg.symbol,
                "volume": o.lot,
                "type": order_type,
                "price": price,
                "sl": o.sl,
                "tp": o.tp,
                "deviation": self.cfg.slippage_points,
                "magic": self.cfg.magic,
                "comment": "gold-signal-bot",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": filling,
            }
            res = mt5.order_send(req)
            if res.retcode != mt5.TRADE_RETCODE_DONE:
                log.error("order_send failed: retcode=%s %s", res.retcode, res.comment)
                return ExecResult(False, f"leg failed: {res.comment}", placed, tickets)
            placed.append(o)
            tickets.append(int(res.order))
            log.info("filled %s %.2f @ %.2f SL %.2f TP %.2f ticket=%s",
                     o.direction, o.lot, price, o.sl, o.tp, res.order)
        return ExecResult(True, f"{len(placed)} leg(s) filled", placed, tickets)

    # ---- position management (used by PositionManager) --------------------
    def positions(self):
        """Open positions tagged with our magic (live only)."""
        if not (self.live and self._connected):
            return []
        rows = mt5.positions_get(symbol=self.cfg.symbol) or []
        return [p for p in rows if p.magic == self.cfg.magic]

    def price_ref(self, direction: str) -> float | None:
        """Reference price for managing a position: the side you'd close on —
        Ask to close a SELL, Bid to close a BUY."""
        if not (self.live and self._connected):
            return None
        tick = mt5.symbol_info_tick(self.cfg.symbol)
        if not tick:
            return None
        return tick.ask if direction == "SELL" else tick.bid

    def _min_stop_distance(self) -> float:
        """Broker's minimum SL distance from price, in price units (0 if unknown)."""
        info = mt5.symbol_info(self.cfg.symbol)
        if not info:
            return 0.0
        return info.trade_stops_level * info.point

    def modify_sl(self, position, new_sl: float) -> bool:
        """Move one position's SL, preserving its TP. Respects broker stop level."""
        tick = mt5.symbol_info_tick(self.cfg.symbol)
        if tick:
            px = tick.ask if position.type == mt5.POSITION_TYPE_SELL else tick.bid
            if abs(new_sl - px) < self._min_stop_distance():
                log.info("skip SL %.3f on %s: inside broker stop level", new_sl, position.ticket)
                return False
        req = {
            "action": mt5.TRADE_ACTION_SLTP,
            "symbol": self.cfg.symbol,
            "position": position.ticket,
            "sl": float(new_sl),
            "tp": float(position.tp),
            "magic": self.cfg.magic,
        }
        res = mt5.order_send(req)
        if res.retcode != mt5.TRADE_RETCODE_DONE:
            log.error("modify SL failed on %s: %s %s", position.ticket, res.retcode, res.comment)
            return False
        return True

    # ---- realized P&L (for the daily loss limit) --------------------------
    def realized_pnl_today(self) -> float | None:
        """Net realized P&L since local midnight for our magic, from MT5 deal
        history. None when not live (dry-run can't know broker fills)."""
        if not (self.live and self._connected):
            return None
        now = datetime.now()
        start = datetime(now.year, now.month, now.day)
        deals = mt5.history_deals_get(start, now + timedelta(seconds=1)) or []
        return sum_deal_pnl(deals, self.cfg.magic)

    def daily_loss(self) -> float | None:
        """Today's realized loss as a positive number (0 if flat/profitable).
        None in dry-run, so the caller falls back to its own stub."""
        pnl = self.realized_pnl_today()
        return None if pnl is None else max(0.0, -pnl)
