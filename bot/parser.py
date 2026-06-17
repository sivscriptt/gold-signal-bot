"""Parse gold trading signals into a structured Signal.

Primary path is regex tuned to the GABFXARMY CIRCLE format, e.g.:

    Gold SELL Now INSTANT
    @ 4344.5 - 4352
    Take Profit 1 - 4340
    Take Profit 2 - 4337
    Stoploss - 4354

If the regex fails to find the essentials (direction + SL), and an Anthropic
API key is configured, we fall back to a tiny LLM extraction so the bot is
robust to wording drift. The LLM is NOT trusted to invent numbers — we re-check
its output is internally consistent before returning.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Signal:
    direction: str               # "BUY" or "SELL"
    entry_low: float             # lower bound of entry zone
    entry_high: float            # upper bound of entry zone (== entry_low if single price)
    sl: float
    tps: list[float] = field(default_factory=list)
    instant: bool = True         # market order now vs. pending limit
    raw: str = ""

    @property
    def entry_mid(self) -> float:
        return (self.entry_low + self.entry_high) / 2

    def is_sane(self) -> tuple[bool, str]:
        """Internal consistency check. For a SELL, SL must be ABOVE entry and
        TPs BELOW; mirror for BUY. Catches mis-parses before they reach a broker."""
        if self.direction not in ("BUY", "SELL"):
            return False, f"bad direction {self.direction!r}"
        if not self.tps:
            return False, "no take-profit found"
        e = self.entry_mid
        if self.direction == "SELL":
            if self.sl <= e:
                return False, f"SELL but SL {self.sl} not above entry {e}"
            if any(tp >= e for tp in self.tps):
                return False, f"SELL but a TP is not below entry {e}"
        else:  # BUY
            if self.sl >= e:
                return False, f"BUY but SL {self.sl} not below entry {e}"
            if any(tp <= e for tp in self.tps):
                return False, f"BUY but a TP is not above entry {e}"
        return True, "ok"


# Gold prices are >= 3 digits; this avoids capturing a TP index like "1" as a price.
_PRICE = r"\d{3,}(?:\.\d+)?"
_PRICE_RE = re.compile(_PRICE)

_DIR_RE = re.compile(r"\b(?:gold|xau(?:usd)?)\b.*?\b(buy|sell)\b", re.I | re.S)
_DIR_RE_ALT = re.compile(r"\b(buy|sell)\b.*?\b(?:gold|xau(?:usd)?)\b", re.I | re.S)
_INSTANT_RE = re.compile(r"\b(instant|now|market)\b", re.I)

_TP_LINE = re.compile(r"\b(?:take\s*profit|tp)", re.I)
_SL_LINE = re.compile(r"(?:stop\s*loss|stoploss|\bsl\b)", re.I)
_ENTRY_LINE = re.compile(r"(?:@|\bentry\b|\benter\b)", re.I)


def _prices(line: str) -> list[float]:
    return [float(x) for x in _PRICE_RE.findall(line)]


def parse_regex(text: str) -> Optional[Signal]:
    m = _DIR_RE.search(text) or _DIR_RE_ALT.search(text)
    if not m:
        return None
    direction = m.group(1).upper()

    # Field extraction is line-oriented: these signals put one field per line,
    # so we take the price(s) from each labelled line rather than one big regex.
    sl: Optional[float] = None
    tps: list[float] = []
    entry_prices: list[float] = []
    for line in text.splitlines():
        if _SL_LINE.search(line):
            nums = _prices(line)
            if nums:
                sl = nums[-1]
            continue
        if _TP_LINE.search(line):
            tps.extend(_prices(line))
            continue
        if _ENTRY_LINE.search(line):
            entry_prices.extend(_prices(line))

    if sl is None or not tps:
        return None
    tps = [t for t in dict.fromkeys(tps) if t != sl]

    if entry_prices:
        entry_low, entry_high = min(entry_prices), max(entry_prices)
    else:
        # No explicit entry → "instant" market signal; use SL/TP midpoint as a
        # placeholder; executor will use the live market price anyway.
        ref = [sl, *tps]
        entry_low = entry_high = sum(ref) / len(ref)

    sig = Signal(
        direction=direction,
        entry_low=entry_low,
        entry_high=entry_high,
        sl=sl,
        tps=sorted(tps, reverse=(direction == "SELL")),
        instant=bool(_INSTANT_RE.search(text)),
        raw=text.strip(),
    )
    ok, _ = sig.is_sane()
    return sig if ok else None


def parse(text: str, llm_fallback=None) -> Optional[Signal]:
    """Parse `text` into a Signal. Returns None if it isn't a tradeable signal.

    `llm_fallback` is an optional callable(text) -> Signal|None used only when
    the regex path fails. See bot/llm.py for an Anthropic-backed implementation.
    """
    sig = parse_regex(text)
    if sig is not None:
        return sig
    if llm_fallback is not None:
        sig = llm_fallback(text)
        if sig is not None:
            ok, _ = sig.is_sane()
            return sig if ok else None
    return None
