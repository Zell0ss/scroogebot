import asyncio
import logging
import logging.config
import yaml

with open("config/logging.yaml") as f:
    logging.config.dictConfig(yaml.safe_load(f))

from src.bot.bot import run

if __name__ == "__main__":
    asyncio.run(run())
