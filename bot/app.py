"""Wire everything together with Telethon.

Two Telethon clients share one asyncio loop:
  * user client  — logged in as YOU; listens to the source channel.
  * bot  client  — your @BotFather bot; sends the confirmation card with
                   inline [Approve]/[Reject] buttons and handles the tap.

Flow per incoming message:
  parse -> dedup -> kill-switch/daily-limit guards -> staleness guard
        -> build order plan -> DM confirmation card -> on Approve: execute.
"""

from __future__ import annotations

import asyncio
import logging

from telethon import TelegramClient, Button, events
from telethon.tl.types import InputPeerUser

from .config import Config
from .executor import Executor, Order
from .manager import PositionManager
from .parser import parse
from .state import State

log = logging.getLogger("app")


def _fmt_card(sig, orders: list[Order], note: str) -> str:
    tps = "\n".join(f"   TP{i+1}: {o.tp:g}  ({o.lot:g} lot)"
                    for i, o in enumerate(orders))
    total = sum(o.lot for o in orders)
    return (
        f"📥 *{sig.direction} {orders[0].entry:g}*  (entry zone {sig.entry_low:g}–{sig.entry_high:g})\n"
        f"   SL: {sig.sl:g}\n"
        f"{tps}\n"
        f"   total: {total:g} lot\n"
        f"   {note}"
    )


class TradingApp:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.state = State()
        self.execu = Executor(cfg)
        self.manager = PositionManager(cfg, self.execu, self.state)
        self.user = TelegramClient(cfg.session_name, cfg.api_id, cfg.api_hash)
        self.bot = TelegramClient(f"{cfg.session_name}_bot", cfg.api_id, cfg.api_hash)
        self.llm = None
        if cfg.use_llm_fallback:
            from .llm import make_fallback
            self.llm = make_fallback(cfg.anthropic_model)
        self.pending: dict[str, list[Order]] = {}
        # A bot can DM a user only after that user has /start-ed it. Addressing
        # the user as InputPeerUser(id, 0) lets the bot send by id without a
        # cached entity (which a fresh bot session lacks) — avoids the
        # "Could not find the input entity for PeerUser" ValueError.
        self.owner = InputPeerUser(cfg.owner_id, 0)

    # ---------------------------------------------------------------- run
    async def start(self):
        self.execu.connect()
        await self.bot.start(bot_token=self.cfg.bot_token)
        await self.user.start()  # interactive login first run (phone + code)

        self.user.add_event_handler(self._on_message,
                                     events.NewMessage(chats=self.cfg.source_channel))
        self.bot.add_event_handler(self._on_callback, events.CallbackQuery())

        if self.cfg.manage_enabled:
            asyncio.create_task(self._manage_loop())

        try:
            await self.bot.send_message(
                self.owner,
                f"🟢 gold-signal-bot up. dry_run={self.cfg.dry_run}. "
                f"manage={self.cfg.manage_enabled}. `touch STOP` to halt.")
        except Exception as e:
            log.warning("could not DM owner on startup (%s). Open your bot in "
                        "Telegram and press Start, then it will reach you.", e)
        log.info("listening on %s", self.cfg.source_channel)
        await self.user.run_until_disconnected()

    async def _manage_loop(self):
        """Poll open positions and apply break-even / trailing SL updates."""
        while True:
            await asyncio.sleep(self.cfg.manage_poll_sec)
            try:
                for ev in self.manager.tick():
                    await self._notify(ev)
            except Exception as e:
                log.warning("manage loop error: %s", e)

    # ------------------------------------------------------------ signals
    async def _on_message(self, event):
        text = event.message.message or ""
        mid = event.message.id

        sig = parse(text, llm_fallback=self.llm)
        if sig is None:
            return  # not a signal
        if self.state.already_seen(mid):
            return
        self.state.mark_seen(mid)

        if self.state.kill_switch_on():
            await self._notify("⛔ kill switch on (STOP file) — ignoring signal.")
            return
        hit, loss = self._daily_limit_hit()
        if hit:
            extra = f" (lost {loss:g}/{self.cfg.daily_loss_limit:g} today)" if loss is not None else ""
            await self._notify(f"⛔ daily loss limit reached{extra} — ignoring signal.")
            return

        fresh, why = self.execu.staleness_guard(sig)
        if not fresh:
            await self._notify(f"⏭️ skipped stale signal: {why}\n\n{text.strip()}")
            return

        orders = self.execu.plan(sig)
        key = str(mid)
        self.pending[key] = orders
        await self.bot.send_message(
            self.owner,
            _fmt_card(sig, orders, why),
            parse_mode="md",
            buttons=[[Button.inline("✅ Approve", f"ok:{key}".encode()),
                      Button.inline("❌ Reject", f"no:{key}".encode())]],
        )
        # auto-expire the confirmation
        asyncio.create_task(self._expire(key))

    async def _expire(self, key: str):
        await asyncio.sleep(self.cfg.confirm_timeout_sec)
        if key in self.pending:
            self.pending.pop(key, None)
            await self._notify(f"⌛ confirmation for {key} expired — not traded.")

    # ----------------------------------------------------------- buttons
    async def _on_callback(self, event):
        if event.sender_id != self.cfg.owner_id:
            return await event.answer("not authorized", alert=True)
        data = event.data.decode()
        action, _, key = data.partition(":")
        orders = self.pending.pop(key, None)
        if orders is None:
            return await event.answer("expired or already handled", alert=True)

        if action == "no":
            await event.edit("❌ Rejected — no trade placed.")
            return
        if self.state.kill_switch_on():
            await event.edit("⛔ kill switch on — not executing.")
            return
        hit, loss = self._daily_limit_hit()
        if hit:
            extra = f" (lost {loss:g}/{self.cfg.daily_loss_limit:g} today)" if loss is not None else ""
            await event.edit(f"⛔ daily loss limit reached{extra} — not executing.")
            return

        res = self.execu.execute(orders)
        if res.ok:
            if self.cfg.manage_enabled and res.tickets:
                # nearest TP (first leg) is TP1 — the break-even trigger level
                self.manager.register(
                    group_id=key, symbol=self.cfg.symbol,
                    direction=orders[0].direction, entry=orders[0].entry,
                    sl=orders[0].sl, tp1=orders[0].tp, tickets=res.tickets,
                )
            await event.edit(f"✅ Executed — {res.detail}\n🛡️ managing SL (BE + trailing)")
        else:
            await event.edit(f"⚠️ Execution problem — {res.detail}")

    def _daily_limit_hit(self) -> tuple[bool, float | None]:
        """Has today's realized loss reached the limit? Uses MT5 deal history
        when live; falls back to the in-memory stub in dry-run."""
        loss = self.execu.daily_loss()
        limit = self.cfg.daily_loss_limit
        if loss is None:
            return self.state.daily_limit_hit(limit), None
        return loss >= limit, loss

    async def _notify(self, msg: str):
        try:
            await self.bot.send_message(self.owner, msg)
        except Exception as e:
            log.warning("notify failed: %s", e)
