# Windows Setup — gold-signal-bot

Step-by-step to run the bot on a Windows laptop. The bot is already built; this
is just installing it and adding two Telegram values. Mostly double-clicking.

> The MetaTrader 5 terminal **must run on this same laptop** — the bot talks to
> it locally. Keep the laptop on while the bot is running.

---

## Step 1 — Copy the project folder to Windows

The project lives on the Mac at `~/Desktop/gold-signal-bot`. Move the **whole
folder** to the Windows laptop (Desktop is fine).

- Easiest: zip it on the Mac (right-click → Compress), transfer via Google Drive
  / USB stick, then unzip on Windows.
- The `.env` and `config.yaml` files **must** come along — they hold your
  settings and tokens. Zipping the whole folder includes them.
- Delete the `.venv` folder before zipping (it doesn't work across Mac↔Windows;
  `setup_windows.bat` rebuilds it). If you forget, no harm — just re-run setup.

---

## Step 2 — Install Python

1. Download Python 3.11 or newer: https://www.python.org/downloads/
2. Run the installer.
3. **On the first screen, tick "Add python.exe to PATH"** ← easy to miss, but required.
4. Click Install.

---

## Step 3 — Install / log into MetaTrader 5

1. If MT5 isn't installed, get it from your broker (or https://www.metatrader5.com).
2. Log into the demo account: **File → Login to Trade Account**, using the
   Login / Password / Server from your MT5 registration. These are the same
   values stored in your `.env` file (`MT5_LOGIN`, `MT5_PASSWORD`, `MT5_SERVER`).
3. Click the **Algo Trading** button in the toolbar so it is **green/on (NOT red)**.
   Orders are rejected when it's off.

---

## Step 4 — Run setup (double-click)

Open the `gold-signal-bot` folder and **double-click `setup_windows.bat`**.

It creates a virtual environment and installs everything (including the
Windows-only `MetaTrader5` package). Wait until it prints **"Setup complete."**

> If it says "Python not found", Python wasn't added to PATH in Step 2 — reinstall
> Python with the PATH box ticked, then run `setup_windows.bat` again.

---

## Step 5 — Add your Telegram API values

These are the only two things still missing.

1. Go to https://my.telegram.org and log in with your phone number.
2. Click **API development tools** → create an app (any name/short-name).
3. Copy the **api_id** and **api_hash** it shows you.
4. Open the `.env` file in the project folder (right-click → Open with → Notepad)
   and fill in these two lines:
   ```
   TG_API_ID=12345678
   TG_API_HASH=abc123def456...
   ```
5. Save and close. (Bot token, your Telegram ID, and MT5 login are already set.)

---

## Step 6 — Verify the broker (double-click `check.bat`)

**Double-click `check.bat`.** This places **no orders** — it only checks:

- the demo account connects,
- your gold symbol exists and is tradable,
- a live price,
- a sample position size against your balance.

**If it reports the gold symbol is named something other than `XAUUSD`**
(MetaQuotes-Demo sometimes uses `XAUUSD.m`, `GOLD`, etc.):
open `config.yaml`, find the line `symbol: "XAUUSD"`, and change it to exactly
what `check.bat` reported. Save.

---

## Step 7 — Start the bot in DRY-RUN (double-click `run.bat`)

**Double-click `run.bat`.**

- The **first time**, it asks for your **phone number** and a **login code**
  Telegram sends you (one-time, so it can read the channel as you).
- You'll get a **🟢 up** message from your bot in Telegram.
- It is still in **dry-run**: when a GABFXARMY signal arrives you get the
  ✅ Approve / ❌ Reject card, but tapping Approve only **logs** the trade — it
  does NOT send a real order yet.

Watch a few signals to confirm the parsing and the cards look correct.

---

## Step 8 — Go live on the DEMO account

When you're happy with dry-run:

1. Open `config.yaml`.
2. Change `dry_run: true` to **`dry_run: false`**. Save.
3. Double-click `run.bat` again.

Now tapping **Approve** actually places the trade on your **demo** account with
SL and TP, and break-even + trailing-stop management begins automatically.

> Only consider real money after the demo behaves correctly for several days,
> and start with a very small `risk_pct`.

---

## Everyday use

- **Start the bot:** double-click `run.bat`.
- **Stop the bot:** close the black window — OR create an empty file named `STOP`
  in the folder (instant kill switch; delete it to allow trading again).
- **Change risk / break-even / trailing settings:** edit `config.yaml`, restart `run.bat`.

---

## Safety features (already built in)

- **Confirm-first:** nothing trades without you tapping ✅.
- **Kill switch:** a file named `STOP` halts all execution immediately.
- **Daily loss limit:** once today's realized loss hits `daily_loss_limit` (in
  `config.yaml`), no new trades are placed until tomorrow.
- **Staleness guard:** signals where price already ran past TP1 are skipped.
- **Sanity check:** a garbled signal (SL/TP on the wrong side) is rejected, never traded.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| "Python not found" | Reinstall Python with **"Add to PATH"** ticked (Step 2). |
| `check.bat`: initialize failed | MT5 not open / wrong login / **Algo Trading off** (must be green). |
| `check.bat`: symbol not found | Set `symbol:` in `config.yaml` to the name it lists. |
| No 🟢 message in Telegram | Send your bot any message once so it can DM you; check `BOT_TOKEN`/`OWNER_ID` in `.env`. |
| Cards arrive but Approve does nothing visible | You're in dry-run — that's expected; it logs only. Flip `dry_run: false` for demo trades. |
| Orders rejected when live | Algo Trading off, wrong symbol, or market closed (gold trades ~Sun–Fri). |

---

## Security reminder

`BOT_TOKEN` was shared in chat during setup — rotate it: message **@BotFather**
→ `/revoke` → pick the bot → copy the new token into `.env`. Never commit `.env`
or share it.
