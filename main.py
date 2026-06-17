"""Entrypoint: python main.py   (uses config.yaml + env vars for secrets)."""

import asyncio
import logging

from bot.app import TradingApp
from bot.config import Config


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    cfg = Config.load("config.yaml")
    app = TradingApp(cfg)
    asyncio.run(app.start())


if __name__ == "__main__":
    main()
