# Windows Setup — gold-signal-bot

The bot is fully built and all your logins are already filled in. This is just
getting it running on the Windows laptop. Mostly double-clicking.

> MetaTrader 5 must run on the **same laptop** as the bot. Keep the laptop on
> while the bot runs.

---

## Step 1 — Copy the folder to Windows

Copy the whole `gold-signal-bot` folder from the Mac to the Windows Desktop
(zip it, send via USB/Drive, unzip on Windows).

- Keep the `.env` file inside it — it holds all your logins (already filled in).
- Delete the `.venv` folder before copying if it's there (Windows rebuilds it).

> Don't use `git clone` for this — the clone won't include `.env`, and you'd have
> to re-enter all the logins. Copy the folder instead.

---

## Step 2 — Install Python

1. Get Python 3.11+ : https://www.python.org/downloads/
2. Run it and **tick "Add python.exe to PATH"** on the first screen. Install.

---

## Step 3 — Open MetaTrader 5

1. Open MT5 and log into your demo account (the login/server are in your `.env`).
2. Click the **Algo Trading** button in the toolbar so it's **green (not red)**.

---

## Step 4 — Double-click `setup_windows.bat`

Installs everything. Wait for **"Setup complete."**

> "Python not found"? Reinstall Python with "Add to PATH" ticked, then try again.

---

## Step 5 — Double-click `check.bat`

Checks the broker connection, gold symbol, and price. **Places no orders.**

If it says gold is named something other than `XAUUSD` (e.g. `XAUUSD.m` or
`GOLD`), open `config.yaml`, change the `symbol:` line to that name, and save.

---

## Step 6 — Double-click `run.bat` (dry-run test)

- First time only: enter your **phone number** and the **code** Telegram sends you.
- You'll get a **🟢 up** message from your bot.
- Still in dry-run: signals show as ✅/❌ cards, but Approve only **logs** the
  trade — no real order yet. Watch a few signals to confirm it looks right.

---

## Step 7 — Go live on the DEMO account

1. Open `config.yaml`, change `dry_run: true` to **`dry_run: false`**, save.
2. Double-click `run.bat` again.

Now Approve actually places the demo trade with SL/TP, and break-even + trailing
stop run automatically. Use real money only after the demo works well for days.

---

## Everyday use

- **Start:** double-click `run.bat`
- **Stop:** close the black window, or make an empty file named `STOP` in the
  folder (instant halt; delete it to resume)
- **Change settings:** edit `config.yaml`, restart `run.bat`

---

## Already protecting you

- **Confirm-first** — nothing trades without your ✅
- **STOP file** — instant kill switch
- **Daily loss limit** — stops new trades after a set loss for the day
- **Sanity + staleness checks** — bad or too-late signals are skipped

---

## If something's off

| Problem | Fix |
|---|---|
| "Python not found" | Reinstall Python with **Add to PATH** ticked |
| `check.bat` connection fails | MT5 not open, or **Algo Trading is off** (must be green) |
| `check.bat` symbol not found | Set `symbol:` in `config.yaml` to the name it shows |
| No 🟢 message | Send your bot any message once so it can DM you |
| Bot runs but no signal cards | Wrong channel name — tell me, I'll help find the exact one |
| Approve does nothing visible | You're in dry-run (expected). Set `dry_run: false` for demo trades |

---

**Security:** rotate the bot token (@BotFather → `/revoke`) since it was shared in
chat, and paste the new one into `.env`. Never share or commit `.env`.
