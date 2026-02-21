import asyncio
import logging
import sys

from loguru import logger


class _InterceptHandler(logging.Handler):
    """Route stdlib logging calls into loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1
        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def _setup_logging() -> None:
    logger.remove()
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>: <level>{message}</level>",
        level="INFO",
        colorize=True,
    )
    logger.add(
        "scroogebot.log",
        rotation="10 MB",
        retention="30 days",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}: {message}",
        level="DEBUG",
    )
    logging.basicConfig(handlers=[_InterceptHandler()], level=0, force=True)
    for noisy in ("httpx", "httpcore", "apscheduler.executors"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


_setup_logging()

from src.bot.bot import run  # noqa: E402

if __name__ == "__main__":
    asyncio.run(run())
