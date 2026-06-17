"""Post-fill position management: break-even + trailing stop.

Once orders are placed, this watches the open positions and ratchets their stop
loss:

  * Break-even — when price reaches TP1, move remaining legs' SL to entry
    (± a small offset to lock a touch of profit / cover spread). Fires once.
  * Trailing  — once price is in profit by `trail_start`, keep the SL
    `trail_distance` behind the best price seen. Only ever tightens.

The decision math lives in pure functions (no MT5, fully testable). `PositionManager`
is the thin live layer that polls MT5, applies the decisions, and reports back.

All distances are in PRICE units (e.g. a gold move of 3.0 = $3), matching sizing.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, asdict
from typing import Optional

log = logging.getLogger("manager")


# --------------------------------------------------------------------------- #
# Pure decision logic (no broker, no I/O) — unit-tested in tests/test_manager.py
# --------------------------------------------------------------------------- #
def is_tighter(direction: str, candidate: float, current: Optional[float]) -> bool:
    """Is `candidate` SL more protective than `current`?
    SELL stops sit above price → lower is tighter. BUY → higher is tighter."""
    if current is None:
        return True
    return candidate < current if direction == "SELL" else candidate > current


def tighter_of(direction: str, a: Optional[float], b: Optional[float]) -> Optional[float]:
    if a is None:
        return b
    if b is None:
        return a
    return min(a, b) if direction == "SELL" else max(a, b)


def breakeven_reached(direction: str, price: float, tp1: float) -> bool:
    """Has price moved far enough in our favour to have hit TP1?"""
    return price <= tp1 if direction == "SELL" else price >= tp1


def breakeven_sl(direction: str, entry: float, offset: float) -> float:
    """SL at entry, nudged `offset` into profit so BE locks a sliver, not zero."""
    return entry - offset if direction == "SELL" else entry + offset


def trailing_active(direction: str, price: float, entry: float, start: float) -> bool:
    profit = (entry - price) if direction == "SELL" else (price - entry)
    return profit >= start


def trail_sl(direction: str, price: float, distance: float) -> float:
    return price + distance if direction == "SELL" else price - distance


@dataclass
class SLDecision:
    new_sl: Optional[float] = None      # None → leave SL unchanged
    be_armed: bool = False              # price reached TP1 this evaluation
    reason: str = ""


def plan_sl_update(rec: "Group", price: float, cfg) -> SLDecision:
    """Combine break-even and trailing into a single SL decision for `rec`.

    Picks the *tighter* of any applicable candidate, and only returns it if it
    improves on the current SL by at least `trail_step` (debounces order spam)."""
    candidate: Optional[float] = None
    be_armed = rec.be_done
    reasons: list[str] = []

    if cfg.be_enabled and breakeven_reached(rec.direction, price, rec.tp1):
        be_armed = True
        if not rec.be_done:
            be = breakeven_sl(rec.direction, rec.entry, cfg.be_offset)
            candidate = tighter_of(rec.direction, candidate, be)
            reasons.append(f"BE→{be:g}")

    if cfg.trail_enabled and trailing_active(rec.direction, price, rec.entry, cfg.trail_start):
        tr = trail_sl(rec.direction, price, cfg.trail_distance)
        candidate = tighter_of(rec.direction, candidate, tr)
        reasons.append(f"trail→{tr:g}")

    if candidate is None or not is_tighter(rec.direction, candidate, rec.sl):
        return SLDecision(None, be_armed, "")
    if rec.sl is not None and abs(candidate - rec.sl) < cfg.trail_step:
        return SLDecision(None, be_armed, "")     # change too small, skip
    return SLDecision(round(candidate, 3), be_armed, " ".join(reasons))


# --------------------------------------------------------------------------- #
# Persisted group record (one signal = one group of legs)
# --------------------------------------------------------------------------- #
@dataclass
class Group:
    group_id: str
    symbol: str
    direction: str
    entry: float
    sl: float
    tp1: float
    tickets: list[int]
    be_done: bool = False

    @classmethod
    def from_dict(cls, d: dict) -> "Group":
        return cls(**d)

    def to_dict(self) -> dict:
        return asdict(self)


# --------------------------------------------------------------------------- #
# Live layer: poll MT5, apply decisions, emit human-readable events
# --------------------------------------------------------------------------- #
class PositionManager:
    def __init__(self, cfg, executor, state):
        self.cfg = cfg
        self.execu = executor
        self.state = state
        # rehydrate groups persisted across restarts
        self.groups: dict[str, Group] = {
            g["group_id"]: Group.from_dict(g) for g in state.get_groups()
        }

    def register(self, group_id: str, symbol: str, direction: str,
                 entry: float, sl: float, tp1: float, tickets: list[int]):
        g = Group(group_id, symbol, direction, entry, sl, tp1, list(tickets))
        self.groups[group_id] = g
        self._persist()
        log.info("managing group %s: %s entry %g sl %g tp1 %g tickets %s",
                 group_id, direction, entry, sl, tp1, tickets)

    def _persist(self):
        self.state.set_groups([g.to_dict() for g in self.groups.values()])

    def tick(self) -> list[str]:
        """One management pass. Returns human-readable event strings to relay.
        Live-only; in dry-run there are no positions/prices to act on."""
        if not self.execu.live:
            return []
        events: list[str] = []
        open_positions = {p.ticket: p for p in self.execu.positions()}

        for gid, rec in list(self.groups.items()):
            # prune tickets that have closed (TP/SL hit or manual)
            rec.tickets = [t for t in rec.tickets if t in open_positions]
            if not rec.tickets:
                del self.groups[gid]
                self._persist()
                events.append(f"📕 group {gid} fully closed — stopped managing.")
                continue

            price = self.execu.price_ref(rec.direction)
            if price is None:
                continue
            decision = plan_sl_update(rec, price, self.cfg)
            if decision.be_armed and not rec.be_done:
                rec.be_done = True
            if decision.new_sl is None:
                continue

            ok_any = False
            for t in rec.tickets:
                pos = open_positions[t]
                if self.execu.modify_sl(pos, decision.new_sl):
                    ok_any = True
            if ok_any:
                rec.sl = decision.new_sl
                self._persist()
                events.append(f"🛡️ group {gid}: SL → {decision.new_sl:g} "
                              f"({decision.reason}) @ price {price:g}")
        return events
