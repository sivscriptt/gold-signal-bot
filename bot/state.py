"""Runtime guards: message de-dup, daily loss limit, kill switch.

State is kept in a small JSON file so a restart doesn't re-fire old signals or
forget today's realized loss.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import date

log = logging.getLogger("state")

KILL_FILE = "STOP"   # `touch STOP` to halt all execution instantly


class State:
    def __init__(self, path: str = ".state.json"):
        self.path = path
        self.seen: set[int] = set()
        self.day: str = date.today().isoformat()
        self.realized_loss: float = 0.0
        self.groups: list[dict] = []      # managed position groups (BE/trailing)
        self._load()

    def _load(self):
        if os.path.exists(self.path):
            try:
                d = json.load(open(self.path))
                self.seen = set(d.get("seen", []))
                self.day = d.get("day", self.day)
                self.realized_loss = float(d.get("realized_loss", 0.0))
                self.groups = d.get("groups", [])
            except Exception as e:
                log.warning("could not load state: %s", e)
        self._roll_day()

    def _save(self):
        json.dump(
            {"seen": list(self.seen)[-500:], "day": self.day,
             "realized_loss": self.realized_loss, "groups": self.groups},
            open(self.path, "w"),
        )

    def _roll_day(self):
        today = date.today().isoformat()
        if today != self.day:
            self.day = today
            self.realized_loss = 0.0
            self._save()

    # --- guards -----------------------------------------------------------
    def kill_switch_on(self) -> bool:
        return os.path.exists(KILL_FILE)

    def already_seen(self, msg_id: int) -> bool:
        return msg_id in self.seen

    def mark_seen(self, msg_id: int):
        self.seen.add(msg_id)
        self._save()

    def daily_limit_hit(self, limit: float) -> bool:
        self._roll_day()
        return self.realized_loss >= limit

    def add_realized_loss(self, amount: float):
        self.realized_loss += max(0.0, amount)
        self._save()

    # --- managed groups (break-even / trailing) ---------------------------
    def get_groups(self) -> list[dict]:
        return self.groups

    def set_groups(self, groups: list[dict]):
        self.groups = groups
        self._save()
