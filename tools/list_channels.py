"""List the Telegram channels/groups your account is in, so you can find the
signal source and its numeric id.

Run on the machine where you've already logged in (the `user.session` file
exists next to config.yaml):

    python tools/list_channels.py

It prints each chat's id, @username (if public), and title. Copy the id of the
signal channel into  config.yaml -> telegram.source_channel.  The numeric id is
the safest choice — it works even for PRIVATE channels that have no @username.

Stop run.bat (close its window) before running this, so they don't fight over
the same session file.
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telethon import TelegramClient          # noqa: E402

from bot.config import Config                 # noqa: E402


async def main():
    cfg = Config.load("config.yaml")
    client = TelegramClient(cfg.session_name, cfg.api_id, cfg.api_hash)
    await client.start()   # no prompt — uses the existing logged-in session

    print(f"{'id':>16}  {'username':<24} title")
    print("-" * 72)
    async for dialog in client.iter_dialogs():
        if dialog.is_channel or dialog.is_group:
            uname = getattr(dialog.entity, "username", None) or ""
            uname = ("@" + uname) if uname else ""
            print(f"{dialog.id:>16}  {uname:<24} {dialog.name}")

    print("\nFind your signal channel above, copy its id (the number on the left,")
    print("including any minus sign), and set it in config.yaml like:")
    print("    source_channel: -1001234567890")
    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
