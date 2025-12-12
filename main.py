#!/usr/bin/env python3
"""
Polymarket In-Efficiency Bot

A trading bot that exploits the lag between real-time Chainlink oracle
price feeds and Polymarket's CLOB order book updates for crypto prediction markets.

Usage:
    python main.py                  # Run the full bot
    python main.py --monitor-only   # Monitor without trading
    python main.py --telegram-only  # Run only Telegram bot
"""

import asyncio
import argparse
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Polymarket In-Efficiency Bot - Exploit price lag for profit"
    )

    parser.add_argument(
        "--monitor-only",
        action="store_true",
        help="Monitor prices and markets without trading"
    )

    parser.add_argument(
        "--telegram-only",
        action="store_true",
        help="Run only the Telegram bot interface"
    )

    parser.add_argument(
        "--enable-trading",
        action="store_true",
        help="Enable live trading (use with caution)"
    )

    parser.add_argument(
        "--config",
        type=str,
        default=".env",
        help="Path to config file (default: .env)"
    )

    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level"
    )

    return parser.parse_args()


async def main():
    """Main entry point."""
    args = parse_args()

    # Load environment variables
    env_path = Path(args.config)
    if env_path.exists():
        load_dotenv(env_path)
    else:
        print(f"Warning: Config file {args.config} not found")
        print("Create a .env file from config/.env.example")

    # Import after loading env
    from src.config import get_settings
    from src.orchestrator import Orchestrator
    from src.utils import setup_logging

    # Get settings
    settings = get_settings()

    # Override with command line args
    if args.log_level:
        settings.log_level = args.log_level

    if args.enable_trading:
        settings.trading_enabled = True

    # Setup logging
    setup_logging(settings.log_level, settings.log_file)

    from loguru import logger
    logger.info("=" * 60)
    logger.info("Polymarket In-Efficiency Bot")
    logger.info("=" * 60)
    logger.info(f"Mode: {'Monitor Only' if args.monitor_only else 'Full Bot'}")
    logger.info(f"Trading: {'Enabled' if settings.trading_enabled else 'Disabled'}")
    logger.info("=" * 60)

    # Create and run orchestrator
    orchestrator = Orchestrator(settings)

    try:
        await orchestrator.run()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise
    finally:
        await orchestrator.stop()


def run():
    """Synchronous entry point."""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBot stopped.")


if __name__ == "__main__":
    run()
