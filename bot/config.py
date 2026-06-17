"""Config loader. Reads config.yaml + environment for secrets."""

from __future__ import annotations

import os
from dataclasses import dataclass

import yaml


def _load_dotenv(path: str = ".env") -> None:
    """Tiny .env loader (no dependency). Lines of KEY=VALUE; existing env wins."""
    if not os.path.exists(path):
        return
    for line in open(path):
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


@dataclass
class Config:
    # --- Telegram (Telethon user session = you, the member) ---
    api_id: int
    api_hash: str
    source_channel: str | int        # @username, t.me link, or numeric id
    session_name: str

    # --- Confirm bot (separate bot from @BotFather) ---
    bot_token: str
    owner_id: int                    # your Telegram user id (where cards are sent)

    # --- Broker / MT5 ---
    symbol: str
    mt5_login: int
    mt5_password: str
    mt5_server: str
    mt5_terminal_path: str

    # --- Risk ---
    risk_pct: float
    contract_size: float
    min_lot: float
    max_lot: float
    lot_step: float
    slippage_points: int
    magic: int

    # --- Safety ---
    dry_run: bool
    demo_balance: float
    max_open_positions: int
    daily_loss_limit: float          # absolute account-currency loss that halts trading
    confirm_timeout_sec: int

    # --- Position management (break-even + trailing) ---
    manage_enabled: bool
    manage_poll_sec: int
    be_enabled: bool
    be_offset: float
    trail_enabled: bool
    trail_start: float
    trail_distance: float
    trail_step: float

    # --- Optional LLM fallback ---
    use_llm_fallback: bool
    anthropic_model: str

    @classmethod
    def load(cls, path: str = "config.yaml") -> "Config":
        _load_dotenv()
        with open(path) as f:
            raw = yaml.safe_load(f) or {}

        def env(key, default=None):
            return os.environ.get(key, default)

        tg = raw.get("telegram", {})
        bot = raw.get("bot", {})
        mt5 = raw.get("mt5", {})
        risk = raw.get("risk", {})
        safety = raw.get("safety", {})
        manage = raw.get("manage", {})
        be = manage.get("breakeven", {})
        trail = manage.get("trailing", {})
        llm = raw.get("llm", {})

        return cls(
            api_id=int(env("TG_API_ID", tg.get("api_id", 0))),
            api_hash=env("TG_API_HASH", tg.get("api_hash", "")),
            source_channel=tg.get("source_channel", ""),
            session_name=tg.get("session_name", "user"),
            bot_token=env("BOT_TOKEN", bot.get("token", "")),
            owner_id=int(env("OWNER_ID", bot.get("owner_id", 0))),
            symbol=mt5.get("symbol", "XAUUSD"),
            mt5_login=int(env("MT5_LOGIN", mt5.get("login", 0))),
            mt5_password=env("MT5_PASSWORD", mt5.get("password", "")),
            mt5_server=env("MT5_SERVER", mt5.get("server", "")),
            mt5_terminal_path=mt5.get("terminal_path", ""),
            risk_pct=float(risk.get("risk_pct", 0.01)),
            contract_size=float(risk.get("contract_size", 100.0)),
            min_lot=float(risk.get("min_lot", 0.01)),
            max_lot=float(risk.get("max_lot", 5.0)),
            lot_step=float(risk.get("lot_step", 0.01)),
            slippage_points=int(risk.get("slippage_points", 20)),
            magic=int(risk.get("magic", 778899)),
            dry_run=bool(safety.get("dry_run", True)),
            demo_balance=float(safety.get("demo_balance", 10000.0)),
            max_open_positions=int(safety.get("max_open_positions", 6)),
            daily_loss_limit=float(safety.get("daily_loss_limit", 300.0)),
            confirm_timeout_sec=int(safety.get("confirm_timeout_sec", 300)),
            manage_enabled=bool(manage.get("enabled", True)),
            manage_poll_sec=int(manage.get("poll_sec", 5)),
            be_enabled=bool(be.get("enabled", True)),
            be_offset=float(be.get("offset", 1.0)),
            trail_enabled=bool(trail.get("enabled", True)),
            trail_start=float(trail.get("start", 5.0)),
            trail_distance=float(trail.get("distance", 3.0)),
            trail_step=float(trail.get("step", 0.5)),
            use_llm_fallback=bool(llm.get("enabled", False)),
            anthropic_model=llm.get("model", "claude-haiku-4-5-20251001"),
        )
