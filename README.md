# gold-signal-bot

Auto-trades gold signals from a Telegram channel (e.g. *GABFXARMY CIRCLE*) into
MetaTrader 5, with a **tap-to-confirm** step, risk-based position sizing, and
SL/TP attached to every order.

```
Telegram channel ──▶ parse ──▶ size ──▶ confirm card (✅/❌) ──▶ MT5 order_send
   (Telethon, you      (regex     (risk %    (your bot DMs you)      (SL + TP per leg)
    as a member)        +LLM)      → lots)
```

## Pieces

| File | Role |
|------|------|
| `bot/parser.py`   | Signal text → `Signal` (regex tuned to the channel + sanity checks + optional LLM fallback) |
| `bot/sizing.py`   | Risk % + SL distance → lot size; splits across TP legs |
| `bot/executor.py` | MT5 `order_send` with SL/TP + SL modification. **Dry-run stub off Windows / when `dry_run: true`** |
| `bot/manager.py`  | Post-fill SL management: break-even + trailing stop (pure decision logic + MT5 poll loop) |
| `bot/app.py`      | Telethon listener + confirm bot with inline buttons; ties it together |
| `bot/state.py`    | De-dup, daily-loss limit, `STOP` kill switch |
| `bot/config.py`   | Loads `config.yaml` + `.env` secrets |
| `tools/mt5_check.py` | Read-only broker diagnostic (connection, symbol, price, sizing) |
| `tests/`          | Parser / manager / risk tests incl. the exact GABFXARMY format |

## The one platform fact

The `MetaTrader5` Python package is **Windows-only** and talks to a running MT5
terminal on the same box. So:

- **Develop/test on your Mac** — everything runs in *dry-run* (orders are logged,
  not sent). You can fully exercise listen → parse → size → confirm here.
- **Run live on a cheap Windows VPS** — install MT5 + this bot there, set
  `dry_run: false`. The VPS stays on 24/7 with low latency to your broker.

## Setup

### 1. Install
```bash
cd ~/Desktop/gold-signal-bot
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt          # MetaTrader5 only installs on Windows
```

### 2. Telegram API (to read the channel as you)
- Go to https://my.telegram.org → **API development tools** → create an app.
- Put `api_id` / `api_hash` in `config.yaml` (or env `TG_API_ID`, `TG_API_HASH`).
- Set `source_channel` to the channel (`@username`, a `t.me/...` link, or its
  numeric id). You must be a member.

### 3. Confirmation bot (to message you + show buttons)
- In Telegram, message **@BotFather** → `/newbot` → copy the token.
- Get your numeric id from **@userinfobot**.
- Send your new bot any message once so it's allowed to DM you.

Put secrets in a **`.env`** file (gitignored, auto-loaded by `config.py`) rather
than in `config.yaml`:
```
BOT_TOKEN=123456:ABC...
OWNER_ID=123456789
TG_API_ID=...
TG_API_HASH=...
MT5_LOGIN=...
MT5_PASSWORD=...
MT5_SERVER=...
```
Anything set in the environment wins over `config.yaml`. **Never commit `.env`.**
If a token leaks, rotate it with @BotFather → `/revoke`.

### 4. Broker (only on the Windows VPS, for live)
- Install MetaTrader 5, log into your account.
- Fill `mt5.login/password/server` (or env `MT5_LOGIN/PASSWORD/SERVER`).
- **Confirm the exact symbol** — brokers name gold `XAUUSD`, `XAUUSD.m`, `GOLD`,
  etc. Set `mt5.symbol` to match, and `risk.contract_size` (usually 100).

### 5. Verify the broker (on the Windows box)
Before running the full bot, sanity-check the MT5 side — connection, that your
gold symbol exists, a live price, and sizing — without placing any orders:
```bash
python tools/mt5_check.py
```
If it reports the symbol is named something other than `XAUUSD` (common on
MetaQuotes-Demo, e.g. `XAUUSD.m` or `GOLD`), set `mt5.symbol` in `config.yaml`
to match. Make sure **Algo Trading** is enabled in the MT5 toolbar.

### 6. Run
```bash
python main.py
```
First run logs you into Telegram (phone number + code, once). You'll get a
"🟢 up" DM from your bot. New signals arrive as confirmation cards.

## Going live (do this in order)
1. **Dry-run on Mac** — verify parsing + confirmation cards look right.
2. **Demo account on the VPS** — `dry_run: false` but MT5 logged into a *demo*
   account. Watch real (fake-money) orders fill with correct SL/TP and lots.
3. **Live, tiny size** — drop `risk.risk_pct` low (e.g. 0.0025), keep
   confirm-each-trade on, watch for a few days.
4. Only then raise risk / consider full-auto.

## Safety
- **Kill switch:** `touch STOP` in the project dir halts all execution instantly.
  `rm STOP` to resume.
- **Daily loss limit:** `safety.daily_loss_limit` — once today's *realized* loss
  (summed from MT5 deal history for this bot's `magic`, profit + commission + swap)
  reaches it, no new trades are sent — checked both when a signal arrives and
  again at the moment you tap Approve. Resets at local midnight.
- **Max open positions:** `safety.max_open_positions`.
- **Staleness guard:** signals where price already ran past TP1 are skipped.
- **Sanity check:** a parsed signal whose SL/TP sit on the wrong side of entry is
  rejected, never traded.
- Confirmation cards **auto-expire** after `confirm_timeout_sec`.

## Stop-loss management (break-even + trailing)

After legs are placed, `PositionManager` polls open positions every
`manage.poll_sec` and ratchets the SL — it only ever *tightens*, never loosens:

- **Break-even** — when price reaches **TP1**, the remaining leg(s)' SL jumps to
  entry ± `breakeven.offset` (locks a sliver of profit / covers spread). Fires once.
- **Trailing** — once price is in profit by `trailing.start`, the SL follows
  `trailing.distance` behind the best price. `trailing.step` debounces tiny moves
  so it doesn't spam the broker with modify requests.

When both apply, the tighter SL wins. You get a 🛡️ DM each time the SL moves, and
a 📕 when a group fully closes. Group state is persisted in `.state.json`, so a
restart keeps managing open positions. Tune it all under `manage:` in `config.yaml`.

Worked example on the screenshot signal (SELL, entry ~4348.25, TP1 4340):
price drops to 4341 → trail SL to 4344; price hits TP1 4340 → SL to ~4343
(BE armed, trailing tighter); keeps trailing down from there.

## Tests
```bash
python tests/test_parser.py      # signal parsing
python tests/test_manager.py     # break-even + trailing logic
python tests/test_risk.py        # position sizing + realized-P&L accounting
# or: python -m pytest -q
```

## Limitations / next steps
- Multiple TPs are handled by **splitting the lot into one position per TP**,
  sharing the SL; break-even + trailing are layered on top (see above).
- Daily-loss limit reads realized P&L from MT5 deal history (live). In dry-run
  there are no broker fills, so the limit can't trigger there.
- The bot manages only orders it placed (tagged via `magic`).
- This executes financial trades automatically. Test on demo. Use at your own risk.
