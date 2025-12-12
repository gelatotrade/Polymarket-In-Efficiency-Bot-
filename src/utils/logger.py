"""
Logging configuration using loguru.
"""

import sys
from pathlib import Path
from loguru import logger


def setup_logging(
    log_level: str = "INFO",
    log_file: str = "./logs/bot.log",
    rotation: str = "10 MB",
    retention: str = "7 days"
) -> None:
    """
    Setup logging configuration.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        log_file: Path to log file
        rotation: Log rotation size
        retention: Log retention period
    """
    # Remove default handler
    logger.remove()

    # Console handler with colors
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
               "<level>{level: <8}</level> | "
               "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
               "<level>{message}</level>",
        level=log_level,
        colorize=True
    )

    # File handler
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    logger.add(
        log_file,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}",
        level=log_level,
        rotation=rotation,
        retention=retention,
        compression="gz"
    )

    logger.info(f"Logging initialized (level={log_level}, file={log_file})")


def get_logger(name: str):
    """Get a logger instance."""
    return logger.bind(name=name)
