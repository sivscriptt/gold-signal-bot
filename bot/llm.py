"""Optional Anthropic-backed fallback parser.

Only used when the regex parser fails. Returns a Signal or None. The numbers it
returns are re-validated by Signal.is_sane() in parser.parse(), so a hallucinated
or inconsistent extraction is rejected rather than traded.
"""

from __future__ import annotations

import json
import logging

from .parser import Signal

log = logging.getLogger("llm")

_PROMPT = """Extract a gold (XAUUSD) trade signal from the message below.
Return ONLY compact JSON, no prose:
{"direction":"BUY"|"SELL","entry_low":<num>,"entry_high":<num>,"sl":<num>,"tps":[<num>,...],"instant":true|false}
If the message is not a tradeable signal, return {"none":true}.

MESSAGE:
\"\"\"%s\"\"\""""


def make_fallback(model: str):
    try:
        import anthropic
    except Exception:
        log.warning("anthropic SDK not installed; LLM fallback disabled")
        return None

    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY

    def fallback(text: str) -> Signal | None:
        try:
            resp = client.messages.create(
                model=model,
                max_tokens=300,
                messages=[{"role": "user", "content": _PROMPT % text}],
            )
            body = resp.content[0].text.strip()
            body = body[body.find("{"): body.rfind("}") + 1]
            d = json.loads(body)
            if d.get("none"):
                return None
            return Signal(
                direction=str(d["direction"]).upper(),
                entry_low=float(d["entry_low"]),
                entry_high=float(d["entry_high"]),
                sl=float(d["sl"]),
                tps=[float(x) for x in d.get("tps", [])],
                instant=bool(d.get("instant", True)),
                raw=text.strip(),
            )
        except Exception as e:
            log.warning("LLM fallback failed: %s", e)
            return None

    return fallback
